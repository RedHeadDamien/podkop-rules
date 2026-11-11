"""Registry, strict plain-text formats and safe file operations."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import date
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def cli(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--root', type=Path, default=ROOT)
    return parser


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'{path}: duplicate JSON key: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def https_url(value):
    url = urlsplit(value)
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
        raise ValueError(f'Expected public HTTPS URL: {value}')
    return value


def load_config(root):
    registry = read_json(root / 'services.json')
    sources = read_json(root / 'sources/sources.json')
    if registry.get('schema_version') != 1 or sources.get('schema_version') != 1:
        raise ValueError('Unsupported schema_version')
    services = registry.get('services')
    evidence = sources.get('sources')
    if not isinstance(services, dict) or not services or not isinstance(evidence, dict):
        raise ValueError('Expected nonempty services and sources objects')
    paths = set()
    for sid, service in services.items():
        if not re.fullmatch(r'[a-z][a-z0-9_-]*', sid) or sid == 'all':
            raise ValueError(f'Invalid service id: {sid}')
        if not isinstance(service, dict):
            raise ValueError(f'{sid}: expected service object')
        for flag in ('enabled', 'auto_update'):
            if type(service.get(flag)) is not bool:
                raise ValueError(f'{sid}: {flag} must be boolean')
        for kind in ('domains', 'subnets'):
            expected = f'{kind}/{sid}.txt'
            if service.get(kind) != expected:
                raise ValueError(f'{sid}: {kind} must be {expected}')
            path = root / expected
            if not path.is_file() or path.is_symlink() or path.resolve().parent != (root / kind).resolve():
                raise ValueError(f'{sid}: missing or unsafe file {expected}')
            if expected in paths:
                raise ValueError(f'Duplicate path: {expected}')
            paths.add(expected)
        ids = service.get('sources')
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            raise ValueError(f'{sid}: expected unique source IDs')
        for source_id in ids:
            if source_id not in evidence or evidence[source_id].get('service') != sid:
                raise ValueError(f'{sid}: unknown or mismatched source {source_id}')
        updates = [evidence[i] for i in ids if evidence[i].get('auto_update')]
        if service['auto_update'] != bool(updates):
            raise ValueError(f'{sid}: auto_update must match available automated sources')
    for source_id, source in evidence.items():
        sid = source.get('service')
        if sid not in services or source_id not in services[sid]['sources']:
            raise ValueError(f'Orphan source: {source_id}')
        for key in ('url', 'data_type', 'trust', 'method', 'last_checked', 'last_updated', 'auto_update', 'records', 'notes'):
            if key not in source:
                raise ValueError(f'{source_id}: missing {key}')
        https_url(source['url'])
        if source['data_type'] not in ('domains', 'subnets', 'context'):
            raise ValueError(f'{source_id}: invalid data_type')
        if source['trust'] not in ('official', 'primary-research'):
            raise ValueError(f'{source_id}: unsupported trust')
        for key in ('last_checked', 'last_updated'):
            if source[key] is not None:
                date.fromisoformat(source[key])
        if type(source['auto_update']) is not bool or not isinstance(source['records'], list):
            raise ValueError(f'{source_id}: invalid source fields')
        if not isinstance(source['notes'], str) or not source['notes']:
            raise ValueError(f'{source_id}: source limitations/notes required')
        if source['data_type'] == 'context':
            if source['records']:
                raise ValueError(f'{source_id}: context source cannot approve routes')
        elif source['records'] != normalize(source['records'], source['data_type']):
            raise ValueError(f'{source_id}: records must be canonical, sorted and unique')
        if source['method'] not in ('https-cidr', 'manual-review'):
            raise ValueError(f'{source_id}: unsupported source method')
        if source['auto_update'] and (source['method'] != 'https-cidr' or source['data_type'] != 'subnets'):
            raise ValueError(f'{source_id}: unsupported automatic parser')
    return services, sources


def domain(value):
    if not isinstance(value, str) or len(value) > 253 or value != value.lower():
        raise ValueError(f'Invalid domain: {value!r}')
    labels = value.split('.')
    if len(labels) < 2 or not all(LABEL.fullmatch(label) for label in labels) or labels[-1].isdigit():
        raise ValueError(f'Invalid domain: {value!r}')
    return value


def subnet(value, *, allow_ipv6=False):
    if '/' not in value:
        raise ValueError(f'CIDR prefix required: {value}')
    network = ipaddress.ip_network(value, strict=True)
    if str(network) != value:
        raise ValueError(f'Noncanonical CIDR: {value}')
    if network.version == 6 and not allow_ipv6:
        raise ValueError(f'IPv6 unsupported by Podkop 0.7.22 plain lists: {value}')
    if not network.network_address.is_global or not network.broadcast_address.is_global:
        raise ValueError(f'Non-public or special network: {value}')
    # Reject public-looking supernets that contain special-use address space.
    special = ('0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
               '169.254.0.0/16', '172.16.0.0/12', '192.0.0.0/24', '192.0.2.0/24',
               '192.168.0.0/16', '198.18.0.0/15', '198.51.100.0/24',
               '203.0.113.0/24', '224.0.0.0/3')
    if network.version == 4 and any(network.overlaps(ipaddress.ip_network(n)) for n in special):
        raise ValueError(f'Network overlaps special-use space: {value}')
    if network.prefixlen < (16 if network.version == 4 else 32):
        raise ValueError(f'Network too broad; requires separate policy review: {value}')
    return value


def normalize(values, kind):
    check = domain if kind == 'domains' else subnet
    result = sorted({check(value) for value in values})
    if kind == 'subnets':
        nets = sorted((ipaddress.ip_network(n) for n in result), key=lambda n: (n.version, int(n.network_address), n.prefixlen))
        for left, right in zip(nets, nets[1:]):
            if left.version == right.version and left.overlaps(right):
                raise ValueError(f'Overlapping CIDRs: {left}, {right}')
    return result


def encode(values):
    return (''.join(f'{value}\n' for value in values)).encode('ascii')


def read_list(path, kind, *, strict=True):
    raw = path.read_bytes()
    try:
        text = raw.decode('ascii')
        lines = text.splitlines()
        result = normalize(lines, kind)
        if strict and raw != encode(result):
            raise ValueError('Expected sorted unique ASCII records with LF and final newline; no blank lines/comments')
        return result
    except ValueError as exc:
        raise ValueError(f'{path}: {exc}') from exc


def atomic_write(path, content):
    """Replace one complete file; preserve bytes and mtime on no-op."""
    if path.exists() and path.read_bytes() == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.', suffix='.tmp', delete=False) as handle:
            name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return True


def combined(root, services, overrides=None):
    overrides = overrides or {}
    outputs = {}
    for kind in ('domains', 'subnets'):
        values = []
        for sid, service in services.items():
            if service['enabled']:
                key = (sid, kind)
                values.extend(overrides[key] if key in overrides else read_list(root / service[kind], kind, strict=False))
        outputs[kind] = normalize(values, kind)
    return outputs


def validate(root, *, check_combined=True, overrides=None, source_document=None):
    services, document = load_config(root)
    document = source_document or document
    evidence = document['sources']
    overrides = overrides or {}
    for sid, service in services.items():
        for kind in ('domains', 'subnets'):
            key = (sid, kind)
            values = overrides[key] if key in overrides else read_list(root / service[kind], kind)
            approved = {record for i in service['sources'] for record in evidence[i]['records'] if evidence[i]['data_type'] == kind}
            missing = set(values) - approved
            if missing:
                raise ValueError(f'{sid}/{kind}: records without source evidence: {sorted(missing)}')
    outputs = combined(root, services, overrides)
    if check_combined:
        for kind, values in outputs.items():
            path = root / kind / 'all.txt'
            actual = read_list(path, kind)
            if actual != values:
                raise ValueError(f'{path}: stale combined list; run build_lists.py')
    return outputs


def run(main):
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise SystemExit(f'ERROR: {exc}') from exc

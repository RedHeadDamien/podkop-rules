"""Refresh approved CIDR feeds; retain existing records pending manual removal review."""
from datetime import datetime, timezone
import copy
import ipaddress
import json
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
try:
    from .common import cli, load_config, read_list, normalize, validate, encode, atomic_write, run
except ImportError:
    from common import cli, load_config, read_list, normalize, validate, encode, atomic_write, run

MAX_BYTES = 1024 * 1024


def fetch(url):
    last_error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={'User-Agent': 'Podkop-Rules/1.0', 'Accept': 'text/plain'})
            with urlopen(request, timeout=20) as response:
                final = urlsplit(response.url)
                if final.scheme != 'https' or final.hostname != urlsplit(url).hostname:
                    raise ValueError('Unexpected redirect destination')
                if response.status != 200:
                    raise ValueError(f'Unexpected HTTP status {response.status}')
                mime = response.headers.get_content_type()
                if mime not in ('text/plain', 'application/octet-stream'):
                    raise ValueError(f'Unexpected Content-Type: {mime}')
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError('Source response exceeds size limit')
                return data.decode('utf-8')
        except (OSError, ValueError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise ValueError(f'Source unavailable: {last_error}')


def parse_cidrs(text):
    values, skipped = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if '/' not in line:
            raise ValueError(f'Non-CIDR source line: {line!r}')
        network = ipaddress.ip_network(line, strict=True)
        if network.version == 6:
            # Validate IPv6 syntax; deliberately exclude from 0.7.22 output.
            skipped.append(str(network))
        else:
            values.append(str(network))
    result = normalize(values, 'subnets')
    if not result:
        raise ValueError('Empty IPv4 source; keeping last known good list')
    return result, sorted(set(skipped))


def update(root, downloader=fetch, today=None):
    validate(root)
    services, document = load_config(root)
    today = today or datetime.now(timezone.utc).date().isoformat()
    report = {'services': {}, 'errors': []}
    overrides = {}
    for sid, service in services.items():
        if not service['enabled'] or not service['auto_update']:
            report['services'][sid] = {'status': 'manual' if service['enabled'] else 'disabled'}
            continue
        candidate = copy.deepcopy(document)
        staged = dict(overrides)
        changes = []
        try:
            for source_id in service['sources']:
                source = candidate['sources'][source_id]
                if not source['auto_update']:
                    continue
                values, skipped = parse_cidrs(downloader(source['url']))
                kind = source['data_type']
                previous = staged.get((sid, kind))
                if previous is None:
                    previous = read_list(root / service[kind], kind)
                # An unavailable/partial feed never silently deletes working routes.
                retained = normalize(previous + values, kind)
                staged[(sid, kind)] = retained
                source['records'] = sorted(set(source['records']) | set(values))
                source['last_checked'] = today
                if retained != previous:
                    source['last_updated'] = today
                changes.append({'source': source_id, 'added': sorted(set(values) - set(previous)),
                                'removal_candidates': sorted(set(previous) - set(values)), 'excluded_ipv6': skipped})
            validate(root, check_combined=False, overrides=staged, source_document=candidate)
            document, overrides = candidate, staged
            report['services'][sid] = {'status': 'ok', 'changes': changes}
        except (ValueError, OSError) as exc:
            report['errors'].append(f'{sid}: {exc}')
            report['services'][sid] = {'status': 'kept-last-good', 'error': str(exc)}
    outputs = validate(root, check_combined=False, overrides=overrides, source_document=document)
    # Validate everything before the first write. Each replacement is atomic;
    # GitHub publishes the complete validated snapshot as one commit.
    for (sid, kind), values in overrides.items():
        atomic_write(root / services[sid][kind], encode(values))
    atomic_write(root / 'sources/sources.json', (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    for kind, values in outputs.items():
        atomic_write(root / kind / 'all.txt', encode(values))
    validate(root)
    return report


def main():
    parser = cli(__doc__)
    parser.add_argument('--report', type=str, help='Optional JSON report file')
    args = parser.parse_args()
    report = update(args.root)
    payload = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if args.report:
        from pathlib import Path
        atomic_write(Path(args.report), payload)
    print(payload.decode('utf-8'))
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    run(main)

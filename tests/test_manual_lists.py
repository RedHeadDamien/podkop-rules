import ipaddress
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.common import ROOT, combined, load_config, normalize, read_json, read_list, remove_covered_subnets, subnet, validate


class ManualListTests(unittest.TestCase):
    def test_kinopub_coverage_preserved(self):
        services, _ = load_config(ROOT)
        service = services['kinopub']
        submitted = read_json(ROOT / 'sources/manual/kinopub.json')['subnets']
        published = read_list(ROOT / service['subnets'], 'subnets', broad_subnets=service['broad_subnets'])
        def coverage(values):
            return list(ipaddress.collapse_addresses(ipaddress.ip_network(value) for value in values))
        self.assertEqual(coverage(submitted), coverage(published))
        self.assertEqual(len(submitted), 52)
        self.assertEqual(len(published), 37)
        self.assertEqual(len(submitted) - len(published), 15)

    def test_broad_exceptions_are_exact(self):
        allowed = ['57.0.0.0/8']
        self.assertEqual(subnet(allowed[0], broad_subnets=allowed), allowed[0])
        with self.assertRaises(ValueError):
            subnet(allowed[0])
        with self.assertRaises(ValueError):
            subnet('52.0.0.0/10', broad_subnets=allowed)

    def test_exception_does_not_allow_private_or_overlap(self):
        with self.assertRaises(ValueError):
            subnet('10.0.0.0/8', broad_subnets=['10.0.0.0/8'])
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            normalize(['57.0.0.0/8', '57.1.0.0/16'], 'subnets', broad_subnets=['57.0.0.0/8'])

    def test_unverified_sources_are_explicit(self):
        _, document = load_config(ROOT)
        for source_id in ('kinopub-user-domains', 'kinopub-user-subnets'):
            source = document['sources'][source_id]
            self.assertEqual(source['trust'], 'user-supplied')
            self.assertIsNone(source['last_checked'])
            self.assertIsNone(source['url'])
            self.assertFalse(source['auto_update'])
            self.assertEqual(source['method'], 'user-input')

    def test_missing_snapshot_and_missing_exception_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for folder in ('domains', 'subnets', 'sources'):
                shutil.copytree(ROOT / folder, root / folder)
            shutil.copy(ROOT / 'services.json', root)
            snapshot = root / 'sources/manual/kinopub.json'
            original = snapshot.read_bytes()
            snapshot.unlink()
            with self.assertRaisesRegex(ValueError, 'snapshot'):
                validate(root)
            snapshot.write_bytes(original)
            registry = read_json(root / 'services.json')
            registry['services']['kinopub']['broad_subnets'] = []
            (root / 'services.json').write_text(json.dumps(registry), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'too broad'):
                validate(root)

    def test_disabled_manual_service_does_not_enter_unions(self):
        from scripts.common import combined
        services, _ = load_config(ROOT)
        services['kinopub']['enabled'] = False
        result = combined(ROOT, services)
        self.assertNotIn('kino.pub', result['domains'])
        self.assertNotIn('57.0.0.0/8', result['subnets'])

    def test_albion_ips_are_exact_user_observations(self):
        services, document = load_config(ROOT)
        snapshot = read_json(ROOT / 'sources/manual/albion.json')
        values = read_list(ROOT / services['albion']['subnets'], 'subnets')
        self.assertEqual(len(values), 17)
        self.assertEqual(values, snapshot['subnets'])
        self.assertEqual(set(values), set(snapshot['ip_evidence']))
        self.assertTrue(all(ipaddress.ip_network(value).prefixlen == 32 for value in values))
        source = document['sources']['albion-user-capture-subnets']
        self.assertEqual(source['trust'], 'user-supplied')
        self.assertFalse(source['auto_update'])

    def test_combined_subnet_coverage_and_disabled_parent(self):
        services, _ = load_config(ROOT)
        values = [value for service in services.values() if service['enabled'] and 'subnets' in service
                  for value in read_list(ROOT / service['subnets'], 'subnets', broad_subnets=service.get('broad_subnets', []))]
        output = combined(ROOT, services)['subnets']
        def coverage(items):
            return list(ipaddress.collapse_addresses(ipaddress.ip_network(value) for value in items))
        self.assertEqual(coverage(values), coverage(output))
        self.assertNotIn('57.129.90.115/32', output)
        services['kinopub']['enabled'] = False
        output = combined(ROOT, services)['subnets']
        self.assertIn('57.129.90.115/32', output)
        self.assertNotIn('57.0.0.0/8', output)

    def test_covered_subnet_removal_does_not_merge_adjacent(self):
        values = ['91.108.4.0/24', '91.108.5.0/24', '91.108.4.1/32', '91.108.4.0/24']
        self.assertEqual(remove_covered_subnets(values), ['91.108.4.0/24', '91.108.5.0/24'])

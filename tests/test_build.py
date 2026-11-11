from pathlib import Path
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
from scripts.common import ROOT, atomic_write, read_json, validate
from scripts.build_lists import build
from scripts.update_lists import update, fetch


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('domains', 'subnets', 'sources'):
            shutil.copytree(ROOT / name, self.root / name)
        shutil.copy(ROOT / 'services.json', self.root)

    def edit_json(self, relative, mutate):
        path = self.root / relative
        doc = read_json(path)
        mutate(doc)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}

    def test_repository_valid(self):
        validate(self.root)
        build(self.root, check=True)

    def test_idempotent(self):
        before = self.snapshot()
        build(self.root)
        build(self.root)
        self.assertEqual(before, self.snapshot())

    def test_disabled_service(self):
        self.edit_json('services.json', lambda d: d['services']['twitch'].update(enabled=False))
        build(self.root)
        validate(self.root)
        self.assertNotIn('twitch.tv', (self.root / 'domains/all.txt').read_text())

    def test_empty_lists(self):
        (self.root / 'domains/albion.txt').write_bytes(b'')
        build(self.root)
        validate(self.root)

    def test_stale_union(self):
        (self.root / 'domains/all.txt').write_bytes(b'')
        with self.assertRaises(ValueError):
            validate(self.root)

    def test_build_deduplicates(self):
        (self.root / 'domains/telegram.txt').write_bytes(b't.me\nt.me\ntelegram.org\n')
        build(self.root)
        self.assertEqual((self.root / 'domains/all.txt').read_text().splitlines().count('t.me'), 1)
        with self.assertRaises(ValueError):
            validate(self.root)

    def test_unknown_provenance(self):
        (self.root / 'domains/albion.txt').write_bytes(b'unknown.com\n')
        with self.assertRaisesRegex(ValueError, 'without source evidence'):
            validate(self.root)

    def test_invalid_registry(self):
        mutations = [lambda d: d['services']['albion'].update(enabled='true'),
                     lambda d: d['services']['albion'].update(domains='../secret'),
                     lambda d: d['services']['albion'].update(subnets=None),
                     lambda d: d['services']['albion'].update(subnets='../secret'),
                     lambda d: d['services']['albion'].update(sources=['unknown']),
                     lambda d: d['services']['albion'].update(auto_update=True)]
        original = (self.root / 'services.json').read_bytes()
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                (self.root / 'services.json').write_bytes(original)
                self.edit_json('services.json', mutation)
                with self.assertRaises(ValueError):
                    validate(self.root)

    def test_duplicate_json_key(self):
        (self.root / 'services.json').write_text('{"services": {}, "services": {}}')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON'):
            validate(self.root)

    def test_missing_file(self):
        (self.root / 'subnets/telegram.txt').unlink()
        with self.assertRaises(ValueError):
            validate(self.root)

    def test_bad_list_never_overwrites_union(self):
        before = (self.root / 'domains/all.txt').read_bytes()
        (self.root / 'subnets/telegram.txt').write_text('BAD\n')
        with self.assertRaises(ValueError):
            build(self.root)
        self.assertEqual(before, (self.root / 'domains/all.txt').read_bytes())

    def test_atomic_failure_keeps_original(self):
        path = self.root / 'domains/all.txt'
        before = path.read_bytes()
        with patch('scripts.common.os.replace', side_effect=OSError('injected failure')):
            with self.assertRaises(OSError):
                atomic_write(path, b'new\n')
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(list(path.parent.glob('*.tmp')), [])

    def test_source_failures_keep_everything(self):
        for response in ('', '<html>error</html>', '10.0.0.0/8', '91.108.4.0/22\nBAD'):
            before = self.snapshot()
            result = update(self.root, downloader=lambda url: response, today='2026-11-11')
            self.assertTrue(result['errors'])
            self.assertEqual(before, self.snapshot())

    def test_offline(self):
        before = self.snapshot()
        def offline(url):
            raise OSError('offline')
        result = update(self.root, downloader=offline)
        self.assertTrue(result['errors'])
        self.assertEqual(before, self.snapshot())

    def test_update_adds_and_retains_missing(self):
        result = update(self.root, downloader=lambda url: '91.108.4.0/22\n91.108.24.0/22\n', today='2026-11-11')
        self.assertFalse(result['errors'])
        self.assertIn('91.108.24.0/22', (self.root / 'subnets/telegram.txt').read_text())
        self.assertIn('149.154.160.0/20', (self.root / 'subnets/telegram.txt').read_text())
        self.assertTrue(result['services']['telegram']['changes'][0]['removal_candidates'])
        validate(self.root)
        before = self.snapshot()
        update(self.root, downloader=lambda url: '91.108.4.0/22\n91.108.24.0/22\n', today='2026-11-11')
        self.assertEqual(before, self.snapshot())

    def test_network_retries(self):
        with patch('scripts.update_lists.urlopen', side_effect=OSError('offline')) as mocked, patch('scripts.update_lists.time.sleep'):
            with self.assertRaisesRegex(ValueError, 'Source unavailable'):
                fetch('https://core.telegram.org/resources/cidr.txt')
            self.assertEqual(mocked.call_count, 3)

    def test_one_service_fails_other_can_update(self):
        self.edit_json('services.json', lambda d: d['services']['twitch'].update(auto_update=True, subnets='subnets/twitch.txt', sources=d['services']['twitch']['sources'] + ['test-feed']))
        (self.root / 'subnets/twitch.txt').write_bytes(b'')
        self.edit_json('sources/sources.json', lambda d: d['sources'].update({'test-feed': dict(service='twitch', url='https://example.com/feed.txt', data_type='subnets', trust='official', method='https-cidr', last_checked=None, last_updated=None, auto_update=True, records=[], notes='Test fixture only')}))
        previous = (self.root / 'subnets/telegram.txt').read_bytes()
        def downloader(url):
            if 'telegram.org' in url:
                raise OSError('offline')
            return '8.8.8.8/32\n'
        result = update(self.root, downloader=downloader, today='2026-11-11')
        self.assertTrue(result['errors'])
        self.assertEqual(previous, (self.root / 'subnets/telegram.txt').read_bytes())
        self.assertEqual((self.root / 'subnets/twitch.txt').read_bytes(), b'8.8.8.8/32\n')
        validate(self.root)

    def test_source_schema_and_records(self):
        original = (self.root / 'sources/sources.json').read_bytes()
        mutations = [lambda d: d['sources']['telegram-api'].update(last_checked='not-a-date'),
                     lambda d: d['sources']['telegram-api'].update(records=['https://telegram.org']),
                     lambda d: d['sources']['telegram-api'].update(url='http://example.com'),
                     lambda d: d['sources']['telegram-api'].update(service='unknown')]
        for mutate in mutations:
            (self.root / 'sources/sources.json').write_bytes(original)
            self.edit_json('sources/sources.json', mutate)
            with self.assertRaises(ValueError):
                validate(self.root)

    def test_file_encoding_and_line_endings(self):
        for data in (b't.me\r\n', b'\xef\xbb\xbft.me\n', b't.me', b'# comment\nt.me\n', b't.me\n\n'):
            (self.root / 'domains/telegram.txt').write_bytes(data)
            with self.assertRaises(ValueError):
                validate(self.root)

    def test_http_response_guards(self):
        from email.message import Message
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.url = 'https://core.telegram.org/resources/cidr.txt'
        response.status = 200
        response.headers = Message()
        response.headers['Content-Type'] = 'text/html'
        with patch('scripts.update_lists.urlopen', return_value=response), patch('scripts.update_lists.time.sleep'):
            with self.assertRaisesRegex(ValueError, 'Content-Type'):
                fetch(response.url)

    def test_new_service_discovered(self):
        self.edit_json('services.json', lambda d: d['services'].update(example=dict(enabled=True, auto_update=False, domains='domains/example.txt', sources=['example-source'])))
        self.edit_json('sources/sources.json', lambda d: d['sources'].update({'example-source': dict(service='example', url='https://example.com/', data_type='domains', trust='official', method='manual-review', last_checked='2026-11-11', last_updated='2026-11-11', auto_update=False, records=['example.com'], notes='Test fixture only')}))
        (self.root / 'domains/example.txt').write_bytes(b'example.com\n')
        build(self.root)
        validate(self.root)
        self.assertIn('example.com', (self.root / 'domains/all.txt').read_text())
        self.assertFalse((self.root / 'subnets/example.txt').exists())

    def test_domains_only_services_survive_build_and_update(self):
        def no_network(url):
            raise OSError('offline')
        build(self.root)
        validate(self.root)
        update(self.root, downloader=no_network)
        for sid in ('twitch',):
            self.assertFalse((self.root / f'subnets/{sid}.txt').exists())

    def test_all_services_can_omit_subnets(self):
        registry = read_json(self.root / 'services.json')
        document = read_json(self.root / 'sources/sources.json')
        for service in registry['services'].values():
            service.pop('subnets', None)
            service.pop('broad_subnets', None)
            service['auto_update'] = False
            service['sources'] = [i for i in service['sources'] if document['sources'][i]['data_type'] != 'subnets']
        document['sources'] = {i: s for i, s in document['sources'].items() if s['data_type'] != 'subnets'}
        (self.root / 'services.json').write_text(json.dumps(registry), encoding='utf-8')
        (self.root / 'sources/sources.json').write_text(json.dumps(document), encoding='utf-8')
        build(self.root)
        validate(self.root)
        self.assertEqual((self.root / 'subnets/all.txt').read_bytes(), b'')

    def test_subnet_source_cannot_create_an_unrequested_list(self):
        self.edit_json('services.json', lambda d: d['services']['twitch'].update(auto_update=True, sources=d['services']['twitch']['sources'] + ['test-feed']))
        self.edit_json('sources/sources.json', lambda d: d['sources'].update({'test-feed': dict(service='twitch', url='https://example.com/feed.txt', data_type='subnets', trust='official', method='https-cidr', last_checked=None, last_updated=None, auto_update=True, records=[], notes='Test fixture only')}))
        with self.assertRaisesRegex(ValueError, 'requires a registered list'):
            update(self.root, downloader=lambda url: '8.8.8.8/32\n')
        self.assertFalse((self.root / 'subnets/twitch.txt').exists())

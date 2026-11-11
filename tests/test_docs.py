import re
import unittest
from scripts.common import ROOT, load_config, read_list


class DocumentationTests(unittest.TestCase):
    def test_local_markdown_links(self):
        for path in [ROOT / 'README.md', ROOT / 'AGENTS.md', *sorted((ROOT / 'docs').glob('*.md'))]:
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' in target or target.startswith('#'):
                    continue
                relative = target.split('#')[0]
                with self.subTest(document=path.name, target=target):
                    self.assertTrue((path.parent / relative).is_file())

    def test_readme_statistics_match_registry(self):
        services, _ = load_config(ROOT)
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        for sid, service in services.items():
            counts = [len(read_list(ROOT / service[kind], kind, broad_subnets=service.get('broad_subnets', [])))
                      if kind in service else 0 for kind in ('domains', 'subnets')]
            self.assertIn(f'| {service.get("name", sid)} | {counts[0]} | {counts[1]} |', readme)

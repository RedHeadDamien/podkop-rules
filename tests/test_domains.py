import unittest
from scripts.common import domain, normalize


class DomainTests(unittest.TestCase):
    def test_valid_domains(self):
        for item in ('t.me', 'api.telegram.org', 'xn--e1afmkfd.xn--p1ai', 'live03-loginserver.ams.albion.zone'):
            self.assertEqual(domain(item), item)

    def test_invalid(self):
        for item in ('https://t.me', 't.me/path', '*.t.me', '.t.me', 'a..com', 'a.com ',
                     'A.com', '-a.com', 'a-.com', 'localhost', '127.0.0.1', 'a'*64+'.com', 'тест.рф', 'a.com:443', '#comment'):
            with self.subTest(item=item), self.assertRaises(ValueError):
                domain(item)

    def test_sort_deduplicate(self):
        self.assertEqual(normalize(['z.com', 'a.com', 'a.com'], 'domains'), ['a.com', 'z.com'])

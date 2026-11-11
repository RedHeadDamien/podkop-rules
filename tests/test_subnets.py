import unittest
from scripts.common import subnet, normalize
from scripts.update_lists import parse_cidrs


class SubnetTests(unittest.TestCase):
    def test_ipv4(self):
        self.assertEqual(subnet('149.154.160.0/20'), '149.154.160.0/20')

    def test_ipv6_parse_and_compatibility(self):
        self.assertEqual(subnet('2001:b28:f23d::/48', allow_ipv6=True), '2001:b28:f23d::/48')
        with self.assertRaisesRegex(ValueError, 'IPv6 unsupported'):
            subnet('2001:b28:f23d::/48')
        with self.assertRaises(ValueError):
            subnet('2001:zzzz::/48', allow_ipv6=True)

    def test_reject_unsafe_and_noncanonical(self):
        for item in ('0.0.0.0/0', '10.0.0.0/8', '127.0.0.0/8', '192.168.1.0/24',
                     '224.0.0.0/4', '100.64.0.0/10', '192.0.2.0/24', '149.154.160.1/20',
                     '149.154.160.0', '91.108.4.0/33', '8.0.0.0/8'):
            with self.subTest(item=item), self.assertRaises(ValueError):
                subnet(item)

    def test_overlaps(self):
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            normalize(['149.154.160.0/20', '149.154.160.0/24'], 'subnets')

    def test_never_widen(self):
        values = ['91.108.4.0/24', '91.108.6.0/24']
        self.assertEqual(normalize(values + values, 'subnets'), values)

    def test_source_filter_ipv6(self):
        self.assertEqual(parse_cidrs('91.108.4.0/22\r\n2001:b28:f23d::/48\n'),
                         (['91.108.4.0/22'], ['2001:b28:f23d::/48']))

    def test_bad_feeds(self):
        for text in ('', '\n', '<html>error</html>', '2001:b28:f23d::/48', '10.0.0.0/8', '91.108.4.0/22\nBAD', 'garbage::/48'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_cidrs(text)

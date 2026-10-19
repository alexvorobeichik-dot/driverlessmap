"""Tests for Driverless Map.

The site is a reference, so most of what can go wrong is a data problem rather
than a code problem. The tests reflect that: the sourcing rule is enforced
mechanically, and the distinction between driverless and supervised services is
asserted rather than trusted.

Run with:  python -m unittest test_site.py -v
"""
import http.client
import os
import sys
import threading
import unittest
import xml.etree.ElementTree
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ['SITE_URL'] = 'https://driverlessmap.com'

import server  # noqa: E402  (must follow the environment setup)


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.httpd.daemon_threads = True
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        try:
            conn.request('GET', path)
            resp = conn.getresponse()
            body = resp.read().decode('utf-8', 'replace')
            headers = {k.lower(): v for k, v in resp.getheaders()}
            return resp.status, headers, body
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # the rules that keep this site worth reading
    # ------------------------------------------------------------------
    def test_every_row_carries_a_named_source(self):
        # The site's only value is that it can be cited. One unsourced figure
        # would undermine the whole thing, so this is a build failure.
        groups = {
            'cities': server.CITIES,
            'supervised': server.SUPERVISED,
            'up_next': server.UP_NEXT,
            'operators': server.OPERATORS,
            'regulations': server.REGULATIONS,
        }
        for group_name, rows in groups.items():
            for row in rows:
                label = row.get('city') or row.get('market') or row.get('name') or row.get('jurisdiction')
                with self.subTest(group=group_name, row=label):
                    self.assertTrue(row.get('source', '').startswith('https://'),
                                    f'{group_name}/{label} needs a source URL')
                    self.assertTrue(row.get('source_name'),
                                    f'{group_name}/{label} needs a named source')

    def test_supervised_services_are_not_counted_as_driverless(self):
        # Tesla's Bay Area service runs with a safety monitor. If it ever leaks
        # into the main table, the site is overstating what is driverless.
        for row in server.CITIES:
            with self.subTest(city=row['city'], operator=row['operator']):
                self.assertFalse(
                    row['operator'] == 'Tesla' and 'Bay Area' in row['city'],
                    'a safety-monitored service must not appear in the driverless table')

    def test_the_three_operators_with_public_service_are_all_present(self):
        operators = {row['operator'] for row in server.CITIES}
        self.assertEqual(operators, {'Waymo', 'Zoox', 'Tesla'})

    def test_every_city_appears_with_a_since_date(self):
        for row in server.CITIES:
            with self.subTest(city=row['city'], operator=row['operator']):
                self.assertTrue(row['since'].strip(), 'a city needs a start date')

    # ------------------------------------------------------------------
    # pages
    # ------------------------------------------------------------------
    def test_healthz(self):
        status, _, body = self.get('/healthz')
        self.assertEqual(status, 200)
        self.assertEqual(body, 'ok')

    def test_home_lists_every_city_and_operator(self):
        status, _, body = self.get('/')
        self.assertEqual(status, 200)
        for row in server.CITIES:
            with self.subTest(city=row['city'], operator=row['operator']):
                self.assertIn(row['city'], body)
                self.assertIn(row['operator'], body)
        self.assertIn('Not driverless', body)
        self.assertIn('Announced, not yet carrying passengers', body)

    def test_operators_page_covers_all_four(self):
        status, _, body = self.get('/operators')
        self.assertEqual(status, 200)
        for name in ('Waymo', 'Zoox', 'Tesla', 'Uber'):
            with self.subTest(operator=name):
                self.assertIn(name, body)
        self.assertIn('Part 555', body)

    def test_regulations_page_names_the_audit_query(self):
        status, _, body = self.get('/regulations')
        self.assertEqual(status, 200)
        self.assertIn('AQ26002', body)
        self.assertIn('exemption', body)

    def test_about_page_states_the_sourcing_rule(self):
        status, _, body = self.get('/about')
        self.assertEqual(status, 200)
        self.assertIn('every claim', body.lower())

    def test_every_page_has_canonical_and_a_title(self):
        for path, label, _ in server.PAGES:
            with self.subTest(path=path):
                _, _, body = self.get(path)
                self.assertIn(f'<link rel="canonical" href="{server.SITE_URL}{path}">', body)
                self.assertIn('<title>', body)
                self.assertIn(f'>{label}<', body, 'the nav should mark this page')

    def test_unknown_path_returns_a_real_404(self):
        # Returning 200 here would be a soft 404: crawlers would index junk URLs
        # and spend crawl budget on them instead of on the pages that matter.
        status, _, body = self.get('/nonsense')
        self.assertEqual(status, 404)
        self.assertIn('Not found', body)

    def test_healthz_is_disallowed_for_crawlers(self):
        status, _, body = self.get('/robots.txt')
        self.assertEqual(status, 200)
        self.assertIn('Disallow: /healthz', body)
        self.assertIn(f'Sitemap: {server.SITE_URL}/sitemap.xml', body)

    def test_sitemap_lists_every_page_and_parses(self):
        status, headers, body = self.get('/sitemap.xml')
        self.assertEqual(status, 200)
        self.assertIn('xml', headers['content-type'])
        root = xml.etree.ElementTree.fromstring(body)
        locations = [e.text for e in root.iter('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
        self.assertEqual(len(locations), len(server.PAGES))
        for path, _, _ in server.PAGES:
            self.assertIn(server.SITE_URL + path, locations)

    def test_chart_renders_from_the_fleet_series(self):
        _, _, body = self.get('/')
        self.assertIn('class="chart"', body)
        self.assertIn('role="img"', body)
        for label, value in server.FLEET_SERIES:
            with self.subTest(point=label):
                self.assertIn(label, body)
                self.assertIn(f'>{value}<', body)

    def test_stylesheet_is_served(self):
        status, headers, body = self.get('/style.css')
        self.assertEqual(status, 200)
        self.assertIn('text/css', headers['content-type'])
        self.assertIn('.table-wrap', body)

    def test_share_card_is_actually_served(self):
        # The Open Graph tags point at this file, so a missing or renamed asset
        # would leave every shared link with a broken preview.
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        try:
            conn.request('GET', '/static/og-card.png')
            resp = conn.getresponse()
            payload = resp.read()
            status = resp.status
            content_type = resp.getheader('Content-Type')
        finally:
            conn.close()
        self.assertEqual(status, 200)
        self.assertEqual(content_type, 'image/png')
        self.assertTrue(payload.startswith(b'\x89PNG\r\n'), 'not a PNG')
        self.assertGreater(len(payload), 10000, 'suspiciously small share card')

    def test_pages_advertise_the_share_card(self):
        _, _, body = self.get('/')
        self.assertIn(f'<meta property="og:image" content="{server.OG_IMAGE}">', body)
        self.assertIn('summary_large_image', body)

    def test_row_content_is_html_escaped(self):
        # Source names and notes are authored, but the escaping path still has to
        # hold: it is the only thing between a stray bracket and broken markup.
        self.assertEqual(server.esc('<script>'), '&lt;script&gt;')
        self.assertEqual(server.esc('Zoox & Waymo'), 'Zoox &amp; Waymo')


if __name__ == '__main__':
    unittest.main(verbosity=2)

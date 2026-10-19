"""Tests for Driverless Map.

The site is a reference, so most of what can go wrong is a data problem rather
than a code problem. The tests reflect that: the sourcing rule is enforced
mechanically, and the distinction between driverless and supervised services is
asserted rather than trusted.

Run with:  python -m unittest test_site.py -v
"""
import datetime
import hashlib
import http.client
import os
import re
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

    def test_every_city_carries_coordinates_to_place_it(self):
        # The map places each dot by projecting these, so a missing or mistyped
        # pair is a wrong map rather than a wrong page.
        for row in server.CITIES:
            with self.subTest(city=row['city']):
                self.assertIn('at', row, 'a city needs coordinates for the map')
                lat, lon = row['at']
                self.assertTrue(24.0 <= lat <= 50.0, f'{lat} is outside the lower 48')
                self.assertTrue(-125.0 <= lon <= -66.0, f'{lon} is outside the lower 48')

    def test_a_city_listed_twice_stands_in_one_place(self):
        # Las Vegas and the Bay Area each run two services. Two rows, one dot.
        placed = {}
        for row in server.CITIES:
            with self.subTest(city=row['city']):
                if row['city'] in placed:
                    self.assertEqual(placed[row['city']], row['at'],
                                     'the same city cannot be in two places')
                placed[row['city']] = row['at']

    def test_the_checked_date_is_not_in_the_future(self):
        # 'Last checked' is a claim about the past, rendered on every page. A
        # date ahead of today makes the whole site look unmaintained, which is
        # the one impression a reference cannot afford.
        checked = datetime.date.fromisoformat(server.DATESTAMP)
        self.assertLessEqual(checked, datetime.date.today(),
                             'the site claims to have been checked in the future')

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

    def test_home_shows_the_coverage_visuals(self):
        _, _, body = self.get('/')
        self.assertIn('class="stats"', body)
        self.assertIn('class="chip"', body, 'operators should be colour coded')
        for name in server.OPERATOR_COLOURS:
            with self.subTest(operator=name):
                self.assertIn(name, body, 'the legend should name every operator')

    def test_home_groups_the_cities_under_operator_headings(self):
        # The listing is grouped by operator, so a city filed under the wrong
        # heading would be a factual error wearing a layout costume.
        _, _, body = self.get('/')
        by_operator = {}
        for city in server.CITIES:
            by_operator.setdefault(city['operator'], set()).add(city['city'])
        blocks = body.split('<h3 class="ophead"')[1:]
        self.assertEqual(len(blocks), len(by_operator), 'one listing per operator')
        for block in blocks:
            head, _, listing = block.partition('</h3>')
            named = [name for name in by_operator if f'>{name}</span>' in head + '</h3>']
            self.assertEqual(len(named), 1, f'each listing names one operator: {head!r}')
            for city in by_operator[named[0]]:
                self.assertIn(city, listing, f'{city} is missing from its operator listing')

    def test_every_class_used_in_the_markup_has_a_rule(self):
        # A layout pass once shipped CSS ahead of the markup. This is the same
        # failure seen from the other side: a class in a page that no rule
        # defines renders as nothing at all, which is the hardest kind of
        # mistake to notice on a page nobody looks at twice.
        css = (server.ROOT / 'style.css').read_text('utf-8')
        for path, _, _ in server.PAGES:
            _, _, body = self.get(path)
            for attribute in re.findall(r'class="([^"]+)"', body):
                for name in attribute.split():
                    with self.subTest(path=path, cls=name):
                        self.assertIn('.' + name, css, f'{name} is used but never styled')

    def test_every_operator_has_its_own_colour(self):
        operators = {c['operator'] for c in server.CITIES}
        self.assertTrue(operators.issubset(server.OPERATOR_COLOURS.keys()),
                        'an operator without a colour would render grey')
        colours = [server.OPERATOR_COLOURS[o] for o in operators]
        self.assertEqual(len(colours), len(set(colours)), 'colours must be distinct')

    def test_home_includes_the_map(self):
        _, _, body = self.get('/')
        self.assertIn('class="usmap"', body)
        self.assertIn('role="img"', body)
        self.assertEqual(body.count('<path class="st'), len(server.STATE_PATHS),
                         'one outline per state')
        states = {c['region'] for c in server.CITIES}
        self.assertEqual(body.count('class="st on"'), len(states),
                         'the states with service should be highlighted')
        self.assertEqual(body.count('<circle'), len(server.CITIES),
                         'one dot per city service')

    def test_every_city_has_map_coordinates(self):
        # A city without a projected point would silently vanish from the map,
        # which is worse than the map not existing at all.
        for city in {c['city'] for c in server.CITIES}:
            with self.subTest(city=city):
                self.assertIn(city, server.CITY_POINTS)

    def test_every_service_state_has_a_label(self):
        for state in {c['region'] for c in server.CITIES}:
            with self.subTest(state=state):
                self.assertIn(state, server.STATE_LABELS)

    def test_map_geometry_is_sane(self):
        # Every coordinate has to land inside the viewBox, or states fall off the
        # edge of the map. Cheap check, catches a broken projection.
        width, height = (float(n) for n in server.MAP_VIEWBOX.split()[2:4])
        for code, path in server.STATE_PATHS.items():
            with self.subTest(state=code):
                numbers = [float(n) for n in path.replace('M', ' ').replace('L', ' ')
                           .replace('Z', ' ').split()]
                xs, ys = numbers[0::2], numbers[1::2]
                self.assertGreaterEqual(min(xs), -1)
                self.assertLessEqual(max(xs), width + 1)
                self.assertGreaterEqual(min(ys), -1)
                self.assertLessEqual(max(ys), height + 1)

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

    def test_the_stylesheet_url_carries_a_version(self):
        # The stylesheet is cached for a day, so its URL has to change when its
        # contents do. Without that, someone who visited before a deploy gets
        # today's markup styled by yesterday's rules: broken for them, and
        # invisible to whoever did the deploying.
        _, _, body = self.get('/')
        match = re.search(r'<link rel="stylesheet" href="(/style\.css\?v=[0-9a-f]+)">', body)
        self.assertIsNotNone(match, 'the stylesheet link carries no version')
        status, headers, css = self.get(match.group(1))
        self.assertEqual(status, 200)
        self.assertIn('text/css', headers['content-type'])
        self.assertIn('.table-wrap', css)

    def test_the_version_is_the_stylesheet_contents(self):
        digest = hashlib.sha256((server.ROOT / 'style.css').read_bytes()).hexdigest()[:10]
        self.assertEqual(server.stylesheet_url(), f'/style.css?v={digest}')

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

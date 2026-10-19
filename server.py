"""Driverless Map - where autonomous ride-hailing actually operates.

One Python file, standard library only, no database and no disk. The site is a
reference, so the tables below are the source of truth and every row carries a
source. There is no user-generated content, which is why nothing here needs
mutable state: deploys are zero-downtime and there is no single-instance ceiling.

Run it:  python server.py     then open http://127.0.0.1:8090
"""
import os, html, time, datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

ROOT = Path(__file__).parent
SITE_NAME = 'Driverless Map'
SITE_URL = os.environ.get('SITE_URL', 'https://driverlessmap.com').rstrip('/')
OG_IMAGE = SITE_URL + '/static/og-card.png'
DEFAULT_DESCRIPTION = ('Every city where driverless ride-hailing actually carries passengers, '
                       'who operates it, and a source for each claim.')

# Bump this whenever the tables below change. It is shown on every page, and it
# is the honest answer to "how current is this". One value in two formats, so the
# machine-readable and human-readable dates cannot drift apart.
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December']
_UPDATED = datetime.date(2026, 10, 19)
DATESTAMP = _UPDATED.isoformat()
UPDATED = f'{_UPDATED.day} {MONTHS[_UPDATED.month - 1]} {_UPDATED.year}'

# ---------------------------------------------------------------------------
# THE DATA.
#
# Two rules, both enforced by tests:
#   1. Every row carries a named source and a URL. A claim without one does not
#      go in.
#   2. "Driverless" means no safety driver aboard. Services that still run with
#      one are listed separately, because quietly merging them is the single
#      most common way coverage of this industry misleads people.
#
# Where sources disagree, the range goes in the note rather than a tidy average.
# ---------------------------------------------------------------------------

# Cities where driverless service is carrying members of the public today.
CITIES = [
    # --- Waymo ------------------------------------------------------------
    {'city': 'Phoenix', 'region': 'AZ', 'operator': 'Waymo', 'since': '2020',
     'open': 'Open to all',
     'note': 'The original commercial market and the most mature. First city to resume freeway service in July 2026.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'San Francisco Bay Area', 'region': 'CA', 'operator': 'Waymo', 'since': '2024',
     'open': 'Open to all',
     'note': 'Widest service area of any market. Note that Tesla also runs here, with a safety monitor aboard, which is not the same thing.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Los Angeles', 'region': 'CA', 'operator': 'Waymo', 'since': '2024',
     'open': 'Open to all',
     'note': 'Covers downtown, Hollywood and Santa Monica.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Miami', 'region': 'FL', 'operator': 'Waymo', 'since': '2025',
     'open': 'Open to all',
     'note': 'Popular for airport runs.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Austin', 'region': 'TX', 'operator': 'Waymo', 'since': 'Mar 2025',
     'open': 'Open, booked through Uber',
     'note': 'The first market Waymo opened through a ride-hail app rather than its own. Also the city where Tesla runs Cybercabs, so riders here can compare directly.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/waymo-on-uber'},
    {'city': 'Atlanta', 'region': 'GA', 'operator': 'Waymo', 'since': '2025',
     'open': 'Open, booked through Uber',
     'note': 'Second Uber-partnered market.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'San Antonio', 'region': 'TX', 'operator': 'Waymo', 'since': 'Feb 2026',
     'open': 'Rolling access',
     'note': 'Part of the February 2026 Texas wave.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Dallas', 'region': 'TX', 'operator': 'Waymo', 'since': '2026',
     'open': 'Invite or waitlist',
     'note': 'Waymo has 1,102 vehicles registered in Texas as of 24 September, up 49% in three weeks.',
     'source_name': 'TechCrunch', 'source': 'https://techcrunch.com/2026/09/24/waymo-is-scaling-fast-heres-what-the-fleet-data-shows/'},
    {'city': 'Houston', 'region': 'TX', 'operator': 'Waymo', 'since': '2026',
     'open': 'Invite or waitlist',
     'note': 'Launched alongside Dallas. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Nashville', 'region': 'TN', 'operator': 'Waymo', 'since': '2026',
     'open': 'Early access, waitlist',
     'note': 'Waitlist still active for most riders.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Orlando', 'region': 'FL', 'operator': 'Waymo', 'since': '2026',
     'open': 'Open to all',
     'note': 'Includes the tourist corridors. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Denver', 'region': 'CO', 'operator': 'Waymo', 'since': 'Jul 2026',
     'open': 'Rolling out',
     'note': 'One of four cities announced on 8 July 2026, and one of three that went public by September.',
     'source_name': "Investor's Business Daily", 'source': 'https://www.investors.com/news/waymo-robotaxi-service-tesla-amazon-zoox-google-alphabet'},
    {'city': 'San Diego', 'region': 'CA', 'operator': 'Waymo', 'since': 'Jul 2026',
     'open': 'Phased, waitlist',
     'note': 'Same July announcement. Ojai vehicles deployed here at scale.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Las Vegas', 'region': 'NV', 'operator': 'Waymo', 'since': 'summer 2026',
     'open': 'Permitted, rolling out',
     'note': 'Listed by Waymo among the cities it serves, though it had not joined the fully public cohort as of September. Zoox is also here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Tampa', 'region': 'FL', 'operator': 'Waymo', 'since': 'Jul 2026',
     'open': 'Rolling out',
     'note': 'Third Florida market. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},

    # --- Zoox -------------------------------------------------------------
    {'city': 'Las Vegas', 'region': 'NV', 'operator': 'Zoox', 'since': '2025',
     'open': 'Open, waitlist',
     'note': 'Purpose-built vehicle with no steering wheel. Service more than doubled its locations, adding the Convention Center and most Strip hotels; began charging in August 2026. Also tests at Harry Reid airport.',
     'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-service-updates-and-expansions'},
    {'city': 'San Francisco', 'region': 'CA', 'operator': 'Zoox', 'since': 'Nov 2025',
     'open': 'Open, waitlist',
     'note': 'Runs free of charge here because Zoox lacks a commercial permit; the geofence quadrupled in spring 2026 to cover the eastern half of the city.',
     'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-robotaxi-in-san-francisco'},

    # --- Tesla ------------------------------------------------------------
    {'city': 'Austin', 'region': 'TX', 'operator': 'Tesla', 'since': 'Jun 2025',
     'open': 'Open',
     'note': 'The only city where Tesla uses the Cybercab. 319 Cybercabs were registered in Texas on 12 October, up from 45 at launch on 3 September, alongside 420 Model Y robotaxis.',
     'source_name': 'Texas AV Tracker, CNBC', 'source': 'https://texasavtracker.com/tesla'},
    {'city': 'Dallas', 'region': 'TX', 'operator': 'Tesla', 'since': 'Apr 2026',
     'open': 'Open',
     'note': 'Model Y robotaxis, unsupervised. Named by Tesla as the next city for the Cybercab, with no date.',
     'source_name': 'TechCrunch', 'source': 'https://techcrunch.com/2026/04/18/tesla-brings-its-robotaxi-service-to-dallas-and-houston/'},
    {'city': 'Houston', 'region': 'TX', 'operator': 'Tesla', 'since': 'Apr 2026',
     'open': 'Open',
     'note': 'Model Y robotaxis. Large numbers of Cybercabs were photographed here in September without a launch following.',
     'source_name': 'TechCrunch', 'source': 'https://techcrunch.com/2026/04/18/tesla-brings-its-robotaxi-service-to-dallas-and-houston/'},
    {'city': 'Miami', 'region': 'FL', 'operator': 'Tesla', 'since': 'Jul 2026',
     'open': 'Open',
     'note': "Tesla's first market outside Texas. Model Y robotaxis.",
     'source_name': 'Tesla Q2 2026 filing', 'source': 'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf'},
    {'city': 'Orlando', 'region': 'FL', 'operator': 'Tesla', 'since': 'Jul 2026',
     'open': 'Open',
     'note': 'Launched 18 days after Miami, with Tampa. Model Y robotaxis.',
     'source_name': 'Tesla Q2 2026 filing', 'source': 'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf'},
    {'city': 'Tampa', 'region': 'FL', 'operator': 'Tesla', 'since': 'Jul 2026',
     'open': 'Open',
     'note': 'Launched 18 days after Miami, with Orlando. Model Y robotaxis.',
     'source_name': 'Tesla Q2 2026 filing', 'source': 'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf'},
]

# Not driverless. Listed separately on purpose: a service with a safety monitor
# aboard is a different product, and merging the two inflates every total.
SUPERVISED = [
    {'market': 'San Francisco Bay Area, CA', 'operator': 'Tesla', 'note': 'Runs with a human safety monitor because Tesla holds no driverless permit in California. The CPUC said in March 2026 that Tesla is not operating an autonomous vehicle service.', 'source_name': 'Electrek, CPUC', 'source': 'https://electrek.co/2026/03/25/california-regulator-confirms-tesla-not-operating-autonomous-vehicle-service/'},
    {'market': 'Austin, Miami and others', 'operator': 'Zoox', 'note': 'Employee, family and friend rides precede public access in new markets, which is why a vehicle on the street is not evidence of a service you can book.', 'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-service-updates-and-expansions'},
]

UP_NEXT = [
    {'market': 'Waymo: Baltimore, Boston, Charlotte, Chicago, Detroit, Minneapolis, New Orleans, New York, Philadelphia, Pittsburgh, Portland, Sacramento, Seattle, St. Louis, Washington DC', 'status': 'Announced', 'note': 'Published on Waymo\'s own updates page as what is next.', 'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'market': 'Waymo: London, Tokyo, Singapore, Toronto', 'status': 'International', 'note': 'London and Singapore announced, Tokyo opening in 2027 with Nihon Kotsu and GO, Toronto announced in October 2026. No public rides in any of them yet.', 'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'market': 'Zoox: Austin and Miami', 'status': 'Vehicle on the road', 'note': 'Purpose-built robotaxi has arrived in both, starting with employees before public access.', 'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-robotaxi-is-now-in-austin'},
    {'market': 'Zoox: Houston and San Diego', 'status': 'Testing', 'note': 'Testing with the retrofitted fleet, not yet the purpose-built robotaxi.', 'source_name': 'Zoox', 'source': 'https://zoox.com/where-to-ride'},
    {'market': 'Tesla: Dallas', 'status': 'Named, no date', 'note': "Tesla's AI director said \"Dallas soon\" on 11 October 2026. Tesla has repeatedly named cities without dates.", 'source_name': 'Teslarati', 'source': 'https://www.teslarati.com/tesla-cybercab-dallas/'},
]

# Operators, for the summary table. Vehicle counts are given only when a source
# provides one, and the source is named.
OPERATORS = [
    {'name': 'Waymo', 'owner': 'Alphabet', 'vehicle': 'Jaguar I-PACE, and Ojai minivans with the sixth-generation driver',
     'cities': '15 US metros', 'vehicles': 'Over 4,000',
     'note': 'The only company running fully driverless commercial ride-hailing at scale in the US. Imports of Ojai are reported to reach 5,100 by the end of 2026. Closed $5bn in debt financing in October 2026.',
     'source_name': 'Waymo, TechCrunch', 'source': 'https://techcrunch.com/2026/09/24/waymo-is-scaling-fast-heres-what-the-fleet-data-shows/'},
    {'name': 'Zoox', 'owner': 'Amazon', 'vehicle': 'Purpose-built robotaxi, no steering wheel, bidirectional',
     'cities': '2 public, 2 more with vehicles on the road', 'vehicles': 'About 100',
     'note': 'Holds the first Part 555 commercial exemption NHTSA has granted for a purpose-built robotaxi, which is the regulatory event worth watching here.',
     'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-nhtsa-part-555-commercial-exemption'},
    {'name': 'Tesla', 'owner': 'Tesla', 'vehicle': 'Cybercab in Austin; modified Model Y elsewhere',
     'cities': '6 markets, Cybercab in 1', 'vehicles': '739 registered in Texas, of which 319 are Cybercabs',
     'note': 'The only operator using two different vehicle types under one brand. Only Austin has the Cybercab, which is a distinction most coverage blurs.',
     'source_name': 'Texas AV Tracker', 'source': 'https://texasavtracker.com/tesla'},
    {'name': 'Uber', 'owner': 'Uber', 'vehicle': 'None of its own',
     'cities': 'Austin and Atlanta via Waymo', 'vehicles': 'n/a',
     'note': 'Runs no vehicles. Its strategy is to be the booking layer for other people\'s fleets, which makes it a partner and a competitor at once.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/waymo-on-uber'},
]

# Chinese operators are expanding, but their city lists are hard to verify from
# primary English-language sources. Rather than print numbers we cannot stand
# behind, this is a standing note inviting correction.
ALSO_OPERATING = (
    'Baidu\u2019s Apollo Go, Pony.ai and WeRide also run public robotaxi services, largely in China, '
    'and have been expanding internationally. Their published city lists are harder to verify from '
    'primary sources in English, so they are not counted in the table above. If you can point at '
    'a primary source for any of them, it belongs here.'
)

REGULATIONS = [
    {'jurisdiction': 'United States, federal', 'status': 'Two live actions',
     'detail': "NHTSA opened Audit Query AQ26002 on 3 September 2026, the day Tesla began commercial Cybercab service in Austin, examining the basis on which Tesla self-certified a vehicle with no pedals, no steering wheel and no mirrors as meeting all applicable Federal Motor Vehicle Safety Standards. Separately, NHTSA granted Zoox the first Part 555 commercial exemption for a purpose-built robotaxi, which is the route a vehicle like this is meant to take. Those two paths, self-certification under audit and a granted exemption, are the substance of the federal picture.",
     'source_name': 'NHTSA', 'source': 'https://www.nhtsa.gov/press-releases/investigation-tesla-cybercab-self-certification'},
    {'jurisdiction': 'Texas', 'status': 'Operating', 'detail': 'Commercially operated automated vehicles need a permit under SB 2807, in force since 2025. Texas DMV registrations are public, which is why Texas is the only state where fleet counts can be checked independently. Waymo had 1,102 vehicles registered on 24 September; Tesla had 739 on 12 October.',
     'source_name': 'Texas AV Tracker', 'source': 'https://texasavtracker.com/tesla'},
    {'jurisdiction': 'California', 'status': 'Split', 'detail': 'Waymo holds the permits needed to charge for driverless rides. Tesla does not: it holds a CPUC charter-party permit covering a human-driven service, and a DMV testing permit requiring a driver present. The CPUC said in March 2026 that Tesla is not operating an autonomous vehicle service.',
     'source_name': 'Electrek, CPUC', 'source': 'https://electrek.co/2026/03/25/california-regulator-confirms-tesla-not-operating-autonomous-vehicle-service/'},
    {'jurisdiction': 'Nevada', 'status': 'Approved', 'detail': 'The Nevada Transportation Authority approved autonomous vehicle network applications for Tesla, Waymo and Aviar on 20 August 2026, covering up to 5,000 vehicles in Clark County in the first 12 months. Airport service needs separate approval.',
     'source_name': 'Nevada B&I', 'source': 'https://www.business.nv.gov/news-media/press-releases/2026/ntata/nevada-transportation-authority-approves-autonomous-vehicle-network-applications-for-tesla-waymo-and-aviari/'},
    {'jurisdiction': 'Arizona', 'status': 'Permitted', 'detail': 'Tesla has held a ride-hailing permit since 17 November 2025, which allows charging for rides statewide. Driverless operation needs separate certification, and no confirmation of it has been found. Waymo operates commercially in Phoenix, the longest-running driverless market anywhere.',
     'source_name': 'TechCrunch', 'source': 'https://techcrunch.com/2025/11/18/tesla-receives-ride-hailing-permit-in-arizona-in-last-required-step-to-launch-robotaxi-service/'},
    {'jurisdiction': 'Florida', 'status': 'Operating, no clear permit', 'detail': 'Waymo and Tesla both carry passengers in Miami, Orlando and Tampa. We have not found a Florida-specific state permit in any source, which is itself worth knowing: three driverless markets and no obvious licensing regime behind them.',
     'source_name': 'Tesla Q2 2026 filing', 'source': 'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf'},
]

FLEET_SERIES = [
    ('3 Sep 2026', 45),
    ('2 Oct 2026', 169),
    ('12 Oct 2026', 319),
]

# ---------------------------------------------------------------------------


def esc(value):
    return html.escape(str(value), quote=True)


def rfc822(stamp):
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    try:
        dt = datetime.datetime.strptime(str(stamp)[:19], '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return ''
    return (f'{days[dt.weekday()]}, {dt.day:02d} {months[dt.month - 1]} {dt.year} '
            f'{dt.hour:02d}:{dt.minute:02d}:{dt.second:02d} +0000')


def ref_table(columns, rows):
    out = ['<div class="table-wrap"><table><thead><tr>']
    out += ['<th>' + esc(c) + '</th>' for c in columns]
    out += ['</tr></thead><tbody>']
    for row in rows:
        out.append('<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>')
    out.append('</tbody></table></div>')
    return ''.join(out)


def bar_chart(series, label):
    top = max(v for _, v in series) or 1
    w, h = 640, 270
    pad, base = 54, 212
    span = w - 2 * pad
    slot = span // len(series)
    bw = min(118, slot - 30)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{esc(label)}" class="chart">']
    for i, (caption, value) in enumerate(series):
        x = pad + i * slot + (slot - bw) // 2
        bh = round((base - 24) * (value / top))
        y = base - bh
        out.append(f'<rect x="{x}" y="{y}" width="{bw}" height="{bh}" rx="4" fill="var(--accent)"/>')
        out.append(f'<text x="{x + bw // 2}" y="{y - 12}" text-anchor="middle" fill="#f2f4ed" font-size="23" font-weight="600">{value}</text>')
        out.append(f'<text x="{x + bw // 2}" y="{base + 28}" text-anchor="middle" fill="#a3ada1" font-size="15">{esc(caption)}</text>')
    out.append(f'<line x1="{pad - 14}" y1="{base}" x2="{w - pad + 14}" y2="{base}" stroke="#30362f" stroke-width="1"/>')
    out.append('</svg>')
    return ''.join(out)


PAGES = [
    ('/', 'Map', 'Every city where driverless ride-hailing carries passengers, and who runs it.'),
    ('/operators', 'Operators', 'Who is actually running driverless services, and what they run them in.'),
    ('/regulations', 'Regulations', 'The federal and state rules behind the map, with sources.'),
    ('/about', 'About', 'What this is, how it is sourced, and what it deliberately does not do.'),
]


class Handler(BaseHTTPRequestHandler):
    timeout = 30
    server_version = 'driverlessmap'

    def send_raw(self, code, raw, content_type, cache=None):
        # One place that writes, so HEAD is handled once rather than per route.
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        if cache:
            self.send_header('Cache-Control', cache)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        if self.command == 'HEAD':
            return
        try:
            self.wfile.write(raw)
        except BrokenPipeError:
            pass

    def send(self, code, body, content_type='text/html; charset=utf-8', cache=None):
        self.send_raw(code, body.encode('utf-8'), content_type, cache)

    def page(self, title, content, description=None, path='/', cache=None, code=200):
        full_title = f'{title} · {SITE_NAME}' if title else SITE_NAME
        desc = description or DEFAULT_DESCRIPTION
        canonical = SITE_URL + path
        nav = ''.join(
            f'<a href="{esc(p)}"{" class=\"on\"" if p == path else ""}>{esc(label)}</a>'
            for p, label, _ in PAGES)
        body = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(full_title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(OG_IMAGE)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{esc(OG_IMAGE)}">
<link rel="stylesheet" href="/style.css">
</head>
<body>
<header>
  <div class="shell bar">
    <a class="brand" href="/">Driverless<em>Map</em></a>
    <nav>{nav}</nav>
  </div>
</header>
<main class="shell">
{content}
</main>
<footer class="shell">
  <p><b>{esc(SITE_NAME)}</b> &mdash; a reference, not a community. Independent. Not affiliated with,
  endorsed by or sponsored by Waymo, Zoox, Tesla, Uber or any other operator.</p>
  <p class="meta">Data last checked {esc(UPDATED)}. Every figure on this site carries a source.</p>
</footer>
</body>
</html>'''
        self.send(code, body, cache=cache)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if len(path) > 1:
            path = path.rstrip('/')

        if path == '/healthz':
            return self.send(200, 'ok', content_type='text/plain; charset=utf-8')

        if path == '/style.css':
            return self.send(200, (ROOT / 'style.css').read_text('utf-8'),
                             content_type='text/css; charset=utf-8', cache='public, max-age=86400')

        if path == '/robots.txt':
            body = ('User-agent: *\nAllow: /\nDisallow: /healthz\n\n'
                    f'Sitemap: {SITE_URL}/sitemap.xml\n')
            return self.send(200, body, content_type='text/plain; charset=utf-8',
                             cache='public, max-age=3600')

        if path == '/sitemap.xml':
            entries = ''.join(
                f'<url><loc>{esc(SITE_URL + p)}</loc>'
                f'<lastmod>{esc(DATESTAMP)}</lastmod></url>'
                for p, _, _ in PAGES)
            body = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                    + entries + '</urlset>')
            return self.send(200, body, content_type='application/xml; charset=utf-8',
                             cache='public, max-age=600')

        if path == '/static/og-card.png':
            # Branded card, drawn from this site's own palette. Not a photograph,
            # so nothing here needs an attribution a link preview would drop.
            return self.send_raw(200, (ROOT / 'static' / 'og-card.png').read_bytes(),
                                 'image/png', cache='public, max-age=86400')

        if path in ('', '/'):
            return self.home()

        if path == '/operators':
            return self.operators()

        if path == '/regulations':
            return self.regulations()

        if path == '/about':
            return self.about()

        # A real 404, not a friendly page claiming to be fine. Returning 200 for
        # a URL that does not exist is a soft 404: crawlers index the junk and
        # spend crawl budget on this domain rather than on the pages that matter.
        self.page('Not found', '<h1>Not found</h1><p>That page does not exist. '
                               '<a href="/">Start from the map.</a></p>',
                  path=path, code=404)

    def home(self):
        rows = [[
            '<b>' + esc(c['city']) + '</b><br>' + esc(c['region']),
            esc(c['operator']),
            esc(c['since']),
            esc(c['open']),
            esc(c['note']) + f' <a href="{esc(c["source"])}">{esc(c["source_name"])}</a>',
        ] for c in CITIES]
        operators = sorted({c['operator'] for c in CITIES})
        regions = sorted({c['region'] for c in CITIES})
        content = f'''
<section class="hero">
  <h1>Where driverless cars actually take passengers</h1>
  <p class="lede">{len(CITIES)} city services run by {len(operators)} operators, across {len(regions)} states.
  Every row below carries a source, and anything still running with a safety monitor is listed
  separately rather than counted in.</p>
  <p class="stamp">Last checked {esc(UPDATED)}</p>
</section>

{ref_table(['City', 'Operator', 'Since', 'Access', 'Notes'], rows)}

<h2>Not driverless, despite the coverage</h2>
<p>These are real services, but a human is still aboard. They are kept out of the table above because
merging the two is how most tracking of this industry goes wrong.</p>
{ref_table(['Market', 'Operator', 'Notes'], [[
    esc(s['market']), esc(s['operator']),
    esc(s['note']) + f' <a href="{esc(s["source"])}">{esc(s["source_name"])}</a>'] for s in SUPERVISED])}

<h2>Announced, not yet carrying passengers</h2>
{ref_table(['Market', 'Status', 'Notes'], [[
    esc(u['market']), esc(u['status']),
    esc(u['note']) + f' <a href="{esc(u["source"])}">{esc(u["source_name"])}</a>'] for u in UP_NEXT])}

<h2>Cybercabs registered in Texas</h2>
{bar_chart(FLEET_SERIES, 'Cybercabs registered for commercial use in Texas, rising from 45 to 319 in six weeks')}
<p class="meta">Texas DMV registrations, the only independently checkable fleet count in the United States.</p>

<h2>Why this exists</h2>
<p>Coverage of this industry is written per company, because the companies are what people follow. That
makes the obvious question hard to answer: <em>where can I actually get one of these, and who runs it?</em>
This site answers that across operators instead, with a source on every line.</p>
'''
        self.page('Where driverless cars take passengers', content,
                  description=('Every city where driverless ride-hailing carries passengers, '
                               'by operator, with a source for each.'),
                  path='/', cache='public, max-age=300')

    def operators(self):
        rows = [[
            '<b>' + esc(o['name']) + '</b><br>' + esc(o['owner']),
            esc(o['cities']),
            esc(o['vehicles']),
            esc(o['vehicle']),
            esc(o['note']) + f' <a href="{esc(o["source"])}">{esc(o["source_name"])}</a>',
        ] for o in OPERATORS]
        content = f'''
<h1>Who runs what</h1>
<p class="lede">Four names matter right now. One runs the largest driverless fleet, one has the most
interesting regulatory precedent, one is the only service using two different vehicles, and one owns no
vehicles at all.</p>
<p class="stamp">Last checked {esc(UPDATED)}</p>

{ref_table(['Operator', 'Where', 'Fleet', 'Vehicle', 'Notes'], rows)}

<h2>Also operating</h2>
<p>{esc(ALSO_OPERATING)}</p>

<h2>The distinction that matters</h2>
<p>Two words get used interchangeably and should not be. <b>Driverless</b> means no human aboard. Many
services described in coverage as robotaxis still carry a safety monitor, and a service you cannot book
without a chaperone is a different product from one you can. Where a service is supervised, this site says so.</p>
'''
        self.page('Operators', content, path='/operators', cache='public, max-age=300')

    def regulations(self):
        rows = [[
            '<b>' + esc(r['jurisdiction']) + '</b>',
            esc(r['status']),
            esc(r['detail']) + f' <a href="{esc(r["source"])}">{esc(r["source_name"])}</a>',
        ] for r in REGULATIONS]
        content = f'''
<h1>The rules behind the map</h1>
<p class="lede">A vehicle with no steering wheel is not a shape the Federal Motor Vehicle Safety
Standards were written around. Two different routes have emerged for dealing with that, and the
difference between them is the most important thing on this site.</p>
<p class="stamp">Last checked {esc(UPDATED)}</p>

{ref_table(['Jurisdiction', 'Status', 'What is happening'], rows)}

<h2>Self-certification, or an exemption</h2>
<p>A manufacturer can certify its own vehicle as meeting the standards, or it can apply for an
exemption from ones it cannot meet. NHTSA is auditing the first approach as applied to the Cybercab,
and has granted the first commercial exemption of its kind for Zoox's purpose-built robotaxi. Whichever
route holds up will shape what every operator after them does.</p>

<h2>What this is not</h2>
<p>A summary for readers. Not legal advice, and not a substitute for the filings. Where a filing exists,
follow the source rather than this page.</p>
'''
        self.page('Regulations', content, path='/regulations', cache='public, max-age=300')

    def about(self):
        content = f'''
<h1>About</h1>
<p class="lede">Driverless Map tracks where autonomous ride-hailing actually carries passengers, across
operators, with a source for every row.</p>

<h2>Sourcing</h2>
<p>Every claim on this site carries a named source and a link, and a test enforces that, because a
single unsourced number would undermine a page whose only value is being trustworthy. Where sources
disagree, the range is printed rather than a tidy average. Where a figure cannot be sourced, it is left
out and the gap is stated instead.</p>

<h2>The distinction this site exists to make</h2>
<p>Coverage of this industry is written per company, which makes it hard to see the actual state of
deployment. Worse, services running with a safety monitor are routinely described alongside driverless
ones, inflating every total. This site separates them deliberately.</p>

<h2>What this is not</h2>
<p>Not a forum, not a news outlet, and not affiliated with any operator. It is a reference, which means
it is useful whether or not anyone else shows up &mdash; the opposite of a community, which is useless
until a crowd does.</p>

<h2>Corrections</h2>
<p>If a row is wrong, it should be fixed rather than defended. The data lives in a single file in the
source repository, each row carrying its own source, so a correction is a one-line change.</p>

<p class="meta">Last checked {esc(UPDATED)}.</p>
'''
        self.page('About', content, path='/about', cache='public, max-age=3600')

    def do_HEAD(self):
        # Uptime checkers and some crawlers use HEAD. Answering 501 makes them
        # log errors that are not errors.
        self.do_GET()

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8090'))
    host = os.environ.get('HOST', '127.0.0.1')
    print(f'Driverless Map running at http://{host}:{port}', flush=True)
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.serve_forever()

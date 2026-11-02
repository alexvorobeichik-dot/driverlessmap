"""Driverless Map - where autonomous ride-hailing actually operates.

One Python file, standard library only, no database and no disk. The site is a
reference, so the tables below are the source of truth and every row carries a
source. There is no user-generated content, which is why nothing here needs
mutable state: deploys are zero-downtime and there is no single-instance ceiling.

Run it:  python server.py     then open http://127.0.0.1:8090
"""
import os, html, time, datetime, hashlib
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

ROOT = Path(__file__).parent
SITE_NAME = 'Driverless Map'
SITE_URL = os.environ.get('SITE_URL', 'https://driverlessmap.com').rstrip('/')
OG_CARD = '/static/og-card.png'
OG_IMAGE = SITE_URL + OG_CARD

# One colour per operator, used in the chips, the legend and the map dots, so the
# same operator reads the same way everywhere on the site.
OPERATOR_COLOURS = {'Waymo': '#6ee7a8', 'Zoox': '#6aa9ff', 'Tesla': '#e8a33d'}
DEFAULT_DESCRIPTION = ('Every city where driverless ride-hailing actually carries passengers, '
                       'who operates it, and a source for each claim.')

# Bump this whenever the tables below change. It is shown on every page, and it
# is the honest answer to "how current is this". One value in two formats, so the
# machine-readable and human-readable dates cannot drift apart.
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
          'July', 'August', 'September', 'October', 'November', 'December']
_UPDATED = datetime.date(2026, 11, 1)
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
     'at': (33.4484, -112.0740),
     'open': 'Open to all',
     'note': 'The original commercial market and the most mature. First city to resume freeway service in July 2026.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'San Francisco Bay Area', 'region': 'CA', 'operator': 'Waymo', 'since': '2024',
     'at': (37.7749, -122.4194),
     'open': 'Open to all',
     'note': 'Widest service area of any market. Note that Tesla also runs here, with a safety monitor aboard, which is not the same thing.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Los Angeles', 'region': 'CA', 'operator': 'Waymo', 'since': '2024',
     'at': (34.0522, -118.2437),
     'open': 'Open to all',
     'note': 'Covers downtown, Hollywood and Santa Monica.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Miami', 'region': 'FL', 'operator': 'Waymo', 'since': '2025',
     'at': (25.7617, -80.1918),
     'open': 'Open to all',
     'note': 'Popular for airport runs.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Austin', 'region': 'TX', 'operator': 'Waymo', 'since': 'Mar 2025',
     'at': (30.2672, -97.7431),
     'open': 'Open, booked through Uber',
     'note': 'The first market Waymo opened through a ride-hail app rather than its own. Also the city where Tesla runs Cybercabs, so riders here can compare directly.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/waymo-on-uber'},
    {'city': 'Atlanta', 'region': 'GA', 'operator': 'Waymo', 'since': '2025',
     'at': (33.7490, -84.3880),
     'open': 'Open, booked through Uber',
     'note': 'Second Uber-partnered market.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'San Antonio', 'region': 'TX', 'operator': 'Waymo', 'since': 'Feb 2026',
     'at': (29.4241, -98.4936),
     'open': 'Open to all',
     'note': 'Part of the February 2026 Texas wave. Open to anyone in the app from 14 October 2026, including pickups and drop-offs at San Antonio International Airport.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/blog/shorts/sat-sd-tpa/'},
    {'city': 'Dallas', 'region': 'TX', 'operator': 'Waymo', 'since': '2026',
     'at': (32.7767, -96.7970),
     'open': 'Invite or waitlist',
     'note': 'Waymo has 1,102 vehicles registered in Texas as of 24 September, up 49% in three weeks.',
     'source_name': 'TechCrunch', 'source': 'https://techcrunch.com/2026/09/24/waymo-is-scaling-fast-heres-what-the-fleet-data-shows/'},
    {'city': 'Houston', 'region': 'TX', 'operator': 'Waymo', 'since': '2026',
     'at': (29.7604, -95.3698),
     'open': 'Invite or waitlist',
     'note': 'Launched alongside Dallas. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Nashville', 'region': 'TN', 'operator': 'Waymo', 'since': '2026',
     'at': (36.1627, -86.7816),
     'open': 'Early access, waitlist',
     'note': 'Waitlist still active for most riders.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Orlando', 'region': 'FL', 'operator': 'Waymo', 'since': '2026',
     'at': (28.5383, -81.3792),
     'open': 'Open to all',
     'note': 'Includes the tourist corridors, and nearly doubled eastwards in the 27 October 2026 expansion. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/blog/shorts/more-places/'},
    {'city': 'Denver', 'region': 'CO', 'operator': 'Waymo', 'since': 'Jul 2026',
     'at': (39.7392, -104.9903),
     'open': 'Rolling out',
     'note': 'One of four cities announced on 8 July 2026, and one of three that went public by September.',
     'source_name': "Investor's Business Daily", 'source': 'https://www.investors.com/news/waymo-robotaxi-service-tesla-amazon-zoox-google-alphabet'},
    {'city': 'San Diego', 'region': 'CA', 'operator': 'Waymo', 'since': 'Jul 2026',
     'at': (32.7157, -117.1611),
     'open': 'Open to all',
     'note': 'Same July announcement. Open to anyone in the app from 14 October 2026; the 27 October expansion added La Jolla.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/blog/shorts/sat-sd-tpa/'},
    {'city': 'Las Vegas', 'region': 'NV', 'operator': 'Waymo', 'since': 'summer 2026',
     'at': (36.1699, -115.1398),
     'open': 'Permitted, rolling out',
     'note': 'Pickups and drop-offs at Harry Reid International began on 21 October 2026 for riders already able to use the service. Zoox is also here.',
     'source_name': 'Waymo', 'source': 'https://support.google.com/waymo/announcements/12766613'},
    {'city': 'Tampa', 'region': 'FL', 'operator': 'Waymo', 'since': 'Jul 2026',
     'at': (27.9506, -82.4572),
     'open': 'Open to all',
     'note': 'Third Florida market. Open to anyone in the app from 14 October 2026. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/blog/shorts/sat-sd-tpa/'},

    # --- Zoox -------------------------------------------------------------
    {'city': 'Las Vegas', 'region': 'NV', 'operator': 'Zoox', 'since': '2025',
     'at': (36.1699, -115.1398),
     'open': 'Open, waitlist',
     'note': 'Purpose-built vehicle with no steering wheel. Service more than doubled its locations, adding the Convention Center and most Strip hotels; began charging in August 2026. Also tests at Harry Reid airport.',
     'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-service-updates-and-expansions'},
    {'city': 'San Francisco Bay Area', 'region': 'CA', 'operator': 'Zoox', 'since': 'Nov 2025',
     'at': (37.7749, -122.4194),
     'open': 'Open, waitlist',
     'note': 'Runs free of charge here because Zoox lacks a commercial permit; the geofence quadrupled in spring 2026 to cover the eastern half of the city.',
     'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-robotaxi-in-san-francisco'},

    # --- Tesla ------------------------------------------------------------
    {'city': 'Austin', 'region': 'TX', 'operator': 'Tesla', 'since': 'Jun 2025',
     'at': (30.2672, -97.7431),
     'open': 'Open',
     'note': 'The only city where Tesla carries passengers in the Cybercab. The Texas roster grew from 45 Cybercabs at launch on 3 September to 573 by 1 November, when Model Ys still outnumbered them 631 to 573.',
     'source_name': 'Texas AV Tracker, Drive Tesla', 'source': 'https://driveteslacanada.ca/news/tesla-robotaxi-fleet-surges-to-1204-vehicles-in-texas-closing-in-on-waymo'},
    {'city': 'Dallas', 'region': 'TX', 'operator': 'Tesla', 'since': 'Apr 2026',
     'at': (32.7767, -96.7970),
     'open': 'Open',
     'note': 'Model Y robotaxis today. Cybercab service is announced for November 2026 and cars have been seen staged in the city, but no day has been given.',
     'source_name': 'TechCrunch, Drive Tesla', 'source': 'https://techcrunch.com/2026/10/22/tesla-is-prepping-a-cybercab-onslaught/'},
    {'city': 'Houston', 'region': 'TX', 'operator': 'Tesla', 'since': 'Apr 2026',
     'at': (29.7604, -95.3698),
     'open': 'Open',
     'note': 'Model Y and Cybercab robotaxis. Expanded on 26 October 2026 to much of the 610 Loop and northwest Houston; drivers have since reported gaps inside the drawn boundary.',
     'source_name': 'Houston Public Media', 'source': 'https://www.houstonpublicmedia.org/articles/news/transportation/2026/10/26/565273/teslas-robotaxi-houston-service-expands-with-a-rocket-shaped-map'},
    {'city': 'Miami', 'region': 'FL', 'operator': 'Tesla', 'since': 'Jul 2026',
     'at': (25.7617, -80.1918),
     'open': 'Open',
     'note': "Tesla's first market outside Texas. Model Y robotaxis.",
     'source_name': 'Tesla Q2 2026 filing', 'source': 'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf'},
    {'city': 'Orlando', 'region': 'FL', 'operator': 'Tesla', 'since': 'Jul 2026',
     'at': (28.5383, -81.3792),
     'open': 'Open',
     'note': 'Launched 18 days after Miami, with Tampa. Model Y robotaxis.',
     'source_name': 'Tesla Q2 2026 filing', 'source': 'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf'},
    {'city': 'Tampa', 'region': 'FL', 'operator': 'Tesla', 'since': 'Jul 2026',
     'at': (27.9506, -82.4572),
     'open': 'Open',
     'note': 'Launched 18 days after Miami, with Orlando. Model Y robotaxis.',
     'source_name': 'Tesla Q2 2026 filing', 'source': 'https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf'},
]

# Not driverless. Listed separately on purpose: a service with a safety monitor
# aboard is a different product, and merging the two inflates every total.
SUPERVISED = [
    {'market': 'San Francisco Bay Area, CA', 'operator': 'Tesla', 'note': 'Runs with a human safety monitor because Tesla holds no driverless permit in California. The CPUC said in March 2026 that Tesla is not operating an autonomous vehicle service.', 'source_name': 'Electrek, CPUC', 'source': 'https://electrek.co/2026/03/25/california-regulator-confirms-tesla-not-operating-autonomous-vehicle-service/'},
    {'market': 'Austin, Miami and others', 'operator': 'Zoox', 'note': 'Employee, family and friend rides precede public access in new markets, which is why a vehicle on the street is not evidence of a service you can book.', 'source_name': 'Zoox', 'source': 'https://zoox.com/journal/zoox-service-updates-and-expansions'},
    {'market': 'Dallas, TX', 'operator': 'Avride', 'note': 'Hyundai IONIQ 5 robotaxis booked through Uber since 3 December 2025, with an on-board specialist in the driver seat on every trip, so it is not driverless. About 9 square miles across Downtown, Uptown, Turtle Creek and Deep Ellum.', 'source_name': 'Robotaxi Atlas, NHTSA', 'source': 'https://www.robotaxiatlas.com/operators/avride'},
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


# US state boundaries from Natural Earth's 1:50m states layer, which is public
# domain and needs no attribution: projected to Albers equal-area, simplified to
# about half a pixel, and reduced to islands big enough to see. Every line below
# is generated by tools/make_map.py, which also places the city dots. Re-run it
# when a city is added. The app does no projection maths and reads no data files
# at runtime.
# Widened north and east to hold the provinces: the map window now starts
# above and left of the origin. The projection and its fitted offset are
# unchanged, so every state redraws exactly where it was and only the visible
# window grew.
MAP_VIEWBOX = "-21 -150 590 456"
STATE_PATHS = {
    'AL': 'M326.9 240.3L325.7 241.7L322.1 242.4L324.1 241.5L321.6 237.2L320.7 241.0L318.2 241.1L316.0 224.2L316.9 189.7L315.8 188.7L339.1 186.7L345.6 209.2L349.1 216.4L347.7 221.2L349.9 230.9L325.3 233.4L325.4 235.0L327.4 237.3L327.0 239.9L326.9 240.3Z',
    'AR': 'M301.4 178.7L301.6 179.6L299.5 182.5L298.1 189.0L294.8 193.5L294.5 196.1L291.7 199.8L291.7 201.4L290.4 202.3L290.6 203.9L289.3 205.7L290.5 210.8L290.2 213.1L263.2 214.1L263.0 208.0L260.1 208.0L259.0 207.0L259.0 187.4L257.2 174.8L297.0 173.3L297.9 175.6L295.4 179.2L299.8 178.8L301.4 178.7Z',
    'AZ': 'M120.9 224.8L102.1 222.0L69.1 202.5L70.7 200.4L71.9 200.5L73.1 199.5L73.3 197.9L71.8 195.5L72.4 192.7L74.4 191.0L76.3 186.2L79.5 184.1L77.7 181.5L76.5 176.4L77.6 171.5L77.7 163.9L78.6 162.8L80.1 162.7L82.7 164.7L84.3 163.2L86.0 154.1L129.7 161.4L121.5 220.8L120.9 224.8Z',
    'CA': 'M76.6 175.5L77.7 181.5L79.5 183.8L76.3 186.2L74.4 191.0L72.4 192.7L71.8 195.5L73.4 198.7L72.6 200.2L48.1 197.8L46.9 188.7L42.5 182.7L39.6 181.8L39.4 178.6L34.0 176.1L33.3 174.2L30.7 171.7L23.1 169.1L22.0 167.6L23.4 161.6L21.9 160.2L22.2 157.8L19.6 154.1L16.4 145.5L16.8 142.8L18.4 141.4L18.6 140.1L18.2 138.9L16.0 137.7L14.7 134.8L14.8 130.9L16.1 128.2L16.7 130.8L18.3 132.6L17.1 126.6L17.8 126.3L24.6 127.6L20.6 125.7L19.4 126.0L17.6 124.6L16.7 124.7L15.5 127.7L12.8 124.2L12.0 124.8L13.0 122.3L13.5 123.6L13.4 122.8L9.1 113.1L10.9 103.4L8.6 95.6L14.2 85.4L14.2 80.6L15.0 78.4L48.6 87.8L40.2 120.7L74.7 172.6L76.6 175.5ZM27.3 174.8L30.0 176.3L27.6 176.2L27.0 174.9L27.3 174.8ZM25.4 176.2L24.3 175.9L23.8 174.7L26.1 175.7L25.4 176.2ZM39.2 185.8L39.5 186.7L38.1 186.4L37.4 184.5L38.9 185.4L39.2 185.8Z',
    'CO': 'M129.7 161.4L135.9 116.5L194.4 122.4L191.7 167.6L133.0 161.8L129.7 161.4Z',
    'CT': 'M442.8 87.3L444.4 94.8L435.7 97.6L430.8 102.2L429.7 101.1L431.4 99.4L429.2 90.2L442.7 87.2L442.8 87.3Z',
    'DE': 'M425.6 132.8L419.9 134.1L416.2 120.2L417.2 118.6L419.0 118.5L418.0 120.8L418.6 122.5L422.0 127.7L424.3 129.4L424.0 131.6L425.5 132.3L425.6 132.8Z',
    'FL': 'M326.9 240.3L327.4 237.3L325.4 235.0L325.3 233.4L349.9 230.9L351.5 233.9L376.9 232.3L377.6 234.1L378.4 234.3L379.2 229.1L383.6 229.4L389.6 242.9L397.0 252.8L396.8 255.2L398.7 259.1L396.7 256.3L396.1 252.5L395.6 254.6L395.2 252.0L393.4 250.3L395.0 254.3L404.7 270.4L405.8 281.2L403.3 288.4L397.1 290.5L396.5 288.6L398.6 288.8L396.7 288.0L393.3 283.3L389.6 282.2L387.3 277.4L386.3 277.0L387.3 274.6L385.4 276.4L385.0 271.8L383.3 272.4L383.5 273.4L382.9 273.4L380.6 271.4L377.2 266.9L379.6 262.5L376.8 261.7L377.7 263.7L376.5 264.6L375.3 263.3L376.1 255.9L375.6 251.5L368.5 246.1L364.0 241.3L360.3 239.8L357.8 240.5L357.4 242.4L348.6 246.0L347.6 245.1L347.5 244.3L348.6 245.1L348.0 243.8L344.6 241.4L345.1 239.5L343.5 241.0L336.8 239.1L340.0 238.7L338.6 237.9L329.7 240.5L331.7 239.3L331.4 237.7L330.8 238.6L329.8 238.2L329.0 240.5L327.1 241.2L327.3 240.1L326.9 240.3ZM402.5 265.5L400.1 261.4L402.5 265.5ZM404.5 289.2L402.9 291.1L405.4 286.8L404.5 289.2Z',
    'GA': 'M349.9 230.9L347.7 221.2L349.1 216.4L345.6 209.2L339.1 186.7L361.8 183.9L360.1 187.5L365.1 189.9L368.1 194.3L378.9 203.5L384.6 212.7L387.3 214.1L385.3 216.1L385.9 217.0L384.5 220.1L385.3 220.0L383.7 222.3L384.7 223.2L384.2 224.3L383.4 224.1L383.6 229.4L379.2 229.1L378.4 234.3L377.6 234.1L376.9 232.3L351.5 233.9L350.4 231.7L349.9 230.9Z',
    'IA': 'M283.5 130.1L280.9 127.5L246.9 128.5L244.2 114.8L239.8 104.5L241.2 100.0L240.1 95.9L283.4 94.9L284.5 96.7L285.2 102.8L288.4 104.7L293.0 110.2L293.2 111.5L291.2 116.4L286.2 118.8L287.2 122.8L286.1 125.8L283.8 128.3L283.9 129.9L283.5 130.1Z',
    'ID': 'M89.6 17.2L96.8 18.8L94.5 29.5L96.2 33.6L95.7 36.1L98.3 39.1L101.3 45.4L104.3 46.8L102.1 52.1L102.2 55.2L101.1 55.8L100.5 58.4L102.1 59.7L104.9 57.9L106.2 59.2L106.4 62.6L107.7 66.0L107.4 67.4L109.6 69.4L110.1 72.7L111.1 73.9L112.4 72.9L115.0 73.7L116.3 72.9L122.0 74.1L123.4 72.0L125.5 75.1L121.0 102.9L72.6 93.6L77.1 73.7L78.8 69.6L77.3 68.3L77.2 66.5L85.7 54.6L83.5 50.5L83.3 45.4L89.2 19.0L89.6 17.2Z',
    'IL': 'M283.5 130.1L287.2 122.8L286.2 118.8L291.2 116.4L293.1 112.6L293.0 110.2L288.8 105.7L312.0 104.3L312.4 107.5L315.2 112.7L317.5 139.2L316.7 141.6L318.1 146.3L317.1 149.3L314.7 152.2L314.3 160.4L311.0 162.6L311.5 165.6L306.3 165.0L305.5 167.2L304.4 166.3L304.2 167.1L302.4 164.9L301.8 160.1L294.0 153.6L295.6 146.8L292.5 145.9L291.7 146.3L290.9 145.5L288.5 141.1L284.3 137.2L283.1 131.9L283.5 130.1Z',
    'IN': 'M314.6 157.4L314.1 156.5L314.7 152.2L317.1 149.3L318.2 145.5L316.7 141.6L317.5 139.2L315.2 112.7L317.5 113.5L320.6 111.8L337.6 110.0L340.8 141.8L341.5 142.4L338.8 144.7L336.4 144.6L336.2 146.9L332.0 153.6L328.8 151.7L327.1 155.3L324.6 154.4L322.5 156.6L318.4 155.2L318.0 156.6L315.9 155.9L315.5 157.3L314.8 157.3L314.6 157.4Z',
    'KS': 'M191.7 167.6L193.7 133.7L250.5 135.3L254.0 136.9L254.3 138.2L252.8 139.9L253.0 140.9L256.8 145.2L257.2 169.2L224.4 169.0L193.7 167.7L191.7 167.6Z',
    'KY': 'M305.5 167.2L306.3 165.0L311.5 165.6L311.0 162.6L314.3 160.4L313.9 158.5L315.5 157.3L315.8 155.9L318.0 156.6L318.4 155.2L319.6 155.3L322.5 156.6L324.6 154.4L327.1 155.3L328.8 151.7L332.0 153.6L336.2 146.9L336.4 144.6L338.5 144.8L341.5 143.0L340.7 140.6L341.4 139.5L344.3 139.6L346.4 141.9L351.3 143.7L358.1 142.1L361.1 145.0L361.3 148.1L363.7 151.4L365.0 152.8L367.9 154.1L362.3 159.5L358.8 164.3L353.9 166.9L315.2 169.8L315.7 172.0L303.3 172.9L303.7 171.9L305.4 171.4L305.9 168.1L305.5 167.2Z',
    'LA': 'M263.2 214.1L290.2 213.1L290.4 217.5L292.6 221.3L288.8 227.2L286.7 232.9L286.5 236.0L304.9 235.0L304.3 239.4L307.5 243.9L300.6 242.3L298.9 245.0L301.3 246.2L305.4 244.3L306.2 244.9L304.8 246.2L306.7 247.2L307.9 245.4L308.8 245.5L309.4 248.0L306.0 250.5L308.2 252.6L311.5 253.3L313.2 254.6L312.0 256.8L311.1 256.1L309.9 257.4L309.0 255.0L301.8 251.7L302.9 252.8L302.3 256.1L301.6 256.5L300.6 254.9L298.6 254.5L296.3 256.5L290.9 255.0L292.3 254.6L291.2 251.9L288.6 252.2L287.0 250.1L285.5 250.1L284.8 249.2L282.5 250.8L283.0 252.0L281.3 252.5L277.3 252.2L272.4 250.3L266.1 251.1L265.5 250.1L267.1 246.7L266.9 241.7L268.5 236.2L265.3 227.8L263.4 225.6L263.2 215.6L263.2 214.1ZM285.9 252.9L283.8 251.8L285.1 251.4L286.2 252.5L285.9 252.9Z',
    'MA': 'M442.8 87.3L429.2 90.2L429.2 82.1L444.5 78.8L447.2 76.0L448.2 75.8L449.3 77.9L450.4 77.8L447.9 82.2L450.6 82.7L452.0 85.1L454.5 87.1L457.7 85.4L456.2 83.5L455.1 83.3L456.1 82.9L457.5 83.9L458.6 86.9L453.3 90.1L452.4 88.2L449.3 91.7L448.8 88.8L448.2 89.4L447.1 88.7L446.1 86.4L443.4 87.1L442.8 87.3ZM455.0 91.5L452.5 92.4L453.4 91.0L454.7 91.1L455.0 91.5Z',
    'MD': 'M407.7 131.6L407.9 132.5L408.5 131.5L407.3 130.3L406.8 131.2L403.4 129.9L403.1 128.7L400.7 127.6L399.1 125.1L396.9 124.6L394.5 125.7L393.9 126.9L391.3 126.3L386.2 132.0L385.3 126.3L416.2 120.2L419.9 134.1L425.6 132.8L423.7 138.2L419.8 139.7L420.0 138.3L418.7 137.6L418.8 135.4L417.4 136.6L414.8 134.7L414.8 133.5L417.0 133.0L414.9 131.6L413.9 132.4L414.0 131.1L415.0 130.5L413.4 129.7L414.8 127.9L414.1 128.3L413.7 126.9L414.1 125.4L416.3 124.2L415.1 124.0L416.0 122.7L415.2 122.9L415.1 122.0L414.0 124.4L413.0 124.2L413.0 125.5L412.4 124.7L412.0 126.8L410.7 126.6L412.2 127.9L412.0 129.1L411.2 128.9L413.0 134.7L414.2 136.3L412.6 135.8L411.3 134.1L411.5 134.9L415.4 139.3L411.3 138.1L410.2 136.9L410.2 138.0L408.9 136.5L407.0 137.3L408.0 132.8L407.7 131.6Z',
    'ME': 'M448.1 24.4L450.0 24.8L453.9 22.0L457.9 23.9L462.0 36.1L461.9 38.4L464.1 39.3L465.5 38.8L466.3 42.4L467.9 43.4L469.3 42.8L470.4 45.8L471.5 46.1L470.4 48.2L465.8 50.8L464.8 53.4L463.7 52.3L462.2 53.4L461.4 52.9L461.6 55.8L459.2 55.6L459.6 54.2L458.9 54.3L458.8 53.0L457.7 54.9L458.0 58.7L457.1 60.3L455.1 61.9L454.6 61.1L454.4 62.3L453.8 61.2L453.6 62.9L452.9 62.4L453.3 63.9L451.9 64.1L451.8 63.3L450.4 64.8L450.0 66.0L450.6 66.3L448.2 73.5L445.5 70.5L438.9 50.1L439.8 49.5L440.7 49.9L441.5 47.9L441.1 46.6L442.6 44.0L442.8 32.6L446.2 23.0L447.7 22.9L447.9 23.9L448.1 24.4ZM464.0 54.2L463.1 54.6L463.3 55.4L462.4 55.1L462.7 53.1L463.9 53.9L464.0 54.2Z',
    'MI': 'M355.2 93.4L354.8 97.9L354.1 98.8L353.8 97.4L352.8 97.8L352.2 100.9L350.8 102.3L350.5 105.1L348.6 108.9L337.7 110.7L337.6 110.0L320.6 111.8L322.3 109.9L323.8 106.3L324.8 101.3L324.2 97.1L321.1 90.5L321.8 88.5L320.8 85.6L322.3 82.6L322.2 78.4L327.0 72.2L326.9 76.4L327.9 74.5L327.7 77.0L328.4 71.2L331.8 69.3L330.3 67.9L331.1 65.3L332.5 64.9L336.8 66.1L338.3 67.4L343.7 69.1L345.2 71.8L344.0 71.8L343.9 72.5L345.4 74.7L345.8 79.3L344.5 80.6L344.0 83.1L342.0 84.5L341.9 87.0L344.2 88.0L345.6 86.6L346.0 84.4L349.9 82.4L351.9 84.4L355.2 93.4L355.2 93.4ZM311.1 74.9L310.2 73.9L310.4 72.0L308.8 72.0L309.0 68.6L306.5 67.3L306.1 65.9L290.5 62.6L288.1 60.0L296.0 56.2L301.1 51.9L302.7 54.2L303.0 56.5L304.6 54.7L308.1 55.1L311.6 58.9L314.1 58.5L317.3 59.2L320.9 56.2L329.3 54.2L329.5 57.3L333.5 57.6L335.0 56.8L336.0 59.9L337.5 60.2L339.0 61.8L334.5 62.5L333.2 61.9L332.5 64.1L329.6 62.4L326.6 62.1L323.4 64.3L320.7 64.6L318.3 68.4L317.7 67.6L318.5 65.5L317.0 65.9L315.8 67.8L315.2 65.4L311.1 74.3L311.1 74.9ZM298.5 44.2L296.7 45.4L296.4 44.4L299.5 42.3L301.4 41.3L300.6 42.9L298.5 44.2ZM307.5 49.3L305.7 49.7L302.9 54.2L302.9 52.2L302.8 53.0L301.4 52.5L302.9 50.0L305.8 48.7L307.8 49.1L307.5 49.3ZM341.8 61.2L341.5 62.1L339.3 62.0L340.5 60.4L341.3 60.6L341.8 61.2Z',
    'MN': 'M235.8 34.4L251.2 34.5L251.2 30.3L252.8 30.5L254.8 36.8L262.1 39.5L264.5 38.4L267.4 38.4L271.2 40.2L271.9 41.9L275.0 41.5L278.8 44.1L283.2 42.2L284.6 43.2L289.5 42.8L290.3 43.9L293.4 43.8L284.1 49.0L273.5 59.9L273.8 66.3L270.7 68.4L269.2 71.2L271.0 73.7L270.6 81.6L282.0 89.4L283.4 94.9L241.3 95.8L241.3 75.7L238.3 72.3L240.3 69.5L240.6 66.2L238.8 60.5L238.4 50.0L236.4 43.5L236.5 37.9L235.8 34.4Z',
    'MO': 'M301.4 178.7L295.4 179.2L297.9 175.6L297.0 173.3L257.2 174.8L256.8 145.2L253.0 140.9L252.8 139.9L254.3 138.2L254.0 136.9L252.4 136.8L250.3 135.2L246.9 128.5L280.9 127.5L283.5 130.1L283.1 133.3L284.3 137.2L288.5 141.1L291.7 146.3L292.5 145.9L295.6 146.8L294.0 153.6L301.8 160.1L302.4 164.9L303.8 166.8L304.4 166.3L305.5 167.2L305.4 171.4L303.7 171.9L303.1 173.1L302.4 172.4L301.5 178.4L301.4 178.7Z',
    'MS': 'M316.1 189.0L316.9 189.7L316.0 224.2L318.2 241.1L313.3 241.0L309.3 242.1L307.5 243.9L304.3 239.4L304.9 235.0L286.5 236.0L286.7 232.9L288.8 227.2L292.6 221.3L290.4 217.5L290.5 210.8L289.3 205.7L296.8 190.3L313.6 189.2L316.1 189.0Z',
    'MT': 'M111.3 21.8L148.2 27.8L185.2 32.0L181.7 76.3L126.3 69.6L125.5 75.1L123.4 72.0L122.0 74.1L116.3 72.9L115.0 73.7L112.4 72.9L111.3 73.9L110.1 72.7L109.6 69.4L107.4 67.4L107.7 66.0L106.4 62.6L106.2 59.2L104.9 57.9L102.1 59.7L100.5 58.4L101.1 55.8L102.2 55.2L102.1 52.1L104.3 46.8L101.3 45.4L98.3 39.1L95.8 36.2L96.2 33.6L94.5 29.5L96.8 18.8L110.6 21.6L111.3 21.8Z',
    'NC': 'M361.8 183.9L350.9 185.5L351.1 182.5L352.9 181.9L354.2 179.1L361.7 174.8L362.4 173.0L363.9 171.9L365.3 172.4L367.3 170.2L369.5 170.0L370.5 167.8L371.9 167.0L372.2 164.1L422.2 155.6L424.5 160.2L421.2 159.0L421.5 160.4L420.4 160.2L420.9 160.9L419.5 161.0L418.2 162.6L416.2 160.6L416.9 163.6L422.7 162.2L423.2 165.3L423.8 164.8L423.6 162.9L425.0 161.9L426.0 165.2L423.2 169.2L420.3 169.3L419.2 168.0L418.0 169.4L415.1 168.9L420.4 170.8L418.6 174.4L415.7 173.1L416.8 174.4L419.1 174.9L421.5 173.8L422.5 174.2L421.5 176.3L419.7 177.4L416.1 178.2L414.9 179.6L413.6 178.4L414.3 180.6L411.5 183.9L410.6 188.1L409.9 185.6L409.9 188.5L405.0 189.9L393.3 181.4L383.1 182.8L382.8 181.3L379.8 179.5L368.0 180.7L362.0 183.9L361.8 183.9ZM422.9 155.5L427.7 162.9L424.2 158.4L422.9 155.5ZM429.0 169.3L427.8 169.8L429.0 168.9L428.1 163.4L429.2 168.8L429.0 169.3Z',
    'ND': 'M205.0 33.4L235.8 34.4L236.4 43.5L238.4 50.0L238.8 60.5L240.6 68.4L200.6 67.1L182.5 65.8L185.2 32.0L201.8 33.2L205.0 33.4Z',
    'NE': 'M193.7 133.7L194.4 122.4L177.7 121.2L179.6 98.7L225.0 101.2L228.9 103.5L234.8 103.0L241.2 107.0L245.8 120.5L246.1 126.9L250.5 135.3L195.5 133.8L193.7 133.7Z',
    'NH': 'M436.4 54.1L437.1 50.7L438.9 50.1L445.2 69.8L448.2 73.5L448.2 75.8L444.5 78.8L435.5 80.8L434.4 79.6L433.9 71.9L434.5 62.8L437.2 59.7L436.4 54.4L436.4 54.1Z',
    'NJ': 'M421.5 116.0L423.9 113.5L419.0 109.5L419.3 106.4L418.6 104.9L421.1 100.2L428.5 102.7L426.8 108.5L427.2 109.2L429.5 109.3L430.2 116.3L429.6 114.2L428.4 121.4L425.3 127.2L425.0 124.9L422.9 124.7L418.9 122.3L419.1 118.8L421.4 116.6L421.5 116.0Z',
    'NM': 'M120.9 224.8L129.7 161.4L182.9 167.0L178.2 223.2L144.3 220.1L146.1 222.9L129.5 220.8L128.8 225.8L122.1 224.9L120.9 224.8Z',
    'NV': 'M86.0 154.1L84.3 163.2L82.7 164.7L80.1 162.7L78.6 162.8L77.7 163.9L77.6 171.5L76.6 175.5L40.2 120.7L48.6 87.8L96.7 98.6L86.4 152.4L86.0 154.1Z',
    'NY': 'M382.0 88.1L381.6 86.1L386.2 84.0L393.9 84.0L398.4 83.1L400.1 81.8L403.7 78.4L402.4 75.3L403.8 73.5L401.3 72.8L408.6 62.1L410.8 60.4L422.4 57.7L425.6 73.3L426.2 72.7L427.1 73.4L429.2 82.1L428.9 90.0L431.4 99.4L429.7 101.1L430.8 102.2L428.5 105.5L428.7 101.9L427.8 100.3L428.5 102.7L418.9 99.3L416.7 95.7L414.3 94.3L378.5 101.3L378.0 98.3L384.1 91.2L383.3 88.2L382.0 88.1ZM439.9 100.0L440.1 100.8L441.6 99.1L444.6 97.9L435.2 105.0L429.7 107.3L430.4 106.6L429.7 106.4L428.7 107.4L429.3 104.9L431.4 102.9L439.0 100.2L441.4 97.7L440.5 99.2L439.9 100.0Z',
    'OH': 'M372.3 102.5L374.8 117.4L373.8 118.6L374.6 120.7L373.6 128.9L370.8 132.5L369.3 132.7L367.7 134.3L366.7 136.6L367.2 138.1L366.3 138.8L365.2 137.7L364.7 138.3L363.8 140.6L364.3 142.1L362.8 144.6L360.8 144.7L358.1 142.1L351.3 143.7L346.4 141.9L344.3 139.6L341.0 140.0L337.7 110.7L348.7 108.8L353.1 110.5L355.2 110.3L352.7 111.6L355.8 111.0L357.3 111.6L363.3 109.4L369.7 104.0L372.3 102.5Z',
    'OK': 'M257.2 174.8L259.0 187.4L259.0 207.0L252.2 203.6L250.7 204.6L248.7 203.8L245.5 204.5L242.0 206.4L239.3 204.2L238.0 204.8L236.3 203.7L234.3 206.1L233.9 204.4L231.7 204.9L229.8 203.2L227.2 204.4L225.6 201.3L222.3 202.0L220.9 201.0L215.9 200.2L214.1 197.5L213.7 198.2L211.6 198.2L208.3 195.8L209.2 174.2L182.5 172.6L182.9 167.0L220.3 168.9L257.2 169.2L257.2 173.4L257.2 174.8Z',
    'OR': 'M48.6 87.8L15.0 78.4L14.4 76.7L15.5 71.6L15.2 68.9L18.5 63.6L19.9 63.1L19.2 63.0L21.2 60.3L29.0 40.6L30.9 33.6L37.5 36.3L38.4 38.7L38.4 42.2L42.0 44.2L46.5 44.0L50.9 46.1L56.4 46.6L67.3 46.2L83.4 49.9L85.6 53.6L84.7 56.5L77.2 66.5L77.3 68.3L78.8 69.6L77.1 73.7L72.6 93.6L51.6 88.6L48.6 87.8Z',
    'PA': 'M378.0 98.3L378.5 101.3L414.3 94.3L416.7 95.7L418.5 99.0L421.1 100.2L418.6 104.9L419.3 106.4L418.8 108.4L419.0 109.5L423.9 113.5L420.9 117.2L419.0 118.5L417.2 118.6L416.2 120.2L376.5 127.8L372.3 102.5L375.7 100.1L378.0 98.3Z',
    'RI': 'M444.4 94.8L442.8 87.3L446.1 86.4L448.2 89.4L446.7 88.8L447.2 92.6L445.0 94.7L444.4 94.8Z',
    'SC': 'M387.3 214.1L384.6 212.7L378.9 203.5L368.1 194.3L365.1 189.9L360.1 187.5L361.7 184.0L368.0 180.7L379.8 179.5L382.8 181.3L383.1 182.8L393.3 181.4L405.0 189.9L402.2 192.9L400.5 197.9L399.9 196.2L400.0 199.3L397.4 201.3L395.8 204.0L394.6 203.9L394.8 205.5L391.2 208.0L388.6 208.3L390.3 209.1L389.6 210.7L387.2 209.3L388.6 211.7L387.1 213.6L387.3 214.1Z',
    'SD': 'M241.3 95.8L240.1 95.9L241.2 100.0L239.8 104.2L241.0 107.0L234.8 103.0L228.9 103.5L225.0 101.2L179.6 98.7L182.5 65.8L211.5 67.7L240.6 68.4L238.3 72.0L241.3 75.7L241.3 93.3L241.3 95.8Z',
    'TN': 'M339.1 186.7L296.8 190.3L298.5 187.9L299.5 182.5L301.6 179.6L302.3 173.0L315.7 172.0L315.2 169.8L353.9 166.9L372.2 164.1L371.9 167.0L370.5 167.8L369.5 170.0L367.3 170.2L365.3 172.4L363.9 171.9L362.4 173.0L361.7 174.8L354.2 179.1L352.9 181.9L351.1 182.5L350.9 185.5L342.1 186.4L339.1 186.7Z',
    'TX': 'M259.0 207.0L260.1 208.0L263.0 208.0L263.4 225.6L265.3 227.8L268.5 236.2L266.9 241.7L267.1 246.7L264.9 250.1L265.4 251.5L263.4 251.7L257.0 255.0L259.3 253.2L256.8 253.2L257.1 250.9L254.4 251.5L255.8 255.2L252.0 259.8L246.4 263.4L242.6 265.1L244.8 263.5L241.2 263.2L240.5 263.9L238.6 262.7L239.7 265.1L240.8 265.5L238.2 266.8L237.3 265.9L236.6 268.4L233.5 268.9L233.6 269.8L234.7 269.5L234.3 270.7L233.3 271.9L230.7 272.3L232.1 274.2L230.5 278.0L227.3 276.5L228.0 278.4L230.0 279.0L229.3 282.0L230.4 287.4L233.3 292.5L233.3 293.2L230.9 294.2L226.6 292.2L221.8 291.3L213.5 287.4L210.2 280.5L209.9 275.0L202.5 266.0L198.4 256.2L192.1 249.2L184.1 247.7L180.7 248.8L179.4 249.9L177.5 254.5L174.7 256.8L165.8 251.7L162.3 248.1L159.2 237.6L148.5 226.8L144.3 220.1L178.2 223.2L182.2 172.6L209.2 174.2L208.3 195.8L211.6 198.2L213.7 198.2L214.1 197.5L215.9 200.2L220.9 201.0L222.3 202.0L225.6 201.3L227.2 204.4L229.8 203.2L231.7 204.9L233.9 204.4L234.3 206.1L236.3 203.7L238.0 204.8L239.3 204.2L242.0 206.4L245.5 204.5L248.7 203.8L250.7 204.6L252.2 203.6L256.9 206.5L259.0 207.0ZM237.3 268.9L239.5 267.5L237.3 268.9ZM231.4 278.3L232.0 275.8L234.4 272.5L232.4 275.6L231.4 278.3ZM233.0 291.0L230.8 283.6L231.0 279.4L232.7 289.5L233.0 291.0Z',
    'UT': 'M129.7 161.4L86.0 154.1L96.7 98.6L121.0 102.9L119.3 114.1L135.9 116.5L130.1 158.6L129.7 161.4Z',
    'VA': 'M406.8 131.2L407.8 132.9L406.4 135.2L406.4 137.6L408.7 137.6L410.3 139.1L413.6 139.6L416.5 141.3L416.3 143.9L415.0 144.1L408.6 139.8L414.5 144.3L416.9 144.9L416.4 145.5L417.4 145.7L417.7 147.2L416.5 147.2L416.3 148.5L413.1 146.5L418.3 150.6L417.4 151.5L414.9 149.4L409.3 149.3L414.6 150.0L416.8 152.7L421.0 151.7L423.1 155.4L388.3 161.8L354.5 166.6L358.8 164.3L362.3 159.5L367.9 154.1L369.1 156.3L371.8 157.3L373.6 155.6L375.3 156.1L377.5 155.2L377.9 153.9L381.9 152.7L385.9 139.7L389.7 139.8L390.8 136.0L394.3 132.9L395.5 127.5L400.3 130.1L400.8 127.7L402.6 128.3L403.4 129.9L406.1 131.0L406.8 131.2ZM421.5 139.5L423.7 138.2L423.1 143.8L421.5 145.7L421.0 148.9L420.5 148.3L420.3 143.7L421.3 141.1L421.5 139.5Z',
    'VT': 'M422.4 57.7L436.4 54.1L437.2 59.7L434.5 62.8L434.8 66.6L433.9 71.3L434.4 79.3L435.5 80.8L429.2 82.1L428.8 81.5L427.1 73.4L426.2 72.7L425.6 73.3L422.6 58.4L422.4 57.7Z',
    'WA': 'M48.2 6.6L89.6 17.2L83.3 45.4L83.4 49.9L67.3 46.2L56.4 46.6L50.9 46.1L46.5 44.0L42.0 44.2L38.4 42.2L38.4 38.7L37.5 36.3L33.1 33.4L30.2 32.7L31.5 29.3L31.7 31.4L32.8 29.1L31.8 26.4L34.1 25.9L32.4 24.6L31.9 25.4L32.5 17.3L31.5 14.2L31.8 11.4L32.5 8.9L37.0 12.8L43.1 14.8L44.0 16.0L45.6 15.7L45.7 18.7L40.6 23.0L42.3 23.2L41.2 23.0L41.6 22.2L46.7 18.5L46.3 20.2L44.7 21.5L44.5 25.1L43.6 24.6L42.8 25.5L42.8 24.2L40.7 25.8L43.0 26.8L46.3 24.8L47.3 20.3L49.1 18.2L48.4 16.0L48.2 17.1L47.6 16.0L48.8 14.8L47.4 12.4L48.8 12.4L49.2 10.6L48.2 8.2L48.2 6.6ZM47.2 15.9L48.0 18.7L46.8 17.7L46.1 14.7L47.4 13.4L47.9 14.3L46.5 14.8L47.1 15.4L47.2 15.9Z',
    'WI': 'M288.8 105.7L284.8 101.8L284.6 97.3L283.5 95.6L282.5 90.0L270.6 81.6L271.0 73.7L269.3 71.9L270.4 68.8L273.8 66.3L273.5 59.9L274.8 58.7L276.4 59.4L279.6 58.4L284.2 56.0L285.1 56.5L284.1 60.0L285.5 59.0L289.5 60.7L290.5 62.6L306.1 65.9L306.5 67.3L309.0 68.6L308.8 72.0L310.4 72.0L310.2 73.9L311.1 74.9L309.5 76.9L308.4 81.1L310.1 80.1L311.4 77.8L312.8 77.4L313.6 78.4L310.6 95.4L312.0 104.3L292.6 105.6L288.8 105.7ZM315.3 72.3L315.4 74.5L314.0 77.7L312.9 76.4L315.0 72.6L315.3 72.3Z',
    'WV': 'M367.9 154.1L365.0 152.8L361.6 148.6L360.9 144.7L363.3 144.0L364.7 138.3L365.2 137.7L366.3 138.8L367.2 138.1L366.7 136.6L367.7 134.3L369.3 132.7L370.8 132.5L373.6 128.9L374.6 120.7L373.9 118.1L374.8 117.4L376.5 127.8L385.3 126.3L386.2 132.0L391.3 126.3L393.9 126.9L396.2 124.7L399.1 125.1L400.8 127.7L400.3 130.1L395.5 127.5L394.3 132.9L390.8 136.0L389.7 139.8L388.4 140.3L386.1 139.3L381.9 152.7L377.9 153.9L377.5 155.2L375.3 156.1L373.6 155.6L371.8 157.3L369.1 156.3L368.1 154.4L367.9 154.1Z',
    'WY': 'M177.7 121.2L119.3 114.1L126.3 69.6L181.4 76.3L178.0 118.4L177.7 121.2Z',
}

STATE_LABELS = {
    'AL': (330.6, 212.7),
    'AR': (277.3, 192.3),
    'AZ': (101.8, 188.1),
    'CA': (39.6, 141.6),
    'CO': (162.9, 142.2),
    'CT': (436.4, 93.3),
    'DE': (420.3, 127.8),
    'FL': (377.8, 253.5),
    'GA': (362.3, 210.6),
    'IA': (265.6, 111.3),
    'ID': (97.2, 71.6),
    'IL': (302.7, 132.8),
    'IN': (327.4, 132.4),
    'KS': (224.4, 151.9),
    'KY': (339.0, 157.8),
    'LA': (283.1, 235.3),
    'MA': (442.1, 84.4),
    'MD': (409.2, 129.1),
    'ME': (452.5, 45.3),
    'MI': (336.6, 90.6),
    'MN': (258.0, 64.6),
    'MO': (275.6, 153.0),
    'MS': (304.1, 215.3),
    'MT': (140.8, 48.5),
    'NC': (394.0, 172.3),
    'ND': (210.9, 50.8),
    'NE': (213.4, 117.1),
    'NH': (439.7, 68.7),
    'NJ': (424.3, 113.0),
    'NM': (152.4, 193.5),
    'NV': (69.2, 123.7),
    'NY': (409.9, 83.6),
    'OH': (356.4, 124.3),
    'OK': (231.3, 185.0),
    'OR': (49.8, 65.6),
    'PA': (396.9, 110.7),
    'RI': (445.2, 90.2),
    'SC': (383.7, 193.0),
    'SD': (211.4, 84.4),
    'TN': (331.7, 177.6),
    'TX': (213.3, 230.9),
    'UT': (111.0, 132.0),
    'VA': (394.5, 149.7),
    'VT': (430.1, 66.6),
    'WA': (60.6, 28.6),
    'WI': (292.5, 81.7),
    'WV': (377.6, 139.9),
    'WY': (151.2, 95.5),
}

# Where those cities sit on the map, projected from the 'at' coordinates on
# each city's row by tools/make_map.py. Generated, not typed: to move a dot,
# edit the row it belongs to.
# Canadian provinces, from the same Natural Earth snapshot and the same
# projection as the states above. Drawn as geography, not as coverage: no
# operator carries paying passengers in Canada yet, so nothing here is ever
# highlighted and no dot lands on it.
CANADA_PATHS = {
    'AB': 'M141.1 26.8L111.3 21.8L108.5 16.7L108.7 15.0L107.7 14.4L109.2 9.8L108.9 5.9L107.9 3.6L106.4 3.2L105.8 1.2L104.0 -0.6L104.4 -1.8L100.8 -6.6L98.9 -12.2L97.0 -11.7L95.3 -17.1L92.4 -18.3L92.1 -19.1L93.0 -20.1L91.4 -21.7L89.7 -21.0L89.7 -24.6L87.6 -30.0L86.6 -31.2L86.0 -30.3L84.1 -33.1L82.3 -33.8L81.3 -36.6L82.6 -36.6L81.4 -39.2L97.5 -101.6L127.8 -94.6L158.3 -89.3L141.7 23.1L141.1 26.8Z',
    'BC': 'M97.5 -101.6L81.4 -39.2L82.6 -36.6L81.3 -36.7L81.2 -35.6L82.3 -33.8L84.1 -33.1L84.7 -31.4L86.1 -30.2L86.6 -31.2L87.6 -30.0L89.7 -24.6L89.7 -21.0L91.4 -21.7L93.0 -20.1L92.1 -19.1L92.4 -18.3L95.3 -17.1L97.0 -11.7L98.9 -12.2L100.8 -6.6L104.4 -1.8L104.0 -0.6L105.8 1.2L106.4 3.2L107.9 3.6L108.9 5.9L109.2 9.8L107.7 14.4L108.7 15.0L108.5 16.7L111.4 21.5L67.3 11.8L48.2 6.6L47.2 5.3L46.0 6.0L46.5 4.5L45.8 4.3L45.9 2.8L48.0 3.1L48.8 2.1L47.6 2.6L45.8 1.8L47.5 -1.5L45.7 0.5L44.1 0.7L41.3 -2.5L42.0 -3.8L42.7 -1.9L44.7 -2.4L43.3 -2.5L42.8 -3.6L44.4 -7.8L43.7 -8.4L43.9 -7.1L42.5 -5.3L40.0 -4.8L38.7 -5.6L37.3 -8.5L36.7 -13.3L38.8 -15.2L39.6 -17.6L37.0 -14.3L34.1 -15.1L34.2 -16.8L32.8 -15.1L29.8 -16.4L27.7 -18.2L31.8 -18.2L27.6 -19.3L29.1 -20.6L28.1 -21.3L28.8 -23.2L27.6 -22.0L24.5 -22.5L21.1 -27.0L21.9 -28.9L24.6 -31.0L29.9 -30.3L25.5 -31.8L22.5 -30.2L22.0 -32.7L23.9 -35.7L23.0 -36.0L24.2 -37.9L27.2 -38.8L28.6 -38.7L31.0 -34.1L29.2 -39.7L31.8 -41.7L31.6 -42.8L30.7 -41.0L26.6 -39.0L24.6 -38.9L20.7 -34.5L20.3 -38.9L23.0 -39.8L24.5 -41.9L21.6 -40.8L25.0 -45.9L22.7 -45.7L22.8 -49.3L20.0 -52.9L20.0 -54.8L21.5 -56.1L22.7 -55.8L21.8 -54.4L23.7 -52.2L26.3 -51.2L27.2 -49.3L26.1 -52.0L24.1 -52.7L23.3 -53.9L23.4 -56.0L25.3 -56.6L24.4 -57.6L22.5 -57.4L20.1 -56.0L19.0 -53.8L16.4 -52.9L15.2 -56.8L13.2 -59.5L16.6 -62.9L19.6 -62.9L16.5 -63.5L15.2 -66.8L16.6 -68.9L24.6 -75.1L23.6 -75.2L23.5 -76.6L21.8 -73.7L20.0 -72.2L19.9 -72.8L21.5 -75.1L23.6 -82.8L21.7 -83.6L20.5 -86.6L16.4 -91.1L14.8 -91.6L15.3 -93.7L14.1 -94.9L15.2 -96.3L13.6 -97.6L14.7 -98.5L12.5 -113.0L9.2 -119.8L9.1 -121.9L7.0 -125.1L7.5 -128.1L6.0 -131.1L0.4 -131.5L0.5 -130.7L-1.0 -130.6L-3.0 -128.0L-4.3 -128.6L-9.0 -127.9L-8.5 -131.4L-11.9 -139.2L-11.8 -140.5L-13.3 -142.4L13.6 -130.1L41.1 -119.2L69.0 -109.7L94.6 -102.3L97.5 -101.6ZM18.9 -72.3L21.0 -74.6L21.6 -78.4L22.8 -80.0L20.6 -73.9L18.9 -72.3ZM18.9 -72.3L17.2 -70.5L15.6 -70.6L17.9 -71.7L18.9 -72.3ZM-0.1 -69.4L2.0 -68.2L2.3 -66.4L1.8 -65.4L-1.3 -64.3L1.1 -63.8L2.8 -67.1L6.2 -67.0L1.1 -59.4L-3.0 -59.7L-4.0 -61.5L-1.8 -61.1L-3.8 -63.7L-4.0 -67.6L-2.6 -70.6L-1.6 -70.1L-0.1 -69.4ZM14.7 -61.6L13.3 -60.9L12.3 -62.3L11.5 -61.8L13.5 -63.4L14.6 -62.6L14.7 -61.6ZM14.2 -52.7L11.3 -58.2L12.1 -58.9L14.6 -55.7L14.9 -53.0L14.2 -52.7ZM18.5 -50.6L17.6 -51.5L18.8 -52.9L18.9 -52.0L18.5 -50.6ZM21.9 -47.3L20.6 -42.9L18.7 -41.0L19.9 -46.0L18.6 -45.4L17.9 -49.0L20.0 -51.9L22.0 -49.3L21.9 -47.3ZM1.9 -57.8L1.6 -54.7L-0.7 -55.1L1.9 -52.0L0.6 -51.1L1.0 -49.1L2.1 -48.6L1.2 -47.6L2.4 -47.1L1.3 -45.9L-2.4 -54.7L-2.4 -56.4L-1.4 -56.8L-3.4 -59.2L1.4 -58.4L1.9 -57.8ZM17.8 -43.8L16.5 -47.3L18.1 -44.8L17.8 -43.8ZM21.1 -41.4L22.5 -45.3L23.3 -45.0L21.4 -41.6L21.1 -41.4ZM20.7 -30.8L19.9 -31.1L19.8 -32.9L21.1 -33.3L20.9 -31.1L20.7 -30.8ZM22.7 -20.5L33.2 -13.6L35.4 -3.5L41.0 3.0L41.8 9.5L42.9 8.7L42.6 11.7L41.7 11.2L40.4 12.0L32.2 5.7L30.8 3.5L33.6 1.8L34.5 -0.1L33.0 1.8L28.7 1.3L26.9 -1.1L28.5 -1.7L27.5 -3.1L26.5 -3.0L27.2 -4.6L22.9 -6.2L23.6 -8.0L26.7 -7.9L24.1 -9.3L22.3 -12.5L20.6 -12.4L20.6 -15.4L19.6 -14.7L19.2 -16.1L16.3 -16.7L17.2 -20.1L19.1 -19.8L19.9 -18.7L20.7 -20.5L18.8 -21.4L18.7 -20.6L16.3 -21.0L15.2 -24.3L17.3 -24.9L19.8 -23.6L22.7 -20.5ZM34.8 -10.2L34.3 -12.8L35.0 -13.8L35.9 -12.7L35.5 -10.8L34.8 -10.2ZM22.9 -8.4L21.3 -10.3L21.8 -11.5L23.1 -11.1L23.1 -8.6L22.9 -8.4ZM40.2 -2.0L37.5 -5.2L39.5 -3.8L40.2 -2.0Z',
    'MB': 'M291.1 -52.2L261.3 -17.7L250.8 -7.5L251.2 34.5L205.0 33.4L205.0 -40.8L207.7 -84.1L252.5 -82.9L252.5 -75.5L251.5 -73.4L255.8 -69.9L255.6 -65.6L256.8 -70.1L262.8 -70.2L268.1 -55.8L265.9 -51.5L278.1 -55.6L289.3 -52.4L291.1 -52.2Z',
    'NB': 'M489.3 26.2L486.8 29.5L485.2 28.4L485.9 29.7L485.2 32.0L478.4 39.2L476.4 38.7L476.7 37.5L475.8 38.7L476.5 39.8L474.7 41.9L474.0 41.6L471.5 43.2L470.4 42.5L467.9 43.4L466.3 42.4L464.9 38.1L464.2 38.9L462.3 38.1L457.9 23.9L453.9 22.0L450.0 24.8L448.2 24.6L451.9 20.5L451.0 16.1L456.3 13.7L458.6 14.7L464.6 10.3L469.3 10.6L471.9 12.6L475.6 9.2L475.5 9.9L478.2 9.8L478.0 14.1L476.0 17.9L479.7 17.1L479.8 19.1L483.6 24.1L484.8 25.1L490.0 24.3L489.1 26.1L489.3 26.2Z',
    'NL': 'M515.7 -48.7L513.3 -54.2L469.3 -37.1L469.7 -37.8L468.2 -40.0L465.6 -41.2L469.1 -44.8L465.6 -48.4L464.5 -47.6L464.7 -45.6L463.6 -44.3L466.2 -38.0L465.6 -36.6L466.7 -32.9L465.1 -30.9L463.9 -32.1L464.1 -33.1L459.5 -35.4L457.3 -35.2L456.8 -33.5L454.9 -32.7L451.4 -34.4L450.9 -32.9L449.2 -37.8L449.2 -40.5L448.0 -41.4L447.0 -40.1L447.2 -37.9L444.6 -37.4L443.5 -43.8L441.4 -45.3L439.1 -45.4L438.6 -47.3L435.8 -49.4L436.9 -51.7L435.3 -54.8L437.5 -55.0L438.0 -56.3L434.9 -60.4L440.4 -58.5L438.2 -64.3L447.2 -60.7L455.8 -63.4L460.0 -63.6L460.6 -67.2L459.5 -69.7L461.5 -72.3L460.6 -74.0L458.6 -74.2L455.9 -76.2L456.1 -78.1L453.2 -77.9L453.4 -79.3L451.7 -79.6L451.3 -80.6L452.3 -81.8L450.3 -83.7L451.0 -86.0L449.6 -92.8L450.0 -94.8L447.1 -94.5L443.8 -97.0L446.0 -101.5L444.0 -102.8L447.1 -105.1L445.3 -105.6L442.8 -103.8L441.9 -104.5L438.3 -104.2L438.4 -105.3L441.2 -105.9L439.4 -107.5L439.2 -110.6L437.4 -109.4L436.5 -109.9L436.2 -113.9L434.5 -114.5L435.7 -116.1L434.1 -116.7L435.2 -117.7L436.8 -116.8L435.3 -114.6L438.0 -116.0L439.4 -113.1L440.1 -114.2L443.0 -111.9L442.2 -110.2L443.6 -109.5L444.8 -110.6L446.0 -109.5L443.2 -107.0L447.4 -108.6L447.9 -106.6L449.3 -107.2L451.1 -105.6L448.3 -100.9L449.8 -102.9L450.4 -102.5L453.4 -104.3L453.1 -101.2L451.0 -98.4L455.2 -101.5L456.9 -100.1L459.3 -100.3L460.3 -97.4L457.5 -95.0L461.3 -95.6L461.9 -95.3L461.6 -93.8L463.9 -93.9L466.4 -92.9L467.4 -89.6L463.1 -88.2L460.9 -88.2L461.1 -89.0L460.0 -88.2L465.7 -87.3L464.8 -85.8L468.2 -86.4L466.9 -84.4L469.1 -85.1L470.2 -83.6L469.5 -82.7L472.2 -82.3L474.0 -83.9L476.0 -82.2L477.1 -83.3L477.2 -81.8L479.2 -80.7L478.2 -75.4L480.1 -78.2L482.6 -80.0L483.5 -79.1L485.2 -79.5L484.1 -74.9L486.2 -80.2L488.0 -80.4L490.6 -77.9L493.3 -78.2L495.6 -80.4L497.1 -79.2L500.3 -79.1L499.3 -76.3L496.6 -74.7L495.3 -72.8L494.8 -70.5L490.2 -66.1L488.1 -65.2L487.0 -62.0L485.1 -62.0L487.7 -61.1L487.1 -58.2L495.0 -69.7L499.0 -72.7L496.5 -71.9L496.0 -72.4L496.8 -73.4L502.0 -74.8L505.3 -71.9L503.7 -69.1L505.5 -68.2L507.4 -72.2L509.7 -73.5L515.4 -71.1L518.8 -64.3L515.9 -61.9L520.0 -62.8L520.2 -61.6L518.6 -61.3L521.3 -60.7L521.8 -59.6L515.7 -48.7L515.7 -48.7ZM461.9 -97.3L463.0 -96.2L462.0 -95.9L460.3 -96.6L461.1 -97.3L461.9 -97.3ZM526.0 -54.4L525.9 -52.5L523.2 -50.6L524.0 -49.4L525.5 -49.7L526.1 -48.3L524.4 -35.3L525.6 -31.0L527.7 -38.0L528.6 -36.3L529.8 -37.8L532.8 -38.7L530.2 -33.1L531.7 -34.5L531.3 -31.6L535.9 -34.1L536.6 -33.1L536.8 -34.8L537.9 -30.1L538.4 -32.3L541.6 -37.2L542.8 -35.4L543.3 -36.8L545.6 -38.1L548.4 -38.0L549.6 -36.3L547.3 -30.9L549.3 -32.1L549.0 -30.7L551.0 -31.0L551.0 -29.5L549.5 -27.1L552.9 -29.8L555.4 -33.2L556.1 -32.4L556.1 -30.3L553.8 -26.9L554.7 -25.8L552.9 -24.1L554.6 -24.8L554.6 -21.3L555.4 -20.8L556.5 -21.4L557.1 -25.8L558.8 -28.5L560.2 -21.3L561.1 -21.4L561.8 -25.3L563.8 -22.6L564.9 -13.3L563.0 -12.9L561.7 -11.1L559.0 -16.2L557.6 -11.8L556.3 -11.7L555.9 -18.4L553.4 -21.1L551.5 -21.5L551.6 -15.9L551.0 -17.4L550.5 -15.5L549.2 -14.6L548.2 -8.2L545.1 -6.3L543.6 -6.5L543.5 -7.5L545.8 -10.3L546.5 -14.1L548.3 -17.6L544.3 -15.7L544.6 -13.9L543.8 -13.1L539.8 -11.7L541.2 -13.5L540.2 -15.8L535.0 -10.4L523.6 -6.9L523.4 -7.4L519.8 -4.1L517.3 -3.7L515.5 -6.6L520.0 -15.5L514.1 -13.5L515.5 -16.4L515.5 -15.2L517.0 -15.2L517.1 -21.1L520.4 -21.3L519.2 -21.9L519.4 -23.8L517.8 -23.5L517.1 -24.7L517.8 -26.9L519.6 -27.0L517.7 -28.7L517.6 -38.3L518.8 -40.1L517.6 -40.6L518.6 -42.9L518.0 -44.5L519.7 -49.9L522.2 -53.0L524.8 -53.0L524.5 -54.2L525.9 -54.6L526.0 -54.4ZM543.3 -40.7L544.4 -40.2L542.8 -38.6L542.2 -39.8L542.9 -40.6L543.3 -40.7Z',
    'NS': 'M487.9 28.8L489.3 26.2L495.8 27.0L498.5 25.7L500.2 25.5L500.1 26.6L502.2 26.2L505.1 22.2L507.3 23.9L509.2 22.8L510.7 23.6L511.7 24.8L510.7 26.1L514.2 25.6L499.8 38.7L497.5 39.1L498.2 41.3L496.5 41.5L494.6 40.5L494.5 42.5L493.6 41.6L492.8 42.3L493.7 44.6L491.0 51.1L488.1 54.4L488.4 55.7L486.0 56.7L483.4 54.4L482.4 55.4L481.5 54.8L479.8 51.5L480.8 46.1L479.2 48.2L479.4 47.4L482.3 44.3L482.9 43.2L481.6 43.9L486.1 37.8L489.0 35.2L488.7 34.4L489.7 34.4L490.2 36.2L492.2 36.9L491.4 35.7L491.8 34.7L496.7 31.3L487.3 34.0L486.6 35.3L485.5 35.3L485.4 33.9L487.8 29.4L487.9 28.8ZM511.0 19.0L512.6 17.9L511.8 19.5L512.4 19.8L512.3 21.4L514.5 20.0L515.6 16.9L513.7 17.8L515.4 12.9L516.4 13.9L519.1 13.3L519.2 14.9L520.2 15.2L517.4 20.0L515.6 21.5L511.2 23.4L509.4 22.4L507.9 17.5L510.4 6.9L511.8 6.0L513.4 8.6L514.1 14.6L512.0 17.4L511.0 19.0Z',
    'ON': 'M251.2 30.3L250.8 -7.5L261.3 -17.7L291.1 -52.2L297.1 -48.6L301.4 -44.2L313.8 -41.0L317.2 -38.7L316.5 -35.7L318.3 -38.1L325.9 -39.4L332.2 -39.3L337.1 -37.5L338.0 -35.6L337.5 -29.4L340.0 -25.2L340.8 -19.2L340.2 -16.6L346.0 -10.9L346.1 -9.7L344.7 -8.4L347.3 -8.6L353.7 -4.7L355.9 -1.0L353.5 2.4L355.8 -0.0L357.3 -0.4L360.6 0.6L363.3 3.0L369.6 40.4L371.9 45.2L376.5 50.5L380.2 51.8L386.4 52.0L392.2 55.2L393.6 54.1L395.4 56.4L397.6 57.6L399.9 57.1L401.7 57.6L409.2 53.5L411.4 53.1L412.9 53.5L412.9 56.3L414.2 57.2L411.9 60.2L408.6 62.1L403.0 69.5L396.4 74.2L395.8 73.9L396.7 72.7L391.9 74.5L393.5 73.9L393.9 74.4L395.2 73.3L395.6 74.7L397.3 73.7L396.2 75.6L397.5 75.5L396.3 76.4L391.0 75.6L381.1 79.6L377.6 82.8L375.9 86.9L379.6 87.4L381.6 86.1L381.9 88.2L383.4 90.1L373.3 93.3L371.8 95.5L374.8 95.7L366.9 95.7L364.0 96.5L361.7 98.9L360.9 101.2L360.7 100.6L356.7 103.6L356.2 105.6L354.9 104.6L352.6 105.3L351.1 104.8L351.0 102.4L356.1 100.7L355.9 99.2L354.1 98.8L355.2 93.4L357.6 91.7L360.0 88.4L359.0 80.2L361.5 73.9L360.4 70.3L357.2 67.7L360.4 67.3L361.0 69.7L362.2 70.7L363.4 70.0L362.5 72.4L364.3 72.0L364.5 73.8L366.2 72.3L368.1 73.6L371.2 74.1L371.6 72.2L370.4 70.7L371.7 69.8L372.7 70.7L373.9 70.5L373.5 69.3L373.0 70.1L370.0 67.3L370.6 66.7L369.5 66.1L369.8 64.3L367.4 64.4L366.5 62.1L365.8 62.5L362.9 59.0L360.7 59.4L360.0 58.6L356.8 59.7L356.4 58.0L355.3 58.9L350.6 58.0L345.4 58.9L339.0 58.4L337.0 58.0L336.1 55.8L333.7 57.0L333.0 56.0L333.8 54.3L333.1 54.7L332.8 53.5L334.1 52.5L330.9 51.5L331.8 47.8L328.2 44.7L329.0 41.1L323.3 41.9L321.0 41.1L316.1 33.4L310.4 33.9L304.2 31.9L302.6 32.2L303.8 34.4L303.0 36.5L300.7 38.4L302.2 35.0L301.6 33.9L300.8 34.1L299.5 39.1L298.0 39.8L299.0 37.0L295.9 38.7L295.1 42.4L293.4 43.8L290.3 43.9L289.5 42.8L284.6 43.2L283.2 42.2L278.8 44.1L275.0 41.5L271.9 41.9L271.2 40.2L267.4 38.4L264.5 38.4L262.1 39.5L255.2 37.2L252.8 30.5L251.2 30.3ZM363.2 2.5L361.3 0.4L362.1 -3.8L362.7 -0.3L363.2 2.5ZM323.6 44.1L321.0 44.3L322.4 43.5L323.7 43.9L323.6 44.1ZM304.1 33.7L305.9 33.3L306.2 34.0L304.2 35.1L303.9 34.1L304.1 33.7ZM346.5 62.7L344.4 62.2L344.6 61.4L347.1 60.8L348.0 62.2L349.8 62.5L349.7 61.0L351.1 60.4L352.7 61.4L354.1 59.9L355.6 62.4L356.3 60.5L356.3 61.5L357.1 61.6L355.3 64.8L354.5 64.5L356.0 62.8L353.9 64.7L346.7 62.9L346.5 62.7ZM339.3 60.1L338.2 60.7L337.0 58.8L338.6 58.6L339.4 59.9L339.3 60.1ZM343.3 61.3L343.9 61.8L343.1 62.7L342.3 62.4L342.9 61.4L343.3 61.3Z',
    'PE': 'M489.3 20.8L489.9 19.5L494.4 19.5L502.2 16.4L499.7 20.2L500.5 22.6L498.5 23.4L496.5 23.0L497.3 22.0L495.7 21.4L495.9 20.2L494.2 22.2L495.1 22.0L494.8 22.5L491.4 22.9L489.9 21.4L487.2 22.0L486.4 20.2L484.4 20.4L484.2 19.0L485.8 15.0L486.1 18.3L489.0 20.6L489.3 20.8Z',
    'QC': 'M462.8 11.4L461.4 13.3L458.6 14.7L456.3 13.7L452.7 14.8L452.9 15.5L451.0 16.1L452.1 19.8L451.6 21.2L448.1 24.4L447.7 22.9L446.2 23.0L442.8 32.6L443.2 35.6L442.4 38.1L443.1 41.9L441.1 46.6L441.5 47.9L440.4 50.1L439.4 49.5L438.6 50.6L437.1 50.7L436.4 54.1L411.9 60.2L419.7 53.5L421.2 46.4L427.6 38.6L433.4 34.7L438.1 30.2L443.0 18.0L449.8 8.4L462.5 -2.4L466.9 -4.4L472.0 -5.3L477.5 -3.5L477.8 -2.8L475.6 -2.4L478.0 -1.5L478.2 1.6L476.4 2.9L473.2 8.0L467.8 7.8L467.0 9.1L464.3 9.8L462.8 11.4ZM435.2 -117.7L434.1 -116.7L435.7 -116.1L434.5 -114.5L436.2 -113.9L436.5 -109.9L437.4 -109.4L439.2 -110.6L439.4 -107.5L441.2 -105.9L438.4 -105.3L438.3 -104.2L441.9 -104.5L442.8 -103.8L445.3 -105.6L447.1 -105.1L444.0 -102.8L446.0 -101.5L443.8 -97.0L447.1 -94.5L450.0 -94.8L449.6 -92.8L451.0 -86.0L450.3 -83.7L452.3 -81.8L451.3 -80.6L451.7 -79.6L453.4 -79.3L453.2 -77.9L456.1 -78.1L455.9 -76.2L458.6 -74.2L460.6 -74.0L461.5 -72.3L459.5 -69.7L460.6 -67.2L460.0 -63.6L455.8 -63.4L447.2 -60.7L438.2 -64.3L440.4 -58.5L434.9 -60.4L438.0 -56.3L437.5 -55.0L435.3 -54.8L436.9 -51.7L435.8 -49.4L438.6 -47.3L439.1 -45.4L441.4 -45.3L443.5 -43.8L444.6 -37.4L447.2 -37.9L447.0 -40.1L448.0 -41.4L449.2 -40.5L449.2 -37.8L450.9 -32.9L451.4 -34.4L454.9 -32.7L456.8 -33.5L457.3 -35.2L459.5 -35.4L464.1 -33.1L463.9 -32.1L465.1 -30.9L466.7 -32.9L465.6 -36.6L466.2 -38.0L463.6 -44.3L464.7 -45.6L464.5 -47.6L465.6 -48.4L469.1 -44.8L465.6 -41.2L468.2 -40.0L469.7 -37.8L469.3 -37.1L513.3 -54.2L515.7 -48.7L513.2 -47.9L510.1 -44.8L507.0 -43.2L504.8 -36.2L500.8 -28.4L495.9 -26.4L490.2 -22.5L488.4 -23.3L482.7 -22.0L479.3 -20.1L465.0 -16.0L456.9 -12.1L454.5 -8.9L453.6 -1.1L447.7 2.5L448.2 2.8L444.2 7.7L440.8 16.0L430.3 15.9L439.5 16.7L440.3 17.3L439.8 21.6L436.4 29.4L433.2 34.3L429.0 36.6L422.0 43.9L419.5 49.9L417.8 50.7L415.8 53.5L413.6 53.7L416.3 54.2L416.7 55.1L414.2 57.2L412.9 56.3L412.9 53.5L410.3 53.1L401.7 57.6L399.9 57.1L397.6 57.6L395.4 56.4L393.6 54.1L392.2 55.2L386.4 52.0L377.6 51.3L371.9 45.2L369.6 40.4L363.3 3.0L364.8 4.5L363.2 2.5L362.1 -3.8L363.5 -4.9L365.7 -3.5L367.1 -0.8L367.8 -4.2L365.5 -6.9L368.2 -12.8L365.4 -16.6L365.2 -18.8L363.6 -20.6L361.0 -26.8L361.7 -28.9L360.7 -29.8L361.1 -30.6L359.2 -31.3L359.7 -32.2L358.2 -32.9L355.0 -36.8L362.6 -41.9L366.7 -45.7L371.9 -54.3L372.5 -58.4L370.6 -66.8L367.3 -72.2L362.2 -76.3L355.4 -79.3L355.4 -81.9L358.7 -87.5L357.9 -88.4L358.3 -90.5L360.8 -90.0L359.8 -90.9L360.3 -94.5L358.3 -94.8L359.0 -95.5L357.1 -98.0L358.0 -99.4L356.0 -100.0L356.8 -102.0L353.4 -101.3L355.0 -104.3L354.9 -107.9L355.9 -109.3L352.4 -111.4L350.9 -115.6L354.8 -119.2L364.4 -118.6L365.4 -118.2L364.9 -117.4L367.2 -119.2L371.8 -118.3L371.5 -119.2L376.4 -122.9L381.9 -120.8L383.1 -121.1L383.2 -118.2L384.6 -119.4L386.4 -118.9L387.9 -117.8L387.1 -116.6L388.9 -118.1L390.4 -117.8L389.6 -115.8L390.9 -115.8L390.5 -114.9L392.8 -113.7L399.8 -114.7L402.0 -113.1L404.4 -115.7L405.5 -114.0L404.5 -110.0L406.1 -106.1L400.3 -104.0L406.1 -104.5L407.7 -102.4L408.1 -98.9L410.2 -99.1L410.3 -94.5L409.7 -93.9L408.5 -95.0L406.8 -92.4L409.2 -92.3L411.8 -95.1L415.2 -96.4L417.6 -95.3L419.3 -93.1L419.5 -89.7L416.1 -85.8L419.5 -88.5L420.6 -93.5L422.0 -91.8L421.4 -90.0L422.5 -93.2L424.2 -89.2L424.2 -91.6L428.5 -96.0L429.7 -99.6L431.8 -98.8L433.0 -96.8L433.1 -98.3L431.6 -100.5L432.6 -101.1L432.0 -101.7L432.8 -103.1L434.7 -104.2L432.4 -105.0L433.0 -106.7L433.8 -106.6L432.9 -107.9L435.7 -108.0L433.1 -108.7L432.1 -111.0L434.6 -111.7L433.3 -112.8L433.6 -116.5L434.6 -117.8L435.2 -117.7ZM493.6 -11.9L490.8 -10.6L484.5 -10.0L480.2 -10.5L477.0 -12.4L472.5 -12.9L472.0 -13.4L472.6 -14.1L483.9 -15.5L492.8 -13.8L493.9 -12.1L493.6 -11.9ZM499.9 7.2L501.0 7.1L499.4 8.0L499.2 5.8L502.2 2.2L499.8 6.5L499.9 7.2ZM419.5 53.0L416.6 54.1L419.2 50.4L419.6 52.8L419.5 53.0Z',
    'SK': 'M141.1 26.8L158.3 -89.3L207.7 -84.1L205.0 -40.8L205.0 33.4L173.4 30.9L141.9 26.9L141.1 26.8Z',
}

CANADA_LABELS = {
    'AB': (121.2, -42.4),
    'BC': (56.0, -56.4),
    'MB': (234.9, -27.9),
    'NB': (469.8, 25.5),
    'NL': (473.3, -63.8),
    'NS': (493.9, 37.6),
    'ON': (319.3, 16.0),
    'PE': (493.6, 20.2),
    'QC': (410.0, -33.9),
    'SK': (177.4, -25.5),
}

CITY_POINTS = {
    'Atlanta': (352.0, 199.5),
    'Austin': (228.1, 245.1),
    'Dallas': (237.5, 217.0),
    'Denver': (168.3, 134.7),
    'Houston': (251.0, 250.9),
    'Las Vegas': (74.6, 161.5),
    'Los Angeles': (41.9, 178.7),
    'Miami': (405.2, 282.1),
    'Nashville': (327.4, 174.8),
    'Orlando': (388.6, 253.5),
    'Phoenix': (96.4, 196.8),
    'San Antonio': (220.6, 254.3),
    'San Diego': (48.3, 195.7),
    'San Francisco Bay Area': (16.2, 128.5),
    'Tampa': (379.0, 261.6),
}

def esc(value):
    return html.escape(str(value), quote=True)


def versioned(path):
    # A long cache on an asset is only safe if its URL changes when its contents
    # do. Without that, a returning visitor gets new markup styled by the rules
    # they cached yesterday, which is invisible to whoever deployed it and
    # obvious to everyone else. The digest is the version.
    digest = hashlib.sha256((ROOT / path.lstrip('/')).read_bytes()).hexdigest()[:10]
    return f'{path}?v={digest}'


def stylesheet_url():
    return versioned('/style.css')


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


def operator_colour(name):
    return OPERATOR_COLOURS.get(name, '#9aa79b')


def chip(operator):
    return ('<span class="chip" style="background:' + operator_colour(operator) + '">'
            + esc(operator) + '</span>')


def stat_strip(pairs):
    return '<div class="stats">' + ''.join(
        '<div><b>' + esc(value) + '</b><span>' + esc(label) + '</span></div>'
        for value, label in pairs) + '</div>'


def coverage_legend():
    return ('<span class="legend">' + ''.join(
        '<span><i class="dot" style="background:' + operator_colour(name) + '"></i>'
        + esc(name) + '</span>' for name in OPERATOR_COLOURS) + '</span>')


def anchor(text):
    # Ids that tie a listing to its heading, so the grouping is announced rather
    # than only visible. Only operator names reach this today.
    return ''.join(ch if ch.isalnum() else '-' for ch in text.lower())


def city_listing(operator, cities):
    # One block per operator, each under the same chip the tables use, so an
    # operator reads the same way wherever it appears. Grouped rather than
    # merged because the services are run that way, but kept on one page: an
    # operator you cannot compare against the others answers half the question.
    states = sorted({c['region'] for c in cities})
    count = len(cities)
    label = (f'{count} ' + ('city' if count == 1 else 'cities')
             + f' in {len(states)} ' + ('state' if len(states) == 1 else 'states'))
    rows = [[
        '<b>' + esc(c['city']) + '</b><br>' + esc(c['region']),
        esc(c['since']),
        esc(c['open']),
        esc(c['note']) + f' <a href="{esc(c["source"])}">{esc(c["source_name"])}</a>',
    ] for c in cities]
    heading = 'op-' + anchor(operator)
    return (f'<section class="card listing" aria-labelledby="{heading}">'
            f'<h3 class="ophead" id="{heading}">{chip(operator)}<span>{esc(label)}</span></h3>'
            + ref_table(['City', 'Since', 'Access', 'Notes'], rows)
            + '</section>')


def city_listings():
    by_operator = {}
    for city in CITIES:
        by_operator.setdefault(city['operator'], []).append(city)
    # Largest first, so the order is a fact about the data rather than a
    # preference about the companies.
    order = sorted(by_operator, key=lambda name: (-len(by_operator[name]), name))
    return ''.join(city_listing(name, by_operator[name]) for name in order)


def us_map():
    # Inline SVG drawn from the same tables the page renders: the highlighted
    # states come from the city list and the dots from the city coordinates, so
    # the map cannot disagree with the rows beneath it. The outlines are Natural
    # Earth geometry, which is public domain and needs no attribution.
    service_states = {city['region'] for city in CITIES}
    by_city = {}
    for city in CITIES:
        by_city.setdefault(city['city'], []).append(city['operator'])
    out = [f'<svg viewBox="{MAP_VIEWBOX}" class="usmap" role="img" aria-label="'
           'Map of the United States and Canada showing which states have driverless '
           'ride-hailing, and which operator runs in each city">']
    # Canada first and unlabelled: it is there so the service area has a
    # boundary visible rather than appearing to stop at the 49th parallel.
    for code, path in sorted(CANADA_PATHS.items()):
        out.append(f'<path class="ca" d="{path}"/>')
    for code, path in sorted(STATE_PATHS.items()):
        css = 'st on' if code in service_states else 'st'
        out.append(f'<path class="{css}" d="{path}"/>')
    for code in sorted(service_states):
        if code in STATE_LABELS:
            x, y = STATE_LABELS[code]
            out.append(f'<text class="stlabel" x="{x:.0f}" y="{y:.0f}">{esc(code)}</text>')
    for name in sorted(by_city):
        if name not in CITY_POINTS:
            continue
        x, y = CITY_POINTS[name]
        operators = by_city[name]
        # A city with two operators gets two dots side by side rather than one
        # hiding the other, so co-location is visible instead of disguised.
        span = (len(operators) - 1) * 10
        for i, operator in enumerate(operators):
            cx = x - span / 2 + i * 10
            out.append(
                f'<circle cx="{cx:.1f}" cy="{y:.1f}" r="5.5" '
                f'fill="{operator_colour(operator)}">'
                f'<title>{esc(name)} &#8212; {esc(operator)}</title></circle>')
    out.append('</svg>')
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
<link rel="stylesheet" href="{esc(stylesheet_url())}">
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
            # Safe to cache for a day only because every page links to it with
            # the digest of its contents as a version.
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

        if path == OG_CARD:
            # Branded card, drawn from this site's own palette. Not a photograph,
            # so nothing here needs an attribution a link preview would drop.
            return self.send_raw(200, (ROOT / OG_CARD.lstrip('/')).read_bytes(),
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
        operators = sorted({c['operator'] for c in CITIES})
        regions = sorted({c['region'] for c in CITIES})
        content = f'''
<section class="hero">
  <div class="herocopy">
    <div class="eyebrow">EVERY CITY. EVERY OPERATOR.</div>
    <h1>Where driverless cars<br>actually take passengers</h1>
    {stat_strip([(len(CITIES), 'city services'), (len(operators), 'operators'), (len(regions), 'states')])}
    <p class="stamp">Last checked {esc(UPDATED)}. Every row carries a source. Services still running
    with a safety monitor are listed separately rather than counted in.</p>
  </div>
  <div class="heromap">
    <p class="meta">{coverage_legend()}</p>
    {us_map()}
    <p class="mapnote">Canada is drawn but carries no service. Waymo announced Toronto in
    October 2026 and is mapping and testing there under Ontario&#8217;s automated vehicle
    pilot; its first public riders are targeted for 2028.</p>
  </div>
</section>

<h2>Every city, and who runs it</h2>
<p class="lede">Grouped by operator, because that is how the services are run, and all on one page,
because that is the comparison coverage written per company does not make.</p>
{city_listings()}

<section class="card listing">
  <h2>Not driverless, despite the coverage</h2>
  <p>These are real services, but a human is still aboard. They are kept out of the listings above
  because merging the two is how most tracking of this industry goes wrong.</p>
  {ref_table(['Market', 'Operator', 'Notes'], [[
    esc(s['market']), esc(s['operator']),
    esc(s['note']) + f' <a href="{esc(s["source"])}">{esc(s["source_name"])}</a>'] for s in SUPERVISED])}
</section>

<section class="card listing">
  <h2>Announced, not yet carrying passengers</h2>
  {ref_table(['Market', 'Status', 'Notes'], [[
    esc(u['market']), esc(u['status']),
    esc(u['note']) + f' <a href="{esc(u["source"])}">{esc(u["source_name"])}</a>'] for u in UP_NEXT])}
</section>

<section class="card">
  <h2>Cybercabs registered in Texas</h2>
  {bar_chart(FLEET_SERIES, 'Cybercabs registered for commercial use in Texas, rising from 45 to 319 in six weeks')}
  <p class="meta">Texas DMV registrations, the only independently checkable fleet count in the United States.</p>
</section>

<section class="card">
  <h2>Why this exists</h2>
  <p>Coverage of this industry is written per company, because the companies are what people follow. That
  makes the obvious question hard to answer: <em>where can I actually get one of these, and who runs it?</em>
  This site answers that across operators instead, with a source on every line.</p>
</section>
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

<section class="card listing">
{ref_table(['Operator', 'Where', 'Fleet', 'Vehicle', 'Notes'], rows)}
</section>

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

<section class="card listing">
{ref_table(['Jurisdiction', 'Status', 'What is happening'], rows)}
</section>

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

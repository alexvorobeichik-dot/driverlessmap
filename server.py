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
_UPDATED = datetime.date(2026, 10, 18)
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
     'open': 'Rolling access',
     'note': 'Part of the February 2026 Texas wave.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
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
     'note': 'Includes the tourist corridors. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Denver', 'region': 'CO', 'operator': 'Waymo', 'since': 'Jul 2026',
     'at': (39.7392, -104.9903),
     'open': 'Rolling out',
     'note': 'One of four cities announced on 8 July 2026, and one of three that went public by September.',
     'source_name': "Investor's Business Daily", 'source': 'https://www.investors.com/news/waymo-robotaxi-service-tesla-amazon-zoox-google-alphabet'},
    {'city': 'San Diego', 'region': 'CA', 'operator': 'Waymo', 'since': 'Jul 2026',
     'at': (32.7157, -117.1611),
     'open': 'Phased, waitlist',
     'note': 'Same July announcement. Ojai vehicles deployed here at scale.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Las Vegas', 'region': 'NV', 'operator': 'Waymo', 'since': 'summer 2026',
     'at': (36.1699, -115.1398),
     'open': 'Permitted, rolling out',
     'note': 'Listed by Waymo among the cities it serves, though it had not joined the fully public cohort as of September. Zoox is also here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},
    {'city': 'Tampa', 'region': 'FL', 'operator': 'Waymo', 'since': 'Jul 2026',
     'at': (27.9506, -82.4572),
     'open': 'Rolling out',
     'note': 'Third Florida market. Tesla also runs Model Y robotaxis here.',
     'source_name': 'Waymo', 'source': 'https://waymo.com/updates/'},

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
     'note': 'The only city where Tesla uses the Cybercab. 319 Cybercabs were registered in Texas on 12 October, up from 45 at launch on 3 September, alongside 420 Model Y robotaxis.',
     'source_name': 'Texas AV Tracker, CNBC', 'source': 'https://texasavtracker.com/tesla'},
    {'city': 'Dallas', 'region': 'TX', 'operator': 'Tesla', 'since': 'Apr 2026',
     'at': (32.7767, -96.7970),
     'open': 'Open',
     'note': 'Model Y robotaxis, unsupervised. Named by Tesla as the next city for the Cybercab, with no date.',
     'source_name': 'TechCrunch', 'source': 'https://techcrunch.com/2026/04/18/tesla-brings-its-robotaxi-service-to-dallas-and-houston/'},
    {'city': 'Houston', 'region': 'TX', 'operator': 'Tesla', 'since': 'Apr 2026',
     'at': (29.7604, -95.3698),
     'open': 'Open',
     'note': 'Model Y robotaxis. Large numbers of Cybercabs were photographed here in September without a launch following.',
     'source_name': 'TechCrunch', 'source': 'https://techcrunch.com/2026/04/18/tesla-brings-its-robotaxi-service-to-dallas-and-houston/'},
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
MAP_VIEWBOX = "0 0 480 304"
STATE_PATHS = {
    'AL': 'M326.9 240.2L325.8 241.6L322.1 242.3L324.1 241.5L321.6 237.1L320.7 240.9L318.2 241.1L316.0 224.1L316.9 189.6L315.8 188.7L339.1 186.7L345.6 209.2L349.1 216.4L347.7 221.2L349.9 230.8L325.3 233.4L325.4 234.9L327.4 237.2L327.0 239.9Z',
    'AR': 'M301.4 178.7L301.6 179.6L299.5 182.5L298.1 188.9L294.8 193.5L294.5 196.1L291.7 199.8L291.8 201.4L290.4 202.3L290.6 203.9L289.3 205.7L290.5 210.8L290.2 213.1L263.2 214.1L263.1 208.0L260.2 208.0L259.0 207.0L259.1 187.4L257.3 174.8L297.0 173.3L297.9 175.6L295.4 179.2L299.8 178.8Z',
    'AZ': 'M121.0 224.7L102.2 222.0L69.2 202.5L70.8 200.3L72.1 200.5L73.3 199.5L73.4 197.9L71.9 195.4L72.5 192.7L74.5 190.9L76.4 186.2L79.6 184.1L77.8 181.4L76.6 176.4L77.7 171.5L77.8 163.9L78.7 162.8L80.2 162.7L82.8 164.7L84.4 163.2L86.1 154.1L129.8 161.3L121.5 220.8Z',
    'CA': 'M76.8 175.4L77.8 181.4L79.6 183.8L76.4 186.2L74.5 190.9L72.5 192.7L71.9 195.4L73.5 198.7L72.7 200.2L48.2 197.7L47.1 188.7L42.6 182.7L39.7 181.7L39.6 178.5L34.1 176.1L33.4 174.2L30.8 171.7L23.2 169.1L22.1 167.6L23.5 161.6L22.1 160.2L22.3 157.7L19.7 154.1L16.5 145.5L16.9 142.8L18.5 141.4L18.7 140.0L18.4 138.9L16.1 137.7L14.8 134.8L15.0 130.9L16.2 128.2L16.8 130.8L18.4 132.6L17.2 126.6L18.0 126.2L24.7 127.6L20.7 125.7L19.5 126.0L17.7 124.6L16.9 124.7L15.7 127.7L12.9 124.2L12.2 124.8L13.1 122.3L13.6 123.6L13.6 122.8L9.3 113.1L11.0 103.4L8.7 95.6L14.4 85.4L14.3 80.6L15.1 78.4L48.7 87.8L40.3 120.7L74.8 172.6ZM27.4 174.8L30.1 176.3L27.8 176.2L27.1 174.8ZM25.5 176.2L24.4 175.9L24.0 174.6L26.2 175.7ZM39.3 185.8L39.6 186.7L38.3 186.3L37.5 184.5L39.0 185.4Z',
    'CO': 'M129.8 161.3L136.0 116.5L194.5 122.4L191.7 167.6L133.1 161.8Z',
    'CT': 'M442.7 87.3L444.3 94.8L435.7 97.6L430.7 102.2L429.7 101.1L431.3 99.4L429.2 90.2L442.7 87.2Z',
    'DE': 'M425.5 132.8L419.9 134.1L416.2 120.2L417.1 118.6L419.0 118.5L418.0 120.7L418.5 122.5L422.0 127.7L424.3 129.4L423.9 131.6L425.4 132.3Z',
    'FL': 'M326.9 240.2L327.4 237.2L325.4 234.9L325.3 233.4L349.9 230.8L351.5 233.8L376.9 232.2L377.6 234.1L378.4 234.2L379.2 229.1L383.6 229.4L389.6 242.9L397.0 252.7L396.8 255.2L398.7 259.0L396.7 256.2L396.1 252.4L395.6 254.5L395.2 251.9L393.4 250.2L395.0 254.2L404.7 270.4L405.7 281.2L403.2 288.4L397.1 290.4L396.5 288.6L398.6 288.7L396.6 287.9L393.3 283.2L389.5 282.1L387.3 277.4L386.3 276.9L387.2 274.5L385.3 276.3L384.9 271.8L383.3 272.3L383.5 273.4L382.8 273.4L380.5 271.3L377.1 266.9L379.6 262.4L376.8 261.7L377.7 263.6L376.5 264.6L375.3 263.2L376.1 255.9L375.6 251.4L368.5 246.0L363.9 241.3L360.3 239.7L357.8 240.5L357.3 242.3L348.6 245.9L347.6 245.0L347.5 244.2L348.6 245.0L348.0 243.8L344.6 241.4L345.1 239.5L343.5 240.9L336.8 239.1L340.0 238.7L338.6 237.8L329.7 240.4L331.7 239.2L331.4 237.7L330.8 238.5L329.8 238.2L329.0 240.5L327.1 241.2L327.3 240.0ZM404.4 289.2L402.9 291.0L405.3 286.7Z',
    'GA': 'M349.9 230.8L347.7 221.2L349.1 216.4L345.6 209.2L339.1 186.7L361.8 183.9L360.1 187.5L365.1 189.9L368.1 194.3L378.9 203.5L384.6 212.7L387.3 214.0L385.3 216.0L385.9 217.0L384.5 220.0L385.3 220.0L383.7 222.3L384.7 223.1L384.2 224.3L383.4 224.1L383.6 229.4L379.2 229.1L378.4 234.2L377.6 234.1L376.9 232.2L351.5 233.8L350.4 231.7Z',
    'IA': 'M283.5 130.1L280.9 127.5L246.9 128.5L244.2 114.8L239.9 104.5L241.2 100.0L240.1 95.9L283.4 94.9L284.5 96.7L285.2 102.8L288.4 104.7L293.1 110.2L293.3 111.5L291.2 116.4L286.2 118.8L287.2 122.7L286.1 125.8L283.8 128.3L283.9 129.9Z',
    'ID': 'M89.7 17.3L96.9 18.8L94.6 29.6L96.3 33.6L95.8 36.2L98.4 39.1L101.4 45.4L104.4 46.9L102.2 52.1L102.3 55.2L101.2 55.8L100.6 58.4L102.2 59.8L105.0 58.0L106.3 59.3L106.5 62.7L107.8 66.1L107.5 67.4L109.7 69.4L110.2 72.8L111.2 73.9L112.5 73.0L115.1 73.7L116.4 72.9L122.1 74.1L123.5 72.0L125.5 75.2L121.1 102.9L72.7 93.6L77.2 73.7L79.0 69.7L77.4 68.3L77.3 66.6L85.8 54.6L83.6 50.5L83.4 45.4L89.3 19.0Z',
    'IL': 'M283.5 130.1L287.2 122.7L286.2 118.8L291.2 116.4L293.1 112.6L293.1 110.2L288.8 105.7L312.1 104.3L312.4 107.5L315.2 112.7L317.5 139.2L316.7 141.6L318.1 146.3L317.1 149.3L314.7 152.2L314.3 160.3L311.0 162.5L311.5 165.6L306.3 164.9L305.5 167.2L304.4 166.3L304.2 167.0L302.4 164.9L301.8 160.0L294.0 153.6L295.6 146.8L292.6 145.9L291.7 146.3L290.9 145.5L288.5 141.1L284.4 137.2L283.1 131.9Z',
    'IN': 'M314.6 157.4L314.1 156.5L314.7 152.2L317.1 149.3L318.2 145.5L316.7 141.6L317.5 139.2L315.2 112.7L317.5 113.5L320.6 111.8L337.6 110.0L340.8 141.8L341.5 142.4L338.8 144.7L336.4 144.6L336.2 146.9L332.0 153.6L328.8 151.7L327.1 155.3L324.7 154.4L322.5 156.5L318.4 155.2L318.1 156.6L316.0 155.9L315.5 157.3L314.8 157.3Z',
    'KS': 'M191.7 167.6L193.8 133.7L250.5 135.3L254.1 136.9L254.4 138.2L252.9 139.9L253.0 140.9L256.8 145.2L257.2 169.2L224.5 169.0L193.8 167.7Z',
    'KY': 'M305.5 167.2L306.3 164.9L311.5 165.6L311.0 162.5L314.3 160.3L313.9 158.5L315.5 157.3L315.8 155.9L318.1 156.6L318.4 155.2L319.6 155.3L322.5 156.5L324.7 154.4L327.1 155.3L328.8 151.7L332.0 153.6L336.2 146.9L336.4 144.6L338.5 144.8L341.5 143.0L340.7 140.6L341.4 139.5L344.3 139.6L346.4 141.9L351.3 143.7L358.1 142.1L361.1 145.0L361.3 148.1L363.7 151.4L364.9 152.8L367.9 154.1L362.3 159.5L358.8 164.2L353.9 166.9L315.2 169.8L315.7 172.0L303.3 172.9L303.7 171.9L305.4 171.3L305.9 168.1Z',
    'LA': 'M263.2 214.1L290.2 213.1L290.4 217.5L292.6 221.3L288.8 227.2L286.7 232.9L286.5 236.0L304.9 234.9L304.3 239.4L307.5 243.9L300.6 242.2L299.0 245.0L301.3 246.1L305.5 244.2L306.2 244.8L304.8 246.1L306.7 247.2L307.9 245.3L308.8 245.4L309.4 247.9L306.0 250.4L308.2 252.5L311.5 253.2L313.2 254.6L312.0 256.8L311.2 256.1L309.9 257.3L309.1 255.0L301.8 251.6L302.9 252.7L302.3 256.1L301.6 256.5L300.6 254.8L298.6 254.4L296.3 256.5L291.0 255.0L292.3 254.6L291.2 251.9L288.6 252.1L287.0 250.0L285.5 250.1L284.8 249.1L282.5 250.8L283.1 251.9L281.4 252.4L277.4 252.1L272.4 250.2L266.1 251.0L265.5 250.1L267.1 246.6L266.9 241.6L268.6 236.1L265.4 227.8L263.5 225.5L263.3 215.5ZM285.9 252.8L283.8 251.7L285.1 251.3L286.2 252.4Z',
    'MA': 'M442.7 87.3L429.2 90.2L429.1 82.1L444.5 78.8L447.2 76.0L448.1 75.8L449.3 77.9L450.4 77.8L447.8 82.2L450.6 82.7L451.9 85.1L454.5 87.1L457.6 85.5L456.2 83.5L455.0 83.3L456.0 83.0L457.4 83.9L458.5 87.0L453.3 90.1L452.4 88.2L449.3 91.7L448.7 88.8L448.1 89.4L447.0 88.7L446.0 86.4L443.3 87.1ZM454.9 91.5L452.4 92.4L453.4 91.0L454.7 91.1Z',
    'MD': 'M407.6 131.6L407.9 132.5L408.5 131.5L407.3 130.3L406.7 131.2L403.3 129.9L403.1 128.7L400.6 127.6L399.1 125.1L396.9 124.6L394.4 125.7L393.9 126.9L391.3 126.3L386.2 132.0L385.2 126.3L416.2 120.2L419.9 134.1L425.5 132.8L423.7 138.2L419.8 139.7L420.0 138.3L418.7 137.6L418.8 135.4L417.3 136.6L414.8 134.7L414.8 133.5L417.0 133.0L414.8 131.6L413.9 132.4L414.0 131.1L415.0 130.5L413.4 129.7L414.7 127.9L414.1 128.3L413.6 126.9L414.0 125.4L416.2 124.2L415.1 124.0L415.9 122.7L415.1 122.9L415.0 122.0L413.9 124.4L413.0 124.2L413.0 125.5L412.4 124.7L412.0 126.8L410.6 126.6L412.2 127.9L412.0 129.1L411.2 128.8L412.9 134.6L414.2 136.3L412.5 135.8L411.3 134.1L411.5 134.9L415.3 139.3L411.3 138.1L410.1 136.9L410.2 138.0L408.9 136.5L407.0 137.3L408.0 132.8Z',
    'ME': 'M448.0 24.4L450.0 24.9L453.9 22.1L457.8 23.9L461.9 36.2L461.8 38.4L464.0 39.3L465.5 38.9L466.3 42.5L467.9 43.4L469.2 42.8L470.3 45.8L471.4 46.1L470.4 48.2L465.8 50.8L464.8 53.4L463.7 52.3L462.1 53.5L461.4 53.0L461.5 55.8L459.1 55.6L459.6 54.2L458.9 54.3L458.8 53.0L457.7 54.9L457.9 58.8L457.1 60.3L455.1 61.9L454.5 61.1L454.3 62.3L453.7 61.2L453.6 62.9L452.9 62.4L453.2 63.9L451.9 64.1L451.8 63.4L450.4 64.8L449.9 66.0L450.6 66.4L448.1 73.5L445.4 70.5L438.9 50.2L439.7 49.5L440.6 50.0L441.5 47.9L441.0 46.6L442.6 44.0L442.8 32.7L446.1 23.0L447.6 23.0L447.8 23.9ZM463.9 54.2L463.0 54.6L463.2 55.4L462.3 55.2L462.7 53.2L463.8 53.9Z',
    'MI': 'M355.2 93.4L354.8 97.9L354.1 98.8L353.8 97.4L352.7 97.8L352.2 100.9L350.7 102.3L350.5 105.1L348.6 108.9L337.7 110.7L337.6 110.0L320.6 111.8L322.3 109.9L323.8 106.3L324.8 101.3L324.2 97.1L321.1 90.5L321.8 88.5L320.8 85.6L322.3 82.6L322.2 78.4L327.1 72.2L326.9 76.4L327.9 74.5L327.7 77.0L328.5 71.2L331.8 69.3L330.3 67.9L331.1 65.3L332.5 64.9L336.8 66.1L338.3 67.4L343.7 69.1L345.2 71.8L344.0 71.8L343.9 72.6L345.4 74.7L345.8 79.3L344.5 80.7L344.0 83.1L342.0 84.5L341.9 87.0L344.2 88.1L345.6 86.6L346.0 84.4L349.9 82.5L351.9 84.4L355.2 93.4ZM311.1 74.9L310.2 73.9L310.4 72.0L308.8 72.0L309.0 68.6L306.5 67.3L306.1 65.9L290.5 62.6L288.1 60.0L296.0 56.2L301.1 51.9L302.7 54.2L303.0 56.6L304.7 54.7L308.1 55.2L311.7 58.9L314.1 58.5L317.3 59.2L320.9 56.2L329.3 54.2L329.5 57.3L333.5 57.6L335.0 56.8L336.0 59.9L337.5 60.2L339.0 61.8L334.5 62.5L333.2 61.9L332.5 64.2L329.6 62.4L326.6 62.1L323.5 64.3L320.7 64.6L318.3 68.4L317.7 67.6L318.5 65.5L317.0 65.9L315.8 67.8L315.2 65.4L311.1 74.3ZM298.5 44.2L296.7 45.4L296.4 44.5L299.6 42.3L301.4 41.3L300.6 42.9ZM307.5 49.4L305.7 49.7L302.9 54.2L302.9 52.2L302.8 53.0L301.4 52.5L302.9 50.0L305.9 48.7L307.8 49.1ZM341.8 61.2L341.5 62.2L339.3 62.0L340.5 60.4L341.3 60.6Z',
    'MN': 'M235.8 34.5L251.2 34.5L251.2 30.3L252.8 30.5L254.8 36.9L262.1 39.5L264.6 38.4L267.4 38.4L271.2 40.2L271.9 41.9L275.0 41.5L278.8 44.1L283.2 42.2L284.6 43.3L289.5 42.8L290.3 43.9L293.4 43.9L284.1 49.1L273.6 59.9L273.8 66.3L270.7 68.4L269.3 71.2L271.0 73.7L270.6 81.7L282.0 89.4L283.4 94.9L241.3 95.8L241.4 75.7L238.3 72.3L240.3 69.6L240.6 66.3L238.9 60.6L238.4 50.1L236.5 43.6L236.5 37.9Z',
    'MO': 'M301.4 178.7L295.4 179.2L297.9 175.6L297.0 173.3L257.3 174.8L256.8 145.2L253.0 140.9L252.9 139.9L254.4 138.2L254.1 136.9L252.5 136.8L250.4 135.2L246.9 128.5L280.9 127.5L283.5 130.1L283.1 133.3L284.4 137.2L288.5 141.1L291.7 146.3L292.6 145.9L295.6 146.8L294.0 153.6L301.8 160.0L302.4 164.9L303.8 166.8L304.4 166.3L305.5 167.2L305.4 171.3L303.7 171.9L303.1 173.0L302.4 172.4L301.5 178.4Z',
    'MS': 'M316.1 188.9L316.9 189.6L316.0 224.1L318.2 241.1L313.3 240.9L309.3 242.0L307.5 243.9L304.3 239.4L304.9 234.9L286.5 236.0L286.7 232.9L288.8 227.2L292.6 221.3L290.4 217.5L290.5 210.8L289.3 205.7L296.8 190.3L313.6 189.1Z',
    'MT': 'M111.4 21.8L148.2 27.9L185.3 32.0L181.7 76.3L126.4 69.6L125.5 75.2L123.5 72.0L122.1 74.1L116.4 72.9L115.1 73.7L112.5 73.0L111.4 73.9L110.2 72.8L109.7 69.4L107.5 67.4L107.8 66.1L106.5 62.7L106.3 59.3L105.0 58.0L102.2 59.8L100.6 58.4L101.2 55.8L102.3 55.2L102.2 52.1L104.4 46.9L101.4 45.4L98.4 39.1L95.9 36.3L96.3 33.6L94.6 29.6L96.9 18.8L110.7 21.7Z',
    'NC': 'M361.8 183.9L350.9 185.5L351.1 182.5L352.8 181.9L354.2 179.1L361.7 174.8L362.4 173.0L363.9 171.9L365.3 172.4L367.3 170.2L369.5 170.0L370.5 167.8L371.9 167.0L372.2 164.1L422.2 155.6L424.5 160.2L421.2 158.9L421.5 160.4L420.3 160.2L420.9 160.9L419.5 161.0L418.2 162.6L416.2 160.6L416.9 163.6L422.6 162.2L423.2 165.3L423.8 164.8L423.6 162.9L424.9 161.9L426.0 165.2L423.1 169.2L420.3 169.3L419.2 168.0L417.9 169.4L415.1 168.9L420.3 170.8L418.6 174.4L415.6 173.1L416.8 174.3L419.0 174.8L421.5 173.8L422.4 174.2L421.4 176.2L419.7 177.4L416.1 178.1L414.9 179.6L413.5 178.4L414.3 180.6L411.5 183.9L410.6 188.0L409.9 185.5L409.9 188.5L405.0 189.8L393.3 181.4L383.1 182.7L382.7 181.2L379.8 179.5L368.0 180.7L362.0 183.9ZM422.8 155.5L427.7 162.9L424.2 158.4ZM429.0 169.3L427.7 169.8L429.0 168.8L428.1 163.4L429.2 168.8Z',
    'ND': 'M205.1 33.4L235.8 34.5L236.5 43.6L238.4 50.1L238.9 60.6L240.6 68.4L200.7 67.1L182.6 65.8L185.3 32.0L201.9 33.2Z',
    'NE': 'M193.8 133.7L194.5 122.4L177.8 121.2L179.6 98.7L225.1 101.2L228.9 103.5L234.9 103.0L241.3 107.0L245.9 120.5L246.1 126.9L250.5 135.3L195.6 133.8Z',
    'NH': 'M436.4 54.1L437.0 50.7L438.9 50.2L445.1 69.8L448.1 73.5L448.1 75.8L444.5 78.8L435.4 80.8L434.4 79.6L433.9 71.9L434.5 62.8L437.1 59.7L436.3 54.4Z',
    'NJ': 'M421.4 116.0L423.8 113.5L419.0 109.5L419.3 106.4L418.5 104.9L421.1 100.2L428.5 102.7L426.8 108.5L427.1 109.2L429.5 109.3L430.2 116.3L429.6 114.2L428.3 121.4L425.3 127.2L425.0 124.9L422.8 124.7L418.9 122.3L419.0 118.8L421.3 116.6Z',
    'NM': 'M121.0 224.7L129.8 161.3L183.0 167.0L178.2 223.2L144.3 220.0L146.2 222.9L129.5 220.7L128.9 225.8L122.2 224.9Z',
    'NV': 'M86.1 154.1L84.4 163.2L82.8 164.7L80.2 162.7L78.7 162.8L77.8 163.9L77.7 171.5L76.8 175.4L40.3 120.7L48.7 87.8L96.8 98.6L86.5 152.4Z',
    'NY': 'M381.9 88.1L381.6 86.1L386.2 84.1L393.9 84.0L398.4 83.1L400.1 81.8L403.7 78.4L402.4 75.3L403.7 73.6L401.3 72.8L408.5 62.2L410.8 60.5L422.4 57.7L425.6 73.3L426.2 72.7L427.0 73.4L429.1 82.1L428.9 90.0L431.3 99.4L429.7 101.1L430.7 102.2L428.5 105.5L428.6 101.9L427.8 100.3L428.5 102.7L418.9 99.3L416.7 95.7L414.2 94.3L378.5 101.3L377.9 98.3L384.1 91.2L383.3 88.2ZM439.9 100.0L440.0 100.8L441.6 99.1L444.6 97.9L435.2 105.0L429.7 107.3L430.3 106.6L429.6 106.4L428.7 107.4L429.2 104.9L431.4 102.9L438.9 100.2L441.3 97.7L440.4 99.2Z',
    'OH': 'M372.3 102.5L374.8 117.4L373.8 118.6L374.6 120.7L373.6 128.9L370.8 132.5L369.3 132.7L367.7 134.3L366.7 136.6L367.2 138.1L366.3 138.8L365.2 137.7L364.6 138.3L363.8 140.6L364.3 142.1L362.8 144.6L360.8 144.7L358.1 142.1L351.3 143.7L346.4 141.9L344.3 139.6L341.0 140.0L337.7 110.7L348.7 108.8L353.1 110.5L355.2 110.3L352.7 111.6L355.8 111.0L357.3 111.6L363.3 109.4L369.6 104.0Z',
    'OK': 'M257.3 174.8L259.1 187.4L259.0 207.0L252.2 203.6L250.7 204.6L248.7 203.8L245.5 204.5L242.0 206.4L239.4 204.2L238.1 204.8L236.3 203.6L234.4 206.0L233.9 204.3L231.8 204.9L229.8 203.1L227.2 204.3L225.7 201.3L222.4 202.0L221.0 201.0L216.0 200.2L214.2 197.5L213.8 198.2L211.7 198.1L208.4 195.8L209.3 174.2L182.6 172.6L183.0 167.0L220.4 168.9L257.2 169.2L257.3 173.4Z',
    'OR': 'M48.7 87.8L15.1 78.4L14.5 76.7L15.7 71.7L15.4 68.9L18.6 63.6L20.1 63.1L19.3 63.1L21.3 60.3L29.1 40.6L31.0 33.6L37.6 36.3L38.6 38.7L38.5 42.2L42.2 44.3L46.6 44.0L51.1 46.2L56.6 46.6L67.4 46.2L83.5 50.0L85.7 53.7L84.8 56.5L77.3 66.6L77.4 68.3L79.0 69.7L77.2 73.7L72.7 93.6L51.7 88.6Z',
    'PA': 'M377.9 98.3L378.5 101.3L414.2 94.3L416.7 95.7L418.4 99.1L421.1 100.2L418.5 104.9L419.3 106.4L418.7 108.5L419.0 109.5L423.8 113.5L420.8 117.2L419.0 118.5L417.1 118.6L416.2 120.2L376.5 127.7L372.3 102.5L375.6 100.1Z',
    'RI': 'M444.3 94.8L442.7 87.3L446.0 86.4L448.1 89.4L446.6 88.8L447.2 92.7L444.9 94.7Z',
    'SC': 'M387.3 214.0L384.6 212.7L378.9 203.5L368.1 194.3L365.1 189.9L360.1 187.5L361.7 183.9L368.0 180.7L379.8 179.5L382.7 181.2L383.1 182.7L393.3 181.4L405.0 189.8L402.2 192.8L400.5 197.9L399.9 196.2L400.0 199.2L397.4 201.2L395.8 203.9L394.6 203.9L394.8 205.5L391.2 208.0L388.6 208.3L390.3 209.0L389.5 210.7L387.2 209.3L388.6 211.7L387.1 213.6Z',
    'SD': 'M241.3 95.8L240.1 95.9L241.2 100.0L239.8 104.2L241.0 107.0L234.9 103.0L228.9 103.5L225.1 101.2L179.6 98.7L182.6 65.8L211.6 67.7L240.6 68.4L238.3 72.0L241.4 75.7L241.3 93.3Z',
    'TN': 'M339.1 186.7L296.8 190.3L298.5 187.9L299.5 182.5L301.6 179.6L302.4 173.0L315.7 172.0L315.2 169.8L353.9 166.9L372.2 164.1L371.9 167.0L370.5 167.8L369.5 170.0L367.3 170.2L365.3 172.4L363.9 171.9L362.4 173.0L361.7 174.8L354.2 179.1L352.8 181.9L351.1 182.5L350.9 185.5L342.1 186.4Z',
    'TX': 'M259.0 207.0L260.2 208.0L263.1 208.0L263.5 225.5L265.4 227.8L268.6 236.1L266.9 241.6L267.1 246.6L264.9 250.0L265.5 251.4L263.4 251.7L257.1 255.0L259.3 253.1L256.9 253.1L257.2 250.9L254.5 251.4L255.8 255.1L252.1 259.7L246.4 263.4L242.6 265.1L244.9 263.5L241.3 263.2L240.5 263.9L238.7 262.6L239.8 265.1L240.8 265.4L238.3 266.7L237.3 265.8L236.6 268.3L233.5 268.8L233.6 269.8L234.7 269.4L234.3 270.6L233.3 271.8L230.7 272.2L232.1 274.1L230.6 277.9L227.3 276.4L228.0 278.3L230.1 278.9L229.3 281.9L230.5 287.3L233.4 292.4L233.3 293.1L231.0 294.1L226.7 292.1L221.9 291.3L213.6 287.3L210.3 280.4L210.0 274.9L202.5 265.9L198.5 256.1L192.1 249.1L184.2 247.6L180.7 248.7L179.5 249.8L177.6 254.5L174.7 256.7L165.9 251.7L162.4 248.1L159.3 237.6L148.6 226.7L144.3 220.0L178.2 223.2L182.2 172.6L209.3 174.2L208.4 195.8L211.7 198.1L213.8 198.2L214.2 197.5L216.0 200.2L221.0 201.0L222.4 202.0L225.7 201.3L227.2 204.3L229.8 203.1L231.8 204.9L233.9 204.3L234.4 206.0L236.3 203.6L238.1 204.8L239.4 204.2L242.0 206.4L245.5 204.5L248.7 203.8L250.7 204.6L252.2 203.6L256.9 206.5ZM231.4 278.2L232.0 275.8L234.4 272.5L232.5 275.6ZM233.1 290.9L230.9 283.6L231.1 279.4L232.8 289.4Z',
    'UT': 'M129.8 161.3L86.1 154.1L96.8 98.6L121.1 102.9L119.3 114.1L136.0 116.5L130.2 158.5Z',
    'VA': 'M406.7 131.2L407.8 132.9L406.3 135.2L406.3 137.6L408.7 137.5L410.2 139.1L413.5 139.6L416.4 141.3L416.3 143.8L415.0 144.0L408.6 139.8L414.5 144.3L416.8 144.9L416.4 145.5L417.3 145.7L417.7 147.2L416.4 147.2L416.2 148.5L413.1 146.5L418.2 150.6L417.3 151.5L414.8 149.4L409.2 149.3L414.6 150.0L416.8 152.7L421.0 151.7L423.1 155.4L388.3 161.8L354.5 166.6L358.8 164.2L362.3 159.5L367.9 154.1L369.1 156.3L371.8 157.3L373.6 155.6L375.2 156.1L377.5 155.2L377.9 153.9L381.9 152.6L385.9 139.7L389.7 139.8L390.8 136.0L394.3 132.9L395.5 127.5L400.3 130.1L400.7 127.7L402.5 128.3L403.3 129.9L406.1 131.0ZM421.5 139.5L423.7 138.2L423.0 143.7L421.4 145.6L421.0 148.9L420.4 148.3L420.3 143.6L421.3 141.1Z',
    'VT': 'M422.4 57.7L436.4 54.1L437.1 59.7L434.5 62.8L434.7 66.7L433.9 71.3L434.3 79.3L435.4 80.8L429.1 82.1L428.7 81.5L427.0 73.4L426.2 72.7L425.6 73.3L422.6 58.4Z',
    'WA': 'M48.3 6.6L89.7 17.3L83.4 45.4L83.5 50.0L67.4 46.2L56.6 46.6L51.1 46.2L46.6 44.0L42.2 44.3L38.5 42.2L38.6 38.7L37.6 36.3L33.3 33.4L30.3 32.8L31.6 29.4L31.8 31.4L32.9 29.1L32.0 26.4L34.3 26.0L32.5 24.6L32.1 25.4L32.6 17.4L31.7 14.2L31.9 11.4L32.6 9.0L37.2 12.9L43.3 14.9L44.1 16.0L45.7 15.7L45.8 18.7L40.8 23.0L42.4 23.2L41.3 23.0L41.7 22.2L46.8 18.6L46.4 20.2L44.9 21.6L44.6 25.2L43.7 24.7L43.0 25.6L42.9 24.2L40.8 25.9L43.1 26.9L46.5 24.8L47.4 20.3L49.2 18.2L48.5 16.0L48.3 17.1L47.7 16.1L48.9 14.8L47.5 12.5L48.9 12.4L49.3 10.6L48.3 8.2ZM47.3 16.0L48.1 18.7L46.9 17.8L46.3 14.7L47.6 13.4L48.0 14.3L46.7 14.8L47.2 15.5Z',
    'WI': 'M288.8 105.7L284.8 101.8L284.6 97.3L283.5 95.6L282.5 90.0L270.6 81.7L271.0 73.7L269.3 72.0L270.4 68.8L273.8 66.3L273.6 59.9L274.8 58.7L276.4 59.4L279.6 58.4L284.2 56.0L285.1 56.6L284.1 60.0L285.5 59.0L289.5 60.8L290.5 62.6L306.1 65.9L306.5 67.3L309.0 68.6L308.8 72.0L310.4 72.0L310.2 73.9L311.1 74.9L309.5 76.9L308.4 81.2L310.2 80.1L311.4 77.8L312.9 77.5L313.6 78.4L310.6 95.4L312.1 104.3L292.6 105.6ZM315.3 72.3L315.5 74.5L314.0 77.7L312.9 76.5L315.0 72.6Z',
    'WV': 'M367.9 154.1L364.9 152.8L361.6 148.6L360.8 144.7L363.3 144.0L364.6 138.3L365.2 137.7L366.3 138.8L367.2 138.1L366.7 136.6L367.7 134.3L369.3 132.7L370.8 132.5L373.6 128.9L374.6 120.7L373.9 118.1L374.8 117.4L376.5 127.7L385.2 126.3L386.2 132.0L391.3 126.3L393.9 126.9L396.2 124.7L399.1 125.1L400.7 127.7L400.3 130.1L395.5 127.5L394.3 132.9L390.8 136.0L389.7 139.8L388.4 140.3L386.1 139.3L381.9 152.6L377.9 153.9L377.5 155.2L375.2 156.1L373.6 155.6L371.8 157.3L369.1 156.3L368.0 154.4Z',
    'WY': 'M177.8 121.2L119.3 114.1L126.4 69.6L181.5 76.3L178.0 118.4Z',
}

STATE_LABELS = {
    'AL': (330.6, 212.7),
    'AR': (277.3, 192.4),
    'AZ': (101.9, 188.2),
    'CA': (39.8, 141.7),
    'CO': (162.9, 142.6),
    'CT': (436.4, 93.4),
    'DE': (420.3, 127.8),
    'FL': (377.9, 253.6),
    'GA': (362.3, 210.6),
    'IA': (265.7, 111.5),
    'ID': (97.3, 71.8),
    'IL': (302.7, 132.8),
    'IN': (327.5, 132.3),
    'KS': (224.4, 152.1),
    'KY': (338.9, 157.9),
    'LA': (283.1, 235.2),
    'MA': (441.8, 84.5),
    'MD': (409.2, 129.2),
    'ME': (452.5, 45.3),
    'MI': (336.7, 90.6),
    'MN': (258.1, 64.7),
    'MO': (275.6, 153.2),
    'MS': (304.1, 215.3),
    'MT': (140.9, 48.7),
    'NC': (393.9, 172.4),
    'ND': (211.0, 50.9),
    'NE': (213.6, 117.3),
    'NH': (439.7, 68.7),
    'NJ': (424.3, 112.9),
    'NM': (152.4, 193.6),
    'NV': (69.3, 123.8),
    'NY': (409.8, 83.6),
    'OH': (356.4, 124.3),
    'OK': (231.5, 185.0),
    'OR': (49.9, 65.6),
    'PA': (396.8, 110.8),
    'RI': (445.2, 90.3),
    'SC': (383.7, 193.0),
    'SD': (211.3, 84.5),
    'TN': (331.6, 177.6),
    'TX': (213.3, 230.8),
    'UT': (111.1, 132.1),
    'VA': (394.6, 149.7),
    'VT': (430.1, 66.6),
    'WA': (60.7, 28.7),
    'WI': (292.6, 81.7),
    'WV': (377.6, 139.9),
    'WY': (151.2, 95.9),
}

# Where those cities sit on the map, projected from the 'at' coordinates on
# each city's row by tools/make_map.py. Generated, not typed: to move a dot,
# edit the row it belongs to.
CITY_POINTS = {
    'Atlanta': (352.0, 199.4),
    'Austin': (228.1, 245.0),
    'Dallas': (237.5, 216.9),
    'Denver': (168.4, 134.7),
    'Houston': (251.1, 250.8),
    'Las Vegas': (74.7, 161.4),
    'Los Angeles': (42.0, 178.7),
    'Miami': (405.2, 282.1),
    'Nashville': (327.4, 174.7),
    'Orlando': (388.5, 253.4),
    'Phoenix': (96.5, 196.8),
    'San Antonio': (220.6, 254.3),
    'San Diego': (48.4, 195.7),
    'San Francisco Bay Area': (16.4, 128.5),
    'Tampa': (379.0, 261.5),
}

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
           'Map of the United States showing which states have driverless ride-hailing, '
           'and which operator runs in each city">']
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

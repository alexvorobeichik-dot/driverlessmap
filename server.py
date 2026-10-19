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

# One colour per operator, used in the chips, the coverage grid and the legend, so
# the same operator reads the same way everywhere on the site.
OPERATOR_COLOURS = {'Waymo': '#6ee7a8', 'Zoox': '#6aa9ff', 'Tesla': '#e8a33d'}
STATE_NAMES = {'AZ': 'Arizona', 'CA': 'California', 'CO': 'Colorado', 'FL': 'Florida',
               'GA': 'Georgia', 'NV': 'Nevada', 'TN': 'Tennessee', 'TX': 'Texas'}
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
    {'city': 'San Francisco Bay Area', 'region': 'CA', 'operator': 'Zoox', 'since': 'Nov 2025',
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


# US state boundaries from Natural Earth, which is public domain and needs no
# attribution. Projected to Albers equal-area and simplified. Generated once by
# tools/make_map.py; the app does no projection maths and reads no data files at
# runtime. Re-run the tool when a city is added.
MAP_VIEWBOX = "0 0 980 620"
STATE_PATHS = {
    'AL': 'M668.6 491.3L666.2 494.2L658.7 495.6L662.8 493.8L657.7 485.0L655.9 492.7L650.6 493.0L646.2 458.2L648.1 387.3L645.7 385.4L693.7 381.3L706.9 427.5L714.1 442.3L711.3 452.1L715.9 472.0L665.3 477.2L665.4 480.4L669.6 485.1L668.7 490.5Z',
    'AR': 'M616.2 364.8L616.6 366.7L612.3 372.6L609.4 385.9L602.6 395.3L602.0 400.5L596.3 408.2L596.4 411.4L593.5 413.3L594.0 416.7L591.3 420.3L593.7 430.8L593.1 435.5L537.7 437.6L537.4 425.1L531.5 425.0L529.0 423.0L529.2 382.7L525.5 356.9L607.1 353.8L609.0 358.4L603.8 365.8L612.8 365.1Z',
    'AZ': 'M245.5 459.4L206.8 453.8L139.1 413.8L142.3 409.3L144.9 409.6L147.4 407.5L147.8 404.3L144.6 399.2L145.8 393.6L150.0 390.0L153.9 380.3L160.4 376.0L156.7 370.5L154.2 360.1L156.6 350.0L156.8 334.4L158.6 332.2L161.7 332.0L167.0 336.0L170.2 333.1L173.8 314.3L263.5 329.2L246.6 451.3Z',
    'CA': 'M154.6 358.2L156.7 370.5L160.5 375.3L153.9 380.3L150.0 390.0L145.8 393.6L144.6 399.2L147.9 406.0L146.3 409.0L96.0 404.0L93.5 385.3L84.4 373.0L78.4 371.1L78.2 364.5L67.0 359.5L65.5 355.7L60.2 350.5L44.6 345.2L42.3 342.0L45.2 329.7L42.2 326.8L42.7 321.8L37.4 314.3L30.8 296.7L31.6 291.1L34.9 288.2L35.3 285.4L34.6 283.1L29.9 280.5L27.3 274.6L27.6 266.6L28.8 261.4L30.2 261.1L31.4 266.4L34.6 270.1L32.2 257.8L33.8 257.1L47.7 259.8L39.4 255.9L36.9 256.6L33.3 253.6L31.5 254.0L29.0 260.1L23.4 252.9L21.8 254.1L23.8 248.9L24.8 251.7L24.7 249.9L15.9 230.1L19.5 210.1L14.7 194.2L26.4 173.2L26.2 163.3L27.9 158.7L97.0 178.2L79.6 245.6L150.6 352.4ZM53.2 356.8L58.7 359.9L53.9 359.7L52.5 356.9ZM49.3 359.7L47.1 359.1L46.1 356.5L50.8 358.7ZM77.7 379.4L78.2 381.3L75.5 380.5L74.0 376.7L77.0 378.6Z',
    'CO': 'M263.5 329.2L276.2 237.1L335.3 244.2L396.5 249.3L390.8 342.0L270.3 330.1Z',
    'CT': 'M906.6 177.1L909.8 192.4L892.1 198.1L881.9 207.6L879.8 205.4L883.2 201.9L878.7 183.0L906.5 176.8Z',
    'DC': 'M834.4 268.1L832.6 267.2L833.7 265.4L836.2 267.8L835.0 270.0Z',
    'DE': 'M871.2 270.6L859.6 273.2L852.0 244.7L854.0 241.5L857.8 241.2L855.8 245.8L856.8 249.5L863.9 260.0L868.7 263.5L867.9 268.1L871.0 269.5Z',
    'FL': 'M668.6 491.3L669.6 485.1L665.4 480.4L665.3 477.2L715.9 472.0L719.0 478.1L771.3 474.9L772.7 478.7L774.4 479.0L775.9 468.4L785.1 469.0L797.4 496.7L812.5 516.9L812.1 522.0L816.1 529.9L812.0 524.2L810.7 516.3L809.7 520.7L808.9 515.3L805.3 511.8L808.4 520.0L828.4 553.2L830.6 575.4L825.4 590.2L812.7 594.4L811.6 590.6L815.8 591.0L811.9 589.2L805.0 579.6L797.3 577.3L792.6 567.6L790.5 566.6L792.5 561.8L788.7 565.5L787.8 556.1L784.5 557.2L784.8 559.4L783.5 559.4L778.8 555.2L771.8 546.0L776.9 536.9L771.1 535.4L773.0 539.4L770.5 541.3L768.1 538.5L769.7 523.5L768.6 514.3L754.1 503.2L744.7 493.4L737.3 490.3L732.1 491.8L731.1 495.6L713.2 503.0L711.1 501.2L710.9 499.5L713.1 501.2L712.0 498.6L705.0 493.6L706.0 489.7L702.6 492.7L689.0 488.9L695.5 488.1L692.6 486.3L674.4 491.7L678.4 489.2L677.9 486.0L676.6 487.8L674.5 487.1L672.8 491.8L669.0 493.2L669.4 490.9ZM827.9 591.8L824.7 595.6L829.7 586.8Z',
    'GA': 'M715.9 472.0L711.3 452.1L714.1 442.3L706.9 427.5L693.7 381.3L740.3 375.6L736.7 382.9L747.0 387.9L753.2 396.8L775.5 415.8L780.9 425.7L785.6 430.3L787.0 434.7L792.6 437.4L788.5 441.6L789.8 443.5L787.0 449.8L788.6 449.7L785.3 454.4L787.4 456.2L786.2 458.5L784.6 458.1L785.1 469.0L775.9 468.4L774.4 479.0L772.7 478.7L771.3 474.9L719.0 478.1L716.9 473.7Z',
    'IA': 'M579.4 265.1L574.1 259.6L504.3 261.8L498.7 233.5L489.7 212.4L492.5 203.2L490.2 194.7L579.1 192.6L581.5 196.5L582.9 209.0L589.5 212.7L599.0 224.0L599.4 226.7L595.2 236.8L585.0 241.8L587.0 249.9L584.8 256.2L580.0 261.4L580.2 264.6Z',
    'ID': 'M181.2 33.2L196.0 36.4L191.3 58.4L194.8 66.7L193.7 72.0L199.0 78.1L205.3 91.0L207.8 93.5L211.4 93.9L206.9 104.8L207.1 111.1L204.8 112.4L203.6 117.8L206.9 120.5L212.6 116.8L215.2 119.4L215.6 126.4L218.4 133.4L217.7 136.2L222.2 140.3L223.3 147.2L225.3 149.5L227.9 147.6L233.3 149.2L236.0 147.5L247.7 149.9L250.5 145.6L254.8 152.1L245.7 209.2L146.3 190.1L155.4 149.1L159.1 140.8L155.9 138.0L155.7 134.4L173.2 109.9L168.6 101.4L168.2 91.0L180.4 36.7Z',
    'IL': 'M579.4 265.1L587.0 249.9L585.0 241.8L595.2 236.8L599.2 229.0L599.0 224.0L590.3 215.0L638.0 211.9L638.9 218.5L644.5 229.2L649.2 283.7L647.6 288.6L650.5 298.3L648.4 304.4L643.5 310.4L642.6 327.1L636.0 331.6L636.9 338.0L626.3 336.6L624.7 341.2L622.4 339.3L622.0 340.9L618.3 336.5L617.0 326.5L600.9 313.3L604.2 299.4L598.0 297.4L596.3 298.4L594.7 296.6L589.7 287.6L581.2 279.6L578.5 268.7Z',
    'IN': 'M643.3 321.1L642.2 319.2L643.5 310.4L648.4 304.4L650.6 296.7L647.6 288.6L649.2 283.7L644.5 229.2L649.3 230.9L655.6 227.4L690.6 223.7L697.2 289.0L698.6 290.3L693.0 295.0L688.1 294.8L687.7 299.5L679.1 313.2L672.5 309.3L669.0 316.8L663.9 314.9L659.5 319.3L651.1 316.6L650.4 319.5L646.1 318.0L645.2 320.9L643.7 320.8Z',
    'KS': 'M390.8 342.0L395.0 272.4L511.6 275.7L515.7 278.7L518.9 278.9L519.5 281.7L516.4 285.0L516.8 287.1L524.5 295.9L525.3 345.3L458.1 344.9L395.0 342.3Z',
    'KY': 'M624.7 341.2L626.3 336.6L636.9 338.0L636.0 331.6L642.6 327.1L641.9 323.3L645.2 320.9L645.8 318.0L650.4 319.5L651.1 316.6L653.5 316.8L659.5 319.3L663.9 314.9L669.0 316.8L672.5 309.3L679.1 313.2L687.7 299.5L688.1 294.8L692.4 295.2L698.6 291.5L696.9 286.5L698.4 284.4L704.3 284.4L708.6 289.2L718.7 293.0L721.2 291.5L727.3 292.1L732.7 289.7L738.8 295.6L739.2 301.9L744.2 308.7L746.7 311.7L752.9 314.2L741.3 325.3L734.1 335.2L724.1 340.6L644.5 346.6L645.5 351.0L620.1 353.0L620.9 350.9L624.4 349.7L625.4 343.0Z',
    'LA': 'M537.7 437.6L593.1 435.5L594.6 442.2L593.6 444.6L598.1 452.4L590.3 464.5L586.0 476.1L585.6 482.5L623.3 480.4L622.2 489.5L628.8 498.8L614.5 495.4L611.1 501.1L616.0 503.4L624.5 499.5L626.0 500.7L623.2 503.4L627.0 505.5L629.5 501.8L631.4 502.0L632.7 507.1L625.7 512.2L630.1 516.5L636.9 518.0L640.4 520.8L637.9 525.2L636.2 523.9L633.6 526.4L631.9 521.6L624.7 518.9L622.8 516.1L617.0 514.6L619.3 516.9L618.1 523.8L616.6 524.6L614.6 521.3L610.5 520.5L605.7 524.7L594.7 521.6L597.5 520.8L595.2 515.2L593.6 516.5L589.9 515.7L586.6 511.5L583.5 511.5L582.1 509.6L577.4 512.9L578.5 515.3L575.0 516.3L566.8 515.7L556.6 511.8L543.6 513.4L542.4 511.5L545.7 504.4L545.3 494.2L548.7 482.8L542.1 465.7L538.2 461.0L537.8 440.5ZM584.4 517.2L580.0 514.9L582.6 514.1L585.0 516.3Z',
    'MA': 'M906.6 177.1L878.7 183.0L878.6 166.5L910.2 159.6L915.7 153.8L917.6 153.4L920.0 157.7L922.3 157.6L917.0 166.7L922.7 167.6L925.5 172.6L930.7 176.7L933.0 176.8L937.2 173.3L934.2 169.2L931.8 168.9L933.9 168.1L936.8 170.1L939.0 176.3L928.2 182.8L926.4 178.9L920.1 186.0L918.9 180.2L917.7 181.5L915.4 179.9L913.3 175.2L907.8 176.7ZM931.6 185.6L926.5 187.5L928.5 184.8L931.1 184.8Z',
    'MD': 'M834.4 268.1L835.0 270.0L836.2 267.8L833.7 265.4L832.6 267.2L825.6 264.6L825.2 262.1L820.1 259.9L817.0 254.7L812.4 253.8L807.3 255.9L806.2 258.4L800.9 257.1L798.3 261.7L796.4 261.5L790.3 268.8L788.4 257.1L852.0 244.7L859.6 273.2L871.2 270.6L867.5 281.6L859.4 284.7L859.8 281.9L857.1 280.5L857.4 275.8L854.4 278.4L849.1 274.4L849.1 271.9L853.7 270.9L849.3 268.1L847.3 269.7L847.5 267.1L849.6 265.8L846.3 264.2L849.1 260.5L847.7 261.2L846.8 258.4L847.6 255.3L852.1 252.9L849.8 252.5L851.5 249.8L849.9 250.3L849.7 248.4L848.0 249.4L847.4 253.2L845.4 252.8L845.5 255.5L844.1 253.9L843.4 258.3L840.7 257.8L843.8 260.6L843.5 262.9L841.8 262.4L845.3 274.3L848.0 277.7L844.5 276.8L841.9 273.2L842.4 274.8L850.3 283.9L841.9 281.4L839.6 278.9L839.7 281.2L837.0 278.1L833.1 279.8L835.2 270.6Z',
    'ME': 'M917.5 47.8L921.4 48.8L929.4 43.0L937.6 46.8L946.0 72.0L945.8 76.6L950.4 78.5L953.3 77.5L954.9 84.9L958.2 86.8L961.0 85.6L963.3 91.7L965.5 92.4L963.4 96.8L954.0 102.1L951.8 107.4L949.6 105.2L946.5 107.5L944.8 106.5L945.2 112.4L940.3 111.9L941.2 109.1L939.8 109.3L939.5 106.5L937.3 110.5L937.8 118.4L936.0 121.6L931.9 124.9L930.8 123.2L930.4 125.8L929.2 123.4L928.9 126.9L927.5 125.9L928.1 129.0L925.4 129.4L925.1 127.9L922.3 130.8L921.4 133.3L922.7 134.0L917.6 148.8L912.1 142.6L898.7 100.7L900.4 99.3L902.2 100.3L904.0 96.1L903.1 93.4L906.3 88.1L906.7 64.8L913.5 44.9L916.7 44.9L917.0 46.9ZM950.1 109.1L948.3 109.9L948.7 111.6L946.9 111.0L947.6 106.9L949.9 108.4Z',
    'MI': 'M726.7 189.6L725.8 198.9L724.4 200.7L723.9 197.7L721.7 198.6L720.6 205.0L717.6 208.0L717.1 213.6L713.2 221.3L690.8 225.0L690.6 223.7L655.6 227.4L659.2 223.6L662.3 216.0L664.2 205.9L663.0 197.2L656.7 183.7L658.1 179.5L656.1 173.6L659.2 167.3L658.9 158.8L661.0 157.5L661.7 153.5L664.8 152.1L668.9 146.0L668.5 154.6L670.6 150.7L670.2 155.9L672.2 149.7L671.8 144.1L678.6 140.1L675.5 137.2L677.2 131.9L680.1 131.1L688.9 133.5L692.0 136.3L703.2 139.7L706.1 145.2L703.7 145.2L703.5 146.8L706.6 151.2L707.4 160.6L704.7 163.4L703.7 168.5L699.7 171.2L699.3 176.5L704.1 178.6L707.1 175.7L707.9 171.0L715.8 167.1L719.9 171.0L726.7 189.6ZM636.2 151.5L634.2 149.6L634.7 145.6L631.3 145.6L631.8 138.6L626.6 136.0L625.8 133.1L614.7 131.9L593.8 126.3L591.8 122.5L588.8 121.0L605.1 113.1L615.5 104.3L618.8 109.1L619.5 113.9L622.9 110.2L629.9 111.0L637.2 118.7L642.3 117.8L648.8 119.3L656.2 113.2L673.6 109.0L674.0 115.4L682.2 116.0L685.2 114.4L687.3 120.8L690.4 121.4L693.4 124.7L684.3 126.1L681.6 125.0L680.1 129.5L674.2 126.0L668.0 125.3L661.5 129.8L655.8 130.5L650.9 138.3L649.6 136.6L651.3 132.2L648.3 133.0L645.7 137.0L644.5 132.1L636.2 150.4ZM610.3 88.6L606.6 91.0L605.9 89.1L612.4 84.6L616.2 82.6L614.5 85.8ZM628.6 99.1L625.1 99.9L619.2 109.1L619.3 104.9L619.1 106.5L616.2 105.6L619.3 100.4L625.3 97.7L629.4 98.5ZM699.2 123.4L698.5 125.4L694.0 125.1L696.5 121.8L698.2 122.2Z',
    'MN': 'M481.5 68.5L513.0 68.6L513.0 60.0L516.3 60.4L520.5 73.4L535.5 78.8L540.5 76.6L546.4 76.5L554.1 80.3L555.6 83.9L561.9 83.0L569.7 88.3L578.8 84.3L581.6 86.6L591.7 85.7L593.4 87.9L599.8 87.8L580.7 98.5L558.9 120.7L559.4 133.9L553.2 138.2L550.1 144.1L553.7 149.1L552.9 165.5L576.3 181.5L579.1 192.6L492.7 194.6L492.9 153.2L486.6 146.3L490.7 140.6L491.2 133.8L487.7 122.1L486.8 100.6L482.8 87.2L482.9 75.6Z',
    'MO': 'M616.2 364.8L603.8 365.8L609.0 358.4L607.1 353.8L525.5 356.9L524.5 295.9L516.8 287.1L516.4 285.0L519.5 281.7L518.9 278.9L515.7 278.7L511.3 275.5L504.3 261.8L574.1 259.6L579.4 265.1L578.6 271.7L581.2 279.6L589.7 287.6L596.3 298.4L598.0 297.4L604.2 299.4L600.9 313.3L617.0 326.5L618.3 336.5L621.0 340.4L622.4 339.3L624.7 341.2L624.4 349.7L620.9 350.9L619.7 353.2L618.2 351.8L616.3 364.1Z',
    'MS': 'M646.3 385.9L648.1 387.3L646.2 458.2L650.6 493.0L640.6 492.8L632.5 495.0L628.8 498.8L622.2 489.5L623.3 480.4L585.6 482.5L586.0 476.1L590.3 464.5L598.1 452.4L593.6 444.6L593.7 430.8L591.3 420.3L594.0 416.7L593.7 412.9L596.4 411.4L596.3 408.2L601.2 402.7L602.6 395.3L606.8 388.7L641.2 386.3Z',
    'MT': 'M225.7 42.4L301.4 54.9L377.5 63.4L370.3 154.5L256.7 140.7L254.8 152.1L250.5 145.6L247.7 149.9L236.0 147.5L233.3 149.2L227.9 147.6L225.7 149.6L223.3 147.2L222.2 140.3L217.7 136.2L218.4 133.4L215.6 126.4L215.2 119.4L212.6 116.8L206.9 120.5L203.6 117.8L204.8 112.4L207.1 111.1L206.9 104.8L211.4 93.9L207.8 93.5L205.3 91.0L199.0 78.1L193.9 72.2L194.8 66.7L191.3 58.4L196.0 36.4L224.3 42.2Z',
    'NC': 'M740.3 375.6L717.9 378.8L718.3 372.6L721.9 371.3L724.7 365.6L740.0 356.9L741.4 353.2L744.6 350.9L746.2 350.2L747.5 351.9L751.7 347.4L756.1 347.0L758.1 342.4L761.1 340.8L761.6 334.8L864.3 317.4L869.1 326.8L862.4 324.3L863.0 327.3L860.6 326.7L861.7 328.3L858.8 328.5L856.2 331.8L852.0 327.6L853.5 333.7L865.2 331.0L866.4 337.4L867.7 336.3L867.3 332.3L870.0 330.3L872.2 337.2L866.3 345.4L860.4 345.6L858.2 342.9L855.6 345.8L849.8 344.7L860.6 348.6L857.0 355.9L850.9 353.3L853.3 355.9L857.9 356.9L862.9 354.7L864.9 355.6L862.8 359.8L859.2 362.2L851.8 363.7L849.3 366.7L846.6 364.2L848.1 368.7L842.3 375.6L840.6 384.1L839.1 378.9L839.1 385.0L829.0 387.7L805.0 370.4L784.0 373.1L783.3 370.1L780.2 367.0L778.3 368.5L777.2 366.5L752.9 368.9L740.6 375.5ZM865.7 317.1L875.7 332.3L868.5 323.1ZM878.4 345.5L875.8 346.5L878.3 344.6L876.5 333.3L878.8 344.4Z',
    'ND': 'M418.2 66.3L481.5 68.5L482.8 87.2L486.8 100.6L487.7 122.1L491.3 138.3L409.2 135.6L372.0 132.9L377.5 63.4L411.7 65.9Z',
    'NE': 'M395.0 272.4L396.5 249.3L362.2 246.7L366.0 200.5L459.3 205.7L467.2 210.4L471.7 208.9L479.4 209.3L492.6 217.6L502.0 245.2L502.6 258.5L511.6 275.7L398.7 272.6Z',
    'NH': 'M893.6 108.9L894.9 101.8L898.7 100.7L911.5 141.1L917.6 148.8L917.6 153.4L910.2 159.6L891.5 163.8L889.4 161.3L888.3 145.5L890.2 134.6L889.6 126.8L895.0 120.3L893.4 109.4Z',
    'NJ': 'M862.8 236.1L867.7 230.9L857.8 222.6L858.4 216.3L856.9 213.3L862.1 203.5L877.3 208.7L873.8 220.6L874.5 222.1L879.4 222.3L880.8 236.6L879.5 232.4L878.7 241.3L876.5 243.3L876.9 247.1L870.7 259.1L870.1 254.4L865.7 253.9L857.6 249.0L857.9 241.8L862.6 237.4Z',
    'NM': 'M245.5 459.4L263.5 329.2L372.9 340.8L363.1 456.3L293.5 449.8L297.2 455.6L263.0 451.3L261.7 461.6L247.9 459.8Z',
    'NV': 'M173.8 314.3L170.2 333.1L167.0 336.0L161.7 332.0L158.6 332.2L156.8 334.4L156.6 350.0L154.6 358.2L79.6 245.6L97.0 178.2L195.7 200.4L174.5 310.7Z',
    'NY': 'M781.6 178.6L781.0 174.6L790.5 170.4L800.7 169.2L806.2 170.2L815.4 168.4L819.0 165.8L826.4 158.8L823.6 152.5L826.5 148.8L821.4 147.3L836.3 125.4L840.9 121.9L864.7 116.3L868.3 128.3L868.6 137.4L871.4 148.3L872.6 147.1L874.3 148.4L878.6 166.5L878.1 182.6L883.2 201.9L879.8 205.4L881.9 207.6L877.3 214.5L877.6 207.2L875.8 203.7L877.3 208.7L857.6 201.8L853.1 194.3L848.0 191.5L774.5 205.9L773.4 199.6L786.0 185.1L784.4 179.0ZM900.7 203.1L899.9 204.9L901.0 204.8L904.2 201.3L910.4 198.9L891.1 213.5L879.7 218.2L881.1 216.7L879.7 216.3L877.7 218.4L878.9 213.1L883.3 209.0L898.8 203.5L903.7 198.4L901.8 201.6Z',
    'OH': 'M761.9 208.3L767.0 239.0L764.9 241.3L766.6 245.7L764.5 262.5L758.8 269.9L755.7 270.3L752.3 273.6L750.4 278.3L751.3 281.4L749.4 282.9L747.2 280.5L746.1 281.8L744.5 286.6L745.3 289.6L742.3 294.8L738.2 295.0L732.7 289.7L727.3 292.1L721.2 291.5L718.7 293.0L708.6 289.2L704.3 284.4L697.5 285.3L690.8 225.0L713.4 221.2L722.3 224.7L726.7 224.4L721.5 226.9L728.0 225.7L730.9 226.9L743.4 222.4L756.4 211.4Z',
    'OK': 'M525.5 356.9L529.2 382.7L529.0 423.0L515.0 416.0L512.1 418.0L507.9 416.4L501.3 417.8L494.2 421.8L488.7 417.3L486.0 418.4L482.5 416.1L478.4 421.1L477.5 417.5L473.1 418.7L469.1 415.0L463.8 417.6L460.5 411.3L453.8 412.7L450.9 410.7L440.6 408.9L437.0 403.4L436.1 404.9L431.8 404.8L425.1 399.9L426.9 355.5L372.0 352.3L372.9 340.8L449.6 344.7L525.3 345.3L525.5 354.0Z',
    'OR': 'M97.0 178.2L27.9 158.7L26.7 155.4L29.0 144.9L28.4 139.2L35.1 128.4L38.1 127.4L36.5 127.2L40.7 121.7L56.7 81.1L60.5 66.7L74.2 72.3L76.1 77.2L75.9 84.5L83.5 88.6L92.7 88.1L101.8 92.5L113.1 93.5L135.3 92.6L168.4 100.4L172.9 107.9L171.1 113.8L155.7 134.4L155.9 138.0L159.1 140.8L155.4 149.1L146.3 190.1L103.1 179.8Z',
    'PA': 'M773.4 199.6L774.5 205.9L848.0 191.5L853.1 194.3L856.7 201.2L862.1 203.5L856.9 213.3L858.4 216.3L857.3 220.5L857.8 222.6L867.7 230.9L861.6 238.5L857.8 241.2L854.0 241.5L852.0 244.7L770.4 260.2L761.9 208.3L768.7 203.4Z',
    'RI': 'M909.8 192.4L906.6 177.1L913.3 175.2L917.7 181.5L914.6 180.2L915.7 188.1L911.1 192.2Z',
    'SC': 'M792.6 437.4L787.0 434.7L785.6 430.3L780.9 425.7L775.5 415.8L753.2 396.8L747.0 387.9L736.7 382.9L740.1 375.6L752.9 368.9L777.2 366.5L778.3 368.5L780.2 367.0L783.3 370.1L784.0 373.1L805.0 370.4L829.0 387.7L823.2 393.9L819.8 404.3L818.5 400.7L818.7 407.1L813.4 411.2L810.1 416.7L807.6 416.6L808.0 419.9L800.6 425.1L795.4 425.7L798.8 427.2L797.3 430.6L792.4 427.6L795.3 432.6L792.3 436.6Z',
    'SD': 'M492.7 194.6L490.2 194.7L492.5 203.2L489.7 211.8L492.1 217.5L479.4 209.3L471.7 208.9L467.2 210.4L459.3 205.7L366.0 200.5L372.0 132.9L431.6 136.8L491.3 138.3L486.5 145.6L492.9 153.2L492.7 189.4Z',
    'TN': 'M693.7 381.3L606.8 388.7L610.2 383.8L612.3 372.6L616.6 366.7L618.1 353.1L645.5 351.0L644.5 346.6L724.1 340.6L761.6 334.8L761.1 340.8L758.1 342.4L756.1 347.0L751.7 347.4L747.5 351.9L746.2 350.2L744.6 350.9L741.4 353.2L740.0 356.9L724.7 365.6L721.9 371.3L718.3 372.6L717.9 378.8L699.8 380.7Z',
    'TX': 'M529.0 423.0L531.5 425.0L537.4 425.1L538.2 461.0L542.1 465.7L548.7 482.8L545.3 494.2L545.7 504.4L541.2 511.4L542.3 514.3L538.2 514.8L525.1 521.6L529.7 517.8L524.6 517.8L525.3 513.2L519.7 514.3L522.5 521.9L514.8 531.4L503.2 538.8L495.4 542.3L500.0 539.0L492.6 538.5L491.1 539.9L487.3 537.2L489.6 542.3L491.7 543.0L486.5 545.7L484.5 543.8L483.1 549.0L476.7 550.1L476.9 552.0L479.1 551.3L478.3 553.7L476.3 556.2L470.9 557.1L473.8 560.9L470.6 568.7L463.9 565.6L465.4 569.6L469.6 570.8L468.1 576.9L470.4 588.0L476.4 598.5L476.3 600.0L471.4 602.0L462.6 598.0L452.8 596.2L435.7 588.0L428.9 573.9L428.4 562.6L413.0 544.1L404.6 524.0L391.7 509.6L375.3 506.4L368.2 508.7L365.7 511.0L361.8 520.6L355.9 525.2L337.7 514.8L330.5 507.4L324.2 485.9L302.1 463.5L293.5 449.8L363.1 456.3L371.3 352.3L426.9 355.5L425.1 399.9L431.8 404.8L436.1 404.9L437.0 403.4L440.6 408.9L450.9 410.7L453.8 412.7L460.5 411.3L463.8 417.6L469.1 415.0L473.1 418.7L477.5 417.5L478.4 421.1L482.5 416.1L486.0 418.4L488.7 417.3L494.2 421.8L501.3 417.8L507.9 416.4L512.1 418.0L515.0 416.0L524.7 421.9ZM472.4 569.4L473.6 564.3L478.5 557.5L474.5 563.9ZM475.8 595.5L471.2 580.3L471.7 571.7L475.2 592.3Z',
    'UT': 'M263.5 329.2L173.8 314.3L195.7 200.4L245.7 209.2L242.1 232.1L276.2 237.1L264.3 323.4Z',
    'VA': 'M832.6 267.2L834.4 268.1L834.7 270.7L831.8 275.5L831.8 280.3L836.6 280.3L839.8 283.4L846.6 284.5L852.5 288.0L852.2 293.2L849.5 293.6L836.4 284.9L848.6 294.2L853.3 295.5L852.4 296.6L854.4 297.1L855.1 300.2L852.5 300.0L852.1 302.8L845.7 298.6L856.2 307.2L854.4 309.0L849.2 304.6L837.7 304.4L848.7 305.9L853.3 311.5L857.4 309.3L861.9 309.3L866.2 317.0L794.7 330.1L725.2 340.0L734.1 335.2L741.3 325.3L752.9 314.2L755.2 318.8L760.7 320.8L764.6 317.3L767.9 318.4L772.4 316.6L773.3 313.8L781.6 311.3L789.8 284.6L797.6 284.9L799.8 277.1L807.0 270.8L809.5 259.7L819.3 265.0L820.3 260.1L824.0 261.3L825.6 264.6L831.3 266.8ZM862.9 284.3L867.5 281.6L866.1 293.0L862.8 296.9L861.9 303.6L860.8 302.4L860.5 292.8L862.5 287.6Z',
    'VT': 'M864.7 116.3L893.6 108.9L895.0 120.3L889.6 126.8L890.2 134.6L888.4 144.1L889.3 160.6L891.5 163.8L878.6 166.5L877.8 165.2L874.3 148.4L872.6 147.1L871.4 148.3L865.2 117.7Z',
    'WA': 'M96.1 11.3L181.2 33.2L168.2 91.0L168.4 100.4L135.3 92.6L113.1 93.5L101.8 92.5L92.7 88.1L83.5 88.6L75.9 84.5L76.1 77.2L74.2 72.3L65.2 66.3L59.2 65.0L61.8 58.0L62.2 62.2L64.5 57.5L62.3 54.8L62.5 52.0L67.2 51.1L63.7 48.2L62.7 49.9L63.9 33.4L61.9 26.9L62.4 21.1L63.8 16.1L73.2 24.1L85.7 28.2L87.5 30.6L90.8 30.0L91.0 36.2L80.6 44.9L84.0 45.4L81.8 45.0L82.6 43.3L93.1 35.9L92.3 39.2L89.0 42.0L89.9 45.8L88.5 49.4L86.7 48.4L85.1 50.2L85.0 47.4L80.7 50.9L85.4 52.9L92.3 48.7L94.2 39.4L98.0 35.1L96.5 30.6L96.2 32.8L94.8 30.7L97.3 28.2L94.5 23.3L97.3 23.2L98.1 19.5L96.2 14.6ZM94.0 30.5L95.7 36.1L93.2 34.2L91.9 27.9L94.6 25.3L95.6 27.0L92.7 28.1L93.9 29.4Z',
    'WI': 'M590.3 215.0L582.0 206.9L581.7 197.7L579.3 194.1L577.4 182.7L552.9 165.5L553.7 149.1L550.2 145.5L552.5 139.0L559.4 133.9L558.9 120.7L561.5 118.3L564.8 119.7L571.4 117.8L580.8 112.7L582.7 113.9L580.7 121.0L583.5 118.9L591.8 122.5L593.8 126.3L614.7 131.9L625.8 133.1L626.6 136.0L631.8 138.6L631.3 145.6L634.7 145.6L634.2 149.6L636.2 151.5L632.9 155.7L630.6 164.4L634.2 162.3L636.7 157.5L639.7 156.8L641.2 158.8L635.0 193.7L638.0 211.9L598.0 214.6ZM644.8 146.2L645.0 150.9L642.0 157.3L639.9 154.8L644.2 146.8Z',
    'WV': 'M752.9 314.2L746.7 311.7L739.9 303.0L738.3 295.0L743.4 293.6L746.1 281.8L747.2 280.5L749.4 282.9L751.3 281.4L750.4 278.3L752.3 273.6L755.7 270.3L758.8 269.9L764.5 262.5L766.6 245.7L765.1 240.3L767.0 239.0L770.4 260.2L788.4 257.1L790.3 268.8L796.4 261.5L798.3 261.7L800.9 257.1L806.2 258.4L811.0 253.9L817.0 254.7L820.3 260.1L819.3 265.0L809.5 259.7L807.0 270.8L799.8 277.1L797.6 284.9L795.0 285.9L790.2 283.9L781.6 311.3L773.3 313.8L772.4 316.6L767.9 318.4L764.6 317.3L760.7 320.8L755.2 318.8L753.1 315.0Z',
    'WY': 'M362.2 246.7L303.0 240.6L242.1 232.1L256.7 140.7L369.8 154.5L362.7 240.9Z',
}

STATE_LABELS = {
    'AL': (676.2, 434.8),
    'AR': (566.6, 393.0),
    'AZ': (206.2, 384.5),
    'CA': (78.6, 288.8),
    'CO': (331.6, 290.6),
    'CT': (893.5, 189.6),
    'DC': (834.5, 267.4),
    'DE': (860.4, 260.2),
    'FL': (773.3, 518.8),
    'GA': (741.3, 430.4),
    'IA': (542.7, 226.8),
    'ID': (196.8, 145.2),
    'IL': (618.8, 270.5),
    'IN': (669.9, 269.6),
    'KS': (458.0, 310.3),
    'KY': (693.2, 322.0),
    'LA': (578.6, 481.0),
    'MA': (904.7, 171.3),
    'MD': (837.7, 263.2),
    'ME': (926.6, 90.7),
    'MI': (688.6, 183.9),
    'MN': (527.1, 130.6),
    'MO': (563.2, 312.4),
    'MS': (621.8, 440.0),
    'MT': (286.4, 97.8),
    'NC': (806.3, 351.9),
    'ND': (430.4, 102.3),
    'NE': (435.7, 238.8),
    'NH': (900.3, 138.8),
    'NJ': (868.7, 229.8),
    'NM': (310.1, 395.5),
    'NV': (139.3, 252.1),
    'NY': (838.9, 169.4),
    'OH': (729.2, 253.1),
    'OK': (472.4, 377.9),
    'OR': (99.4, 132.6),
    'PA': (812.2, 225.4),
    'RI': (911.7, 183.2),
    'SC': (785.3, 394.3),
    'SD': (431.1, 171.3),
    'TN': (678.2, 362.7),
    'TX': (435.2, 472.0),
    'UT': (225.2, 269.1),
    'VA': (807.6, 305.4),
    'VT': (880.7, 134.6),
    'WA': (121.6, 56.6),
    'WI': (598.0, 165.6),
    'WV': (772.7, 285.1),
    'WY': (307.5, 194.7),
}

CITY_POINTS = {
    'Atlanta': (720.2, 407.5),
    'Austin': (465.6, 501.1),
    'Dallas': (484.9, 443.4),
    'Denver': (342.8, 274.4),
    'Houston': (512.8, 513.1),
    'Las Vegas': (150.3, 329.4),
    'Los Angeles': (83.2, 364.9),
    'Miami': (829.5, 577.3),
    'Nashville': (669.6, 356.7),
    'Orlando': (795.2, 518.5),
    'Phoenix': (195.2, 402.0),
    'San Antonio': (450.2, 520.2),
    'San Diego': (96.3, 399.7),
    'San Francisco Bay Area': (30.5, 261.8),
    'Tampa': (775.5, 535.0),
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


def coverage_grid():
    # Which operators run in which state, read straight from the city table so it
    # cannot drift from the figures below it.
    by_state = {}
    for city in CITIES:
        by_state.setdefault(city['region'], set()).add(city['operator'])
    out = ['<div class="coverage">']
    for state in sorted(by_state, key=lambda s: STATE_NAMES.get(s, s)):
        dots = ''.join(
            '<i class="dot" style="background:' + operator_colour(name)
            + '" title="' + esc(name) + '"></i>'
            for name in OPERATOR_COLOURS if name in by_state[state])
        out.append('<div class="cov"><b>' + esc(STATE_NAMES.get(state, state))
                   + '</b><span class="dots">' + dots + '</span></div>')
    out.append('</div>')
    return ''.join(out)


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
        rows = [[
            '<b>' + esc(c['city']) + '</b><br>' + esc(c['region']),
            chip(c['operator']),
            esc(c['since']),
            esc(c['open']),
            esc(c['note']) + f' <a href="{esc(c["source"])}">{esc(c["source_name"])}</a>',
        ] for c in CITIES]
        operators = sorted({c['operator'] for c in CITIES})
        regions = sorted({c['region'] for c in CITIES})
        content = f'''
<section class="hero">
  <div class="eyebrow">EVERY CITY. EVERY OPERATOR.</div>
  <h1>Where driverless cars<br>actually take passengers</h1>
  {stat_strip([(len(CITIES), 'city services'), (len(operators), 'operators'), (len(regions), 'states')])}
  <p class="stamp">Last checked {esc(UPDATED)}. Every row carries a source. Services still running
  with a safety monitor are listed separately rather than counted in.</p>
</section>

<h2>Where it runs</h2>
<p class="meta">{coverage_legend()}</p>
{us_map()}
{coverage_grid()}

<h2>Every city, and who runs it</h2>
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

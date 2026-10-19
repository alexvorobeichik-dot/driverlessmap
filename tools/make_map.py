"""Regenerate the map in server.py from Natural Earth.

The home page draws its map from three tables in server.py: STATE_PATHS (state
outlines), STATE_LABELS (where each state's abbreviation sits) and CITY_POINTS
(one dot per city). None of them is typed by hand. This tool produces all three
from the same public-domain source the committed geometry came from, which is
why adding a city is one line of coordinates in the CITIES table and one run of
this.

    python tools/make_map.py                  # report what would change
    python tools/make_map.py --write          # rewrite server.py in place
    python tools/make_map.py --source FILE    # use a local copy of the source

A --write run replaces three blocks in server.py and nothing else, but it does
type the file it is writing: run the tests afterwards, since they are what say
the map still adds up.

The source is fetched once into tools/.cache/ and reused. Its digest is pinned,
because Natural Earth does revise these files: if the download does not match,
the tool stops rather than quietly redrawing every state line on a live site.

The transform below was fitted against the geometry already committed, so a
plain re-run reproduces the existing map to within a fraction of a pixel rather
than nudging it. That is deliberate: this tool exists to place a new city, not
to redraw the country.
"""
import argparse
import hashlib
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SERVER = ROOT / 'server.py'
CACHE = TOOLS / '.cache'

SOURCE_URL = ('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/'
              'v5.1.2/geojson/ne_50m_admin_1_states_provinces_lakes.geojson')
SOURCE_SHA256 = 'b92c3f709b691240f6320e5cd7fade78cedfa3b91ecff14cecd3de0616c764b9'
SOURCE_NAME = 'Natural Earth 5.1.2, 1:50m Admin 1 - States, Provinces (lakes)'

# Albers equal-area, the conventional projection for a map of the lower 48:
# standard parallels 29.5 and 45.5 north, drawn around 96 west, with 37.5 north
# as the latitude the y axis is measured from. Metres on a sphere of the radius
# Natural Earth is drawn on.
LAT_1, LAT_2, LAT_0, LON_0 = 29.5, 45.5, 37.5, -96.0
RADIUS = 6370997.0

# Fitted once to the geometry already in server.py, so re-running this
# reproduces the committed map instead of moving it. Every state depends on
# these, so they are not the place to fix a single state: refit them, do not
# nudge them.
SCALE = 0.00010075
OFFSET_X, OFFSET_Y = 244.92, 163.63

# Fitted to the committed geometry, like the transform above. At these values
# 46 of the 48 states redraw within 0.19px of the committed outlines, and the
# other two keep one speck of island more or less than the committed map does.
# The remaining difference is a pixel or two of ink, not a shape: this
# reproduces the map, it does not redraw it.
MIN_RING_AREA = 1.5   # px^2. Below this a ring is a speck of a few pixels.
SIMPLIFY = 0.55       # px. Douglas-Peucker tolerance.
DECIMALS = 1          # 1 decimal is about a tenth of a pixel at 1x.

CONUS = sorted("AL AR AZ CA CO CT DE FL GA IA ID IL IN KS KY LA MA MD ME MI MN "
               "MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD TN TX UT "
               "VA VT WA WI WV WY".split())

LON_RANGE = (-125.0, -66.0)   # sanity bounds for a city coordinate
LAT_RANGE = (24.0, 50.0)


def albers(lat, lon):
    p1, p2, p0 = math.radians(LAT_1), math.radians(LAT_2), math.radians(LAT_0)
    n = (math.sin(p1) + math.sin(p2)) / 2
    c = math.cos(p1) ** 2 + 2 * n * math.sin(p1)
    rho = math.sqrt(c - 2 * n * math.sin(math.radians(lat))) / n
    rho0 = math.sqrt(c - 2 * n * math.sin(p0)) / n
    theta = n * (math.radians(lon) - math.radians(LON_0))
    return RADIUS * rho * math.sin(theta), -RADIUS * (rho0 - rho * math.cos(theta))


def placed(lat, lon):
    """A city's or a boundary point's place on the map, in viewBox units."""
    x, y = albers(lat, lon)
    return SCALE * x + OFFSET_X, SCALE * y + OFFSET_Y


def ring_area(ring):
    total = 0.0
    for i in range(len(ring) - 1):
        total += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(total) / 2


def simplify(points, tolerance):
    """Douglas-Peucker, iteratively so deep rings cannot blow the stack.

    Natural Earth rings repeat their first point at the end. Dropping that
    repeat matters: with it, the baseline chord has zero length and the whole
    ring simplifies away to two points.
    """
    if len(points) < 3:
        return list(points)
    closed = points[0] == points[-1]
    points = points[:-1] if closed else points
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        ax, ay = points[first]
        bx, by = points[last]
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1e-12
        worst, worst_at = -1.0, -1
        for i in range(first + 1, last):
            px, py = points[i]
            distance = abs(dy * px - dx * py + bx * ay - by * ax) / length
            if distance > worst:
                worst, worst_at = distance, i
        if worst > tolerance:
            keep[worst_at] = True
            stack.append((first, worst_at))
            stack.append((worst_at, last))
    kept = [point for point, k in zip(points, keep) if k]
    if closed:
        kept.append(kept[0])
    return kept


def centroid(ring):
    """Area centroid, which is where a state abbreviation reads best."""
    area = cx = cy = 0.0
    for i in range(len(ring) - 1):
        cross = ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
        area += cross
        cx += (ring[i][0] + ring[i + 1][0]) * cross
        cy += (ring[i][1] + ring[i + 1][1]) * cross
    area /= 2
    return cx / (6 * area), cy / (6 * area)


def cached_source(path=None):
    if path:
        return Path(path).read_bytes(), str(path)
    CACHE.mkdir(exist_ok=True)
    local = CACHE / SOURCE_URL.rsplit('/', 1)[-1]
    if local.exists():
        return local.read_bytes(), str(local)
    print(f'downloading {SOURCE_NAME}')
    with urllib.request.urlopen(SOURCE_URL, timeout=120) as response:
        raw = response.read()
    local.write_bytes(raw)
    return raw, str(local)


def load_rings(raw, where):
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SOURCE_SHA256:
        print(f'{where} does not match the pinned snapshot.')
        print(f'  expected {SOURCE_SHA256}')
        print(f'  found    {digest}')
        print('Refusing to redraw the map from a source it was not generated from.')
        print('Pass --source with the pinned file, or update SOURCE_SHA256 if the')
        print('intention really is to move every state line.')
        raise SystemExit(2)
    features = json.loads(raw.decode('utf-8'))['features']
    rings = {}
    for feature in features:
        props = feature['properties']
        code = props.get('postal')
        if props.get('adm0_a3') != 'USA' or code not in CONUS:
            continue
        geometry = feature['geometry']
        polygons = (geometry['coordinates'] if geometry['type'] == 'MultiPolygon'
                    else [geometry['coordinates']])
        rings[code] = [[tuple(coordinates) for coordinates in polygon[0]]
                       for polygon in polygons]
    if sorted(rings) != CONUS:
        missing = sorted(set(CONUS) - set(rings))
        print(f'the source is missing {missing}; not writing a partial map')
        raise SystemExit(2)
    return rings


def build_states(rings):
    """Projected, simplified, island-filtered outlines and their labels."""
    paths, labels = {}, {}
    for code in CONUS:
        placed_rings = [[placed(lat, lon) for lon, lat in ring] for ring in rings[code]]
        kept = []
        for ring in placed_rings:
            # Measure before simplifying: at this scale simplification moves a
            # small island's area more than the threshold does, so filtering
            # afterwards would drop specks the committed map kept.
            if ring_area(ring) < MIN_RING_AREA:
                continue
            simplified = simplify(ring, SIMPLIFY)
            if len(simplified) >= 3:
                kept.append(simplified)
        largest = max(kept, key=ring_area)
        x, y = centroid(largest)
        paths[code] = kept
        labels[code] = (round(x, DECIMALS), round(y, DECIMALS))
    return paths, labels


def build_cities(cities):
    """One dot per city, from the coordinates on the city's own row."""
    points = {}
    for row in cities:
        name = row['city']
        if 'at' not in row:
            raise SystemExit(f"{name} has no 'at' coordinates to place it with")
        lat, lon = row['at']
        if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]):
            raise SystemExit(f'{name} is at {lat}, {lon}, which is not in the lower 48')
        here = tuple(round(v, DECIMALS) for v in placed(lat, lon))
        if name in points and points[name] != here:
            raise SystemExit(f'{name} is listed twice at two different places')
        points[name] = here
    unknown = set(points) - set(server.CITY_POINTS)
    if unknown:
        print(f'note: {sorted(unknown)} are new, so the map will gain dots')
    return points


def render_dict(name, entries, quote):
    body = ''.join(f'    {quote}{key}{quote}: {value},\n' for key, value in entries)
    return f'{name} = {{\n{body}}}\n'


def render_paths(paths):
    lines = []
    for code in CONUS:
        parts = []
        for ring in paths[code]:
            head = f'M{ring[0][0]:.{DECIMALS}f} {ring[0][1]:.{DECIMALS}f}'
            tail = ''.join(f'L{x:.{DECIMALS}f} {y:.{DECIMALS}f}' for x, y in ring[1:])
            parts.append(head + tail + 'Z')
        lines.append((code, "'" + ''.join(parts) + "'"))
    return render_dict('STATE_PATHS', lines, "'")


def replace_block(text, name, rendered):
    pattern = re.compile(rf'^{name} = \{{.*?^\}}\n', re.S | re.M)
    if not pattern.search(text):
        raise SystemExit(f'could not find the {name} block in {SERVER}')
    return pattern.sub(lambda _: rendered, text, count=1)


def deviation(generated, committed):
    """Distance from every committed vertex to the generated outline."""
    def to_line(point, ring):
        best = 1e9
        for i in range(len(ring) - 1):
            ax, ay = ring[i]
            bx, by = ring[i + 1]
            dx, dy = bx - ax, by - ay
            if dx == dy == 0:
                distance = math.hypot(point[0] - ax, point[1] - ay)
            else:
                t = max(0, min(1, ((point[0] - ax) * dx + (point[1] - ay) * dy)
                                  / (dx * dx + dy * dy)))
                distance = math.hypot(point[0] - (ax + t * dx), point[1] - (ay + t * dy))
            best = min(best, distance)
        return best

    worst = []
    for code in CONUS:
        if code not in committed:
            continue
        peak = 0.0
        for ring in committed[code]:
            for point in ring:
                peak = max(peak, min(to_line(point, r) for r in generated[code]))
        worst.append((peak, code))
    return sorted(worst, reverse=True)


def parse_rings(path):
    rings = []
    for part in path.split('M')[1:]:
        numbers = [float(n) for n in re.findall(r'-?\d+\.?\d*', part)]
        rings.append([(numbers[i], numbers[i + 1]) for i in range(0, len(numbers), 2)])
    return rings


def report(paths, points):
    committed = {code: parse_rings(path) for code, path in server.STATE_PATHS.items()}
    vertices = sum(len(r) for code in paths for r in paths[code])
    was = sum(len(r) for code in committed for r in committed[code])
    peaks = {code: deviation({code: paths[code]}, {code: committed[code]})[0][0]
             for code in committed if code in paths}
    same = [c for c in CONUS if len(paths[c]) == len(committed[c])]
    islands = [(c, len(paths[c]), len(committed[c])) for c in CONUS
               if len(paths[c]) != len(committed[c])]

    print(f'outlines  {vertices} vertices, was {was}')
    print(f'          {len(same)} of {len(CONUS)} states redraw within '
          f'{max(peaks[c] for c in same):.3f}px of the committed outline')
    if islands:
        print(f'          the other {len(islands)} keep a different number of specks:')
        print('          ' + ', '.join(f'{c} {n} vs {w}' for c, n, w in islands))
    print(f'city dots {len(points)}, was {len(server.CITY_POINTS)}')
    for name in sorted(points):
        if name in server.CITY_POINTS:
            moved = math.dist(points[name], server.CITY_POINTS[name])
            if moved >= 0.15:
                print(f'          {name} moves {moved:.2f}px')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--write', action='store_true',
                        help='rewrite server.py instead of only reporting')
    parser.add_argument('--source', help='a local copy of the source file')
    args = parser.parse_args(argv)

    global server
    sys.path.insert(0, str(ROOT))
    import server as server_module           # noqa: E402  (needs ROOT on the path)
    server = server_module

    raw, where = cached_source(args.source)
    rings = load_rings(raw, where)
    paths, labels = build_states(rings)
    points = build_cities(server.CITIES)
    report(paths, points)

    if not args.write:
        print('\nnothing written. --write rewrites server.py.')
        return 0

    text = SERVER.read_text(encoding='utf-8')
    text = replace_block(text, 'STATE_PATHS', render_paths(paths))
    text = replace_block(text, 'STATE_LABELS',
                         render_dict('STATE_LABELS',
                                     [(c, f'({labels[c][0]}, {labels[c][1]})') for c in CONUS],
                                     "'"))
    text = replace_block(text, 'CITY_POINTS',
                         render_dict('CITY_POINTS',
                                     [(name, f'({points[name][0]}, {points[name][1]})')
                                      for name in sorted(points)], "'"))
    SERVER.write_text(text, encoding='utf-8')
    print(f'\nwrote {SERVER}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

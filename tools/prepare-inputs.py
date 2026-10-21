#!/usr/bin/env python3
"""The small inputs of Sierra Leone's registry build, in a work folder.

Reads, read-only, the osmium exports of N-Ways' Sierra Leone extract (tools/README.md:
admin, bar and place .geojsonseq in the work folder), N-Ways' routing compounds and
gates (data/valhalla) and N-Ways places (the database), and writes:

  enclosures.geojson  closed walls, fences, hedges and retaining walls (40-20,000 m2): every
                      structure inside one is one compound (engine/SPEC.md 4.2, rule 1)
  estates.geojson     N-Ways' estate, government, military and police compounds: parents,
                      whose compounds keep their own codes (rule 2)
  gates.csv           OpenStreetMap barrier=gate/entrance points, N-Ways gates
  places.csv          N-Ways places (POIs) in Sierra Leone
  seeds.csv           the named places an address area takes its name from (SPEC 4.4):
                      OpenStreetMap place nodes, primary (city, town, suburb, quarter,
                      village) and secondary (neighbourhood, hamlet, locality,
                      isolated_dwelling)
  labels.geojson      the districts (admin_level 5), shown beside codes; Western Area
                      Urban is Freetown City Council's area
  country.geojson     the national border (tools/border.py national: the admin_level 2 boundary
                      tagged ISO3166-1=SL, territorial waters included): a footprint outside it
                      is in a neighbouring country and gets no code; and its simplified outline,
                      engine/data/country.geojson (tools/border.py simplify), for the server

Every id is stable: osm:<type>/<id>, geonames:<id>, nways:<id>.

  python3 tools/prepare-inputs.py <work folder>
"""
import csv, json, math, os, re, subprocess, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import border  # noqa: E402

ROOT = os.environ.get('NWAYS_ROOT', '.')   # the N-Ways map data (data/ below it)
DB = os.environ.get('NWAYS_DB', 'postgres:///nways')   # the N-Ways map database (PostGIS: regions, places)
work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
BOX = (-13.40, 6.85, -10.20, 10.05)


def seq(path):
    for line in open(path, encoding='utf-8'):
        line = line.strip('\x1e\n ')
        if line:
            yield json.loads(line)


def oid(p):
    return f"osm:{p.get('@type', 'way')}/{p.get('@id')}"


def ring_area(ring):
    """Area of a lon/lat ring in m2 (local equirectangular)."""
    k = math.cos(math.radians(ring[0][1])) * 111320.0
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0] * k, ring[i][1] * 110574.0
        x2, y2 = ring[i + 1][0] * k, ring[i + 1][1] * 110574.0
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def polys(g):
    if g['type'] == 'Polygon':
        return [g['coordinates']]
    if g['type'] == 'MultiPolygon':
        return g['coordinates']
    if g['type'] == 'LineString' and len(g['coordinates']) >= 4 and g['coordinates'][0] == g['coordinates'][-1]:
        return [[g['coordinates']]]
    return []


def poly_area(ps):
    return sum(ring_area(p[0]) - sum(ring_area(h) for h in p[1:]) for p in ps)


def in_box(x, y):
    return BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3]


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).lower().strip()


# ---------------------------------------------------------------- enclosures and estates
feats, seen = [], set()
for o in seq(W('bar.geojsonseq')):
    p, g = o['properties'], o['geometry']
    kind = p.get('barrier') if p.get('barrier') in ('wall', 'fence', 'hedge', 'retaining_wall') else None
    ps = polys(g)
    if not kind or not ps:
        continue
    i = oid(p)
    if i in seen:          # osmium writes a closed way twice (line and area)
        continue
    a = poly_area(ps)
    if 40 <= a <= 20000:
        seen.add(i)
        feats.append({'type': 'Feature', 'properties': {'eid': i, 'kind': 'osm-' + kind, 'areaM2': round(a, 1)},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(W('enclosures.geojson'), 'w'))
est = []
for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'compounds.geojsonseq')):
    p, g = o['properties'], o['geometry']
    ps = polys(g)
    if not ps or not in_box(*ps[0][0][0]) or p['kind'] not in ('estate', 'government', 'military', 'police'):
        continue
    est.append({'type': 'Feature', 'properties': {'estate': 'nways:' + str(p['id']), 'kind': p['kind'], 'name': p.get('name') or ''},
                'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
json.dump({'type': 'FeatureCollection', 'features': est}, open(W('estates.geojson'), 'w'))

# ---------------------------------------------------------------- gates
with open(W('gates.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['gid', 'src', 'barrier', 'lon', 'lat'])
    for o in seq(W('bar.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and (p.get('barrier') in ('gate', 'lift_gate', 'sliding_gate', 'swing_gate', 'entrance') or p.get('entrance')):
            w.writerow([oid(p), 'osm', p.get('barrier') or 'entrance', *g['coordinates']])
    for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'gates.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and in_box(*g['coordinates']):
            w.writerow(['nways:' + str(p.get('id')), 'nways', p.get('barrier') or p.get('kind') or 'gate', *g['coordinates']])

# ---------------------------------------------------------------- N-Ways places (POIs)
with open(W('places.csv'), 'w') as f:
    subprocess.run(['psql', DB, '-Atc', """COPY (SELECT p.id, p.name, p.category, p.source, ST_X(p.location::geometry) lon, ST_Y(p.location::geometry) lat
        FROM places p JOIN regions r ON ST_Intersects(r.geom, p.location::geometry) WHERE r.country='SL' ORDER BY p.id) TO STDOUT WITH CSV HEADER"""],
                   stdout=f, check=True)

# ---------------------------------------------------------------- seeds (area names)
PRIMARY = {'city', 'town', 'suburb', 'quarter', 'village'}
SECONDARY = {'neighbourhood', 'hamlet', 'locality', 'isolated_dwelling'}
seeds = []
for o in seq(W('place.geojsonseq')):
    p, g = o['properties'], o['geometry']
    if p.get('name') and g['type'] == 'Point' and p.get('place') in PRIMARY | SECONDARY:
        seeds.append({'id': oid(p), 'kind': p['place'], 'tier': 'P' if p['place'] in PRIMARY else 'S', 'name': p['name'].strip(),
                      'lon': g['coordinates'][0], 'lat': g['coordinates'][1]})
seeds.sort(key=lambda r: r['id'])
with open(W('seeds.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, ['id', 'kind', 'tier', 'name', 'lon', 'lat'])
    w.writeheader()
    w.writerows(seeds)

# ---------------------------------------------------------------- labels
lab = []
for o in seq(W('admin.geojsonseq')):
    p = o['properties']
    if p.get('admin_level') == '5' and p.get('name'):
        lab.append({'type': 'Feature', 'properties': {'lid': oid(p), 'name': p['name'].replace(' District', '')}, 'geometry': o['geometry']})
json.dump({'type': 'FeatureCollection', 'features': lab}, open(W('labels.geojson'), 'w'), ensure_ascii=False)
# the border decides (tools/border.py): only the admin_level 2 boundary tagged ISO3166-1=SL, never
# another admin_level 2 relation the extract holds; then the simplified outline the server ships
src = border.national(W('admin.geojsonseq'), W('country.geojson'))
pts, dev, _ = border.simplify(W('country.geojson'), os.path.join(REPO, 'engine', 'data', 'country.geojson'))
print('border:', src, f'({pts} points simplified, {dev} m from the full line)')
loc = seeds
print(len(feats), 'enclosures,', len(est), 'estates,', len(loc), 'seeds,', len(lab), 'labels')

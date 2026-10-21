#!/usr/bin/env python3
"""Sierra Leone: build design-stage address areas (place name + number) and size their numbers.

Each address area is named after a place Sierra Leoneans already use (a Freetown
community, a town, a village); no administrative boundary is used. Every structure is assigned to its nearest
named place; areas too big for a 4-digit number are split among the
neighbourhoods and hamlets inside them (docs/model.md, "Address areas").
Output: model/area-stats.json (counts, digits needed, examples). The areas
themselves are frozen only at first issue; this run sizes the design.

  tools/area_stats.py --centroids centroids-SL.csv --places sierra-leone-place.csv \
      --compounds-per-structure 0.86

centroids: lat,lon,area_m2 per structure (tools/profile_stats.py --centroids)
places:    place,name,lat,lon from OpenStreetMap place=* nodes
Standard library only.
"""
import argparse, collections, csv, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
from sl_address import name_key  # noqa: E402  the national name normalisation (docs/model.md 4.1)

PRIMARY = {'city', 'town', 'suburb', 'quarter', 'village'}     # names first tried
SECONDARY = {'neighbourhood', 'hamlet', 'locality', 'isolated_dwelling'}
REACH_KM = 4.0          # Freetown's communities are close together; beyond this use the nearest secondary
CAP = 4500              # compounds per area for 4 digits (9,000 numbers, half kept free)
MIN_COMPOUNDS = 20      # smaller areas fold into their nearest neighbour
CAPITAL_BOX = (8.36, -13.31, 8.51, -13.10)  # Freetown (Western Area Urban), for examples


def km(a, b):
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[0] - b[0]) * 110.574, (a[1] - b[1]) * 111.32 * k)


class Index:
    def __init__(self, pts, cell=0.05):
        self.cell, self.pts, self.g = cell, pts, collections.defaultdict(list)
        for i, p in enumerate(pts):
            self.g[(int(p[0] // cell), int(p[1] // cell))].append(i)

    def nearest(self, q, max_km, allow=None):
        r = max(1, math.ceil(max_km / (self.cell * 110)))
        cy, cx = int(q[0] // self.cell), int(q[1] // self.cell)
        best = None
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                for i in self.g.get((cy + dy, cx + dx), ()):
                    if allow is not None and i not in allow:
                        continue
                    d = km(q, self.pts[i])
                    if d <= max_km and (best is None or d < best[0]):
                        best = (d, i)
        return best


def inside(pt, ring):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def load_polys(path, names):
    import json as _j
    out = []
    for f in _j.load(open(path))['features']:
        if names and f['properties'].get('name') not in names:
            continue
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        for poly in polys:
            ring = [tuple(p) for p in poly[0]]
            xs, ys = [p[0] for p in ring], [p[1] for p in ring]
            out.append((min(xs), min(ys), max(xs), max(ys), ring))
    return out


def in_any(lat, lon, polys):
    return any(b[0] <= lon <= b[2] and b[1] <= lat <= b[3] and inside((lon, lat), b[4]) for b in polys)


def digits_for(n):
    d = 3
    while 9 * 10 ** (d - 1) < 2 * n:
        d += 1
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--centroids', required=True)
    ap.add_argument('--places', required=True)
    ap.add_argument('--compounds-per-structure', type=float, required=True,
                    help='compounds per structure measured in the capital (model/profile-stats.json)')
    ap.add_argument('--official', help='GeoJSON polygons where a government address system already has addresses: N-Ways issues no codes there')
    ap.add_argument('--official-label', help='description of --official recorded in the output (default: the path)')
    ap.add_argument('--official-names', default='', help='comma-separated feature names in --official to use (default: all)')
    ap.add_argument('--out', default=os.path.join(REPO, 'model', 'area-stats.json'))
    ap.add_argument('--areas-out', default=os.path.join(REPO, 'model', 'design-areas.csv'),
                    help='one row per design-stage area, official names (input to tools/name_ranges.py, which adds the plate names)')
    a = ap.parse_args()
    places = [(r[0], r[1].strip(), float(r[2]), float(r[3])) for r in csv.reader(open(a.places)) if r[1].strip()]
    prim = [p for p in places if p[0] in PRIMARY]
    sec = [p for p in places if p[0] in SECONDARY]
    pi = Index([(p[2], p[3]) for p in prim])
    si = Index([(p[2], p[3]) for p in sec])
    members = collections.defaultdict(list)   # area key -> structure points
    unplaced = 0
    pts = []
    for r in csv.reader(open(a.centroids)):
        q = (float(r[0]), float(r[1]))
        pts.append(q)
        b = pi.nearest(q, REACH_KM)
        if b:
            members[('P', b[1])].append(q)
            continue
        b = si.nearest(q, 15.0)
        if b:
            members[('S', b[1])].append(q)
        else:
            unplaced += 1
    # Split primary areas that are too big among the secondary places inside them.
    sec_parent = collections.defaultdict(set)
    for j, s in enumerate(sec):
        b = pi.nearest((s[2], s[3]), REACH_KM)
        if b:
            sec_parent[b[1]].add(j)
    r = a.compounds_per_structure
    split = 0
    for key in [k for k in members if k[0] == 'P']:
        if len(members[key]) * r <= CAP or not sec_parent.get(key[1]):
            continue
        split += 1
        allow = sec_parent[key[1]]
        moved = collections.defaultdict(list)
        keep = []
        home = (prim[key[1]][2], prim[key[1]][3])
        for q in members[key]:
            b = si.nearest(q, 3.0, allow)
            if b and b[0] < km(q, home):
                moved[('S', b[1])].append(q)
            else:
                keep.append(q)
        members[key] = keep
        for k2, v in moved.items():
            members[k2].extend(v)
    # Fold tiny areas into the nearest primary area.
    folded = 0
    for key in [k for k in members if len(members[k]) * r < MIN_COMPOUNDS]:
        seed = prim[key[1]] if key[0] == 'P' else sec[key[1]]
        b = pi.nearest((seed[2], seed[3]), 30.0, None)
        if b and ('P', b[1]) != key and ('P', b[1]) in members:
            members[('P', b[1])].extend(members.pop(key))
            folded += 1
    areas = []
    for key, qs in members.items():
        if not qs:
            continue
        seed = prim[key[1]] if key[0] == 'P' else sec[key[1]]
        n = round(len(qs) * r)
        areas.append({'name': seed[1], 'place': seed[0], 'lat': seed[2], 'lon': seed[3], 'structures': len(qs),
                      'compounds': n, 'digits': digits_for(max(n, 1))})   # per-area length; the issued length is the name's range (name_ranges.py)
    official = load_polys(a.official, set(n for n in a.official_names.split(',') if n)) if a.official else []
    for x in areas:
        x['official'] = in_any(x['lat'], x['lon'], official) if official else False
    issuing = [x for x in areas if not x['official']]
    names = collections.Counter(name_key(x['name']) for x in areas)
    dup = sum(1 for x in areas if names[name_key(x['name'])] > 1)
    names_i = collections.Counter(name_key(x['name']) for x in issuing)
    dup_i = sum(1 for x in issuing if names_i[name_key(x['name'])] > 1)
    by_digits = collections.Counter(x['digits'] for x in areas)
    comp_by_digits = collections.Counter()
    for x in areas:
        comp_by_digits[x['digits']] += x['compounds']
    cap = [x for x in areas if CAPITAL_BOX[0] <= x['lat'] <= CAPITAL_BOX[2] and CAPITAL_BOX[1] <= x['lon'] <= CAPITAL_BOX[3]]
    cap.sort(key=lambda x: -x['compounds'])
    sizes = sorted(x['compounds'] for x in areas)
    q = lambda f: sizes[min(len(sizes) - 1, int(f * len(sizes)))]
    out = {
        'country': 'SL', 'tool': 'tools/area_stats.py',
        'rules': {'primary': sorted(PRIMARY), 'secondary': sorted(SECONDARY), 'reachKm': REACH_KM, 'capPer4Digits': CAP,
                  'minCompounds': MIN_COMPOUNDS, 'compoundsPerStructure': r},
        'structures': len(pts), 'unplacedStructures': unplaced,
        'areas': len(areas), 'areasSplit': split, 'areasFolded': folded,
        'areasWithDuplicateNames': dup,   # same normalised name anywhere, FCC's area included
        'areasByDigits': dict(sorted(by_digits.items())),
        'compoundsByDigits': dict(sorted(comp_by_digits.items())),
        'compoundsPerArea': {'p10': q(0.1), 'p50': q(0.5), 'p90': q(0.9), 'p99': q(0.99), 'max': sizes[-1]},
        'officialCoverage': {'source': a.official_label or a.official, 'names': a.official_names,
                             'areasUnderOfficial': len(areas) - len(issuing), 'compoundsUnderOfficial': sum(x['compounds'] for x in areas if x['official'])},
        'issuing': {'areas': len(issuing), 'compounds': sum(x['compounds'] for x in issuing),
                    'areasWithRepeatedNames': dup_i, 'numberRanges': 'per name, national: model/name-ranges.json (tools/name_ranges.py)',
                    'areasByDigits': dict(sorted(collections.Counter(x['digits'] for x in issuing).items())),
                    'compoundsByDigits': dict(sorted(collections.Counter({d: sum(x['compounds'] for x in issuing if x['digits'] == d) for d in set(x['digits'] for x in issuing)}).items())),
                    'largest': [{k: x[k] for k in ('name', 'place', 'compounds', 'digits')} for x in sorted(issuing, key=lambda x: -x['compounds'])[:15]]},
        'capital': {'areas': len(cap), 'compounds': sum(x['compounds'] for x in cap),
                    'areasByDigits': dict(sorted(collections.Counter(x['digits'] for x in cap).items())),
                    'largest': [{k: x[k] for k in ('name', 'place', 'compounds', 'digits')} for x in cap[:25]]},
    }
    json.dump(out, open(a.out, 'w'), ensure_ascii=False, indent=1)
    with open(a.areas_out, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['officialName', 'place', 'lat', 'lon', 'structures', 'compounds', 'official'])   # plate names: tools/name_ranges.py
        for x in sorted(areas, key=lambda x: (x['name'].lower(), x['lat'], x['lon'])):
            w.writerow([x['name'], x['place'], f"{x['lat']:.6f}", f"{x['lon']:.6f}", x['structures'], x['compounds'], int(x['official'])])
    print(f"wrote {a.out}: {len(areas)} areas, digits {out['areasByDigits']}")


if __name__ == '__main__':
    main()

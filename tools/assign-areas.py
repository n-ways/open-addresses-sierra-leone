#!/usr/bin/env python3
"""Every Sierra Leonean footprint's address area, and the density around it (engine/SPEC.md 4.2, 4.4).

  python3 tools/assign-areas.py <work folder>

Reads <work>/buildings-raw.csv (tools/extract-buildings.py; only bid, lat, lon, label),
<work>/seeds.csv and <work>/country.geojson (tools/prepare-inputs.py; a seed over the border
names no home), and applies the area rules of the design
(tools/area_stats.py, docs/model.md "Address areas"), with no administrative boundary:

  1. a footprint takes the nearest primary seed (city, town, suburb, quarter, village)
     within 4 km, else the nearest secondary seed (neighbourhood, hamlet, locality,
     isolated dwelling) within 15 km, else the nearest primary seed at any distance;
  2. a primary area with more than 4,500 compounds (footprints x 0.779, the compounds per
     structure measured in Freetown) is split: a footprint moves to the nearest secondary
     seed within 3 km whose own nearest primary is that area, when that seed is nearer
     than the area's own;
  3. an area with fewer than 20 compounds folds into the area of the primary seed nearest
     its seed, within 30 km.

Density: footprints in the footprint's 100 m x 100 m cell (x = lon x 111,320 x cos 8.5 deg,
y = lat x 110,574), for the dense-hectare and village-yard rules (SPEC 4.2).

Writes <work>/area-of.csv (bid, aid, dens) and <work>/area-points.csv (every area: aid =
its seed's id, name, kind, tier, lat, lon, footprints, label = the district most of its
footprints are in, fcc = whether most are in Western Area Urban). Standard library only.
"""
import collections, csv, math, os, sys

work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
REACH_KM, SEC_KM, SPLIT_KM, FOLD_KM = 4.0, 15.0, 3.0, 30.0
CAP, MIN_COMPOUNDS, RATIO = 4500, 20, 0.779
KX = 111320.0 * math.cos(math.radians(8.5))
KY = 110574.0
FCC_LABEL = 'Western Area Urban'


def km(a, b):
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[0] - b[0]) * 110.574, (a[1] - b[1]) * 111.32 * k)


class Index:
    def __init__(self, pts, cell=0.05):
        self.cell, self.pts, self.g = cell, pts, collections.defaultdict(list)
        for i, p in enumerate(pts):
            self.g[(int(p[0] // cell), int(p[1] // cell))].append(i)

    def nearest(self, q, max_km, allow=None):
        """(distance km, index) of the nearest point within max_km; ties to the lower index."""
        r = max(1, math.ceil(max_km / (self.cell * 110)))
        cy, cx = int(q[0] // self.cell), int(q[1] // self.cell)
        best = None
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                for i in self.g.get((cy + dy, cx + dx), ()):
                    if allow is not None and i not in allow:
                        continue
                    d = km(q, self.pts[i])
                    if d <= max_km and (best is None or (d, i) < best):
                        best = (d, i)
        return best


def rings(path):
    import json
    out = []
    for f in json.load(open(path))['features']:
        g = f['geometry']
        for p in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]):
            out.append(p)
    return out


def inside(x, y, ring):
    c, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


COUNTRY = rings(W('country.geojson'))
seeds = []
for s in csv.DictReader(open(W('seeds.csv'), encoding='utf-8')):
    s['lat'], s['lon'] = float(s['lat']), float(s['lon'])
    if any(inside(s['lon'], s['lat'], p[0]) and not any(inside(s['lon'], s['lat'], h) for h in p[1:]) for p in COUNTRY):
        seeds.append(s)
prim = [s for s in seeds if s['tier'] == 'P']
sec = [s for s in seeds if s['tier'] == 'S']
pi = Index([(p['lat'], p['lon']) for p in prim])
si = Index([(p['lat'], p['lon']) for p in sec])

bids, pts, labels = [], [], []
key = []
cells = collections.Counter()
with open(W('buildings-raw.csv'), encoding='utf-8', newline='') as f:
    for r in csv.DictReader(f):
        q = (float(r['lat']), float(r['lon']))
        bids.append(int(r['bid']))
        pts.append(q)
        labels.append(r['label'] or '')
        c = (int(q[1] * KX // 100), int(q[0] * KY // 100))
        cells[c] += 1
        b = pi.nearest(q, REACH_KM)
        if b:
            key.append(('P', b[1]))
            continue
        b = si.nearest(q, SEC_KM)
        if b:
            key.append(('S', b[1]))
            continue
        b = pi.nearest(q, 400.0)
        key.append(('P', b[1]))
members = collections.defaultdict(list)
for i, k in enumerate(key):
    members[k].append(i)
# split primary areas too big for four digits among their secondary seeds
sec_parent = collections.defaultdict(set)
for j, s in enumerate(sec):
    b = pi.nearest((s['lat'], s['lon']), REACH_KM)
    if b:
        sec_parent[b[1]].add(j)
split = 0
for k in sorted(k for k in members if k[0] == 'P'):
    if len(members[k]) * RATIO <= CAP or not sec_parent.get(k[1]):
        continue
    split += 1
    home = (prim[k[1]]['lat'], prim[k[1]]['lon'])
    keep = []
    for i in members[k]:
        b = si.nearest(pts[i], SPLIT_KM, sec_parent[k[1]])
        if b and b[0] < km(pts[i], home):
            members[('S', b[1])].append(i)
        else:
            keep.append(i)
    members[k] = keep
# fold tiny areas into the area of the primary seed nearest their own seed
folded = 0
for k in sorted(k for k in members if len(members[k]) * RATIO < MIN_COMPOUNDS):
    s = prim[k[1]] if k[0] == 'P' else sec[k[1]]
    b = pi.nearest((s['lat'], s['lon']), FOLD_KM)
    if b and ('P', b[1]) != k and ('P', b[1]) in members and members[('P', b[1])]:
        members[('P', b[1])].extend(members.pop(k))
        folded += 1
aid_of = [None] * len(pts)
areas = []
for k, idx in members.items():
    if not idx:
        continue
    s = prim[k[1]] if k[0] == 'P' else sec[k[1]]
    for i in idx:
        aid_of[i] = s['id']
    lab = collections.Counter(labels[i] for i in idx)
    top = min(lab, key=lambda x: (-lab[x], x))
    areas.append({'aid': s['id'], 'name': s['name'], 'kind': s['kind'], 'tier': s['tier'], 'lat': s['lat'], 'lon': s['lon'],
                  'footprints': len(idx), 'label': top, 'fcc': int(lab.get(FCC_LABEL, 0) * 2 > len(idx))})
areas.sort(key=lambda a: a['aid'])
with open(W('area-of.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['bid', 'aid', 'dens'])
    for i, q in enumerate(pts):
        w.writerow([bids[i], aid_of[i], cells[(int(q[1] * KX // 100), int(q[0] * KY // 100))]])
with open(W('area-points.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, ['aid', 'name', 'kind', 'tier', 'lat', 'lon', 'footprints', 'label', 'fcc'])
    w.writeheader()
    w.writerows(areas)
print(len(pts), 'footprints,', len(areas), 'areas,', split, 'split,', folded, 'folded,', sum(a['fcc'] for a in areas), 'in FCC area')

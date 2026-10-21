#!/usr/bin/env python3
"""Sierra Leone's national border, and the rule that keeps every code inside it.

The border decides: a code is only ever issued for a building whose entrance is
inside the national border (OpenStreetMap's admin_level 2 boundary of Sierra Leone,
ISO3166-1 = SL, territorial waters included) or within 300 m of it (BORDER_M in
server/geo.py: the line's own accuracy, and gates on the line). Zone outlines from
other sources (geoBoundaries, GADM and the like) may spill over the border; they
never decide. Standard library only.

  python3 tools/border.py national <admin.geojsonseq> <country.geojson>
      the national boundary out of the osmium export of tools/README.md (step 1):
      the admin_level 2 relation tagged ISO3166-1=SL, and only that one (an extract
      also holds parts of a neighbouring country's boundary; it is never taken)
  python3 tools/border.py simplify <country.geojson> <engine/data/country.geojson> [tolerance m]
      the outline the server and decoders ship: Douglas-Peucker at 50 m by default,
      under 1 MB; the measured distance between the simplified and the full line is
      recorded as deviationM, and the server's tolerance shrinks by it, so a point it
      accepts is never more than 300 m outside the full border
  python3 tools/border.py check <country.geojson> <registry folder>
      counts the published codes whose entrance is more than 300 m outside the
      border (there must be none); exits 1 if there is one

Used by tools/extract-buildings.py (footprints) and tools/issue_registry.py
(compounds, lotes): ``Border(path).keeps(lat, lon)``.
"""
import csv, gzip, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
from server.geo import BORDER_M, M_LAT, M_LON_EQ, Outline, seg_dist  # noqa: E402

ISO = 'SL'
NAME = 'Sierra Leone'
REACH_M = 5000.0


class Border(Outline):
    """The border rule over a border file: ``keeps`` is inside or within 300 m."""

    def keeps(self, lat, lon):
        return self.contains(lat, lon)


def _seq(path):
    for line in open(path, encoding='utf-8'):
        line = line.strip('\x1e\n ')
        if line:
            yield json.loads(line)


def national(admin_path, out_path):
    found = []
    for o in _seq(admin_path):
        p = o['properties']
        if p.get('admin_level') == '2' and p.get('boundary') in (None, 'administrative') and p.get('ISO3166-1') == ISO:
            found.append(o)
    if len(found) != 1:
        raise SystemExit(f'{admin_path}: {len(found)} admin_level 2 boundaries tagged ISO3166-1={ISO}, expected exactly one')
    o = found[0]
    src = f"OpenStreetMap {o['properties'].get('@type', 'relation')}/{o['properties'].get('@id')} (admin_level 2)"
    with open(out_path, 'w') as f:
        json.dump({'type': 'FeatureCollection', 'features': [
            {'type': 'Feature', 'properties': {'name': NAME, 'iso': ISO, 'source': src}, 'geometry': o['geometry']}]}, f)
    return src


def _polys(g):
    return g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]


def _dp(pts, tol, k):
    """Douglas-Peucker on an open chain of (lng, lat), in metres."""
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = pts[i][0] * k, pts[i][1] * M_LAT
        bx, by = pts[j][0] * k, pts[j][1] * M_LAT
        far, at = -1.0, -1
        for m in range(i + 1, j):
            d = seg_dist(pts[m][0] * k, pts[m][1] * M_LAT, ax, ay, bx, by)
            if d > far:
                far, at = d, m
        if at >= 0 and far > tol:
            keep[at] = True
            stack += [(i, at), (at, j)]
    return [p for p, kp in zip(pts, keep) if kp]


def _simplify_ring(ring, tol):
    r = [(float(x), float(y)) for x, y in ring]
    if r[0] == r[-1]:
        r = r[:-1]
    if len(r) < 4:
        return None
    k = M_LON_EQ * math.cos(sum(y for _, y in r) / len(r) * math.pi / 180)
    far = max(range(len(r)), key=lambda i: math.hypot((r[i][0] - r[0][0]) * k, (r[i][1] - r[0][1]) * M_LAT))
    out = _dp(r[:far + 1], tol, k)[:-1] + _dp(r[far:] + [r[0]], tol, k)[:-1]
    if len(out) < 3:
        return None
    return [[round(x, 6), round(y, 6)] for x, y in out] + [[round(out[0][0], 6), round(out[0][1], 6)]]


def _deviation(a_path, b_path, step_m=10.0):
    """The largest distance from a point of either line to the other (sampled every step_m, an upper bound)."""
    worst = 0.0
    for src, dst in ((a_path, b_path), (b_path, a_path)):
        other = Outline(dst)
        for r in Outline(src).rings:
            for i in range(len(r)):
                (x1, y1), (x2, y2) = r[i - 1], r[i]
                k = M_LON_EQ * math.cos(y1 * math.pi / 180)
                n = max(1, int(math.hypot((x2 - x1) * k, (y2 - y1) * M_LAT) // step_m))
                for t in range(n):
                    x, y = x1 + (x2 - x1) * t / n, y1 + (y2 - y1) * t / n
                    worst = max(worst, other.line_m(y, x, REACH_M))
    return worst + step_m / 2   # the distance moves at most step_m / 2 between samples


def simplify(src_path, out_path, tol_m=50.0):
    fc = json.load(open(src_path, encoding='utf-8'))
    feat = fc['features'][0]
    polys = []
    for p in _polys(feat['geometry']):
        outer = _simplify_ring(p[0], tol_m)
        if outer is None:
            continue
        polys.append([outer] + [h for h in (_simplify_ring(h, tol_m) for h in p[1:]) if h])
    geom = {'type': 'Polygon', 'coordinates': polys[0]} if len(polys) == 1 else {'type': 'MultiPolygon', 'coordinates': polys}
    props = {k: v for k, v in (feat.get('properties') or {}).items() if k != 'deviationM'}
    props.update(toleranceM=tol_m, borderM=BORDER_M)
    out = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': props, 'geometry': geom}]}
    with open(out_path, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    dev = math.ceil(_deviation(src_path, out_path) * 10) / 10
    props['deviationM'] = dev
    with open(out_path, 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    size = os.path.getsize(out_path)
    if size >= 1 << 20:
        raise SystemExit(f'{out_path} is {size} bytes, over 1 MB: raise the tolerance')
    return sum(len(r) for p in polys for r in p), dev, size


def check(border_path, registry):
    b = Border(border_path)
    n = abroad = 0
    first = None
    for name in sorted(os.listdir(registry)):
        if not name.endswith('.csv.gz') or name.startswith('areas'):
            continue
        with gzip.open(os.path.join(registry, name), 'rt', encoding='utf-8', newline='') as f:
            for r in csv.DictReader(f):
                n += 1
                lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
                if b.outside_m(lat, lng, REACH_M) > BORDER_M:
                    abroad += 1
                    first = first or r['machine']
    return n, abroad, first


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'national':
        print(national(sys.argv[2], sys.argv[3]))
    elif cmd == 'simplify':
        pts, dev, size = simplify(sys.argv[2], sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 50.0)
        print(f'{pts} points, {size} bytes, at most {dev} m from the full border; server tolerance {BORDER_M - dev:.1f} m')
    elif cmd == 'check':
        n, abroad, first = check(sys.argv[2], sys.argv[3])
        print(f'{n} codes, {abroad} more than {BORDER_M:.0f} m outside the border' + (f' ({first} first)' if first else ''))
        sys.exit(1 if abroad else 0)
    else:
        raise SystemExit(__doc__)

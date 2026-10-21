"""Plane geometry at the scale of a compound, and the national outline.

Distances follow the issuer: ``dist_m`` is the local-plane distance used to
pick an area seed, ``door_m`` the one used for the 80 m door and entrance
rules, and ``ground_m`` a great-circle distance for "what is at this point".
"""
import json
import math

# Metres per degree (a local plane is enough at a home's scale).
M_LAT = 110574.0
M_LON_EQ = 111320.0
EARTH_M = 6371008.8


def dist_m(lat1, lon1, lat2, lon2):
    """Distance from (lat1, lon1) to (lat2, lon2), the longitude scaled at lat2."""
    return math.hypot((lat1 - lat2) * M_LAT, (lon1 - lon2) * M_LON_EQ * math.cos(lat2 * math.pi / 180))


def door_m(lat1, lng1, lat2, lng2):
    """Distance used for doors and entrances: 111,320 m per degree, longitude at the mean latitude."""
    dy = (lat2 - lat1) * 111320
    dx = (lng2 - lng1) * 111320 * math.cos((lat1 + lat2) / 2 * math.pi / 180)
    return math.hypot(dx, dy)


def ground_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_M * math.asin(min(1.0, math.sqrt(a)))


def round_half_away(x):
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


# ---------------------------------------------------------------- outlines ([lng, lat] rings)
def open_ring(ring):
    """Drop the closing point of a ring given closed."""
    ring = [(float(p[0]), float(p[1])) for p in ring]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


def ring_area_m2(ring):
    """Shoelace area in square metres, the longitude scaled at the first vertex."""
    if len(ring) < 3:
        return 0.0
    k = math.cos(ring[0][1] * math.pi / 180)
    a = 0.0
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        xi, yi = ring[i][0] * M_LON_EQ * k, ring[i][1] * M_LAT
        xj, yj = ring[j][0] * M_LON_EQ * k, ring[j][1] * M_LAT
        a += xi * yj - xj * yi
    return abs(a) / 2


def in_ring(x, y, ring):
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0.0
    ln = dx * dx + dy * dy
    if ln > 0:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ln))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def ring_dist_m(lat, lng, ring):
    """Metres from a point to a [lng, lat] ring: 0 inside, else to the nearest edge."""
    if in_ring(lng, lat, ring):
        return 0.0
    k = M_LON_EQ * math.cos(lat * math.pi / 180)
    pts = [((x - lng) * k, (y - lat) * M_LAT) for x, y in ring]
    best = math.inf
    for i in range(len(pts)):
        a, b = pts[i - 1], pts[i]
        best = min(best, seg_dist(0.0, 0.0, a[0], a[1], b[0], b[1]))
    return best


def overlap_m2(r1, r2, samples=4096):
    """Area shared by two rings, by counting points of a regular grid over the
    intersection of their bounding boxes (exact to a few per cent, enough for
    the "more than half of the smaller one" rule)."""
    w = max(min(p[0] for p in r1), min(p[0] for p in r2))
    e = min(max(p[0] for p in r1), max(p[0] for p in r2))
    s = max(min(p[1] for p in r1), min(p[1] for p in r2))
    n = min(max(p[1] for p in r1), max(p[1] for p in r2))
    if w >= e or s >= n:
        return 0.0
    side = max(1, int(math.sqrt(samples)))
    dx, dy = (e - w) / side, (n - s) / side
    hit = 0
    for i in range(side):
        x = w + (i + 0.5) * dx
        for j in range(side):
            y = s + (j + 0.5) * dy
            if in_ring(x, y, r1) and in_ring(x, y, r2):
                hit += 1
    k = M_LON_EQ * math.cos((s + n) / 2 * math.pi / 180)
    return hit * dx * k * dy * M_LAT


# A code is only ever issued for a building whose entrance is inside the national border
# (OpenStreetMap's admin_level 2 boundary) or within BORDER_M of it. Zone outlines and
# other sources never decide.
BORDER_M = 300.0


class Outline:
    """The national border (engine/data/country.geojson, every ring of every polygon).

    ``outside_m`` is how far a point lies outside it (0 inside); ``contains`` is the
    border rule: inside, or within ``BORDER_M`` of the line. A simplified outline
    records in its properties how far it strays from the full line
    (``deviationM``); the tolerance shrinks by that much, so a point accepted here
    is never more than ``BORDER_M`` outside the full border."""

    BAND = 0.01   # degrees per latitude band (point in polygon)
    CELL = 0.01   # degrees per grid cell (distance to the line); 0.01 deg > BORDER_M

    def __init__(self, path, border_m=BORDER_M):
        with open(path, encoding='utf-8') as f:
            fc = json.load(f)
        self.rings, dev = [], 0.0
        for feat in fc['features']:
            g = feat['geometry']
            dev = max(dev, float((feat.get('properties') or {}).get('deviationM') or 0.0))
            polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
            for p in polys:
                for r in p:
                    r = open_ring(r)
                    if len(r) >= 3:
                        self.rings.append(r)
        if not self.rings:
            raise ValueError(f'{path} holds no border')
        self.deviation_m = dev
        self.border_m = border_m - dev
        if self.border_m < 0:
            raise ValueError(f'{path} strays {dev:.0f} m from the border, more than the {border_m:.0f} m tolerance')
        self.bands, self.cells = {}, {}
        for r in self.rings:
            for i in range(len(r)):
                a, b = r[i - 1], r[i]
                e = (a[0], a[1], b[0], b[1])
                for k in range(math.floor(min(a[1], b[1]) / self.BAND), math.floor(max(a[1], b[1]) / self.BAND) + 1):
                    self.bands.setdefault(k, []).append(e)
                for cx in range(math.floor(min(a[0], b[0]) / self.CELL), math.floor(max(a[0], b[0]) / self.CELL) + 1):
                    for cy in range(math.floor(min(a[1], b[1]) / self.CELL), math.floor(max(a[1], b[1]) / self.CELL) + 1):
                        self.cells.setdefault((cx, cy), []).append(e)

    def inside(self, lat, lng):
        """Inside the border (even-odd over every ring, so holes and islands count)."""
        c = False
        for xa, ya, xb, yb in self.bands.get(math.floor(lat / self.BAND), ()):
            if (ya > lat) != (yb > lat) and lng < (xb - xa) * (lat - ya) / (yb - ya) + xa:
                c = not c
        return c

    def outside_m(self, lat, lng, reach_m=None):
        """Metres outside the border: 0 inside, else to the nearest point of the line
        (math.inf when farther than ``reach_m``, default the tolerance)."""
        if self.inside(lat, lng):
            return 0.0
        return self.line_m(lat, lng, self.border_m if reach_m is None else reach_m)

    def line_m(self, lat, lng, reach_m):
        """Metres from a point to the nearest point of the line, either side
        (math.inf when farther than ``reach_m``)."""
        k = M_LON_EQ * math.cos(lat * math.pi / 180)
        r = max(1, math.ceil(reach_m / (self.CELL * M_LAT * min(1.0, k / M_LON_EQ))))
        cx, cy = math.floor(lng / self.CELL), math.floor(lat / self.CELL)
        best, seen = math.inf, set()
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for e in self.cells.get((cx + dx, cy + dy), ()):
                    if e in seen:
                        continue
                    seen.add(e)
                    d = seg_dist(0.0, 0.0, (e[0] - lng) * k, (e[1] - lat) * M_LAT, (e[2] - lng) * k, (e[3] - lat) * M_LAT)
                    best = min(best, d)
        return best if best <= reach_m else math.inf

    def contains(self, lat, lng):
        """The border rule: inside, or within the tolerance of the line."""
        return self.outside_m(lat, lng) <= self.border_m

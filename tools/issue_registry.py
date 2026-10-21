#!/usr/bin/env python3
"""The compounds of Sierra Leone for issuing their codes (engine/SPEC.md 4.2, 4.5, 4.6).

Reads <work>/buildings.csv (tools/sort-buildings.py, sorted by area) one area at a time.

  python3 tools/issue_registry.py group <work>     compounds and profiles: <work>/compounds.jsonl.gz,
                                                    <work>/area-counts.json
  python3 tools/build-register.py <work> --freeze  plate names, national ranges and blocks
  python3 tools/issue_registry.py number <work> <lotes.jsonl.gz>
                                                    numbers every area's compounds inside its block and
                                                    writes the lotes, tile by tile (the area seed's
                                                    4-character Plus Code area), for the issuer, which
                                                    numbers them again with its own engine and
                                                    refuses any difference

Grouping (SPEC 4.2, the first rule that applies):
  wall       footprints whose centre is inside one closed wall, fence or hedge are one compound
  dense      in a 100 m x 100 m cell with more than 70 footprints (Kroo Bay, Susan's Bay, Mabella,
             the hillside settlements) nothing is grouped: each footprint is its own compound
  yard       where the cell has at most 25 footprints, a satellite (under 30 m2) joins the nearest
             principal (at least 30 m2 and twice its size) within 8 m, footprint to footprint
  proximity  elsewhere the same join within 4 m
  single     everything else
The border decides (tools/border.py): a compound whose main structure's centre (its point
and, until a gate is confirmed, its entrance) lies more than 300 m outside the national border
is dropped by the grouping and counted as "abroad", and the numbering refuses to write a lote
for one. Only satellites join, and only principals receive them, so two houses are never joined. An
estate, government, military or police compound is a parent: the compounds inside keep their
own codes and record it. Footprints are taken in a fixed order (their stable id), so the result
never depends on the order the map data arrives in.

Each lote line: {"key": the main structure's stable id, "muni": tile ("6CW8"), "zone": area
index ("03606"), "areaId", "nameId", "number", "lat", "lon" (the main structure's centre,
SPEC 4.3), "anchor", "anchorKind", "gate", "coverage": "official" in Freetown City Council's
area (its address is the property's Plus Code) else "nways", "official": "FQR7+HX Freetown"
or null, "estate", "rule", "dens", "label", "structures": [...]} (largest first).
Structure ids: OpenStreetMap "osm:way/<id>"; a Google/Microsoft footprint "nw:" + the first
12 hex characters of the SHA-1 of its centre to 1e-6 degrees and its area to 1 m2.
"""
import collections, csv, gzip, hashlib, json, math, os, re, sys

csv.field_size_limit(1 << 30)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import sl_address as E  # noqa: E402
sys.path.insert(0, HERE)
from border import Border  # noqa: E402

SATELLITE_MAX_M2, PRINCIPAL_MIN_M2, JOIN_M, YARD_M, YARD_MAX_HA, DENSE = E.SATELLITE_MAX_M2, E.PRINCIPAL_MIN_M2, E.JOIN_M, E.YARD_M, E.YARD_MAX_HA, E.DENSE
TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made', 'government', 'craft',
        'building:levels', 'height', 'name', 'roof:material', 'building:material']
CELL = 40.0

OSM_BUILDING = {
    'house': ('residential.house', 0.8), 'detached': ('residential.house', 0.85), 'residential': ('residential.house', 0.85),
    'semidetached_house': ('residential.house', 0.85), 'terrace': ('residential.house', 0.85), 'hut': ('residential.round-hut', 0.85),
    'cabin': ('residential.house', 0.85), 'apartments': ('residential.apartments', 0.85), 'commercial': ('commercial.shop', 0.85),
    'retail': ('commercial.shop', 0.85), 'kiosk': ('commercial.kiosk', 0.85), 'office': ('commercial.office', 0.85),
    'warehouse': ('commercial.warehouse', 0.85), 'industrial': ('industrial', 0.85), 'shed': ('ancillary', 0.85),
    'farm': ('agricultural', 0.85), 'barn': ('agricultural', 0.85), 'school': ('education', 0.85), 'university': ('education', 0.85),
    'college': ('education', 0.85), 'kindergarten': ('education', 0.85), 'hospital': ('health', 0.85), 'clinic': ('health', 0.85),
    'church': ('religious', 0.85), 'chapel': ('religious', 0.85), 'cathedral': ('religious', 0.85), 'mosque': ('religious', 0.85),
    'public': ('government', 0.85), 'civic': ('government', 0.85), 'government': ('government', 0.85), 'hotel': ('hospitality', 0.85),
    'construction': ('status.construction', 0.85), 'ruins': ('status.ruin', 0.85), 'garage': ('transport', 0.85),
    'roof': ('commercial.market', 0.85), 'stadium': ('public.sport', 0.85),
}
OSM_AMENITY = {
    'school': 'education', 'kindergarten': 'education', 'university': 'education', 'college': 'education', 'hospital': 'health',
    'clinic': 'health', 'doctors': 'health', 'pharmacy': 'health', 'place_of_worship': 'religious', 'townhall': 'government',
    'courthouse': 'government', 'police': 'government', 'post_office': 'government', 'marketplace': 'commercial.market',
    'bank': 'commercial.office', 'restaurant': 'hospitality', 'bar': 'hospitality', 'fuel': 'transport', 'bus_station': 'transport',
}
POI = {
    'office': 'commercial.office', 'school': 'education', 'hotel': 'hospitality', 'hospital': 'health', 'food': 'hospitality',
    'shop': 'commercial.shop', 'church': 'religious', 'bar': 'hospitality', 'mosque': 'religious', 'petrol': 'transport',
    'bank': 'commercial.office', 'supermarket': 'commercial.shop', 'pharmacy': 'health', 'market': 'commercial.market',
    'police': 'government', 'cafe': 'hospitality', 'motorpark': 'transport', 'salon': 'commercial.shop', 'phones': 'commercial.shop',
    'mechanic': 'commercial.workshop', 'fastfood': 'hospitality', 'vulcanizer': 'commercial.workshop', 'attraction': 'public.landmark',
}
NUM = re.compile(r'-?\d+(?:\.\d+)?')


def structure_id(r):
    if r['src'] == 'osm':
        return 'osm:' + r['oid']
    return 'nw:' + hashlib.sha1(f"{float(r['lat']):.6f},{float(r['lon']):.6f},{round(float(r['area']))}".encode()).hexdigest()[:12]


def ring_of(wkt):
    """The outer ring of a footprint's first polygon, as (lon, lat) pairs, closing point dropped."""
    s = wkt[wkt.index('(') :]
    first = s.lstrip('(').split(')')[0]
    nums = [float(x) for x in NUM.findall(first)]
    pts = list(zip(nums[0::2], nums[1::2]))
    return pts[:-1] if len(pts) > 1 and pts[0] == pts[-1] else pts


def areas_of(path):
    cur, rows = None, []
    with open(path, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['aid'] != cur:
                if rows:
                    yield cur, rows
                cur, rows = r['aid'], []
            rows.append(r)
    if rows:
        yield cur, rows


def prep(rows):
    lat0 = sum(float(r['lat']) for r in rows) / len(rows)
    k = E.M_LON * math.cos(math.radians(lat0))
    for r in rows:
        r['sid'] = structure_id(r)
        r['a'] = float(r['area'])
        r['dens'] = int(r['dens'])
        r['c'] = (float(r['lon']) * k, float(r['lat']) * E.M_LAT)
        r['ring'] = [(x * k, y * E.M_LAT) for x, y in ring_of(r['wkt'])]
    rows.sort(key=lambda r: r['sid'])


def group(rows):
    """[(indexes, rule)] for one area (SPEC 4.2)."""
    home_of, how = {}, {}
    by_e = collections.defaultdict(list)
    for i, r in enumerate(rows):
        if r['eid']:
            by_e[r['eid']].append(i)
    for eid, ks in by_e.items():
        for i in ks:
            home_of[i], how[i] = ('wall', eid), 'wall'
    principals = [i for i, r in enumerate(rows) if i not in home_of and r['a'] >= PRINCIPAL_MIN_M2]
    grid = collections.defaultdict(list)
    for i in principals:
        c = rows[i]['c']
        grid[(int(c[0] // CELL), int(c[1] // CELL))].append(i)
    for i, r in enumerate(rows):
        if i in home_of:
            continue
        if r['dens'] > DENSE:
            home_of[i], how[i] = ('b', i), 'dense'
            continue
        reach = YARD_M if r['dens'] <= YARD_MAX_HA else JOIN_M
        if r['a'] < SATELLITE_MAX_M2:
            best = None
            cx, cy = int(r['c'][0] // CELL), int(r['c'][1] // CELL)
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    for j in grid.get((cx + dx, cy + dy), ()):
                        p = rows[j]
                        if p['a'] >= 2 * r['a'] and math.dist(p['c'], r['c']) < 60:
                            d = E._dist(r['ring'], p['ring'])
                            if d <= reach and (best is None or (d, p['sid']) < (best[0], rows[best[1]]['sid'])):
                                best = (d, j)
            if best:
                home_of[i], how[i] = ('b', best[1]), 'yard' if reach == YARD_M else 'proximity'
                continue
        home_of[i], how[i] = ('b', i), 'single'
    comps = collections.defaultdict(list)
    for i in range(len(rows)):
        comps[home_of[i]].append(i)
    out = []
    for cid in sorted(comps, key=lambda c: (c[0], str(c[1]))):
        ks = comps[cid]
        kinds = {how[i] for i in ks}
        rule = 'wall' if 'wall' in kinds else ('yard' if 'yard' in kinds else 'proximity') if len(ks) > 1 else min(kinds)
        out.append((ks, rule))
    return out


def floors(r):
    lv = r['building:levels']
    try:
        if lv:
            return max(1, round(float(lv))), 'osm:building:levels'
    except ValueError:
        pass
    try:
        if r['height']:
            return max(1, round(float(r['height'].replace('m', '').strip()) / 3.0)), 'osm:height'
    except ValueError:
        pass
    return None, None   # the Google/Microsoft height is a rendering filler (36 values, 3.5-7 m): never used


def profile(r):
    """Use class, confidence and source of one structure (SPEC 4.6)."""
    b = (r['building'] or '').lower()
    mat = (r['building:material'] or '').lower()
    fl, _ = floors(r)
    if r['amenity'] in OSM_AMENITY:
        return OSM_AMENITY[r['amenity']], 0.85, 'osm:amenity'
    if r['shop']:
        return 'commercial.shop', 0.85, 'osm:shop'
    if r['office'] or r['government']:
        return ('government' if r['government'] else 'commercial.office'), 0.85, 'osm:office'
    if r['tourism'] in ('hotel', 'guest_house', 'hostel', 'motel'):
        return 'hospitality', 0.85, 'osm:tourism'
    if b in OSM_BUILDING:
        cls, conf = OSM_BUILDING[b]
        if cls == 'residential.house':
            if mat in ('metal', 'zink', 'zinc', 'tapoline', 'corrugated_iron'):
                cls = 'residential.pan-body'
            elif mat == 'mud':
                cls = 'residential.mud-house'
            elif fl and fl >= 3:
                cls = 'residential.storey-building'
        return cls, conf, 'osm:building'
    if r['poi']:
        cats = sorted(POI[c] for c in r['poi'].split('|') if c in POI)
        if cats:
            top = collections.Counter(cats).most_common(1)[0][0]
            return top, (0.7 if len(set(cats)) == 1 else 0.6), 'nways:places'
    if mat in ('metal', 'zink', 'zinc', 'tapoline', 'corrugated_iron'):
        return 'residential.pan-body', 0.6, 'osm:building:material'
    if mat == 'mud':
        return 'residential.mud-house', 0.6, 'osm:building:material'
    if r['a'] < 6:
        return 'ancillary', 0.35, 'shape:size'
    if r['a'] >= 2000:
        return 'commercial.warehouse', 0.35, 'shape:size'
    return 'unknown', 0.0, 'default'


def cmd_group(work):
    counts, stats = {}, collections.Counter()
    seen = set()
    border = Border(os.path.join(work, 'country.geojson'))   # the border decides (tools/border.py)
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'wt', encoding='utf-8') as out:
        for aid, rows in areas_of(os.path.join(work, 'buildings.csv')):
            prep(rows)
            n = 0
            for ks, rule in group(rows):
                ks = sorted(ks, key=lambda i: (-rows[i]['a'], rows[i]['sid']))
                sts = []
                for i in ks:
                    r = rows[i]
                    cls, conf, src = profile(r)
                    fl, fls = floors(r)
                    sts.append({'id': r['sid'], 'src': r['src'], 'lat': round(float(r['lat']), 7), 'lon': round(float(r['lon']), 7),
                                'areaM2': round(r['a'], 1), 'perimeterM': round(float(r['perim']), 1),
                                'tags': {t: r[t] for t in TAGS if r.get(t)}, 'places': [p for p in (r['poi'] or '').split('|') if p],
                                'class': cls, 'confidence': conf, 'classSource': src, 'floors': fl, 'floorsSource': fls, 'wkt': r['wkt']})
                key = sts[0]['id']
                if key in seen:
                    stats['duplicateKey'] += 1
                    continue
                seen.add(key)
                main = rows[ks[0]]
                if not border.keeps(float(main['lat']), float(main['lon'])):
                    stats['abroad'] += 1      # more than 300 m outside the border: a neighbouring country's, no code
                    continue
                rec = {'key': key, 'aid': aid, 'lat': round(float(main['lat']), 7), 'lon': round(float(main['lon']), 7), 'rule': rule,
                       'enclosed': rule == 'wall', 'estate': main['estate'] or None, 'dens': main['dens'], 'label': main['label'] or '',
                       'structures': sts}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                n += 1
                stats['rule:' + rule] += 1
                stats['structures'] += len(sts)
                stats[f'size:{min(len(sts), 7)}'] += 1
            counts[aid] = n
            stats['compounds'] += n
    json.dump(counts, open(os.path.join(work, 'area-counts.json'), 'w'))
    json.dump(dict(stats), open(os.path.join(work, 'group-stats.json'), 'w'), indent=1)
    print(json.dumps(dict(stats)))


def cmd_number(work, out_path):
    reg = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))
    area = {a['aid']: a for a in reg['areas']}
    counts = collections.Counter()
    border = Border(os.path.join(work, 'country.geojson'))   # the border decides: no lote over it
    by_tile = collections.defaultdict(list)
    for a in reg['areas']:
        by_tile[a['tile']].append(a['aid'])
    for tile in sorted(by_tile):
        want = set(by_tile[tile])
        by_area = collections.defaultdict(list)
        with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
            for line in f:
                c = json.loads(line)
                if c['aid'] in want:
                    by_area[c['aid']].append(c)
        if not by_area:
            continue
        with gzip.open(out_path, 'at', encoding='utf-8') as out:
            for aid in sorted(by_area, key=lambda x: area[x]['index']):
                a = area[aid]
                lo, hi = a['blocks'][0]
                cs = by_area[aid]
                abroad = [c['key'] for c in cs if not border.keeps(c['lat'], c['lon'])]
                if abroad:
                    raise SystemExit(f'{len(abroad)} compounds of area {aid} ({abroad[0]} first) lie more than 300 m outside the border: '
                                     'group them again (issue_registry.py group) with the national border in the work folder')
                nums, _ = E.number_area([(c['key'], c['lat'], c['lon']) for c in cs], {'lo': lo, 'hi': hi})
                for c in sorted(cs, key=lambda c: nums[c['key']]):
                    fcc = bool(a['fcc'])
                    off = E.spot(c['lat'], c['lon'])['short'] if fcc else None
                    rec = {'key': c['key'], 'muni': tile, 'zone': f"{a['index']:05d}", 'areaId': a['index'], 'nameId': a['family'],
                           'number': nums[c['key']], 'lat': c['lat'], 'lon': c['lon'], 'anchor': [c['lat'], c['lon']], 'anchorKind': 'centre',
                           'gate': None, 'coverage': 'official' if fcc else 'nways', 'official': off, 'enclosed': c['enclosed'],
                           'estate': c['estate'], 'rule': c['rule'], 'dens': c['dens'], 'label': c['label'], 'structures': c['structures']}
                    out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                    counts['compounds'] += 1
                    counts[f'digits:{len(str(rec["number"]))}'] += 1
        print(tile, sum(len(v) for v in by_area.values()), 'compounds', flush=True)
    print(json.dumps(counts))


if __name__ == '__main__':
    if sys.argv[1] == 'group':
        cmd_group(os.path.abspath(sys.argv[2]))
    elif sys.argv[1] == 'number':
        p = sys.argv[3]
        if os.path.exists(p):
            os.remove(p)
        cmd_number(os.path.abspath(sys.argv[2]), p)

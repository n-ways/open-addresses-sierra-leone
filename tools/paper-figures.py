#!/usr/bin/env python3
"""Data for the paper's figures (docs/figures/*.dat), from the published files only.

  python3 tools/paper-figures.py

Reads engine/data/ (the register and the national outline), registry/ (every issued
code) and model/building-stats.json. Writes small whitespace-separated tables that the
TikZ/pgfplots sources in docs/figures/ plot. Standard library only; the registry is
streamed tile by tile.
"""
import csv, gzip, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import sl_address as E  # noqa: E402

OUT = os.path.join(REPO, 'docs', 'figures')
REG = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json')))
STATS = json.load(open(os.path.join(REPO, 'model', 'building-stats.json')))
MANIFEST = json.load(open(os.path.join(REPO, 'registry', 'MANIFEST.json')))

EXAMPLE_ZONE = '03663'          # Moyamba town
EXAMPLE_CELL = '6CW95H68'       # the 0.0025-degree cell of Moyamba 15727
# Where the zone map prints each zone's label (lng, lat): inside the zone, clear of the
# reference towns' names.
ZONE_LABEL = {'6CV8': (-13.35, 7.4), '6CV9': (-12.7, 6.95), '6CVC': (-11.4, 7.7), '6CVF': (-10.45, 7.5),
              '6CRC': (-11.95, 6.88), '6CW8': (-13.53, 8.8), '6CW9': (-12.55, 8.55), '6CWC': (-11.5, 8.3),
              '6CWF': (-10.35, 8.85), '6CX8': (-13.35, 9.5), '6CX9': (-12.6, 9.3), '6CXC': (-11.65, 9.3),
              '6CXF': (-10.4, 9.75)}
TOWN_LABEL_ABOVE = {'Koidu'}


def write(name, header, rows):
    with open(os.path.join(OUT, name), 'w') as f:
        f.write(' '.join(header) + '\n')
        for r in rows:
            f.write(' '.join(str(x) for x in r) + '\n')


def outline():
    g = json.load(open(os.path.join(REPO, 'engine', 'data', 'country.geojson')))
    ring = g['features'][0]['geometry']['coordinates'][0]
    keep = ring[::4] + [ring[0]]
    write('outline.dat', ['lng', 'lat'], [(round(x, 4), round(y, 4)) for x, y in keep])


def towns_and_zones():
    # names print east of their town, or above it where that would run into a neighbour
    rows = [(t['lng'], t['lat'], t['name'].replace(' ', '~')) for t in REG['towns']]
    write('towns.dat', ['lng', 'lat', 'name'], [r for r in rows if r[2] not in TOWN_LABEL_ABOVE])
    write('towns-above.dat', ['lng', 'lat', 'name'], [r for r in rows if r[2] in TOWN_LABEL_ABOVE])
    rows = []
    for tile, n in sorted(MANIFEST['byTile'].items()):
        a = E.olc_decode(tile + '0000+')
        x, y = ZONE_LABEL.get(tile, (a['west'] + 0.5, a['south'] + 0.5))
        rows.append((x, y, tile, n, f'{n:,}', f'{n:,}'.replace(',', '\\,')))
    write('zones.dat', ['lng', 'lat', 'zone', 'codes', 'label', 'labelfr'], rows)


def area_sizes():
    edges = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    counts = [0] * (len(edges) - 1)
    compounds = [0] * (len(edges) - 1)
    for a in REG['areas']:
        n = a['compounds']
        for i in range(len(edges) - 1):
            if edges[i] <= n < edges[i + 1]:
                counts[i] += 1
                compounds[i] += n
    total = sum(compounds)
    write('area-sizes.dat', ['bin', 'lo', 'hi', 'areas', 'compoundShare'],
          [(i, edges[i], edges[i + 1] - 1, counts[i], round(100 * compounds[i] / total, 2))
           for i in range(len(counts))])


def ranges():
    rows = []
    for row, name in enumerate(['Moyamba', 'Madina', 'Masorie']):
        areas = [a for a in REG['areas'] if a['name'] == name]
        rec = REG['names'][areas[0]['key']]
        d = rec['digits']
        u, lo0 = E.unit_size(d), 10 ** (d - 1)
        for k, a in enumerate(sorted(areas, key=lambda a: a['blocks'][0][0])):
            for lo, hi in a['blocks']:
                rows.append((row, (lo - lo0) // u, (hi + 1 - lo0) // u, k % 2, a['compounds'],
                             a['label'].replace(' ', '~')))
        s0, s1 = rec['spare']
        rows.append((row, (s0 - lo0) // u, (s1 + 1 - lo0) // u, 2, 0, 'spare'))
    write('ranges.dat', ['row', 'u0', 'u1', 'kind', 'compounds', 'district'], rows)


def registry_points():
    hil, cell = [], []
    a = E.olc_decode(EXAMPLE_CELL + '+')
    tile = EXAMPLE_CELL[:4]
    with gzip.open(os.path.join(REPO, 'registry', tile + '.csv.gz'), 'rt', newline='') as f:
        for r in csv.DictReader(f):
            lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
            if r['zone'] == EXAMPLE_ZONE:
                hil.append((lng, lat, int(r['number'])))
            if a['south'] <= lat < a['north'] and a['west'] <= lng < a['east']:
                full = E.olc_encode(lat, lng)
                cell.append((round((lng - a['west']) / 0.000125, 3), round((lat - a['south']) / 0.000125, 3),
                             r['number'], full[-2:]))
    hil.sort(key=lambda p: p[2])
    write('moyamba-numbers.dat', ['lng', 'lat', 'number'], hil)
    # The path joins consecutive numbers only (a step of 2 in this block); a larger gap
    # means the curve left the cell, so the line is broken there.
    cell.sort(key=lambda c: int(c[2]))
    path = []
    for k, c in enumerate(cell):
        if k and int(c[2]) - int(cell[k - 1][2]) > 2:
            path.append(('nan', 'nan', 0, '-'))
        path.append(c)
    write('spot-cell.dat', ['cx', 'cy', 'number', 'pair'], path)


def hilbert():
    # The order-3 curve of Eq. (8): every cell of an 8 x 8 grid with its position h.
    cells = sorted((E.hilbert_d(3, x, y), x, y) for x in range(8) for y in range(8))
    write('hilbert.dat', ['h', 'cx', 'cy'], [(h, x + 0.5, y + 0.5) for h, x, y in cells])


def districts():
    order = sorted(((k, v) for k, v in STATS['districts'].items() if v['compounds'] > 1000),
                   key=lambda kv: kv[1]['compounds'])
    rows = []
    for i, (k, v) in enumerate(order):
        osm = v['fromOpenStreetMap']
        ml = v['structures'] - osm
        dg = v['compoundsByDigits']
        n = v['compounds']
        rows.append((i, k.replace(' ', '~'),
                     round(osm / 1000, 2), round(ml / 1000, 2),
                     round(100 * dg.get('3', 0) / n, 2), round(100 * dg.get('4', 0) / n, 2),
                     round(100 * dg.get('5', 0) / n, 2)))
    write('districts.dat', ['i', 'district', 'osmK', 'mlK', 'd3', 'd4', 'd5'], rows)


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    outline()
    towns_and_zones()
    area_sizes()
    ranges()
    registry_points()
    districts()
    hilbert()
    print('figure data written to', OUT)

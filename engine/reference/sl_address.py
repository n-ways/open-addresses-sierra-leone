#!/usr/bin/env python3
"""N-Ways Addressing for Sierra Leone: reference engine (standard library only).

The normative description is engine/SPEC.md. The grid is the Open Location
Code (Plus Code) grid, because Freetown City Council already identifies
properties with Plus Codes (fcc.gov.sl, Property Reform FAQ): an N-Ways spot
code in Sierra Leone is a Plus Code. What the engine adds is what Plus Codes
lack: a code people can remember for every compound (plot or yard), made of a
community or town name and a number, with its structures, flats and shops, a
check digit for systems, and a fixed list of reference towns, so that nothing
depends on district or chiefdom boundaries (redrawn in 2017 and again in 2026).

Plate names: the name in a code is the area's PLATE NAME, at most 12
characters and 2 words ("Gbangbatoke 1051" for the area officially
"Gbangbatoke Junction"); the official name is printed small for context and,
typed, decodes as an alias (plate_names.py for the rule; tools/name_ranges.py
for the word lists and council flags).

Codes (docs/model.md):
  official   FQR7+HX Freetown            in Freetown City Council's area, FCC's Plus Code of the
                                         property, shown first, as FCC writes it
  compound   Moyamba 15727               what people remember: a community or town name + a number,
                                         unique in the whole country on its own (same-named areas share
                                         one national range for the name, in frozen blocks)
             Moyamba 157 27 · 5H68+3V Moyamba   plate: the name, the number in groups, the gate's Plus Code
             SL-03663-15727              machine form (area, number); systems add the check digit
  structure  Moyamba 15727.2             a building inside the compound (1 = main house)
  unit       Moyamba 15727.2/3           a flat, shop or room let separately
  spot       FQQ6+9G Freetown            any point: a Plus Code (short form + reference town)

Usage
  sl_address.py spot 8.48743 -13.23869             full and short Plus Code with its town
  sl_address.py recover "FQR7+HX" Freetown         short code + town -> full code and point
  sl_address.py number 2674 "Moyamba 15727"        check digit and plate text (name id, code)
  sl_address.py key "Ka-Sasi"                      the national name key (normalisation)
  sl_address.py plate "Gbangbatoke Junction"       does a name fit a plate (12 characters, 2 words)?
  sl_address.py decode "Moyamba 157 27"            name + number -> its one area, nationally
  sl_address.py towns                              the reference towns
  sl_address.py group footprints.geojson Moyamba 2674   group footprints into compounds and number them
  sl_address.py test                               run engine/reference/test_vectors.json
"""
import json, math, os, sys
import re as _re

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import plate_names  # noqa: E402  the plate-name limit (12 characters, 2 words)
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))

ALPHABET = '23456789CFGHJMPQRVWX'  # the Open Location Code alphabet
IDX = {c: i for i, c in enumerate(ALPHABET)}
SEP, SEP_POS, PAD = '+', 8, '0'
LAT_MULT = 8000 * 3125   # 20^3 * 5^5: integer precision of an 15-digit code
LNG_MULT = 8000 * 1024   # 20^3 * 4^5
GRID_ROWS, GRID_COLS = 5, 4
PAIR_RES = [20.0, 1.0, 0.05, 0.0025, 0.000125]

# Reference towns: fixed points, never moved once published (model/design.json).
# A short code is recovered against the town the person names; the engine only
# offers a town for shortening when the point is within SHORTEN_DEG (0.4 degrees)
# of it, inside the half degree within which Open Location Code recovery is exact.
TOWNS = None


def load_towns():
    global TOWNS
    if TOWNS is None:
        d = json.load(open(os.path.join(REPO, 'model', 'design.json')))
        TOWNS = d['referenceTowns']['towns']
    return TOWNS


def town(name):
    for t in load_towns():
        if t['name'].lower() == name.lower() or name.lower() in [a.lower() for a in t.get('aliases', [])]:
            return t
    raise ValueError(f'unknown reference town {name!r}')


# ---------------------------------------------------------------- Open Location Code
def olc_encode(lat, lng, length=10):
    lat = min(90.0, max(-90.0, lat))
    lng = (lng + 180) % 360 - 180
    if lat == 90:
        lat -= 0.000125 / 5 ** 0  # keep inside the last cell
    lat_val = int(math.floor(round((lat + 90) * LAT_MULT, 6)))
    lng_val = int(math.floor(round((lng + 180) * LNG_MULT, 6)))
    code = ''
    if length > 10:
        for _ in range(5):
            code = ALPHABET[(lat_val % GRID_ROWS) * GRID_COLS + lng_val % GRID_COLS] + code
            lat_val //= GRID_ROWS
            lng_val //= GRID_COLS
    else:
        lat_val //= GRID_ROWS ** 5
        lng_val //= GRID_COLS ** 5
    pairs = ''
    for _ in range(5):
        pairs = ALPHABET[lat_val % 20] + ALPHABET[lng_val % 20] + pairs
        lat_val //= 20
        lng_val //= 20
    full = pairs + code
    full = full[:SEP_POS] + SEP + full[SEP_POS:]
    return full[:length + 1] if length >= 8 else full[:length] + PAD * (8 - length) + SEP


def olc_decode(code):
    c = code.upper().replace(SEP, '').rstrip(PAD)
    lat, lng = -90.0, -180.0
    lat_res, lng_res = 400.0, 400.0
    for i in range(0, min(10, len(c)), 2):
        lat_res /= 20
        lng_res /= 20
        lat += IDX[c[i]] * lat_res
        if i + 1 < len(c):
            lng += IDX[c[i + 1]] * lng_res
    for ch in c[10:15]:
        lat_res /= GRID_ROWS
        lng_res /= GRID_COLS
        v = IDX[ch]
        lat += (v // GRID_COLS) * lat_res
        lng += (v % GRID_COLS) * lng_res
    return {'south': lat, 'west': lng, 'north': lat + lat_res, 'east': lng + lng_res,
            'lat': lat + lat_res / 2, 'lng': lng + lng_res / 2, 'length': len(c)}


def olc_shorten(code, ref_lat, ref_lng):
    a = olc_decode(code)
    rng = max(abs(a['lat'] - ref_lat), abs(a['lng'] - ref_lng))
    for i in range(len(PAIR_RES) - 2, 0, -1):
        if rng < PAIR_RES[i] * 0.3:
            return code[(i + 1) * 2:]
    return code


def olc_recover(short, ref_lat, ref_lng):
    if short.index(SEP) >= SEP_POS:
        return short.upper()
    pad = SEP_POS - short.index(SEP)
    res = 20 ** (2 - pad / 2)
    half = res / 2
    a = olc_decode(olc_encode(ref_lat, ref_lng)[:pad] + short.upper())
    lat, lng = a['lat'], a['lng']
    if ref_lat + half < lat and lat - res >= -90:
        lat -= res
    elif ref_lat - half > lat and lat + res <= 90:
        lat += res
    if ref_lng + half < lng:
        lng -= res
    elif ref_lng - half > lng:
        lng += res
    return olc_encode(lat, lng, a['length'])


# ---------------------------------------------------------------- spot codes
# N-Ways drops the first four characters when the point is within 0.4 degrees of the
# town on both axes (standard libraries use 0.3). Recovery is exact within 0.5 degrees,
# so 0.1 degree (~11 km) is left for another app placing the town slightly differently.
# The 31 towns in model/design.json reach every building in Sierra Leone this way.
SHORTEN_DEG = 0.4


def nearest_town(lat, lng):
    best = None
    for t in load_towns():
        d = max(abs(t['lat'] - lat), abs(t['lng'] - lng))
        if d < SHORTEN_DEG and (best is None or d < best[0]):
            best = (d, t)
    return best[1] if best else None


def spot(lat, lng, precise=False):
    """Full code, and the short form against the nearest reference town (Chebyshev degrees)."""
    full = olc_encode(lat, lng, 11 if precise else 10)
    t = nearest_town(lat, lng)
    return {'full': full, 'short': f"{full[4:]} {t['name']}" if t else full, 'town': t['name'] if t else None}


# ---------------------------------------------------------------- compound codes
# What people remember: a community or town name they already use and a short
# number, "Moyamba 15727" (in Freetown City Council's area beside FCC's Plus Code,
# which is shown first). The remembered code is unique in the
# whole country on its own: every address area whose name normalises to the same
# key (the several Crab Towns, Looking Towns, Kissy Towns ...) draws its numbers
# from ONE national range for that name, split into frozen blocks, one per area,
# so "Looking Town 13316" decodes to exactly one area and compound wherever it is said
# (docs/model.md section 4.1). The Plus Code of the gate is kept on the record
# and printed on the plate, for FCC and for any Plus Code app.
DAMM = [
    [0, 3, 1, 7, 5, 9, 8, 6, 4, 2], [7, 0, 9, 2, 1, 5, 4, 8, 6, 3], [4, 2, 0, 6, 8, 7, 1, 3, 5, 9],
    [1, 7, 5, 0, 9, 8, 3, 4, 2, 6], [6, 1, 2, 3, 0, 4, 5, 9, 7, 8], [3, 6, 7, 4, 2, 0, 9, 5, 8, 1],
    [5, 8, 6, 9, 7, 2, 0, 1, 3, 4], [8, 9, 4, 5, 3, 6, 2, 0, 1, 7], [9, 4, 3, 8, 6, 1, 7, 2, 0, 5],
    [2, 5, 8, 1, 4, 3, 6, 7, 9, 0]]
# Numbering frame: one Hilbert curve over the whole country (fixed box), so the order
# never depends on any administrative boundary.
FRAME = (6.85, -13.35, 10.05, -10.20)  # south, west, north, east


def damm(digits):
    k = 0
    for ch in digits:
        k = DAMM[k][int(ch)]
    return k


def check_digit(name_id, number):
    """Damm over the 4-digit national name id and the number. It binds name, number and
    area: the area is a frozen function of (name, number) -- the block the number falls
    in -- so the check is computed for exactly one area. Because the name id and the
    digits before the number are the same for every same-named area, Damm's guarantee
    holds across them: every single wrong digit and every swap of neighbours is caught,
    including the ones that would land in another block of the same name (another
    same-named area). Checked on 40 numbers in every block of the register
    (model/name-ranges.json): 582,688 such cross-area single typos, 0 accepted. Writing the area id digits into
    the check as well would break that guarantee (61,619 of them accepted, about 1 in 9).
    A right number under the wrong name fails 9 times in 10."""
    return damm(f'{name_id:04d}{number}')


def verify(record, name_id, number, check=None):
    """Decode name + number (+ optional check digit) to one area, or raise."""
    area = decode_number(record, number)
    if area is None:
        raise ValueError('no area of this name has that number')
    if check is not None and check != check_digit(name_id, number):
        raise ValueError('check digit does not match: a digit is wrong or two are swapped')
    return area


# ---------------------------------------------------------------- national name ranges
# Normalisation (English and Krio spellings): what counts as "the same name".
# Case, accents, punctuation, spaces and hyphens are folded; a leading "The" is
# dropped; Krio and English spellings of the same word are folded (tong/town,
# kru/kroo, saint/st, mount/mt, and/&); number words and digits are the same
# ("Koya Town 2" = "Koya Town Two"). Two areas whose names give the same key share
# one national range. The list is fixed in model/design.json -> names.normalise.
_WORD_FOLD = {'tong': 'town', 'kru': 'kroo', 'saint': 'st', 'mount': 'mt', 'mt.': 'mt', '&': 'and',
              'one': '1', 'two': '2', 'three': '3', 'four': '4', 'five': '5', 'six': '6',
              'seven': '7', 'eight': '8', 'nine': '9', 'ten': '10', 'ii': '2', 'iii': '3'}


def name_key(name):
    import unicodedata
    t = unicodedata.normalize('NFKD', name)
    t = ''.join(ch for ch in t if not unicodedata.combining(ch)).casefold()
    t = t.replace("'", '').replace('\u2019', '').replace('&', ' & ')
    for ch in '-_.,/()':
        t = t.replace(ch, ' ')
    words = [_WORD_FOLD.get(w, w) for w in t.split()]
    if len(words) > 1 and words[0] == 'the':
        words = words[1:]
    return ''.join(w for w in words if w.isalnum())


# A range of d digits is the 9 x 10^(d-1) numbers without a leading zero, cut into
# 90 units of 10^(d-2) numbers (10 for 3 digits, 100 for 4, 1,000 for 5).
# Each same-named area gets a block of whole units holding twice its compounds
# (half kept free inside the block, as before), blocks laid out in the order of the
# areas' seeds along the national curve, and at least NAME_SPARE_UNITS units of the
# range stay unallocated for future areas of that name. A name takes the smallest
# d >= 3 that fits; if even 5 digits do not fit, the name takes established
# qualifiers, decided once and listed (model/design.json -> names.qualified).
UNITS, NAME_SPARE_UNITS, MAX_DIGITS = 90, 9, 5


def unit_size(d):
    return 10 ** (d - 2)


def block_units(compounds, d):
    return max(1, -(-2 * compounds // unit_size(d)))


def name_range_digits(compounds_per_area):
    """Smallest d (3..5) whose 90 units hold every same-named area's block plus the
    name's spare units; None if even 5 digits do not fit (qualifier needed)."""
    for d in range(3, MAX_DIGITS + 1):
        if sum(block_units(n, d) for n in compounds_per_area) + NAME_SPARE_UNITS <= UNITS:
            return d
    return None


def allocate_name(areas):
    """First issue of one normalised name. areas: [(area id, seed lat, seed lon, compounds)].
    Returns {'digits', 'blocks': [{'area', 'lo', 'hi'}], 'spareLo', 'spareHi'}: block numbers
    are lo..hi inclusive; spareLo..spareHi is the unallocated rest. Frozen at issue: a
    name's blocks are never renumbered."""
    d = name_range_digits([a[3] for a in areas])
    if d is None:
        raise ValueError('combined compounds exceed a 5-digit range: give this name its listed qualifiers')
    u, lo = unit_size(d), 10 ** (d - 1)
    blocks, at = [], lo
    for a in sorted(areas, key=lambda a: (curve_position(a[1], a[2]), str(a[0]))):
        size = block_units(a[3], d) * u
        blocks.append({'area': a[0], 'lo': at, 'hi': at + size - 1})
        at += size
    return {'digits': d, 'blocks': blocks, 'spareLo': at, 'spareHi': 10 ** d - 1}


def add_block(record, area_id, compounds):
    """A new area with an existing name, or a full block: the next whole units from the
    name's spare space (top of the range). Existing blocks never move. If the spare is
    exhausted the name opens a range one digit longer (numbers of different lengths never
    collide); beyond 5 digits the new area takes one of the name's listed qualifiers."""
    d = record['digits']
    size = block_units(compounds, d) * unit_size(d)
    if record['spareHi'] - record['spareLo'] + 1 >= size:
        b = {'area': area_id, 'lo': record['spareLo'], 'hi': record['spareLo'] + size - 1}
        record['blocks'].append(b)
        record['spareLo'] += size
        return b
    if record.get('next'):
        return add_block(record['next'], area_id, compounds)
    if d >= MAX_DIGITS:
        raise ValueError('name range full at 5 digits: the new area takes one of the name\'s listed qualifiers')
    d2 = d + 1
    size = block_units(compounds, d2) * unit_size(d2)
    b = {'area': area_id, 'lo': 10 ** d, 'hi': 10 ** d + size - 1}
    record['next'] = {'digits': d2, 'blocks': [b], 'spareLo': 10 ** d + size, 'spareHi': 10 ** d2 - 1}
    return b


def decode_number(record, number):
    """The block (hence the area) a number belongs to, or None if it is in no block.
    The number's length picks the range (a name's longer extension range, if any)."""
    while record and len(str(number)) != record['digits']:
        record = record.get('next')
    if not record:
        return None
    for b in record['blocks']:
        if b['lo'] <= number <= b['hi']:
            return b['area']
    return None


def hilbert_d(order, x, y):
    d, s = 0, 1 << (order - 1)
    while s > 0:
        rx = 1 if x & s else 0
        ry = 1 if y & s else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        s >>= 1
    return d


def curve_position(lat, lng, order=16):
    s, w, n, e = FRAME
    side = 1 << order
    x = min(side - 1, max(0, int((lng - w) / (e - w) * side)))
    y = min(side - 1, max(0, int((lat - s) / (n - s) * side)))
    return hilbert_d(order, x, y)


def digits_for(n):
    d = 3
    while 9 * 10 ** (d - 1) < 2 * n:
        d += 1
    return d


def number_area(anchors, block=None, digits=None):
    """First issue in one address area: anchors (compound id, lat, lon), usually gates.
    block: the area's block {'lo', 'hi'} in its name's national range (allocate_name);
    without one, the whole range of `digits` (a name with a single area and no spare,
    used only by the examples). Evenly spaced numbers along the curve inside the block;
    half the block stays free."""
    if block is None:
        d = digits or digits_for(len(anchors))
        block = {'lo': 10 ** (d - 1), 'hi': 10 ** d - 1}
    lo, cap = block['lo'], block['hi'] - block['lo'] + 1
    if 2 * len(anchors) > cap:
        raise ValueError('block too full: take a further block from the name\'s spare (add_block)')
    order = sorted(anchors, key=lambda a: (curve_position(a[1], a[2]), str(a[0])))
    step = cap // max(1, len(order))
    return {a[0]: lo + i * step + step // 2 for i, a in enumerate(order)}, len(str(lo))


def next_free_number(lat, lng, issued, block):
    """Add my home: the free number halfway between the curve neighbours, inside the
    area's block. issued: {number: (lat, lng)} of this block. A full block raises; the
    area then takes another block from its name's spare (add_block)."""
    if isinstance(block, int):   # digits only: the whole range (examples)
        block = {'lo': 10 ** (block - 1), 'hi': 10 ** block - 1}
    pos = curve_position(lat, lng)
    lo_n, hi_n = block['lo'] - 1, block['hi'] + 1
    for p, n in sorted((curve_position(la, lo), n) for n, (la, lo) in issued.items()):
        if p <= pos:
            lo_n = n
        else:
            hi_n = n
            break
    cand = (lo_n + hi_n) // 2
    for delta in range(block['hi'] - block['lo'] + 2):
        for k in (cand + delta, cand - delta):
            if lo_n < k < hi_n and k not in issued:
                return k
    for k in range(block['lo'], block['hi'] + 1):
        if k not in issued:
            return k
    raise ValueError('block full: the area takes a further block from its name\'s spare (add_block)')


# ---------------------------------------------------------------- plate names
PLATE_LANG = 'en'   # Sierra Leone's area names are English and Krio (with Temne, Mende ... words)


def plate_name_ok(name):
    """A plate name has at most 12 characters (letters, spaces, hyphens, apostrophes; an
    accented letter is one) and at most 2 words (a hyphen separates words; of/the/and
    do not count) and no digit (the number is always the last thing in a code)."""
    return plate_names.fits(name, PLATE_LANG)


def check_plate_name(name):
    if not plate_name_ok(name):
        raise ValueError(f'{name!r} is not a plate name: at most {plate_names.MAX_CHARS} characters and '
                         f'{plate_names.MAX_WORDS} words, no digits (the council confirms a short name before first issue)')
    return name


def group_digits(number):
    """Written and said in groups, like Sierra Leonean phone numbers: 482 / 27 16 / 482 15."""
    s = str(number)
    return {3: s, 4: s[:2] + ' ' + s[2:], 5: s[:3] + ' ' + s[3:]}.get(len(s), s)


def compound_text(area_name, number, structure=None, unit=None):
    t = f'{check_plate_name(area_name)} {number}'
    if structure:
        t += f'.{structure}'
        if unit:
            t += f'/{unit}'
    return t


def plate(area_name, name_id, number, gate_lat=None, gate_lng=None):
    """Plate text: the name, the number in groups and the gate's Plus Code (short form with
    its town). The check digit is for systems and is never printed; name_id is kept in the
    signature so that callers can print the machine form beside it if they need to."""
    t = f'{check_plate_name(area_name)} {group_digits(number)}'
    if gate_lat is not None:
        t += f" · {spot(gate_lat, gate_lng)['short']}"
    return t


def parse_compound(text):
    """'Moyamba 15727', 'moyamba 157 27.2/3', 'Moyamba 157 27 · 0' -> (name, number, structure, unit, check).
    A check digit after the number, typed by a system, is returned to be verified."""
    t = text.strip()
    unit = structure = check = None
    if '/' in t:
        t, unit = t.rsplit('/', 1)
        unit = int(unit)
    if '.' in t.split()[-1]:
        t, structure = t.rsplit('.', 1)
        structure = int(structure)
    words = t.replace('-', ' ').replace('·', ' ').split()
    nums = []
    while words and words[-1].isdigit():
        nums.insert(0, words.pop())
    if not words or not nums:
        raise ValueError('expected an area name and a number')
    if len(nums) >= 2 and len(nums[-1]) == 1 and len(''.join(nums[:-1])) >= 3:
        check = int(nums.pop())
    return ' '.join(words), int(''.join(nums)), structure, unit, check


# ---------------------------------------------------------------- compounds
M_LAT, M_LON = 110574.0, 111320.0
# Sierra Leone compound rules (docs/model.md "Compounds"), from model/profile-stats.json:
# satellites join a principal within JOIN_M; huts and kitchens around a village yard
# within YARD_M where the hectare is sparse; nothing is grouped in hectares above DENSE
# (Kroo Bay, Susan's Bay, Mabella, the hillside settlements), where each structure is its own unit.
SATELLITE_MAX_M2, PRINCIPAL_MIN_M2, JOIN_M, YARD_M, YARD_MAX_HA, DENSE = 30.0, 30.0, 4.0, 8.0, 25, 70


def _area(r):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]))) / 2


def _inside(p, r):
    x, y = p
    inside = False
    for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def _seg(p, a, b):
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def _dist(r1, r2):
    if any(_inside(p, r2) for p in r1) or any(_inside(p, r1) for p in r2):
        return 0.0
    e1, e2 = list(zip(r1, r1[1:] + r1[:1])), list(zip(r2, r2[1:] + r2[:1]))
    return min(min(_seg(p, a, b) for p in r1 for a, b in e2), min(_seg(p, a, b) for p in r2 for a, b in e1))


def group(features, enclosures=(), gates=()):
    """Group footprints into compounds (engine/SPEC.md section 4.2): walls first, then
    satellites joined to a principal building, with the yard and density rules above."""
    if not features:
        return []
    lat0 = sum(p[1] for f in features for p in f['ring']) / sum(len(f['ring']) for f in features)
    k = M_LON * math.cos(math.radians(lat0))
    to_m = lambda lon, lat: (lon * k, lat * M_LAT)
    fs = []
    for f in features:
        r = [to_m(*p) for p in f['ring']]
        fs.append({'id': f['id'], 'ring': r, 'area': _area(r), 'c': (sum(p[0] for p in r) / len(r), sum(p[1] for p in r) / len(r)), 'll': f['ring']})
    cell = lambda p: (math.floor(p[0] / 100), math.floor(p[1] / 100))
    per_ha = {}
    for f in fs:
        per_ha[cell(f['c'])] = per_ha.get(cell(f['c']), 0) + 1
    encl = [{'id': e['id'], 'ring': [to_m(*p) for p in e['ring']]} for e in enclosures]
    gts = [{'id': g['id'], 'p': to_m(g['lon'], g['lat']), 'll': (g['lat'], g['lon'])} for g in gates]
    home_of, how = {}, {}
    for f in fs:
        for e in encl:
            if _inside(f['c'], e['ring']):
                home_of[f['id']], how[f['id']] = 'wall:' + str(e['id']), ('wall', 0.8)
                break
    principals = [f for f in fs if f['id'] not in home_of and f['area'] >= PRINCIPAL_MIN_M2]
    for f in fs:
        if f['id'] in home_of:
            continue
        dens = per_ha[cell(f['c'])]
        if dens > DENSE:
            home_of[f['id']], how[f['id']] = 'b:' + str(f['id']), ('dense', 0.6)
            continue
        reach = YARD_M if dens <= YARD_MAX_HA else JOIN_M
        if f['area'] < SATELLITE_MAX_M2:
            best = None
            for p in principals:
                if p['area'] >= 2 * f['area'] and math.dist(p['c'], f['c']) < 60:
                    d = _dist(f['ring'], p['ring'])
                    if d <= reach and (best is None or d < best[0]):
                        best = (d, p)
            if best:
                home_of[f['id']] = 'b:' + str(best[1]['id'])
                how[f['id']] = ('yard' if reach == YARD_M else 'proximity', 0.4 if reach == YARD_M else 0.45)
                continue
        home_of[f['id']], how[f['id']] = 'b:' + str(f['id']), ('single', 0.5)
    comps = {}
    for f in fs:
        comps.setdefault(home_of[f['id']], []).append(f)
    out = []
    for cid, members in comps.items():
        members.sort(key=lambda f: (-f['area'], str(f['id'])))
        kinds = {how[m['id']][0] for m in members}
        rule = 'wall' if 'wall' in kinds else ('yard' if 'yard' in kinds else 'proximity') if len(members) > 1 else min(kinds)
        conf = min(how[m['id']][1] for m in members)
        gate = None
        if cid.startswith('wall:'):
            ring = next(e['ring'] for e in encl if 'wall:' + str(e['id']) == cid)
            near = [g for g in gts if min(_seg(g['p'], a, b) for a, b in zip(ring, ring[1:] + ring[:1])) <= 3]
            gate = min(near, key=lambda g: math.dist(g['p'], members[0]['c'])) if near else None
        ll = members[0]['ll']
        anchor = list(gate['ll']) if gate else [round(sum(p[1] for p in ll) / len(ll), 7), round(sum(p[0] for p in ll) / len(ll), 7)]
        out.append({'compound': cid, 'rule': rule, 'confidence': conf, 'gate': gate['id'] if gate else None, 'anchor': anchor,
                    'structures': [{'index': i + 1, 'footprint': m['id'], 'areaM2': round(m['area'], 1)} for i, m in enumerate(members)]})
    return out


def load_register(path=None):
    """The frozen register (engine/data/register.json) as {key: record}
    with each record's areas and blocks, plus {official name key: plate name key} aliases."""
    d = json.load(open(path or os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))
    out = {}
    for k, n in d['names'].items():
        out[k] = {'nameId': n['id'], 'digits': n['digits'], 'spareLo': n['spare'][0], 'spareHi': n['spare'][1], 'blocks': [], 'areas': {}}
    for a in d['areas']:
        rec = out[a['key']]
        rec.setdefault('name', a['name'])
        for lo, hi in a['blocks']:
            rec['blocks'].append({'area': a['index'], 'lo': lo, 'hi': hi})
        rec['areas'][a['index']] = {'name': a['name'], 'officialName': a['officialName'], 'place': a['place'], 'lat': a['lat'],
                                    'lon': a['lon'], 'district': a['label'], 'fcc': a['fcc']}
    return out, d.get('aliases', {})


def resolve(register, aliases, name):
    """The name record for a typed name: its plate name, or an official name that is an
    alias of exactly one plate name (an alias claimed by two plate names is not listed)."""
    k = name_key(name)
    return register.get(k) or register.get(aliases.get(k, ''))


def decode_compound(text, register, aliases):
    """'Moyamba 157 27' -> {'area', 'number', 'structure', 'unit', 'machine'}, nationally, or ValueError.
    An official name that ends in a number ("Mile 91 1001", "Badasuma 2 101") is tried with
    its number as part of the name too: every split is tried, the longest number first,
    and the first that names an area and a block wins."""
    t = text.split(',')[0].strip()
    name, number, st, un, chk = parse_compound(t)
    # the digit groups after the name, as typed (the number may be grouped: "157 27")
    m = _re.match(r'^(.*?)((?:\s+\d+)+)(\s*·\s*\d)?(\.\d+(?:/\d+)?)?$', t.replace('-', ' '))
    nums = m.group(2).split() if m else [str(number)]
    if chk is not None and m and not m.group(3) and len(nums) >= 2 and len(nums[-1]) == 1:
        nums = nums[:-1]
    why = f'no area of Sierra Leone is called {name!r}'
    for k in range(len(nums), 0, -1):
        nm = ' '.join([name] + nums[:len(nums) - k]) if k < len(nums) else name
        n = int(''.join(nums[len(nums) - k:]))
        rec = resolve(register, aliases, nm)
        if rec is None:
            continue
        area = decode_number_any(rec, n)
        if area is None:
            why = 'no area of this name has that number'
            continue
        if chk is not None and chk != check_digit(rec['nameId'], n):
            why = 'check digit does not match: a digit is wrong or two are swapped'
            continue
        return {'area': area, 'number': n, 'structure': st, 'unit': un, 'machine': f'SL-{area:05d}-{n}'}
    raise ValueError(why)


def decode_number_any(record, number):
    """The area whose block holds the number, whatever its length (a name's blocks of every range)."""
    for b in record['blocks']:
        if b['lo'] <= number <= b['hi']:
            return b['area']
    return None


# ---------------------------------------------------------------- command line
def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd = argv[1]
    if cmd == 'spot':
        print(json.dumps(spot(float(argv[2]), float(argv[3]), precise=len(argv) > 4)))
    elif cmd == 'recover':
        t = town(' '.join(argv[3:]))
        full = olc_recover(argv[2], t['lat'], t['lng'])
        print(json.dumps({'full': full, **olc_decode(full)}))
    elif cmd == 'number':
        name, number, st, un, chk = parse_compound(argv[3])
        cd = check_digit(int(argv[2]), number)
        print(json.dumps({'text': compound_text(name, number, st, un), 'plate': plate(name, int(argv[2]), number),
                          'checkDigit': cd, 'checkGiven': chk, 'checkOk': None if chk is None else chk == cd}))
    elif cmd == 'key':
        print(name_key(' '.join(argv[2:])))
    elif cmd == 'plate':
        n = ' '.join(argv[2:])
        print(json.dumps({'name': n, 'characters': plate_names.plate_length(n), 'words': plate_names.word_count(n, PLATE_LANG),
                          'plateName': plate_name_ok(n)}, ensure_ascii=False))
    elif cmd == 'decode':
        reg, aliases = load_register()
        d = decode_compound(' '.join(argv[2:]), reg, aliases)
        print(json.dumps(d, ensure_ascii=False))
    elif cmd == 'towns':
        print(json.dumps(load_towns(), indent=1, ensure_ascii=False))
    elif cmd == 'group':
        fc = json.load(open(argv[2]))
        feats, encl, gates = [], [], []
        for f in fc['features']:
            g, p = f['geometry'], f.get('properties', {})
            if g['type'] == 'Point':
                gates.append({'id': p.get('id'), 'lon': g['coordinates'][0], 'lat': g['coordinates'][1]})
            else:
                ring = [tuple(x) for x in (g['coordinates'][0] if g['type'] == 'Polygon' else g['coordinates'][0][0])][:-1]
                (encl if p.get('barrier') in ('wall', 'fence') else feats).append({'id': p.get('id'), 'ring': ring})
        comps = group(feats, encl, gates)
        area_name, name_id = argv[3], int(argv[4])
        nums, d = number_area([(c['compound'], *c['anchor']) for c in comps])
        for c in comps:
            c['code'] = compound_text(area_name, nums[c['compound']])
            c['plate'] = plate(area_name, name_id, nums[c['compound']], *c['anchor'])
        print(json.dumps(comps, indent=1))
    elif cmd == 'test':
        return run_tests()
    else:
        print(__doc__)
        return 1
    return 0


def run_tests():
    tv = json.load(open(os.path.join(HERE, 'test_vectors.json')))
    bad = 0
    for v in tv['olc']:
        got = olc_encode(v['lat'], v['lng'], v.get('length', 10))
        ok = got == v['full']
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'encode', v['name'], got)
    for v in tv['recover']:
        t = town(v['town'])
        got = olc_recover(v['short'], t['lat'], t['lng'])
        a = olc_decode(got)
        ok = got == v['full'] and ('lat' not in v or (a['south'] <= v['lat'] <= a['north'] and a['west'] <= v['lng'] <= a['east']))
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'recover', v['short'], v['town'], got)
    for v in tv['spot']:
        got = spot(v['lat'], v['lng'])['short']
        ok = got == v['short']
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'spot', v['name'], got)
    for v in tv.get('numbers', []):
        name, number, st, un, chk = parse_compound(v['text'])
        ok = (name, number, st, un) == (v['area'], v['number'], v.get('structure'), v.get('unit'))
        if 'check' in v:
            ok = ok and (check_digit(v['nameId'], number) == v['check']) == v.get('checkValid', True)
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'number', v['text'])
    for v in tv.get('nameKeys', []):
        got = [name_key(t) for t in v['names']]
        ok = all(k == v['key'] for k in got)
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'name key', v['names'], got)
    for v in tv.get('nameKeysDistinct', []):
        got = [name_key(t) for t in v['names']]
        ok = len(set(got)) == len(got)
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'distinct names', v['names'], got)
    for v in tv.get('allocation', []):
        rec = allocate_name([tuple(x) for x in v['areas']])
        ok = rec['digits'] == v['digits'] and [[b['area'], b['lo'], b['hi']] for b in rec['blocks']] == v['blocks'] \
            and [rec['spareLo'], rec['spareHi']] == v['spare']
        for nb in v.get('addBlocks', []):
            b = add_block(rec, nb['area'], nb['compounds'])
            ok = ok and [b['area'], b['lo'], b['hi']] == nb['expect']
        ok = ok and [[b['area'], b['lo'], b['hi']] for b in rec['blocks'][:len(v['blocks'])]] == v['blocks']  # frozen
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'allocation', v['name'], rec['digits'], [[b['area'], b['lo'], b['hi']] for b in rec['blocks']])
    reg = {k: {**r, 'blocks': [dict(area=b[0], lo=b[1], hi=b[2]) for b in r['blocks']]} for k, r in tv.get('register', {}).items()}
    aliases = tv.get('aliases', {})
    for v in tv.get('plateNames', []):
        ok = plate_name_ok(v['plate']) and plate_name_ok(v['official']) == v.get('officialFits', False)
        if 'key' in v:
            rec = resolve(reg, aliases, v['official'])
            ok = ok and name_key(v['plate']) == v['key'] and rec is not None and rec is reg[v['key']]
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'plate name', v['official'], '->', v['plate'])
    for v in tv.get('plateRejected', []):
        try:
            compound_text(v['name'], 1050)
            ok = False
        except ValueError:
            ok = True
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'not a plate name', v['name'])
    for v in tv.get('decode', []):
        name, number, st, un, chk = parse_compound(v['text'])
        rec = resolve(reg, aliases, name)
        try:
            got = verify(rec, rec['nameId'], number, chk)
        except ValueError as e:
            got = 'reject'
        ok = got == v['expect']
        bad += not ok
        where = rec['areas'].get(str(got), {}) if got != 'reject' else {}
        print(('ok  ' if ok else 'FAIL'), 'decode', v['text'], '->', got, where.get('where', ''))
    for v in tv.get('numbering', []):
        nums, d = number_area([tuple(x) for x in v['anchors']])
        ok = nums == v['expect'] and d == v['digits']
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'numbering', v['name'], nums)
    for v in tv.get('compounds', []):
        comps = group(v['footprints'], v.get('enclosures', []), v.get('gates', []))
        got = sorted(sorted(s['footprint'] for s in c['structures']) for c in comps)
        ok = got == sorted(sorted(x) for x in v['expect'])
        bad += not ok
        print(('ok  ' if ok else 'FAIL'), 'group', v['name'], got)
    print('all passed' if not bad else f'{bad} failed')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

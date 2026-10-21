"""The addressing rules the server applies, on top of the reference engine.

Parsing, check digits, name keys, Plus Codes and the "next free number" rule
come from ``engine/reference/sl_address.py`` unchanged. What lives here is the
part only an issuer needs: the register in force (the frozen areas with every
block added since), the choice of area for a new compound, extension blocks,
and the card a code is served as.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
REFERENCE = os.environ.get('ENGINE_REFERENCE', os.path.join(REPO, 'engine', 'reference'))
if REFERENCE not in sys.path:
    sys.path.insert(0, REFERENCE)
import sl_address as E  # noqa: E402  the reference engine

from . import COUNTRY, COUNTRY_NAME  # noqa: E402
from .geo import dist_m  # noqa: E402

AREA_COLUMNS = ['zone', 'seed_id', 'plate_name', 'official_name', 'place', 'district', 'fcc_area', 'name_key', 'name_id',
                'blocks', 'needs_council_choice', 'tile', 'seed_lat', 'seed_lon']
CODE_COLUMNS = ['machine', 'home', 'written', 'zone', 'official_name', 'district', 'number', 'check', 'status', 'issued',
                'issued_at', 'entrance_lat', 'entrance_lng', 'entrance_kind', 'plus_code', 'fcc_address', 'class', 'use',
                'kind', 'structures', 'floor_area_m2', 'rule', 'estate']

CREDIT = 'N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)'
CREDIT_URL = 'https://github.com/n-ways/open-addresses-sierra-leone'

# Issue limits (engine/SPEC.md section 8).
MIN_AREA_M2 = 6.0
MAX_AREA_M2 = 20000.0
EXISTS_M = 3.0          # a point this close to an issued compound already has its code
AT_M = 12.0             # "what is here": the compound within this distance
SPOT_M = 15.0           # a Plus Code typed as a code: the compound within this distance of its centre
DOOR_M = 80.0           # another door of a compound, or a moved entrance, stays this close to it
PRIMARY_M = 4000.0      # a new compound joins the nearest primary seed within this distance,
SECONDARY_M = 15000.0   # else the nearest secondary seed within this one, else the nearest primary

name_key = E.name_key


def group_digits(n):
    return E.group_digits(n)


def place_line(area):
    """What is shown beside a code: Freetown in FCC's area, else the district."""
    if area['fcc']:
        return 'Freetown'
    if not area['district']:
        return COUNTRY_NAME
    if area['district'] == 'Western Area Rural':
        return area['district']
    return area['district'] + ' District'


def forms(area, number):
    """Every form of a code. ``written`` is the registry's written form (the
    remembered form with its number in groups); the check digit is for systems."""
    chk = E.check_digit(area['nameId'], number)
    return {'machine': f"{COUNTRY}-{area['index']:05d}-{number}", 'home': f"{area['name']} {number}",
            'written': f"{area['name']} {E.group_digits(number)}", 'spoken': f"{area['name']}, {E.group_digits(number)}",
            'check': chk}


class Register:
    """The register in force: towns, names, aliases and areas with their blocks."""

    def __init__(self, con):
        self.towns = [{'name': r['name'], 'lat': r['lat'], 'lng': r['lng'], 'aliases': json.loads(r['aliases'])}
                      for r in con.execute('SELECT * FROM towns ORDER BY name')]
        E.TOWNS = self.towns     # the reference engine's spot codes use the published towns
        self.names = {r['key']: {'id': r['id'], 'digits': r['digits'], 'spare': (r['spare_lo'], r['spare_hi'])}
                      for r in con.execute('SELECT * FROM names')}
        self.aliases = {r['key']: r['name_key'] for r in con.execute('SELECT * FROM aliases')}
        self.areas, self.by_zone, self.families = [], {}, {}
        for r in con.execute('SELECT * FROM areas ORDER BY idx'):
            a = {'index': r['idx'], 'zone': r['zone'], 'name': r['plate_name'], 'officialName': r['official_name'],
                 'place': r['place'], 'district': r['district'], 'fcc': r['fcc_area'] == 'true', 'key': r['name_key'],
                 'nameId': r['name_id'], 'blocks': parse_blocks(r['blocks']), 'needsCouncilChoice': r['needs_council_choice'] == 'true',
                 'tile': r['tile'], 'tier': r['tier'], 'lat': r['lat'], 'lon': r['lon'], 'seedId': r['seed_id']}
            self.areas.append(a)
            self.by_zone[a['zone']] = a
            self.families.setdefault(a['key'], []).append(a)
        self.records = self._records()

    def _records(self):
        """The register in the reference engine's shape (sl_address.load_register)."""
        out = {}
        for k, n in self.names.items():
            out[k] = {'nameId': n['id'], 'digits': n['digits'], 'spareLo': n['spare'][0], 'spareHi': n['spare'][1],
                      'blocks': [], 'areas': {}}
        for a in self.areas:
            rec = out[a['key']]
            rec.setdefault('name', a['name'])
            for lo, hi in a['blocks']:
                rec['blocks'].append({'area': a['index'], 'lo': lo, 'hi': hi})
            rec['areas'][a['index']] = {'name': a['name'], 'officialName': a['officialName']}
        return out

    def area(self, zone):
        if isinstance(zone, int) or (isinstance(zone, str) and zone.isdigit()):
            return self.by_zone.get(f'{int(zone):05d}')
        return None

    def owner(self, key, number):
        for a in self.families.get(key, []):
            if any(lo <= number <= hi for lo, hi in a['blocks']):
                return a
        return None

    def resolve(self, name):
        """The plate-name key of a typed name, or of an official name that is an alias of one plate name."""
        k = E.name_key(name)
        if k in self.names:
            return k
        return self.aliases.get(k)

    # ------------------------------------------------------------ decoding
    def decode_text(self, text):
        """A remembered or written form -> (area, number), or ValueError with the reason."""
        t = text.split(',')[0].strip()
        t = re.sub(r'(?<=[^\W\d_])(?=\d)', ' ', t, count=1)   # "Moyamba15727" -> "Moyamba 15727"
        d = E.decode_compound(t, self.records, self.aliases)
        return self.by_zone[f"{d['area']:05d}"], d['number'], d

    def decode_machine(self, text):
        """``SL-03663-15727`` (any case or spacing; ``·0`` may follow with the check digit).
        A structure (``.2``) and a unit (``/3``) may follow the number.
        -> (area, number, check given or None, structure, unit), or ValueError."""
        t = re.sub(r'\s+', '', text.strip().upper())
        m = MACHINE_RE.match(t)
        if not m:
            raise ValueError(f'not an N-Ways {COUNTRY_NAME} machine code (SL-NNNNN-NNNNN)')
        idx, n = int(m.group(1)), int(m.group(2))
        a = self.by_zone.get(f'{idx:05d}')
        if a is None:
            raise ValueError(f'there is no area {m.group(1)}')
        if self.owner(a['key'], n) is not a:
            raise ValueError(f'the number {n} is not in a block of area {m.group(1)}')
        chk = int(m.group(5)) if m.group(5) is not None else None
        st = int(m.group(3)) if m.group(3) else None
        un = int(m.group(4)) if m.group(4) else None
        return a, n, chk, st, un

    def spot_point(self, text):
        """The centre of a Plus Code: full, or short with its reference town."""
        t = text.strip().split()
        code = t[0].upper()
        if code.index('+') < 8:
            if len(t) < 2:
                raise ValueError('a short Plus Code needs its town, like FQQ6+9G Freetown')
            name = ' '.join(t[1:])
            try:
                town = E.town(name)
            except ValueError:
                raise ValueError(f'{name!r} is not one of the reference towns (GET /v1/info lists them)')
            code = E.olc_recover(code, town['lat'], town['lng'])
        try:
            a = E.olc_decode(code)
        except (KeyError, IndexError):
            raise ValueError(f'{t[0]!r} is not a valid Plus Code')
        return a['lat'], a['lng'], code, a

    # ------------------------------------------------------------ issue
    def place_for(self, lat, lon):
        """The area a new compound takes: the nearest primary seed (city, town,
        suburb, quarter, village) within 4 km, else the nearest secondary seed
        within 15 km, else the nearest primary seed at any distance."""
        def near(tier, max_m):
            best, bd = None, max_m
            for a in self.areas:
                if a['tier'] != tier:
                    continue
                d = dist_m(a['lat'], a['lon'], lat, lon)
                if d < bd or (d == bd and best is not None and a['index'] < best['index']):
                    best, bd = a, d
            return best
        return near('P', PRIMARY_M) or near('S', SECONDARY_M) or near('P', math.inf)

    def add_block(self, area, compounds):
        """The next block of a name, appended to ``area['blocks']``: whole units
        from the name's spare holding twice ``compounds``; when the spare is too
        small the name opens a range one digit longer. None past 5 digits."""
        n = self.names.get(area['key'])
        if n is None:
            return None
        d = n['digits']
        lo, hi = n['spare']
        family = self.families.get(area['key'], [])
        for x in family:
            for b in x['blocks']:
                if len(str(b[0])) > d:
                    d = len(str(b[0]))
                    lo, hi = 10 ** (d - 1), 10 ** d - 1
        for x in family:
            for b in x['blocks']:
                if len(str(b[0])) == d and b[1] + 1 > lo:
                    lo = b[1] + 1
        size = E.block_units(compounds, d) * E.unit_size(d)
        if hi - lo + 1 >= size:
            b = (lo, lo + size - 1)
        elif d >= E.MAX_DIGITS:
            return None
        else:
            d += 1
            size = E.block_units(compounds, d) * E.unit_size(d)
            b = (10 ** (d - 1), 10 ** (d - 1) + size - 1)
        area['blocks'].append(b)
        return b

    def insert(self, area, issued, lat, lon):
        """A new compound's number in its area: the free number halfway between
        its curve neighbours in the first block with room, else the middle of a
        new block. ``issued``: [(number, lat, lon)] of every code of the area.
        -> (number, new block or None), or (None, None) when the name is full."""
        for lo, hi in area['blocks']:
            inb = {n: (la, lo_) for n, la, lo_ in issued if lo <= n <= hi}
            try:
                return E.next_free_number(lat, lon, inb, {'lo': lo, 'hi': hi}), None
            except ValueError:
                continue
        b = self.add_block(area, len(issued) + 1)
        if b is None:
            return None, None
        return b[0] + (b[1] - b[0] + 1) // 2, b


MACHINE_RE = re.compile(r'^SL-?(\d{5})-?(\d{3,5})(?:\.(\d{1,2})(?:/(\d{1,3}))?)?(?:·(\d))?$')
SPOT_RE = re.compile(r'^[23456789CFGHJMPQRVWX0]{4}(?:[23456789CFGHJMPQRVWX0]{4})?\+[23456789CFGHJMPQRVWX]{2,3}$')


def looks_machine(text):
    return bool(MACHINE_RE.match(re.sub(r'\s+', '', text.strip().upper())))


def looks_spot(text):
    t = text.strip().upper().split()
    return bool(t) and bool(SPOT_RE.match(t[0]))


def parse_blocks(s):
    return [tuple(int(x) for x in b.split('-')) for b in s.split('|')] if s else []


def format_blocks(blocks):
    return '|'.join(f'{lo}-{hi}' for lo, hi in blocks)


def spot(lat, lng):
    """The Plus Code of a point: 10 characters, 11 (precise), and the short form with its town."""
    s = E.spot(lat, lng)
    return {'full': s['full'], 'short': s['short'], 'precise': E.olc_encode(lat, lng, 11), 'town': s['town']}

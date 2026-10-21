"""The JSON API (``/v1``) over the store.

Every response is JSON. Errors are ``{"error": {"code", "message"}}`` with the
HTTP status that fits. Reads never take a lock; issuing and changes go through
one process-wide lock and a ``BEGIN IMMEDIATE`` transaction, so numbers stay
unique even with several writers on one database file.
"""
import hashlib
import hmac
import json
import math
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from . import COUNTRY, COUNTRY_NAME, SPEC
from . import engine as X
from . import geo, store

MAX_BODY = 64 * 1024
NEAR_MAX_M = 500.0
NEAR_MAX_RESULTS = 100
PAGE_MAX = 1000
STATUSES = ('provisional', 'confirmed', 'retired')


class ApiError(Exception):
    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def body(self):
        e = {'code': self.code, 'message': self.message}
        e.update(self.extra)
        return {'error': e}


def bad(code, message, **kw):
    return ApiError(400, code, message, **kw)


class Config:
    def __init__(self, db, port=8080, host='0.0.0.0', issue_keys=(), issue_per_day=5, cors_origins=(), outline=None, log_requests=True):
        self.db, self.port, self.host = db, port, host
        self.issue_keys = [k for k in issue_keys if k]
        self.issue_per_day = issue_per_day
        self.cors_origins = [o for o in cors_origins if o]
        self.outline = outline or f'{X.REPO}/engine/data/country.geojson'
        self.log_requests = log_requests


class Service:
    def __init__(self, cfg):
        self.cfg = cfg
        self.local = threading.local()
        self.write_lock = threading.Lock()
        self.outline = geo.Outline(cfg.outline)
        con = self.con()
        if store.meta(con, 'country') != COUNTRY:
            raise SystemExit(f'{cfg.db} is not an imported {COUNTRY_NAME} registry: run "python3 -m server import" first')
        self.spatial = store.meta(con, 'spatial', 'grid')
        self._reg, self._reg_rev = None, None
        self._reg_lock = threading.Lock()
        self._counts, self._counts_at = None, 0.0
        self.register()
        self.counts()

    # ------------------------------------------------------------ plumbing
    def con(self):
        c = getattr(self.local, 'con', None)
        if c is None:
            c = self.local.con = store.connect(self.cfg.db)
        return c

    def register(self):
        """The register in force; rebuilt when an issue has added a block (here or in another process)."""
        rev = store.meta(self.con(), 'blocks_rev', '0')
        if self._reg is None or rev != self._reg_rev:
            with self._reg_lock:
                if self._reg is None or rev != self._reg_rev:
                    self._reg, self._reg_rev = X.Register(self.con()), rev
                    self._zones = self._zone_names()
        return self._reg

    def _zone_names(self):
        """A zone (a registry file, one 4-character Plus Code area) is named after
        the district holding most of its compounds."""
        out = {}
        for r in self.con().execute('SELECT tile, district, sum(compounds) n, count(*) a FROM areas GROUP BY tile, district'):
            z = out.setdefault(r['tile'], {'districts': {}, 'areas': 0})
            z['districts'][r['district'] or COUNTRY_NAME] = r['n']
            z['areas'] += r['a']
        for k, z in out.items():
            z['name'] = max(z['districts'].items(), key=lambda kv: (kv[1], kv[0]))[0]
        return out

    def counts(self):
        """Codes by zone and status (cached for five minutes; a write here clears it)."""
        if self._counts is None or time.time() - self._counts_at > 300:
            by_zone, by_status = {}, {}
            for r in self.con().execute('SELECT tile, status, count(*) n FROM codes GROUP BY tile, status'):
                by_zone[r['tile']] = by_zone.get(r['tile'], 0) + r['n']
                by_status[r['status']] = by_status.get(r['status'], 0) + r['n']
            self._counts, self._counts_at = (by_zone, by_status), time.time()
        return self._counts

    def forget_counts(self):
        self._counts = None

    # ------------------------------------------------------------ shapes
    def area_json(self, a, full=False):
        out = {'id': a['zone'], 'plateName': a['name'], 'officialName': a['officialName'] or a['name'],
               'nameProvisional': a['needsCouncilChoice'], 'district': a['district'], 'placeLine': X.place_line(a),
               'place': a['place'], 'fccArea': a['fcc'], 'nameKey': a['key'], 'nameId': a['nameId'], 'zone': a['tile']}
        if full:
            n = self._reg.names[a['key']]
            rows = self.con().execute('SELECT status, count(*) n FROM codes WHERE zone = ? GROUP BY status', (a['zone'],)).fetchall()
            by = {r['status']: r['n'] for r in rows}
            out.update({
                'seed': {'id': a['seedId'], 'lat': a['lat'], 'lng': a['lon'], 'tier': 'primary' if a['tier'] == 'P' else 'secondary'},
                'blocks': [{'lo': lo, 'hi': hi, 'digits': len(str(lo)), 'size': hi - lo + 1} for lo, hi in a['blocks']],
                'codes': sum(by.values()), 'byStatus': by,
                'name': {'key': a['key'], 'id': n['id'], 'digits': n['digits'], 'spare': {'lo': n['spare'][0], 'hi': n['spare'][1]},
                         'areas': [x['zone'] for x in self._reg.families[a['key']]]}})
        return out

    def zone_json(self, key, full=False):
        z = self._zones.get(key)
        if z is None:
            raise ApiError(404, 'zone_not_found', f'There is no zone {key}. GET /v1/zones lists them.')
        a = X.E.olc_decode(key + '0000+')
        by_zone, _ = self.counts()
        out = {'key': key, 'name': z['name'], 'districts': sorted(z['districts'], key=lambda d: -z['districts'][d]),
               'bbox': [a['west'], a['south'], a['east'], a['north']], 'areas': z['areas'], 'codes': by_zone.get(key, 0)}
        if full:
            out['areaList'] = [self.area_json(x) for x in self._reg.areas if x['tile'] == key]
        return out

    def card(self, row, distance=None):
        reg = self._reg
        a = reg.by_zone[row['zone']]
        pl = X.place_line(a)
        lat, lng = row['lat'], row['lng']
        record = {c: (str(row['check_digit']) if c == 'check' else str(row[c]) if row[c] is not None else '') for c in X.CODE_COLUMNS}
        out = {
            'country': COUNTRY,
            'machine': row['machine'], 'remembered': row['home'], 'written': row['written'],
            'spoken': f"{a['name']}, {X.group_digits(row['number'])}", 'check': row['check_digit'],
            'number': row['number'], 'status': row['status'], 'issued': row['issued'], 'issuedAt': row['issued_at'],
            'officialAddress': row['fcc_address'] or None, 'coverage': 'official' if row['fcc_address'] else None,
            'area': self.area_json(a), 'zone': {'key': row['tile'], 'name': self._zones[row['tile']]['name']},
            'placeLine': pl, 'fullLine': f"{a['name']} {X.group_digits(row['number'])} · {pl}",
            'entrance': {'lat': lat, 'lng': lng, 'kind': row['entrance_kind']},
            'spot': X.spot(lat, lng),
            'building': {'class': row['class'], 'use': row['use'], 'kind': row['kind'], 'structures': int(row['structures'] or 0),
                         'floorAreaM2': float(row['floor_area_m2'] or 0), 'rule': row['rule'] or None, 'estate': row['estate'] or None},
            'outline': json.loads(row['outline']) if row['outline'] else None,
            'record': record,
            'credit': X.CREDIT, 'creditUrl': X.CREDIT_URL,
        }
        if distance is not None:
            out['distanceM'] = distance
        return out

    # ------------------------------------------------------------ spatial
    def candidates(self, lat, lng, radius_m):
        """Codes whose entrance lies in the box around a point."""
        dlat = radius_m / 110574.0 + 1e-7
        dlng = radius_m / (111320.0 * max(0.2, math.cos(math.radians(lat)))) + 1e-7
        c = self.con()
        if self.spatial == 'rtree':
            return c.execute('SELECT codes.* FROM codes_rtree JOIN codes ON codes.id = codes_rtree.id WHERE '
                             'min_lat >= ? AND max_lat <= ? AND min_lng >= ? AND max_lng <= ?',
                             (lat - dlat, lat + dlat, lng - dlng, lng + dlng)).fetchall()
        cells = [store.cell_of(la, ln) for la in _steps(lat - dlat, lat + dlat) for ln in _steps(lng - dlng, lng + dlng)]
        out = []
        for i in range(0, len(cells), 500):
            part = cells[i:i + 500]
            out += c.execute('SELECT * FROM codes WHERE cell IN (%s) AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?' % ','.join('?' * len(part)),
                             (*part, lat - dlat, lat + dlat, lng - dlng, lng + dlng)).fetchall()
        return out

    def code_at(self, lat, lng, max_m, live_only=True):
        """The compound at a point, as the issuer decides it: a compound whose
        outline holds the point; else the nearest whose entrance or outline is
        within ``max_m``. Retired codes are skipped. -> (row, metres) or (None, None)."""
        rows = self.candidates(lat, lng, max(max_m, 150.0))
        best = None
        for r in rows:
            if live_only and r['status'] == 'retired':
                continue
            if r['outline']:
                ring = geo.open_ring(json.loads(r['outline']))
                if geo.in_ring(lng, lat, ring):
                    return r, 0.0
        for r in rows:
            if live_only and r['status'] == 'retired':
                continue
            d = geo.ground_m(lat, lng, r['lat'], r['lng'])
            if r['outline']:
                d = min(d, geo.ring_dist_m(lat, lng, geo.open_ring(json.loads(r['outline']))))
            if d <= max_m and (best is None or (d, r['machine']) < (best[1], best[0]['machine'])):
                best = (r, d)
        return best if best else (None, None)

    def by_machine(self, machine):
        return self.con().execute('SELECT * FROM codes WHERE machine = ?', (machine,)).fetchone()

    def by_code(self, text):
        """The row of a machine code as typed (any case or spacing, optional check digit).

        None if the text is not a machine code or no compound has it; a check digit that
        does not match is refused (422), never looked past."""
        try:
            a, n, chk, _st, _un = self.register().decode_machine(text)
        except ValueError:
            return None
        if chk is not None and chk != X.E.check_digit(a['nameId'], n):
            raise ApiError(422, 'check_mismatch', 'The check digit does not match: a digit is wrong or two are swapped.')
        return self.con().execute('SELECT * FROM codes WHERE zone = ? AND number = ?', (a['zone'], n)).fetchone()

    def in_country(self, lat, lng):
        return self.outline.contains(lat, lng)

    # ------------------------------------------------------------ read endpoints
    def health(self, q):
        c = self.con()
        n = c.execute('SELECT count(*) FROM codes').fetchone()[0]
        return 200, {'status': 'ok', 'country': COUNTRY, 'codes': n, 'exported': store.meta(c, 'exported'),
                     'issuing': bool(self.cfg.issue_keys)}

    def info(self, q):
        c = self.con()
        reg = self.register()
        by_zone, by_status = self.counts()
        return 200, {
            'country': COUNTRY, 'name': COUNTRY_NAME, 'spec': SPEC, 'engine': store.meta(c, 'engine'),
            'exported': store.meta(c, 'exported'), 'codes': sum(by_zone.values()), 'byStatus': by_status,
            'zones': len(self._zones), 'areas': len(reg.areas), 'names': len(reg.names), 'aliases': len(reg.aliases),
            'forms': {'remembered': 'Moyamba 15727', 'written': 'Moyamba 157 27', 'machine': 'SL-03663-15727',
                      'spot': '5H68+3V Moyamba', 'official': 'FQQ6+9G Freetown'},
            'towns': [t['name'] for t in reg.towns],
            'licences': {'data': 'ODbL-1.0', 'code': 'Apache-2.0', 'documents': 'CC-BY-4.0'},
            'credit': X.CREDIT, 'creditUrl': X.CREDIT_URL,
            'issuing': bool(self.cfg.issue_keys), 'issuePerDay': self.cfg.issue_per_day if self.cfg.issue_keys else 0,
        }

    def get_code(self, machine):
        reg = self.register()
        try:
            a, n, chk, st, un = reg.decode_machine(machine)
        except ValueError as e:
            raise ApiError(404, 'code_not_found', f'{_cap(str(e))}.')
        if chk is not None and chk != X.E.check_digit(a['nameId'], n):
            raise ApiError(422, 'check_mismatch', 'The check digit does not match: a digit is wrong or two are swapped.')
        row = self.con().execute('SELECT * FROM codes WHERE zone = ? AND number = ?', (a['zone'], n)).fetchone()
        if row is None:
            f = X.forms(a, n)
            raise ApiError(404, 'code_not_found', f"No compound has {f['machine']} yet (the number is in a block of {a['name']}, {X.place_line(a)}).")
        out = self.card(row)
        if st:
            out['structure'] = st
        if un:
            out['unit'] = un
        return 200, out

    def find(self, q):
        text = _one(q, 'q').strip()
        if not text:
            raise bad('missing_q', 'Give the code to find in q, for example ?q=Moyamba 157 27.')
        if len(text) > 200:
            raise bad('bad_q', 'q is too long.')
        reg = self.register()
        c = self.con()
        if X.looks_machine(text):
            _, card = self.get_code(text)
            return 200, {'query': text, 'kind': 'machine', 'codes': [card]}
        if X.looks_spot(text):
            try:
                lat, lng, full, _ = reg.spot_point(text)
            except ValueError as e:
                raise ApiError(422, 'bad_spot', f'{_cap(str(e))}.')
            short = X.spot(lat, lng)['short']
            # In Freetown City Council's area the property's Plus Code is the official
            # address: every compound recorded with it answers.
            rows = c.execute('SELECT * FROM codes WHERE fcc_address <> \'\' AND fcc_address = ? AND status <> \'retired\' ORDER BY machine',
                             (short,)).fetchall()
            if rows:
                rows = sorted(rows, key=lambda r: (geo.ground_m(lat, lng, r['lat'], r['lng']), r['machine']))[:20]
                return 200, {'query': text, 'kind': 'official', 'point': {'lat': lat, 'lng': lng, 'plusCode': full},
                             'codes': [self.card(r, round(geo.ground_m(lat, lng, r['lat'], r['lng']), 1)) for r in rows]}
            row, d = self.code_at(lat, lng, X.SPOT_M)
            if row is None:
                raise ApiError(404, 'code_not_found', f'The spot {text} is not on a compound with a code. '
                               f'GET /v1/at?lat={lat:.6f}&lng={lng:.6f} shows the area there.')
            return 200, {'query': text, 'kind': 'spot', 'point': {'lat': lat, 'lng': lng, 'plusCode': full},
                         'codes': [self.card(row, round(d, 1))]}
        try:
            a, n, d = reg.decode_text(text)
        except ValueError as e:
            msg = str(e)
            if 'check digit' in msg:
                raise ApiError(422, 'check_mismatch', 'The check digit does not match: a digit is wrong or two are swapped.')
            raise ApiError(404, 'code_not_found', f'No compound in {COUNTRY_NAME} has the code {text} ({msg}). '
                           'Check the place name and the number on the plate.')
        row = c.execute('SELECT * FROM codes WHERE zone = ? AND number = ?', (a['zone'], n)).fetchone()
        if row is None:
            raise ApiError(404, 'code_not_found', f"No compound has {a['name']} {n} yet (the number is in a block of "
                           f"{a['name']}, {X.place_line(a)}). Check the number on the plate.")
        if row['status'] == 'retired':
            raise ApiError(410, 'code_retired', f"{row['home']} was retired: there is no compound there any more. A retired number is never reused.")
        out = self.card(row)
        if d.get('structure'):
            out['structure'] = d['structure']
        if d.get('unit'):
            out['unit'] = d['unit']
        return 200, {'query': text, 'kind': 'remembered', 'codes': [out]}

    def at(self, q):
        lat, lng = _point(q)
        if not self.in_country(lat, lng):
            raise ApiError(422, 'outside_country', f'That point is outside {COUNTRY_NAME}.')
        reg = self.register()
        row, d = self.code_at(lat, lng, X.AT_M)
        a = reg.place_for(lat, lng)
        area = self.area_json(a)
        if row is not None:
            return 200, {'status': 'found', 'distanceM': geo.round_half_away(d), 'code': self.card(row), 'area': area}
        return 200, {'status': 'none', 'area': area, 'spot': X.spot(lat, lng)}

    def near(self, q):
        lat, lng = _point(q)
        radius = _num(q, 'radius', 100.0)
        if not 0 < radius <= NEAR_MAX_M:
            raise bad('bad_radius', f'radius is in metres, more than 0 and at most {NEAR_MAX_M:.0f}.')
        limit = int(_num(q, 'limit', 20))
        if not 1 <= limit <= NEAR_MAX_RESULTS:
            raise bad('bad_limit', f'limit is from 1 to {NEAR_MAX_RESULTS}.')
        self.register()
        hits = []
        for r in self.candidates(lat, lng, radius):
            d = geo.ground_m(lat, lng, r['lat'], r['lng'])
            if d <= radius:
                hits.append((d, r['machine'], r))
        hits.sort(key=lambda h: (h[0], h[1]))
        return 200, {'point': {'lat': lat, 'lng': lng}, 'radiusM': radius, 'count': min(len(hits), limit), 'total': len(hits),
                     'codes': [self.card(r, round(d, 1)) for d, _, r in hits[:limit]]}

    def verify(self, q):
        code = _one(q, 'code').strip()
        if not code:
            raise bad('missing_code', 'Give the machine code in code, for example ?code=SL-03663-15727.')
        reg = self.register()
        out = {'code': code, 'syntax': X.looks_machine(code), 'valid': False, 'issued': False}
        if not out['syntax']:
            out['reason'] = 'not a machine code: SL-, the area in 5 digits, -, the number in 3 to 5 digits'
            return 200, out
        try:
            a, n, chk, _, _ = reg.decode_machine(code)
        except ValueError as e:
            out['reason'] = str(e)
            return 200, out
        expect = X.E.check_digit(a['nameId'], n)
        out.update({'machine': f"{COUNTRY}-{a['zone']}-{n}", 'check': expect, 'area': a['zone']})
        if chk is not None and chk != expect:
            out.update(checkGiven=chk, reason='the check digit does not match: a digit is wrong or two are swapped')
            return 200, out
        out['valid'] = True
        row = self.con().execute('SELECT machine, home, status FROM codes WHERE zone = ? AND number = ?', (a['zone'], n)).fetchone()
        if row:
            out.update(issued=True, status=row['status'], remembered=row['home'])
        else:
            out['reason'] = 'a valid number of the area, not issued yet'
        return 200, out

    def spot(self, q):
        lat, lng = _point(q)
        self.register()
        return 200, {'lat': lat, 'lng': lng, **X.spot(lat, lng), 'inCountry': self.in_country(lat, lng)}

    def spot_decode(self, q):
        code = _one(q, 'code').strip()
        if not code:
            raise bad('missing_code', 'Give the Plus Code in code, for example ?code=FQQ6+9G Freetown.')
        if not X.looks_spot(code):
            raise ApiError(422, 'bad_spot', f'{code!r} is not a Plus Code.')
        try:
            lat, lng, full, a = self.register().spot_point(code)
        except ValueError as e:
            raise ApiError(422, 'bad_spot', f'{_cap(str(e))}.')
        return 200, {'code': code, 'full': full, 'lat': lat, 'lng': lng,
                     'bbox': [a['west'], a['south'], a['east'], a['north']], 'inCountry': self.in_country(lat, lng)}

    def zones(self, q):
        self.register()
        return 200, {'zones': [self.zone_json(k) for k in sorted(self._zones)]}

    def zone(self, key):
        self.register()
        return 200, self.zone_json(key.upper(), full=True)

    def zone_codes(self, key, q):
        self.register()
        key = key.upper()
        self.zone_json(key)
        after = _one(q, 'after').strip().upper()
        limit = int(_num(q, 'limit', 100))
        if not 1 <= limit <= PAGE_MAX:
            raise bad('bad_limit', f'limit is from 1 to {PAGE_MAX}.')
        rows = self.con().execute('SELECT * FROM codes WHERE tile = ? AND machine > ? ORDER BY machine LIMIT ?', (key, after, limit + 1)).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        return 200, {'zone': key, 'count': len(rows), 'next': rows[-1]['machine'] if more else None,
                     'codes': [self.card(r) for r in rows]}

    def area(self, ident):
        reg = self.register()
        a = reg.area(ident)
        if a is None:
            raise ApiError(404, 'area_not_found', f'There is no area {ident}. Areas are numbered 00001 to {len(reg.areas):05d}.')
        return 200, self.area_json(a, full=True)

    def areas(self, q):
        name = _one(q, 'name').strip()
        if not name:
            raise bad('missing_name', 'Give a plate or official name in name, for example ?name=Moyamba.')
        reg = self.register()
        key = reg.resolve(name)
        found = list(reg.families.get(key, [])) if key else []
        k = X.name_key(name)
        for r in self.con().execute('SELECT idx FROM areas WHERE official_key = ? ORDER BY idx', (k,)):
            a = reg.area(r['idx'])
            if a not in found:
                found.append(a)
        if not found:
            raise ApiError(404, 'area_not_found', f'No area of {COUNTRY_NAME} is called {name!r}.')
        return 200, {'query': name, 'nameKey': key, 'areas': [self.area_json(a, full=True) for a in found]}

    # ------------------------------------------------------------ writes
    def key_id(self, headers):
        if not self.cfg.issue_keys:
            raise ApiError(403, 'read_only', 'This server is read-only. Only the issuer designated for the country issues codes '
                           '(see server/README.md, "One issuer per country").')
        auth = headers.get('Authorization', '')
        m = re.match(r'^Bearer\s+(\S+)$', auth)
        if not m or not any(hmac.compare_digest(m.group(1), k) for k in self.cfg.issue_keys):
            raise ApiError(401, 'unauthorized', 'A valid issuing key is needed: Authorization: Bearer <key>.')
        return hashlib.sha256(m.group(1).encode()).hexdigest()[:16]

    def issue(self, body, headers):
        kid = self.key_id(headers)
        lat, lng = _body_point(body)
        outline, of = body.get('outline'), body.get('of')
        if of is not None and not isinstance(of, str):
            raise bad('bad_of', 'of is the machine code of the compound the new door belongs to.')
        if outline is not None:
            if not isinstance(outline, list) or not all(isinstance(p, list) and len(p) == 2 and all(_isnum(v) for v in p) for p in outline):
                raise bad('bad_outline', 'outline is a list of [lng, lat] points.')
        of = (of or '').strip()
        with self.write_lock:
            c = self.con()
            c.execute('BEGIN IMMEDIATE')
            try:
                out = self._issue(c, kid, lat, lng, outline, of)
                c.execute('COMMIT')
            except BaseException:
                c.execute('ROLLBACK')
                raise
        self.forget_counts()
        return 201, out

    def _issue(self, c, kid, lat, lng, outline, of):
        now = time.time()
        n = c.execute('SELECT count(*) FROM issue_log WHERE key_id = ? AND at >= ?', (kid, now - 86400)).fetchone()[0]
        if n >= self.cfg.issue_per_day:
            raise ApiError(429, 'issue_limit', f"This key has issued {n} code{'' if n == 1 else 's'} in the last 24 hours, its daily limit. Try again later.")
        if self._reg_rev != store.meta(c, 'blocks_rev', '0'):
            self.register()
        reg = self._reg
        if not self.in_country(lat, lng):
            raise ApiError(422, 'outside_country', f'That point is outside {COUNTRY_NAME}, so it cannot have an N-Ways {COUNTRY_NAME} code.')
        ring, area_m2 = None, 0.0
        if not of:
            row, _ = self.code_at(lat, lng, X.EXISTS_M)
            if row is not None:
                raise ApiError(409, 'code_exists', f"This compound already has its code: {row['home']}.", card=self.card(row))
            if outline is not None and len(outline) >= 3:
                ring = geo.open_ring(outline)
                area_m2 = geo.ring_area_m2(ring)
                if len(ring) < 3 or area_m2 < X.MIN_AREA_M2 or area_m2 > X.MAX_AREA_M2:
                    raise ApiError(422, 'bad_outline', f"That outline is {area_m2:.0f} m², but a compound's is between 6 m² and 2 ha.")
                for r in self.candidates(lat, lng, 250.0):
                    if r['outline'] and r['status'] != 'retired':
                        other = geo.open_ring(json.loads(r['outline']))
                        if geo.overlap_m2(ring, other) > 0.5 * min(area_m2, geo.ring_area_m2(other)):
                            raise ApiError(409, 'code_exists', f"This compound already has its code: {r['home']}.", card=self.card(r))
        if of:
            o = self.by_code(of)
            if o is None:
                raise ApiError(404, 'code_not_found', f'There is no code {of} to add a door to.')
            if geo.door_m(o['lat'], o['lng'], lat, lng) > X.DOOR_M:
                raise ApiError(422, 'too_far', f"That door is more than 80 m from {o['home']}. Stand at the door and try again.")
            a = reg.by_zone[o['zone']]
        else:
            a = reg.place_for(lat, lng)
        if a is None:
            raise ApiError(422, 'no_area', 'There is no area for this point.')
        # Work on a copy of the area: its blocks change only if the issue commits.
        # The register is current: it was reloaded above if another writer added a block.
        work = dict(a, blocks=list(a['blocks']))
        saved = reg.families[a['key']]
        reg.families[a['key']] = [work if x['zone'] == a['zone'] else x for x in saved]
        try:
            issued = [(r[0], r[1], r[2]) for r in c.execute('SELECT number, anchor_lat, anchor_lng FROM codes WHERE zone = ?', (a['zone'],))]
            num, block = reg.insert(work, issued, lat, lng)
        finally:
            reg.families[a['key']] = saved
        if num is None:
            raise ApiError(409, 'name_full', f"{a['name']} has used every number of its name. Its council chooses a qualifier before more compounds there get a code.")
        f = X.forms(a, num)
        sp = X.spot(lat, lng)
        lat_s, lng_s = f'{lat:.7f}', f'{lng:.7f}'
        floor = round(area_m2 * 10) / 10 if ring else 0.0
        vals = {
            'machine': f['machine'], 'home': f['home'], 'written': f['written'], 'zone': a['zone'],
            'official_name': a['officialName'], 'district': a['district'], 'number': num, 'check_digit': f['check'],
            'status': 'provisional', 'issued': 'on-demand', 'issued_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(now)),
            'entrance_lat': lat_s, 'entrance_lng': lng_s, 'entrance_kind': 'door' if of else 'centre',
            'plus_code': sp['short'], 'fcc_address': sp['short'] if a['fcc'] else '',
            'class': 'residential.house' if ring else '', 'use': 'residential', 'kind': 'door' if of else 'building',
            'structures': '1' if ring else '0', 'floor_area_m2': f'{floor:.1f}', 'rule': '', 'estate': '',
            'tile': a['tile'], 'name_id': a['nameId'], 'lat': float(lat_s), 'lng': float(lng_s),
            'anchor_lat': lat, 'anchor_lng': lng, 'outline': json.dumps([list(p) for p in ring]) if ring else None,
            'cell': store.cell_of(float(lat_s), float(lng_s)),
        }
        cols = list(vals)
        try:
            cur = c.execute('INSERT INTO codes (%s) VALUES (%s)' % (', '.join(cols), ','.join('?' * len(cols))), [vals[k] for k in cols])
        except sqlite3.IntegrityError:
            raise ApiError(409, 'busy', 'Another code was issued at the same moment. Try again.')
        if self.spatial == 'rtree':
            c.execute('INSERT INTO codes_rtree VALUES (?, ?, ?, ?, ?)', (cur.lastrowid, vals['lat'], vals['lat'], vals['lng'], vals['lng']))
        if block:
            c.execute('UPDATE areas SET blocks = ? WHERE zone = ?', (X.format_blocks(work['blocks']), a['zone']))
            store.set_meta(c, 'blocks_rev', int(store.meta(c, 'blocks_rev', '0')) + 1)
        c.execute('INSERT INTO issue_log (key_id, machine, at) VALUES (?, ?, ?)', (kid, f['machine'], now))
        _event(c, kid, f['machine'], 'issue', {'lat': lat, 'lng': lng, 'of': of or None, 'block': list(block) if block else None})
        store.set_meta(c, 'dirty', 1)
        row = c.execute('SELECT * FROM codes WHERE machine = ?', (f['machine'],)).fetchone()
        if block:
            self._reg = None
            self.register()
        out = self.card(row)
        if block:
            out['newBlock'] = {'lo': block[0], 'hi': block[1]}
        return out

    def patch(self, machine, body, headers):
        kid = self.key_id(headers)
        status, ent = body.get('status'), body.get('entrance')
        if status is None and ent is None:
            raise bad('nothing_to_change', 'Give status (confirmed, provisional or retired) or entrance {lat, lng}.')
        if status is not None and status not in STATUSES:
            raise bad('bad_status', 'status is provisional, confirmed or retired.')
        if ent is not None:
            if not isinstance(ent, dict):
                raise bad('bad_entrance', 'entrance is {"lat": ..., "lng": ...}.')
            elat, elng = _body_point(ent)
        self.register()
        with self.write_lock:
            c = self.con()
            c.execute('BEGIN IMMEDIATE')
            try:
                row = self.by_code(machine)
                if row is None:
                    raise ApiError(404, 'code_not_found', f'There is no code {machine}.')
                if row['status'] == 'retired':
                    raise ApiError(409, 'code_retired', f"{row['home']} is retired; a retired code never changes and its number is never reused.")
                changes = {}
                if status is not None and status != row['status']:
                    changes['status'] = status
                if ent is not None:
                    if geo.door_m(row['lat'], row['lng'], elat, elng) > X.DOOR_M:
                        raise ApiError(422, 'too_far', f"The new entrance is more than 80 m from {row['home']}.")
                    if not self.in_country(elat, elng):
                        raise ApiError(422, 'outside_country', f'That point is outside {COUNTRY_NAME}.')
                    la, ln = f'{elat:.7f}', f'{elng:.7f}'
                    changes.update(entrance_lat=la, entrance_lng=ln, entrance_kind='gate', lat=float(la), lng=float(ln),
                                   plus_code=X.spot(float(la), float(ln))['short'], cell=store.cell_of(float(la), float(ln)))
                if changes:
                    c.execute('UPDATE codes SET %s WHERE id = ?' % ', '.join(f'{k} = ?' for k in changes), (*changes.values(), row['id']))
                    if 'lat' in changes and self.spatial == 'rtree':
                        c.execute('UPDATE codes_rtree SET min_lat = ?, max_lat = ?, min_lng = ?, max_lng = ? WHERE id = ?',
                                  (changes['lat'], changes['lat'], changes['lng'], changes['lng'], row['id']))
                    _event(c, kid, row['machine'], 'change', {k: v for k, v in changes.items() if k in ('status', 'entrance_lat', 'entrance_lng')})
                    store.set_meta(c, 'dirty', 1)
                c.execute('COMMIT')
            except BaseException:
                c.execute('ROLLBACK')
                raise
        self.forget_counts()
        return 200, self.card(self.by_machine(row['machine']))


def _event(c, kid, machine, action, detail):
    c.execute('INSERT INTO events (at, key_id, machine, action, detail) VALUES (?, ?, ?, ?, ?)',
              (time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), kid, machine, action, json.dumps(detail, sort_keys=True)))


def _steps(a, b):
    out, x = [], math.floor(a / store.CELL_DEG) * store.CELL_DEG
    while x <= b + 1e-12:
        out.append(x + store.CELL_DEG / 2)
        x += store.CELL_DEG
    return out


def _cap(s):
    return s[:1].upper() + s[1:]


def _one(q, k):
    v = q.get(k)
    return v[0] if v else ''


def _isnum(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _num(q, k, default):
    v = _one(q, k).strip()
    if not v:
        return default
    try:
        x = float(v)
    except ValueError:
        raise bad(f'bad_{k}', f'{k} must be a number.')
    if not math.isfinite(x):
        raise bad(f'bad_{k}', f'{k} must be a number.')
    return x


def _point(q):
    if not _one(q, 'lat') or not _one(q, 'lng'):
        raise bad('missing_point', 'Give the point as lat and lng in decimal degrees (WGS 84).')
    lat, lng = _num(q, 'lat', None), _num(q, 'lng', None)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise bad('bad_point', 'lat is from -90 to 90 and lng from -180 to 180.')
    return lat, lng


def _body_point(b):
    lat, lng = b.get('lat'), b.get('lng')
    if not _isnum(lat) or not _isnum(lng):
        raise bad('missing_point', 'Give lat and lng as numbers in decimal degrees (WGS 84).')
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise bad('bad_point', 'lat is from -90 to 90 and lng from -180 to 180.')
    return float(lat), float(lng)


# ---------------------------------------------------------------- HTTP
ROUTES = [
    ('GET', re.compile(r'^/v1/health$'), lambda s, m, q, b, h: s.health(q)),
    ('GET', re.compile(r'^/v1/info$'), lambda s, m, q, b, h: s.info(q)),
    ('GET', re.compile(r'^/v1/find$'), lambda s, m, q, b, h: s.find(q)),
    ('GET', re.compile(r'^/v1/at$'), lambda s, m, q, b, h: s.at(q)),
    ('GET', re.compile(r'^/v1/near$'), lambda s, m, q, b, h: s.near(q)),
    ('GET', re.compile(r'^/v1/verify$'), lambda s, m, q, b, h: s.verify(q)),
    ('GET', re.compile(r'^/v1/spot$'), lambda s, m, q, b, h: s.spot(q)),
    ('GET', re.compile(r'^/v1/spot/decode$'), lambda s, m, q, b, h: s.spot_decode(q)),
    ('GET', re.compile(r'^/v1/zones$'), lambda s, m, q, b, h: s.zones(q)),
    ('GET', re.compile(r'^/v1/zones/([^/]+)$'), lambda s, m, q, b, h: s.zone(m.group(1))),
    ('GET', re.compile(r'^/v1/zones/([^/]+)/codes$'), lambda s, m, q, b, h: s.zone_codes(m.group(1), q)),
    ('GET', re.compile(r'^/v1/areas$'), lambda s, m, q, b, h: s.areas(q)),
    ('GET', re.compile(r'^/v1/areas/([^/]+)$'), lambda s, m, q, b, h: s.area(m.group(1))),
    ('GET', re.compile(r'^/v1/codes/([^/]+)$'), lambda s, m, q, b, h: s.get_code(m.group(1))),
    ('POST', re.compile(r'^/v1/codes$'), lambda s, m, q, b, h: s.issue(b, h)),
    ('PATCH', re.compile(r'^/v1/codes/([^/]+)$'), lambda s, m, q, b, h: s.patch(m.group(1), b, h)),
]


def make_handler(service):
    cfg = service.cfg

    class Handler(BaseHTTPRequestHandler):
        server_version = 'N-Ways-Registry'
        sys_version = ''
        protocol_version = 'HTTP/1.1'

        def log_message(self, fmt, *args):
            pass

        def _cors(self):
            origin = self.headers.get('Origin')
            if not origin or not cfg.cors_origins:
                return {}
            if '*' in cfg.cors_origins:
                return {'Access-Control-Allow-Origin': '*'}
            if origin in cfg.cors_origins:
                return {'Access-Control-Allow-Origin': origin, 'Vary': 'Origin'}
            return {}

        def _send(self, status, body, extra=None):
            data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store' if self.command != 'GET' else 'public, max-age=60')
            self.send_header('X-Content-Type-Options', 'nosniff')
            for k, v in {**self._cors(), **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)
            if not cfg.log_requests:
                return
            t = time.time() - self._t0
            print(f'{self.command} {self.path[:200]} {status} {t * 1000:.0f}ms', flush=True)

        def _handle(self):
            self._t0 = time.time()
            try:
                u = urlsplit(self.path)
                path = unquote(u.path)
                q = parse_qs(u.query, keep_blank_values=True)
                method = 'GET' if self.command == 'HEAD' else self.command
                body = {}
                if method in ('POST', 'PATCH'):
                    n = int(self.headers.get('Content-Length') or 0)
                    if n > MAX_BODY:
                        raise ApiError(413, 'too_large', f'The body is over {MAX_BODY // 1024} KB.')
                    raw = self.rfile.read(n) if n else b''
                    try:
                        body = json.loads(raw or b'{}')
                    except ValueError:
                        raise bad('bad_json', 'The body is not valid JSON.')
                    if not isinstance(body, dict):
                        raise bad('bad_json', 'The body is a JSON object.')
                allowed = []
                for meth, rx, fn in ROUTES:
                    m = rx.match(path)
                    if not m:
                        continue
                    if meth != method:
                        allowed.append(meth)
                        continue
                    status, out = fn(service, m, q, body, self.headers)
                    return self._send(status, out)
                if allowed:
                    raise ApiError(405, 'method_not_allowed', f"{self.command} is not allowed here; use {', '.join(sorted(set(allowed)))}.")
                raise ApiError(404, 'not_found', f'There is no endpoint {path}. GET /v1/info describes the API.')
            except ApiError as e:
                extra = {'WWW-Authenticate': 'Bearer'} if e.status == 401 else None
                return self._send(e.status, e.body(), extra)
            except Exception as e:  # noqa: BLE001  an unexpected fault is logged and answered as JSON
                import traceback
                traceback.print_exc()
                return self._send(500, {'error': {'code': 'internal', 'message': f'Internal error: {type(e).__name__}.'}})

        do_GET = do_HEAD = do_POST = do_PATCH = _handle

        def do_PUT(self):
            self._handle()

        def do_DELETE(self):
            self._handle()

        def do_OPTIONS(self):
            self._t0 = time.time()
            h = self._cors()
            if h:
                h.update({'Access-Control-Allow-Methods': 'GET, POST, PATCH, OPTIONS',
                          'Access-Control-Allow-Headers': 'Authorization, Content-Type', 'Access-Control-Max-Age': '600'})
            self.send_response(204)
            for k, v in h.items():
                self.send_header(k, v)
            self.send_header('Content-Length', '0')
            self.end_headers()

    return Handler


def serve(cfg):
    service = Service(cfg)
    httpd = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(service))
    httpd.daemon_threads = True
    mode = f'issuing with {len(cfg.issue_keys)} key(s), {cfg.issue_per_day} per key per day' if cfg.issue_keys else 'read-only'
    print(f'N-Ways {COUNTRY_NAME} registry: {cfg.db} on http://{cfg.host}:{cfg.port}/v1 ({mode})', flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return service

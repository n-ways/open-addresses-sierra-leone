"""Tests of the registry server on a fixture registry: the real codes of one
zone (6CV8, Mania in Bonthe District) and the full frozen area table.

  python3 -m unittest discover -s server/tests -t .
"""
import gzip
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from server import api, engine as X, geo, store

HERE = os.path.dirname(os.path.abspath(__file__))
TESTDATA = os.path.join(os.path.dirname(HERE), 'testdata')
FIXTURE = os.path.join(TESTDATA, 'registry')
REGISTER = os.path.join(X.REPO, 'engine', 'data', 'register.json')
KEY = 'test-key-1'


def quiet(*a, **k):
    pass


class Server:
    """A server on an ephemeral port over a fresh import of the fixture."""

    def __init__(self, keys=(KEY,), per_day=1000):
        self.dir = tempfile.mkdtemp(prefix='sl-server-')
        self.db = os.path.join(self.dir, 'a.sqlite')
        store.import_registry(FIXTURE, self.db, REGISTER, log=quiet)
        self.cfg = api.Config(self.db, port=0, host='127.0.0.1', issue_keys=list(keys), issue_per_day=per_day, cors_origins=['*'], log_requests=False)
        self.service = api.Service(self.cfg)
        self.httpd = api.ThreadingHTTPServer(('127.0.0.1', 0), api.make_handler(self.service))
        self.base = f'http://127.0.0.1:{self.httpd.server_address[1]}'
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def call(self, method, path, body=None, key=KEY, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        if data is not None:
            req.add_header('Content-Type', 'application/json')
        if key:
            req.add_header('Authorization', f'Bearer {key}')
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read() or b'null'), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b'null'), dict(e.headers)

    def get(self, path):
        s, b, _ = self.call('GET', path, key=None)
        return s, b

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.dir)


def q(s):
    return urllib.request.quote(s, safe='')


def fixture_rows():
    import csv
    with gzip.open(os.path.join(FIXTURE, '6CV8.csv.gz'), 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- import / export
class ImportExport(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='sl-import-')

    def tearDown(self):
        shutil.rmtree(self.dir)

    def copy_fixture(self):
        d = os.path.join(self.dir, 'registry')
        shutil.copytree(FIXTURE, d)
        return d

    def test_round_trip_is_byte_identical(self):
        db = os.path.join(self.dir, 'a.sqlite')
        self.assertEqual(store.import_registry(FIXTURE, db, REGISTER, log=quiet), 125)
        out = os.path.join(self.dir, 'out')
        store.export_registry(store.connect(db), out, log=quiet)
        for name in ('6CV8.csv', 'areas.csv'):
            with gzip.open(os.path.join(FIXTURE, name + '.gz')) as a, gzip.open(os.path.join(out, name + '.gz')) as b:
                self.assertEqual(a.read(), b.read(), name)
        with open(os.path.join(FIXTURE, 'MANIFEST.json'), 'rb') as a, open(os.path.join(out, 'MANIFEST.json'), 'rb') as b:
            self.assertEqual(a.read(), b.read())
        # gzip -n: the same text gives the same bytes
        out2 = os.path.join(self.dir, 'out2')
        store.export_registry(store.connect(db), out2, log=quiet)
        with open(os.path.join(out, '6CV8.csv.gz'), 'rb') as a, open(os.path.join(out2, '6CV8.csv.gz'), 'rb') as b:
            self.assertEqual(a.read(), b.read())

    def test_import_twice(self):
        db = os.path.join(self.dir, 'a.sqlite')
        store.import_registry(FIXTURE, db, REGISTER, log=quiet)
        store.import_registry(FIXTURE, db, REGISTER, log=quiet)
        self.assertEqual(store.connect(db).execute('SELECT count(*) FROM codes').fetchone()[0], 125)

    def test_refuses_a_changed_file(self):
        d = self.copy_fixture()
        p = os.path.join(d, '6CV8.csv.gz')
        with gzip.open(p, 'rb') as f:
            text = f.read()
        with gzip.open(p, 'wb') as f:
            f.write(text.replace(b'provisional', b'confirmed', 1))
        db = os.path.join(self.dir, 'a.sqlite')
        with self.assertRaisesRegex(store.RegistryError, 'SHA-256'):
            store.import_registry(d, db, REGISTER, log=quiet)
        self.assertFalse(os.path.exists(db))

    def test_refuses_a_wrong_count(self):
        d = self.copy_fixture()
        p = os.path.join(d, 'MANIFEST.json')
        m = json.load(open(p))
        m['byTile']['6CV8'] = 124
        json.dump(m, open(p, 'w'))
        with self.assertRaisesRegex(store.RegistryError, 'add up'):
            store.import_registry(d, os.path.join(self.dir, 'a.sqlite'), REGISTER, log=quiet)

    def test_refuses_extra_and_missing_files(self):
        d = self.copy_fixture()
        shutil.copy(os.path.join(d, '6CV8.csv.gz'), os.path.join(d, '6CW8.csv.gz'))
        with self.assertRaisesRegex(store.RegistryError, 'not in the manifest'):
            store.import_registry(d, os.path.join(self.dir, 'a.sqlite'), REGISTER, log=quiet)
        os.remove(os.path.join(d, '6CW8.csv.gz'))
        os.remove(os.path.join(d, 'MANIFEST.json'))
        with self.assertRaisesRegex(store.RegistryError, 'missing'):
            store.import_registry(d, os.path.join(self.dir, 'a.sqlite'), REGISTER, log=quiet)

    def test_csv_fields_as_published(self):
        self.assertEqual(store.csv_line(['a', '', 'b,c', 'say "x"', ' lead']), 'a,,"b,c","say ""x"""," lead"\n')


# ---------------------------------------------------------------- read endpoints
class Reads(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server(keys=())
        cls.rows = fixture_rows()

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def test_health_and_info(self):
        s, b = self.s.get('/v1/health')
        self.assertEqual((s, b['status'], b['country'], b['codes'], b['issuing']), (200, 'ok', 'SL', 125, False))
        s, b = self.s.get('/v1/info')
        self.assertEqual((s, b['areas'], b['zones'], b['codes']), (200, 5184, 13, 125))
        self.assertEqual(b['licences']['data'], 'ODbL-1.0')

    def test_card_has_every_registry_column(self):
        r = self.rows[0]
        s, b = self.s.get('/v1/codes/' + r['machine'])
        self.assertEqual(s, 200)
        self.assertEqual(b['record'], r)
        self.assertEqual(b['remembered'], r['home'])
        self.assertEqual(b['spot']['short'], r['plus_code'])
        self.assertEqual(b['check'], int(r['check']))
        self.assertEqual(b['area']['id'], r['zone'])
        self.assertEqual(b['zone']['key'], '6CV8')

    def test_card_errors(self):
        self.assertEqual(self.s.get('/v1/codes/SL-03002-1002')[1]['error']['code'], 'code_not_found')    # in the block, not issued
        self.assertEqual(self.s.get('/v1/codes/SL-03002-2001')[0], 404)                                   # outside the area's block
        self.assertEqual(self.s.get('/v1/codes/SL-99999-1001')[0], 404)
        self.assertEqual(self.s.get('/v1/codes/nonsense')[0], 404)
        s, b = self.s.get('/v1/codes/' + q('SL-03002-1001·9'))
        self.assertEqual((s, b['error']['code']), (422, 'check_mismatch'))

    def test_find_remembered_any_spacing_case_or_accents(self):
        r = self.rows[0]   # Mania 1001
        for text in ('Mania 1001', 'MANIA 10 01', 'mánia 1001', '  mania   10 01 ', 'Mania1001', 'Mania 10 01 · 2', 'Mania 1001, Bonthe',
                     'Mania 1001.2/3'):
            s, b = self.s.get('/v1/find?q=' + q(text))
            self.assertEqual(s, 200, text)
            self.assertEqual(b['codes'][0]['machine'], r['machine'], text)
            self.assertEqual(b['kind'], 'remembered')

    def test_find_machine_and_spot(self):
        r = self.rows[3]
        s, b = self.s.get('/v1/find?q=' + q(r['machine'].lower()))
        self.assertEqual((s, b['kind'], b['codes'][0]['machine']), (200, 'machine', r['machine']))
        s, b = self.s.get('/v1/find?q=' + q(r['plus_code']))
        self.assertEqual((s, b['kind']), (200, 'spot'))
        self.assertLessEqual(b['codes'][0]['distanceM'], X.SPOT_M)   # the compound nearest the cell's centre

    def test_find_errors(self):
        s, b = self.s.get('/v1/find?q=' + q('Mania 10 01 · 5'))
        self.assertEqual((s, b['error']['code']), (422, 'check_mismatch'))
        s, b = self.s.get('/v1/find?q=' + q('SL-03002-1001·5'))
        self.assertEqual((s, b['error']['code']), (422, 'check_mismatch'))
        self.assertEqual(self.s.get('/v1/find?q=' + q('Mania 1002'))[0], 404)          # a free number in the block
        self.assertEqual(self.s.get('/v1/find?q=' + q('Nowhereville 1001'))[0], 404)
        self.assertEqual(self.s.get('/v1/find?q=' + q('FQQ6+9G Nowhere'))[0], 422)
        self.assertEqual(self.s.get('/v1/find?q=' + q('FQQ6+9G Freetown'))[0], 404)     # no code there in the fixture
        self.assertEqual(self.s.get('/v1/find?q=')[1]['error']['code'], 'missing_q')

    def test_at(self):
        r = self.rows[5]
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        s, b = self.s.get(f'/v1/at?lat={lat + 0.00005}&lng={lng}')   # about 5.5 m north
        self.assertEqual((s, b['status'], b['code']['machine'], b['distanceM']), (200, 'found', r['machine'], 6))
        s, b = self.s.get('/v1/at?lat=7.70&lng=-13.00')
        self.assertEqual((s, b['status']), (200, 'none'))
        self.assertIn('id', b['area'])
        self.assertEqual(self.s.get('/v1/at?lat=8.0&lng=-14.5')[1]['error']['code'], 'outside_country')
        self.assertEqual(self.s.get('/v1/at?lat=x&lng=1')[1]['error']['code'], 'bad_lat')
        self.assertEqual(self.s.get('/v1/at?lat=8')[1]['error']['code'], 'missing_point')

    def test_near(self):
        s, b = self.s.get('/v1/near?lat=7.6258546&lng=-13.0482777&radius=300&limit=5')
        self.assertEqual((s, b['count']), (200, 5))
        ds = [c['distanceM'] for c in b['codes']]
        self.assertEqual(ds, sorted(ds))
        self.assertTrue(all(d <= 300 for d in ds))
        self.assertEqual(self.s.get('/v1/near?lat=7.62&lng=-13.04&radius=501')[1]['error']['code'], 'bad_radius')
        self.assertEqual(self.s.get('/v1/near?lat=7.62&lng=-13.04&limit=101')[1]['error']['code'], 'bad_limit')

    def test_verify(self):
        s, b = self.s.get('/v1/verify?code=SL-03002-1001')
        self.assertEqual((s, b['valid'], b['issued'], b['check']), (200, True, True, 2))
        b = self.s.get('/v1/verify?code=' + q('SL-03002-1001·3'))[1]
        self.assertEqual((b['valid'], b['checkGiven']), (False, 3))
        b = self.s.get('/v1/verify?code=SL-03002-1002')[1]
        self.assertEqual((b['valid'], b['issued']), (True, False))
        b = self.s.get('/v1/verify?code=SL-03002-9001')[1]
        self.assertFalse(b['valid'])
        self.assertFalse(self.s.get('/v1/verify?code=hello')[1]['syntax'])
        self.assertEqual(self.s.get('/v1/verify')[0], 400)

    def test_spot(self):
        s, b = self.s.get('/v1/spot?lat=8.48842&lng=-13.23869')
        self.assertEqual((s, b['short'], b['full']), (200, 'FQQ6+9G Freetown', '6CW8FQQ6+9G'))
        s, b = self.s.get('/v1/spot/decode?code=' + q('FQR7+HX Freetown'))
        self.assertEqual((s, b['full']), (200, '6CW8FQR7+HX'))
        self.assertEqual(self.s.get('/v1/spot/decode?code=' + q('FQR7+HX'))[0], 422)
        self.assertEqual(self.s.get('/v1/spot/decode?code=hello')[0], 422)

    def test_zones_and_areas(self):
        s, b = self.s.get('/v1/zones')
        self.assertEqual((s, len(b['zones'])), (200, 13))
        s, b = self.s.get('/v1/zones/6cv8')
        self.assertEqual((s, b['codes'], [a['id'] for a in b['areaList']]), (200, 125, ['03002']))
        self.assertEqual(self.s.get('/v1/zones/XXXX')[0], 404)
        s, b = self.s.get('/v1/zones/6CV8/codes?limit=50')
        self.assertEqual((s, b['count']), (200, 50))
        s, b2 = self.s.get('/v1/zones/6CV8/codes?limit=100&after=' + b['next'])
        self.assertEqual((b2['count'], b2['next']), (75, None))
        self.assertGreater(b2['codes'][0]['machine'], b['codes'][-1]['machine'])
        self.assertEqual(self.s.get('/v1/zones/6CV8/codes?limit=0')[0], 400)
        s, b = self.s.get('/v1/areas/03002')
        self.assertEqual((s, b['codes'], b['blocks'][0]['lo']), (200, 125, 1000))
        self.assertEqual(self.s.get('/v1/areas/3002')[1]['id'], '03002')
        self.assertEqual(self.s.get('/v1/areas/99999')[0], 404)
        s, b = self.s.get('/v1/areas?name=' + q('MANIA'))
        self.assertEqual((s, len(b['areas'])), (200, 4))
        s, b = self.s.get('/v1/areas?name=' + q('Gbangbatoke Junction'))     # an official name, alias of its plate name
        self.assertEqual(s, 200)
        self.assertTrue(all(a['plateName'] != 'Gbangbatoke Junction' for a in b['areas']))
        self.assertEqual(self.s.get('/v1/areas?name=Nowhereville')[0], 404)
        self.assertEqual(self.s.get('/v1/areas')[0], 400)

    def test_http_errors(self):
        s, b = self.s.get('/v1/nothing')
        self.assertEqual((s, b['error']['code']), (404, 'not_found'))
        s, b, _ = self.s.call('DELETE', '/v1/codes/SL-03002-1001', key=None)
        self.assertEqual((s, b['error']['code']), (405, 'method_not_allowed'))
        s, b, _ = self.s.call('POST', '/v1/codes', {'lat': 7.62, 'lng': -13.04})
        self.assertEqual((s, b['error']['code']), (403, 'read_only'))
        s, b, h = self.s.call('GET', '/v1/health', key=None, headers={'Origin': 'https://example.org'})
        self.assertEqual(h.get('Access-Control-Allow-Origin'), '*')


# ---------------------------------------------------------------- issuing
class Border(unittest.TestCase):
    """The shipped outline and the 300 m border rule (server/geo.py, tools/border.py)."""

    def setUp(self):
        self.o = geo.Outline(os.path.join(X.REPO, 'engine', 'data', 'country.geojson'))

    def test_the_outline_is_small_and_keeps_the_tolerance_correct(self):
        path = os.path.join(X.REPO, 'engine', 'data', 'country.geojson')
        self.assertLess(os.path.getsize(path), 1 << 20)
        with open(path, encoding='utf-8') as f:
            props = json.load(f)['features'][0]['properties']
        self.assertEqual(props['iso'], 'SL')
        self.assertTrue(0 < props['deviationM'] <= 60, props)
        self.assertAlmostEqual(self.o.border_m + self.o.deviation_m, geo.BORDER_M)

    def test_points(self):
        self.assertTrue(self.o.contains(8.484, -13.234))                    # Freetown
        self.assertTrue(self.o.contains(7.5, -12.5))                        # Sherbro Island
        self.assertFalse(self.o.contains(9.5092, -13.7122))                 # in a neighbouring country
        self.assertFalse(self.o.contains(9.0, -10.58001))                   # 0.75 km over the eastern border
        self.assertTrue(self.o.contains(9.0, -10.58817))                    # 33 m over it
        self.assertEqual(self.o.outside_m(9.0, -10.5936), 0.0)
        self.assertTrue(700 < self.o.outside_m(9.0, -10.58001, 5000) < 800)
        self.assertEqual(self.o.outside_m(9.5092, -13.7122), float('inf'))  # beyond the reach asked


class Issue(unittest.TestCase):
    def setUp(self):
        self.s = Server()

    def tearDown(self):
        self.s.close()

    def post(self, body, key=KEY):
        s, b, _ = self.s.call('POST', '/v1/codes', body, key=key)
        return s, b

    def test_parity_with_the_national_issuer(self):
        """Every case of testdata/parity.json, in order: same area, number, forms, spot code and blocks."""
        with open(os.path.join(TESTDATA, 'parity.json'), encoding='utf-8') as f:
            cases = json.load(f)
        for i, c in enumerate(cases['steps']):
            s, b = self.post(c['request'])
            e = c['expect']
            if not e['inCountry']:
                self.assertEqual((s, b['error']['code']), (422, 'outside_country'), i)
                continue
            self.assertEqual(s, 201, (i, b))
            self.assertEqual(b['area']['id'], e['zone'], i)
            self.assertEqual((b['number'], b['machine'], b['remembered'], b['check']), (e['number'], e['machine'], e['home'], e['check']), i)
            self.assertEqual(b['record']['plus_code'], e['spot'], i)
            self.assertEqual(b.get('newBlock') and [b['newBlock']['lo'], b['newBlock']['hi']], e.get('newBlock'), i)
            self.assertEqual((b['status'], b['issued']), ('provisional', 'on-demand'))
            self.assertEqual(b['entrance']['kind'], 'door' if c['request'].get('of') else 'centre')
            if b['area']['fccArea']:
                self.assertEqual(b['officialAddress'], e['spot'])
        reg = X.Register(self.s.service.con())
        for c in cases['addBlock']:
            a = reg.by_zone[c['request']['zone']]
            got = reg.add_block(dict(a, blocks=list(a['blocks'])), c['request']['compounds'])
            self.assertEqual(list(got) if got else None, c['expect']['block'], c)

    def test_extension_block_persists_and_exports(self):
        a = self.s.service.register().by_zone['02634']       # Magboto: one block of 10 numbers, 150-159
        pts = [(a['lat'] + i * 0.0001, a['lon']) for i in range(11)]
        for lat, lng in pts:
            s, b = self.post({'lat': lat, 'lng': lng})
            self.assertEqual(s, 201, b)
        self.assertEqual(b['newBlock'], {'lo': 160, 'hi': 189})
        s, area = self.s.get('/v1/areas/02634')
        self.assertEqual([x['lo'] for x in area['blocks']], [150, 160])
        s, f = self.s.get('/v1/find?q=' + q(b['remembered']))
        self.assertEqual(f['codes'][0]['machine'], b['machine'])
        out = os.path.join(self.s.dir, 'out')
        store.export_registry(store.connect(self.s.db), out, log=quiet)
        with gzip.open(os.path.join(out, 'areas.csv.gz'), 'rt') as fh:
            self.assertIn('150-159|160-189', fh.read())
        m = json.load(open(os.path.join(out, 'MANIFEST.json')))
        self.assertEqual((m['codes'], m['byTile']['6CW9']), (136, 11))
        self.assertNotEqual(m['exported'], '2026-10-20T15:54:15Z')
        # the export imports again and serves the same codes
        db2 = os.path.join(self.s.dir, 'b.sqlite')
        self.assertEqual(store.import_registry(out, db2, REGISTER, log=quiet), 136)

    def test_duplicate_checks(self):
        r = fixture_rows()[0]
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        s, b = self.post({'lat': lat + 0.00002, 'lng': lng})          # about 2 m from an issued compound
        self.assertEqual((s, b['error']['code']), (409, 'code_exists'))
        self.assertEqual(b['error']['card']['machine'], r['machine'])
        ring = [[-13.0300, 7.6400], [-13.0299, 7.6400], [-13.0299, 7.6401], [-13.0300, 7.6401]]   # about 11 m x 11 m
        s, b = self.post({'lat': 7.64005, 'lng': -13.02995, 'outline': ring})
        self.assertEqual(s, 201, b)
        self.assertEqual((b['building']['class'], b['building']['structures']), ('residential.house', 1))
        shifted = [[x + 0.00002, y] for x, y in ring]                     # mostly the same building
        s, b2 = self.post({'lat': 7.640055, 'lng': -13.02990, 'outline': shifted})
        self.assertEqual((s, b2['error']['code'], b2['error']['card']['machine']), (409, 'code_exists', b['machine']))
        s, b3 = self.post({'lat': 7.64005, 'lng': -13.02995})            # inside the outline
        self.assertEqual(s, 409)
        tiny = [[-13.0400, 7.6500], [-13.04001, 7.6500], [-13.04001, 7.65001]]
        s, b = self.post({'lat': 7.65, 'lng': -13.04, 'outline': tiny})
        self.assertEqual((s, b['error']['code']), (422, 'bad_outline'))

    def test_doors(self):
        r = fixture_rows()[0]
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        s, b = self.post({'lat': lat + 0.00003, 'lng': lng, 'of': r['machine']})
        self.assertEqual((s, b['entrance']['kind'], b['building']['kind'], b['area']['id']), (201, 'door', 'door', r['zone']))
        s, b = self.post({'lat': lat + 0.001, 'lng': lng, 'of': r['machine']})
        self.assertEqual((s, b['error']['code']), (422, 'too_far'))
        s, b = self.post({'lat': lat, 'lng': lng, 'of': 'SL-99999-1000'})
        self.assertEqual((s, b['error']['code']), (404, 'code_not_found'))
        wrong = (int(r['check']) + 1) % 10
        s, b = self.post({'lat': lat + 0.00003, 'lng': lng, 'of': f"{r['machine']}\u00b7{wrong}"})
        self.assertEqual((s, b['error']['code']), (422, 'check_mismatch'))
        s, b = self.post({'lat': lat - 0.00003, 'lng': lng, 'of': f"{r['machine'].lower()} \u00b7 {r['check']}"})
        self.assertEqual((s, b['area']['id']), (201, r['zone']))

    def test_the_border_decides(self):
        """A point more than 300 m outside the national border is refused, whatever its nearest seed;
        a point inside, or just over the line, is issued."""
        across = [(9.0, -10.58001),     # 0.75 km over the eastern border, in a neighbouring country
                  (9.0, -10.56186),     # 2.7 km over it
                  (9.5092, -13.7122)]   # far inside a neighbouring country
        for lat, lng in across:
            self.assertGreater(self.s.service.outline.outside_m(lat, lng, 5000), 300.0)
            s, b = self.post({'lat': lat, 'lng': lng})
            self.assertEqual((s, b['error']['code']), (422, 'outside_country'), (lat, lng))
        s, b = self.post({'lat': 9.0, 'lng': -10.5936})          # inside, near the same border
        self.assertEqual(s, 201, b)
        self.assertEqual((b['entrance']['lat'], b['entrance']['lng']), (9.0, -10.5936))
        s, b = self.post({'lat': 9.0, 'lng': -10.58817})         # 33 m over the line: within its accuracy
        self.assertEqual(s, 201, b)

    def test_keys_limits_and_validation(self):
        self.assertEqual(self.post({'lat': 7.7, 'lng': -13.0}, key=None)[0], 401)
        self.assertEqual(self.post({'lat': 7.7, 'lng': -13.0}, key='wrong')[0], 401)
        self.assertEqual(self.post({'lat': 'x', 'lng': -13.0})[1]['error']['code'], 'missing_point')
        self.assertEqual(self.post({'lat': 7.7, 'lng': -13.0, 'outline': 'x'})[1]['error']['code'], 'bad_outline')
        self.assertEqual(self.post({'lat': 8.0, 'lng': -14.5})[1]['error']['code'], 'outside_country')
        s, b, _ = self.s.call('POST', '/v1/codes', None)
        self.assertEqual(s, 400)
        self.s.cfg.issue_per_day = 2
        self.assertEqual(self.post({'lat': 7.70, 'lng': -13.00})[0], 201)
        self.assertEqual(self.post({'lat': 7.71, 'lng': -13.00})[0], 201)
        s, b = self.post({'lat': 7.72, 'lng': -13.00})
        self.assertEqual((s, b['error']['code']), (429, 'issue_limit'))

    def test_patch(self):
        r = fixture_rows()[1]
        m = r['machine']
        wrong = (int(r['check']) + 1) % 10
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + q(f'{m}\u00b7{wrong}'), {'status': 'confirmed'})
        self.assertEqual((s, b['error']['code']), (422, 'check_mismatch'))
        s, b, _ = self.s.call('PATCH', '/v1/codes/' + q(f"{m}\u00b7{r['check']}"), {'status': 'confirmed'})
        self.assertEqual((s, b['status']), (200, 'confirmed'))
        lat, lng = float(r['entrance_lat']), float(r['entrance_lng'])
        s, b, _ = self.s.call('PATCH', f'/v1/codes/{m}', {'entrance': {'lat': lat + 0.0002, 'lng': lng}})
        self.assertEqual((s, b['entrance']['kind'], b['record']['entrance_lat']), (200, 'gate', f'{lat + 0.0002:.7f}'))
        s, b, _ = self.s.call('PATCH', f'/v1/codes/{m}', {'entrance': {'lat': lat + 0.01, 'lng': lng}})
        self.assertEqual((s, b['error']['code']), (422, 'too_far'))
        self.assertEqual(self.s.call('PATCH', f'/v1/codes/{m}', {'status': 'gone'})[0], 400)
        self.assertEqual(self.s.call('PATCH', f'/v1/codes/{m}', {})[0], 400)
        self.assertEqual(self.s.call('PATCH', '/v1/codes/SL-03002-1002', {'status': 'confirmed'})[0], 404)
        s, b, _ = self.s.call('PATCH', f'/v1/codes/{m}', {'status': 'retired'})
        self.assertEqual((s, b['status']), (200, 'retired'))
        s, b = self.s.get('/v1/find?q=' + q(r['home']))
        self.assertEqual((s, b['error']['code']), (410, 'code_retired'))
        self.assertEqual(self.s.call('PATCH', f'/v1/codes/{m}', {'status': 'confirmed'})[0], 409)
        # a retired number is never given again
        a = self.s.service.register().by_zone[r['zone']]
        s, b = self.post({'lat': lat, 'lng': lng})
        self.assertEqual(s, 201)
        self.assertNotEqual(b['machine'], m)
        self.assertTrue(any(lo <= b['number'] <= hi for lo, hi in a['blocks']))

    def test_dirty_database_is_not_replaced(self):
        self.assertEqual(self.post({'lat': 7.70, 'lng': -13.00})[0], 201)
        with self.assertRaisesRegex(store.RegistryError, 'export'):
            store.import_registry(FIXTURE, self.s.db, REGISTER, log=quiet)


if __name__ == '__main__':
    unittest.main()

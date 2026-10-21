"""The SQLite store: import of the published registry, export in the same
format, and the queries the API needs.

The registry columns are stored as the text that was published, so an export
of an unchanged database reproduces every file byte for byte. Derived columns
(numbers, coordinates, the tile) sit beside them for indexes.
"""
import csv
import gzip
import hashlib
import io
import json
import math
import os
import sqlite3
import time

from . import COUNTRY
from .engine import AREA_COLUMNS, CODE_COLUMNS

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS towns (name TEXT PRIMARY KEY, lat REAL NOT NULL, lng REAL NOT NULL, aliases TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS names (
  key TEXT PRIMARY KEY, id INTEGER NOT NULL UNIQUE, digits INTEGER NOT NULL, spare_lo INTEGER NOT NULL, spare_hi INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS aliases (key TEXT PRIMARY KEY, name_key TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS areas (
  idx INTEGER PRIMARY KEY,
  zone TEXT NOT NULL UNIQUE, seed_id TEXT, plate_name TEXT, official_name TEXT, place TEXT, district TEXT,
  fcc_area TEXT, name_key TEXT, name_id INTEGER, blocks TEXT, needs_council_choice TEXT, tile TEXT,
  seed_lat TEXT, seed_lon TEXT,
  tier TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL, compounds INTEGER NOT NULL, official_key TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS areas_name ON areas(name_key);
CREATE INDEX IF NOT EXISTS areas_official ON areas(official_key);
CREATE INDEX IF NOT EXISTS areas_tile ON areas(tile);
CREATE TABLE IF NOT EXISTS codes (
  id INTEGER PRIMARY KEY,
  machine TEXT NOT NULL UNIQUE, home TEXT NOT NULL, written TEXT NOT NULL, zone TEXT NOT NULL, official_name TEXT,
  district TEXT, number INTEGER NOT NULL, check_digit INTEGER NOT NULL, status TEXT NOT NULL, issued TEXT NOT NULL,
  issued_at TEXT NOT NULL, entrance_lat TEXT NOT NULL, entrance_lng TEXT NOT NULL, entrance_kind TEXT NOT NULL,
  plus_code TEXT, fcc_address TEXT, class TEXT, use TEXT, kind TEXT, structures TEXT, floor_area_m2 TEXT, rule TEXT,
  estate TEXT,
  tile TEXT NOT NULL, name_id INTEGER NOT NULL, lat REAL NOT NULL, lng REAL NOT NULL,
  anchor_lat REAL NOT NULL, anchor_lng REAL NOT NULL, outline TEXT, cell INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS issue_log (id INTEGER PRIMARY KEY, key_id TEXT NOT NULL, machine TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS issue_log_key ON issue_log(key_id, at);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY, at TEXT NOT NULL, key_id TEXT NOT NULL, machine TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
"""

CODE_INDEXES = """
CREATE INDEX IF NOT EXISTS codes_home ON codes(home);
CREATE INDEX IF NOT EXISTS codes_official ON codes(fcc_address) WHERE fcc_address <> '';
CREATE INDEX IF NOT EXISTS codes_plus ON codes(plus_code);
CREATE INDEX IF NOT EXISTS codes_zone_number ON codes(zone, number);
CREATE INDEX IF NOT EXISTS codes_name_number ON codes(name_id, number);
CREATE INDEX IF NOT EXISTS codes_tile ON codes(tile, name_id, number);
CREATE INDEX IF NOT EXISTS codes_cell ON codes(cell);
"""

# Grid index used when SQLite lacks R*Tree: cells of 0.001 degree (about 110 m).
CELL_DEG = 0.001
CELL_COLS = 400000


def cell_of(lat, lng):
    return int(math.floor((lat + 90) / CELL_DEG)) * CELL_COLS + int(math.floor((lng + 180) / CELL_DEG))


class RegistryError(Exception):
    """The registry on disk does not match its manifest, or the database."""


def connect(path, readonly=False):
    if readonly:
        con = sqlite3.connect(f'file:{os.path.abspath(path)}?mode=ro', uri=True, timeout=30, check_same_thread=False)
    else:
        con = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        con.execute('PRAGMA journal_mode=WAL')
        con.execute('PRAGMA synchronous=NORMAL')
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=30000')
    return con


def has_rtree(con):
    try:
        con.execute('CREATE VIRTUAL TABLE temp.rtree_probe USING rtree(id, a, b, c, d)')
        con.execute('DROP TABLE temp.rtree_probe')
        return True
    except sqlite3.OperationalError:
        return False


def meta(con, key, default=None):
    r = con.execute('SELECT value FROM meta WHERE key = ?', (key,)).fetchone()
    return r[0] if r else default


def set_meta(con, key, value):
    con.execute('INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', (key, str(value)))


# ---------------------------------------------------------------- CSV, as the issuer writes it
_SPACE = set('\t\n\v\f\r \x85\xa0            '
             '    　')


def csv_field(s):
    """One field: quoted only when it holds a comma, a quote or a line break,
    or starts with white space; an empty field is never quoted."""
    if s == '':
        return s
    if s == '\\.' or any(c in s for c in ',"\r\n') or s[0] in _SPACE:
        return '"' + s.replace('"', '""') + '"'
    return s


def csv_line(fields):
    return ','.join(csv_field(f) for f in fields) + '\n'


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def gzip_bytes(data):
    """gzip -n: no name, no timestamp, so the same text always gives the same bytes."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buf, mtime=0, compresslevel=9) as g:
        g.write(data)
    return buf.getvalue()


# ---------------------------------------------------------------- import
class _HashingReader(io.RawIOBase):
    """Wraps the decompressed stream of a file and hashes what passes."""

    def __init__(self, raw):
        self.raw, self.h = raw, hashlib.sha256()

    def readable(self):
        return True

    def readinto(self, b):
        data = self.raw.read(len(b))
        n = len(data)
        b[:n] = data
        self.h.update(data)
        return n


def _open_hashed(path):
    raw = gzip.open(path, 'rb') if path.endswith('.gz') else open(path, 'rb')
    hr = _HashingReader(raw)
    text = io.TextIOWrapper(io.BufferedReader(hr, 1 << 20), encoding='utf-8', newline='')
    return text, hr, raw


def _float(s):
    return float(s)


def import_registry(registry, db, register_path, log=print, force=False):
    """Load ``registry`` (the published directory) into a new database at ``db``.

    The registry is checked against its MANIFEST.json (every file's SHA-256 of
    the uncompressed text, every count, the total) and against the frozen
    register (engine/data/register.json); any mismatch aborts and leaves an
    existing database untouched. The new database replaces the old one only
    when complete. A database holding codes issued or changed since its last
    export is not replaced unless ``force`` is given.
    """
    t0 = time.time()
    man_path = os.path.join(registry, 'MANIFEST.json')
    if not os.path.exists(man_path):
        raise RegistryError(f'{man_path} is missing')
    with open(man_path, encoding='utf-8') as f:
        man = json.load(f)
    if man.get('country') != COUNTRY:
        raise RegistryError(f"the manifest is for {man.get('country')!r}, not {COUNTRY}")
    by_tile, shas = man.get('byTile', {}), man.get('sha256', {})
    expected = {f'{t}.csv' for t in by_tile} | {'areas.csv'}
    if set(shas) != expected:
        raise RegistryError('the manifest lists hashes for %s but counts for %s' % (sorted(shas), sorted(expected)))
    if sum(by_tile.values()) != man.get('codes'):
        raise RegistryError(f"the manifest's tile counts add up to {sum(by_tile.values())}, not {man.get('codes')}")
    present = {n[:-3] if n.endswith('.gz') else n for n in os.listdir(registry) if n.endswith(('.csv', '.csv.gz'))}
    extra = sorted(present - expected)
    if extra:
        raise RegistryError(f'files not in the manifest: {extra}')

    if os.path.exists(db) and not force:
        try:
            old = connect(db, readonly=True)
            dirty = meta(old, 'dirty', '0')
            old.close()
        except sqlite3.DatabaseError:
            dirty = '0'
        if dirty == '1':
            raise RegistryError(f'{db} holds codes issued or changed since its last export: export them first, or pass --force')

    with open(register_path, encoding='utf-8') as f:
        reg = json.load(f)
    if reg.get('country') != COUNTRY:
        raise RegistryError(f'{register_path} is not the register of {COUNTRY}')

    tmp = db + '.importing'
    for p in (tmp, tmp + '-wal', tmp + '-shm'):
        if os.path.exists(p):
            os.remove(p)
    os.makedirs(os.path.dirname(os.path.abspath(db)), exist_ok=True)
    con = connect(tmp)
    try:
        con.executescript(SCHEMA)
        rtree = has_rtree(con)
        if rtree:
            con.execute('CREATE VIRTUAL TABLE IF NOT EXISTS codes_rtree USING rtree(id, min_lat, max_lat, min_lng, max_lng)')
        con.execute('BEGIN')
        for t in reg['towns']:
            con.execute('INSERT INTO towns VALUES (?, ?, ?, ?)', (t['name'], t['lat'], t['lng'], json.dumps(t.get('aliases', []))))
        for k, n in reg['names'].items():
            con.execute('INSERT INTO names VALUES (?, ?, ?, ?, ?)', (k, n['id'], n['digits'], n['spare'][0], n['spare'][1]))
        for k, v in reg.get('aliases', {}).items():
            con.execute('INSERT INTO aliases VALUES (?, ?)', (k, v))
        frozen = {f"{a['index']:05d}": a for a in reg['areas']}

        # areas.csv: the frozen area table, with every block added since.
        from .engine import name_key
        name_of = {k: n['id'] for k, n in reg['names'].items()}
        text, hr, raw = _open_hashed(_find(registry, 'areas.csv'))
        rd = csv.reader(text)
        if next(rd) != AREA_COLUMNS:
            raise RegistryError('areas.csv: unexpected columns')
        seen = set()
        for row in rd:
            z = row[0]
            a = frozen.get(z)
            if a is None:
                raise RegistryError(f'areas.csv: area {z} is not in the frozen register')
            blocks = [tuple(int(x) for x in b.split('-')) for b in row[9].split('|')] if row[9] else []
            if [tuple(b) for b in a['blocks']] != blocks[:len(a['blocks'])]:
                raise RegistryError(f'areas.csv: the blocks of area {z} differ from the frozen register')
            if row[7] != a['key'] or int(row[8]) != a['family'] or name_of.get(a['key']) != a['family'] or row[11] != a['tile']:
                raise RegistryError(f'areas.csv: area {z} differs from the frozen register')
            con.execute('INSERT INTO areas VALUES (%s)' % ','.join('?' * 20),
                        (a['index'], *row[:8], int(row[8]), *row[9:], a['tier'], a['lat'], a['lon'], a['compounds'],
                         name_key(a['officialName'] or a['name'])))
            seen.add(z)
        text.close()
        if hr.h.hexdigest() != shas['areas.csv']:
            raise RegistryError('areas.csv: SHA-256 does not match the manifest')
        if seen != set(frozen):
            raise RegistryError('areas.csv: %d areas, the frozen register has %d' % (len(seen), len(frozen)))
        area_tile = {z: a['tile'] for z, a in frozen.items()}
        area_name = {z: a['family'] for z, a in frozen.items()}

        total = 0
        ins = 'INSERT INTO codes (%s, tile, name_id, lat, lng, anchor_lat, anchor_lng, outline, cell) VALUES (%s)' % (
            ', '.join(c if c != 'check' else 'check_digit' for c in CODE_COLUMNS), ','.join('?' * (len(CODE_COLUMNS) + 8)))
        for tile in sorted(by_tile):
            text, hr, raw = _open_hashed(_find(registry, f'{tile}.csv'))
            rd = csv.reader(text)
            if next(rd) != CODE_COLUMNS:
                raise RegistryError(f'{tile}.csv: unexpected columns')
            n = 0
            batch = []
            for row in rd:
                z = row[3]
                if area_tile.get(z) != tile:
                    raise RegistryError(f'{tile}.csv: {row[0]} is in area {z}, which is not in this tile')
                lat, lng = _float(row[11]), _float(row[12])
                vals = row[:6] + [int(row[6]), int(row[7])] + row[8:]
                batch.append((*vals, tile, area_name[z], lat, lng, lat, lng, None, cell_of(lat, lng)))
                n += 1
                if len(batch) >= 20000:
                    con.executemany(ins, batch)
                    batch.clear()
            if batch:
                con.executemany(ins, batch)
            text.close()
            if hr.h.hexdigest() != shas[f'{tile}.csv']:
                raise RegistryError(f'{tile}.csv: SHA-256 does not match the manifest')
            if n != by_tile[tile]:
                raise RegistryError(f'{tile}.csv: {n} codes, the manifest says {by_tile[tile]}')
            total += n
            log(f'  {tile}: {n:,} codes')
        if total != man['codes']:
            raise RegistryError(f"{total} codes, the manifest says {man['codes']}")
        if rtree:
            con.execute('INSERT INTO codes_rtree SELECT id, lat, lat, lng, lng FROM codes')
        for k, v in (('country', COUNTRY), ('exported', man['exported']), ('engine', man['engine']), ('credit', man['credit']),
                     ('licence', man['licence']), ('codes_imported', total), ('dirty', 0), ('blocks_rev', 0),
                     ('imported_at', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())), ('spatial', 'rtree' if rtree else 'grid')):
            set_meta(con, k, v)
        con.execute('COMMIT')
        log('  indexing ...')
        con.executescript(CODE_INDEXES)
        con.execute('ANALYZE')
        con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        con.close()
    except BaseException:
        con.close()
        for p in (tmp, tmp + '-wal', tmp + '-shm'):
            if os.path.exists(p):
                os.remove(p)
        raise
    for p in (db + '-wal', db + '-shm'):
        if os.path.exists(p):
            os.remove(p)
    os.replace(tmp, db)
    log(f'imported {total:,} codes from {registry} into {db} in {time.time() - t0:.0f} s')
    return total


def _find(registry, name):
    for p in (os.path.join(registry, name + '.gz'), os.path.join(registry, name)):
        if os.path.exists(p):
            return p
    raise RegistryError(f'{name}(.gz) is missing from {registry}')


# ---------------------------------------------------------------- export
def export_registry(con, out, log=print):
    """Write the registry in the published format: areas.csv (and .gz), one
    gzip CSV per tile, rows by name id then number, and MANIFEST.json."""
    os.makedirs(out, exist_ok=True)
    shas, by_tile = {}, {}
    buf = io.StringIO()
    buf.write(csv_line(AREA_COLUMNS))
    cols = ', '.join(AREA_COLUMNS[:8]) + ', CAST(name_id AS TEXT), ' + ', '.join(AREA_COLUMNS[9:])
    tiles = set()
    for r in con.execute(f'SELECT {cols}, tile FROM areas ORDER BY idx'):
        buf.write(csv_line(list(r)[:len(AREA_COLUMNS)]))
        tiles.add(r['tile'])
    data = buf.getvalue().encode('utf-8')
    shas['areas.csv'] = sha256_hex(data)
    _write(os.path.join(out, 'areas.csv'), data)
    _write(os.path.join(out, 'areas.csv.gz'), gzip_bytes(data))
    sel = ', '.join(c if c not in ('number', 'check') else f"CAST({'check_digit' if c == 'check' else c} AS TEXT)" for c in CODE_COLUMNS)
    total = 0
    for tile in sorted(tiles):
        buf = io.StringIO()
        buf.write(csv_line(CODE_COLUMNS))
        n = 0
        for r in con.execute(f'SELECT {sel} FROM codes WHERE tile = ? ORDER BY name_id, number', (tile,)):
            buf.write(csv_line(list(r)))
            n += 1
        if not n:
            continue
        data = buf.getvalue().encode('utf-8')
        shas[f'{tile}.csv'] = sha256_hex(data)
        _write(os.path.join(out, f'{tile}.csv.gz'), gzip_bytes(data))
        by_tile[tile] = n
        total += n
        log(f'  {tile}: {n:,} codes')
    dirty = meta(con, 'dirty', '0') == '1'
    exported = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) if dirty else meta(con, 'exported')
    man = {'byTile': by_tile, 'codes': total, 'country': COUNTRY, 'credit': meta(con, 'credit'), 'engine': meta(con, 'engine'),
           'exported': exported, 'licence': meta(con, 'licence'), 'sha256': shas}
    _write(os.path.join(out, 'MANIFEST.json'), (json.dumps(man, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8'))
    if dirty:
        con.execute('BEGIN IMMEDIATE')
        set_meta(con, 'exported', exported)
        set_meta(con, 'dirty', 0)
        con.execute('COMMIT')
    log(f'exported {total:,} codes to {out}')
    return total


def _write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)

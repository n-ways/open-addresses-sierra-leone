#!/usr/bin/env python3
"""Sierra Leone's national name register from the real compound counts (engine/SPEC.md 4.4).

  python3 tools/build-register.py <work folder> [--freeze]

Reads <work>/area-points.csv (tools/assign-areas.py) and <work>/area-counts.json
(`tools/issue_registry.py group`), and:

  1. gives every area its plate name (tools/name_ranges.py derive_plate: the rule of
     engine/reference/plate_names.py with Sierra Leone's word lists and council flags), its official name kept beside it;
  2. groups the areas whose plate names give the same key (sl_address.name_key) into ONE
     national range per name and cuts it into blocks of whole units, one per area, with
     at least 9 spare units for future areas (sl_address.allocate_name);
  3. numbers the areas (index 1... by plate key, then the seed's position on the national
     curve, then the seed id) and the names (id 1... by key).

Every area issues codes, Freetown City Council's included: every building has its code, and
in FCC's area the property's Plus Code, FCC's address, is shown first. Once frozen, nothing that exists changes; only areas and names are added.

Writes model/name-ranges.json (the register, every name with its blocks),
engine/data/register.json (what an engine ships) and model/stats/register.json (summary).
"""
import collections, csv, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import sl_address as E  # noqa: E402
import plate_names as P  # noqa: E402
spec = importlib.util.spec_from_file_location('name_ranges', os.path.join(HERE, 'name_ranges.py'))
NR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(NR)

work = os.path.abspath(sys.argv[1])
FREEZE = '--freeze' in sys.argv
RANGES = os.path.join(REPO, 'model', 'name-ranges.json')
counts = json.load(open(os.path.join(work, 'area-counts.json')))
rows = []
for r in csv.DictReader(open(os.path.join(work, 'area-points.csv'), encoding='utf-8')):
    n = counts.get(r['aid'], 0)
    if not n:
        continue
    rows.append({'aid': r['aid'], 'officialName': r['name'], 'place': r['kind'], 'tier': r['tier'], 'lat': float(r['lat']),
                 'lon': float(r['lon']), 'footprints': int(r['footprints']), 'compounds': n, 'label': r['label'], 'fcc': r['fcc'] == '1'})
old = json.load(open(RANGES, encoding='utf-8')) if os.path.exists(RANGES) else {}
if old.get('frozen'):
    sys.exit('the register is frozen: later codes and blocks are added by the issuer (server/, POST /v1/codes), not by this tool')

# ---------------------------------------------------------------- plate names (tools/name_ranges.py)
freq = P.word_freq([NR.prepare(r['officialName']) for r in rows], NR.LANG)
design = json.load(open(os.path.join(REPO, 'model', 'design.json'), encoding='utf-8'))
towns = [(t['name'], t['lat'], t['lng']) for t in design['referenceTowns']['towns']]
towns += [(r['officialName'], r['lat'], r['lon']) for r in rows if r['place'] in ('town', 'city')]
avoid_all = {E.name_key(n) for n in NR.AVOID_LISTED} | {E.name_key(NR.prepare(t[0])) for t in towns}
official_keys = collections.Counter(E.name_key(r['officialName']) for r in rows)
for r in rows:
    own = {E.name_key(NR.prepare(t[0])) for t in towns if NR.km((r['lat'], r['lon']), (t[1], t[2])) <= NR.OWN_TOWN_KM}
    own_key = E.name_key(r['officialName'])
    d = NR.derive_plate(r['officialName'], freq, avoid_all - own, {k for k in official_keys if k != own_key})
    r.update(name=d['plate'], plateRule=d['rule'], needsCouncilChoice=d['needsCouncilChoice'],
             plateCandidates=d['candidates'] if d['needsCouncilChoice'] else [], plateReason=d.get('reason', '') if d['needsCouncilChoice'] else '',
             key=E.name_key(d['plate']), officialKey=own_key, overLimit=not P.fits(d['plate'], NR.LANG))

# ---------------------------------------------------------------- ids, ranges, blocks
rows.sort(key=lambda r: (r['key'], E.curve_position(r['lat'], r['lon']), r['aid']))
for i, r in enumerate(rows, 1):
    r['index'] = i
by_key = collections.defaultdict(list)
for r in rows:
    by_key[r['key']].append(r)
qualified = [k for k in sorted(by_key) if E.name_range_digits([r['compounds'] for r in by_key[k]]) is None]
if qualified:
    sys.exit(f'names needing a qualifier: {qualified}')
names = {}
for nid, k in enumerate(sorted(by_key), 1):
    rec = E.allocate_name([(r['index'], r['lat'], r['lon'], r['compounds']) for r in by_key[k]])
    names[k] = {'id': nid, 'key': k, 'digits': rec['digits'], 'spareLo': rec['spareLo'], 'spareHi': rec['spareHi'],
                'blocks': {b['area']: [b['lo'], b['hi']] for b in rec['blocks']}}
for r in rows:
    n = names[r['key']]
    r['family'], r['digits'], r['blocks'] = n['id'], n['digits'], [n['blocks'][r['index']]]
    r['tile'] = E.olc_encode(r['lat'], r['lon'])[:4]

# ---------------------------------------------------------------- aliases
claims = collections.defaultdict(set)
for r in rows:
    if r['officialKey'] != r['key']:
        claims[r['officialKey']].add(r['key'])
aliases, dropped = {}, []
for ok, pks in sorted(claims.items()):
    if len(pks) == 1 and ok not in by_key:
        aliases[ok] = next(iter(pks))
    else:
        dropped.append({'alias': ok, 'plateKeys': sorted(pks), 'why': 'claimed by two plate names' if len(pks) > 1 else 'is itself a plate name'})

AREA_FIELDS = ('index', 'aid', 'name', 'officialName', 'key', 'family', 'digits', 'blocks', 'lat', 'lon', 'tier', 'place', 'label', 'fcc',
               'tile', 'compounds', 'needsCouncilChoice')
reg = {'country': 'SL', 'version': '2026-10-20', 'frozen': FREEZE, 'frozenOn': '2026-10-20' if FREEZE else None,
       'note': ('National name register. "name" is the plate name (at most 12 characters and 2 words); "officialName" the full name, '
                'printed small and decoding as an alias. Blocks are whole units of a name\'s range holding twice the area\'s compounds '
                'at first issue; the spare units of each name are kept for its future areas. Frozen at first issue: blocks never move, '
                'shrink or get renumbered; new areas and full blocks take the spare (sl_address.add_block).'),
       'rule': {'units': E.UNITS, 'spareUnits': E.NAME_SPARE_UNITS, 'maxDigits': E.MAX_DIGITS, 'order': 'seed along the national Hilbert curve (order 16)'},
       'aliases': aliases, 'droppedAliases': dropped,
       'names': [{'id': n['id'], 'key': n['key'], 'digits': n['digits'], 'spare': [n['spareLo'], n['spareHi']],
                  'areas': [dict({f: r[f] for f in AREA_FIELDS}, plateRule=r['plateRule'], plateCandidates=r['plateCandidates'],
                                 plateReason=r['plateReason'], overLimit=r['overLimit'])
                            for r in by_key[n['key']]]} for n in sorted(names.values(), key=lambda n: n['id'])]}
json.dump(reg, open(RANGES, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
eng = {'version': 1, 'country': 'SL',
       'note': 'N-Ways Addressing for Sierra Leone: the register a decoder needs (no data about any home). Frozen at first issue; later blocks are only added.',
       'towns': design['referenceTowns']['towns'],
       'areas': [{f: r[f] for f in AREA_FIELDS} for r in sorted(rows, key=lambda r: r['index'])],
       'names': {k: {'id': n['id'], 'digits': n['digits'], 'spare': [n['spareLo'], n['spareHi']]} for k, n in sorted(names.items())},
       'aliases': aliases}
os.makedirs(os.path.join(REPO, 'engine', 'data'), exist_ok=True)
json.dump(eng, open(os.path.join(REPO, 'engine', 'data', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

shared = [k for k in by_key if len(by_key[k]) > 1]
digits = collections.Counter(names[r['key']]['digits'] for r in rows)
cdig = collections.Counter()
for r in rows:
    cdig[r['digits']] += r['compounds']
summary = {'areas': len(rows), 'fccAreas': sum(r['fcc'] for r in rows), 'compounds': sum(r['compounds'] for r in rows), 'names': len(names),
           'repeatedNames': len(shared), 'areasSharingAName': sum(len(by_key[k]) for k in shared),
           'namesByDigits': dict(sorted(collections.Counter(n['digits'] for n in names.values()).items())),
           'areasByDigits': dict(sorted(digits.items())), 'compoundsByDigits': dict(sorted(cdig.items())),
           'plateNames': {'byRule': dict(collections.Counter(r['plateRule'] for r in rows)), 'needsCouncilChoice': sum(r['needsCouncilChoice'] for r in rows),
                          'stillOverLimit': sum(r['overLimit'] for r in rows), 'compoundsWithProvisionalName': sum(r['compounds'] for r in rows if r['needsCouncilChoice']),
                          'aliases': len(aliases), 'droppedAliases': len(dropped),
                          'officialOver12': sum(1 for r in rows if P.plate_length(r['officialName']) > P.MAX_CHARS)},
           'largestRanges': sorted(({'name': by_key[k][0]['name'], 'areas': len(by_key[k]), 'compounds': sum(r['compounds'] for r in by_key[k]),
                                     'digits': names[k]['digits']} for k in shared), key=lambda x: -x['compounds'])[:12],
           'mostAreas': sorted(({'name': by_key[k][0]['name'], 'areas': len(by_key[k]), 'compounds': sum(r['compounds'] for r in by_key[k]),
                                 'digits': names[k]['digits']} for k in shared), key=lambda x: (-x['areas'], x['name']))[:12],
           'biggestAreas': sorted(({'name': r['name'], 'label': r['label'], 'compounds': r['compounds'], 'digits': r['digits']} for r in rows),
                                  key=lambda x: -x['compounds'])[:12]}
os.makedirs(os.path.join(REPO, 'model', 'stats'), exist_ok=True)
json.dump(summary, open(os.path.join(REPO, 'model', 'stats', 'register.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1)[:3500])

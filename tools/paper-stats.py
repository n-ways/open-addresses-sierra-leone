#!/usr/bin/env python3
"""The figures of the white paper, from the issued compounds: model/building-stats.json.

  python3 tools/paper-stats.py <work folder> <lotes.jsonl.gz>

Reads the lotes written by `tools/issue_registry.py number` (every compound with its
structures and number), the sorted footprints (for the grouping check) and the
N-Ways places (for access to services). Standard library only, one area or one
compound at a time.

  country, districts   compounds, structures, sources, sizes, rules, use classes,
                       floors, digits of the numbers, Freetown City Council's area
  validation           the rules re-run with the mapped walls and fences hidden:
                       how many come out whole
  access               straight-line distance from 20,000 random compounds to the
                       nearest mapped health facility, school, police post, pharmacy
"""
import collections, csv, gzip, importlib.util, json, math, os, random, statistics, sys

csv.field_size_limit(1 << 30)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
work, lotes = os.path.abspath(sys.argv[1]), sys.argv[2]
spec = importlib.util.spec_from_file_location('issue_registry', os.path.join(HERE, 'issue_registry.py'))
IR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(IR)


def pct(v, ps=(10, 25, 50, 75, 90)):
    v = sorted(v)
    return {f'p{p}': round(v[int(p / 100 * (len(v) - 1))], 1) for p in ps} if v else {}


class Acc:
    def __init__(self):
        self.compounds = 0
        self.structures = 0
        self.osm = 0
        self.sizes = collections.Counter()
        self.rules = collections.Counter()
        self.settle = collections.Counter()
        self.classes = collections.Counter()
        self.top = collections.Counter()
        self.round = 0
        self.family = 0
        self.floors_src = collections.Counter()
        self.floors = collections.Counter()
        self.digits = collections.Counter()
        self.street = 0
        self.areas = []
        self.multi = 0

    def add(self, c):
        sts = c['structures']
        self.compounds += 1
        self.structures += len(sts)
        self.osm += sum(1 for s in sts if s['src'] == 'osm')
        self.sizes[min(len(sts), 7)] += 1
        if len(sts) > 1:
            self.multi += len(sts)
        self.rules[c['rule']] += 1
        self.settle['fcc' if c['coverage'] == 'official' else 'nways'] += 1
        self.family += c['rule'] == 'dense'
        self.digits[len(str(c['number']))] += 1
        self.street += c['rule'] == 'yard'
        for s in sts:
            self.classes[s['class']] += 1
            self.top[s['class'].split('.')[0]] += 1
            self.round += s['class'] == 'residential.round-hut'
            self.floors_src[s['floorsSource'] or 'none'] += 1
            if s['floors']:
                self.floors[min(s['floors'], 4)] += 1
            if len(self.areas) < 400000 or random.random() < 0.1:
                self.areas.append(s['areaM2'])

    def out(self):
        return {'compounds': self.compounds, 'structures': self.structures, 'fromOpenStreetMap': self.osm,
                'structuresPerCompound': round(self.structures / max(1, self.compounds), 3),
                'shareStructuresInMultiStructureCompounds': round(self.multi / max(1, self.structures), 3),
                'compoundSizeMix': {('7+' if k == 7 else str(k)): v for k, v in sorted(self.sizes.items())},
                'rules': dict(self.rules.most_common()), 'coverage': dict(self.settle), 'denseCompounds': self.family,
                'useTop': dict(self.top.most_common()), 'useDetail': dict(self.classes.most_common(20)),
                'roundHouses': self.round, 'roundHouseShare': round(self.round / max(1, self.structures), 3),
                'floorsFrom': dict(self.floors_src.most_common()), 'floors': {str(k): v for k, v in sorted(self.floors.items())},
                'compoundsByDigits': {str(k): v for k, v in sorted(self.digits.items())}, 'yardCompounds': self.street,
                'footprintAreaM2': pct(self.areas)}


random.seed(224)
country, frames, labels = Acc(), collections.defaultdict(Acc), collections.defaultdict(Acc)
sample = []
seen = 0
with gzip.open(lotes, 'rt', encoding='utf-8') as f:
    for line in f:
        c = json.loads(line)
        country.add(c)
        frames['Freetown (FCC)' if c['coverage'] == 'official' else (c['label'] or '(none)')].add(c)
        labels[c['label'] or '(none)'].add(c)
        seen += 1
        if len(sample) < 20000:
            sample.append((c['lat'], c['lon']))
        elif random.random() < 20000 / seen:
            sample[random.randrange(20000)] = (c['lat'], c['lon'])

# ---------------------------------------------------------------- grouping check
enc = {r['eid']: r for r in csv.DictReader(open(os.path.join(work, 'enclosure-gates.csv'), encoding='utf-8'))}
TRUTH = ('osm-wall', 'osm-fence', 'osm-hedge', 'osm-retaining_wall')
whole = exact = near_one = total = 0
by_kind = collections.Counter()
for aid, rows in IR.areas_of(os.path.join(work, 'buildings.csv')):
    truth = collections.defaultdict(list)
    for k, r in enumerate(rows):
        if r['eid'] and enc.get(r['eid'], {}).get('kind') in TRUTH:
            truth[r['eid']].append(k)
    truth = {e: ks for e, ks in truth.items() if len(ks) >= 2}
    if not truth:
        continue

    IR.prep(rows)            # prep sorts rows: map the truth by structure id
    sid_eid = {}
    for r in rows:
        if r['eid'] in truth:
            sid_eid[r['sid']] = r['eid']
        r['eid'] = ''
    groups = [ks for ks, rule in IR.group(rows)]
    of = {}
    for i, grp in enumerate(groups):
        for k in grp:
            of[rows[k]['sid']] = i
    members = collections.defaultdict(list)
    for sid, e in sid_eid.items():
        members[e].append(sid)
    for e, sids in members.items():
        gs = collections.Counter(of[s] for s in sids)
        total += 1
        by_kind[enc[e]['kind']] += 1
        top, n = gs.most_common(1)[0]
        if n == len(sids):
            whole += 1
            if len(groups[top]) == len(sids):
                exact += 1
        elif n == len(sids) - 1:
            near_one += 1
validation = {'mappedEnclosures': total, 'byKind': dict(by_kind), 'whole': whole, 'exact': exact, 'missingOne': near_one,
              'shareWhole': round(whole / max(1, total), 3), 'shareExact': round(exact / max(1, total), 3),
              'shareMissingOne': round(near_one / max(1, total), 3)}

# ---------------------------------------------------------------- access to services
KINDS = {'health': ('hospital', 'clinic', 'health', 'doctors', 'healthcentre', 'health_centre'), 'school': ('school', 'university', 'college'),
         'police': ('police',), 'pharmacy': ('pharmacy',)}
fac = collections.defaultdict(list)
for r in csv.DictReader(open(os.path.join(work, 'places.csv'), encoding='utf-8')):
    for k, cats in KINDS.items():
        if r['category'] in cats:
            fac[k].append((float(r['lat']), float(r['lon'])))
grid = {k: collections.defaultdict(list) for k in fac}
for k, pts in fac.items():
    for la, lo in pts:
        grid[k][(int(la * 10), int(lo * 10))].append((la, lo))


def nearest(k, la, lo):
    best = None
    for ring in range(0, 80):
        for i in range(-ring, ring + 1):
            for j in range(-ring, ring + 1):
                if max(abs(i), abs(j)) != ring:
                    continue
                for pla, plo in grid[k].get((int(la * 10) + i, int(lo * 10) + j), ()):
                    d = math.hypot((pla - la) * 110.574, (plo - lo) * 111.32 * math.cos(math.radians(la)))
                    if best is None or d < best:
                        best = d
        if best is not None and best < ring * 10:
            return best
    return best if best is not None else 999.0


access = {}
for k in KINDS:
    ds = [nearest(k, la, lo) for la, lo in sample]
    access[k] = {'facilities': len(fac[k]), 'within2km': round(sum(d <= 2 for d in ds) / len(ds), 3),
                 'within5km': round(sum(d <= 5 for d in ds) / len(ds), 3), 'medianKm': round(statistics.median(ds), 1)}

out = {'date': '2026-10-20', 'note': 'From the codes issued on 20 October 2026 (tools/issue_registry.py) and the N-Ways map data (OpenStreetMap, Google Open Buildings, Microsoft footprints).',
       'rules': {'satelliteBelowM2': IR.SATELLITE_MAX_M2, 'principalFromM2': IR.PRINCIPAL_MIN_M2, 'townJoinM': IR.JOIN_M, 'yardJoinM': IR.YARD_M,
                 'yardMaxPerCell': IR.YARD_MAX_HA, 'denseAbovePerCell': IR.DENSE},
       'country': country.out(), 'districts': {k: v.out() for k, v in sorted(frames.items())},
       'labels': {k: {'compounds': v.compounds, 'structures': v.structures, 'roundHutShare': round(v.round / max(1, v.structures), 3)}
                  for k, v in sorted(labels.items(), key=lambda kv: -kv[1].compounds)},
       'validation': validation, 'access': access, 'accessSample': len(sample)}
json.dump(out, open(os.path.join(REPO, 'model', 'building-stats.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({'country': out['country'], 'validation': validation, 'access': access}, ensure_ascii=False, indent=1)[:6000])

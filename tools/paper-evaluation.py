#!/usr/bin/env python3
"""The measured properties reported in the paper's evaluation: model/stats/evaluation.json.

  python3 tools/paper-evaluation.py

From the published files only (registry/, engine/data/register.json), with the reference
engine. Standard library only; the registry is streamed tile by tile.

  uniqueness      every machine form and every remembered form occurs once
  decode          every remembered form, as people write it (in groups), decodes to its machine form
  lengths         characters of the remembered form, digits of the number
  plusCodeCells   compounds whose 10-character Plus Code cell holds another compound's entrance
  slips           single wrong digits and swaps of neighbours that land in another block of the
                  same name, and how many each check-digit design would accept
"""
import collections, csv, gzip, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import sl_address as E  # noqa: E402

SAMPLES_PER_BLOCK = 40


def registry_rows():
    manifest = json.load(open(os.path.join(REPO, 'registry', 'MANIFEST.json')))
    for tile in sorted(manifest['byTile']):
        with gzip.open(os.path.join(REPO, 'registry', tile + '.csv.gz'), 'rt', newline='', encoding='utf-8') as f:
            yield from csv.DictReader(f)


def slips(reg):
    """Errors in the number that stay inside the name's range and land in another place's block."""
    by_name = collections.defaultdict(list)
    for a in reg['areas']:
        for lo, hi in a['blocks']:
            by_name[a['key']].append((lo, hi, a['index']))
    out = collections.Counter(crossPlace=0, acceptedNameCheck=0, acceptedAreaCheck=0)
    for key, blocks in by_name.items():
        if len({b[2] for b in blocks}) < 2:
            continue
        name_id = reg['names'][key]['id']

        def area_of(n):
            for lo, hi, ix in blocks:
                if lo <= n <= hi:
                    return ix
            return None
        for lo, hi, ix in blocks:
            step = max(1, (hi - lo + 1) // SAMPLES_PER_BLOCK)
            for n in range(lo + step // 2, hi + 1, step):
                s = str(n)
                wrong = set()
                for i, ch in enumerate(s):
                    for d in '0123456789':
                        if d != ch and not (i == 0 and d == '0'):
                            wrong.add(s[:i] + d + s[i + 1:])
                for i in range(len(s) - 1):
                    if s[i] != s[i + 1] and not (i == 0 and s[i + 1] == '0'):
                        wrong.add(s[:i] + s[i + 1] + s[i] + s[i + 2:])
                for w in wrong:
                    m = int(w)
                    other = area_of(m)
                    if other is None or other == ix:
                        continue
                    out['crossPlace'] += 1
                    if E.damm(f'{name_id:04d}{m}') == E.damm(f'{name_id:04d}{n}'):
                        out['acceptedNameCheck'] += 1
                    if E.damm(f'{other:05d}{m}') == E.damm(f'{ix:05d}{n}'):
                        out['acceptedAreaCheck'] += 1
    return dict(out)


def main():
    reg = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json')))
    register, aliases = E.load_register()
    machines, homes, cells = set(), collections.Counter(), collections.Counter()
    dup_machine = 0
    lengths, digits = collections.Counter(), collections.Counter()
    decoded = failed = 0
    n = 0
    for r in registry_rows():
        n += 1
        if r['machine'] in machines:
            dup_machine += 1
        machines.add(r['machine'])
        homes[E.name_key(r['home'].rsplit(' ', 1)[0]) + ' ' + r['number']] += 1
        lengths[len(r['home'])] += 1
        digits[len(r['number'])] += 1
        cells[E.olc_encode(float(r['entrance_lat']), float(r['entrance_lng']))] += 1
        try:
            if E.decode_compound(r['written'], register, aliases)['machine'] == r['machine']:
                decoded += 1
            else:
                failed += 1
        except ValueError:
            failed += 1
    shared = sum(c for c in cells.values() if c > 1)
    ls = sorted(lengths.elements())
    out = {
        'codes': n,
        'uniqueness': {'duplicateMachine': dup_machine, 'duplicateRemembered': sum(c - 1 for c in homes.values() if c > 1)},
        'decode': {'decoded': decoded, 'failed': failed},
        'lengths': {'median': ls[len(ls) // 2], 'p90': ls[int(0.9 * (len(ls) - 1))], 'max': ls[-1],
                    'atMost16': sum(c for k, c in lengths.items() if k <= 16),
                    'histogram': {str(k): lengths[k] for k in sorted(lengths)}},
        'digits': {str(k): digits[k] for k in sorted(digits)},
        'plusCodeCells': {'cells': len(cells), 'compoundsInSharedCells': shared, 'share': round(shared / n, 4)},
        'slips': slips(reg),
        'samplesPerBlock': SAMPLES_PER_BLOCK,
    }
    with open(os.path.join(REPO, 'model', 'stats', 'evaluation.json'), 'w') as f:
        json.dump(out, f, indent=1)
        f.write('\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()

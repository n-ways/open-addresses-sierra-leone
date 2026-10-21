#!/usr/bin/env python3
"""Conformance vectors for every implementation of the engine: engine/reference/vectors.json.

Computed by the reference engine (engine/reference/sl_address.py) on the frozen register
(engine/data/register.json); every implementation of the engine (the issuer's among them) must
reproduce them value for value.

  python3 tools/vectors.py
"""
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import sl_address as E  # noqa: E402


def main():
    rnd = random.Random(232)
    reg = json.load(open(os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))
    register, aliases = E.load_register()
    areas = reg['areas']
    words = sorted({a['name'] for a in areas} | {a['officialName'] for a in areas})
    tricky = ['Kissy Tong', 'Kissy Town', "Kroo Bay", 'Kru Bay', 'Saint John', 'St John', 'Mount Aureol', 'Mt Aureol', 'The Wharf',
              'Koya Town Two', 'Koya Town 2', 'Koya Town II', "Ma'Sorie", 'Masorie', 'Gbangbatoke Junction', 'Rokel & Co', 'Bo-Kenema',
              'Kemedugu (II)', 'Fourah Bay', 'FOURAH BAY', 'Mabella', 'Lumley']
    keys = [[w, E.name_key(w)] for w in tricky + rnd.sample(words, 500)]
    forms, found = [], []
    for a in rnd.sample(areas, 400):
        lo, hi = a['blocks'][0]
        n = rnd.randint(lo, hi)
        chk = E.check_digit(a['family'], n)
        forms.append({'zone': f"{a['index']:05d}", 'number': n, 'check': chk, 'home': f"{a['name']} {n}",
                      'written': f"{a['name']} {E.group_digits(n)} · {chk}", 'machine': f"SL-{a['index']:05d}-{n}"})
        for text in (f"{a['name']} {n}", f"{a['name']} {E.group_digits(n)} · {chk}", f"{a['name']} {n}.2/3"):
            try:
                found.append({'text': text, 'machine': E.decode_compound(text, register, aliases)['machine']})
            except ValueError as e:
                found.append({'text': text, 'error': str(e)})
    off = [a for a in areas if a['officialName'] != a['name']]
    for a in rnd.sample(off, min(80, len(off))):
        n = a['blocks'][0][0] + 1
        text = f"{a['officialName']} {n}"
        try:
            found.append({'text': text, 'machine': E.decode_compound(text, register, aliases)['machine']})
        except ValueError as e:
            found.append({'text': text, 'error': str(e)})
    for a in rnd.sample(areas, 40):
        n = a['blocks'][0][0] + 3
        found.append({'text': f"{a['name']} {E.group_digits(n)} · {(E.check_digit(a['family'], n) + 1) % 10}", 'error': 'check'})
    found.append({'text': 'Nowhere Land 1234', 'error': 'no such name'})
    spots = []
    for _ in range(400):
        lat, lng = rnd.uniform(6.9, 10.0), rnd.uniform(-13.3, -10.3)
        sp = E.spot(lat, lng)
        rec = None
        if sp['town']:
            t = E.town(sp['town'])
            rec = E.olc_recover(sp['short'].split(' ')[0], t['lat'], t['lng'])
        d = E.olc_decode(sp['full'])
        spots.append({'lat': lat, 'lng': lng, 'full': sp['full'], 'short': sp['short'], 'recovered': rec, 'precise': E.olc_encode(lat, lng, 11),
                      'decoded': [d['lat'], d['lng']], 'curve': E.curve_position(lat, lng)})
    lat0, lon0 = 8.4650, -13.2350
    comps = [(f'c{k:02d}', lat0 + rnd.uniform(0, 0.004), lon0 + rnd.uniform(0, 0.004)) for k in range(18)]
    nums, _ = E.number_area(comps, {'lo': 1000, 'hi': 1099})
    issued = {nums[c[0]]: (c[1], c[2]) for c in comps}
    inserts = []
    for _ in range(50):
        lat, lon = lat0 + rnd.uniform(-0.001, 0.005), lon0 + rnd.uniform(-0.001, 0.005)
        try:
            n = E.next_free_number(lat, lon, issued, {'lo': 1000, 'hi': 1099})
        except ValueError:
            n = None
        inserts.append({'lat': lat, 'lon': lon, 'number': n})
    out = {'note': 'Computed by engine/reference/sl_address.py on the frozen register; every implementation must match.',
           'nameKeys': keys, 'forms': forms, 'found': found, 'spots': spots,
           'numbering': {'lo': 1000, 'hi': 1099, 'compounds': [{'id': c[0], 'lat': c[1], 'lon': c[2]} for c in comps], 'numbers': nums,
                         'inserts': inserts},
           'blockSizes': [[n, d, E.block_units(n, d) * E.unit_size(d)] for n in (0, 1, 4, 5, 6, 49, 50, 51, 499, 4500) for d in (3, 4, 5)],
           'groups': [[n, E.group_digits(n)] for n in (482, 2716, 17216, 100, 99999)]}
    json.dump(out, open(os.path.join(REPO, 'engine', 'reference', 'vectors.json'), 'w'), ensure_ascii=False, indent=0)
    print(len(keys), 'name keys,', len(forms), 'forms,', len(found), 'decodings,', len(spots), 'spots,', len(inserts), 'inserts')


if __name__ == '__main__':
    main()

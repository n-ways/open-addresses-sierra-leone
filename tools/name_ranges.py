#!/usr/bin/env python3
"""Sierra Leone: plate names and national number ranges (docs/model.md sections 4.1-4.2).

1. Plate names. Every design-stage address area keeps its official name (the name on
   the map, printed small on cards and plates) and gets a PLATE NAME, the name
   people say and type in the remembered code: at most 12 characters and 2
   words (engine/reference/plate_names.py, with Sierra Leone's word lists
   and the country rules below).
2. National ranges. Every area whose PLATE name gives the same normalised key
   (engine/reference/sl_address.py name_key) draws its numbers from ONE national
   range for that name, cut into frozen blocks, one per area, with spare units
   left for future areas of the name (allocate_name). The official name becomes
   an alias of the plate name when it belongs to one plate name only.

  tools/name_ranges.py [--areas model/design-areas.csv] [--out model/name-ranges.json]

Input: model/design-areas.csv (tools/area_stats.py --areas-out), one row per design-stage
area; the official name is the column officialName (or name, as area_stats.py
writes it). This script rewrites the file with the plate columns added. Only
areas outside official coverage (official = 0) get N-Ways numbers; areas inside
Freetown City Council's area get plate names too (for spoken aliases if FCC
adopts them, docs/model.md 2.3) but no blocks. Design-stage area ids and name ids are
illustrative until the areas are frozen. Standard library only.
"""
import argparse, collections, csv, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import sl_address as E  # noqa: E402
import plate_names as P  # noqa: E402

LANG = 'en'   # area names are English and Krio, with Temne, Mende, Limba ... words: English word lists

# ---------------------------------------------------------------- country rules
# Generic words always dropped (the English list less "Town", plus the
# "Comm" abbreviation of Community used in Freetown's community list).
GENERIC_ALWAYS = ['community', 'comm', 'estate', 'area']
# "Town", "Village", "Ville" are dropped ONLY when the name is over the limit:
# many names are "X Town" said whole (Allen Town, Congo Town, Murray Town, Kissy
# Town is not Kissy), so "Town" stays wherever the name fits.
GENERIC_IF_LONG = ['town', 'village', 'ville']
# Documented short forms people already say: {official name: (plate, source)}.
# None documented for Sierra Leone's design-stage areas yet (see SOURCES.md).
KNOWN = {}
# Well-known towns a shortened plate name must not equal (the area's own town
# is removed, see own_town): district headquarters and big towns, the reference
# towns of model/design.json, every design-stage area mapped as place=town or city
# (OpenStreetMap; chiefdom headquarters as far as the map tags them), and the
# neighbouring countries and their capitals.
AVOID_LISTED = [
    'Freetown', 'Waterloo', 'Bo', 'Kenema', 'Makeni', 'Koidu', 'Kono', 'Port Loko', 'Kambia', 'Kabala', 'Kailahun',
    'Magburaka', 'Kamakwie', 'Bendugu', 'Moyamba', 'Bonthe', 'Mattru Jong', 'Pujehun', 'Lunsar', 'Lungi',
    'Segbwema', 'Daru', 'Tongo', 'Yengema', 'Mile 91', 'Pendembu', 'Zimmi', 'Koindu', 'Rokupr', 'Masiaka',
    'Bumbuna', 'Kamabai', 'Binkolo', 'Njala', 'Taiama', 'Blama', 'Hangha', 'Panguma', 'Potoru', 'Sumbuya',
    'Mano', 'Moyamba Junction', 'Taiama Junction', 'Bandajuma', 'Panguema', 'Falaba', 'Hastings', 'Wellington',
    'Kissy', 'Lumley', 'Goderich', 'Aberdeen',
    'Conakry', 'Monrovia', 'Liberia', 'Guinea',
]
OWN_TOWN_KM = 5.0
NUMBER_WORDS = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven',
                'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen']
TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def number_word(n):
    n = int(n)
    if n < 20:
        return NUMBER_WORDS[n]
    if n < 100:
        return TENS[n // 10] + ('-' + NUMBER_WORDS[n % 10] if n % 10 else '')
    return str(n)


def prepare(official):
    """Spelling clean-up before the plate-name rule (the official name is never changed):
    ", Sierra Leone" dropped; a leading "*" dropped; spaced dashes joined ("Tombo - Banka"
    -> "Tombo-Banka"); names typed in capitals written in title case (acronyms of up to
    3 letters kept); Roman numerals in capitals; trailing dots dropped; digits written as
    words, so that the number is always the last thing in a code ("Badasuma 2" ->
    "Badasuma Two"; name_key folds them back)."""
    s = re.sub(r',\s*Sierra Leone\s*$', '', official.strip()).lstrip('*').strip()
    s = re.sub(r'\s*\((I{1,3}|IV|VI{0,3}|\d{1,2})\)', r' \1', s, flags=re.I)   # "Kemedugu (II)": a qualifier, kept
    s = re.sub(r'\s+-\s+', '-', s)
    s = re.sub(r'\s+', ' ', s)
    if s.upper() == s and re.search(r'[A-Z]{4}', s):
        s = ' '.join(w if len(w) <= 3 and ' ' not in s else w.title() for w in s.split())
    s = ' '.join(w.upper() if re.fullmatch(r'(?i)i{1,3}|iv|vi{0,3}', w) else w for w in s.split())
    s = re.sub(r'(?<=[A-Za-z])\.$', '', s)
    s = re.sub(r'(?<![\w.])(\d{1,2})(?!\w)', lambda m: number_word(m.group(1)), s)
    return s


def km(a, b):
    k = math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot((a[0] - b[0]) * 110.574, (a[1] - b[1]) * 111.32 * k)


def with_generic(generic, fn, *args, **kw):
    """Run a plate_names function with a generic-word list in place of the
    module's default one (which drops "Town" and "Village" always)."""
    default = P.GENERIC[LANG]
    P.GENERIC[LANG] = list(generic)
    try:
        return fn(*args, **kw)
    finally:
        P.GENERIC[LANG] = default


def derive_with(generic, name, freq, kw):
    return with_generic(generic, P.derive, name, LANG, freq, **kw)


def clean_with(generic, name):
    return with_generic(generic, P.clean, name, LANG)[0]


NUMBER_WORD_SET = {x.lower() for x in NUMBER_WORDS + TENS if x}
# Words that are not a place name on their own: a plate made only of them goes to the council
# ("Police Barracks" is not "Police", "Chinese Quarry" is not "Chinese").
NOT_A_PLACE = {'police', 'government', 'chinese', "couple's", "missionary's", "clerk's", 'mansion', 'commercial',
               'eastern', 'western', 'southern', 'northern', 'mountain', 'local', 'number', 'no', 'site', 'hole',
               'shepherd', 'good', 'down', 'community', 'dj', "dj snow's", "snow's", 'ndmc', 'ckc', 'coal burner'}


def words(s):
    return [w.strip('.()') for w in re.split(r'[\s-]+', s) if w and re.search(r'\w', w)]


def strong_words(s):
    """Place words: not linking, weak, landmark, generic or number words."""
    skip = {P.plain(x) for x in P.WEAK[LANG] | P.HEADS[LANG]} | set(GENERIC_ALWAYS + GENERIC_IF_LONG) | NUMBER_WORD_SET
    return [w for w in words(s) if not P._is_link(w, LANG) and P.plain(w) not in skip and not P.ROMAN.match(w)]


def qualifier_words(s):
    """Words that tell two places of one name apart: weak words (Upper, New, Old ...),
    numbers written as words and Roman numerals."""
    weak = {P.plain(x) for x in P.WEAK[LANG]}
    return [w for w in words(s) if P.plain(w) in weak | NUMBER_WORD_SET or re.fullmatch(r'I{1,3}|IV|VI{0,3}', w)]


def not_a_place(s):
    """Only weak, landmark or non-place words ("Police", "Upper"), or a possessive
    alone ("Basti's"); a number with a landmark word ("Five Mile") is a place name."""
    ws = words(s)
    if all(P.plain(w) in NOT_A_PLACE for w in ws) or (len(ws) == 1 and re.search(r"['’]s$", ws[0])) \
            or all(P.plain(w) in NUMBER_WORD_SET for w in ws):
        return True
    return not strong_words(s) and not any(P.plain(w) in NUMBER_WORD_SET for w in ws)


def strip_trailing(s, generic):
    """Drop trailing generic words one at a time while the name is over the limit
    ("Samuel Town Village" -> "Samuel Town"; "Adonkia Village" -> "Adonkia")."""
    while not P.fits(s, LANG):
        ws = s.split(' ')
        if len(ws) < 2 or P.plain(ws[-1]) not in generic or not strong_words(' '.join(ws[:-1])):
            break
        s = ' '.join(ws[:-1])
    return s


def drop_town_before_number(s):
    """"Gbondo Town One" -> "Gbondo One": the number stays, "Town" goes (a council candidate)."""
    ws = s.split(' ')
    if len(ws) >= 3 and P.plain(ws[-2]) in GENERIC_IF_LONG and P.plain(ws[-1]) in NUMBER_WORD_SET:
        return ' '.join(ws[:-2] + ws[-1:])
    return s


def flag(r, reason, first=None):
    cs = ([first] if first else []) + [c for c in r['candidates'] if c != first]
    r.update(rule='council', needsCouncilChoice=True, reason=reason, candidates=list(dict.fromkeys(cs))[:3])
    if first:
        r['plate'] = first


def derive_plate(official, freq, avoid, other_names):
    """The plate-name rule (engine/reference/plate_names.py) with Sierra Leone's rules. -> derive() dict.

    Pass 1 drops only the always-generic words (Community, Estate, Area). If the
    name is still over the limit, pass 2 also drops a TRAILING Town / Village /
    Ville. An automatic short form (rule distinctive, or a pass-2 drop) is kept
    only when nothing but landmark and generic words was dropped (never a place
    word, a person's name, a qualifier such as Upper or a number), the result is
    a place name on its own, and it is not the name of another design-stage area
    ("Moyamba Junction" is not Moyamba); otherwise the area goes to the council."""
    prep = prepare(official)
    kw = dict(known=KNOWN, avoid=avoid, avoid_key=E.name_key)
    r = derive_with(GENERIC_ALWAYS, prep, freq, kw)
    if official in KNOWN:
        return r
    r['official'] = official
    pass2 = False
    if not P.fits(r['plate'], LANG) or r['rule'] in ('distinctive', 'council'):
        short = strip_trailing(clean_with(GENERIC_ALWAYS, prep), set(GENERIC_IF_LONG))
        r2 = derive_with(GENERIC_ALWAYS, short, freq, kw)
        if short != clean_with(GENERIC_ALWAYS, prep) and (r2['rule'] in ('as-is', 'cleaned') or r['rule'] == 'council'):
            r2['official'], pass2 = official, True
            r2['candidates'] = list(dict.fromkeys(r2['candidates'] + r['candidates']))
            r = r2
    if r['rule'] == 'as-is' and prep != official.strip():
        r['rule'] = 'cleaned'
    if pass2 and r['rule'] == 'as-is':
        r['rule'] = 'cleaned'
    r['plate'] = re.sub(r'(?<=[A-Za-z])\.$', '', r['plate'])
    r['candidates'] = [re.sub(r'(?<=[A-Za-z])\.$', '', c) for c in r['candidates']]
    base = clean_with(GENERIC_ALWAYS, prep)          # pass-1 cleaned name
    if r['rule'] in ('distinctive', 'cleaned') and not r['needsCouncilChoice'] and r['plate'] != prep:
        kept = {P.plain(w) for w in words(r['plate'])}
        lost = [w for w in strong_words(base) + qualifier_words(base) if P.plain(w) not in kept]
        if r['rule'] == 'distinctive':
            town = r['plate'] + ' Town'
            if (' ' + town + ' ') in (' ' + prep + ' ') and P.fits(town, LANG):
                r['plate'] = town   # "Kandeh Town Extension" -> "Kandeh Town", not "Kandeh"
        if lost:
            flag(r, "shortening drops a place word, qualifier or person's name (%s)" % ', '.join(lost), r['plate'])
        elif not_a_place(r['plate']):
            flag(r, 'the short form is not a place name on its own', r['plate'])
        elif E.name_key(r['plate']) in other_names and (r['rule'] == 'distinctive' or pass2):
            flag(r, 'the short form is the name of another place', r['plate'])
    if r['needsCouncilChoice']:
        # never a number, a weak word or a non-place word alone as a candidate
        ok = lambda c: P.fits(c, LANG) and not not_a_place(c)
        town_first = drop_town_before_number(strip_trailing(base, set(GENERIC_IF_LONG)))
        cs = ([town_first] if town_first != base and ok(town_first) else []) + [c for c in r['candidates'] if ok(c)]
        for c in list(cs):   # "Kandeh Town" before "Kandeh"
            if c + ' Town' in cs:
                cs.remove(c + ' Town')
                cs.insert(cs.index(c), c + ' Town')
        if not cs:
            # no run of whole words fits: the hyphen-free spelling (same name key)
            # and the parts that are place words on their own
            joined = prep.replace('-', '').replace(' ', '')
            if '-' in prep and P.fits(joined, LANG):
                cs.append(joined[:1].upper() + joined[1:].lower())
            cs += [w for w in strong_words(prep) if P.fits(w, LANG) and len(w) >= P.MIN_LETTERS
                   and E.name_key(w) not in avoid and P.plain(w) not in NOT_A_PLACE]
        cs = list(dict.fromkeys(cs))[:3]
        r['candidates'] = cs
        whole = re.sub(r'(?<=[A-Za-z])\.$', '', P._cap(strip_trailing(base, set(GENERIC_IF_LONG)), LANG))
        quals = {P.plain(w) for w in qualifier_words(base)}
        # provisional plate: the first candidate, unless every candidate drops a qualifier
        # (Upper, a number ...): then the cleaned name, still over the limit until the council chooses
        # and never a well-known town elsewhere ("Moyamba Junction" is not numbered as Moyamba)
        keeps = [c for c in cs if quals <= {P.plain(w) for w in words(c)} and E.name_key(c) not in avoid]
        r['plate'] = keeps[0] if keeps else whole
        if quals and not keeps and 'qualifier' not in r.get('reason', ''):
            r['reason'] = 'every short form drops a qualifier (%s)' % ', '.join(sorted(quals))
    return r


def allocate(issuing, key_of):
    """Group issuing areas by key and allocate. -> (by_key, stats)."""
    by_key = collections.defaultdict(list)
    for r in issuing:
        by_key[key_of(r)].append(r)
    names_by_digits, areas_by_digits, comp_by_digits = collections.Counter(), collections.Counter(), collections.Counter()
    recs, qualified = {}, []
    for k in sorted(by_key):
        grp = by_key[k]
        d = E.name_range_digits([r['compounds'] for r in grp])
        if d is None:
            qualified.append(k)
            continue
        recs[k] = E.allocate_name([(r['id'], r['lat'], r['lon'], r['compounds']) for r in grp])
        names_by_digits[d] += 1
        areas_by_digits[d] += len(grp)
        comp_by_digits[d] += sum(r['compounds'] for r in grp)
    rep = [k for k in by_key if len(by_key[k]) > 1]
    big = max(rep, key=lambda k: (sum(r['compounds'] for r in by_key[k]), k)) if rep else None
    stats = {'names': len(by_key), 'repeatedNames': len(rep), 'areasWithRepeatedNames': sum(len(by_key[k]) for k in rep),
             'largestSharedRange': None if not big else {'key': big, 'areas': len(by_key[big]),
                                                         'compounds': sum(r['compounds'] for r in by_key[big]),
                                                         'digits': recs[big]['digits'] if big in recs else None},
             'namesByDigits': dict(sorted(names_by_digits.items())), 'areasByDigits': dict(sorted(areas_by_digits.items())),
             'compoundsByDigits': dict(sorted(comp_by_digits.items())), 'qualified': qualified}
    return by_key, recs, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--areas', default=os.path.join(REPO, 'model', 'design-areas.csv'))
    ap.add_argument('--out', default=os.path.join(REPO, 'model', 'name-ranges.json'))
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.areas, encoding='utf-8')))
    for r in rows:
        r['officialName'] = r.get('officialName') or r['name']
        r['lat'], r['lon'], r['compounds'], r['structures'] = float(r['lat']), float(r['lon']), int(r['compounds']), int(r['structures'])
        r['official'] = r['official'] in ('1', 'True', 'true')
    # -- plate names
    freq = P.word_freq([prepare(r['officialName']) for r in rows], LANG)
    design = json.load(open(os.path.join(REPO, 'model', 'design.json'), encoding='utf-8'))
    towns = [(t['name'], t['lat'], t['lng']) for t in design['referenceTowns']['towns']]
    towns += [(r['officialName'], r['lat'], r['lon']) for r in rows if r['place'] in ('town', 'city')]
    avoid_all = {E.name_key(n) for n in AVOID_LISTED} | {E.name_key(prepare(t[0])) for t in towns}
    official_keys = collections.Counter(E.name_key(r['officialName']) for r in rows)
    for r in rows:
        own = {E.name_key(prepare(t[0])) for t in towns if km((r['lat'], r['lon']), (t[1], t[2])) <= OWN_TOWN_KM}
        own_key = E.name_key(r['officialName'])
        others = {k for k in official_keys if k != own_key}
        d = derive_plate(r['officialName'], freq, avoid_all - own, others)
        r['name'] = d['plate']
        r['plateRule'] = d['rule']
        r['needsCouncilChoice'] = d['needsCouncilChoice']
        r['plateCandidates'] = d['candidates'] if d['needsCouncilChoice'] else []
        r['plateReason'] = d.get('reason', '') if d['needsCouncilChoice'] else ''
        r['plateSource'] = d.get('source', '')
        r['key'] = E.name_key(r['name'])
        r['officialKey'] = E.name_key(r['officialName'])
    issuing = [r for r in rows if not r['official']]
    # Design-stage ids: areas by (plate key, curve position), names by key; 1-based.
    issuing.sort(key=lambda r: (r['key'], E.curve_position(r['lat'], r['lon'])))
    for i, r in enumerate(issuing, 1):
        r['id'] = i
    by_key, recs, after = allocate(issuing, lambda r: r['key'])
    _, _, before = allocate(issuing, lambda r: r['officialKey'])
    keys = sorted(by_key)
    name_id = {k: i for i, k in enumerate(keys, 1)}
    fcc_keys = {r['key'] for r in rows if r['official']}
    # -- aliases: official name key -> plate key, only when it names one plate name and is no other plate's key
    claims = collections.defaultdict(set)
    for r in issuing:
        if r['officialKey'] != r['key']:
            claims[r['officialKey']].add(r['key'])
    aliases, dropped_aliases = {}, []
    for ok, pks in sorted(claims.items()):
        if len(pks) == 1 and ok not in by_key:
            aliases[ok] = next(iter(pks))
        else:
            dropped_aliases.append({'alias': ok, 'plateKeys': sorted(pks) + ([ok] if ok in by_key else []),
                                    'why': 'claimed by two plate names' if len(pks) > 1 else 'is itself a plate name'})
    # -- per-area stats
    over = lambda n: not P.fits(n, LANG)
    before_over = [r for r in issuing if over(r['officialName'])]
    rule_count = collections.Counter(r['plateRule'] for r in issuing)
    flagged = [r for r in issuing if r['needsCouncilChoice']]
    still_over = [r for r in flagged if over(r['name'])]
    changed_len = 0
    repeated = []
    for k in keys:
        grp = by_key[k]
        if k not in recs:
            continue
        rec = recs[k]
        changed_len += sum(1 for r in grp if E.digits_for(r['compounds']) != rec['digits'])
        if len(grp) > 1:
            byid = {r['id']: r for r in grp}
            repeated.append({
                'key': k, 'nameId': name_id[k], 'names': sorted({r['name'] for r in grp}),
                'officialNames': sorted({r['officialName'] for r in grp}),
                'aliases': sorted(al for al, pk in aliases.items() if pk == k),
                'areas': len(grp), 'compounds': sum(r['compounds'] for r in grp), 'digits': rec['digits'],
                'spare': [rec['spareLo'], rec['spareHi']],
                'alsoInFccArea': k in fcc_keys,
                'blocks': [{'areaId': b['area'], 'name': byid[b['area']]['name'], 'officialName': byid[b['area']]['officialName'],
                            'place': byid[b['area']]['place'], 'lat': byid[b['area']]['lat'], 'lon': byid[b['area']]['lon'],
                            'compounds': byid[b['area']]['compounds'], 'lo': b['lo'], 'hi': b['hi']} for b in rec['blocks']]})
    repeated.sort(key=lambda x: (-x['compounds'], x['key']))
    by_areas = sorted(repeated, key=lambda x: (-x['areas'], x['key']))
    sizes = collections.Counter(x['areas'] for x in repeated)

    def first_number(r, rs):   # the area's first issued number (number_area: lo + step div 2)
        b = next(b for b in rs[r['k']]['blocks'] if b['area'] == r['id'])
        step = (b['hi'] - b['lo'] + 1) // max(1, r['compounds'])
        return b['lo'] + step // 2

    def longest_code(name_of, key_of, rs, pool):
        best = None
        for r in pool:
            r['k'] = key_of(r)
            code = f"{name_of(r)} {first_number(r, rs)}"
            if best is None or (P.plate_length(code), code) > (P.plate_length(best[0]), best[0]):
                best = (code, r)
        return {'code': best[0], 'characters': P.plate_length(best[0]), 'said': f"{name_of(best[1])} {E.group_digits(first_number(best[1], rs))}",
                'needsCouncilChoice': best[1]['needsCouncilChoice']}

    _, recs_before, _ = allocate(issuing, lambda r: r['officialKey'])
    out = {
        'country': 'SL', 'tool': 'tools/name_ranges.py', 'input': 'model/design-areas.csv',
        'rule': {'normalise': 'engine/reference/sl_address.py name_key (model/design.json -> names.normalise)',
                 'plateName': 'engine/reference/plate_names.py: at most %d characters and %d words (model/design.json -> names.plate)' % (P.MAX_CHARS, P.MAX_WORDS),
                 'units': E.UNITS, 'spareUnits': E.NAME_SPARE_UNITS, 'maxDigits': E.MAX_DIGITS,
                 'block': 'whole units of 10^(d-2) numbers holding 2 x compounds', 'order': 'area seeds along the national Hilbert curve'},
        'plates': {
            'issuingAreas': len(issuing),
            'officialOverLimit': {'areas': len(before_over),
                                  'over12Characters': sum(1 for r in issuing if P.plate_length(r['officialName']) > P.MAX_CHARS),
                                  'over2Words': sum(1 for r in issuing if P.word_count(r['officialName'], LANG) > P.MAX_WORDS),
                                  'withDigits': sum(1 for r in issuing if re.search(r'\d', r['officialName']))},
            'byRule': dict(sorted(rule_count.items())),
            'needsCouncilChoice': len(flagged), 'stillOverLimit': len(still_over),
            'stillOverLimitNames': sorted({r['name'] for r in still_over}),
            'longestCodeBefore': longest_code(lambda r: r['officialName'], lambda r: r['officialKey'], recs_before, issuing),
            'longestCode': longest_code(lambda r: r['name'], lambda r: r['key'], recs, issuing),
            'longestCodeNotFlagged': longest_code(lambda r: r['name'], lambda r: r['key'], recs,
                                                  [r for r in issuing if not r['needsCouncilChoice']]),
            'aliases': len(aliases), 'droppedAliases': dropped_aliases,
        },
        'before': {'basis': 'official names (the design-stage areas before plate names)', **{k: v for k, v in before.items() if k != 'qualified'}},
        'issuingAreas': len(issuing), 'names': len(keys),
        'repeatedNames': len(repeated), 'areasWithRepeatedNames': sum(x['areas'] for x in repeated),
        'compoundsInRepeatedNames': sum(x['compounds'] for x in repeated),
        'repeatedNamesByAreaCount': dict(sorted(sizes.items())),
        'mostRepeated': [{k: x[k] for k in ('names', 'areas', 'compounds', 'digits')} for x in by_areas[:15]],
        'largestSharedRange': None if not repeated else {k: repeated[0][k] for k in ('names', 'areas', 'compounds', 'digits')},
        'largestSharedRanges': [{k: x[k] for k in ('names', 'officialNames', 'areas', 'compounds', 'digits')} for x in repeated[:15]],
        'namesByDigits': after['namesByDigits'], 'areasByDigits': after['areasByDigits'], 'compoundsByDigits': after['compoundsByDigits'],
        'areasByDigitsPerAreaRule': dict(sorted(collections.Counter(E.digits_for(r['compounds']) for r in issuing).items())),
        'areasWhoseLengthChanged': changed_len,
        'qualified': after['qualified'],
        'fccAreaNames': {'areas': sum(1 for r in rows if r['official']), 'keys': len(fcc_keys),
                         'sharedWithIssuingNames': len(fcc_keys & set(keys))},
        'aliases': aliases,
        'repeated': repeated,
    }
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    with open(a.areas, 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['name', 'officialName', 'place', 'lat', 'lon', 'structures', 'compounds', 'official',
                    'plateRule', 'needsCouncilChoice', 'plateCandidates', 'plateReason', 'plateSource'])
        for r in sorted(rows, key=lambda x: (x['officialName'].lower(), x['lat'], x['lon'])):
            w.writerow([r['name'], r['officialName'], r['place'], f"{r['lat']:.6f}", f"{r['lon']:.6f}", r['structures'],
                        r['compounds'], int(r['official']), r['plateRule'], int(r['needsCouncilChoice']),
                        '|'.join(r['plateCandidates']), r['plateReason'], r['plateSource']])
    print(f"wrote {a.out}: {len(keys)} plate names ({before['names']} official), {len(repeated)} repeated in "
          f"{out['areasWithRepeatedNames']} areas (was {before['repeatedNames']} in {before['areasWithRepeatedNames']}), "
          f"digits by area {out['areasByDigits']} (was {before['areasByDigits']}); rules {dict(rule_count)}, "
          f"council {len(flagged)} ({len(still_over)} still over)")


if __name__ == '__main__':
    main()

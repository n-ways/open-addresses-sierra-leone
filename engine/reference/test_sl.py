#!/usr/bin/env python3
"""Unit-test wrapper: runs every vector in test_vectors.json through sl_address.run_tests,
plus the national-uniqueness property on the whole frozen register (engine/data/register.json)
and the plate-name limit on every area.

  python3 -m unittest engine/reference/test_sl.py      (or: python3 engine/reference/sl_address.py test)
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sl_address as E  # noqa: E402


class Vectors(unittest.TestCase):
    def test_vectors(self):
        self.assertEqual(E.run_tests(), 0)

    def test_register_unique_nationally(self):
        """Every number of every repeated name decodes to at most one area; blocks never overlap."""
        for key, rec in E.load_register()[0].items():
            blocks = sorted(rec['blocks'], key=lambda b: b['lo'])
            self.assertGreaterEqual(blocks[0]['lo'], 10 ** (rec['digits'] - 1), key)
            for a, b in zip(blocks, blocks[1:]):
                self.assertLess(a['hi'], b['lo'], key)
            self.assertLess(blocks[-1]['hi'], rec['spareLo'], key)
            self.assertLessEqual(rec['spareHi'], 10 ** rec['digits'] - 1, key)
            self.assertLessEqual(rec['digits'], E.MAX_DIGITS, key)

    def test_cross_area_typos_rejected(self):
        """A single wrong digit or swap that lands in another same-named area never passes the check."""
        for key, rec in list(E.load_register()[0].items())[:120]:
            for b in rec['blocks']:
                n = (b['lo'] + b['hi']) // 2
                cd = E.check_digit(rec['nameId'], n)
                s = str(n)
                typos = {s[:i] + c + s[i + 1:] for i in range(len(s)) for c in '0123456789'}
                typos |= {s[:i] + s[i + 1] + s[i] + s[i + 2:] for i in range(len(s) - 1)}
                for t in typos:
                    if t == s or t[0] == '0':
                        continue
                    other = E.decode_number(rec, int(t))
                    if other is not None and other != b['area']:
                        self.assertNotEqual(E.check_digit(rec['nameId'], int(t)), cd, (key, n, t))


class PlateNames(unittest.TestCase):
    def setUp(self):
        import json
        self.areas = json.load(open(os.path.join(E.REPO, 'engine', 'data', 'register.json'), encoding='utf-8'))['areas']

    def test_every_confirmed_plate_name_fits(self):
        """Every area not flagged for its council has a plate name of at most 12 characters and 2 words."""
        for a in self.areas:
            if not a['needsCouncilChoice']:
                self.assertTrue(E.plate_name_ok(a['name']), (a['officialName'], a['name']))

    def test_aliases_name_one_plate(self):
        """An official name typed decodes to its one plate name; no alias is also a plate name."""
        reg, aliases = E.load_register()
        for alias, key in aliases.items():
            self.assertNotIn(alias, reg, alias)
            self.assertIn(key, reg, alias)

    def test_engine_rejects_long_names(self):
        for n in ('Connaught Hospital Community', 'Kpandembu Dama Village', 'Mile 91', 'Gbonkobankala'):
            self.assertRaises(ValueError, E.compound_text, n, 1050)


if __name__ == '__main__':
    unittest.main()

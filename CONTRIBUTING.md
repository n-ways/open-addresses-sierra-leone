# Contributing

N-Ways Addressing for Sierra Leone is open to corrections and proposals from anyone: councils and ministries, Freetown City Council, couriers and emergency services, researchers and residents. Write in English; French is welcome.

## What you can propose, and how

| You want to | Do this |
|---|---|
| Report a wrong code, a wrong entrance or a building with no code | Open an issue with the machine code (`SL-03663-15727`) or the point (latitude and longitude), what is wrong and how you know. The N-Ways app accepts the same report from the gate itself. |
| Correct a place name, a spelling or a plate name | Open an issue with the area (`GET /v1/areas/{id}` or `registry/areas.csv`), the proposed name and a source: a council list, a gazette, a signboard photo. Plate names flagged `needs_council_choice` are chosen by the district or city council, with the chiefdom. |
| Fix the engine, the server, the tools or a document | Open a pull request. Keep the reference engine and the server to the Python standard library; run the tests below; explain the change in plain words in the pull request. |
| Change anything frozen (areas, blocks, name ids, reference towns, the rules of `engine/SPEC.md`) | Write a proposal in `docs/` and open a pull request. Frozen parts change only after a 60-day public comment period and the agreement of the maintainers and of any adopting authority (`GOVERNANCE.md`). |

## The rules every change keeps

- **An issued code is never moved, renumbered or reused.** A code can be confirmed, have its entrance moved within 80 m, or be retired; its number is never given to another place.
- **One issuer per country.** Codes are issued only by the issuer N-WAYS LIMITED operates or by the body the State designates. A pull request never adds codes to `registry/` by hand: the registry is the issuer's export, verified against its `MANIFEST.json`.
- **Places, never people.** No names of occupants, phone numbers, identity numbers or household details beyond a count, in any file, issue or pull request.
- **The check digit is for systems.** Plates, documents and screens show the name and the number only.
- **Government addresses first.** Where a public body already addresses properties (Freetown City Council's Plus Codes), its address is shown first, as it writes it.

## Tests

```sh
python3 engine/reference/sl_address.py test
python3 -m unittest engine/reference/test_sl.py
python3 -m unittest discover -s server/tests -t .
```

All three must pass. A change to the engine's behaviour must also update `engine/reference/vectors.json` (`python3 tools/vectors.py`) and say why the vectors changed.

## Licences

By contributing you agree that your contribution is licensed as the part of the repository it changes: Apache License 2.0 for code, ODbL 1.0 for data, CC BY 4.0 for documents (`LICENSING.md`).

Questions: hello@nways.ng.

# N-Ways Addressing for Sierra Leone

**Status: issued on 20 October 2026.** Every compound in Sierra Leone has an N-Ways code: 1,359,282 of them, provisional until residents confirm them in the N-Ways app. Sierra Leone has no postal codes and no national address system; Freetown City Council (FCC) addresses its properties with Plus Codes, so in FCC's area the property's Plus Code is the official address and is shown first, with the N-Ways code beside it. No part of a code depends on a district, chiefdom or ward.

A home's code is **the name of a community or town people already use plus a number said in groups**:

| Remembered | Plate | Machine form | What it is |
|---|---|---|---|
| `Moyamba 15727` | `Moyamba 157 27 · 5H68+3V Moyamba` | `SL-03663-15727` | a compound in Moyamba town |
| `Connaught 2301` | `Connaught 23 01` (after `FQQ6+9G Freetown`, FCC's address) | `SL-00623-2301` | next to Connaught Hospital, Freetown |
| `Masorie 151`, `Masorie 315` | | | two places of one name, 42 km apart: one national range, two blocks |
| (a link) | `5H68+3V Moyamba` | `6CW95H68+3V` | any point: its Plus Code |

The remembered form is unique in the whole country on its own: every place with the same name shares one national number range (3 to 5 digits), cut into blocks of whole units, one per place, with spare kept for future places. A Damm check digit over the name and the number is for systems only; plates show the name and the number. The name is a **plate name** of at most 12 characters and 2 words ("Gbangbatoke 1051" for the area officially "Gbangbatoke Junction"; the official name still finds it). 156 areas wait for their council to choose a short name; their codes are issued with a provisional name, and the number never changes.

The registry is complete: [`registry/`](registry/) holds every issued code, in every district, with its entrance, Plus Code and building summary, and the [registry server](server/) serves it, and issues new codes by the national rules, from one command.

## What is where

| Path | Contents |
|---|---|
| [docs/paper.md](docs/paper.md), [paper.fr.md](docs/paper.fr.md) | the research paper in English and French, with its PDFs (`docs/n-ways-addressing-sierra-leone-en.pdf`, `-fr.pdf`): the model, every formula with worked examples, the evaluation, the designs considered, and what the codes change for citizens, logistics, emergency services and government |
| [docs/paper/](docs/paper/), [docs/figures/](docs/figures/) | the paper's typesetting (LaTeX template, style, bibliography `references.bib`, build script) and its figures (TikZ sources, their data and the compiled PDF and SVG) |
| [docs/api.md](docs/api.md) | the registry API: every endpoint with a real request and response |
| [docs/existing-systems.md](docs/existing-systems.md) | what postal and address systems exist (no postcodes; FCC's Plus Codes in Freetown) |
| [docs/model.md](docs/model.md) | the reasoning behind every choice of the model |
| [engine/SPEC.md](engine/SPEC.md) | the engine specification (normative) |
| [engine/reference/](engine/reference/) | the reference engine (`sl_address.py`, `plate_names.py`; standard library only), its tests and the conformance vectors every implementation must reproduce |
| [engine/data/](engine/data/) | what a decoder ships: `register.json` (reference towns, every area with its plate name, official name, name key, national id and frozen blocks, the aliases) and the national outline |
| [registry/](registry/) | every issued code, one gzip CSV per zone (a 4-character Plus Code area: `6CW8.csv.gz` ...), the frozen area table `areas.csv` and `MANIFEST.json` (counts and SHA-256 of every file) |
| [server/](server/) | the registry server: import, JSON API, issuing, export; Docker and plain Python ([server/README.md](server/README.md), [openapi.yaml](server/openapi.yaml)) |
| [model/](model/) | `name-ranges.json` (every name with its areas, blocks and spare, frozen at first issue), `building-stats.json` (the compound and building statistics of the paper), `design.json`, `stats/` (`register.json`, and `evaluation.json` with the paper's measured properties) |
| [tools/](tools/) | the scripts that built the inputs, the areas, the compounds, the names and the registry ([tools/README.md](tools/README.md)) |
| [GOVERNANCE.md](GOVERNANCE.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) | rules and the single issuer, how to propose a change, how to report a problem |
| [SOURCES.md](SOURCES.md), [LICENSING.md](LICENSING.md), [NOTICE](NOTICE), [CITATION.cff](CITATION.cff) | sources, licences, how to credit and cite |

## Run the server

```sh
docker compose up -d                                   # imports the registry on first start, then serves
curl -s 'http://localhost:8080/v1/find?q=Moyamba%2015727'
```

Without Docker (Python 3.9 or newer, no packages):

```sh
python3 -m server import --registry registry --db data/addresses.sqlite   # checks every file against MANIFEST.json
python3 -m server serve --db data/addresses.sqlite --port 8080
python3 -m unittest discover -s server/tests -t .                         # the server's tests
```

A deployment is read-only unless it is the country's designated issuer ([server/README.md](server/README.md), "One issuer per country").

## Run the reference engine

```sh
python3 engine/reference/sl_address.py test                       # test vectors
python3 -m unittest engine/reference/test_sl.py                   # vectors and the frozen register
python3 engine/reference/sl_address.py decode "Moyamba 157 27"    # decode nationally: area, number, machine form
python3 engine/reference/sl_address.py spot 8.48842 -13.23869     # Plus Code -> FQQ6+9G Freetown
python3 engine/reference/sl_address.py recover FQR7+HX Freetown   # FCC's own office
```

Python 3.9 or newer, no packages (see [requirements.txt](requirements.txt)).

## Build the paper

```sh
python3 tools/paper-figures.py      # the figures' data (docs/figures/*.dat), from engine/data, registry and model
python3 tools/paper-evaluation.py   # model/stats/evaluation.json: uniqueness, decoding, lengths, check-digit slips
sh docs/paper/build.sh              # pandoc, LaTeX (tectonic) and pdftocairo: the figures, then docs/*.pdf
```

## How the registry was made

```sh
python3 tools/prepare-inputs.py <work>              # enclosures, estates, gates, places, seeds, districts, national boundary
python3 tools/extract-buildings.py <work>           # every footprint inside Sierra Leone (DuckDB, 3 GB cap)
python3 tools/assign-areas.py <work>                # each footprint's area and density
python3 tools/sort-buildings.py <work>              # sorted by area
python3 tools/issue_registry.py group <work>        # compounds and profiles, one area at a time
python3 tools/build-register.py <work> --freeze     # plate names, national ranges, blocks
python3 tools/issue_registry.py number <work> <work>/lotes.jsonl.gz
python3 tools/vectors.py                            # engine/reference/vectors.json
python3 tools/paper-stats.py <work> <work>/lotes.jsonl.gz
```

The issuer then numbers every compound again with its own implementation of the engine, refuses any difference from the reference's numbers, and exports `registry/` in the format `python3 -m server export` writes. The register is frozen: a later issue adds codes for new compounds and never renumbers an issued one.

## Licence and credit

Code (engine, server, tools): Apache License 2.0, with [NOTICE](NOTICE). Data (registry, model, engine data): ODbL 1.0. Documents: CC BY 4.0. Credit every use: **"N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)"**, with a link to this repository ([LICENSING.md](LICENSING.md)). Derived from OpenStreetMap (© OpenStreetMap contributors, ODbL), Google Open Buildings (CC BY 4.0) and Microsoft building footprints (ODbL). Contact: hello@nways.ng.

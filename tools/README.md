# Tools: Sierra Leone's registry

All inputs are read-only: the N-Ways map data (the folder named by `NWAYS_ROOT`, with `data/` below it) and the N-Ways map database (`NWAYS_DB`, PostGIS, tables `regions` and `places`). Outside N-Ways, start from the published `registry/` and `model/` instead. Run one heavy step at a time: DuckDB runs with `memory_limit='3GB'` and spills to the work folder; the grouping reads the footprints one area at a time.

| Step | Script | Writes |
|---|---|---|
| 1 | osmium exports (below) | `admin`, `bar`, `place` `.geojsonseq` in the work folder |
| 2 | `prepare-inputs.py <work>` | `enclosures.geojson`, `estates.geojson`, `gates.csv`, `places.csv`, `seeds.csv`, `labels.geojson`, `country.geojson` (the national border), `engine/data/country.geojson` (its simplified outline) |
| 3 | `extract-buildings.py <work>` | `buildings-raw.csv` (every footprint whose centre is inside the national border, with its enclosure, estate, district and places), `enclosure-gates.csv` |
| 4 | `assign-areas.py <work>` | `area-of.csv` (each footprint's area and density), `area-points.csv` (every area) |
| 5 | `sort-buildings.py <work>` | `buildings.csv`, sorted by area |
| 6 | `issue_registry.py group <work>` | `compounds.jsonl.gz` (compounds and profiles; a compound more than 300 m outside the border is dropped and counted as `abroad`), `area-counts.json` |
| 7 | `build-register.py <work> --freeze` | `model/name-ranges.json`, `engine/data/register.json`, `model/stats/register.json` |
| 8 | `issue_registry.py number <work> <work>/lotes.jsonl.gz` | the lotes, tile by tile, with the reference's numbers (it stops at a compound more than 300 m outside the border) |
| 9 | the issuer: numbers the lotes again with its own implementation, refuses any difference, and exports the registry (the format of `python3 -m server export`) | the codes; the registry, gzipped into `registry/` |
| 10 | `vectors.py`, `paper-stats.py <work> <work>/lotes.jsonl.gz` | `engine/reference/vectors.json`, `model/building-stats.json` |
| 11 | `border.py check <work>/country.geojson registry` | nothing: counts the published codes whose entrance is more than 300 m outside the border, and fails if there is one |

`paper-figures.py` and `paper-evaluation.py` read only the published files (`engine/data/`, `registry/`, `model/`) and write the data of the paper's figures (`docs/figures/*.dat`) and its measured properties (`model/stats/evaluation.json`).

`border.py` holds the national border and the border rule (below). `name_ranges.py` holds Sierra Leone's plate-name rules (used by `build-register.py`); `profile_stats.py` produced the design-time statistics in `model/profile-stats.json`.

### The border decides

A code is only ever issued for a building whose entrance is inside Sierra Leone's national border, or within 300 m of it (the line's own accuracy, and gates on the line). The border is OpenStreetMap's admin_level 2 boundary tagged `ISO3166-1=SL`, territorial waters included, taken from the same extract as everything else (`border.py national`, run by `prepare-inputs.py`); an extract also holds parts of a neighbouring country's boundary, and it is never taken. Zone outlines from other sources (geoBoundaries, GADM and the like) may spill over the border; they never decide.

The pipeline applies it three times: `extract-buildings.py` keeps only footprints whose centre is inside the border (stricter than 300 m); `issue_registry.py group` drops any compound whose point (its main structure's centre, the entrance until a gate is confirmed) is more than 300 m outside it; `issue_registry.py number` refuses to write a lote for one. `border.py check` verifies the published registry. The server applies the same rule when it issues (`server/geo.py`, `BORDER_M`), with the simplified outline `border.py simplify` writes to `engine/data/country.geojson`: Douglas-Peucker at 50 m, under 1 MB, its measured distance from the full line recorded as `deviationM`. The server's tolerance is 300 m less that distance (about 245 m), so a point it accepts is never more than 300 m outside the full border.

### osmium exports

```
P=data/osm/sierra-leone-latest.osm.pbf
osmium tags-filter -o b.osm.pbf $P r/boundary=administrative
osmium export -a type,id -f geojsonseq --geometry-types=polygon -o admin.geojsonseq b.osm.pbf
osmium tags-filter -o bar.osm.pbf $P w/barrier=wall,fence,hedge,retaining_wall n/barrier=gate,entrance,lift_gate,sliding_gate,swing_gate n/entrance
osmium export -a type,id -f geojsonseq -o bar.geojsonseq bar.osm.pbf
osmium tags-filter -o place.osm.pbf $P n/place
osmium export -a type,id -f geojsonseq -o place.geojsonseq place.osm.pbf
```

# Engine specification: N-Ways addressing for Sierra Leone

Specification 1.0. The register was issued on 20 October 2026: 1,359,282 codes, one for every compound in Sierra Leone, Freetown City Council's area included, provisional until residents confirm them. Areas, name ids and blocks are frozen; later issues only add. The reference implementation is `engine/reference/sl_address.py` (Python standard library only); `engine/reference/test_vectors.json` and `engine/reference/vectors.json` are normative, and `server/` applies the same rules as a deployable service.

## 0. Government addresses first

**Where a government body already has addresses, the engine shows them first.** In Freetown City Council's area (Western Area Urban, and any council later created from it) the address is the property's Plus Code, FCC's identifier: every compound there carries it as its official address (`coverage: official`, the 10-character Plus Code of its main building, short with its reference town, "FQQ6+9G Freetown"), shown first on every card and plate. Like every compound in the country it also has its N-Ways code, shown beside the official address: a code that can be said, and that tells the buildings of one property apart.

**Import:** (1) FCC agreement for address fields only (Plus Code, location; property ID and footprint if FCC agrees), outside the public repository if FCC's terms require; (2) residents' entries from their FCC document plus a photo, accepted only if `olc_decode(code)` lies on the compound's footprint or within one cell (~14 m) of it. A code imported this way replaces the computed one where they differ. FCC property IDs are never shown publicly.

## 1. Codes

The first design criterion is that people can **remember** their code and **get** it with no effort (`docs/model.md` §1–2): what people remember is a community or town name they already use and a short number; the Plus Code is on the plate, not in the head, and the check digit is for systems only.

| Code | Remembered / written | Plate and forms | Machine form | Points at |
|---|---|---|---|---|
| Compound (everywhere; in FCC's area after FCC's Plus Code) | `Moyamba 15727` | `Moyamba 157 27 · 5H68+3V Moyamba` | `SL-03663-15727` | one plot or yard; navigation ends at its gate |
| Structure | `Moyamba 15727.2` | | `SL-03663-15727.2` | a building in the compound (`.1` main house) |
| Unit | `Moyamba 15727.2/3` | | `SL-03663-15727.2/3` | a flat, room or shop let separately |
| Spot | (not remembered) | `FQQ6+9G Freetown` | `6CW8FQQ6+9G` | a Plus Code cell of about 14 × 14 m; with an 11th character (`FQQ6+9G7`) about 2.8 m north–south × 3.4 m east–west |

- **Area name:** the **plate name** of an N-Ways address area (§4.4b: at most 12 characters and 2 words, no digit), with no administrative parent; the official name is printed small and decodes as an alias. Several areas may have the same name; they share one national number range for that name (§4.4a), so **`(name, number)` identifies exactly one area and compound in Sierra Leone**, with no town, district or position needed. The area id stays unique per area (machine form).
- **Number:** 3–5 digits, never starting with 0, unique among all areas with the same normalised name (it falls in exactly one area's block), written and said in groups (`482`, `27 16`, `157 27`).
- **Check digit:** Damm over the name id and the number (§5), for systems only: returned by the API and accepted after a `·`, never printed on plates or shown to people. A person reads and says the name and the number; a system that stores or transmits a code can add the check to catch typing errors.
- **The gate's Plus Code** is stored on every compound and printed on its plate, so FCC, couriers and any Plus Code app can use it.
- **A spot code is a Plus Code.** `6CW8FQR7+HX`, the Freetown City Council office as FCC prints it (`FQR7+HX`), decodes in any Plus Code app; this engine produces and reads the same strings. A spot code is written with one of 31 fixed **reference towns** (`model/design.json` → `referenceTowns`); any listed town within 0.5° recovers the same place.
- **Parsing:** trailing digits are the number; a final single digit after a grouped number is the check digit; names never end in a digit. A string with `+` is a Plus Code.

## 2. Why the Plus Code grid in Sierra Leone

1. **It is already the de facto property identifier in the capital.** Freetown City Council records 160,000+ properties and uses Plus Codes because "buildings do not always have a reliable street name nor a house number" (FCC Property Reform FAQ). Any other grid would give Freetown residents two unrelated codes for one house.
2. **Sierra Leone's administrative map keeps moving.** The North West Province and two districts were created in 2017; chiefdoms were restored to 190; in October 2026 new districts and city councils were announced. A code built on districts, chiefdoms or wards would go stale with each change. The Plus Code grid and fixed town points never move.
3. **The country fits the short form.** Sierra Leone spans about 3° × 3°; 31 towns, each with a 0.4° reach, cover every one of its building locations, so every Plus Code on a plate needs only 4 + 2 characters plus a town.

The Plus Code is the spot and the gate; it is **not** what people are asked to remember (§1): `FQP5+QW` is a 14 m square that in Kroo Bay can hold several homes, and it has letters that must be spelled.

## 3. Spot codes (Open Location Code)

Encoding, decoding, shortening and recovery follow the Open Location Code specification exactly (`olc_encode`, `olc_decode`, `olc_recover`): five pairs of base-20 digits (20°, 1°, 0.05°, 0.0025°, 0.000125°), then grid digits of 5 rows × 4 columns.

**Shortening (N-Ways rule):** the first four characters are dropped when the point is within **0.4°** of the chosen town on both axes, and the town written after the code. The town is the nearest listed town by that measure. Standard Plus Code libraries shorten only within 0.3°; recovery is exact within 0.5°, so N-Ways' short codes also recover correctly in other Plus Code apps provided those apps place the town within 0.1° (~11 km) of the N-Ways point. Where the 0.3° rule also applies, the short code is identical to what other apps produce.

**Recovery:** take the first four characters of the town's own full code, prepend them, decode, and move by one degree in latitude or longitude if the result is more than half a degree from the town (OLC algorithm).

## 4. Compound registry

### 4.1 Inputs, in order of trust

1. People's confirmations in the N-Ways app (gate, "these buildings are one home", doors, use).
2. Partner data under agreement (Freetown City Council property IDs and Plus Codes; Ministry of Lands survey plans; utilities).
3. OpenStreetMap: buildings, `barrier=wall|fence|hedge` closed rings, gates and entrances, tags.
4. Google Open Buildings and Microsoft footprints (`h` metres).
5. N-Ways places, gated compounds (estates, government, military, police) and gates.

### 4.2 Grouping structures into compounds (before numbering)

1. **Confirmed plots and mapped enclosures** (closed walls or fences): all structures with their centroid inside form one compound (confidence 0.9 confirmed, 0.8 mapped).
2. **Estates and institutional compounds** (N-Ways compounds; e.g. Hill Station, government quarters, barracks) are parents: compounds inside keep their own codes; navigation goes estate gate → compound gate.
3. **Dense hectares:** in any 100 m × 100 m cell (a fixed national grid: x = lon × 111,320 × cos 8.5°, y = lat × 110,574) with more than `DENSE = 70` structures (Kroo Bay, Susan's Bay, Mabella, Colbot, Moa Wharf, the hillside settlements above Kissy, Wellington and Dwarzark), nothing is grouped: each structure is its own compound. Confidence 0.6. These settlements have no walls and shared yards; grouping would merge unrelated households and route people wrongly.
4. **Village yards:** where a hectare has at most `YARD_MAX_HA = 25` structures (rural towns and villages, where a family compound is several houses, huts and a kitchen round a yard), a satellite (< 30 m²) joins the nearest principal (≥ 30 m² and at least twice its size) within `YARD_M = 8 m`. Confidence 0.4.
5. **Town proximity:** elsewhere the same join uses `JOIN_M = 4 m`. Confidence 0.45.
6. Everything else is a single-structure compound (0.5).

Distances between structures are between their outlines (0 when they touch or overlap); within an area, structures are taken in the order of their stable ids, so the result never depends on the order of the map data. Only satellites join, and only principals receive them, so two houses are never joined. Structure `.1` is the largest footprint unless people confirm another main house; others follow by descending area. A shop in the front wall with its own street door is its own structure with its own entrance. **Regrouping never changes an issued code** (merge: the compound with the confirmed gate keeps its code, others become aliases; split: the part with the original gate keeps it).

### 4.3 Anchor and gate

Confirmed gate → mapped gate/entrance within 3 m of the enclosure → where the nearest road or footpath meets the enclosure → main structure's centroid. The gate's Plus Code (10 characters, 11 where two gates share a cell) is stored.

### 4.4 Address areas and numbering

**Areas** (`model/design.json` → `areas`), everywhere: N-Ways' own named zones, frozen at first issue, with **no administrative parent**. Seeds are OSM `place` nodes inside the national boundary (primary: city, town, suburb, quarter, village; secondary: neighbourhood, hamlet, locality, isolated dwelling); a footprint outside the boundary is in a neighbouring country and gets no code (**the border decides**, §7). Each footprint goes to the nearest primary seed within 4 km, else the nearest secondary seed within 15 km, else the nearest primary seed at any distance; a primary area over 4,500 compounds (footprints × 0.779) is split: a footprint moves to the nearest secondary seed within 3 km whose own nearest primary is that area, when it is nearer than the area's seed; an area under 20 compounds folds into the area of the primary seed nearest its seed, within 30 km (`tools/assign-areas.py`). Areas never cross the Sierra Leone River estuary (Freetown peninsula / Lungi and the Bullom shore), the Sherbro estuary, or a river without a bridge. Areas keep the name people use, even when other areas have it too (§4.4a); each area carries an official name and a plate name (§4.4b). Area indexes (5 digits) are given by plate-name key, then the seed's curve position, then the seed id; name ids (4 digits) by key. Both, with the blocks, are published in `engine/data/register.json` and `registry/areas.csv`; an area's tile is its seed's 4-character Plus Code area.

**Digits:** the length `d` of the area's **name range** (§4.4a), fixed at first issue.

**Order and spacing (`number_area`):** one Hilbert curve (order 16) over a fixed national frame (6.85°N–10.05°N, 13.35°W–10.20°W), by anchor; inside the area's block `[lo, hi]`, compound `i` of `N` gets `lo + i × step + step div 2`, `step = (hi − lo + 1) div N`. **Later additions (`next_free_number`):** the free number halfway between curve neighbours, inside the block; a full block takes a further block from the name's spare (`add_block`); nothing is renumbered.

### 4.4a National name ranges (same-named areas)

The remembered code must be unique in the whole country on its own. Ranges are per **plate name** (§4.4b). At first issue (`model/name-ranges.json`, `tools/build-register.py`): 5,184 areas, 3,706 plate names, **590 names shared by 2,068 areas**; 2,945 names on 3 digits, 720 on 4, 41 on 5.

1. **Normalisation (`name_key`)**, English and Krio: Unicode NFKD, accents removed, casefolded; apostrophes removed; `- _ . , / ( )` → space; words folded: `tong→town`, `kru→kroo`, `saint→st`, `mount→mt`, `&→and`, `one…ten→1…10`, `ii→2`, `iii→3`; a leading `the` dropped; then all spaces removed. Two areas with the same key have the same name. The fold list is frozen in `model/design.json` → `names.normalise`; adding a fold later never merges two names that already have issued blocks (the second name keeps its own range under an alias key).
2. **Range:** a name with range length `d` owns the numbers `10^(d−1) … 10^d − 1`, cut into `UNITS = 90` units of `10^(d−2)` numbers.
3. **Blocks (`allocate_name`):** each area gets `max(1, ⌈2N / 10^(d−2)⌉)` whole units, in the order of the area seeds' curve positions (ties by area id), packed from the bottom of the range. At least `NAME_SPARE_UNITS = 9` units stay free at the top (the name's spare). `d` is the smallest of 3, 4, 5 with `Σ blocks + 9 ≤ 90`.
4. **Qualifiers:** if no `d ≤ 5` fits, the name is split once, before first issue, into established names people already use (listed in `model/design.json` → `names.qualified`, each with its areas); each split name then gets its own range. Sierra Leone's list is empty (largest shared range: Kpetema, 7 areas, 10,116 compounds, 5 digits).
5. **Decoding (`decode_number`, `verify`):** `name_key(name)` → the name record; the number's length selects the range (the name's base range or a longer extension); the block containing the number gives the area; a number in the spare or in no block is "no such address". Never decoded by position or context.
6. **Frozen (`add_block`):** blocks never move or shrink and are never renumbered. A new area with the name, or an area whose block is full, takes the next whole units from the bottom of the spare. When the spare is too small, the name opens an extension range of `d + 1` digits (its own 90 units and spare; numbers of different lengths cannot collide); beyond 5 digits the new area takes one of the name's listed qualifiers.
7. **FCC's area:** its 134 areas take blocks like every other (§0: FCC's Plus Code is shown first, the N-Ways code beside it).

### 4.4b Plate names

1. **Two names per area.** `officialName` (map or council list; printed small on cards and plates, never required) and `name`, the **plate name** used in the code, the name key and the range.
2. **Limit (`plate_name_ok`, `check_plate_name`):** at most `MAX_CHARS = 12` characters of the NFC form (letters, spaces, hyphens, apostrophes; an accented letter is one) and at most `MAX_WORDS = 2` words (parts between spaces or hyphens other than `of`, `the`, `and`, `on`, `at`), and no digit. `compound_text` and `plate` raise on a longer name, so no plate is printed with one; an area whose provisional name is still over the limit keeps its codes under that name until the council chooses (4.).
3. **Derivation** (`tools/name_ranges.py`, with `engine/reference/plate_names.py`, language `en`): spelling clean-up (", Sierra Leone", `*`, spaced dashes, capitals, bracketed Roman numerals kept, digits as words); Community, Comm, Estate, Area and bracketed text dropped; a trailing Town, Village or Ville dropped only while the name is over the limit; then landmark words (Junction, Wharf, Street, Corner, Quarry, Line, Mosque …). Words are never cut; `St`/`Mt` abbreviations would be expanded back by `name_key`.
4. **Council (`needsCouncilChoice`):** when shortening would drop a place word, a person's name, a qualifier (weak words such as Upper, Small; numbers; Roman numerals), or give another area's name, a well-known town (avoid list, own town within 5 km allowed) or a word that is no place name alone, the area keeps up to 3 `plateCandidates` and a `plateReason`. It is numbered provisionally under the first candidate that keeps every qualifier and is no avoided town, else under its cleaned name (then over the limit until the council chooses). The district or city council, with the chiefdom, chooses later; the area's codes are issued with the provisional name, and its numbers never change. At first issue: 235 official names over 12 characters; 4,890 as-is, 115 cleaned, 23 distinctive, 156 council (42 still over the limit; 84,311 codes).
5. **Known short forms** (`known`, each with a source) take precedence; Sierra Leone's list is empty.
6. **Aliases (`resolve`):** `name_key(officialName)` → the plate name's key when it belongs to exactly one plate name and is not itself a plate name; otherwise it is dropped and listed (`plates.droppedAliases`). 169 aliases, none dropped.

### 4.5 Building and compound profiles

With Sierra Leone's taxonomy (`model/design.json` → `profile`): each attribute is `{value, source, confidence, confirmed}`.

- **Structure:** `use`, `footprintM2`, `perimeterM`, `heightM` + `heightSource`, `floors`, `floorAreaM2`, `material`/`roof`, `entrances[]` (each with its Plus Code), `name` (businesses and public buildings only), `status` (`in-use`, `under-construction`, `uncompleted-shell`, `ruin`, `demolished`), `fccPropertyId` (only with FCC's agreement), `fccPlusCode`.
- **Compound:** `kind` (`one-household`, `multi-household`, `family-yard`, `mixed`, `commercial`, `public`, `unknown`), `plotM2`, `structures`, `floorAreaM2`, `gates[]`, `households` (count only), `estate`, `rule`, `confidence`.

### 4.6 Use inference (Sierra Leone)

| Signal | Confidence |
|---|---|
| Person confirmation | 0.95 |
| Partner record (e.g. FCC property use) | 0.9 |
| OSM `amenity`/`shop`/`office`/`tourism` on the outline | 0.85 |
| OSM `building=*` other than `yes` | 0.85 (`house` 0.8) |
| One N-Ways place inside (two or more: 0.6) | 0.7 |
| OSM material `mud` | 0.6 |
| Footprint < 6 m² → `ancillary`; ≥ 2,000 m² → `commercial.warehouse` | 0.35 |
| Nothing → `unknown` | 0 |

Residential sub-forms: corrugated-iron walls (`metal`, `zink`, `tapoline`) → **pan body** (Krio *pan bodi*); `mud` → mud house; `hut` / thatch → round hut; three or more levels → storey building; `construction` → under construction (the many uncompleted block houses that FCC does not assess are `uncompleted-shell` once confirmed).

## 5. Check digit

`check = damm(name id as 4 digits ‖ number)`, with the standard order-10 totally anti-symmetric quasigroup (table in `sl_address.py`). It **binds name, number and area**: the name id fixes the name, and the area is the one whose block holds the number, so a check is valid for exactly one area. Because every area of one name shares the same prefix, Damm's guarantee covers them all: every single wrong digit and every swap of two neighbouring digits is rejected, **including those that land in another same-named area** (checked on 40 numbers per block of the register: 582,688 cross-area typos, 0 accepted; `damm(name id ‖ area id ‖ number)` would have accepted 61,619 of them, which is why the area id is not written into the check). A right number under the wrong name fails 9 times in 10. The check digit is for systems only: it is carried in machine records and API responses, verified whenever it is given (a wrong check is refused, never corrected), never required, and never printed on plates or shown to people. Plus Codes carry no N-Ways check, so that they stay identical to FCC's; their syntax (alphabet, separator) is validated.

## 6. Lookup

- Text: `parse_compound` splits area name, number, optional check digit, `.structure`, `/unit`; when the name could end in a number (an official name such as "Mile 91" typed with its home number), every split of the trailing digit groups is tried, the longest number first, and the first that names an area whose block holds the number wins; the name is normalised (`name_key`) and looked up nationally as a plate name, else as an official-name alias (`resolve`); the number's block gives the one area (§4.4a), the check digit is verified if given, and the area's tile file gives the compound. The user's position is never used to choose between same-named areas. A string with `+` is a Plus Code, decoded with its town. Unknown town names are matched against `aliases` and the N-Ways gazetteer; if the town is missing, the app uses the user's location as the reference, like any Plus Code app.
- Reverse: confirmed plot or enclosure → footprint → spot code.
- FCC property ID or an FCC-printed Plus Code → the compound recorded with it.

## 7. Offline and data files

| File | Content |
|---|---|
| `engine/data/register.json` | the reference towns, every area (index, plate and official names, name key and id, blocks, seed, district, FCC flag, tile) and the aliases (~1.5 MB) |
| `engine/data/country.geojson` | the national border (OpenStreetMap's admin_level 2 boundary of Sierra Leone, `ISO3166-1=SL`, territorial waters included), simplified to about 50 m (under 1 MB), with its measured distance from the full line (`deviationM`) |
| `model/name-ranges.json` | every name with its areas, blocks, spare and plate-name rule |
| `registry/<tile>.csv.gz` | every issued code per 4-character Plus Code area (~111 km): code, written form, zone, entrance, Plus Code, FCC address, class, use, kind, structures, floor area, rule, estate |
| `registry/areas.csv`, `MANIFEST.json` | the frozen areas and blocks; counts and SHA-256 of every file |

Plus Codes need nothing but the town list. Compound codes need the register.

**The border decides.** A code is only ever issued for a building whose entrance is inside the national border or within 300 m of it (the line's own accuracy, and gates on the line). The border is OpenStreetMap's admin_level 2 boundary of Sierra Leone; zone outlines from other sources (geoBoundaries, GADM and the like) may spill over it and never decide. The build drops every footprint whose centre is outside the border and every compound more than 300 m outside it (`tools/border.py`, `tools/README.md`); an issuer refuses a point more than 300 m outside it, even where an area's seed or a Plus Code would place it (§8.1). With the simplified outline the tolerance is 300 m less its `deviationM`, so an accepted point is never more than 300 m outside the full border. Every published code's entrance is inside the border.

## 8. "Add my home" (new compounds)

The flow, with Sierra Leone's survey facts:

1. **Gate:** GPS averaged for at least 10 s at the gate, plus one gate photo.
2. **Outline:** tap corners on imagery; or walk the boundary with ARKit/ARCore world tracking (centimetre relative shape, placed by GPS averaged over the walk, checked against imagery and footprints; raw phone GPS is 3–10 m); or import a survey plan's beacons. Sierra Leonean plans are drawn by licensed surveyors and lodged with the Ministry of Lands, Housing and Country Planning; under the National Land Commission Act 2022 the Commission's Cadastral Index Mapping Department will keep cadastral index maps. Coordinates are usually on the **Sierra Leone 1968** datum, UTM zone 28N (EPSG:2161) in Freetown and the west, zone 29N (EPSG:2162) east of 12°W; older plans may use the 1924 War Office grid. The person picks the datum; WGS 84 is never assumed. The published 1968 → WGS 84 transformation is ±15 m per axis, so an imported plan is still checked against imagery.
3. **Describe:** households (count), structures, floors, use.
4. **Address at once:** a provisional number, the next free number in the area's block (§4.4); a new area with an existing name first takes a block from the name's spare (§4.4a). In Freetown the official address is the FCC Plus Code from the owner's FCC document (checked as in §0), else the gate's Plus Code until FCC registers the property.
5. **Confirmed** by deliveries/arrivals at the gate, new imagery or footprints, or 30 days without a neighbour's dispute.

Checks: gate on the outline (± 3 m); closed loop; GPS and AR agree (centroid within 5 m, area within 15%). The issuer then applies §8.1. Hillside plots in dense hectares (§4.2) are added as single structures, not plots, unless walled.

The flow states that **a code is an address, not a land title**, and is no evidence in a land dispute. Only the outline and gate photo are kept. Offline: the spot code (a Plus Code) is shown at once; the compound code is issued on the next connection.

### 8.1 Issuer rules

These are the rules of the national issuer, which `server/` applies unchanged (its tests replay cases computed by the issuer):

0. **The border decides:** a point more than 300 m outside the national border is refused (`outside_country`), whatever area or Plus Code it would have (§7).
1. **Already has a code:** a point within 3 m of an issued compound's entrance or outline, inside an outline, or an outline covering more than half of an issued compound's outline (or half of its own area) is not issued: the existing code is returned. Retired codes do not count.
2. **Outline:** 6 m² to 2 ha.
3. **Another door** of a compound (`of`): within 80 m of its entrance; same area.
4. **Area:** the nearest primary seed within 4 km, else the nearest secondary seed within 15 km, else the nearest primary seed (§4.4).
5. **Number:** `next_free_number` in the area's first block with room; then a new block from the name's spare holding twice the area's compounds (`add_block`, §4.4a), its middle number first; a name full at 5 digits takes a qualifier before more codes are issued.
6. **Record:** `status: provisional`, `issued: on-demand`; the entrance is the point (`centre`, or `door`); in FCC's area the point's Plus Code is also the official address.
7. **One issuer:** numbers are unique because one register decides them; only the deployment designated by the State or by N-WAYS LIMITED issues, every other runs read-only (`server/README.md`).

## 9. Privacy

As in `docs/model.md`: codes, outlines, gates and building profiles describe places; no occupant names, phones, IDs or household details beyond a count; residential names never stored; a household may make its gate private (its code then resolves to the area, not the gate).

## 10. Conformance

An implementation conforms if it reproduces every vector in `engine/reference/test_vectors.json` and `engine/reference/vectors.json` (including the Plus Code vectors, which any OLC library must also pass, and the name-key, allocation and decode vectors in which two same-named areas — two Looking Towns, five Moyambas, and two Masories whose names meet only after shortening — decode to different places, and the plate-name vectors: long official names to their plate names, names the engine refuses), uses the frozen town list and name register, and never issues, moves or reuses a compound code or block outside §4.4–4.4a. `python3 -m unittest engine/reference/test_sl.py` also checks the frozen register: no overlapping blocks, no number decoding to two areas, no cross-area typo accepted, every confirmed plate name within the limit, every alias pointing to one plate name.

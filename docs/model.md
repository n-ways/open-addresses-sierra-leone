# The Sierra Leonean model

These notes give the reasoning behind each choice of the model issued on 20 October 2026 (1,359,282 codes). The figures in §3.3 and §4 were measured on the design-stage areas before issue (`model/profile-stats.json`); the issued figures are in `model/building-stats.json` and `model/stats/register.json`. Where these notes and `engine/SPEC.md` differ, the specification is normative.

**Settled at issue:**

- every compound has an N-Ways code, Freetown City Council's area included, with FCC's Plus Code shown first there: a code that can be said is as useful in Freetown as anywhere, and FCC's code stays the official address;
- blocks are cut from the 1,359,282 compounds actually grouped, not from footprints × 0.779;
- footprints and seeds outside the national boundary are dropped;
- the machine-learned footprints' height is a filler and gives no floors;
- names ending in a number decode with every split ("Mile 91 1001").

This is Sierra Leone's own model, designed from Sierra Leone's facts: no postcodes, Freetown City Council's Plus Codes, an administrative map that keeps being redrawn, Freetown squeezed between the hills and the sea, Lungi across the estuary, and Krio as the language everyone shares.

## 0. The rule: government addresses first

**Where a government body already has addresses, N-Ways shows them first, exactly as the government writes them.** The N-Ways code sits beside the official address, as a code that can be said and that tells the buildings of one property apart.

| Where | Address used | N-Ways issues |
|---|---|---|
| **Freetown City Council's area** (Western Area Urban; if it is divided between two councils, as approved in 2025, each takes FCC's place for its part) | **FCC's Plus Code** for the property, exactly as FCC writes it (`FQR7+HX`, with "Freetown"), and the street address where the street is named and numbered (`7A Ross Road`) | **N-Ways codes beside FCC's Plus Code**, which is shown first; and the layers FCC's register does not provide: compound, gate, structures, flats and wall shops, and building profiles |
| Any other council that is found to address properties (Bo, Kenema, Makeni, Koidu … — not verified) | That council's identifier, as written | Same as Freetown |
| **The rest of the country** (Western Area Rural, Lungi and every province) | Nothing official at door level; no postcodes | **N-Ways codes**: a community name and a number (`Moyamba 15727`) |

If SALPOST, the Ministry of Communication, Technology and Innovation or the National Land Commission launches an official address or postcode, the same rule applies: it becomes the official address and is shown first, and the N-Ways codes stay valid beside it (a code is never reused for another place).

## 1. Design criteria, in order

0. **Government addresses first** (§0).
1. **Easy to remember, effortless to get.** A code is a community or town name people already use, in a short form of at most 12 characters and 2 words (§4.2), and a short number: `Moyamba 157 27`. **The name and number alone are unique in Sierra Leone**: nobody has to add a district, a town or a comma, and the app never needs to know where the person is (§4.1). The app shows "Your home code" (with FCC's Plus Code first in Freetown) without being asked.
2. **The same grid as Freetown City Council.** Every N-Ways spot code is a Plus Code; every compound record and plate carries its gate's Plus Code.
3. **No dependence on boundaries that move.** Provinces were reorganised in 2017 (North West Province, Falaba and Karene districts, chiefdoms restored to 190) and new districts and councils were approved by Cabinet in 2025. No part of an N-Ways code uses a province, district, chiefdom or ward.
4. **Compound and door level**, 5. **Stable**, 6. **Open, offline and private.**

## 2. Using Freetown City Council's addresses

### 2.1 Where the data is and on what terms

- FCC's property register (more than 160,000 properties, measured from satellite imagery, each identified by a Plus Code and a property/business ID) is held by Freetown City Council (City Hall, 17 Wallace Johnson Street; fcc.gov.sl). It is not published as open data, and it is a rates register: owners, valuations and payments are confidential. No licence terms for reuse were found (checked in October 2026).
- FCC Plus Codes are printed on what FCC gives owners (FCC gives its own office as `FQR7+HX`). Street names and numbers exist on central streets.

### 2.2 How N-Ways imports them

1. **Agreement with FCC (the goal).** Only the address fields — property Plus Code, location, and if FCC agrees the property ID and footprint — under FCC's terms; never owners, valuations or payments. If FCC's terms do not allow republication, these fields stay out of the public repository and are used only inside the app.
2. **From residents, until then.** A resident types the Plus Code from their FCC document or plate and takes a photo. Because Plus Codes are an open algorithm, the engine checks that the code's cell lies on or next to the compound's footprint (within one cell, ~14 m); if it does, the record is `source: person`, shown as "FCC Plus Code (from your document)", and confirmed by arrivals at the gate. The FCC property ID is **never shown publicly** (it links to the rates account).
3. **Street addresses** from FCC street naming and OpenStreetMap `addr:*` tags, shown as written.

### 2.3 How N-Ways shows them

Exactly as written and labelled: **"FCC Plus Code: FQR7+HX Freetown"**, **"7A Ross Road, Cline, Freetown"**. N-Ways' layers sit beside them in plain words ("Building 2 of 3", "Shop in the front wall", "Gate on Ross Road"), never appended. Where FCC's code is not yet known, the app shows the **Plus Code of the gate** (the same open grid FCC uses), labelled "Plus Code (location)", not "FCC address". The N-Ways code is printed beside FCC's code, as the code that can be said; FCC's code stays the official address.

## 3. Remembering: why "Moyamba 157 27"

### 3.1 What Sierra Leoneans already remember

- **Community and town names.** People say where they live by community and town. OpenStreetMap holds 9,316 named places in Sierra Leone (7,178 hamlets, 1,501 villages, 96 isolated dwellings, 68 towns, 95 suburbs, 349 neighbourhoods), 282 of them in and around Freetown.
- **Numbers in groups.** Phone numbers (`+232 76 …`) are memorised and read in pairs or threes in Krio ("fo-et-tu").
- **Plus Codes are copied, not remembered.** `FQR7+HX` is precise but has letters and a `+`.

### 3.2 Options compared

| Option | Example | What a person must learn | Any keypad, any language | Fits? |
|---|---|---|---|---|
| A. Area name + number | `Moyamba 157 27` | 3–5 digits | yes | yes (§3.3, §4.1) |
| B. Plus Code (short form) | `5H68+3V Moyamba` | 6 symbols incl. letters | letters must be spelled | a 14 m square, not a home |
| C. Block + alphanumeric serial | `5H68-G2V Moyamba` | 7 symbols | letters | yes |
| D. Digits only, national | `20512716` | 8 digits, no meaning | yes | yes |

**Option A is chosen**, with the gate's Plus Code printed under it on plates (`Moyamba 157 27 · 5H68+3V Moyamba`); the Plus Code is not to be remembered, and the check digit is for systems only, never printed.

### 3.3 The arithmetic

- **1,615,149 buildings** inside the province outlines (830,924 OpenStreetMap + 784,225 Google/Microsoft; 1,629,276 in the national extract); the Western Area has 481,038 of them on 694 km².
- Sized one area at a time, an area of `N` compounds would need the smallest `d ≥ 3` digits with `9 × 10^(d−1) ≥ 2N`: 3 digits to 450 compounds, 4 to 4,500, 5 to 45,000. **The issued length is the length of the area's name range (§4.1)**: all areas with the same name share one national range, so a name's length depends on all its areas together.
- Applied to all 1,629,276 mapped structures (≈ 1,269,195 compounds at 0.779 compounds per structure, measured in the capital), the rules give **5,240 design-stage address areas** (47 large areas split among their neighbourhoods, 1,506 tiny ones folded into neighbours): 4,611 with 3 digits (38% of compounds), 616 with 4 digits (56% of compounds), 13 with 5 digits (6% of compounds); the median area holds 83 compounds (90th percentile 551, largest 9,844). **154 of these areas (180,412 compounds) lie in Freetown City Council's area (Western Area Urban).** The design first left them to FCC's Plus Codes and sized the other **5,086 areas (1,088,783 compounds)**; at issue FCC's area was numbered as well (§0). The 5,086 areas outside it: 4,576 areas with 3 digits (43% of compounds), 498 areas with 4 digits (50% of compounds), 12 areas with 5 digits (7% of compounds). The largest are Makeni (9,844, 5 digits), Kpetema (9,463, 5 digits), Koidu (7,790, 5 digits), Port Loko (6,625, 5 digits), Robani (6,611, 5 digits), Ida (6,548, 5 digits). Names such as quarters named after an institution need residents' confirmation before freezing.
- **With plate names (§4.2) and national name ranges (§4.1)** (`model/name-ranges.json`): the 5,086 issuing areas carry **3,627 distinct plate names**; **581 names repeat, in 2,040 areas** (431,342 compounds). Lengths become: **3,537 areas with 3 digits** (31% of compounds), **1,384 with 4 digits** (55%), **165 with 5 digits** (14%); by name, 3,040 names use 3 digits, 561 use 4 and 26 use 5. 1,074 areas get a longer number than they would alone (1,041 because they share their name, 33 single-name areas because every name keeps a tenth of its range spare); none needs more than 5 digits and **no name needs a qualifier**. With the raw map names (before plate names) it was 3,661 names, 569 repeated in 1,994 areas, and 3,556 / 1,378 / 152 areas with 3 / 4 / 5 digits.

### 3.4 Saying it

Digits in Krio or English, in the printed groups: `482` → "fo-et-tu"; `27 16` → "tu-sevin, wan-siks" or "twenti-sevin, sikstin". Mende and Temne speakers usually give phone numbers with Krio/English numerals; the digits are written the same whatever is spoken (to be confirmed in the field test). Area names as residents say and spell them; variants are aliases.

## 4. Address areas

- **No administrative parent.** Areas are N-Ways' own named zones, frozen at first issue; district, chiefdom and city council are attributes that follow every redistricting.
- **Seeds:** towns, suburbs, quarters, villages first; neighbourhoods, hamlets, localities to split big areas and name remote ones.
- **Assignment:** nearest primary place within 4 km, else nearest secondary place within 15 km; areas over 4,500 compounds split among the neighbourhoods inside; under 20 compounds fold into a neighbour.
- **Water:** areas never cross the Sierra Leone River estuary — **Lungi** and the Bullom shore, an hour or more from Freetown by ferry or water taxi, keep their own areas even where a Freetown seed is nearer across the water — nor the Sherbro estuary (Bonthe on Sherbro Island) or rivers without a bridge.
- **Repeated names** share one national number range (§4.1); no area is renamed to make it unique.
- **A name with a digit** writes it as a word (`Badasuma 2` → plate name `Badasuma Two`), so the number is always last.
- **Every area has a plate name** of at most 12 characters and 2 words (§4.2); the official name stays on the record.


### 4.1 One name, one national range: the code is unique on its own

"Looking Town 13316" must mean one door whoever says it and wherever they are. Sierra Leone repeats place names heavily: of the 5,086 design-stage areas outside FCC's area, **2,040 share their plate name with at least one other** — **581 repeated names**, 313 of them in two areas, 110 in three, and up to 28 areas for **Madina**, 24 for **Baoma**, 23 each for **Nyandehun** and **Sembehun** and 21 for **Taninahun**. Big towns share their names with hamlets: there are 5 Moyambas, 7 Kenemas, 3 Koidus, 2 Makenis. Telling them apart by context (the app's position) or by adding a town was considered and rejected: a code must mean the same thing wherever it is said. Instead:

1. **What counts as the same name** (compared on plate names, §4.2) (English and Krio spellings, `name_key` in the engine, listed in `model/design.json` → `names.normalise`): case, accents, apostrophes, hyphens, dots and spaces are folded; a leading "The" is dropped; Krio and English forms of the same word are one (`tong` = `town`, `Kru` = `Kroo`, `Saint` = `St`, `Mount` = `Mt`, `&` = `and`); number words, Roman numerals and digits are one (`Koya Town 2` = `Koya Town Two` = `Koya Town II`). So `Ka-Sasi` and `Kasasi`, `Moriba Town` and `Moribatown`, `FANKOYA` and `Fankoya` are one name (6 such spelling pairs occur in the design-stage areas). Shortening also joins names: `Masorie Community` (plate name `Masorie`) shares the Masorie range with the village called Masorie 42 km away. Different words stay different (`Kissy` ≠ `Kissy Town`).
2. **One national range per name.** Every area with that name draws its numbers from one range of `d` digits (no leading zero), cut into 90 **units** of `10^(d−2)` numbers (10 for 3 digits, 100 for 4, 1,000 for 5). Each area gets a **block** of whole units holding twice its compounds (half the block stays free for new houses, as before). Blocks are laid out in the order of the areas' seeds along the national Hilbert curve; at least **9 units (10%) of every name's range stay unallocated** as the name's spare, for future areas of the same name. A name takes the smallest `d ≥ 3` that fits.
3. **So "name + number" decodes to exactly one area and compound anywhere in Sierra Leone.** In the frozen register the five Looking Towns share one 5-digit range: the one in Western Area Rural holds 13000–13999, the four in Freetown 10000–12999, 14000–18999, 19000–19999 and 20000–21999. `Looking Town 133 16` and `Looking Town 153 16` are different places, and `Looking Town 253 16` is no place (spare). Moyamba town holds 12000–20999, the Moyamba village in Sanda Loko (Bombali) 21000–21999.
4. **Numbers stay at most 5 digits.** A 5-digit range holds about 40,500 compounds; the largest shared range in Sierra Leone is **Kpetema: 7 areas, 10,116 compounds, 5 digits** (then Makeni 2 areas / 9,852, Koidu 3 / 7,909, Baoma 24 / 7,458, New London 7 / 7,230). 17 repeated names use 5 digits (16 with the raw names).
5. **Qualifiers only where a name cannot fit.** If a name's areas together do not fit in 5 digits, the name is split once, before first issue, into established names people already say (a quarter or section name residents already use), and the list is published in `model/design.json` → `names.qualified`. **In Sierra Leone today that list is empty**; it is decided once per name and never changes.
6. **Frozen at issue.** A name's blocks never move and are never renumbered. A new area with an existing name (a new settlement) gets the next units from the name's spare; a full block takes a further block the same way. If the spare runs out, the name opens a range one digit longer (numbers of different lengths never collide), up to 5 digits; beyond that the new area takes one of the name's listed qualifiers.
7. **The check digit binds name, number and area** (§5 of `engine/SPEC.md`): Damm over the 4-digit national name id and the number. The area is fixed by the block the number falls in, so every single mistyped digit and every swap of neighbours is rejected, including the ones that would land in **another same-named area** (Damm guarantees this when the digits before the number are the same, which they are for every area of one name; checked on 40 numbers in every block of the register: 582,688 such typos, none accepted. Writing the area id into the check as well would have let 61,619 of them through). A system that carries `Looking Town 13316` with its check 2 rejects the mistyped `Looking Town 15316` with the same check (its own is 6), instead of sending a courier to another Looking Town.

Other parts of the everyday form are not needed for uniqueness: the official name printed small on the plate is context only; the gate's Plus Code and its town on the plate are for finding the gate, never part of what is remembered, and the remembered `Moyamba 157 27` is unique without them.

### 4.2 Plate names: short names in the code

The rule: the name in a remembered code is at most **12 characters** (letters and spaces; a hyphen or apostrophe counts as one; an accented letter as one) and at most **2 words** (a hyphen separates words; `of`, `the`, `and` do not count), and it has no digit. Taken raw from OpenStreetMap, **225 of the 5,086 issuing areas** break it: 196 have more than 12 characters, 50 more than 2 words, 35 a digit (`Connaught Hospital Community`, `Kpandembu Dama Village`, `Bumbuna Town, Sierra Leone`, `Mile 91`).

So every area has two names (`registry/areas.csv`: `plate_name` and `official_name`):

- **`officialName`**: the name on the map (later the council's list), printed in small type on cards and plates for context, never required;
- **`name`, the plate name**: what people say and type, used for the national range (§4.1).

The plate name is derived by `tools/name_ranges.py` with the rule in `engine/reference/plate_names.py` (language `en`: Sierra Leone's names are English and Krio, with Temne, Mende, Limba and other words), in this order:

1. **Spelling**: ", Sierra Leone" and a leading `*` dropped; spaced dashes joined (`Tombo - Banka` → `Tombo-Banka`); names typed in capitals written in title case; a bracketed Roman numeral kept as a word (`Kemedugu (II)` → `Kemedugu II`); a digit written as a word (`Badasuma 2` → `Badasuma Two`; `name_key` folds it back).
2. **Always dropped**: Community, Comm, Estate, Area, other text in brackets (`Bumbe (at Bridge)` → `Bumbe`).
3. **Town, Village, Ville**: dropped only at the end of a name that is still over the limit (`Adonkia Village` → `Adonkia`, `Mar Jay Town` → `Mar Jay`). Wherever the name fits, Town stays: many Sierra Leonean names are "X Town" said whole (Allen Town, Congo Town, Murray Town, Kissy Town, which is not Kissy), and no source was found showing that the short form is what people say.
4. **Landmark words** go first when a name is still too long: Junction, Wharf, Street, Corner, Quarry, Line, Mosque, Landing, Terrace, Prison … (`Gbangbatoke Junction` → `Gbangbatoke`, `Benkiya Wharf` → `Benkiya`); a word is never cut.
5. **To the council, never automatic** (`needsCouncilChoice`, up to 3 `plateCandidates`, a `plateReason`): shortening that drops a place word or a person's name (two-part Mende and Temne names such as `Blama Massaquoi`, `Jaiama Nimikoro`, `Petifu Mamaso`), a qualifier (`Upper Komende`, `Small Kampala`) or a number (`Magbesseh 1`, `Mile 91`); a short form that is the name of another area (`Moyamba Junction`, `Kent Junction`, `Hastings Quarry`) or a well-known town (the avoid list: district headquarters and big towns, the 31 reference towns, every area mapped as a town or city, and the neighbouring countries and their capitals; an area's own town within 5 km is allowed); a short form that is no place name alone (`Police Barracks`, `Chinese Quarry`); a single word over 12 letters (`Kasirimathatoi`).
6. **Documented short forms** (`known`, each with a source) would win over all of this; none was found for Sierra Leone's design-stage areas (`SOURCES.md`).

Result on the 5,086 issuing areas: 4,851 names kept as they are, **83 cleaned**, **16 shortened** to their distinctive words, **136 flagged** for the council. A flagged area is numbered provisionally under its first candidate that keeps every qualifier and is no well-known town, otherwise under its cleaned name: **36 of them are still over the limit** (the single long words, `Mile 91` and the other mile posts, numbered names such as `Magbesseh 1`, and institution names such as `Police Barracks`). The engine refuses to print a plate with a name over the limit. **The district or city council, with the chiefdom, confirms or chooses every flagged plate name.** At issue the flagged areas (156 in the frozen register, 42 of them still over the limit) were numbered under their provisional names, so that every compound has its number now; the council's choice replaces the name and never the number.

**Aliases.** Typing the official name still decodes: its key is an alias of the plate name (169 aliases), unless it would belong to two plate names or is itself another area's plate name, in which case it is dropped and listed (`model/name-ranges.json` → `plates.droppedAliases`; none today).

**Codes get shorter.** The longest remembered code was `Connaught Hospital Community 1001` (33 characters); among plate names not flagged it is now `Torkpoi Town 1001` (17). The flagged names still over the limit (up to 23 characters) are replaced by the council's choice; their numbers stay.

## 5. Compounds

The addressed unit is the **compound** — the plot or yard and its gate — whatever the address system: under an FCC Plus Code in Freetown, under an N-Ways code elsewhere. A walled house in Hill Station or Wilberforce with boys' quarters, kitchen and generator house; a family yard in Bo or Makeni; a "storey" building in central Freetown; shops in the front wall; estates and barracks with one main gate.

Freetown's informal settlements need their own rule. Kroo Bay, Susan's Bay, Mabella and Colbot on the shore, and the hillside settlements above Kissy, Wellington, Dwarzark and Mount Aureol, have no walls, shared yards and very dense structures. The model does **not** group where a hectare holds more than 70 structures: each structure is its own compound, so a driver is never sent to the wrong door of a merged "compound". In sparse villages (25 structures or fewer per hectare) small huts and kitchens within 8 m of a house join it as a **family yard**; in towns the reach is 4 m.

| Case | Handling |
|---|---|
| Walled compound | One compound under one address; structures "1 main house", "2 boys' quarters" …; route to the gate |
| Family yard (several households) | One compound, `kind = family-yard`; houses are structures |
| Storey building / apartments | One compound; flats are units |
| Shops in the wall | Own structure and street door |
| Estate / barracks / government quarters | Parent: estate gate → compound gate |
| Dense shore and hillside settlements | No grouping; one structure, one compound |

Measured for Freetown (`model/profile-stats.json` → `compoundsCapital`):

- 242,462 structures in Freetown (Western Area Urban) form **188,960 compounds** (0.78 compounds per structure): 39,064 grouped by proximity (92,403 structures), 70 by mapped walls (233 structures), 49,083 single structures in dense hectares, 100,743 single structures elsewhere.
- 39,114 compounds (21%) hold two or more structures; distribution: 1: 149,846, 2: 28,639, 3: 7,739, 4: 1,983, 5: 512, 6+: 241.
- **Density:** 49,764 structures (21%) stand in hectares with more than 70 structures, where nothing is grouped.
- **Walls and gates are rarely mapped:** 423 closed walls/fences in the whole country (70 enclosing structures in Freetown (Western Area Urban), 233 structures inside them); 354 gates and entrances nationally (OpenStreetMap and N-Ways routing gates). N-Ways knows 2,834 gated sites and compounds nationally (site 2691, government 80, police 34, military 28, estate 1).
- So most compounds are, for now, inferred by proximity at modest confidence (0.45); people's confirmations and walk-the-boundary outlines raise them to 0.9.


## 6. Building profile

The schema is in `model/design.json` → `profile`, with a Sierra Leonean taxonomy: residential (block house, **pan body** — the Krio *pan bodi*, a corrugated-iron house —, mud house, round hut, storey building), shop-house, commercial (shop, market, office, warehouse), government, education, health, religious (mosques and churches), industrial (mining at Koidu, Tongo, Marampa/Lunsar, Mokanji and Sierra Rutile; fishing at Tombo, Goderich, Shenge), hospitality, transport (Lungi airport, Tagrin and Kissy ferry terminals, Queen Elizabeth II Quay), agricultural, ancillary, under construction, **uncompleted shell** (the many unfinished block houses Freetown City Council does not rate), ruin, unknown. Each attribute carries source, confidence and last-confirmed date; inference precedence as in `engine/SPEC.md` §4.6 (person 0.95, partner such as FCC 0.9, OSM tags 0.85, OSM type 0.8–0.85, place inside 0.7, `mud` 0.6, size extremes 0.35, else unknown).

Measured for Freetown (Western Area Urban) (`model/profile-stats.json`): of 242,462 structures, 18,260 (8%) have a use from evidence and 224,202 (92%) are `unknown` until people confirm them; nationally 4% have a use. Class mix in Freetown (Western Area Urban):

| Class | Structures | Share | Mean confidence |
|---|---|---|---|
| `unknown` | 224,202 | 92% | 0.0 |
| `ancillary` | 7,630 | 3% | 0.35 |
| `under_construction` | 5,620 | 2% | 0.85 |
| `residential.unspecified` | 3,570 | 1% | 0.8 |
| `commercial.shop` | 370 | 0% | 0.77 |
| `residential.apartment` | 224 | 0% | 0.85 |
| `education` | 174 | 0% | 0.8 |
| `hospitality` | 143 | 0% | 0.72 |
| `religious` | 142 | 0% | 0.76 |
| `commercial.office` | 109 | 0% | 0.71 |
| `health` | 90 | 0% | 0.77 |
| `government` | 57 | 0% | 0.82 |
| `commercial.warehouse` | 46 | 0% | 0.35 |
| `industrial.general` | 30 | 0% | 0.85 |

Size:

| Footprint (m²) | Structures | Share |
|---|---|---|
| < 12 | 30,950 | 13% |
| 12–30 | 56,243 | 23% |
| 30–60 | 51,478 | 21% |
| 60–120 | 54,161 | 22% |
| 120–250 | 37,162 | 15% |
| 250–500 | 10,944 | 5% |
| 500–2,000 | 1,459 | 1% |
| ≥ 2,000 | 65 | 0% |

- **Footprints, Freetown (Western Area Urban):** 242,462 structures; median 48 m² (10th–90th percentile 10–186 m², 99th 425 m²); mean 80 m²; 19.47 km² of roof in all. Nationally the median is 60 m².
- **Height and floors:** 48% of heights come from the footprint model's `h` (which ranges only 3.5–7 m, so it cannot see a third storey), 0% from OpenStreetMap levels or height, the rest none. In Freetown (Western Area Urban) 95% of structures are estimated at one floor and 5% at two; estimated floor area is 19.96 km² (median 50 m² per structure). The two-floor share is an artefact of rounding the model's narrow 3.5–7 m `h` (anything from 4.5 m counts as two floors), so floors from `h` carry confidence 0.3 until OpenStreetMap levels or people confirm them.


## 7. Spot codes: Plus Codes with fixed towns

A spot code is the Plus Code of the point (`6CW8FQQ6+9G`), written short with a reference town (`FQQ6+9G Freetown`), exactly the form FCC prints. N-Ways fixes **31 reference towns** (all district headquarters plus towns chosen so that every building is within 0.4° of one) and shortens within 0.4°. A spot code is a location, not an address: it is what the app shares for a point that has no address and what every gate is stored as.

## 8. Getting a code: zero effort

| Who | How | Steps |
|---|---|---|
| App user at home | "Your home code" as soon as home is known (a saved home, or a tap on "This is my home" at the gate; never inferred from location history): the N-Ways code, with **FCC's Plus Code** first in Freetown; **Share** → WhatsApp or SMS link | 0 / 1 |
| Freetown, FCC code not yet known | "Add the Plus Code from your FCC document" (type + photo; checked against the footprint); meanwhile the gate's Plus Code | 1–2 |
| Standing at a gate | The app shows that compound's address | 0 |
| New house | **Add my home** (§9) | 4 short steps |
| No smartphone | Plate or sticker on the gate; a relative shares it | 0 |
| Courier, bank, utility, FCC | Look the address up from the location in the partner API | 0 for the resident |

That is the whole list. An SMS lookup service is a possible later option only.

## 9. Add my home

Gate (averaged GPS + one photo; its Plus Code appears at once) → outline (tap corners; walk the boundary with AR tracking anchored by averaged GPS; or import a survey plan's beacons, choosing its datum: Sierra Leone 1968 UTM 28N or 29N, the 1924 War Office grid, or WGS 84) → describe (households, structures, floors, use) → **address**: a **provisional N-Ways code at once**, and in Freetown the FCC Plus Code from the owner's FCC document as the official address if they have one, else the gate's Plus Code until FCC registers the property; (next free number in the area's block; a new area with an existing name first takes a block from the name's spare, §4.1), **confirmed** by arrivals, new imagery or 30 days without dispute. A point or outline on a compound that already has a code gets that code, not a new one. **A code is an address, not a land title or survey plan**: land is surveyed by licensed surveyors and recorded with the Ministry of Lands, Housing and Country Planning and, under the National Land Commission Act 2022, the Commission's cadastral index maps; customary land under the Customary Land Rights Act 2022. Land disputes are a live issue in Freetown's hills and the peri-urban Western Area; an N-Ways record is never evidence in one.

## 10. Privacy and data protection

Places, never people: no occupant names, phones or IDs; households as a count; business and public names only; gate photos not published; private gates resolve to the area; FCC property IDs and rates data never public. Sierra Leone has **no data protection law in force**; Cabinet approved a National Data Protection Policy on 21 April 2026 and a Data Protection and Right to Access Information Bill is pending, with a unified authority built from the Right to Access Information Commission. N-Ways follows the ECOWAS Supplementary Act now and will register when the authority exists.

## 11. Governance partners

Freetown City Council and any council later created from its area (their Plus Codes are the address in their areas; data agreement first); the Ministry of Lands, Housing and Country Planning and the National Land Commission; Statistics Sierra Leone (2026 census localities); SALPOST and MoCTI; the National Emergency Medical Service; SLURC on informal settlements; couriers and okada/keke delivery groups. See `GOVERNANCE.md`.

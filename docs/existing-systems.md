# Sierra Leone: existing postal and address systems

Checked 18 October 2026, and again on 20 October 2026 (web and N-Ways map data): nothing new. Every source below was opened on that date unless a different access date is given.

## Verdict

**Sierra Leone has no postal codes and no national address system. Freetown City Council identifies properties with Plus Codes (Open Location Code); street names and house numbers exist only in parts of Freetown and the larger towns.**

1. **No postcodes.** The UPU addressing sheet for Sierra Leone (checked 07/2002) shows no postcode at all: `Mr. John Kamara, 7A Ross Road Cline, FREETOWN, SIERRA LEONE`. Sierra Leone Postal Services Limited (SALPOST) publishes no postcode list or standard; Sierra Leone is not among the UPU members with postcodes. No later SALPOST, Ministry of Communication, Technology and Innovation (MoCTI) or NCRA announcement of postcodes or a national address system was found up to 18 October 2026. A SALPOST–MoCTI–GIG Logistics agreement to modernise postal and logistics services mentions no addressing.
2. **Freetown uses Plus Codes for properties.** Freetown City Council (FCC) says "buildings do not always have a reliable street name nor a house number", so its property reform uses Plus Codes: "a unique eleven-character code that acts like a postal code and street address"; its own office at 17 Wallace Johnson Street is `FQR7+HX`. The FCC property database "contains more than 160,000 properties, compared to 60,000 properties in the old database", measured from satellite images, and excludes properties "that are not permanent and or do not have a completed roof, walls and foundation".
3. **Street names and numbers** exist in central Freetown (e.g. Ross Road, Siaka Stevens Street, Wallace Johnson Street) and in parts of Bo, Kenema and Makeni, but are not systematic. Elsewhere people navigate by community, junction and landmark.
4. **Upcoming:** the 2026 Population and Housing Census (enumeration from 2 December 2026; Statistics Sierra Leone reports the national cartographic mapping as complete) will produce enumeration areas and locality lists, not addresses. In 2025 the Minister of Local Government announced Cabinet approval for two new districts, Bandajuma (from parts of Bo and Pujehun) and Kpanguma (from parts of Kenema and Kailahun), and for new councils in Freetown and the Western Area Rural district; Lungi has been proposed as a city.

**Consequence for this model: government addresses first.** Where a government body already has addresses, N-Ways shows them first, exactly as the government writes them. Freetown City Council has addressed its 160,000+ properties with Plus Codes, so in FCC's area (Western Area Urban, and any council later created from it) the official address is FCC's Plus Code, imported from FCC or recorded from the owner's FCC document; the N-Ways code (a community name and a number) is shown beside it, with the compound, gate, structures and building profile. Everywhere else nothing official exists, and the N-Ways code is the address, on the same Plus Code grid, with no dependence on district or chiefdom boundaries. See `docs/model.md` §0–2.

## Evidence

| What | Finding | Source |
|---|---|---|
| UPU addressing sheet | No postcode; example `7A Ross Road Cline / FREETOWN / SIERRA LEONE`; SALPOST, GPO Building, Siaka Stevens Street; dated 07/2002 | UPU, *Sierra Leone* addressing sheet, https://www.upu.int/UPU/media/upu/PostalEntitiesFiles/addressingUnit/sleEn.pdf |
| Postcode lists | "Sierra Leone · SL · no codes"; SALPOST publishes no postcode lookup or standard | https://en.wikipedia.org/wiki/List_of_postal_codes ; https://datahub.io/logistics/postal-codes-sl |
| Freetown property identifiers | Plus Codes as building addresses; `FQR7+HX` for 17 Wallace Johnson Street; 160,000+ properties; rooftop area from satellite images; impermanent or illegally built properties not assessed | Freetown City Council, Property Reform FAQ, https://fcc.gov.sl/property-reform-faq/ |
| Freetown property register growth | Digital property rate system from 2020 using satellite images; register from ~57,000 to over 120,000 properties at the end of discovery (early 2020) | African Tax Administration Forum, "Property Tax Reform – Lessons from Freetown", https://www.ataftax.org/property-tax-reform-lessons-from-freetown ; African Arguments, May 2020, https://africanarguments.org/2020/05/freetown-just-implemented-a-new-tax-system-that-could-quintuple-revenue/ |
| SALPOST modernisation | MoCTI, SALPOST and GIG Logistics agreement to upgrade postal and logistics services (no addressing mentioned) | Premier Media, https://www.premiermedia-sl.com/?p=26119 |
| Regional planning | Sierra Leone among five English-speaking West African countries planning addressing with the UPU (2011); nothing launched since | UPU news, Mar 2011, https://www.upu.int/en/news/2011/3/addressing-a-key-issue-in-west-africa |
| Digital public infrastructure | MoCTI dialogue (Aug 2026) on digital ID, payments and data exchange; no addressing pillar | TechAfrica News, 5 Aug 2026, https://techafricanews.com/2026/08/05/sierra-leone-advances-national-digital-identity-and-digital-public-infrastructure-agenda/ ; Biometric Update, Aug 2026, https://www.biometricupdate.com/202608/sierra-leone-consults-private-sector-on-trusted-digital-id-framework |
| Census 2026 | Enumeration from 2 December 2026 (census night 1 December), a digital census with tablets | MoICE, Statistics Sierra Leone town hall in Falaba (2026), https://moice.gov.sl/statistics-sierra-leone-explains-census-process-to-falaba-residents/ ; Calabash, https://thecalabashnewspaper.com/archives/65401 |
| Redistricting | Cabinet approval announced by the Minister of Local Government: districts Bandajuma (Bo and Pujehun) and Kpanguma (Kenema and Kailahun), two councils for Freetown and three for Western Area Rural, 18 districts in all; not yet in force | Sierraloaded, 20 Aug 2025, https://sierraloaded.sl/news/local-government-minister-announces-creation/ ; Awoko, "Lungi Poised to Become Sierra Leone's Newest City", https://awokonewspapersl.com/lungi-poised-to-become-sierra-leones-newest-city/ |
| OpenStreetMap | Building extract: 790,492 of 839,967 OSM buildings tagged only `building=yes`; 16,330 carry `addr:city` (mostly Kailahun and Kambia mapping projects); `addr:housenumber` count not taken | `tools/profile_stats.py` input; N-Ways research |

## Land and survey records (for "Add my home" plot outlines)

- The **National Land Commission Act 2022** (Act No. 19, Gazette 23 Sep 2022) creates a National Land Commission with a **Cadastral Index Mapping Department** to "develop guidelines for undertaking cadastral" mapping, "maintain a depository of cadastral index maps" and "permit searches", and recognises licensed surveyors, pupil surveyors and para-surveyors (FAOLEX text, https://faolex.fao.org/docs/pdf/sie212618.pdf). The **Customary Land Rights Act 2022** (Act No. 20) covers registration and demarcation of customary land (s. 42 on demarcation and survey of land for investment; FAOLEX https://faolex.fao.org/docs/pdf/sie212374.pdf). Both passed Parliament on 8 Aug 2022 (Parliament press release, https://www.parliament.gov.sl/uploads/press_release/pdf/PARLIAMENT%20PASSES%20NATIONAL%20LAND%20COMMISSION%20ACT,2022%20-%208th%20AUGUST,%202022.pdf).
- Survey plans in the Western Area are lodged with the Ministry of Lands, Housing and Country Planning (Director of Surveys and Lands). No open cadastral parcel layer was found. A World Bank policy note (2019) describes Freetown's registration as ineffective, with inadequate surveying (https://openknowledge.worldbank.org/signposting/describedby/f6a3772f-741b-5cbb-9eb3-177d6a11781a).
- Survey coordinates: the national datum is **Sierra Leone 1968** (EPSG:6175, Clarke 1880 RGS), projected to UTM zone 28N west of 12°W (EPSG:2161, Freetown and the Western Area) and zone 29N east of it (EPSG:2162); the published transformation to WGS 84 is accurate to about ±15 m per axis (https://epsg.io/2161, https://epsg.io/2162). Older plans may use the Sierra Leone 1924 "New War Office" grid. A plan's beacons must therefore be converted with its datum stated, never assumed to be WGS 84.

## Data protection (Sierra Leone)

- **No data protection law in force** as of 18 Oct 2026. Cabinet approved the first National Data Protection Policy on 21 Apr 2026 and authorised a Data Protection and Right to Access Information Act, merging data protection with the Right to Access Information Commission (RAIC) (MoICE, https://moice.gov.sl/?p=2375). The Data Protection and Right to Access Information Bill 2025 finished national validation on 7 Nov 2025 (MoICE, https://moice.gov.sl/moice-concludes-final-national-validation-of-the-data-protection-and-right-to-access-information-bill-2025/). No evidence it has passed Parliament.

## Not verified

- Whether any district council other than Freetown (e.g. Bo, Kenema, Makeni city councils) also uses Plus Codes in its property register.
- FCC ward boundaries after the 2022 delimitation and the redistricting approved in 2025 (FCC refers people to "your Councillor … in your Ward"); the model does not depend on them.
- Whether the Data Protection Bill passed after April 2026; the Cyber Security and Crime Act 2021's bearing on location data.
- Which datum the Ministry of Lands now requires for new survey plans.
- The names and boundaries of the councils that will succeed the redistricting approved in 2025: press reports of an announcement on 13 October 2026 name further councils, but no official text was found.
- Short forms of place names in use (for plate names, `docs/model.md` §4.2): none documented was found; the flagged names go to the councils.

These points are listed in `SOURCES.md` as open checks.

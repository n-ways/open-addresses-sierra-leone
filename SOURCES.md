# Sources: Sierra Leone

All accessed 18 October 2026 unless stated. Requests used a generic User-Agent; no personal data was sent anywhere.

## Official and primary

| # | Source | Used for |
|---|---|---|
| 1 | UPU, Sierra Leone addressing sheet (07/2002), https://www.upu.int/UPU/media/upu/PostalEntitiesFiles/addressingUnit/sleEn.pdf | No postcode; `7A Ross Road Cline, FREETOWN`; SALPOST contact |
| 2 | Freetown City Council, Property Reform FAQ, https://fcc.gov.sl/property-reform-faq/ | Plus Codes as property addresses; `FQR7+HX` = 17 Wallace Johnson Street; 160,000+ properties; rooftop area from satellite images; exclusions |
| 3 | Freetown City Council, Transform Freetown, https://fcc.gov.sl/transform-freetown/ | City programme (2024–2028) |
| 4 | National Land Commission Act 2022 (Act No. 19), FAOLEX https://faolex.fao.org/docs/pdf/sie212618.pdf | Cadastral Index Mapping Department; licensed surveyors and para-surveyors |
| 5 | Customary Land Rights Act 2022 (Act No. 20), FAOLEX https://faolex.fao.org/docs/pdf/sie212374.pdf | Customary land registration, demarcation (s. 42) |
| 6 | Parliament of Sierra Leone, press release 8 Aug 2022, https://www.parliament.gov.sl/uploads/press_release/pdf/PARLIAMENT%20PASSES%20NATIONAL%20LAND%20COMMISSION%20ACT,2022%20-%208th%20AUGUST,%202022.pdf | Passage of both land Acts |
| 7 | MoICE, 22 Apr 2026, https://moice.gov.sl/?p=2375 | National Data Protection Policy approved by Cabinet |
| 8 | MoICE, Nov 2025, https://moice.gov.sl/moice-concludes-final-national-validation-of-the-data-protection-and-right-to-access-information-bill-2025/ | Bill validated, not yet passed |
| 9 | MoICE, Statistics Sierra Leone town hall in Falaba (2026), https://moice.gov.sl/statistics-sierra-leone-explains-census-process-to-falaba-residents/ | 2026 census: census night 1 December, enumeration from 2 December |
| 10 | EPSG:2161 / 2162 Sierra Leone 1968 / UTM 28N and 29N, https://epsg.io/2161 , https://epsg.io/2162 | Datum and projections of survey plans |
| 11 | Open Location Code specification and reference code, https://github.com/google/open-location-code | The grid, encoding, shortening and recovery rules |

## Press and secondary

| # | Source | Used for |
|---|---|---|
| 12 | ATAF, "Property Tax Reform – Lessons from Freetown", https://www.ataftax.org/property-tax-reform-lessons-from-freetown | Satellite-based property capture; register growth |
| 13 | African Arguments, May 2020, https://africanarguments.org/2020/05/freetown-just-implemented-a-new-tax-system-that-could-quintuple-revenue/ | Register from ~57,000 to ~110,000+ |
| 14 | Premier Media, SALPOST/MoCTI/GIGL agreement, https://www.premiermedia-sl.com/?p=26119 | Postal modernisation, no addressing |
| 15 | Wikipedia, List of postal codes, https://en.wikipedia.org/wiki/List_of_postal_codes | "Sierra Leone – no codes" |
| 16 | datahub.io, https://datahub.io/logistics/postal-codes-sl | No SALPOST postcode lookup |
| 17 | UPU news, Mar 2011, https://www.upu.int/en/news/2011/3/addressing-a-key-issue-in-west-africa | 2011 planning |
| 18 | TechAfrica News, 5 Aug 2026; Biometric Update, Aug 2026 | Digital public infrastructure agenda (no addressing pillar) |
| 19 | World Bank, Freetown land policy note (2019), https://openknowledge.worldbank.org/signposting/describedby/f6a3772f-741b-5cbb-9eb3-177d6a11781a | Registration and surveying weaknesses |
| 20 | Sierraloaded, 20 Aug 2025, https://sierraloaded.sl/news/local-government-minister-announces-creation/ | Cabinet approval of the Bandajuma and Kpanguma districts and new councils for Freetown and Western Area Rural |
| 21 | Africa Review, July 2017 (web archive), https://web.archive.org/web/20180221142807/http://www.africareview.com/news/Sierra-Leone-unveils-new-geographical-map/979180-4041036-4x8dfaz/index.html | The 2017 map: 16 districts, 190 chiefdoms |
| 22 | Ragazzoni et al. (2021), Prehospital and Disaster Medicine 36(1); Caviglia et al. (2021), BMJ Global Health 6(11) | The National Emergency Medical Service: operations and prehospital times |

## Literature

The research literature the paper relies on (UPU S42 and the UPU white paper, ISO 19160-1, the World Bank's review of street addressing, Damm's and Verhoeff's check digits, Hilbert's curve and its clustering properties, Open Location Code, the building-footprint datasets and the emergency-medicine studies) is listed, with every entry checked against its publisher, in `docs/paper/references.bib`.

## Data

| Data | Licence | Used for |
|---|---|---|
| OpenStreetMap (Geofabrik extract 17 Oct 2026; `data/osm/sierra-leone-latest.osm.pbf`, `data/detail/countries/sierra-leone/buildings-src.geojsonseq`) | ODbL 1.0 | 839,967 building outlines and tags; walls, fences, gates; towns (reference-town points) |
| Google Open Buildings / Microsoft footprints via Overture (`data/detail/ml/SL.parquet`) | CC BY 4.0 / ODbL | Footprints OSM lacks, with height `h` |
| geoBoundaries SLE ADM2 (2017, Government of Sierra Leone / OCHA) and ADM3 (165 chiefdoms, 2016, openAfrica), https://www.geoboundaries.org | CC BY 3.0 IGO / CC BY 4.0 | Western Area Urban outline; buildings per chiefdom |
| N-Ways places, gated compounds and gates; regions table | per source / ODbL | Uses, compounds, gates, province outlines |

## Plate names (short forms)

The plate name rule (`docs/model.md` §4.2) lets a documented short form that people already say replace an over-long official name, with its source. No such short form was found for Sierra Leone's design-stage areas (OpenStreetMap names; no council or Statistics Sierra Leone locality list with short forms was available on 18 October 2026), so `KNOWN` in `tools/name_ranges.py` is empty and every shortening follows the written rules or goes to the council. The choice to keep "Town" in names that fit (Allen Town, Congo Town, Murray Town) rests on these being the names used on the map and by FCC's community list, not on a source for the short forms.

## Open checks (not verified)

1. Whether Bo, Kenema, Makeni or other councils use Plus Codes in their registers.
2. Current FCC ward map and the boundaries of the districts and councils approved in 2025 (not needed by any code).
3. Data Protection Bill status after April 2026; the Cyber Security and Crime Act 2021.
4. The datum the Ministry of Lands requires for new survey plans; whether any cadastral index map is public.
5. Krio, Mende and Temne letter-name confusions (field test with okada riders and couriers).
6. The plate names flagged for the council (156 areas, `needs_council_choice` in `registry/areas.csv`), with district and city councils and chiefdoms, and whether people say "Town" in the names that keep it.

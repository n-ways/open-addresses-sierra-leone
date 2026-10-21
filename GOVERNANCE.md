# Governance: N-Ways addressing for Sierra Leone

Status: **issued on 20 October 2026** (1,359,282 codes, provisional until residents confirm them); open under the licences in LICENSING.md. This repo is maintained by N-Ways until a Sierra Leonean public body chooses to take it over.

## What this repo is, and is not

- It is an **open compound and building registry** for Sierra Leone on the **Plus Code (Open Location Code) grid**, the grid Freetown City Council already uses to identify properties. Every N-Ways spot code in Sierra Leone is a valid Plus Code; every compound record and plate carries its gate's Plus Code. What people remember is a community name, at most 12 characters, and a number (`Moyamba 15727`); in Freetown, FCC's Plus Code is shown first.
- It is **not** an official address system, a postcode or a land record. Until a Sierra Leonean authority adopts it, its codes are "N-Ways addresses" / "N-Ways compound codes".
- A compound code is an address. **It is not a title, a survey plan or proof of ownership**, and N-Ways never presents it as one (see `docs/model.md`, "Add my home").

## Relation to Freetown City Council and others

**Rule: where a government body already has addresses, N-Ways shows them first.** In FCC's area the official address is FCC's Plus Code, verbatim; the N-Ways code is shown beside it.

- FCC's property IDs and Plus Codes stay FCC's. The registry records the Plus Code FCC assigned (from an FCC agreement or the owner's document) and shows it as the address; property IDs are kept private. N-Ways never renumbers or replaces them.
- If SALPOST, the Ministry of Communication, Technology and Innovation, or the National Land Commission launches a national address or postcode, this registry maps onto it and the app shows the official code first.

## Maintainers

- **N-Ways** maintains the engine, the reference-town list, the registry build and the registry server, and is the designated issuer until the State designates another.
- **Sierra Leonean reviewers** (to be invited): a Freetown courier or motorbike delivery company, the National Emergency Medical Service, Freetown City Council's property-rates team, SLURC (Sierra Leone Urban Research Centre, on informal settlements), and a university GIS department (Fourah Bay College or Njala University).
- Any public body that wants a role gets one, up to full ownership of the repo.

## What can change, and how

| Change | Rule |
|---|---|
| The grid | Not ours to change: it is the Open Location Code grid, fixed by its published specification. |
| Reference towns (`model/design.json` → `referenceTowns`) | Frozen once published: a town's point never moves. Towns can be **added** (for example a new district headquarters); never removed. A short code works against any listed town within 0.5 degrees. |
| District, chiefdom, ward, city council | **Not part of any code.** They are looked-up attributes that follow each redistricting (2017, October 2026, any later one). |
| Address areas (names, polygons, ids) | **Frozen** at first issue, independent of any district, chiefdom or ward. Never redrawn or renamed; spellings may gain aliases; new settlements may get new areas. |
| Plate names (the short name in the code) | Derived by fixed rules from the official name (`docs/model.md` §4.2); the 156 flagged areas carry provisional names until **the district or city council, with the chiefdom, confirms or chooses them**; the numbers never change; the official name stays an alias. |
| Compound codes | Issued once, never moved, never reused; retired on demolition. |
| Grouping into compounds | Corrected by people's confirmations; **regrouping never changes an issued code** (merged compounds keep the gate's code, others become aliases; a split keeps the code on the part with the original gate). |
| Building profiles | Kept current; each attribute keeps its source and last-confirmed date. |
| Spoken forms (Krio, Mende, Temne) | Field-tested; changed by pull request with evidence. |

Changes to anything frozen need a written proposal in `docs/`, a 60-day public comment period, and agreement of the maintainers and any adopting authority.

## Issuing: one issuer per country

Codes are issued by one issuer only: N-WAYS LIMITED, or the body the State designates. The registry server in `server/` can be deployed by anyone, read-only; it issues only on the deployment the issuer runs. Two issuers would hand out the same number to two compounds, so a second issuing deployment is never authorised, and a change of issuer is a hand-over (the old issuer stops and exports, the new one imports that export before issuing). The issuer publishes its exports in `registry/`, and every other deployment updates from them (`server/README.md`).

## Disputes

- Address disputes are settled by agreement signals (arrivals, deliveries, the occupant confirming twice), never by a manual review queue.
- **Land disputes are out of scope.** Overlapping claims get no compound code for the overlap and are pointed to the Ministry of Lands, Housing and Country Planning or the National Land Commission (once operating). Existing codes are never reassigned because of a land claim.

## Hand-over

The repo moves as a whole to a Sierra Leonean public body if one adopts it; N-Ways keeps a read-only mirror and keeps its app compatible.

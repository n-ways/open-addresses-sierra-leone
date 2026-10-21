# The registry API

This is the HTTP API of the registry server in [`server/`](../server/). Every example on this page is a real request to a server holding the published registry (1,359,282 codes) and its real response, errors included. The issuing examples were made on a scratch copy of the database with a demonstration key; they are not codes of the published registry. The machine-readable description is [`server/openapi.yaml`](../server/openapi.yaml) (OpenAPI 3.1).

## Conventions

- Base path `/v1`. Requests and responses are JSON in UTF-8; field names are stable.
- Coordinates are WGS 84 decimal degrees, `lat` then `lng`; outlines are `[lng, lat]` pairs, as in GeoJSON.
- Errors have one shape, `{"error": {"code": "...", "message": "..."}}`, with the HTTP status that fits: 400 a missing or malformed parameter, 401 no valid key, 403 a read-only server, 404 nothing found, 405 a wrong method, 409 a conflict (the compound already has a code, a retired code, a full name), 410 a retired code, 413 a body over 64 KB, 422 a well-formed request that the rules refuse (a point more than 300 m outside the national border, a wrong check digit, a door too far, an outline too small or too large), 429 the daily limit of a key, 500 a fault of the server. `code` is for programs; `message` is for people.
- Writes need `Authorization: Bearer <key>`, with a key from `ISSUE_KEYS`. A server without keys is read-only. The write examples below read the key from the shell variable `ISSUE_KEY`.
- The check digit is for systems. It is returned in `check` and may be given after a `·`; it is never shown on plates or to people.

## Endpoints

- [`GET /v1/health`](#get-v1health)
- [`GET /v1/info`](#get-v1info)
- [`GET /v1/codes/{machine}`](#get-v1codesmachine)
- [`GET /v1/find?q=`](#get-v1findq)
- [`GET /v1/at?lat=&lng=`](#get-v1atlatlng)
- [`GET /v1/near?lat=&lng=&radius=&limit=`](#get-v1nearlatlngradiuslimit)
- [`GET /v1/verify?code=`](#get-v1verifycode)
- [`GET /v1/spot?lat=&lng=`](#get-v1spotlatlng)
- [`GET /v1/spot/decode?code=`](#get-v1spotdecodecode)
- [`GET /v1/zones`](#get-v1zones)
- [`GET /v1/zones/{key}`](#get-v1zoneskey)
- [`GET /v1/zones/{key}/codes?after=&limit=`](#get-v1zoneskeycodesafterlimit)
- [`GET /v1/areas/{id}`](#get-v1areasid)
- [`GET /v1/areas?name=`](#get-v1areasname)
- [`POST /v1/codes`](#post-v1codes)
- [`PATCH /v1/codes/{machine}`](#patch-v1codesmachine)
- [Other paths and methods](#other-paths-and-methods)

## `GET /v1/health`

Liveness and the registry in service: the country, the number of codes and the date of the registry export the database came from. `issuing` says whether this deployment accepts issuing keys.

### Health

```sh
curl -s 'http://localhost:8080/v1/health'
```

`200`

```json
{
  "status": "ok",
  "country": "SL",
  "codes": 1359282,
  "exported": "2026-10-20T15:54:15Z",
  "issuing": true
}
```

## `GET /v1/info`

The country, its zones, areas and names, the codes by status, the reference towns of short Plus Codes, the licences and the credit line every reuse must carry.

### Country, counts and licences

```sh
curl -s 'http://localhost:8080/v1/info'
```

`200`

```json
{
  "country": "SL",
  "name": "Sierra Leone",
  "spec": "1.0",
  "engine": "internal/addressing/sl (SPEC v1.0)",
  "exported": "2026-10-20T15:54:15Z",
  "codes": 1359282,
  "byStatus": {
    "provisional": 1359282
  },
  "zones": 13,
  "areas": 5184,
  "names": 3706,
  "aliases": 208,
  "forms": {
    "remembered": "Moyamba 15727",
    "written": "Moyamba 157 27",
    "machine": "SL-03663-15727",
    "spot": "5H68+3V Moyamba",
    "official": "FQQ6+9G Freetown"
  },
  "towns": [
    "Alikalia",
    "Bafodia",
    "Bendugu",
    "Bo",
    "Bonthe",
    "Daru",
    "Falaba",
    "Freetown",
    "Kabala",
    "Kailahun",
    "Kainkordu",
    "Kamakwie",
    "Kamaron",
    "Kambia",
    "Kenema",
    "Koidu",
    "Lungi",
    "Lunsar",
    "Magburaka",
    "Makeni",
    "Masingbi",
    "Mattru Jong",
    "Mile 91",
    "Moyamba",
    "Port Loko",
    "Pujehun",
    "Sainya",
    "Shenge",
    "Sullima",
    "Waterloo",
    "Zimmi"
  ],
  "licences": {
    "data": "ODbL-1.0",
    "code": "Apache-2.0",
    "documents": "CC-BY-4.0"
  },
  "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone",
  "issuing": true,
  "issuePerDay": 50
}
```

## `GET /v1/codes/{machine}`

The card of one code. `record` holds every column of the published registry under its own name, exactly as published; the other fields are the same facts in a ready-to-use shape: the remembered, written and spoken forms, the check digit (for systems; never printed for people), the area and zone, the entrance, its Plus Code and the building summary. A structure (`.2`) and a unit (`/3`) may follow the number, and the check digit may follow a `·`; a wrong check is refused, never guessed.

### A code by its machine form

```sh
curl -s 'http://localhost:8080/v1/codes/SL-03663-15727'
```

`200`

```json
{
  "country": "SL",
  "machine": "SL-03663-15727",
  "remembered": "Moyamba 15727",
  "written": "Moyamba 157 27",
  "spoken": "Moyamba, 157 27",
  "check": 0,
  "number": 15727,
  "status": "provisional",
  "issued": "bulk",
  "issuedAt": "2026-10-20T13:03:17Z",
  "officialAddress": null,
  "coverage": null,
  "area": {
    "id": "03663",
    "plateName": "Moyamba",
    "officialName": "Moyamba",
    "nameProvisional": false,
    "district": "Moyamba",
    "placeLine": "Moyamba District",
    "place": "town",
    "fccArea": false,
    "nameKey": "moyamba",
    "nameId": 2674,
    "zone": "6CW9"
  },
  "zone": {
    "key": "6CW9",
    "name": "Port Loko"
  },
  "placeLine": "Moyamba District",
  "fullLine": "Moyamba 157 27 · Moyamba District",
  "entrance": {
    "lat": 8.1602399,
    "lng": -12.4327947,
    "kind": "centre"
  },
  "spot": {
    "full": "6CW95H68+3V",
    "short": "5H68+3V Moyamba",
    "precise": "6CW95H68+3VW",
    "town": "Moyamba"
  },
  "building": {
    "class": "unknown",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floorAreaM2": 888.7,
    "rule": "single",
    "estate": null
  },
  "outline": null,
  "record": {
    "machine": "SL-03663-15727",
    "home": "Moyamba 15727",
    "written": "Moyamba 157 27",
    "zone": "03663",
    "official_name": "Moyamba",
    "district": "Moyamba",
    "number": "15727",
    "check": "0",
    "status": "provisional",
    "issued": "bulk",
    "issued_at": "2026-10-20T13:03:17Z",
    "entrance_lat": "8.1602399",
    "entrance_lng": "-12.4327947",
    "entrance_kind": "centre",
    "plus_code": "5H68+3V Moyamba",
    "fcc_address": "",
    "class": "unknown",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "888.7",
    "rule": "single",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
}
```

### Error: a number of the area that is not issued

```sh
curl -s 'http://localhost:8080/v1/codes/SL-03663-15728'
```

`404`

```json
{
  "error": {
    "code": "code_not_found",
    "message": "No compound has SL-03663-15728 yet (the number is in a block of Moyamba, Moyamba District)."
  }
}
```

### Error: the check digit does not match

```sh
curl -s 'http://localhost:8080/v1/codes/SL-03663-15727%C2%B74'
```

`422`

```json
{
  "error": {
    "code": "check_mismatch",
    "message": "The check digit does not match: a digit is wrong or two are swapped."
  }
}
```

## `GET /v1/find?q=`

Finds a code from what a person says or types: a remembered or written form (any spacing, case or accents; the name may be the official name of the area), a machine form, an official address in Freetown City Council's area (the property's Plus Code), or any Plus Code (the compound nearest its centre, within 15 m). `kind` says how the text was read. A wrong check digit is refused (422), never corrected.

### Remembered form, as people say it

```sh
curl -s 'http://localhost:8080/v1/find?q=moyamba%20157%2027'
```

`200`

```json
{
  "query": "moyamba 157 27",
  "kind": "remembered",
  "codes": [
    {
      "country": "SL",
      "machine": "SL-03663-15727",
      "remembered": "Moyamba 15727",
      "written": "Moyamba 157 27",
      "spoken": "Moyamba, 157 27",
      "check": 0,
      "number": 15727,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T13:03:17Z",
      "officialAddress": null,
      "coverage": null,
      "area": {
        "id": "03663",
        "plateName": "Moyamba",
        "officialName": "Moyamba",
        "nameProvisional": false,
        "district": "Moyamba",
        "placeLine": "Moyamba District",
        "place": "town",
        "fccArea": false,
        "nameKey": "moyamba",
        "nameId": 2674,
        "zone": "6CW9"
      },
      "zone": {
        "key": "6CW9",
        "name": "Port Loko"
      },
      "placeLine": "Moyamba District",
      "fullLine": "Moyamba 157 27 · Moyamba District",
      "entrance": {
        "lat": 8.1602399,
        "lng": -12.4327947,
        "kind": "centre"
      },
      "spot": {
        "full": "6CW95H68+3V",
        "short": "5H68+3V Moyamba",
        "precise": "6CW95H68+3VW",
        "town": "Moyamba"
      },
      "building": {
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 888.7,
        "rule": "single",
        "estate": null
      },
      "outline": null,
      "record": {
        "machine": "SL-03663-15727",
        "home": "Moyamba 15727",
        "written": "Moyamba 157 27",
        "zone": "03663",
        "official_name": "Moyamba",
        "district": "Moyamba",
        "number": "15727",
        "check": "0",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T13:03:17Z",
        "entrance_lat": "8.1602399",
        "entrance_lng": "-12.4327947",
        "entrance_kind": "centre",
        "plus_code": "5H68+3V Moyamba",
        "fcc_address": "",
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "888.7",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
      "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
    }
  ]
}
```

### Official address in Freetown (the property's Plus Code)

```sh
curl -s 'http://localhost:8080/v1/find?q=FQQ6%2B9G%20Freetown'
```

`200`

```json
{
  "query": "FQQ6+9G Freetown",
  "kind": "official",
  "point": {
    "lat": 8.4884375,
    "lng": -13.2386875,
    "plusCode": "6CW8FQQ6+9G"
  },
  "codes": [
    {
      "country": "SL",
      "machine": "SL-00623-2301",
      "remembered": "Connaught 2301",
      "written": "Connaught 23 01",
      "spoken": "Connaught, 23 01",
      "check": 8,
      "number": 2301,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T13:02:38Z",
      "officialAddress": "FQQ6+9G Freetown",
      "coverage": "official",
      "area": {
        "id": "00623",
        "plateName": "Connaught",
        "officialName": "Connaught Hospital Community",
        "nameProvisional": false,
        "district": "Western Area Urban",
        "placeLine": "Freetown",
        "place": "neighbourhood",
        "fccArea": true,
        "nameKey": "connaught",
        "nameId": 418,
        "zone": "6CW8"
      },
      "zone": {
        "key": "6CW8",
        "name": "Western Area Urban"
      },
      "placeLine": "Freetown",
      "fullLine": "Connaught 23 01 · Freetown",
      "entrance": {
        "lat": 8.4884654,
        "lng": -13.2387389,
        "kind": "centre"
      },
      "spot": {
        "full": "6CW8FQQ6+9G",
        "short": "FQQ6+9G Freetown",
        "precise": "6CW8FQQ6+9GJ",
        "town": "Freetown"
      },
      "building": {
        "class": "health",
        "use": "health",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 194.0,
        "rule": "single",
        "estate": null
      },
      "outline": null,
      "record": {
        "machine": "SL-00623-2301",
        "home": "Connaught 2301",
        "written": "Connaught 23 01",
        "zone": "00623",
        "official_name": "Connaught Hospital Community",
        "district": "Western Area Urban",
        "number": "2301",
        "check": "8",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T13:02:38Z",
        "entrance_lat": "8.4884654",
        "entrance_lng": "-13.2387389",
        "entrance_kind": "centre",
        "plus_code": "FQQ6+9G Freetown",
        "fcc_address": "FQQ6+9G Freetown",
        "class": "health",
        "use": "health",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "194.0",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
      "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone",
      "distanceM": 6.4
    }
  ]
}
```

### Any Plus Code: the compound nearest its centre

```sh
curl -s 'http://localhost:8080/v1/find?q=5H68%2B3V%20Moyamba'
```

`200`

```json
{
  "query": "5H68+3V Moyamba",
  "kind": "spot",
  "point": {
    "lat": 8.160187500000001,
    "lng": -12.432812499999999,
    "plusCode": "6CW95H68+3V"
  },
  "codes": [
    {
      "country": "SL",
      "machine": "SL-03663-15727",
      "remembered": "Moyamba 15727",
      "written": "Moyamba 157 27",
      "spoken": "Moyamba, 157 27",
      "check": 0,
      "number": 15727,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T13:03:17Z",
      "officialAddress": null,
      "coverage": null,
      "area": {
        "id": "03663",
        "plateName": "Moyamba",
        "officialName": "Moyamba",
        "nameProvisional": false,
        "district": "Moyamba",
        "placeLine": "Moyamba District",
        "place": "town",
        "fccArea": false,
        "nameKey": "moyamba",
        "nameId": 2674,
        "zone": "6CW9"
      },
      "zone": {
        "key": "6CW9",
        "name": "Port Loko"
      },
      "placeLine": "Moyamba District",
      "fullLine": "Moyamba 157 27 · Moyamba District",
      "entrance": {
        "lat": 8.1602399,
        "lng": -12.4327947,
        "kind": "centre"
      },
      "spot": {
        "full": "6CW95H68+3V",
        "short": "5H68+3V Moyamba",
        "precise": "6CW95H68+3VW",
        "town": "Moyamba"
      },
      "building": {
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 888.7,
        "rule": "single",
        "estate": null
      },
      "outline": null,
      "record": {
        "machine": "SL-03663-15727",
        "home": "Moyamba 15727",
        "written": "Moyamba 157 27",
        "zone": "03663",
        "official_name": "Moyamba",
        "district": "Moyamba",
        "number": "15727",
        "check": "0",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T13:03:17Z",
        "entrance_lat": "8.1602399",
        "entrance_lng": "-12.4327947",
        "entrance_kind": "centre",
        "plus_code": "5H68+3V Moyamba",
        "fcc_address": "",
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "888.7",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
      "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone",
      "distanceM": 6.1
    }
  ]
}
```

### Error: wrong check digit

```sh
curl -s 'http://localhost:8080/v1/find?q=Moyamba%20157%2027%20%C2%B7%204'
```

`422`

```json
{
  "error": {
    "code": "check_mismatch",
    "message": "The check digit does not match: a digit is wrong or two are swapped."
  }
}
```

### Error: unknown name

```sh
curl -s 'http://localhost:8080/v1/find?q=Nowhereville%201001'
```

`404`

```json
{
  "error": {
    "code": "code_not_found",
    "message": "No compound in Sierra Leone has the code Nowhereville 1001 (no area of Sierra Leone is called 'Nowhereville'). Check the place name and the number on the plate."
  }
}
```

### Error: nothing to find

```sh
curl -s 'http://localhost:8080/v1/find?q='
```

`400`

```json
{
  "error": {
    "code": "missing_q",
    "message": "Give the code to find in q, for example ?q=Moyamba 157 27."
  }
}
```

## `GET /v1/at?lat=&lng=`

The compound at a point: a code whose entrance is within 12 m (or, for a compound issued with its outline, whose outline holds the point). Otherwise `status` is `none`, with the area a new compound there would join and the point's Plus Code. `distanceM` is rounded to the metre.

### A point on a compound

```sh
curl -s 'http://localhost:8080/v1/at?lat=8.48842&lng=-13.23869'
```

`200`

```json
{
  "status": "found",
  "distanceM": 7,
  "code": {
    "country": "SL",
    "machine": "SL-00623-2301",
    "remembered": "Connaught 2301",
    "written": "Connaught 23 01",
    "spoken": "Connaught, 23 01",
    "check": 8,
    "number": 2301,
    "status": "provisional",
    "issued": "bulk",
    "issuedAt": "2026-10-20T13:02:38Z",
    "officialAddress": "FQQ6+9G Freetown",
    "coverage": "official",
    "area": {
      "id": "00623",
      "plateName": "Connaught",
      "officialName": "Connaught Hospital Community",
      "nameProvisional": false,
      "district": "Western Area Urban",
      "placeLine": "Freetown",
      "place": "neighbourhood",
      "fccArea": true,
      "nameKey": "connaught",
      "nameId": 418,
      "zone": "6CW8"
    },
    "zone": {
      "key": "6CW8",
      "name": "Western Area Urban"
    },
    "placeLine": "Freetown",
    "fullLine": "Connaught 23 01 · Freetown",
    "entrance": {
      "lat": 8.4884654,
      "lng": -13.2387389,
      "kind": "centre"
    },
    "spot": {
      "full": "6CW8FQQ6+9G",
      "short": "FQQ6+9G Freetown",
      "precise": "6CW8FQQ6+9GJ",
      "town": "Freetown"
    },
    "building": {
      "class": "health",
      "use": "health",
      "kind": "building",
      "structures": 1,
      "floorAreaM2": 194.0,
      "rule": "single",
      "estate": null
    },
    "outline": null,
    "record": {
      "machine": "SL-00623-2301",
      "home": "Connaught 2301",
      "written": "Connaught 23 01",
      "zone": "00623",
      "official_name": "Connaught Hospital Community",
      "district": "Western Area Urban",
      "number": "2301",
      "check": "8",
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T13:02:38Z",
      "entrance_lat": "8.4884654",
      "entrance_lng": "-13.2387389",
      "entrance_kind": "centre",
      "plus_code": "FQQ6+9G Freetown",
      "fcc_address": "FQQ6+9G Freetown",
      "class": "health",
      "use": "health",
      "kind": "building",
      "structures": "1",
      "floor_area_m2": "194.0",
      "rule": "single",
      "estate": ""
    },
    "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
    "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
  },
  "area": {
    "id": "01885",
    "plateName": "Kingtom",
    "officialName": "Kingtom",
    "nameProvisional": false,
    "district": "Western Area Urban",
    "placeLine": "Freetown",
    "place": "suburb",
    "fccArea": true,
    "nameKey": "kingtom",
    "nameId": 1310,
    "zone": "6CW8"
  }
}
```

### A point with no compound

```sh
curl -s 'http://localhost:8080/v1/at?lat=8.1652&lng=-12.43'
```

`200`

```json
{
  "status": "none",
  "area": {
    "id": "03663",
    "plateName": "Moyamba",
    "officialName": "Moyamba",
    "nameProvisional": false,
    "district": "Moyamba",
    "placeLine": "Moyamba District",
    "place": "town",
    "fccArea": false,
    "nameKey": "moyamba",
    "nameId": 2674,
    "zone": "6CW9"
  },
  "spot": {
    "full": "6CW95H8C+32",
    "short": "5H8C+32 Moyamba",
    "precise": "6CW95H8C+32J",
    "town": "Moyamba"
  }
}
```

### Error: outside the country

```sh
curl -s 'http://localhost:8080/v1/at?lat=8.0&lng=-14.5'
```

`422`

```json
{
  "error": {
    "code": "outside_country",
    "message": "That point is outside Sierra Leone."
  }
}
```

## `GET /v1/near?lat=&lng=&radius=&limit=`

Codes whose entrance is within `radius` metres (default 100, at most 500), nearest first; `limit` from 1 to 100 (default 20). `total` counts every code in the radius.

### Codes near a point

```sh
curl -s 'http://localhost:8080/v1/near?lat=8.1602399&lng=-12.4327947&radius=60&limit=2'
```

`200`

```json
{
  "point": {
    "lat": 8.1602399,
    "lng": -12.4327947
  },
  "radiusM": 60.0,
  "count": 2,
  "total": 9,
  "codes": [
    {
      "country": "SL",
      "machine": "SL-03663-15727",
      "remembered": "Moyamba 15727",
      "written": "Moyamba 157 27",
      "spoken": "Moyamba, 157 27",
      "check": 0,
      "number": 15727,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T13:03:17Z",
      "officialAddress": null,
      "coverage": null,
      "area": {
        "id": "03663",
        "plateName": "Moyamba",
        "officialName": "Moyamba",
        "nameProvisional": false,
        "district": "Moyamba",
        "placeLine": "Moyamba District",
        "place": "town",
        "fccArea": false,
        "nameKey": "moyamba",
        "nameId": 2674,
        "zone": "6CW9"
      },
      "zone": {
        "key": "6CW9",
        "name": "Port Loko"
      },
      "placeLine": "Moyamba District",
      "fullLine": "Moyamba 157 27 · Moyamba District",
      "entrance": {
        "lat": 8.1602399,
        "lng": -12.4327947,
        "kind": "centre"
      },
      "spot": {
        "full": "6CW95H68+3V",
        "short": "5H68+3V Moyamba",
        "precise": "6CW95H68+3VW",
        "town": "Moyamba"
      },
      "building": {
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 888.7,
        "rule": "single",
        "estate": null
      },
      "outline": null,
      "record": {
        "machine": "SL-03663-15727",
        "home": "Moyamba 15727",
        "written": "Moyamba 157 27",
        "zone": "03663",
        "official_name": "Moyamba",
        "district": "Moyamba",
        "number": "15727",
        "check": "0",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T13:03:17Z",
        "entrance_lat": "8.1602399",
        "entrance_lng": "-12.4327947",
        "entrance_kind": "centre",
        "plus_code": "5H68+3V Moyamba",
        "fcc_address": "",
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "888.7",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
      "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone",
      "distanceM": 0.0
    },
    {
      "country": "SL",
      "machine": "SL-03663-15703",
      "remembered": "Moyamba 15703",
      "written": "Moyamba 157 03",
      "spoken": "Moyamba, 157 03",
      "check": 0,
      "number": 15703,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T13:03:17Z",
      "officialAddress": null,
      "coverage": null,
      "area": {
        "id": "03663",
        "plateName": "Moyamba",
        "officialName": "Moyamba",
        "nameProvisional": false,
        "district": "Moyamba",
        "placeLine": "Moyamba District",
        "place": "town",
        "fccArea": false,
        "nameKey": "moyamba",
        "nameId": 2674,
        "zone": "6CW9"
      },
      "zone": {
        "key": "6CW9",
        "name": "Port Loko"
      },
      "placeLine": "Moyamba District",
      "fullLine": "Moyamba 157 03 · Moyamba District",
      "entrance": {
        "lat": 8.1599408,
        "lng": -12.4325222,
        "kind": "centre"
      },
      "spot": {
        "full": "6CW95H58+XX",
        "short": "5H58+XX Moyamba",
        "precise": "6CW95H58+XXH",
        "town": "Moyamba"
      },
      "building": {
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 12.7,
        "rule": "single",
        "estate": null
      },
      "outline": null,
      "record": {
        "machine": "SL-03663-15703",
        "home": "Moyamba 15703",
        "written": "Moyamba 157 03",
        "zone": "03663",
        "official_name": "Moyamba",
        "district": "Moyamba",
        "number": "15703",
        "check": "0",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T13:03:17Z",
        "entrance_lat": "8.1599408",
        "entrance_lng": "-12.4325222",
        "entrance_kind": "centre",
        "plus_code": "5H58+XX Moyamba",
        "fcc_address": "",
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "12.7",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
      "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone",
      "distanceM": 44.8
    }
  ]
}
```

### Error: radius too large

```sh
curl -s 'http://localhost:8080/v1/near?lat=8.16&lng=-12.43&radius=900'
```

`400`

```json
{
  "error": {
    "code": "bad_radius",
    "message": "radius is in metres, more than 0 and at most 500."
  }
}
```

## `GET /v1/verify?code=`

Checks a machine code without returning the card: its syntax, whether the number lies in a block of the area, the check digit (computed, and compared when one is given after `·`), and whether it is issued. Always 200 when `code` is present; `valid` and `reason` carry the verdict.

### An issued code

```sh
curl -s 'http://localhost:8080/v1/verify?code=SL-03663-15727'
```

`200`

```json
{
  "code": "SL-03663-15727",
  "syntax": true,
  "valid": true,
  "issued": true,
  "machine": "SL-03663-15727",
  "check": 0,
  "area": "03663",
  "status": "provisional",
  "remembered": "Moyamba 15727"
}
```

### A wrong check digit

```sh
curl -s 'http://localhost:8080/v1/verify?code=SL-03663-15727%C2%B74'
```

`200`

```json
{
  "code": "SL-03663-15727·4",
  "syntax": true,
  "valid": false,
  "issued": false,
  "machine": "SL-03663-15727",
  "check": 0,
  "area": "03663",
  "checkGiven": 4,
  "reason": "the check digit does not match: a digit is wrong or two are swapped"
}
```

### A number in no block of the area

```sh
curl -s 'http://localhost:8080/v1/verify?code=SL-03663-99999'
```

`200`

```json
{
  "code": "SL-03663-99999",
  "syntax": true,
  "valid": false,
  "issued": false,
  "reason": "the number 99999 is not in a block of area 03663"
}
```

### Error: no code given

```sh
curl -s 'http://localhost:8080/v1/verify'
```

`400`

```json
{
  "error": {
    "code": "missing_code",
    "message": "Give the machine code in code, for example ?code=SL-03663-15727."
  }
}
```

## `GET /v1/spot?lat=&lng=`

The Plus Code of a point: 10 characters, 11 (`precise`) and the short form with its reference town.

### The Plus Code of a point

```sh
curl -s 'http://localhost:8080/v1/spot?lat=8.48842&lng=-13.23869'
```

`200`

```json
{
  "lat": 8.48842,
  "lng": -13.23869,
  "full": "6CW8FQQ6+9G",
  "short": "FQQ6+9G Freetown",
  "precise": "6CW8FQQ6+9G7",
  "town": "Freetown",
  "inCountry": true
}
```

## `GET /v1/spot/decode?code=`

The point and cell of a Plus Code, full or short with a reference town (`GET /v1/info` lists the towns).

### A short Plus Code with its town

```sh
curl -s 'http://localhost:8080/v1/spot/decode?code=FQR7%2BHX%20Freetown'
```

`200`

```json
{
  "code": "FQR7+HX Freetown",
  "full": "6CW8FQR7+HX",
  "lat": 8.491437499999998,
  "lng": -13.2350625,
  "bbox": [
    -13.235125,
    8.491374999999998,
    -13.235,
    8.491499999999998
  ],
  "inCountry": true
}
```

### Error: a short code without its town

```sh
curl -s 'http://localhost:8080/v1/spot/decode?code=FQR7%2BHX'
```

`422`

```json
{
  "error": {
    "code": "bad_spot",
    "message": "A short Plus Code needs its town, like FQQ6+9G Freetown."
  }
}
```

## `GET /v1/zones`

The zones: one per registry file, each a 4-character Plus Code area of 1° × 1°. A zone is named after the district holding most of its compounds. (The example below shows the first three of thirteen.)

### Every zone

```sh
curl -s 'http://localhost:8080/v1/zones'
```

`200`

```json
{
  "zones": [
    {
      "key": "6CRC",
      "name": "Pujehun",
      "districts": [
        "Pujehun"
      ],
      "bbox": [
        -12.0,
        6.0,
        -11.0,
        7.0
      ],
      "areas": 7,
      "codes": 1074
    },
    {
      "key": "6CV8",
      "name": "Bonthe",
      "districts": [
        "Bonthe"
      ],
      "bbox": [
        -14.0,
        7.0,
        -13.0,
        8.0
      ],
      "areas": 1,
      "codes": 125
    },
    {
      "key": "6CV9",
      "name": "Bonthe",
      "districts": [
        "Bonthe",
        "Moyamba",
        "Bo",
        "Sierra Leone"
      ],
      "bbox": [
        -13.0,
        7.0,
        -12.0,
        8.0
      ],
      "areas": 368,
      "codes": 66647
    }
  ]
}
```

## `GET /v1/zones/{key}`

One zone with its areas.

### One zone with its areas

```sh
curl -s 'http://localhost:8080/v1/zones/6CV8'
```

`200`

```json
{
  "key": "6CV8",
  "name": "Bonthe",
  "districts": [
    "Bonthe"
  ],
  "bbox": [
    -14.0,
    7.0,
    -13.0,
    8.0
  ],
  "areas": 1,
  "codes": 125,
  "areaList": [
    {
      "id": "03002",
      "plateName": "Mania",
      "officialName": "Mania",
      "nameProvisional": false,
      "district": "Bonthe",
      "placeLine": "Bonthe District",
      "place": "village",
      "fccArea": false,
      "nameKey": "mania",
      "nameId": 2135,
      "zone": "6CV8"
    }
  ]
}
```

### Error: no such zone

```sh
curl -s 'http://localhost:8080/v1/zones/6CZZ'
```

`404`

```json
{
  "error": {
    "code": "zone_not_found",
    "message": "There is no zone 6CZZ. GET /v1/zones lists them."
  }
}
```

## `GET /v1/zones/{key}/codes?after=&limit=`

Every code of a zone in machine-code order, a page at a time (`limit` 1 to 1,000, default 100). Pass the `next` value as `after` to get the following page; `next` is `null` on the last page.

### Codes of a zone, one page

```sh
curl -s 'http://localhost:8080/v1/zones/6CV8/codes?limit=1'
```

`200`

```json
{
  "zone": "6CV8",
  "count": 1,
  "next": "SL-03002-1001",
  "codes": [
    {
      "country": "SL",
      "machine": "SL-03002-1001",
      "remembered": "Mania 1001",
      "written": "Mania 10 01",
      "spoken": "Mania, 10 01",
      "check": 2,
      "number": 1001,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T13:02:09Z",
      "officialAddress": null,
      "coverage": null,
      "area": {
        "id": "03002",
        "plateName": "Mania",
        "officialName": "Mania",
        "nameProvisional": false,
        "district": "Bonthe",
        "placeLine": "Bonthe District",
        "place": "village",
        "fccArea": false,
        "nameKey": "mania",
        "nameId": 2135,
        "zone": "6CV8"
      },
      "zone": {
        "key": "6CV8",
        "name": "Bonthe"
      },
      "placeLine": "Bonthe District",
      "fullLine": "Mania 10 01 · Bonthe District",
      "entrance": {
        "lat": 7.6259445,
        "lng": -13.0496583,
        "kind": "centre"
      },
      "spot": {
        "full": "6CV8JXG2+94",
        "short": "JXG2+94 Shenge",
        "precise": "6CV8JXG2+94G",
        "town": "Shenge"
      },
      "building": {
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 20.3,
        "rule": "single",
        "estate": null
      },
      "outline": null,
      "record": {
        "machine": "SL-03002-1001",
        "home": "Mania 1001",
        "written": "Mania 10 01",
        "zone": "03002",
        "official_name": "Mania",
        "district": "Bonthe",
        "number": "1001",
        "check": "2",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T13:02:09Z",
        "entrance_lat": "7.6259445",
        "entrance_lng": "-13.0496583",
        "entrance_kind": "centre",
        "plus_code": "JXG2+94 Shenge",
        "fcc_address": "",
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "20.3",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
      "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
    }
  ]
}
```

## `GET /v1/areas/{id}`

One area: its plate and official names, district, seed, blocks of numbers, codes by status, and the national name record it shares with every area of the same name (id, range length, spare and member areas).

### One area

```sh
curl -s 'http://localhost:8080/v1/areas/03663'
```

`200`

```json
{
  "id": "03663",
  "plateName": "Moyamba",
  "officialName": "Moyamba",
  "nameProvisional": false,
  "district": "Moyamba",
  "placeLine": "Moyamba District",
  "place": "town",
  "fccArea": false,
  "nameKey": "moyamba",
  "nameId": 2674,
  "zone": "6CW9",
  "seed": {
    "id": "osm:node/496344427",
    "lat": 8.1593455,
    "lng": -12.4313893,
    "tier": "primary"
  },
  "blocks": [
    {
      "lo": 12000,
      "hi": 20999,
      "digits": 5,
      "size": 9000
    }
  ],
  "codes": 4313,
  "byStatus": {
    "provisional": 4313
  },
  "name": {
    "key": "moyamba",
    "id": 2674,
    "digits": 5,
    "spare": {
      "lo": 24000,
      "hi": 99999
    },
    "areas": [
      "03662",
      "03663",
      "03664",
      "03665",
      "03666"
    ]
  }
}
```

### Error: no such area

```sh
curl -s 'http://localhost:8080/v1/areas/09999'
```

`404`

```json
{
  "error": {
    "code": "area_not_found",
    "message": "There is no area 09999. Areas are numbered 00001 to 05184."
  }
}
```

## `GET /v1/areas?name=`

The areas a name refers to: the plate name, or an official name (an alias of its plate name), compared after the national name normalisation (case, accents, punctuation, Krio and English spellings).

### Areas by name (official name, through its alias)

```sh
curl -s 'http://localhost:8080/v1/areas?name=Gbangbatoke%20Junction'
```

`200`

```json
{
  "query": "Gbangbatoke Junction",
  "nameKey": "gbangbatoke",
  "areas": [
    {
      "id": "01031",
      "plateName": "Gbangbatoke",
      "officialName": "Gbangbatoke Junction",
      "nameProvisional": false,
      "district": "Moyamba",
      "placeLine": "Moyamba District",
      "place": "village",
      "fccArea": false,
      "nameKey": "gbangbatoke",
      "nameId": 717,
      "zone": "6CW9",
      "seed": {
        "id": "osm:node/2041747142",
        "lat": 8.0004697,
        "lng": -12.4807578,
        "tier": "primary"
      },
      "blocks": [
        {
          "lo": 1000,
          "hi": 2099,
          "digits": 4,
          "size": 1100
        }
      ],
      "codes": 511,
      "byStatus": {
        "provisional": 511
      },
      "name": {
        "key": "gbangbatoke",
        "id": 717,
        "digits": 4,
        "spare": {
          "lo": 2100,
          "hi": 9999
        },
        "areas": [
          "01031"
        ]
      }
    }
  ]
}
```

### Error: no such name

```sh
curl -s 'http://localhost:8080/v1/areas?name=Nowhereville'
```

`404`

```json
{
  "error": {
    "code": "area_not_found",
    "message": "No area of Sierra Leone is called 'Nowhereville'."
  }
}
```

## `POST /v1/codes`

Issues a code (bearer key required; see "One issuer per country" in `server/README.md`). Body: `lat`, `lng` (WGS 84), optionally `outline` (the building as `[lng, lat]` points, 6 m² to 2 ha) and `of` (the machine code of a compound when the point is another door of it, within 80 m). The rules are the national issuer's: a point within 3 m of an issued compound, inside a recorded outline, or an outline overlapping more than half of a recorded one already has a code (409, with that code's card); the area is the nearest primary seed within 4 km, else the nearest secondary seed within 15 km, else the nearest primary seed; the number is the free number halfway between the new compound's neighbours on the national Hilbert curve, inside the area's blocks; a full area takes a new block from its name's spare (`newBlock`), and a name whose spare is used opens a range one digit longer. The new code is `provisional` and `on-demand`. Each key may issue `ISSUE_PER_DAY` codes in 24 hours (429 beyond).

### A new compound

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"lat": 8.1652, "lng": -12.43}' 'http://localhost:8080/v1/codes'
```

`201`

```json
{
  "country": "SL",
  "machine": "SL-03663-17328",
  "remembered": "Moyamba 17328",
  "written": "Moyamba 173 28",
  "spoken": "Moyamba, 173 28",
  "check": 2,
  "number": 17328,
  "status": "provisional",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:39:23Z",
  "officialAddress": null,
  "coverage": null,
  "area": {
    "id": "03663",
    "plateName": "Moyamba",
    "officialName": "Moyamba",
    "nameProvisional": false,
    "district": "Moyamba",
    "placeLine": "Moyamba District",
    "place": "town",
    "fccArea": false,
    "nameKey": "moyamba",
    "nameId": 2674,
    "zone": "6CW9"
  },
  "zone": {
    "key": "6CW9",
    "name": "Port Loko"
  },
  "placeLine": "Moyamba District",
  "fullLine": "Moyamba 173 28 · Moyamba District",
  "entrance": {
    "lat": 8.1652,
    "lng": -12.43,
    "kind": "centre"
  },
  "spot": {
    "full": "6CW95H8C+32",
    "short": "5H8C+32 Moyamba",
    "precise": "6CW95H8C+32J",
    "town": "Moyamba"
  },
  "building": {
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "outline": null,
  "record": {
    "machine": "SL-03663-17328",
    "home": "Moyamba 17328",
    "written": "Moyamba 173 28",
    "zone": "03663",
    "official_name": "Moyamba",
    "district": "Moyamba",
    "number": "17328",
    "check": "2",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:39:23Z",
    "entrance_lat": "8.1652000",
    "entrance_lng": "-12.4300000",
    "entrance_kind": "centre",
    "plus_code": "5H8C+32 Moyamba",
    "fcc_address": "",
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
}
```

### Another door of a compound

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"lat": 8.1603299, "lng": -12.4327947, "of": "SL-03663-15727"}' 'http://localhost:8080/v1/codes'
```

`201`

```json
{
  "country": "SL",
  "machine": "SL-03663-15726",
  "remembered": "Moyamba 15726",
  "written": "Moyamba 157 26",
  "spoken": "Moyamba, 157 26",
  "check": 2,
  "number": 15726,
  "status": "provisional",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:39:23Z",
  "officialAddress": null,
  "coverage": null,
  "area": {
    "id": "03663",
    "plateName": "Moyamba",
    "officialName": "Moyamba",
    "nameProvisional": false,
    "district": "Moyamba",
    "placeLine": "Moyamba District",
    "place": "town",
    "fccArea": false,
    "nameKey": "moyamba",
    "nameId": 2674,
    "zone": "6CW9"
  },
  "zone": {
    "key": "6CW9",
    "name": "Port Loko"
  },
  "placeLine": "Moyamba District",
  "fullLine": "Moyamba 157 26 · Moyamba District",
  "entrance": {
    "lat": 8.1603299,
    "lng": -12.4327947,
    "kind": "door"
  },
  "spot": {
    "full": "6CW95H68+4V",
    "short": "5H68+4V Moyamba",
    "precise": "6CW95H68+4VP",
    "town": "Moyamba"
  },
  "building": {
    "class": "",
    "use": "residential",
    "kind": "door",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "outline": null,
  "record": {
    "machine": "SL-03663-15726",
    "home": "Moyamba 15726",
    "written": "Moyamba 157 26",
    "zone": "03663",
    "official_name": "Moyamba",
    "district": "Moyamba",
    "number": "15726",
    "check": "2",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:39:23Z",
    "entrance_lat": "8.1603299",
    "entrance_lng": "-12.4327947",
    "entrance_kind": "door",
    "plus_code": "5H68+4V Moyamba",
    "fcc_address": "",
    "class": "",
    "use": "residential",
    "kind": "door",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
}
```

### A new compound with its outline

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"lat": 8.16585, "lng": -12.42975, "outline": [[-12.4298, 8.1658], [-12.4297, 8.1658], [-12.4297, 8.1659], [-12.4298, 8.1659]]}' 'http://localhost:8080/v1/codes'
```

`201`

```json
{
  "country": "SL",
  "machine": "SL-03663-17160",
  "remembered": "Moyamba 17160",
  "written": "Moyamba 171 60",
  "spoken": "Moyamba, 171 60",
  "check": 3,
  "number": 17160,
  "status": "provisional",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:39:23Z",
  "officialAddress": null,
  "coverage": null,
  "area": {
    "id": "03663",
    "plateName": "Moyamba",
    "officialName": "Moyamba",
    "nameProvisional": false,
    "district": "Moyamba",
    "placeLine": "Moyamba District",
    "place": "town",
    "fccArea": false,
    "nameKey": "moyamba",
    "nameId": 2674,
    "zone": "6CW9"
  },
  "zone": {
    "key": "6CW9",
    "name": "Port Loko"
  },
  "placeLine": "Moyamba District",
  "fullLine": "Moyamba 171 60 · Moyamba District",
  "entrance": {
    "lat": 8.16585,
    "lng": -12.42975,
    "kind": "centre"
  },
  "spot": {
    "full": "6CW95H8C+84",
    "short": "5H8C+84 Moyamba",
    "precise": "6CW95H8C+84R",
    "town": "Moyamba"
  },
  "building": {
    "class": "residential.house",
    "use": "residential",
    "kind": "building",
    "structures": 1,
    "floorAreaM2": 121.8,
    "rule": null,
    "estate": null
  },
  "outline": [
    [
      -12.4298,
      8.1658
    ],
    [
      -12.4297,
      8.1658
    ],
    [
      -12.4297,
      8.1659
    ],
    [
      -12.4298,
      8.1659
    ]
  ],
  "record": {
    "machine": "SL-03663-17160",
    "home": "Moyamba 17160",
    "written": "Moyamba 171 60",
    "zone": "03663",
    "official_name": "Moyamba",
    "district": "Moyamba",
    "number": "17160",
    "check": "3",
    "status": "provisional",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:39:23Z",
    "entrance_lat": "8.1658500",
    "entrance_lng": "-12.4297500",
    "entrance_kind": "centre",
    "plus_code": "5H8C+84 Moyamba",
    "fcc_address": "",
    "class": "residential.house",
    "use": "residential",
    "kind": "building",
    "structures": "1",
    "floor_area_m2": "121.8",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
}
```

### Error: the compound already has a code

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"lat": 8.1602399, "lng": -12.4327947}' 'http://localhost:8080/v1/codes'
```

`409`

```json
{
  "error": {
    "code": "code_exists",
    "message": "This compound already has its code: Moyamba 15727.",
    "card": {
      "country": "SL",
      "machine": "SL-03663-15727",
      "remembered": "Moyamba 15727",
      "written": "Moyamba 157 27",
      "spoken": "Moyamba, 157 27",
      "check": 0,
      "number": 15727,
      "status": "provisional",
      "issued": "bulk",
      "issuedAt": "2026-10-20T13:03:17Z",
      "officialAddress": null,
      "coverage": null,
      "area": {
        "id": "03663",
        "plateName": "Moyamba",
        "officialName": "Moyamba",
        "nameProvisional": false,
        "district": "Moyamba",
        "placeLine": "Moyamba District",
        "place": "town",
        "fccArea": false,
        "nameKey": "moyamba",
        "nameId": 2674,
        "zone": "6CW9"
      },
      "zone": {
        "key": "6CW9",
        "name": "Port Loko"
      },
      "placeLine": "Moyamba District",
      "fullLine": "Moyamba 157 27 · Moyamba District",
      "entrance": {
        "lat": 8.1602399,
        "lng": -12.4327947,
        "kind": "centre"
      },
      "spot": {
        "full": "6CW95H68+3V",
        "short": "5H68+3V Moyamba",
        "precise": "6CW95H68+3VW",
        "town": "Moyamba"
      },
      "building": {
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": 1,
        "floorAreaM2": 888.7,
        "rule": "single",
        "estate": null
      },
      "outline": null,
      "record": {
        "machine": "SL-03663-15727",
        "home": "Moyamba 15727",
        "written": "Moyamba 157 27",
        "zone": "03663",
        "official_name": "Moyamba",
        "district": "Moyamba",
        "number": "15727",
        "check": "0",
        "status": "provisional",
        "issued": "bulk",
        "issued_at": "2026-10-20T13:03:17Z",
        "entrance_lat": "8.1602399",
        "entrance_lng": "-12.4327947",
        "entrance_kind": "centre",
        "plus_code": "5H68+3V Moyamba",
        "fcc_address": "",
        "class": "unknown",
        "use": "residential",
        "kind": "building",
        "structures": "1",
        "floor_area_m2": "888.7",
        "rule": "single",
        "estate": ""
      },
      "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
      "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
    }
  }
}
```

### Error: no key

```sh
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"lat": 8.17, "lng": -12.43}' 'http://localhost:8080/v1/codes'
```

`401`

```json
{
  "error": {
    "code": "unauthorized",
    "message": "A valid issuing key is needed: Authorization: Bearer <key>."
  }
}
```

### Error: a read-only server

```sh
# on a server started without ISSUE_KEYS
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"lat": 8.17, "lng": -12.43}' 'http://localhost:8080/v1/codes'
```

`403`

```json
{
  "error": {
    "code": "read_only",
    "message": "This server is read-only. Only the issuer designated for the country issues codes (see server/README.md, \"One issuer per country\")."
  }
}
```

### Error: outline too small

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"lat": 8.17, "lng": -12.44, "outline": [[-12.44, 8.17], [-12.44001, 8.17], [-12.44001, 8.17001]]}' 'http://localhost:8080/v1/codes'
```

`422`

```json
{
  "error": {
    "code": "bad_outline",
    "message": "That outline is 1 m², but a compound's is between 6 m² and 2 ha."
  }
}
```

## `PATCH /v1/codes/{machine}`

Changes a code (bearer key required): `status` (`provisional`, `confirmed` or `retired`) and/or `entrance` (`{lat, lng}`, at most 80 m from the current one; the entrance becomes a `gate` and its Plus Code follows). A retired code never changes again and its number is never issued again.

### Confirm a code

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"status": "confirmed"}' 'http://localhost:8080/v1/codes/SL-03663-17328'
```

`200`

```json
{
  "country": "SL",
  "machine": "SL-03663-17328",
  "remembered": "Moyamba 17328",
  "written": "Moyamba 173 28",
  "spoken": "Moyamba, 173 28",
  "check": 2,
  "number": 17328,
  "status": "confirmed",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:39:23Z",
  "officialAddress": null,
  "coverage": null,
  "area": {
    "id": "03663",
    "plateName": "Moyamba",
    "officialName": "Moyamba",
    "nameProvisional": false,
    "district": "Moyamba",
    "placeLine": "Moyamba District",
    "place": "town",
    "fccArea": false,
    "nameKey": "moyamba",
    "nameId": 2674,
    "zone": "6CW9"
  },
  "zone": {
    "key": "6CW9",
    "name": "Port Loko"
  },
  "placeLine": "Moyamba District",
  "fullLine": "Moyamba 173 28 · Moyamba District",
  "entrance": {
    "lat": 8.1652,
    "lng": -12.43,
    "kind": "centre"
  },
  "spot": {
    "full": "6CW95H8C+32",
    "short": "5H8C+32 Moyamba",
    "precise": "6CW95H8C+32J",
    "town": "Moyamba"
  },
  "building": {
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "outline": null,
  "record": {
    "machine": "SL-03663-17328",
    "home": "Moyamba 17328",
    "written": "Moyamba 173 28",
    "zone": "03663",
    "official_name": "Moyamba",
    "district": "Moyamba",
    "number": "17328",
    "check": "2",
    "status": "confirmed",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:39:23Z",
    "entrance_lat": "8.1652000",
    "entrance_lng": "-12.4300000",
    "entrance_kind": "centre",
    "plus_code": "5H8C+32 Moyamba",
    "fcc_address": "",
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
}
```

### Move the entrance to the gate

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"entrance": {"lat": 8.16525, "lng": -12.43002}}' 'http://localhost:8080/v1/codes/SL-03663-17328'
```

`200`

```json
{
  "country": "SL",
  "machine": "SL-03663-17328",
  "remembered": "Moyamba 17328",
  "written": "Moyamba 173 28",
  "spoken": "Moyamba, 173 28",
  "check": 2,
  "number": 17328,
  "status": "confirmed",
  "issued": "on-demand",
  "issuedAt": "2026-10-21T13:39:23Z",
  "officialAddress": null,
  "coverage": null,
  "area": {
    "id": "03663",
    "plateName": "Moyamba",
    "officialName": "Moyamba",
    "nameProvisional": false,
    "district": "Moyamba",
    "placeLine": "Moyamba District",
    "place": "town",
    "fccArea": false,
    "nameKey": "moyamba",
    "nameId": 2674,
    "zone": "6CW9"
  },
  "zone": {
    "key": "6CW9",
    "name": "Port Loko"
  },
  "placeLine": "Moyamba District",
  "fullLine": "Moyamba 173 28 · Moyamba District",
  "entrance": {
    "lat": 8.16525,
    "lng": -12.43002,
    "kind": "gate"
  },
  "spot": {
    "full": "6CW95H89+4X",
    "short": "5H89+4X Moyamba",
    "precise": "6CW95H89+4X5",
    "town": "Moyamba"
  },
  "building": {
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": 0,
    "floorAreaM2": 0.0,
    "rule": null,
    "estate": null
  },
  "outline": null,
  "record": {
    "machine": "SL-03663-17328",
    "home": "Moyamba 17328",
    "written": "Moyamba 173 28",
    "zone": "03663",
    "official_name": "Moyamba",
    "district": "Moyamba",
    "number": "17328",
    "check": "2",
    "status": "confirmed",
    "issued": "on-demand",
    "issued_at": "2026-10-21T13:39:23Z",
    "entrance_lat": "8.1652500",
    "entrance_lng": "-12.4300200",
    "entrance_kind": "gate",
    "plus_code": "5H89+4X Moyamba",
    "fcc_address": "",
    "class": "",
    "use": "residential",
    "kind": "building",
    "structures": "0",
    "floor_area_m2": "0.0",
    "rule": "",
    "estate": ""
  },
  "credit": "N-Ways Addressing for Sierra Leone, © N-WAYS LIMITED (nways.ng)",
  "creditUrl": "https://github.com/n-ways/open-addresses-sierra-leone"
}
```

### Error: entrance more than 80 m away

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"entrance": {"lat": 8.17, "lng": -12.43}}' 'http://localhost:8080/v1/codes/SL-03663-17328'
```

`422`

```json
{
  "error": {
    "code": "too_far",
    "message": "The new entrance is more than 80 m from Moyamba 17328."
  }
}
```

### Error: unknown status

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' \
  -d '{"status": "deleted"}' 'http://localhost:8080/v1/codes/SL-03663-17328'
```

`400`

```json
{
  "error": {
    "code": "bad_status",
    "message": "status is provisional, confirmed or retired."
  }
}
```

## Other paths and methods

An unknown path answers 404 `not_found`; a known path with the wrong method answers 405 `method_not_allowed`.

### Error: no such endpoint

```sh
curl -s 'http://localhost:8080/v1/codes'
```

`405`

```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "GET is not allowed here; use POST."
  }
}
```


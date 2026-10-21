# The registry server

A ready-made HTTP service for the N-Ways codes of Sierra Leone. It serves every published code from [`registry/`](../registry/) through a JSON API and, on the deployment designated as the country's issuer, issues new codes by exactly the rules of the national issuer, so that every deployment gives the same answer for the same question.

- Python 3.9 or newer, standard library only (SQLite, `http.server`). No packages to install.
- One command to deploy with Docker; three commands without it.
- The API is described in [`openapi.yaml`](openapi.yaml) (OpenAPI 3.1) and, with a real request and response for every endpoint, in [`docs/api.md`](../docs/api.md).

| | |
|---|---|
| Database | about 650 MB for the 1,359,282 published codes (SQLite, WAL mode) |
| Import | about 20 seconds on a laptop; under 100 MB of memory |
| Serving | a few milliseconds per request; under 150 MB of memory |

## Deploy with Docker

From the root of this repository:

```sh
docker compose up -d
curl -s http://localhost:8080/v1/health
```

The compose file publishes the API on the host's loopback address only (`127.0.0.1:8080`; set `HOST_PORT` for another port), ready for the TLS proxy described below. On its first start the container finds its database volume empty, imports the registry bundled in the image (checking every file against `registry/MANIFEST.json`) and starts serving. Later starts serve the database as it stands. The container runs as an unprivileged user and reports its health to Docker from `GET /v1/health`.

The deployment is read-only unless `ISSUE_KEYS` is set (see [One issuer per country](#one-issuer-per-country)):

```sh
ISSUE_KEYS="$(openssl rand -hex 24)" docker compose up -d
```

## Run with plain Python

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
python3 -m server serve  --db data/addresses.sqlite --port 8080
python3 -m server export --db data/addresses.sqlite --out out/registry   # the registry, in the published format
```

Run the commands from the repository root: the server uses the reference engine in `engine/reference/` and the frozen register in `engine/data/`.

## Configuration

| Variable | Option | Default | Meaning |
|---|---|---|---|
| `ADDRESSES_DB` | `--db` | `data/addresses.sqlite` | the database file |
| `PORT` | `--port` | `8080` | the port to listen on |
| `HOST` | `--host` | `0.0.0.0` | the address to listen on |
| `ISSUE_KEYS` | | empty | comma-separated bearer keys allowed to issue and change codes; empty means read-only |
| `ISSUE_PER_DAY` | `--issue-per-day` | `5` | codes each key may issue in any 24 hours |
| `CORS_ORIGINS` | | empty | comma-separated origins allowed to call the API from a browser, or `*` |
| `REGISTRY` | `--registry` | `registry` | the registry directory `import` reads |

Keys are compared in constant time and never stored: the database records a short hash of the key beside each code it issues (`issue_log`) and each change (`events`), so that an issuer can tell which of its clients did what.

## Behind a reverse proxy with TLS

Serve the API over HTTPS only. The server speaks plain HTTP on its port; put a TLS-terminating proxy in front of it and do not publish port 8080 beyond the host. With Caddy, which obtains and renews certificates by itself:

```
addresses.example.gov.sl {
    reverse_proxy 127.0.0.1:8080
}
```

With nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name addresses.example.gov.sl;
    ssl_certificate     /etc/letsencrypt/live/addresses.example.gov.sl/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/addresses.example.gov.sl/privkey.pem;
    client_max_body_size 64k;
    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

When publishing through Docker, bind the container to the loopback interface (`"127.0.0.1:8080:8080"` in `docker-compose.yml`).

## Back up

The database is one SQLite file. Take a consistent copy while the server runs with SQLite's online backup:

```sh
sqlite3 data/addresses.sqlite ".backup 'backup/addresses-$(date +%F).sqlite'"
# in Docker:
docker compose exec registry python3 -c "import sqlite3; s = sqlite3.connect('/data/addresses.sqlite'); d = sqlite3.connect('/data/backup.sqlite'); s.backup(d)"
```

An issuing deployment should also export the registry after each day of issuing (`python3 -m server export`) and keep the exports: an export is the published format, verifiable against its own `MANIFEST.json`, and any deployment can import it.

## Update to a newer registry

A newer registry replaces the database as a whole:

```sh
git pull                                      # or copy the new registry/ directory
python3 -m server import --registry registry --db data/addresses.sqlite
```

The import builds the new database beside the old one and swaps it in only when every file has passed its checks, so a failed import leaves the running database untouched. Restart the server afterwards (`docker compose up -d --build` with Docker; the volume must then be emptied first, or the import run inside the container: `docker compose exec registry python3 -m server import --registry /app/registry --db /data/addresses.sqlite`).

The import refuses to replace a database that holds codes issued or changed since its last export: those codes exist nowhere else. Export them first and send the export to the issuer, or pass `--force` to discard them deliberately.

## One issuer per country

**A deployment issues codes only if the State or N-WAYS LIMITED has designated it as the country's issuer. Every other deployment runs read-only, with no `ISSUE_KEYS`.**

A number is unique because one register decides it. Two deployments that both issue would each find the same free number for two different compounds in the same area, and the country would then have two homes with one address: the failure an address system exists to prevent. The same holds for extension blocks: two issuers would each take the same units from a name's spare. Read-only deployments are safe in any number; they serve the same registry and give identical answers.

The designated issuer publishes its exports; every other deployment updates from them. A change of issuer is a hand-over: the old issuer stops issuing, exports, and the new issuer imports that export before it issues anything.

## The issuing rules

`POST /v1/codes` applies the national issuer's rules unchanged (`engine/SPEC.md`, sections 4.4, 4.4a and 8):

0. **The border decides.** A point more than 300 m outside Sierra Leone's national border is refused with 422 `outside_country`, even when an area's seed or a Plus Code would take it: the code of one country is never given to a building in a neighbouring country. The border is OpenStreetMap's admin_level 2 boundary, shipped simplified in `engine/data/country.geojson`; the tolerance is 300 m less the outline's measured distance from the full line (`deviationM`, about 55 m), so an accepted point is never more than 300 m outside the full border. A new door (`PATCH` with an entrance) is held to the same rule.
1. **Already has a code.** A point within 3 m of an issued compound's entrance, or inside the outline of a compound issued with one, or an outline covering more than half of such an outline (or half of its own area), already has a code: the answer is 409 with that code's card. Retired codes are not counted.
2. **Outline.** When given, between 6 m² and 2 ha.
3. **Another door.** With `of`, the point must be within 80 m of that compound's entrance; the new code is in the same area.
4. **Area.** Otherwise the area of the nearest primary seed (city, town, suburb, quarter, village) within 4 km, else the nearest secondary seed within 15 km, else the nearest primary seed at any distance.
5. **Number.** The free number halfway between the new compound's neighbours on the national Hilbert curve, inside the area's first block with room (`next_free_number` of the reference engine). Retired numbers are never given again.
6. **Extension block.** A full area takes the next whole units of its name's range holding twice its compounds, from the bottom of the name's spare; when the spare is too small, the name opens a range one digit longer. A name full at 5 digits takes a council-chosen qualifier first (409 `name_full`). The new block is recorded in the database and appears in `areas.csv` on export.
7. **The code.** Machine, remembered and written forms; `status: provisional`, `issued: on-demand`; the entrance is the point (`centre`, or `door` for another door); in Freetown City Council's area the point's Plus Code is also the official address.
8. **Limit.** `ISSUE_PER_DAY` codes per key in any 24 hours.

These rules are checked against the national issuer: [`testdata/parity.json`](testdata/parity.json) holds 32 issue requests and 7 extension-block cases whose expected numbers, forms, spot codes and blocks were computed by the issuer's own engine on the same state; the tests replay them.

What the registry publishes is the address register: codes, entrances and building summaries. Building footprints are not part of it, so "already has a code" and "what is here" use the entrance points of published codes, plus the outlines of compounds this server has issued with one.

## Tests

```sh
python3 -m unittest discover -s server/tests -t .
```

The tests import a fixture registry (`testdata/registry/`: the 125 real codes of zone 6CV8 and the full area table), check that an export reproduces it byte for byte, call every endpoint for its answers and its errors, replay the parity cases, and cover extension blocks, duplicate checks, doors, keys, limits, changes and retirement.

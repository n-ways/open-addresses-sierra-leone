#!/usr/bin/env python3
"""Extract every Sierra Leonean building footprint with its raw profile facts.

One DuckDB run (memory_limit 3GB, spilling to the work folder) over N-Ways' map
data, read-only:
  data/detail/countries/sierra-leone/buildings-src.geojsonseq  OpenStreetMap buildings (ODbL)
  data/detail/ml/SL.parquet                                    Google Open Buildings / Microsoft footprints (CC BY 4.0 / ODbL)
plus the small inputs of tools/prepare-inputs.py in the work folder, among them the
national boundary (country.geojson, territorial waters included, so islets are in).

The border decides (tools/border.py): a footprint whose centre is outside the national
border is in a neighbouring country and is dropped here, whatever zone or estate outline
holds it. This is stricter than the 300 m the issuer allows on the line; the grouping
checks every compound against the border again (tools/issue_registry.py).

Every footprint whose centre is inside the border gets:
  eid      the smallest closed wall, fence or hedge holding its centre (SPEC 4.2, rule 1)
  estate   the N-Ways estate, government, military or police compound holding it (rule 2)
  label    its district (admin_level 5); Western Area Urban is Freetown City Council's area
  poi      the N-Ways places on it

Writes <work>/buildings-raw.csv (one row per footprint, with a stable row id bid and its
outline as WKT); tools/assign-areas.py then gives each its address area, and
tools/sort-buildings.py writes <work>/buildings.csv sorted by area.

  python3 tools/extract-buildings.py <work folder>
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.environ.get('NWAYS_ROOT', '.')   # the N-Ways map data (data/ below it)
work = os.path.abspath(sys.argv[1])
osm = os.path.join(ROOT, 'data', 'detail', 'countries', 'sierra-leone', 'buildings-src.geojsonseq')
ml = os.path.join(ROOT, 'data', 'detail', 'ml', 'SL.parquet')
W = lambda f: os.path.join(work, f)

TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made',
        'government', 'craft', 'building:levels', 'height', 'name', 'roof:material', 'building:material']
tag_cols = ', '.join(f"json_extract_string(j, '$.properties.\"{t}\"') AS \"{t}\"" for t in TAGS)
null_cols = ', '.join(f"NULL::VARCHAR AS \"{t}\"" for t in TAGS)
area_m2 = "ST_Area(g) * 110574.0 * 111320.0 * cos(radians(ST_Y(ST_Centroid(g))))"

sql = f"""
SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false; SET temp_directory='{W('duck-tmp')}';
INSTALL spatial; LOAD spatial;
CREATE TABLE ol AS SELECT ST_Union_Agg(geom) AS geom FROM ST_Read('{W('country.geojson')}');
CREATE TABLE e AS SELECT eid, kind, areaM2, geom FROM ST_Read('{W('enclosures.geojson')}');
CREATE TABLE es AS SELECT estate, kind, geom FROM ST_Read('{W('estates.geojson')}');
CREATE TABLE lb AS SELECT lid, "name", geom FROM ST_Read('{W('labels.geojson')}');
CREATE TABLE p AS SELECT id, "name", category, ST_Point(lon, lat) AS g FROM read_csv('{W('places.csv')}', header=true,
  columns={{'id':'VARCHAR','name':'VARCHAR','category':'VARCHAR','source':'VARCHAR','lon':'DOUBLE','lat':'DOUBLE'}});
CREATE TABLE raw AS
  SELECT 'osm' AS src, json_extract_string(j, '$.properties."@type"') || '/' || json_extract_string(j, '$.properties."@id"') AS oid,
         ST_GeomFromGeoJSON(json_extract(j, '$.geometry')) AS g, {tag_cols}
  FROM (SELECT ltrim(line, chr(30)) AS j FROM read_csv('{osm}', columns={{'line':'VARCHAR'}}, header=false, delim=chr(1), quote='', escape='', max_line_size=16000000) WHERE length(line) > 2)
  UNION ALL
  SELECT 'ml', NULL, geometry, {null_cols} FROM '{ml}';
CREATE TABLE b AS SELECT row_number() OVER () AS bid, *, ST_Centroid(g) AS c, {area_m2} AS area,
  ST_Perimeter_Spheroid(ST_FlipCoordinates(g)) AS perim FROM raw;
DROP TABLE raw;
DELETE FROM b WHERE NOT ST_Contains((SELECT geom FROM ol), b.c);   -- the border decides: over it is a neighbouring country
CREATE TABLE be AS SELECT bid, arg_min(eid, areaM2) AS eid FROM (SELECT b.bid, e.eid, e.areaM2 FROM b JOIN e ON ST_Contains(e.geom, b.c)) GROUP BY bid;
CREATE TABLE bes AS SELECT b.bid, min(es.estate) AS estate FROM b JOIN es ON ST_Contains(es.geom, b.c) GROUP BY b.bid;
CREATE TABLE bl AS SELECT b.bid, min(lb."name") AS label FROM b JOIN lb ON ST_Contains(lb.geom, b.c) GROUP BY b.bid;
CREATE TABLE bp AS SELECT bid, string_agg(DISTINCT category, '|' ORDER BY category) AS poi
  FROM (SELECT b.bid, p.category FROM b JOIN p ON ST_Intersects(b.g, ST_Buffer(p.g, 0.00004))) GROUP BY bid;
COPY (SELECT b.bid, b.src, b.oid, round(ST_X(b.c), 7) AS lon, round(ST_Y(b.c), 7) AS lat,
        round(b.area, 1) AS area, round(b.perim, 1) AS perim, {', '.join(f'b."{t}"' for t in TAGS)},
        be.eid, bes.estate, bl.label, bp.poi, ST_AsText(ST_ReducePrecision(b.g, 0.0000001)) AS wkt
      FROM b LEFT JOIN be USING (bid) LEFT JOIN bes USING (bid) LEFT JOIN bl USING (bid) LEFT JOIN bp USING (bid) ORDER BY b.bid)
  TO '{W('buildings-raw.csv')}' (HEADER, DELIMITER ',');
COPY (SELECT eid, kind, areaM2 FROM e ORDER BY eid) TO '{W('enclosure-gates.csv')}' (HEADER, DELIMITER ',');
SELECT count(*) AS footprints, sum(CASE WHEN src='osm' THEN 1 ELSE 0 END) AS osm FROM b;
"""
r = subprocess.run(['duckdb', '-csv'], input=sql, capture_output=True, text=True)
print(r.stdout[-2000:], r.stderr[-3000:])
sys.exit(r.returncode)

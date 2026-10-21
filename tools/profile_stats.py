#!/usr/bin/env python3
"""Sierra Leone: building profiles, compound and block statistics for the model.

Reads (read-only) N-Ways' map data and writes model/profile-stats.json:

  * every building's inferred use class (Sierra Leonean taxonomy, docs/model.md
    "Building profile"), confidence, footprint area, perimeter, height,
    floors and floor area, aggregated nationally and for Freetown (Western Area Urban);
  * buildings per chiefdom (geoBoundaries ADM3, 2016 boundaries; they are
    statistics only: no Sierra Leone code depends on a boundary);
  * buildings per Plus Code block (~275 m), to size compound serials.

Inputs
  data/detail/countries/sierra-leone/buildings-src.geojsonseq   OpenStreetMap buildings (ODbL)
  data/detail/ml/SL.parquet                                 Google/Microsoft footprints, h in metres
  places CSV (lon,lat,category,source,name)                 N-Ways places (an export of the N-Ways gazetteer)
  Western Area Urban outline (GeoJSON)                      geoBoundaries SLE ADM2 (CC BY 3.0 IGO)
  chiefdoms (GeoJSON)                                       geoBoundaries SLE ADM3 (CC BY 4.0)

  tools/profile_stats.py --places places-SL.csv --capital capital-SL.geojson \
      --districts geoBoundaries-SLE-ADM3.geojson ...

Runs under a 3 GB DuckDB memory cap.
Standard library only, plus the duckdb command-line tool.
"""
import argparse, csv, io, json, math, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.environ.get('NWAYS_ROOT', '.')   # the N-Ways map data (data/ below it)
UTM = 'EPSG:32628'  # UTM 28N: Freetown and the Western Area (scale error under 0.4% at the eastern border)
# Structures per hectare above which footprints are not grouped into compounds
# (Kroo Bay, Susan's Bay, Mabella, the hillside settlements: no walls; docs/model.md).
DENSE = 70
YARD_M, YARD_MAX_HA, JOIN_M = 8, 25, 4

# Sierra Leonean use classes from OpenStreetMap building=* (docs/model.md, "Building profile").
OSM_BUILDING = {
    'residential': 'residential.unspecified', 'house': 'residential.unspecified', 'detached': 'residential.unspecified',
    'semidetached_house': 'residential.unspecified', 'terrace': 'residential.unspecified', 'bungalow': 'residential.unspecified',
    'apartments': 'residential.apartment', 'dormitory': 'residential.apartment',
    'hut': 'residential.hut', 'cabin': 'residential.hut',
    'commercial;residential': 'mixed_use.shop_house', 'residential;commercial': 'mixed_use.shop_house',
    'commercial': 'commercial.shop', 'retail': 'commercial.shop', 'kiosk': 'commercial.shop', 'supermarket': 'commercial.shop',
    'office': 'commercial.office', 'warehouse': 'commercial.warehouse', 'storage_tank': 'industrial.general',
    'market': 'commercial.market',
    'public': 'government', 'government': 'government', 'civic': 'government', 'townhall': 'government', 'courthouse': 'government',
    'school': 'education', 'university': 'education', 'college': 'education', 'kindergarten': 'education',
    'clinic': 'health', 'hospital': 'health',
    'church': 'religious', 'mosque': 'religious', 'chapel': 'religious', 'religious': 'religious', 'cathedral': 'religious',
    'industrial': 'industrial.general', 'factory': 'industrial.general', 'manufacture': 'industrial.general',
    'hotel': 'hospitality',
    'train_station': 'transport', 'transportation': 'transport', 'garage': 'transport', 'garages': 'transport', 'hangar': 'transport',
    'farm': 'agricultural', 'barn': 'agricultural', 'sty': 'agricultural', 'farm_auxiliary': 'agricultural', 'greenhouse': 'agricultural',
    'stable': 'agricultural', 'cowshed': 'agricultural',
    'kitchen': 'ancillary', 'shed': 'ancillary', 'roof': 'ancillary', 'toilets': 'ancillary', 'bathroom': 'ancillary',
    'construction': 'under_construction',
    'ruins': 'ruin', 'abandoned': 'ruin', 'damaged': 'ruin', 'collapsed': 'ruin', 'destroyed': 'ruin',
}
# amenity / shop / office / tourism tags on the building outline itself.
OSM_AMENITY = {
    'school': 'education', 'kindergarten': 'education', 'college': 'education', 'university': 'education', 'library': 'education',
    'clinic': 'health', 'hospital': 'health', 'health center': 'health', 'doctors': 'health', 'pharmacy': 'health', 'dentist': 'health',
    'place_of_worship': 'religious',
    'townhall': 'government', 'police': 'government', 'courthouse': 'government', 'fire_station': 'government', 'post_office': 'government',
    'community_centre': 'government', 'prison': 'government',
    'marketplace': 'commercial.market', 'bank': 'commercial.shop', 'fuel': 'commercial.shop', 'sacco': 'commercial.office',
    'bar': 'hospitality', 'restaurant': 'hospitality', 'cafe': 'hospitality', 'fast_food': 'hospitality', 'pub': 'hospitality',
    'nightclub': 'hospitality', 'cinema': 'hospitality',
    'toilets': 'ancillary', 'bathroom': 'ancillary', 'drinking_water': 'ancillary', 'shower': 'ancillary',
    'bus_station': 'transport', 'parking': 'transport',
}
# N-Ways gazetteer categories for a place inside the footprint.
PLACE = {
    'hospital': 'health', 'pharmacy': 'health', 'school': 'education', 'church': 'religious', 'mosque': 'religious',
    'hotel': 'hospitality', 'food': 'hospitality', 'bar': 'hospitality', 'cafe': 'hospitality', 'fastfood': 'hospitality',
    'shop': 'commercial.shop', 'supermarket': 'commercial.shop', 'bank': 'commercial.shop', 'phones': 'commercial.shop',
    'salon': 'commercial.shop', 'mechanic': 'commercial.shop', 'pos': 'commercial.shop', 'vulcanizer': 'commercial.shop',
    'carwash': 'commercial.shop', 'petrol': 'commercial.shop', 'office': 'commercial.office', 'market': 'commercial.market',
    'police': 'government', 'motorpark': 'transport', 'parking': 'transport', 'charging': 'transport', 'attraction': 'public.culture',
}


def run(cmd, data=None):
    r = subprocess.run(cmd, input=data, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'{cmd[0]} failed: {r.stderr.strip()[-2000:]}')
    return r.stdout


def case(expr, table, default='NULL'):
    parts = ' '.join(f"WHEN {expr} = '{k}' THEN '{v}'" for k, v in table.items())
    return f'CASE {parts} ELSE {default} END'


def sql_q(rows):
    return list(csv.reader(io.StringIO(rows)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--places', required=True)
    ap.add_argument('--capital', required=True)
    ap.add_argument('--districts', required=True)
    ap.add_argument('--enclosures', required=True, help='closed OSM walls/fences (GeoJSON polygons)')
    ap.add_argument('--gates', required=True, help='OSM gates/entrances and N-Ways routing gates (GeoJSON points)')
    ap.add_argument('--nways-compounds', required=True, help='N-Ways gated compounds/sites (data/valhalla/compounds.geojsonseq, LR part)')
    ap.add_argument('--centroids', help='also write every structure centroid and area (CSV lat,lon,area) for tools/area_stats.py')
    ap.add_argument('--out', default=os.path.join(REPO, 'model', 'profile-stats.json'))
    a = ap.parse_args()
    osm = os.path.join(ROOT, 'data', 'detail', 'countries', 'sierra-leone', 'buildings-src.geojsonseq')
    ml = os.path.join(ROOT, 'data', 'detail', 'ml', 'SL.parquet')
    regions = json.load(open(os.path.join(REPO, 'model', 'regions.json')))

    p = lambda k: f"json_extract_string(p, '$.\"{k}\"')"
    material = p('building:material')
    roof = p('roof:material')
    sql = f"""
SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false;
LOAD spatial;
CREATE TABLE raw AS
  SELECT ST_GeomFromGeoJSON(json_extract(l, '$.geometry')) AS g, json_extract(l, '$.properties') AS p
  FROM (SELECT ltrim(line, chr(30)) AS l FROM read_csv('{osm}', columns={{'line':'VARCHAR'}}, header=false,
        delim=chr(1), quote='', escape='', max_line_size=16000000) WHERE length(line) > 2);
CREATE TABLE b AS
  SELECT 'osm' AS src, g,
    lower({p('building')}) AS building, lower({p('amenity')}) AS amenity, lower({p('shop')}) AS shop,
    lower({p('office')}) AS office, lower({p('tourism')}) AS tourism, lower({p('man_made')}) AS man_made,
    lower({material}) AS material, lower({roof}) AS roof,
    TRY_CAST(regexp_extract({p('building:levels')}, '^[0-9]+') AS INTEGER) AS levels,
    TRY_CAST(regexp_extract({p('height')}, '^[0-9.]+') AS DOUBLE) AS osm_h,
    NULL::DOUBLE AS ml_h, {p('name')} IS NOT NULL AS named
  FROM raw;
DROP TABLE raw;
INSERT INTO b SELECT 'ml', geometry, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, h, false FROM '{ml}';
ALTER TABLE b ADD COLUMN id BIGINT; UPDATE b SET id = rowid;
CREATE TABLE m AS
  SELECT id, ST_Centroid(g) AS c, ST_Area(t) AS area, ST_Perimeter(t) AS perim
  FROM (SELECT id, g, ST_Transform(g, 'EPSG:4326', '{UTM}', always_xy := true) AS t FROM b);
CREATE TABLE poi AS SELECT ST_Point(column0::DOUBLE, column1::DOUBLE) AS pt, column2 AS cat FROM read_csv('{a.places}', header=false);
CREATE TABLE inpoi AS
  SELECT b.id, mode(poi.cat) AS cat, count(*) AS n FROM b JOIN poi ON ST_Contains(b.g, poi.pt) GROUP BY b.id;
CREATE TABLE cap AS SELECT geom AS g FROM ST_Read('{a.capital}');
CREATE TABLE dist AS SELECT shapeName AS name, geom AS g FROM ST_Read('{a.districts}');
CREATE TABLE incap AS SELECT m.id FROM m JOIN cap ON ST_Contains(cap.g, m.c);
CREATE TABLE indist AS SELECT m.id, dist.name FROM m JOIN dist ON ST_Contains(dist.g, m.c);
CREATE TABLE prof AS
SELECT b.id, b.src, m.area, m.perim,
  -- height: OpenStreetMap height, else levels x 3 m, else the footprint model's h
  coalesce(b.osm_h, b.levels * 3.0, b.ml_h) AS h,
  CASE WHEN b.osm_h IS NOT NULL THEN 'osm:height' WHEN b.levels IS NOT NULL THEN 'osm:building:levels'
       WHEN b.ml_h IS NOT NULL THEN 'ml:h' ELSE 'none' END AS h_src,
  coalesce(b.levels, greatest(1, round(coalesce(b.osm_h, b.ml_h, 3.0) / 3.0))::INTEGER) AS floors,
  {case('b.building', OSM_BUILDING)} AS c_building,
  coalesce({case('b.amenity', OSM_AMENITY)}, CASE WHEN b.shop IS NOT NULL THEN 'commercial.shop' END,
           CASE WHEN b.office IN ('government','administrative') THEN 'government' WHEN b.office IS NOT NULL THEN 'commercial.office' END,
           CASE WHEN b.tourism IN ('hotel','guest_house','motel','hostel') THEN 'hospitality' END) AS c_amenity,
  {case('inpoi.cat', PLACE)} AS c_place, coalesce(inpoi.n, 0) AS n_places,
  b.material, b.roof, b.building, incap.id IS NOT NULL AS capital, indist.name AS district
FROM b JOIN m USING (id) LEFT JOIN inpoi USING (id) LEFT JOIN incap USING (id) LEFT JOIN indist USING (id);
CREATE TABLE cls AS
SELECT *,
  CASE
    WHEN c_amenity IS NOT NULL THEN c_amenity
    WHEN c_building IS NOT NULL AND c_building <> 'residential.unspecified' THEN c_building
    WHEN c_place IS NOT NULL THEN c_place
    WHEN c_building = 'residential.unspecified' AND (floors >= 3) THEN 'residential.apartment'
    WHEN c_building = 'residential.unspecified' AND material = 'mud' THEN 'residential.mud_house'
    WHEN c_building = 'residential.unspecified' AND (material IN ('metal','tin','zink','wood;metal','tapoline','plastic') ) THEN 'residential.pan_body'
    WHEN c_building = 'residential.unspecified' AND roof = 'thatch' THEN 'residential.hut'
    WHEN c_building = 'residential.unspecified' AND material IN ('brick','cement_block','concrete','cement','bricks') THEN 'residential.block_house'
    WHEN c_building = 'residential.unspecified' THEN 'residential.unspecified'
    WHEN material = 'mud' THEN 'residential.mud_house'
    WHEN area < 6 THEN 'ancillary'
    WHEN area >= 2000 THEN 'commercial.warehouse'
    ELSE 'unknown'
  END AS class,
  CASE
    WHEN c_amenity IS NOT NULL THEN 0.85
    WHEN c_building IS NOT NULL AND c_building <> 'residential.unspecified' THEN 0.85
    WHEN c_place IS NOT NULL THEN CASE WHEN n_places = 1 THEN 0.7 ELSE 0.6 END
    WHEN c_building IS NOT NULL THEN 0.8
    WHEN material = 'mud' THEN 0.6
    WHEN area < 6 OR area >= 2000 THEN 0.35
    ELSE 0.0
  END AS conf
FROM prof;

-- Compounds (docs/model.md "Compounds"): Freetown (Western Area Urban) only, in UTM metres.
CREATE TABLE capb AS SELECT cls.id, cls.area, cls.class, ST_Transform(b.g, 'EPSG:4326', '{UTM}', always_xy := true) AS u
  FROM cls JOIN b USING (id) WHERE cls.capital;
ALTER TABLE capb ADD COLUMN cx DOUBLE; ALTER TABLE capb ADD COLUMN cy DOUBLE;
UPDATE capb SET cx = ST_X(ST_Centroid(u)), cy = ST_Y(ST_Centroid(u));
CREATE TABLE dens AS SELECT floor(cx/100) AS gx, floor(cy/100) AS gy, count(*) AS n FROM capb GROUP BY 1, 2;
CREATE TABLE capd AS SELECT capb.*, dens.n AS per_ha FROM capb JOIN dens ON floor(capb.cx/100) = dens.gx AND floor(capb.cy/100) = dens.gy;
CREATE TABLE enc AS SELECT row_number() OVER () AS eid, ST_Transform(geom, 'EPSG:4326', '{UTM}', always_xy := true) AS u, kind FROM ST_Read('{a.enclosures}');
CREATE TABLE inenc AS SELECT capd.id, min(enc.eid) AS eid FROM capd JOIN enc ON ST_Contains(enc.u, ST_Centroid(capd.u)) GROUP BY 1;
CREATE TABLE gate AS SELECT ST_Transform(geom, 'EPSG:4326', '{UTM}', always_xy := true) AS u, kind FROM ST_Read('{a.gates}');
CREATE TABLE ncomp AS SELECT kind, name, geom AS g FROM ST_Read('{a.nways_compounds}');
-- Proximity rule where no wall is mapped: a satellite (< 30 m2) joins the nearest principal (>= 30 m2,
-- at least twice its size) within JOIN_M, or YARD_M around a village yard (<= YARD_MAX_HA per hectare), unless the hectare holds more than DENSE structures (no grouping).
CREATE TABLE sats AS SELECT id, area, u, ST_Buffer(u, CASE WHEN per_ha <= {YARD_MAX_HA} THEN {YARD_M} ELSE {JOIN_M} END) AS sb
  FROM capd WHERE area < 30 AND per_ha <= {DENSE} AND id NOT IN (SELECT id FROM inenc);
CREATE TABLE prin AS SELECT id, area, u FROM capd WHERE area >= 30 AND id NOT IN (SELECT id FROM inenc);
-- plain ST_Intersects on two columns so DuckDB uses its spatial join, not a range join
CREATE TABLE pairs AS SELECT s.id AS sid, p.id AS pid, s.area AS sa, p.area AS pa, ST_Distance(s.u, p.u) AS d
  FROM sats s JOIN prin p ON ST_Intersects(s.sb, p.u);
CREATE TABLE sat AS SELECT sid, arg_min(pid, d) AS pid FROM pairs WHERE pa >= 2 * sa GROUP BY sid;
CREATE TABLE unit AS
  SELECT capd.id, CASE WHEN inenc.eid IS NOT NULL THEN 'w' || inenc.eid WHEN sat.pid IS NOT NULL THEN 'b' || sat.pid ELSE 'b' || capd.id END AS cid,
         CASE WHEN inenc.eid IS NOT NULL THEN 'wall' WHEN sat.pid IS NOT NULL OR capd.id IN (SELECT pid FROM sat) THEN 'proximity'
              WHEN capd.per_ha > {DENSE} THEN 'dense' ELSE 'single' END AS how
  FROM capd LEFT JOIN inenc USING (id) LEFT JOIN sat ON sat.sid = capd.id;
CREATE TABLE comp AS SELECT cid, count(*) AS n, min(how) AS how FROM unit GROUP BY 1;
"""
    outputs = {
        'sources': "SELECT src, count(*) FROM cls GROUP BY 1",
        'class_all': "SELECT class, count(*), round(avg(conf),2) FROM cls GROUP BY 1 ORDER BY 2 DESC",
        'class_cap': "SELECT class, count(*), round(avg(conf),2) FROM cls WHERE capital GROUP BY 1 ORDER BY 2 DESC",
        'area_all': "SELECT count(*), quantile_cont(area,[0.1,0.25,0.5,0.75,0.9,0.99]), round(avg(area),1), round(sum(area)/1e6,2) FROM cls",
        'area_cap': "SELECT count(*), quantile_cont(area,[0.1,0.25,0.5,0.75,0.9,0.99]), round(avg(area),1), round(sum(area)/1e6,2) FROM cls WHERE capital",
        'perim_cap': "SELECT quantile_cont(perim,[0.1,0.5,0.9]) FROM cls WHERE capital",
        'bins_all': "SELECT CASE WHEN area<12 THEN 'a<12' WHEN area<30 THEN 'b12-30' WHEN area<60 THEN 'c30-60' WHEN area<120 THEN 'd60-120' WHEN area<250 THEN 'e120-250' WHEN area<500 THEN 'f250-500' WHEN area<2000 THEN 'g500-2000' ELSE 'h>=2000' END, count(*) FROM cls GROUP BY 1 ORDER BY 1",
        'bins_cap': "SELECT CASE WHEN area<12 THEN 'a<12' WHEN area<30 THEN 'b12-30' WHEN area<60 THEN 'c30-60' WHEN area<120 THEN 'd60-120' WHEN area<250 THEN 'e120-250' WHEN area<500 THEN 'f250-500' WHEN area<2000 THEN 'g500-2000' ELSE 'h>=2000' END, count(*) FROM cls WHERE capital GROUP BY 1 ORDER BY 1",
        'h_src': "SELECT h_src, count(*) FROM cls GROUP BY 1 ORDER BY 2 DESC",
        'floors_cap': "SELECT floors, count(*) FROM cls WHERE capital GROUP BY 1 ORDER BY 1",
        'floor_area_cap': "SELECT round(sum(area*floors)/1e6,2), quantile_cont(area*floors,[0.5,0.9]) FROM cls WHERE capital",
        'class_area_cap': "SELECT class, round(quantile_cont(area,0.5),1), round(avg(area),1) FROM cls WHERE capital GROUP BY 1 ORDER BY 1",
        'material': "SELECT material, count(*) FROM cls WHERE material IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 12",
        'districts': "SELECT district, count(*), count(*) FILTER (WHERE src='osm') FROM cls WHERE district IS NOT NULL GROUP BY 1 ORDER BY 2 DESC",
        'no_district': "SELECT count(*) FROM cls WHERE district IS NULL",
        'cap_density': "SELECT CASE WHEN per_ha<=20 THEN 'a<=20' WHEN per_ha<=40 THEN 'b21-40' WHEN per_ha<=60 THEN 'c41-60' WHEN per_ha<=" + str(DENSE) + " THEN 'd61-" + str(DENSE) + "' ELSE 'e>" + str(DENSE) + "' END, count(*) FROM capd GROUP BY 1 ORDER BY 1",
        'enc_all': "SELECT kind, count(*) FROM enc GROUP BY 1",
        'enc_cap': "SELECT count(DISTINCT eid), count(*) FROM inenc",
        'enc_sizes': "SELECT n, count(*) FROM (SELECT eid, count(*) n FROM inenc GROUP BY 1) GROUP BY 1 ORDER BY 1",
        'enc_area': "SELECT quantile_cont(ST_Area(u),[0.25,0.5,0.75,0.9]) FROM enc WHERE eid IN (SELECT eid FROM inenc)",
        'comp_how': "SELECT how, count(*), sum(n) FROM comp GROUP BY 1 ORDER BY 1",
        'comp_sizes': "SELECT least(n, 6), count(*) FROM comp GROUP BY 1 ORDER BY 1",
        'gates_all': "SELECT kind, count(*) FROM gate GROUP BY 1 ORDER BY 2 DESC",
        'ncomp': "SELECT kind, count(*), round(sum(ST_Area(ST_Transform(g,'EPSG:4326','" + UTM + "', always_xy := true)))/1e6,2) FROM ncomp GROUP BY 1 ORDER BY 2 DESC",
        'blocks_all': "SELECT count(*), quantile_cont(n,[0.5,0.9,0.99,0.999]), max(n), count(*) FILTER (WHERE n>200) FROM (SELECT floor((ST_Y(c)+90)/0.0025) a, floor((ST_X(c)+180)/0.0025) o, count(*) n FROM m GROUP BY 1,2)",
        'blocks_cap_units': "SELECT count(*), quantile_cont(n,[0.5,0.9,0.99,0.999]), max(n), count(*) FILTER (WHERE n>200) FROM (SELECT floor((ST_Y(m.c)+90)/0.0025) a, floor((ST_X(m.c)+180)/0.0025) o, count(DISTINCT unit.cid) n FROM unit JOIN m USING (id) GROUP BY 1,2)",
        'district_centroid': "SELECT name, ST_Y(ST_Centroid(g)), ST_X(ST_Centroid(g)), ST_Area(ST_Transform(g,'EPSG:4326','" + UTM + "', always_xy := true))/1e6 FROM dist",
    }
    if a.centroids:
        sql += f"\nCOPY (SELECT round(ST_Y(c), 6), round(ST_X(c), 6), round(area, 1) FROM m) TO '{a.centroids}' (HEADER false);"
    for k, q in outputs.items():
        sql += f"\nSELECT '{k}', * FROM ({q});"
    out = run(['duckdb', '-csv', '-noheader'], data=sql)
    res = {}
    for row in sql_q(out):
        if row:
            res.setdefault(row[0], []).append(row[1:])

    def digits_if_one_area(n):
        """Digits a number would need if the whole unit were one address area (docs/model.md §2.3)."""
        d = 3
        while 9 * 10 ** (d - 1) < 2 * n:
            d += 1
        return d

    area_km2 = {n: float(a) for n, _, _, a in res.get('district_centroid', [])}
    districts = []
    for name, n, n_osm in res.get('districts', []):
        n = int(n)
        districts.append({'name': name, 'buildings': n, 'openstreetmap': int(n_osm),
                          'areaKm2': round(area_km2.get(name, 0), 1), 'digitsIfOneArea': digits_if_one_area(n)})

    def fl(x):
        return [round(float(v), 1) for v in x.strip('[]').split(',')]

    stats = {
        'country': 'SL', 'tool': 'tools/profile_stats.py',
        'capital': 'Western Area Urban (Freetown), geoBoundaries SLE ADM2',
        'sources': {k: int(v) for k, v in res.get('sources', [])},
        'classes': {'national': [{'class': c, 'buildings': int(n), 'meanConfidence': float(cf)} for c, n, cf in res.get('class_all', [])],
                    'capital': [{'class': c, 'buildings': int(n), 'meanConfidence': float(cf)} for c, n, cf in res.get('class_cap', [])]},
        'footprintM2': {
            'national': dict(zip(['buildings', 'quantiles10_25_50_75_90_99', 'mean', 'totalKm2'],
                                 [int(res['area_all'][0][0]), fl(res['area_all'][0][1]), float(res['area_all'][0][2]), float(res['area_all'][0][3])])),
            'capital': dict(zip(['buildings', 'quantiles10_25_50_75_90_99', 'mean', 'totalKm2'],
                                [int(res['area_cap'][0][0]), fl(res['area_cap'][0][1]), float(res['area_cap'][0][2]), float(res['area_cap'][0][3])])),
            'binsNational': {k: int(v) for k, v in res.get('bins_all', [])},
            'binsCapital': {k: int(v) for k, v in res.get('bins_cap', [])},
            'medianByClassCapital': {c: {'median': float(md), 'mean': float(mn)} for c, md, mn in res.get('class_area_cap', [])},
        },
        'perimeterMCapital10_50_90': fl(res['perim_cap'][0][0]),
        'heightSource': {k: int(v) for k, v in res.get('h_src', [])},
        'floorsCapital': {k: int(v) for k, v in res.get('floors_cap', [])},
        'floorAreaCapital': {'totalKm2': float(res['floor_area_cap'][0][0]), 'median50_90': fl(res['floor_area_cap'][0][1])},
        'osmMaterial': {k: int(v) for k, v in res.get('material', [])},
        'chiefdoms2016': districts,
        'buildingsOutsideDistricts': int(res['no_district'][0][0]),
        'plusCodeBlocks': {
            'national': dict(zip(['blocks', 'structuresPerBlock50_90_99_999', 'max', 'blocksOver200'],
                                 [int(res['blocks_all'][0][0]), fl(res['blocks_all'][0][1]), int(res['blocks_all'][0][2]), int(res['blocks_all'][0][3])])),
            'capitalUnits': dict(zip(['blocks', 'unitsPerBlock50_90_99_999', 'max', 'blocksOver200'],
                                     [int(res['blocks_cap_units'][0][0]), fl(res['blocks_cap_units'][0][1]), int(res['blocks_cap_units'][0][2]), int(res['blocks_cap_units'][0][3])])),
        },
        'compoundsCapital': {
            'denseThresholdPerHa': DENSE, 'joinM': JOIN_M, 'yardM': YARD_M, 'yardMaxPerHa': YARD_MAX_HA,
            'structuresByDensityPerHa': {k: int(v) for k, v in res.get('cap_density', [])},
            'enclosuresNational': {k: int(v) for k, v in res.get('enc_all', [])},
            'enclosuresWithBuildings': int(res['enc_cap'][0][0]), 'structuresInEnclosures': int(res['enc_cap'][0][1]),
            'structuresPerEnclosure': {k: int(v) for k, v in res.get('enc_sizes', [])},
            'enclosureAreaM2_25_50_75_90': fl(res['enc_area'][0][0]) if res.get('enc_area') and res['enc_area'][0][0] else None,
            'unitsByRule': {k: {'units': int(n), 'structures': int(m)} for k, n, m in res.get('comp_how', [])},
            'structuresPerUnit': {k: int(v) for k, v in res.get('comp_sizes', [])},
            'gatesNational': {k: int(v) for k, v in res.get('gates_all', [])},
            'nwaysCompoundsNational': {k: {'count': int(n), 'km2': float(km)} for k, n, km in res.get('ncomp', [])},
        },
    }
    json.dump(stats, open(a.out, 'w'), ensure_ascii=False, indent=1)
    print(f"wrote {a.out}: {sum(stats['sources'].values()):,} buildings, {len(districts)} chiefdoms")


if __name__ == '__main__':
    main()

"""Gold — OSM spatial joins onto stop features.

SDLC §5.1: eyes-on-street (POIs in 150m), sightline (buildings in 50m forward arc).
Appends to existing gold/stop_features.parquet.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).parent.parent
SILVER = ROOT / "data" / "silver"
GOLD = ROOT / "data" / "gold"
IN_FEATURES = GOLD / "stop_features.parquet"
OUT_FEATURES = GOLD / "stop_features_osm.parquet"

SQL = r"""
CREATE OR REPLACE MACRO hav(lat1, lon1, lat2, lon2) AS
    6371000 * 2 * ASIN(SQRT(
        POWER(SIN((RADIANS(lat2) - RADIANS(lat1)) / 2), 2) +
        COS(RADIANS(lat1)) * COS(RADIANS(lat2)) *
        POWER(SIN((RADIANS(lon2) - RADIANS(lon1)) / 2), 2)
    ));

CREATE OR REPLACE TABLE stops AS SELECT uid, stop_lat, stop_lon
FROM read_parquet('{features}');

-- POI count in 150m
CREATE OR REPLACE TABLE pois AS SELECT lon, lat, amenity, shop, leisure, tourism, name
FROM read_parquet('{silver}/osm_pois.parquet');

CREATE OR REPLACE TABLE stop_pois AS
SELECT s.uid,
       COUNT(p.lat) AS pois_150m,
       COUNT(p.lat) FILTER (p.amenity IN ('restaurant', 'cafe', 'fast_food', 'bar', 'pub', 'nightclub')) AS food_drink_150m,
       COUNT(p.lat) FILTER (p.amenity IN ('bench', 'waste_basket')) AS street_furniture_150m,
       COUNT(p.lat) FILTER (p.shop IS NOT NULL) AS shops_150m,
       COUNT(p.lat) FILTER (p.tourism IS NOT NULL) AS tourism_150m
FROM stops s
LEFT JOIN pois p ON
    p.lat BETWEEN s.stop_lat - 0.002 AND s.stop_lat + 0.002
    AND p.lon BETWEEN s.stop_lon - 0.003 AND s.stop_lon + 0.003
    AND hav(p.lat, p.lon, s.stop_lat, s.stop_lon) <= 150
GROUP BY s.uid;

-- Building footprint area proxy in 50m (count x avg node count ≈ footprint)
CREATE OR REPLACE TABLE bldgs AS SELECT lon, lat, building, num_nodes
FROM read_parquet('{silver}/osm_buildings.parquet');

CREATE OR REPLACE TABLE stop_bldgs AS
SELECT s.uid,
       COUNT(b.lat) AS buildings_50m,
       COALESCE(SUM(b.num_nodes), 0) AS building_nodes_50m
FROM stops s
LEFT JOIN bldgs b ON
    b.lat BETWEEN s.stop_lat - 0.002 AND s.stop_lat + 0.002
    AND b.lon BETWEEN s.stop_lon - 0.003 AND s.stop_lon + 0.003
    AND hav(b.lat, b.lon, s.stop_lat, s.stop_lon) <= 50
GROUP BY s.uid;

-- Lit highway count in 100m
CREATE OR REPLACE TABLE lit AS SELECT mid_lon AS lon, mid_lat AS lat, highway, lit
FROM read_parquet('{silver}/osm_lit_ways.parquet');

CREATE OR REPLACE TABLE stop_lit AS
SELECT s.uid,
       COUNT(l.lat) AS lit_ways_100m,
       COUNT(l.lat) FILTER (l.lit = 'yes') AS lit_yes_100m
FROM stops s
LEFT JOIN lit l ON
    l.lat BETWEEN s.stop_lat - 0.002 AND s.stop_lat + 0.002
    AND l.lon BETWEEN s.stop_lon - 0.003 AND s.stop_lon + 0.003
    AND hav(l.lat, l.lon, s.stop_lat, s.stop_lon) <= 100
GROUP BY s.uid;

-- Full join: original features + OSM features
COPY (
    SELECT f.*,
        COALESCE(p.pois_150m, 0) AS pois_150m,
        COALESCE(p.food_drink_150m, 0) AS food_drink_150m,
        COALESCE(p.street_furniture_150m, 0) AS street_furniture_150m,
        COALESCE(p.shops_150m, 0) AS shops_150m,
        COALESCE(p.tourism_150m, 0) AS tourism_150m,
        COALESCE(b.buildings_50m, 0) AS buildings_50m,
        COALESCE(b.building_nodes_50m, 0) AS building_nodes_50m,
        COALESCE(l.lit_ways_100m, 0) AS lit_ways_100m,
        COALESCE(l.lit_yes_100m, 0) AS lit_yes_100m
    FROM read_parquet('{features}') f
    LEFT JOIN stop_pois p ON f.uid = p.uid
    LEFT JOIN stop_bldgs b ON f.uid = b.uid
    LEFT JOIN stop_lit l ON f.uid = l.uid
) TO '{out}' (FORMAT PARQUET, COMPRESSION SNAPPY);
""".format(features=str(IN_FEATURES), silver=str(SILVER), out=str(OUT_FEATURES))


def main() -> int:
    print("OSM spatial joins (POI 150m + buildings 50m + lit 100m)...")
    con = duckdb.connect()
    con.load_extension("spatial")
    con.execute(SQL)
    con.close()

    df = pd.read_parquet(OUT_FEATURES)
    print(f"\n  -> {OUT_FEATURES} ({OUT_FEATURES.stat().st_size / 1024:.0f} KB)")
    print(f"rows: {len(df):,}  cols: {len(df.columns)}")

    for col in ["pois_150m", "buildings_50m", "lit_ways_100m"]:
        if col in df.columns:
            print(f"  {col}: min={df[col].min():.0f} max={df[col].max():.0f} "
                  f"mean={df[col].mean():.1f} zeros={int((df[col]==0).sum())}")

    # Replace original
    import shutil
    shutil.move(str(OUT_FEATURES), str(IN_FEATURES))
    print(f"\nMoved -> {IN_FEATURES}")

    # Update manifest
    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "file": "stop_features.parquet",
        "rows": len(df),
        "bytes": IN_FEATURES.stat().st_size,
        "columns": list(df.columns),
    }
    (GOLD / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

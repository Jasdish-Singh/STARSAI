"""Gold — spatial buffer joins: per-stop feature counts from silver datasets.

Uses DuckDB spatial extension for fast point-in-polygon joins.
SDLC §4.3: BUFFER_INNER=50m (lighting), BUFFER_MID=200m (eyes/311), BUFFER_OUTER=500m (crime).

Inputs: silver/{crime,poles,service311}.parquet + gold/stops_h3.parquet
Output: gold/stop_features.parquet
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).parent.parent
SILVER = ROOT / "data" / "silver"
BRONZE = ROOT / "data" / "bronze"
GOLD = ROOT / "data" / "gold"
GOLD.mkdir(parents=True, exist_ok=True)

# Output schema
OUT_PATH = GOLD / "stop_features.parquet"

SQL = r"""
-- Haversine MACRO — deduplicates the 3 distance filters below
CREATE OR REPLACE MACRO hav(lat1, lon1, lat2, lon2) AS
    6371000 * 2 * ASIN(SQRT(
        POWER(SIN((RADIANS(lat2) - RADIANS(lat1)) / 2), 2) +
        COS(RADIANS(lat1)) * COS(RADIANS(lat2)) *
        POWER(SIN((RADIANS(lon2) - RADIANS(lon1)) / 2), 2)
    ));

-- Load stops with H3
CREATE OR REPLACE TABLE stops AS SELECT * FROM read_parquet('{gold}/stops_h3.parquet');

-- Lighting poles: count within 50m per stop
CREATE OR REPLACE TABLE poles AS SELECT lat, lon, feature_type, is_streetlight
FROM read_parquet('{silver}/poles.parquet');

CREATE OR REPLACE TABLE stop_lights AS
SELECT s.uid,
       COUNT(p.lat) FILTER (WHERE p.is_streetlight) AS lights_50m,
       COUNT(p.lat) AS poles_total_50m
FROM stops s
LEFT JOIN poles p ON
    p.lat BETWEEN s.stop_lat - 0.002 AND s.stop_lat + 0.002
    AND p.lon BETWEEN s.stop_lon - 0.003 AND s.stop_lon + 0.003
    AND hav(p.lat, p.lon, s.stop_lat, s.stop_lon) <= 50
GROUP BY s.uid;

-- Crime: count night incidents within 500m per stop
-- Day-of-week splits live in labels.parquet (ml_labels.py); not duplicated here.
CREATE OR REPLACE TABLE crime AS SELECT lat, lon, mci_category, occ_hour
FROM read_parquet('{silver}/crime.parquet');

CREATE OR REPLACE TABLE stop_crime AS
SELECT s.uid,
       COUNT(c.lat) AS crime_count_500m,
       COUNT(c.lat) FILTER (c.mci_category = 'Assault') AS crime_assault_500m,
       COUNT(c.lat) FILTER (c.mci_category = 'Robbery') AS crime_robbery_500m
FROM stops s
LEFT JOIN crime c ON
    c.lat BETWEEN s.stop_lat - 0.007 AND s.stop_lat + 0.007
    AND c.lon BETWEEN s.stop_lon - 0.009 AND s.stop_lon + 0.009
    AND hav(c.lat, c.lon, s.stop_lat, s.stop_lon) <= 500
GROUP BY s.uid;

-- 311 disorders: count within 200m per stop (all time — silver already filtered 12mo)
CREATE OR REPLACE TABLE s311 AS SELECT lat, lon, request_type, disorder_category
FROM read_parquet('{silver}/service311.parquet')
WHERE lat IS NOT NULL AND lon IS NOT NULL;

CREATE OR REPLACE TABLE stop_311 AS
SELECT s.uid,
       COUNT(d.lat) AS disorder_count_200m,
       COUNT(d.lat) FILTER (d.disorder_category = 'noise') AS disorder_noise_200m,
       COUNT(d.lat) FILTER (d.disorder_category = 'graffiti') AS disorder_graffiti_200m,
       COUNT(d.lat) FILTER (d.disorder_category = 'drugs') AS disorder_drugs_200m,
       COUNT(d.lat) FILTER (d.disorder_category = 'encampment') AS disorder_encampment_200m,
       COUNT(d.lat) FILTER (d.disorder_category = 'dumping') AS disorder_dumping_200m,
       COUNT(d.lat) FILTER (d.disorder_category = 'litter') AS disorder_litter_200m,
       COUNT(d.lat) FILTER (d.disorder_category = 'vandalism') AS disorder_vandalism_200m
FROM stops s
LEFT JOIN s311 d ON
    d.lat BETWEEN s.stop_lat - 0.003 AND s.stop_lat + 0.003
    AND d.lon BETWEEN s.stop_lon - 0.004 AND s.stop_lon + 0.004
    AND hav(d.lat, d.lon, s.stop_lat, s.stop_lon) <= 200
GROUP BY s.uid;

-- Merge all
CREATE OR REPLACE TABLE features AS
SELECT
    s.*,
    COALESCE(sl.lights_50m, 0) AS lights_50m,
    COALESCE(sl.poles_total_50m, 0) AS poles_total_50m,
    COALESCE(sc.crime_count_500m, 0) AS crime_count_500m,
    COALESCE(sc.crime_assault_500m, 0) AS crime_assault_500m,
    COALESCE(sc.crime_robbery_500m, 0) AS crime_robbery_500m,
    COALESCE(sd.disorder_count_200m, 0) AS disorder_count_200m,
    COALESCE(sd.disorder_noise_200m, 0) AS disorder_noise_200m,
    COALESCE(sd.disorder_graffiti_200m, 0) AS disorder_graffiti_200m,
    COALESCE(sd.disorder_drugs_200m, 0) AS disorder_drugs_200m,
    COALESCE(sd.disorder_encampment_200m, 0) AS disorder_encampment_200m,
    COALESCE(sd.disorder_dumping_200m, 0) AS disorder_dumping_200m,
    COALESCE(sd.disorder_litter_200m, 0) AS disorder_litter_200m,
    COALESCE(sd.disorder_vandalism_200m, 0) AS disorder_vandalism_200m
FROM stops s
LEFT JOIN stop_lights sl ON s.uid = sl.uid
LEFT JOIN stop_crime sc ON s.uid = sc.uid
LEFT JOIN stop_311 sd ON s.uid = sd.uid;

COPY features TO '{out}' (FORMAT PARQUET, COMPRESSION SNAPPY);
""".format(gold=str(GOLD), silver=str(SILVER), out=str(OUT_PATH))


def main() -> int:
    print("Running spatial buffer joins (DuckDB + Haversine)...")
    con = duckdb.connect()
    try:
        con.install_extension("spatial")
    except Exception:
        pass  # may already be installed
    con.load_extension("spatial")

    # Run SQL
    con.execute(SQL)
    con.close()

    # Report
    import pandas as pd
    df = pd.read_parquet(OUT_PATH)
    print(f"\n  -> {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")
    print(f"rows: {len(df):,}")
    print(f"cols: {list(df.columns)}")
    print(f"\nfeature summary:")
    for col in ["lights_50m", "crime_count_500m", "disorder_count_200m"]:
        if col in df.columns:
            print(f"  {col}: min={df[col].min():.0f} max={df[col].max():.0f} "
                  f"mean={df[col].mean():.1f} zeros={int((df[col]==0).sum())}")

    # Manifest
    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "file": "stop_features.parquet",
        "rows": len(df),
        "bytes": OUT_PATH.stat().st_size,
    }
    mpath = GOLD / "manifest.json"
    mpath.write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

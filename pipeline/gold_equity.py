"""Gold stage: spatial-join stops -> Census Tract, append 4 equity columns.

SDLC ref: FR-006 — equity layer.
In:
  data/gold/stop_features.parquet   (existing gold stops with 35+ features)
  data/silver/statcan_ct.parquet    (Toronto CMA CTs + 4 equity fields)
Out:
  data/gold/stop_features.parquet   (overwritten with 4 new cols + ctuid)

New columns: ctuid, pop_density_km2, median_household_income,
             pct_low_income_lim_at, pct_visible_minority
"""
from pathlib import Path
import shutil
import tempfile

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

ROOT = Path(r"C:\Jasdish-IMP\STARSAI")
STOPS = ROOT / "data" / "gold" / "stop_features.parquet"
CT = ROOT / "data" / "silver" / "statcan_ct.parquet"

EQUITY_COLS = ["ctuid", "pop_density_km2", "median_household_income",
               "pct_low_income_lim_at", "pct_visible_minority"]

# 1. Load
stops_df = pd.read_parquet(STOPS)
n0 = len(stops_df)
print(f"stops: {n0:,}  |  existing cols: {len(stops_df.columns)}")

# Drop equity cols if already present (idempotent rerun)
existing = [c for c in EQUITY_COLS if c in stops_df.columns]
if existing:
    stops_df = stops_df.drop(columns=existing)
    print(f"  dropped existing equity cols: {existing}")

ct_df = gpd.read_parquet(CT)
print(f"CT polygons: {len(ct_df):,}")

# 2. Build stops GeoDataFrame (WGS84)
stops_gdf = gpd.GeoDataFrame(
    stops_df,
    geometry=[Point(xy) for xy in zip(stops_df["stop_lon"], stops_df["stop_lat"])],
    crs="EPSG:4326",
)

# 3. Spatial join (within)
joined = gpd.sjoin(stops_gdf, ct_df[["geometry"] + [c for c in EQUITY_COLS]],
                   how="left", predicate="within")
# sjoin keeps duplicate matches at CT borders -> first match wins
joined = joined[~joined["stop_id"].duplicated(keep="first")].copy()
joined = joined.drop(columns=["geometry", "index_right"])

matched = joined["ctuid"].notna().sum()
print(f"stops with CT match: {matched:,} / {n0:,} ({100*matched/n0:.1f}%)")

# 4. Write back (atomic via temp file)
out_df = pd.DataFrame(joined)
assert len(out_df) == n0, f"row count drift: {len(out_df)} != {n0}"

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False, dir=STOPS.parent) as tmp:
    tmp_path = Path(tmp.name)
out_df.to_parquet(tmp_path, compression="snappy", index=False)
shutil.move(str(tmp_path), str(STOPS))

print(f"\nstop_features.parquet -> +{len(EQUITY_COLS)} cols")
print(out_df[EQUITY_COLS].describe().to_string())

"""Silver stage: filter Toronto CMA Census Tracts + extract 4 equity fields.

SDLC ref: FR-006.
Bronze in:
  data/bronze/statcan/profile_ct.csv      (~2.5 GB Canada-wide CT profile)
  data/bronze/statcan/lct_000b21a_e/*.shp (CT cartographic boundaries)
Silver out:
  data/silver/statcan_ct.parquet          (Toronto CMA CTs + geometry + 4 cols)

Fields extracted (CHARACTERISTIC_IDs):
    6    -> pop_density_km2
    243  -> median_household_income
    345  -> pct_low_income_lim_at
    1684 -> visible_minority_count    (numerator)
    1683 -> visible_minority_total    (denominator)
       -> pct_visible_minority = 100 * 1684 / 1683
"""
from pathlib import Path

import duckdb
import geopandas as gpd
import pandas as pd

ROOT = Path(r"C:\Jasdish-IMP\STARSAI")
CSV = ROOT / "data" / "bronze" / "statcan" / "profile_ct.csv"
SHP = ROOT / "data" / "bronze" / "statcan" / "lct_000b21a_e" / "lct_000b21a_e.shp"
OUT = ROOT / "data" / "silver" / "statcan_ct.parquet"

TORONTO_CMA = "535"
WANTED_IDS = {6: "pop_density_km2", 243: "median_household_income",
              345: "pct_low_income_lim_at", 1684: "vm_count", 1683: "vm_total"}

# 1. Pull rows from huge CSV via DuckDB (filtered server-side)
con = duckdb.connect()
ids = ",".join(str(i) for i in WANTED_IDS)
q = f"""
SELECT CAST(ALT_GEO_CODE AS VARCHAR) AS ctuid,
       CHARACTERISTIC_ID AS cid,
       C1_COUNT_TOTAL    AS val
FROM read_csv_auto('{CSV.as_posix()}', encoding='latin-1', sample_size=-1)
WHERE GEO_LEVEL = 'Census tract'
  AND CAST(ALT_GEO_CODE AS VARCHAR) LIKE '{TORONTO_CMA}%'
  AND CHARACTERISTIC_ID IN ({ids})
"""
long_df = con.execute(q).fetchdf()
print(f"long rows (Toronto CMA, 5 IDs): {len(long_df):,}")

# 2. Pivot to wide
wide = long_df.pivot_table(index="ctuid", columns="cid", values="val", aggfunc="first").reset_index()
wide = wide.rename(columns=WANTED_IDS)

# 3. Compute visible minority %
wide["pct_visible_minority"] = (wide["vm_count"] / wide["vm_total"] * 100).round(2)
wide = wide.drop(columns=["vm_count", "vm_total"])

# 4. Normalize ctuid (CSV: "5350001.00", shapefile CTUID: same form)
wide["ctuid"] = wide["ctuid"].astype(str).str.rstrip("0").str.rstrip(".")

print(f"CTs with values: {len(wide):,}")
print(wide.head(3).to_string())

# 5. Load CT boundaries, filter to Toronto bbox, transform to WGS84
gdf = gpd.read_file(SHP)
gdf["ctuid"] = gdf["CTUID"].astype(str).str.rstrip("0").str.rstrip(".")
if gdf.crs is None or gdf.crs.to_epsg() != 4326:
    gdf = gdf.to_crs(epsg=4326)

# Toronto bbox clip (saves disk + later join cost)
TORONTO_BBOX = (-79.70, 43.55, -79.10, 43.90)
gdf = gdf.cx[TORONTO_BBOX[0]:TORONTO_BBOX[2], TORONTO_BBOX[1]:TORONTO_BBOX[3]].copy()
print(f"CT polygons in Toronto bbox: {len(gdf):,}")

# 6. Join values onto geometry
out = gdf[["ctuid", "geometry"]].merge(wide, on="ctuid", how="left")
n_with_income = out["median_household_income"].notna().sum()
print(f"CTs with income value: {n_with_income:,} / {len(out):,}")

# 7. Write parquet (geometry as WKB for parquet compat)
OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_parquet(OUT, compression="snappy", index=False)
print(f"\noutput: {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.1f} KB)")
print(out.describe(include="all").to_string())

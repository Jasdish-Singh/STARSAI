"""Silver stage: dedupe + bbox-filter + streetlight flag for lighting poles.

SDLC ref: docs/SDLC.md §4.2 (clean stage), §5.1 (lighting factor).
Bronze in  -> data/bronze/lighting_poles.parquet
Silver out -> data/silver/poles.parquet
"""
from pathlib import Path
import pandas as pd

ROOT = Path(r"C:\Jasdish-IMP\STARSAI")
BRONZE = ROOT / "data" / "bronze" / "lighting_poles.parquet"
SILVER = ROOT / "data" / "silver" / "poles.parquet"

# 1. read
df = pd.read_parquet(BRONZE)
n0 = len(df)

# 2. dedupe on rounded coords + feature_type (~1m precision)
df["_lat5"] = df["lat"].round(5)
df["_lon5"] = df["lon"].round(5)
df = df.drop_duplicates(subset=["_lat5", "_lon5", "feature_type"]).drop(columns=["_lat5", "_lon5"])
n1 = len(df)

# 3. bbox filter (Toronto)
df = df[(df["lat"].between(43.55, 43.90)) & (df["lon"].between(-79.70, -79.10))].copy()
n2 = len(df)

# 4. streetlight flag
ft = df["feature_type"].astype(str).str.upper()
df["is_streetlight"] = ft.str.contains("LIGHT") | ft.str.contains("LAMP")
n_sl = int(df["is_streetlight"].sum())

# 5. write silver
SILVER.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(SILVER, compression="snappy", index=False)

# 6. report
size_kb = SILVER.stat().st_size / 1024
print(f"rows bronze:        {n0:,}")
print(f"rows after dedupe:  {n1:,}")
print(f"rows after bbox:    {n2:,}")
print(f"streetlight count:  {n_sl:,}")
print(f"output size:        {size_kb:,.1f} KB ({SILVER})")
print("\ntop 10 feature_type:")
print(df["feature_type"].value_counts().head(10).to_string())

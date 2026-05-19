"""Check bronze/silver 311 coordinate status."""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent

for label, path in [
    ("bronze", ROOT / "data/bronze/service311.parquet"),
    ("silver", ROOT / "data/silver/service311.parquet"),
]:
    df = pd.read_parquet(path)
    print(f"=== {label} ===")
    print(f"Rows: {len(df)}, Cols: {df.columns.tolist()}")
    coord_cols = [c for c in df.columns if any(x in c.lower() for x in ['lat','lon','geom','coord','x','y'])]
    print(f"Coord-like cols: {coord_cols}")
    for c in coord_cols:
        nulls = df[c].isna().sum()
        print(f"  {c}: null={nulls}/{len(df)}")
    print(f"Sample: {df.head(2).to_dict('records')}")
    print()

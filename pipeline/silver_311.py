"""Silver stage: clean 311 service requests.

Reads bronze parquet, dedupes, geocodes via postal FSA (pgeocode),
classifies disorder type, writes silver parquet. SDLC ref: docs/SDLC.md §4.2.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import pgeocode

BRONZE = Path(r"C:\Jasdish-IMP\STARSAI\data\bronze\service311.parquet")
SILVER = Path(r"C:\Jasdish-IMP\STARSAI\data\silver\service311.parquet")

# Toronto bbox
LAT_MIN, LAT_MAX = 43.55, 43.90
LON_MIN, LON_MAX = -79.70, -79.10

DISORDER_RULES = [
    ("graffiti",   ["graffiti"]),
    ("encampment", ["encampment", "tent", "homeless"]),
    ("drugs",      ["drug", "needle", "syringe", "narcotic"]),
    ("noise",      ["noise"]),
    ("dumping",    ["dump", "illegal dumping"]),
    ("vandalism",  ["vandal"]),
    ("litter",     ["litter", "garbage", "trash", "waste"]),
]


def classify(rt: str) -> str:
    if not isinstance(rt, str):
        return "other"
    s = rt.lower()
    for cat, kws in DISORDER_RULES:
        if any(k in s for k in kws):
            return cat
    return "other"


def geocode_fsa(df: pd.DataFrame) -> pd.DataFrame:
    """Replace null lat/lon with FSA centroid from pgeocode (Canadian postal data)."""
    nomi = pgeocode.Nominatim("ca")
    unique_fsa = df["postal_fsa"].dropna().unique()
    # pgeocode queries on full postal code; FSA (3 chars) works as prefix
    coords = {}
    for fsa in unique_fsa:
        r = nomi.query_postal_code(fsa)
        if r is not None and not pd.isna(r.latitude) and not pd.isna(r.longitude):
            coords[fsa] = (float(r.latitude), float(r.longitude))
    mapped = 0
    lat_new, lon_new = df["lat"].copy(), df["lon"].copy()
    for fsa, (la, lo) in coords.items():
        mask = df["postal_fsa"] == fsa
        lat_new.loc[mask] = la
        lon_new.loc[mask] = lo
        mapped += int(mask.sum())
    df["lat"] = lat_new
    df["lon"] = lon_new
    print(f"  FSA geocoded: {len(coords)}/{len(unique_fsa)} FSAs, {mapped} rows")
    return df


def main() -> None:
    df = pd.read_parquet(BRONZE)
    n0 = len(df)

    # Dedupe
    key = ["created_date", "request_type", "lat", "lon", "postal_fsa"]
    df = df.drop_duplicates(subset=key, keep="first")
    n_after_dedupe = len(df)

    # Drop NaT created_date
    before_nat = len(df)
    df = df[df["created_date"].notna()].copy()
    dropped_nat = before_nat - len(df)

    # Geocode: fill null lat/lon from postal_fsa
    df = geocode_fsa(df)

    # Geographic sanity — null out lat/lon outside bbox (keep row)
    has_coord = df["lat"].notna() & df["lon"].notna()
    out_bbox = has_coord & ~(
        df["lat"].between(LAT_MIN, LAT_MAX) & df["lon"].between(LON_MIN, LON_MAX)
    )
    dropped_bbox = int(out_bbox.sum())
    df.loc[out_bbox, ["lat", "lon"]] = pd.NA

    # local_date_toronto
    df["local_date_toronto"] = (
        df["created_date"].dt.tz_convert("America/Toronto").dt.date.astype("string")
    )

    # disorder_category
    df["disorder_category"] = df["request_type"].map(classify).astype("string")

    SILVER.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SILVER, compression="snappy", index=False)

    print(f"rows_before:        {n0}")
    print(f"rows_after_dedupe:  {n_after_dedupe}")
    print(f"dropped_nat:        {dropped_nat}")
    print(f"dropped_bbox:       {dropped_bbox}")
    print(f"rows_final:         {len(df)}")
    print("disorder_category value_counts:")
    print(df["disorder_category"].value_counts(dropna=False).to_string())
    print(f"silver_file:        {SILVER}")
    print(f"silver_size_bytes:  {SILVER.stat().st_size}")


if __name__ == "__main__":
    main()

"""STARSAI silver_crime — bronze -> silver clean stage (SDLC Sec 4.2).

Reads data/bronze/crime_night.parquet, dedupes by event_id, drops NaT and
out-of-bbox rows, adds local_hour_toronto + day_type (and h3_r10 if h3 lib
available), writes data/silver/crime.parquet (Snappy).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BRONZE = ROOT / "data" / "bronze" / "crime_night.parquet"
SILVER_DIR = ROOT / "data" / "silver"
SILVER = SILVER_DIR / "crime.parquet"

LAT_MIN, LAT_MAX = 43.55, 43.90
LON_MIN, LON_MAX = -79.70, -79.10
TZ = "America/Toronto"


def day_type_from_dow(dow: int) -> str:
    if dow <= 3:
        return "weekday"
    if dow == 4:
        return "fri"
    if dow == 5:
        return "sat"
    return "sun"


def main() -> int:
    SILVER_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(BRONZE)
    n_before = len(df)

    # Dedupe by event_id (keep first)
    df = df.drop_duplicates(subset=["event_id"], keep="first")
    n_after_dedupe = len(df)
    dropped_dupes = n_before - n_after_dedupe

    # Drop NaT occ_date
    df = df[df["occ_date"].notna()].copy()
    n_after_nat = len(df)
    dropped_nat = n_after_dedupe - n_after_nat

    # Defensive bbox filter
    bbox = (
        df["lat"].between(LAT_MIN, LAT_MAX)
        & df["lon"].between(LON_MIN, LON_MAX)
    )
    df = df[bbox].copy()
    n_after_bbox = len(df)
    dropped_bbox = n_after_nat - n_after_bbox

    # Ensure UTC tz-aware then convert to America/Toronto
    occ = df["occ_date"]
    if occ.dt.tz is None:
        occ = occ.dt.tz_localize("UTC")
    local = occ.dt.tz_convert(TZ)
    df["local_hour_toronto"] = local.dt.hour.astype("int16")

    # day_type from local dayofweek
    df["day_type"] = local.dt.dayofweek.map(day_type_from_dow).astype("category")

    # h3 optional
    h3_added = False
    try:
        import h3  # type: ignore

        # h3 v4 uses latlng_to_cell; v3 uses geo_to_h3
        if hasattr(h3, "latlng_to_cell"):
            df["h3_r10"] = [
                h3.latlng_to_cell(lat, lon, 10)
                for lat, lon in zip(df["lat"].to_numpy(), df["lon"].to_numpy())
            ]
        else:
            df["h3_r10"] = [
                h3.geo_to_h3(lat, lon, 10)
                for lat, lon in zip(df["lat"].to_numpy(), df["lon"].to_numpy())
            ]
        h3_added = True
    except Exception as e:
        print(f"h3 lib unavailable, skipping h3_r10 column ({type(e).__name__}: {e})")

    df.to_parquet(SILVER, compression="snappy", index=False)

    total_dropped = dropped_dupes + dropped_nat + dropped_bbox
    print(f"rows_before:      {n_before}")
    print(f"rows_after_dedupe:{n_after_dedupe} (dropped_dupes={dropped_dupes})")
    print(f"rows_after_nat:   {n_after_nat} (dropped_nat={dropped_nat})")
    print(f"rows_after_bbox:  {n_after_bbox} (dropped_bbox={dropped_bbox})")
    print(f"rows_final:       {len(df)}")
    print(f"total_dropped:    {total_dropped}")
    print(f"h3_r10_added:     {h3_added}")
    print("schema:")
    print(df.dtypes.to_string())
    size = SILVER.stat().st_size
    print(f"file: {SILVER}")
    print(f"file_size_bytes: {size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

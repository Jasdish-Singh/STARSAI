"""Gold — H3 r9 grid + stop assignment + k-ring neighbours.

SDLC §4.3: H3 resolution 9 (~150m edge). k-ring 1 = ~200m radius (eyes/co-presence).
k-ring 3 = ~500m radius (crime density).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import h3

ROOT = Path(__file__).parent.parent
SILVER = ROOT / "data" / "silver"
BRONZE = ROOT / "data" / "bronze"
GOLD = ROOT / "data" / "gold"
GOLD.mkdir(parents=True, exist_ok=True)

H3_RES = 9

# Toronto bbox
MIN_LAT, MAX_LAT = 43.55, 43.90
MIN_LON, MAX_LON = -79.70, -79.10


def main() -> int:
    # 1. Load stops
    stops = pd.read_parquet(BRONZE / "stops.parquet")
    print(f"stops loaded: {len(stops):,}")

    keep = ["uid", "stop_id", "stop_name", "stop_lat", "stop_lon",
            "system", "location_type", "parent_station"]
    stops = stops[[c for c in keep if c in stops.columns]].copy()

    # 2. Compute H3 cell for each stop
    stops["h3_r9"] = stops.apply(
        lambda r: h3.latlng_to_cell(r.stop_lat, r.stop_lon, H3_RES), axis=1)
    print(f"unique H3 cells: {stops['h3_r9'].nunique():,}")

    # 3. k-ring 1 (neighbours at ~200m)
    def ring_k1(cell: str) -> str:
        return "|".join(sorted(h3.grid_disk(cell, 1)))

    def ring_k3(cell: str) -> str:
        return "|".join(sorted(h3.grid_disk(cell, 3)))

    stops["h3_ring_k1"] = stops["h3_r9"].apply(ring_k1)
    stops["h3_ring_k3"] = stops["h3_r9"].apply(ring_k3)

    # 4. Write
    out_path = GOLD / "stops_h3.parquet"
    stops.to_parquet(out_path, index=False, engine="pyarrow")
    sz_kb = out_path.stat().st_size / 1024

    print(f"\n  -> {out_path} ({sz_kb:.0f} KB)")
    print(f"rows: {len(stops):,}")
    print(f"cols: {list(stops.columns)}")
    print(f"sample H3 cells: {stops['h3_r9'].head(3).tolist()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

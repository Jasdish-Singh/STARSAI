"""Pack — Scores to GeoJSON + summary CSV for frontend consumption.

SDLC §4.2 pack stage. One GeoJSON FeatureCollection, one summary CSV.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
SCORES = ROOT / "data" / "scores"
PUBLIC = ROOT / "data" / "public"
PUBLIC.mkdir(parents=True, exist_ok=True)


def main() -> int:
    df = pd.read_parquet(SCORES / "scores.parquet")
    print(f"Loaded {len(df):,} stops")

    # GeoJSON FeatureCollection
    features = []
    for _, r in df.iterrows():
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(r["stop_lon"]), float(r["stop_lat"])],
            },
            "properties": {
                "stop_id": r["stop_id"],
                "stop_name": r["stop_name"],
                "system": r["system"],
                "t_ntsi_score": r["t_ntsi_score"],
                "rank": int(r["rank"]),
                "quartile": str(r["quartile"]),
                "f_lighting": r["f_lighting"],
                "f_crime": r["f_crime"],
                "f_eyes_on_street": r["f_eyes_on_street"],
                "f_isolation": r["f_isolation"],
                "f_wait_exposure": r["f_wait_exposure"],
                "f_sightline": r["f_sightline"],
                "f_disorder_311": r["f_disorder_311"],
                "f_lit_way_supplement": r["f_lit_way_supplement"],
            },
        })

    geojson = {"type": "FeatureCollection", "features": features}
    gj_path = PUBLIC / "stops_scores.geojson"
    gj_path.write_text(json.dumps(geojson, indent=None), encoding="utf-8")
    print(f"  -> {gj_path} ({gj_path.stat().st_size / 1024:.0f} KB)")

    # Summary CSV (flat, no geometry nesting)
    csv_path = PUBLIC / "stops_scores.csv"
    df.to_csv(csv_path, index=False)
    print(f"  -> {csv_path} ({csv_path.stat().st_size / 1024:.0f} KB)")

    # Manifest
    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "files": {
            "stops_scores.geojson": {"rows": len(df), "bytes": gj_path.stat().st_size},
            "stops_scores.csv": {"rows": len(df), "bytes": csv_path.stat().st_size},
        },
    }
    (PUBLIC / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

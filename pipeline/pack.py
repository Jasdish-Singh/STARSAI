"""Pack — Scores to compact JSON + GeoJSON + summary CSV.

SDLC §4.2 pack + FR-031 static API. Outputs:
  scores.json      — compact static API (FR-031), browser-fetched
  stops_scores.geojson — map rendering layer
  stops_scores.csv     — analyst download
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
SCORES = ROOT / "data" / "scores"
PUBLIC = ROOT / "data" / "public"
CFG = ROOT / "config"
PUBLIC.mkdir(parents=True, exist_ok=True)


FACTOR_COLS = [
    "f_lighting", "f_crime", "f_eyes_on_street", "f_isolation",
    "f_wait_exposure", "f_sightline", "f_disorder_311", "f_lit_way_supplement",
]


def _git_short_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _model_meta() -> dict:
    p = CFG / "calibrated_weights.json"
    if not p.exists():
        return {"version": "theory", "method": "theory_weights", "auroc": None}
    d = json.loads(p.read_text())
    return {
        "version": d.get("model_version", "unknown"),
        "method": d.get("method", "unknown"),
        "auroc": d.get("auroc"),
    }


def main() -> int:
    df = pd.read_parquet(SCORES / "scores.parquet")
    print(f"Loaded {len(df):,} stops")

    commit = _git_short_sha()
    model = _model_meta()
    generated_at = pd.Timestamp.now("UTC").isoformat(timespec="seconds")

    # scores.json — compact static API (FR-031). One JSON, all browser needs.
    factor_cols_present = [c for c in FACTOR_COLS if c in df.columns]
    stops = []
    for _, r in df.iterrows():
        entry = {
            "uid": str(r["uid"]) if "uid" in df.columns else str(r["stop_id"]),
            "id": str(r["stop_id"]),
            "name": str(r["stop_name"]),
            "sys": str(r["system"]),
            "lat": round(float(r["stop_lat"]), 6),
            "lon": round(float(r["stop_lon"]), 6),
            "score": float(r["t_ntsi_score"]),
            "rank": int(r["rank"]),
            "q": str(r["quartile"]),
            "f": {c[2:]: float(r[c]) for c in factor_cols_present},
        }
        stops.append(entry)

    scores_json = {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "commit": commit,
        "model": model,
        "n_stops": len(stops),
        "stops": stops,
    }
    sj_path = PUBLIC / "scores.json"
    sj_path.write_text(json.dumps(scores_json, separators=(",", ":")), encoding="utf-8")
    print(f"  -> {sj_path} ({sj_path.stat().st_size / 1024:.0f} KB)")

    # GeoJSON FeatureCollection — for Deck.gl/Mapbox layer
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
                **{c: r[c] for c in factor_cols_present},
            },
        })

    geojson = {"type": "FeatureCollection", "features": features}
    gj_path = PUBLIC / "stops_scores.geojson"
    gj_path.write_text(json.dumps(geojson, separators=(",", ":")), encoding="utf-8")
    print(f"  -> {gj_path} ({gj_path.stat().st_size / 1024:.0f} KB)")

    # Summary CSV (flat, analyst download)
    csv_path = PUBLIC / "stops_scores.csv"
    df.to_csv(csv_path, index=False)
    print(f"  -> {csv_path} ({csv_path.stat().st_size / 1024:.0f} KB)")

    # Manifest
    manifest = {
        "generated_at": generated_at,
        "commit": commit,
        "model": model,
        "files": {
            "scores.json": {"rows": len(stops), "bytes": sj_path.stat().st_size,
                            "role": "FR-031 static API"},
            "stops_scores.geojson": {"rows": len(df), "bytes": gj_path.stat().st_size,
                                     "role": "map layer"},
            "stops_scores.csv": {"rows": len(df), "bytes": csv_path.stat().st_size,
                                 "role": "analyst download"},
            "provenance.json": {"role": "FR-019 per-stop provenance",
                                "exists": (PUBLIC / "provenance.json").exists()},
        },
    }
    (PUBLIC / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

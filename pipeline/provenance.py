"""Provenance — per-stop factor inputs, factor scores, composite, weights, commit.

SDLC FR-019. Output: data/public/provenance.json (single dict keyed by uid).
Cheap by design: cites source datasets + record counts, not per-row IDs (bloat).

Schema per uid:
  raw: feature inputs from gold/stop_features.parquet
  factors: f_lighting, f_crime, ... 0-100 (100=safest)
  composite: t_ntsi_score
  weights: {factor: weight_used}
  model: {version, method, auroc} from calibrated_weights.json
  commit: short git SHA (pipeline reproducibility)
  generated_at: ISO timestamp
  sources: {dataset_id: open-data URL, record_count}
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"
SCORES = ROOT / "data" / "scores"
PUBLIC = ROOT / "data" / "public"
CFG = ROOT / "config"

RAW_FEATURE_COLS = [
    "lights_50m", "poles_total_50m",
    "crime_count_500m", "crime_assault_500m", "crime_robbery_500m",
    "disorder_count_200m",
    "pois_150m", "food_drink_150m", "buildings_50m",
    "building_nodes_50m", "lit_yes_100m",
]

FACTOR_COLS = [
    "f_lighting", "f_crime", "f_eyes_on_street", "f_isolation",
    "f_wait_exposure", "f_sightline", "f_disorder_311", "f_lit_way_supplement",
]

SOURCES = {
    "ttc_gtfs":   "https://open.toronto.ca/dataset/ttc-routes-and-schedules/",
    "mci":        "https://data.torontopolice.on.ca/datasets/major-crime-indicators-open-data",
    "poles":      "https://open.toronto.ca/dataset/street-furniture-poles/",
    "service311": "https://open.toronto.ca/dataset/311-service-requests-customer-initiated/",
    "osm":        "https://www.openstreetmap.org/copyright",
    "statcan_ct": "https://www12.statcan.gc.ca/census-recensement/2021/",
}


def _git_short_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def _load_model_meta() -> dict:
    p = CFG / "calibrated_weights.json"
    if not p.exists():
        return {"version": "theory", "method": "theory_weights", "auroc": None}
    d = json.loads(p.read_text())
    return {
        "version": d.get("model_version", "unknown"),
        "method": d.get("method", "unknown"),
        "auroc": d.get("auroc"),
    }


def _record_counts() -> dict:
    silver = ROOT / "data" / "silver"
    out = {}
    for ds, fname in [
        ("mci", "crime.parquet"),
        ("poles", "poles.parquet"),
        ("service311", "service311.parquet"),
        ("osm_pois", "osm_pois.parquet"),
        ("osm_buildings", "osm_buildings.parquet"),
        ("osm_lit_ways", "osm_lit_ways.parquet"),
    ]:
        fp = silver / fname
        if fp.exists():
            try:
                out[ds] = int(pd.read_parquet(fp, columns=[]).shape[0])
            except Exception:
                out[ds] = None
    return out


def main() -> int:
    feats_path = GOLD / "stop_features.parquet"
    scores_path = SCORES / "scores.parquet"
    if not feats_path.exists() or not scores_path.exists():
        print(f"ERROR: missing inputs ({feats_path} or {scores_path})", file=sys.stderr)
        return 1

    feats = pd.read_parquet(feats_path)
    scores = pd.read_parquet(scores_path)

    feats["uid"] = feats["uid"].astype(str)
    scores["uid"] = scores["uid"].astype(str)

    raw_cols = [c for c in RAW_FEATURE_COLS if c in feats.columns]
    factor_cols = [c for c in FACTOR_COLS if c in scores.columns]

    raw_df = feats[["uid"] + raw_cols].set_index("uid")
    score_df = scores[["uid", "stop_id", "stop_name", "t_ntsi_score"] + factor_cols].set_index("uid")

    model = _load_model_meta()
    cal = json.loads((CFG / "calibrated_weights.json").read_text()) \
        if (CFG / "calibrated_weights.json").exists() else {}
    weights = cal.get("weights_blended") or cal.get("weights") or {}

    commit = _git_short_sha()
    record_counts = _record_counts()
    generated_at = pd.Timestamp.now("UTC").isoformat(timespec="seconds")

    out = {}
    for uid in score_df.index:
        raw = raw_df.loc[uid].to_dict() if uid in raw_df.index else {}
        scr = score_df.loc[uid]
        out[uid] = {
            "stop_id": str(scr["stop_id"]),
            "stop_name": str(scr["stop_name"]),
            "composite": float(scr["t_ntsi_score"]),
            "factors": {c[2:]: float(scr[c]) for c in factor_cols},
            "raw": {k: (None if pd.isna(v) else (int(v) if float(v).is_integer() else float(v)))
                    for k, v in raw.items()},
        }

    payload = {
        "schema_version": "1.0",
        "generated_at": generated_at,
        "commit": commit,
        "model": model,
        "weights": weights,
        "sources": {ds: {"url": url, "records": record_counts.get(ds)}
                    for ds, url in SOURCES.items()},
        "stops": out,
    }

    PUBLIC.mkdir(parents=True, exist_ok=True)
    outp = PUBLIC / "provenance.json"
    outp.write_text(json.dumps(payload, separators=(",", ":")))

    size_kb = outp.stat().st_size / 1024
    print(f"  -> {outp} ({size_kb:,.0f} KB, {len(out):,} stops)")
    print(f"commit={commit}  model={model['version']}  auroc={model.get('auroc')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

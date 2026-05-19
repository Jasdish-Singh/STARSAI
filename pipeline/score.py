"""Score — Compute 8 factors + composite T-NTSI score per stop.

SDLC §5.1 factor catalogue. Each factor 0-100 where 100 = safest.
Missing: alcohol_outlets (AGCO not sourced), streetscape_vision (Mapillary P2),
crossing_danger (KSI not sourced).

Weights from SDLC theory weights (remaining 20% redistributed pro-rata
since no survey or logistic regression yet).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
BRONZE = ROOT / "data" / "bronze"
GOLD = ROOT / "data" / "gold"
SCORES = ROOT / "data" / "scores"
SCORES.mkdir(parents=True, exist_ok=True)

# Load calibrated weights from ML stage (SDLC §5.2 blended: 40/40/20)
# Falls back to theory weights if calibrated not found
CALIBRATED_PATH = ROOT / "config" / "calibrated_weights.json"
if CALIBRATED_PATH.exists():
    import json as _json
    _cal = _json.loads(CALIBRATED_PATH.read_text())
    WEIGHTS = _cal["weights_blended"]
    print(f"Using calibrated weights (AUROC={_cal['auroc']:.3f})")
else:
    WEIGHTS = {
        "lighting":          0.18,
        "crime":             0.25,
        "eyes_on_street":    0.15,
        "isolation":         0.10,
        "wait_exposure":     0.12,
        "sightline":         0.05,
        "disorder_311":      0.10,
        "lit_way_supplement": 0.05,
    }
    print("Using theory weights (calibrated_weights.json not found)")

# Percentile caps for log/power transforms
CAPS = {
    "lights_50m": 50,
    "crime_count_500m": 200,
    "pois_150m": 50,
    "food_drink_150m": 30,
    "buildings_50m": 20,
    "building_nodes_50m": 100,
    "disorder_count_200m": 10,
    "lit_yes_100m": 20,
}


def _norm(x: pd.Series, invert: bool = False) -> pd.Series:
    """Min-max scale to [0,1], optionally invert so high=good."""
    mn, mx = x.min(), x.max()
    if mx == mn:
        return pd.Series(0.5, index=x.index)
    r = (x - mn) / (mx - mn)
    if invert:
        r = 1 - r
    return r.clip(0, 1)


def factor_lighting(df: pd.DataFrame) -> pd.Series:
    raw = df["lights_50m"].clip(upper=CAPS["lights_50m"])
    return _norm(np.log1p(raw), invert=False) * 100


def factor_crime(df: pd.DataFrame) -> pd.Series:
    raw = df["crime_count_500m"].clip(upper=CAPS["crime_count_500m"])
    return _norm(np.log1p(raw), invert=True) * 100


def factor_eyes_on_street(df: pd.DataFrame) -> pd.Series:
    pois = df["pois_150m"].clip(upper=CAPS["pois_150m"])
    food = df["food_drink_150m"].clip(upper=CAPS["food_drink_150m"])
    combined = np.log1p(pois) * 0.5 + np.log1p(food) * 0.5
    return _norm(combined, invert=False) * 100


def factor_isolation(df: pd.DataFrame) -> pd.Series:
    raw = df["pois_150m"] + df["buildings_50m"]
    return _norm(np.log1p(raw), invert=True) * 100


def factor_wait_exposure(df: pd.DataFrame) -> pd.Series:
    # No per-stop headway data yet — use isolation as proxy
    # Higher isolation → longer effective wait
    raw = df["pois_150m"] + df["buildings_50m"]
    isolation = _norm(np.log1p(raw), invert=True)  # 1 = isolated
    return isolation * 100


def factor_sightline(df: pd.DataFrame) -> pd.Series:
    nodes = df["building_nodes_50m"].clip(upper=CAPS["building_nodes_50m"])
    count = df["buildings_50m"].clip(upper=CAPS["buildings_50m"])
    occlusion_proxy = nodes * count  # more buildings × more nodes = more occlusion
    return _norm(np.log1p(occlusion_proxy), invert=True) * 100


def factor_disorder(df: pd.DataFrame) -> pd.Series:
    raw = df["disorder_count_200m"].clip(upper=CAPS["disorder_count_200m"])
    return _norm(np.log1p(raw), invert=True) * 100


def factor_lit_supplement(df: pd.DataFrame) -> pd.Series:
    raw = df["lit_yes_100m"].clip(upper=CAPS["lit_yes_100m"])
    return _norm(np.log1p(raw), invert=False) * 100


def compute_composite(df: pd.DataFrame, factors: dict) -> pd.Series:
    composite = pd.Series(0.0, index=df.index)
    for name, w in WEIGHTS.items():
        if name in factors:
            composite += w * factors[name]
    composite = composite.clip(0, 100)
    return composite


def main() -> int:
    print("Loading features...")
    df = pd.read_parquet(GOLD / "stop_features.parquet")
    print(f"  stops: {len(df):,}")

    factors = {}
    print("\nComputing factors (0-100, 100=safest)...")

    factors["lighting"] = factor_lighting(df)
    print(f"  lighting:          mean={factors['lighting'].mean():.1f}")

    factors["crime"] = factor_crime(df)
    print(f"  crime:             mean={factors['crime'].mean():.1f}")

    factors["eyes_on_street"] = factor_eyes_on_street(df)
    print(f"  eyes_on_street:    mean={factors['eyes_on_street'].mean():.1f}")

    factors["isolation"] = factor_isolation(df)
    print(f"  isolation:         mean={factors['isolation'].mean():.1f}")

    factors["wait_exposure"] = factor_wait_exposure(df)
    print(f"  wait_exposure:     mean={factors['wait_exposure'].mean():.1f}")

    factors["sightline"] = factor_sightline(df)
    print(f"  sightline:         mean={factors['sightline'].mean():.1f}")

    factors["disorder_311"] = factor_disorder(df)
    print(f"  disorder_311:      mean={factors['disorder_311'].mean():.1f}")

    factors["lit_way_supplement"] = factor_lit_supplement(df)
    print(f"  lit_way_supplement: mean={factors['lit_way_supplement'].mean():.1f}")

    composite = compute_composite(df, factors)
    print(f"\n  COMPOSITE T-NTSI:  mean={composite.mean():.1f} "
          f"min={composite.min():.0f} max={composite.max():.0f}")

    # Build scores dataframe
    out = df[["uid", "stop_id", "stop_name", "stop_lat", "stop_lon", "system"]].copy()
    for name, vals in factors.items():
        out[f"f_{name}"] = vals.round(1)
    out["t_ntsi_score"] = composite.round(1)

    # Rank
    out["rank"] = out["t_ntsi_score"].rank(ascending=False).astype(int)
    out["quartile"] = pd.qcut(out["t_ntsi_score"], 4, labels=["Q4", "Q3", "Q2", "Q1"])

    # Sort worst first
    out = out.sort_values("t_ntsi_score").reset_index(drop=True)

    score_path = SCORES / "scores.parquet"
    out.to_parquet(score_path, index=False, engine="pyarrow")
    print(f"\n  -> {score_path} ({score_path.stat().st_size / 1024:.0f} KB)")

    # Top 10 worst / best
    print("\n=== WORST 5 stops ===")
    for _, r in out.head(5).iterrows():
        print(f"  {r['t_ntsi_score']:5.1f}  {r['stop_name'][:45]}  ({r['system']})")

    print("\n=== BEST 5 stops ===")
    for _, r in out.tail(5).iterrows():
        print(f"  {r['t_ntsi_score']:5.1f}  {r['stop_name'][:45]}  ({r['system']})")

    # Validation: check 14 known-bad stops
    print("\n=== VALIDATION STOPS (from config) ===")
    from config import VALIDATION_STOPS

    matched = 0
    for vs in VALIDATION_STOPS:
        hits = out[out["stop_name"].str.contains(vs["name"][:15], case=False, na=False)]
        if len(hits) > 0:
            row = hits.iloc[0]
            q = row["quartile"]
            status = "OK (bottom quartile)" if q == "Q1" else "WARN"
            print(f"  {row['t_ntsi_score']:5.1f}  Q={q}  {status}  {vs['name'][:50]}")
            matched += 1
        else:
            print(f"  ---    --  NOT FOUND  {vs['name'][:50]}")
    print(f"\n  Matched: {matched}/{len(VALIDATION_STOPS)}")

    # Manifest
    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "file": "scores.parquet",
        "rows": len(out),
        "bytes": score_path.stat().st_size,
        "weights": WEIGHTS,
        "composite_stats": {
            "mean": float(composite.mean()),
            "min": float(composite.min()),
            "max": float(composite.max()),
        },
        "factors_available": list(WEIGHTS.keys()),
        "factors_missing": ["alcohol_outlets", "streetscape_vision", "crossing_danger"],
    }
    (SCORES / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nManifest: {SCORES / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

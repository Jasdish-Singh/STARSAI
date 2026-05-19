"""ML train — Logistic regression weight calibration (SDLC §5.2).

- Per-bin labels (64 bins = 16 hours × 4 day_types)
- Features: 8 static factor values + hour + day_type (categorical)
- 80/20 grid-based split (H3 cell, not random)
- Output: config/calibrated_weights.yaml
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).parent.parent
GOLD = ROOT / "data" / "gold"
CONFIG = ROOT / "config"
CONFIG.mkdir(parents=True, exist_ok=True)

# SDLC §5.2 theory weights (normalised, 8 of 10 factors)
THEORY = {
    "lighting": 0.18, "crime": 0.25, "eyes_on_street": 0.15,
    "isolation": 0.10, "wait_exposure": 0.12, "sightline": 0.05,
    "disorder_311": 0.10, "lit_way_supplement": 0.05,
}

# Factor computation (same as score.py, for feature matrix)
CAPS = {
    "lights_50m": 50, "crime_count_500m": 200, "pois_150m": 50,
    "food_drink_150m": 30, "buildings_50m": 20, "building_nodes_50m": 100,
    "disorder_count_200m": 10, "lit_yes_100m": 20,
}


def _norm(x: pd.Series, invert: bool = False) -> pd.Series:
    mn, mx = x.min(), x.max()
    if mx == mn:
        return pd.Series(0.5, index=x.index)
    r = (x - mn) / (mx - mn)
    return (1 - r if invert else r).clip(0, 1)


def compute_factors(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["lighting"] = _norm(np.log1p(df["lights_50m"].clip(upper=CAPS["lights_50m"])), invert=False)
    out["crime"] = _norm(np.log1p(df["crime_count_500m"].clip(upper=CAPS["crime_count_500m"])), invert=True)
    pois = np.log1p(df["pois_150m"].clip(upper=CAPS["pois_150m"]))
    food = np.log1p(df["food_drink_150m"].clip(upper=CAPS["food_drink_150m"]))
    out["eyes_on_street"] = _norm(pd.Series(pois * 0.5 + food * 0.5, index=df.index), invert=False)
    raw = df["pois_150m"] + df["buildings_50m"]
    out["isolation"] = _norm(np.log1p(raw), invert=True)
    out["wait_exposure"] = _norm(np.log1p(raw), invert=True)  # proxy
    nodes = df["building_nodes_50m"].clip(upper=CAPS["building_nodes_50m"])
    count = df["buildings_50m"].clip(upper=CAPS["buildings_50m"])
    out["sightline"] = _norm(np.log1p(nodes * count), invert=True)
    out["disorder_311"] = _norm(np.log1p(df["disorder_count_200m"].clip(upper=CAPS["disorder_count_200m"])), invert=True)
    out["lit_way_supplement"] = _norm(np.log1p(df["lit_yes_100m"].clip(upper=CAPS["lit_yes_100m"])), invert=False)
    return out.clip(0, 1)


def main() -> int:
    print("Loading data...")
    labels = pd.read_parquet(GOLD / "labels.parquet")
    features = pd.read_parquet(GOLD / "stop_features.parquet")
    print(f"  Labels: {len(labels):,} rows, {labels['label'].mean()*100:.1f}% positive")

    # Compute factors from raw features (0-1 scale for LR)
    print("Computing factors...")
    factor_df = compute_factors(features)

    # Join labels → factor values + hour + day_type
    factor_df = factor_df.set_index(features["uid"])
    df = labels.merge(features[["uid", "h3_r9"]], on="uid", how="left")  # H3 for split
    for col in factor_df.columns:
        df[col] = df["uid"].map(factor_df[col])

    # One-hot encode day_type
    df = pd.get_dummies(df, columns=["day_type"], prefix="dt", drop_first=False)

    # Feature columns
    factor_cols = list(factor_df.columns)
    temporal_cols = ["hour"] + [c for c in df.columns if c.startswith("dt_")]
    feature_cols = factor_cols + temporal_cols

    X = df[feature_cols].copy()
    y = df["label"].values

    # 80/20 grid-based split by H3 cell
    h3_cells = list(df["h3_r9"].unique())
    np.random.seed(42)
    np.random.shuffle(h3_cells)
    n_train = int(len(h3_cells) * 0.8)
    train_cells = set(h3_cells[:n_train])
    train_mask = df["h3_r9"].isin(train_cells)
    test_mask = ~train_mask

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    print(f"  Train: {len(X_train):,}  Test: {len(X_test):,}")

    # Standardize (not hour/day_type dummies, but safe for all)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    # Train
    print("Training logistic regression...")
    lr = LogisticRegression(max_iter=2000, C=0.1, class_weight="balanced", random_state=42)
    lr.fit(X_train_s, y_train)

    # Evaluate
    y_prob = lr.predict_proba(X_test_s)[:, 1]
    y_pred = lr.predict(X_test_s)
    auc = roc_auc_score(y_test, y_prob)
    print(f"\n  AUROC: {auc:.4f}  (target >= 0.70)")

    # Factor coefficients (exclude temporal controls)
    coef_idx = {c: i for i, c in enumerate(feature_cols)}
    print("\n=== FACTOR COEFFICIENTS ===")
    fcoef = {}
    for c in factor_cols:
        idx = coef_idx[c]
        coef = lr.coef_[0][idx]
        fcoef[c] = float(coef)
        direction = "OK" if coef > 0 else "WRONG SIGN"
        flag = direction if c in ('eyes_on_street',) else ""
        print(f"  {c:20s}: {coef:+.4f}  {flag}")

    # Temporal coefficients
    print("\n=== TEMPORAL COEFFICIENTS ===")
    for c in temporal_cols:
        idx = coef_idx[c]
        print(f"  {c:20s}: {lr.coef_[0][idx]:+.4f}")

    # Normalize factor coefficients to weights (softmax)
    coef_arr = np.array([fcoef[c] for c in factor_cols])
    # Shift to positive via exp, then normalize
    w_data = np.exp(coef_arr) / np.exp(coef_arr).sum()

    print("\n=== CALIBRATED WEIGHTS ===")
    data_weights = {}
    for c, w in zip(factor_cols, w_data):
        data_weights[c] = float(round(w, 4))
        print(f"  {c:20s}: data={w:.4f}  theory={THEORY[c]:.4f}")

    # Blend per SDLC §5.2: 40% theory + 40% data + 20% uniform
    uniform_w = 1.0 / len(factor_cols)
    blended = {}
    for c in factor_cols:
        blended[c] = float(round(0.4 * THEORY[c] + 0.4 * data_weights[c] + 0.2 * uniform_w, 4))

    total = sum(blended.values())
    blended = {k: float(round(v / total, 4)) for k, v in blended.items()}

    print("\n=== FINAL BLENDED WEIGHTS (40/40/20) ===")
    for c, w in blended.items():
        print(f"  {c:20s}: {w:.4f}")

    # Write config
    output = {
        "model_version": "v0.3.1",
        "method": "logistic_regression",
        "blend": "0.4_theory + 0.4_data + 0.2_uniform",
        "auroc": float(round(auc, 4)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "positive_rate": float(df["label"].mean()),
        "factor_coefficients_raw": {c: float(round(v, 4)) for c, v in fcoef.items()},
        "weights_theory": THEORY,
        "weights_data": data_weights,
        "weights_blended": blended,
    }

    weight_path = CONFIG / "calibrated_weights.json"
    weight_path.write_text(json.dumps(output, indent=2))
    print(f"\n  -> {weight_path}")

    # Also write YAML format for score.py
    yaml_path = CONFIG / "calibrated_weights.yaml"
    lines = ["# STARSAI calibrated weights — auto-generated by ml_train.py",
             f"# AUROC: {auc:.4f}  Blend: 40% theory + 40% data + 20% uniform",
             f"# Model version: v0.3.1",
             "weights:"]
    for c, w in blended.items():
        lines.append(f"  {c}: {w}")
    yaml_path.write_text("\n".join(lines) + "\n")
    print(f"  -> {yaml_path}")

    # Sign check for eyes_on_street
    if fcoef["eyes_on_street"] < 0:
        print("\n*** WARNING: eyes_on_street coefficient is NEGATIVE. "
              "Data contradicts CPTED theory. Keeping data-driven sign; "
              "document as finding for methodology report. ***")

    return 0


if __name__ == "__main__":
    sys.exit(main())

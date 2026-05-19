"""Compute per-bin T-NTSI scores (16h x 4 day_types = 64 bins).

Crime + lighting both vary per bin:
 - f_crime uses GLOBAL log-min/max so absolute bin magnitude is preserved
   (within-bin normalization wipes day/night variance — see review B1).
 - lighting weight gets shifted up at night via darkness factor (D2),
   penalizing low-lit stops harder after dusk without retraining.

Output: data/scores/scores_dynamic.parquet (uid, hour, day_type, t_ntsi_score, f_crime)
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "data" / "gold"
SCORES_DIR = ROOT / "data" / "scores"
OUT = SCORES_DIR / "scores_dynamic.parquet"

CAPS = {
    "crime_count_500m": 200, "lights_50m": 50, "pois_150m": 50,
    "food_drink_150m": 30, "buildings_50m": 20,
    "building_nodes_50m": 100, "disorder_count_200m": 10, "lit_yes_100m": 20,
}

CALIBRATED_PATH = ROOT / "config" / "calibrated_weights.json"
if CALIBRATED_PATH.exists():
    WEIGHTS = json.loads(CALIBRATED_PATH.read_text())["weights_blended"]
else:
    WEIGHTS = {
        "lighting": 0.18, "crime": 0.25, "eyes_on_street": 0.15,
        "isolation": 0.10, "wait_exposure": 0.12, "sightline": 0.05,
        "disorder_311": 0.10, "lit_way_supplement": 0.05,
    }


def _norm(x: pd.Series, invert: bool = False) -> pd.Series:
    mn, mx = x.min(), x.max()
    if mx == mn:
        return pd.Series(0.5, index=x.index)
    r = (x - mn) / (mx - mn)
    return (1 - r if invert else r).clip(0, 1)


def _darkness(hour: int) -> float:
    """Return 1.0 for deep night (20-06), 0.2 for daytime."""
    return 1.0 if (hour >= 20 or hour <= 6) else 0.2


def _night_weights(base: dict, hour: int) -> dict:
    """Shift weight toward lighting at night, taken proportionally from non-crime factors.

    Preserves sum-to-~1.0. At noon: unchanged. At 2am: lighting +0.10 absolute.
    """
    darkness = _darkness(hour)
    shift = 0.10 * darkness
    w = dict(base)
    w["lighting"] = w["lighting"] + shift
    other_keys = [k for k in w if k not in ("crime", "lighting")]
    other_total = sum(w[k] for k in other_keys) or 1.0
    for k in other_keys:
        w[k] = max(0.01, w[k] - shift * (w[k] / other_total))
    return w


def main() -> int:
    feats = pd.read_parquet(GOLD / "stop_features.parquet")
    labels = pd.read_parquet(GOLD / "labels.parquet")

    # T1: enforce uid as string everywhere — prevents silent dtype-drift KeyErrors downstream
    feats["uid"] = feats["uid"].astype(str)
    labels["uid"] = labels["uid"].astype(str)
    uids = feats["uid"].values

    # Static factors (indexed by uid for alignment)
    sf = pd.DataFrame(index=uids)
    sf["lighting"] = _norm(np.log1p(feats["lights_50m"].clip(upper=CAPS["lights_50m"])), invert=False).values * 100

    pois = feats["pois_150m"].clip(upper=CAPS["pois_150m"])
    food = feats["food_drink_150m"].clip(upper=CAPS["food_drink_150m"])
    sf["eyes_on_street"] = _norm(np.log1p(pois) * 0.5 + np.log1p(food) * 0.5, invert=False).values * 100

    raw_iso = feats["pois_150m"] + feats["buildings_50m"]
    iso = _norm(np.log1p(raw_iso), invert=True).values * 100
    sf["isolation"] = iso
    sf["wait_exposure"] = iso

    nodes = feats["building_nodes_50m"].clip(upper=CAPS["building_nodes_50m"])
    bldgs = feats["buildings_50m"].clip(upper=CAPS["buildings_50m"])
    sf["sightline"] = _norm(np.log1p(nodes * bldgs), invert=True).values * 100

    sf["disorder_311"] = _norm(np.log1p(feats["disorder_count_200m"].clip(upper=CAPS["disorder_count_200m"])), invert=True).values * 100

    sf["lit_way_supplement"] = _norm(np.log1p(feats["lit_yes_100m"].clip(upper=CAPS["lit_yes_100m"])), invert=False).values * 100

    # B1: GLOBAL crime normalization across ALL bins (was per-bin → variance wiped)
    all_crime_log = np.log1p(labels["mci_count"].clip(upper=CAPS["crime_count_500m"]))
    log_min = float(all_crime_log.min())
    log_max = float(all_crime_log.max())
    log_span = log_max - log_min if log_max > log_min else 1.0
    print(f"Global crime log range: [{log_min:.3f}, {log_max:.3f}] (span={log_span:.3f})")

    hours = sorted(labels["hour"].unique())
    day_types = sorted(labels["day_type"].unique())
    print(f"Bins: {len(hours)}h x {len(day_types)} day_types = {len(hours) * len(day_types)}")

    rows = []
    for hour in hours:
        for dt in day_types:
            bin_mask = (labels["hour"] == hour) & (labels["day_type"] == dt)
            bin_labels = labels.loc[bin_mask].set_index("uid")
            crime_per_stop = bin_labels["mci_count"].reindex(uids, fill_value=0)

            # Global-normalized crime: preserves absolute magnitude across bins
            log_c = np.log1p(crime_per_stop.clip(upper=CAPS["crime_count_500m"]).values.astype(float))
            f_crime_raw = np.clip((log_c - log_min) / log_span, 0.0, 1.0)
            f_crime = (1.0 - f_crime_raw) * 100.0  # invert: high crime → low safety score

            # D2: night-shifted weights — boost lighting weight when dark
            w_local = _night_weights(WEIGHTS, hour)

            composite = np.zeros(len(uids), dtype=np.float64)
            for name, w in w_local.items():
                if name == "crime":
                    composite += w * f_crime
                elif name in sf.columns:
                    composite += w * sf[name].values
            composite = np.clip(composite, 0.0, 100.0)

            rows.append(pd.DataFrame({
                "uid": uids,
                "hour": int(hour),
                "day_type": str(dt),
                "t_ntsi_score": composite.round(1),
                "f_crime": f_crime.round(1),
            }))

    out = pd.concat(rows, ignore_index=True)
    out["uid"] = out["uid"].astype(str)
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False, engine="pyarrow")

    print(f"Output: {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print(f"Rows: {len(out):,}")
    print(f"Score range: {out['t_ntsi_score'].min():.1f} - {out['t_ntsi_score'].max():.1f}")

    sample = out[out["uid"].isin(uids[:3])]
    print("\nSample stop score variance across bins:")
    for uid in uids[:3]:
        s = sample[sample["uid"] == uid]["t_ntsi_score"]
        print(f"  {uid}: min={s.min():.1f} max={s.max():.1f} range={s.max()-s.min():.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

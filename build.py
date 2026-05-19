"""STARSAI reproducible build (FR-034) — cross-platform.

Use this OR the Makefile. Both define the same DAG.

Usage:
    python build.py install         # install pipeline/requirements.txt
    python build.py all             # full rebuild
    python build.py <stage>         # bronze | silver | gold | ml | score | public | route
    python build.py clean           # remove derived artifacts

Examples:
    python build.py install
    python build.py all
    python build.py score
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
P = ROOT / "pipeline"

STAGES = {
    "bronze": ["ingest.py", "preprocess.py", "bronze_statcan.py"],
    "silver": ["silver_crime.py", "silver_poles.py", "silver_311.py",
               "silver_osm.py", "silver_statcan.py"],
    "gold":   ["gold_h3.py", "gold_joins.py", "gold_osm.py", "gold_equity.py"],
    "ml":     ["ml_labels.py", "ml_train.py"],
    "score":  ["score.py", "score_dynamic.py"],
    "public": ["provenance.py", "pack.py"],
    "route":  ["route_graph.py", "route_weights.py"],
}

ALL_ORDER = ["bronze", "silver", "gold", "ml", "score", "public"]


def run(script: str) -> None:
    cmd = [sys.executable, str(P / script)]
    print(f"\n>>> {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=ROOT)
    if res.returncode != 0:
        sys.exit(f"FAILED: {script} (exit {res.returncode})")


def stage(name: str) -> None:
    for script in STAGES[name]:
        run(script)


def install() -> None:
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(P / "requirements.txt")]
    print(f">>> {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def clean(deep: bool = False) -> None:
    for d in ["data/silver", "data/gold", "data/scores", "data/public"]:
        path = ROOT / d
        if path.exists():
            shutil.rmtree(path)
            print(f"removed {d}")
    if deep:
        for f in ["data/bronze/crime_night.parquet", "data/bronze/manifest.json"]:
            fp = ROOT / f
            if fp.exists():
                fp.unlink()
                print(f"removed {f}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "install":
        install()
    elif cmd == "all":
        install()
        for s in ALL_ORDER:
            stage(s)
    elif cmd == "clean":
        clean(deep=False)
    elif cmd == "clean-all":
        clean(deep=True)
    elif cmd in STAGES:
        stage(cmd)
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        return 1
    print("\nDONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

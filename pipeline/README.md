# Pipeline

Bronze → silver → gold → ml → score → public.

## Setup

```bash
# project root
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r pipeline/requirements.txt
```

## Run order (single-shot)

```bash
# from project root
make all          # Unix/macOS
py build.py all   # Windows / cross-platform
```

## Run order (per-stage)

```bash
python pipeline/ingest.py          # bronze: raw download
python pipeline/preprocess.py      # bronze: filter night MCI etc
python pipeline/bronze_statcan.py  # bronze: StatCan census

python pipeline/silver_crime.py    # silver: dedupe + temporal enrich
python pipeline/silver_poles.py
python pipeline/silver_311.py
python pipeline/silver_osm.py
python pipeline/silver_statcan.py

python pipeline/gold_h3.py         # gold: stop H3 indexing
python pipeline/gold_joins.py      # gold: spatial buffer joins
python pipeline/gold_osm.py        # gold: OSM feature enrichment
python pipeline/gold_equity.py     # gold: StatCan equity append

python pipeline/ml_labels.py       # ml: weak labels per bin
python pipeline/ml_train.py        # ml: calibrated LR weights

python pipeline/score.py           # static composite score
python pipeline/score_dynamic.py   # time-aware bin scores

python pipeline/provenance.py      # public: FR-019 per-stop JSON
python pipeline/pack.py            # public: scores.json + GeoJSON + CSV
```

Routing (optional, separate from scoring DAG):

```bash
python pipeline/route_graph.py     # OSM street graph
python pipeline/route_weights.py   # edge weights from scores
python pipeline/route_planner.py   # A* CLI
python pipeline/route_api.py       # FastAPI demo
```

## Output schema

`data/public/scores.json` — compact static API, one entry per stop:

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-05-19T...",
  "commit": "<git short sha>",
  "model": {"version": "v0.3.1", "method": "logistic_regression", "auroc": 0.6806},
  "n_stops": 9378,
  "stops": [
    {
      "uid": "ttc:13805",
      "id": "13805",
      "name": "Wellesley Station - Northbound Platform",
      "sys": "ttc",
      "lat": 43.666149,
      "lon": -79.383788,
      "score": 27.1,
      "rank": 9378,
      "q": "Q4",
      "f": {
        "lighting": 36.6, "crime": 0.0, "eyes_on_street": 97.9,
        "isolation": 17.7, "wait_exposure": 17.7, "sightline": 15.4,
        "disorder_311": 0.0, "lit_way_supplement": 22.8
      }
    }
  ]
}
```

`data/public/provenance.json` — same `stops` keyed by uid, plus raw input
feature counts (lights_50m, crime_count_500m, etc), weights used, model meta,
source dataset URLs + record counts.

## Day-type schema

4-way: `weekday | fri | sat | sun`. See `silver_crime.py:day_type_from_dow`.
`labels.parquet` and `scores_dynamic.parquet` are keyed on `(uid, hour, day_type)`.

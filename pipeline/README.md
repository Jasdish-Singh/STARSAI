# Pipeline

Data ingestion → cleaning → factor computation → T-NTSI score → JSON output

## Setup

```bash
cd pipeline
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

## Run order

```bash
python ingest.py          # 1. Download all raw data
python factors.py         # 2. Compute 12 factors per stop per time bin
python score.py           # 3. Compute T-NTSI composite score
python validate.py        # 4. Run validation against 14 known-bad stops
python export.py          # 5. Export index.geojson → ../frontend/public/
```

## Output schema

`data/processed/index.geojson` — one feature per stop:
```json
{
  "stop_id": "TTC_14532",
  "system": "ttc",
  "lat": 43.6712,
  "lon": -79.3857,
  "scores": {
    "weekday": { "18": 72, "19": 68, "20": 61, "21": 54, "22": 41, "23": 33, "0": 28 },
    "fri_sat": { "18": 70, ... },
    "sunday":  { "18": 74, ... }
  },
  "factors": {
    "lighting": 0.82, "crime": 0.34, "eyes_on_street": 0.61,
    "isolation": 0.45, "wait_exposure": 0.38, "sightline": 0.71,
    "co_presence": 0.55, "crossing_danger": 0.60, "disorder_311": 0.78,
    "alcohol_outlets": 0.65, "enclosure": 0.90, "terminal_desolation": 0.88
  },
  "provenance": { "crime_row_ids": [...], "lighting_count": 3, ... }
}
```

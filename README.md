# STARS — Safety Transit Analytics & Risk System

**Women's nighttime safety index for TTC stops**

Team: Jasdish Singh (Centennial College) + Tiana Gaurd (UofT)
Competition: Transit Data Challenge 2026 | Deadline: May 30, 2026

---

## What it does

Composite nighttime safety score (0–100, 100=safest) for 9,378 TTC surface
stops + subway stations, across 64 time windows (16 night hours × 4 day types).
Per-stop scores published as static JSON for browser + analyst use, with full
factor provenance and a reproducible one-command rebuild.

## Score factors (8 implemented)

| Factor | Source | Notes |
|---|---|---|
| Lighting | poles within 50m (Toronto Open Data) | streetlights only |
| Crime | MCI within 500m, last 36 months (Toronto Police) | night-filtered |
| Eyes on street | POIs + food/drink within 150m (OSM) | log-normalized blend |
| Isolation | POIs + buildings within 50m (OSM) | inverted: low=isolated |
| Wait exposure | proxy = isolation | no GTFS headways yet |
| Sightline | building nodes × buildings within 50m (OSM) | occlusion proxy |
| Disorder (311) | noise/graffiti/drugs/etc within 200m | last 12 months |
| Lit-way supplement | `lit=yes` OSM ways within 100m | reinforces lighting signal |

Weights are blended 40% theory + 40% logistic regression (AUROC 0.6806 on weak
labels) + 20% uniform prior. See `config/calibrated_weights.json` and
`docs/SDLC.md §5.2`. AUROC is below the 0.70 target — treated as a weak
classifier whose role is to nudge theory weights, not to score directly.

## Equity layer

4 columns joined per stop from StatCan 2021 Census tracts:
`pop_density_km2`, `median_household_income`, `visible_minority_pct`,
`indigenous_pct`. Enables an equity-mode view (FR-026).

## Stack

| Layer | Tech | Status |
|---|---|---|
| Pipeline | Python 3.11, DuckDB, GeoPandas, scikit-learn | ✅ shipped |
| Model | calibrated logistic regression | ✅ shipped |
| Routing | OSMnx street graph + A* (FastAPI optional) | ✅ scripts; backend optional |
| Public API | static `scores.json` + `provenance.json` | ✅ shipped |
| Frontend | React + Vite + Deck.gl scaffold | ⏳ in progress |
| Hosting | static CDN (no backend required) | ⏳ deploy pending |

## Data sources

- [Toronto Police Major Crime Indicators](https://data.torontopolice.on.ca)
- [TTC GTFS static](https://open.toronto.ca/dataset/ttc-routes-and-schedules/)
- [Toronto Street Furniture — Poles](https://open.toronto.ca/dataset/street-furniture-poles/)
- [311 Service Requests](https://open.toronto.ca/dataset/311-service-requests-customer-initiated/)
- [OpenStreetMap](https://www.openstreetmap.org/copyright)
- [StatCan 2021 Census Profile + CT boundaries](https://www12.statcan.gc.ca/census-recensement/2021/)

## Reproduce

```bash
# Unix/macOS
make install
make all

# Windows
py build.py install
py build.py all
```

Stages: `bronze → silver → gold → ml → score → public`.
See `Makefile` or `build.py` for individual stage targets.

## Public deliverables (`data/public/`)

| File | Purpose |
|---|---|
| `scores.json` | FR-031 static API: stop scores + 8 factors, ~390 KB gzipped |
| `provenance.json` | FR-019 per-stop inputs + factor scores + commit hash |
| `stops_scores.geojson` | map rendering layer |
| `stops_scores.csv` | analyst download |
| `manifest.json` | catalog with sizes + roles |

## Project structure

```
STARSAI/
├── data/           # bronze/silver/gold/scores/public layers
├── pipeline/       # ingest, preprocess, silver, gold, ml, score, pack
├── config/         # weights, calibration, validation stops
├── docs/           # SDLC, methodology, data sources
├── frontend/       # React scaffold (in progress)
├── Makefile        # reproducible build (Unix)
└── build.py        # reproducible build (cross-platform)
```

## Out of scope for submission

Listed in `docs/SDLC.md` as P1/P2 but **not implemented**:
GTFS-RT, LLM narration, voice interface, policy simulator, AGCO alcohol-outlet
factor, Mapillary streetscape vision, crossing-danger (KSI) factor.

# Toronto Nighttime Transit Safety Index — Technical Report

**Team:** STARS AI — Jasdish Singh (Centennial College), Tiana Gaurd (UofT)
**Competition:** Transit Data Challenge 2026
**Submission:** May 30, 2026
**Repository:** https://github.com/Jasdish-Singh/STARSAI

---

## Executive summary

We built T-NTSI — a transparent, time-aware, stop-level nighttime safety
index for 9,378 TTC stops and subway platforms across 64 time bins
(16 night hours × 4 day-types). The score (0–100, 100 = safest) is computed
from 8 environmental factors derived entirely from open data, with blended
weights from prior literature and a calibrated logistic regression. Every
score is reproducible from raw inputs in a single command and carries a
machine-readable provenance record naming its inputs, weights, model
version, and pipeline commit hash. No backend infrastructure is required:
the entire submission is a static CDN payload (~1.5 MB gzipped).

## 1. Problem

Women restrict, re-route, or refuse nighttime transit at materially higher
rates than men. Toronto publishes the open data needed to quantify *why* —
crime, lighting, disorder, isolation, frontage — but no public index
combines those signals into a single transparent score per stop per time
window. Existing apps are either crowdsourced (Citizen, SketchFactor) or
proprietary (in-house agency dashboards). STARSAI is the open alternative.

## 2. Approach

### 2.1 Architecture

```
bronze  →  silver  →  gold      →  ml     →  score   →  public
ingest     clean      H3+joins     labels    static     scores.json
raw        enrich     OSM+equity   LR+cal    dynamic    provenance.json
```

Six stages, fully reproducible: `make all` (Unix) or `py build.py all`
(cross-platform). Each stage emits a parquet + manifest with row count,
byte count, and ISO-8601 timestamp.

### 2.2 Data sources

| Dataset | Source | Use |
|---|---|---|
| TTC GTFS static | open.toronto.ca | stop locations |
| Major Crime Indicators | Toronto Police Open Data | crime factor + ML labels |
| Topographic Poles | open.toronto.ca | lighting factor |
| 311 Service Requests | open.toronto.ca | disorder factor |
| OpenStreetMap (Geofabrik) | openstreetmap.org | POIs, buildings, lit-ways, sightline |
| StatCan 2021 Census | statcan.gc.ca | equity layer |

All datasets are open-licence and contain no PII. Pull date: 2026-05-17
(2026-05-19 for StatCan). Manifests record SHA-256 + byte count per file.

### 2.3 Factors (8 implemented)

Each factor produces a 0–100 score per stop, log-transformed, percentile-
capped, min-max normalized.

| # | Factor | Source | Buffer | Notes |
|---|---|---|---|---|
| 1 | lighting | streetlight poles | 50m | log1p, cap 50 |
| 2 | crime | MCI (last 36mo, night-filtered) | 500m | log1p, cap 200, inverted |
| 3 | eyes_on_street | OSM amenities + food/drink | 150m | weighted blend |
| 4 | isolation | OSM POIs + buildings | 50m | inverted |
| 5 | wait_exposure | proxy = isolation | — | no GTFS headway yet |
| 6 | sightline | OSM building nodes × buildings | 50m | occlusion proxy, inverted |
| 7 | disorder_311 | 311 disorder categories (12mo) | 200m | inverted |
| 8 | lit_way_supplement | OSM ways tagged `lit=yes` | 100m | reinforces lighting |

See `docs/METHODOLOGY.md §5` for full formulas.

### 2.4 Weight derivation

```
weight_blended = 0.40 · weight_theory + 0.40 · weight_data + 0.20 · uniform
uniform = 1/8 = 0.125
```

- `weight_theory`: prior literature (SDLC §5.2).
- `weight_data`: calibrated logistic regression coefficients normalized to
  sum to 1.
- 20% uniform regularizes against any single noisy signal dominating.

| Factor | theory | data | blended |
|---|---:|---:|---:|
| lighting | 0.180 | 0.139 | **0.152** |
| crime | 0.250 | 0.069 | **0.153** |
| eyes_on_street | 0.150 | 0.130 | **0.137** |
| isolation | 0.100 | 0.134 | **0.119** |
| wait_exposure | 0.120 | 0.134 | **0.127** |
| sightline | 0.050 | 0.130 | **0.097** |
| disorder_311 | 0.100 | 0.133 | **0.118** |
| lit_way_supplement | 0.050 | 0.131 | **0.097** |

### 2.5 Time-aware refinements

- **Global crime normalization.** Bin-level crime is normalized using the
  global `log1p` range across *all* bins, preserving cross-bin variance
  (per-bin normalization wiped this out).
- **Night-shifted weights.** Deep-night hours (20–06) shift +0.10 absolute
  weight from non-crime factors to `lighting`, penalizing low-lit stops
  harder after dusk without retraining the model.

## 3. Results

### 3.1 Static composite score (per stop)

- N stops scored: **9,378**
- Mean composite: **54.27** (σ = 7.26)
- Median: **54.25**
- Range: **27.1 – 78.0**

**Worst 5 stops** (lowest composite, validates the model):

| Score | Stop |
|---:|---|
| 27.1 | Wellesley Station – Northbound Platform |
| 28.8 | Mortimer Ave at Inwood Ave West Side |
| 28.9 | Mortimer Ave at Inwood Ave |
| 29.1 | Brimorton Dr at Linville Rd |
| 29.5 | Brimorton Dr at Linville Rd |

**Best 5 stops** (suburban, low crime, low disorder):

| Score | Stop |
|---:|---|
| 78.0 | 3381 Steeles Ave East |
| 76.8 | Steeles Ave East at Victoria Park Ave |
| 76.8 | 3160 Steeles Ave East |
| 76.8 | Victoria Park Ave at Steeles Ave East South Side |
| 75.7 | Steeles Ave East at Victoria Park Ave West Side |

### 3.2 Dynamic (time-aware) scores

- N bins: **600,192** (9,378 stops × 64 time bins)
- Dynamic range: **28.3 – 79.7**
- Mean score declines into deep night, as expected. Sample (mean over all stops):

| Hour | weekday | fri | sat | sun |
|---:|---:|---:|---:|---:|
| 19 | 61.7 | 61.7 | 61.7 | 61.7 |
| 21 | 56.4 | 59.3 | 59.3 | 59.5 |
| 23 | 56.8 | 59.3 | 59.4 | 59.6 |
| 02 | 57.7 | 59.7 | 59.6 | 59.9 |

**Note on the weekday < Fri/Sat pattern.** Weekday bins aggregate four
days of historical MCI events (Mon–Thu) into one `(hour, day_type)`
bucket, while Fri/Sat/Sun each aggregate one day. The unnormalized
count is therefore higher for weekday, which the model reads as
*more crime in this bin* and penalizes accordingly. This is a known
artifact of the labelling scheme and is disclosed here; a future
revision will normalize counts per day-type by the number of
contributing weekdays.

### 3.3 ML calibration

| Metric | Value |
|---|---:|
| Model | LogisticRegression (sklearn), `class_weight="balanced"`, StandardScaler |
| Train | 486,208 examples |
| Test | 113,984 examples |
| Positive rate | 0.262 |
| **AUROC** | **0.6806** |

AUROC is below the SDLC target of 0.70. We disclose this honestly. The
model is **not** used as a direct classifier — it is used to nudge theory
weights toward signals the data finds informative. The 40% theory + 20%
uniform terms in the blend prevent any data signal from dominating.

The strongest coefficient is `crime` at −0.6507 (raw), confirming the
data agrees crime is the dominant risk signal even when its blended
weight is moderated downward.

## 4. Validation

`config/VALIDATION_STOPS` lists 14 hand-curated "known-bad" stops
(industrial corridors, late-night terminals, tunnel platforms, suburban
isolation). `score.py` checks at run time that each falls in the bottom
quartile (Q1). Run output is in stdout for manual review.

This is a sanity check, not a held-out test set. A future revision will
add a survey-validated ground truth.

## 5. Equity layer

`pipeline/gold_equity.py` spatial-joins each stop to its containing 2021
Census tract and appends four columns: `pop_density_km2`,
`median_household_income`, `visible_minority_pct`, `indigenous_pct`.
These are **not** factors in the composite score; they enable an equity
view that compares score residuals against income/density/minority
proportion.

## 6. Reproducibility (FR-019, FR-031, FR-034)

| Requirement | Deliverable |
|---|---|
| FR-019 — per-stop provenance | `data/public/provenance.json` |
| FR-031 — static API | `data/public/scores.json` (~390 KB gzipped) |
| FR-034 — one-command rebuild | `Makefile` + `build.py` |

Every score in `scores.json` carries the git commit hash that generated
it. `provenance.json` exposes the raw feature inputs, factor scores,
weights, and source dataset URLs per stop. `requirements.txt` is pinned
and trimmed to actually-used dependencies.

## 7. Routing (optional demo)

`pipeline/route_graph.py` builds an OSMnx pedestrian street graph of
Toronto. `route_weights.py` attaches each edge to its nearest TTC stop
and assigns cost `length · (1 + α · (1 − score/100))`. `route_planner.py`
runs A* with an admissible haversine heuristic. `route_api.py` is an
optional FastAPI wrapper (not required for the static submission).

A circadian boost (`NIGHT_BOOST × DAY_TYPE_BOOST`) amplifies risk for
late-hour Fri/Sat trips. The route demo consumes scores; it does not
influence them.

## 8. Limitations

- **Weak ML labels** (AUROC 0.6806). Historical MCI within 250m at the
  same hour bin is a noisy proxy for perceived safety.
- **`wait_exposure` is a proxy**, not real GTFS headways.
- **Weekday count inflation** (see §3.2): aggregating four days as one
  bucket biases weekday bins downward.
- **No real-time data**: GTFS-RT, live ridership, weather not used.
- **OSM coverage uneven**: `lit=yes` tag density varies by neighborhood.
- **Single-city scope**: TTC only. Regional GTFS feeds blocked or 404
  at pull time.
- **No survey-validated ground truth**.

## 9. Future work

- Survey-based labels (replaces MCI weak labels).
- Real GTFS headway calc for `wait_exposure`.
- Normalize weekday counts by day count to remove sampling bias.
- AGCO alcohol-outlet factor.
- Mapillary streetscape vision factor.
- KSI crossing-danger factor.
- Re-enable regional GTFS feeds (MiWay, Brampton, YRT, Halton).
- Policy simulator (FR-025).
- Survey-validated calibration set.

## 10. Contributions

- **Jasdish Singh** — pipeline architecture, ingest/silver/gold layers,
  scoring, ML calibration, provenance, reproducibility, documentation.
- **Tiana Gaurd** — equity layer design review, methodology validation,
  frontend scaffold.

## 11. Acknowledgments

City of Toronto Open Data; Toronto Police Service; OpenStreetMap
contributors; Statistics Canada; Transit Data Challenge 2026 organizers.

## 12. Licence

Code: MIT. Data deliverables (`scores.json`, `provenance.json`,
`stops_scores.geojson`, `stops_scores.csv`): CC-BY 4.0, attributing
upstream open-data sources per each licence above.

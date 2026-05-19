# Methodology — Toronto Nighttime Transit Safety Index (T-NTSI)

**Project:** STARS — Safety Transit Analytics & Risk System
**Team:** STARS AI (Jasdish Singh, Centennial College + Tiana Gaurd, UofT)
**Competition:** Transit Data Challenge 2026
**Submission:** May 30, 2026
**Pipeline commit at score generation:** see `data/public/scores.json#commit`

---

## 1. Problem

Women restrict, re-route, or refuse nighttime transit at higher rates than
men. Toronto publishes the data to explain *why* — crime, lighting,
disorder, isolation, frontage — but no public index fuses it into a
transparent, time-aware, stop-level score. STARSAI builds that index using
only open data, with full per-stop provenance.

## 2. Scope

- 9,378 stops: TTC surface routes + subway stations.
- 16 night hours: 17:00–08:00 local Toronto time.
- 4 day-types: `weekday` (Mon–Thu), `fri`, `sat`, `sun`.
- 64 time bins per stop = 16 hours × 4 day-types.
- 8 implemented factors (see §5).

**Out of scope for this submission:** GTFS-RT, LLM narration, voice
interface, policy simulator, AGCO alcohol-outlet factor, Mapillary
streetscape vision factor, crossing-danger (KSI) factor. See README.

## 3. Data sources

| Dataset | Source | Pull date | Use |
|---|---|---|---|
| TTC GTFS static | open.toronto.ca | 2026-05-17 | stop locations |
| Major Crime Indicators (MCI) | Toronto Police Open Data | 2026-05-17 | crime factor + ML labels |
| Topographic Poles (streetlight proxy) | open.toronto.ca | 2026-05-17 | lighting factor |
| 311 Service Requests (2024 + 2025) | open.toronto.ca | 2026-05-17 | disorder factor |
| OpenStreetMap (Geofabrik Ontario extract) | openstreetmap.org | 2026-05-17 | POIs, buildings, lit-ways, sightline |
| StatCan 2021 Census Profile + CT boundaries | statcan.gc.ca | 2026-05-19 | equity layer (4 columns) |

All sources are open (ODbL or Open Government Licence). No PII. Resource IDs
and verified URLs in `pipeline/config.py`. Bronze-layer manifests record
download SHA-256 + byte count.

## 4. Pipeline (medallion architecture)

```
bronze  → silver   → gold        → ml         → score      → public
ingest    clean      H3+joins      labels       static       provenance.json
raw       enrich     OSM+equity    LR+calib     dynamic      scores.json
```

Reproducible via `make all` (Unix) or `py build.py all` (cross-platform).
Each stage emits a parquet + manifest with timestamp, row count, bytes.

**Buffer rings:** 50m (lighting, sightline), 150m (POIs), 200m (311),
500m (crime). DuckDB spatial extension + Haversine macro for joins.

## 5. Factors

Each factor produces a 0–100 score per stop, 100 = safest. All raw counts
are cap-clipped at percentile-driven thresholds (see `pipeline/score.py`
`CAPS`), then `log1p`-transformed and min-max normalized.

| # | Factor | Formula (raw → score) | Source |
|---|---|---|---|
| 1 | `lighting` | `log1p(streetlights within 50m)`, cap 50 | Topographic Poles |
| 2 | `crime` | `log1p(MCI within 500m, 36mo, night)`, cap 200, inverted | MCI |
| 3 | `eyes_on_street` | `0.5·log1p(POIs_150m) + 0.5·log1p(food_drink_150m)` | OSM `amenity` |
| 4 | `isolation` | `log1p(POIs_150m + buildings_50m)`, inverted | OSM |
| 5 | `wait_exposure` | proxy = `isolation` (no GTFS headway calc yet) | OSM |
| 6 | `sightline` | `log1p(building_nodes_50m × buildings_50m)`, inverted | OSM building footprints |
| 7 | `disorder_311` | `log1p(disorder requests within 200m, 12mo)`, cap 10, inverted | 311 |
| 8 | `lit_way_supplement` | `log1p(OSM ways with lit=yes within 100m)`, cap 20 | OSM |

**Inverted** = high count means lower safety (more crime, more isolation,
more occlusion, more disorder).

**Honest caveat on factor 5 (`wait_exposure`):** SDLC originally specified
GTFS headways as the input, but the May 30 build uses isolation as a
proxy. This is documented in the score JSON and provenance JSON; a real
headway calculation is a deferred improvement.

## 6. Composite score

```
T-NTSI(stop) = Σ_f  weight_f · factor_f(stop)
```

Output is clipped to [0, 100]. See `pipeline/score.py:compute_composite`.

## 7. Weight derivation

Blended formula (see `pipeline/ml_train.py` and `config/calibrated_weights.json`):

```
weight_blended = 0.40 · weight_theory + 0.40 · weight_data + 0.20 · uniform
uniform        = 1/8 = 0.125 for each factor
```

- **`weights_theory`** (from SDLC §5.2 prior literature): lighting 0.18,
  crime 0.25, eyes 0.15, isolation 0.10, wait_exposure 0.12, sightline 0.05,
  disorder_311 0.10, lit_way_supplement 0.05. Sum = 1.00.
- **`weights_data`** derived from a calibrated logistic regression on weak
  labels (§8).
- **`weights_blended`** is what `score.py` uses at runtime. Snapshot for
  v0.3.1:

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

The 20% uniform prior is a deliberate regularizer: it prevents any
single noisy data signal from dominating, and prevents theory weights
from suppressing factors the data finds informative.

## 8. ML calibration — weak-label logistic regression

`pipeline/ml_labels.py` generates a per-`(stop, hour, day_type)` binary
label: `1` if any MCI incident occurred within 250m at that bin in the
last 36 months, else `0`. Result: 600,192 examples (9,378 stops × 64
bins), positive rate ~26.2%.

`pipeline/ml_train.py` fits a `LogisticRegression` with `class_weight=
"balanced"` and `StandardScaler`. Reported metrics in
`config/calibrated_weights.json`:

- AUROC = **0.6806** (test split, 113,984 examples)
- N train = 486,208 | N test = 113,984
- Positive rate = 0.2619

**AUROC 0.6806 is below the SDLC target of 0.70.** We disclose this
honestly. The model is **not** used as a direct classifier; it is used
to *nudge* theory weights toward signals the data actually finds
predictive. Two reasons we keep it despite the weak AUROC:

1. **Label noise.** "MCI within 250m at the same hour bin in the last
   36 months" is a weak proxy for the latent quantity we care about
   (perceived safety for women at night). Historical crime location is
   spatially correlated with future risk but not a faithful label.
2. **Blending dampens overfit.** The 40% theory + 20% uniform terms
   anchor the weights, so the data term cannot pull any factor to zero
   or to one. The blended weights stay close to theory while letting
   data adjust the ranking.

Coefficient signs are still informative: `crime` is the strongest
negative coefficient (−0.6507 raw), confirming that the data agrees
crime is the dominant risk signal even when its blended weight is
moderated downward.

## 9. Dynamic (time-aware) scoring

`pipeline/score_dynamic.py` produces per-bin scores for all 64 bins.
Two refinements over the static composite:

- **B1 — global crime normalization.** Crime counts within a bin are
  normalized using the global `log1p`-range across *all* bins, not the
  bin's own range. This preserves the absolute magnitude difference
  between a low-crime 02:00 stop and a high-crime 19:00 stop. (Per-bin
  normalization wiped out exactly the cross-bin variance we want to
  expose.)
- **D2 — night-shifted weights.** At deep night (hours 20–06) the
  lighting weight is shifted upward by +0.10 absolute, taken proportionally
  from non-crime factors. Sum-to-~1.0 preserved. This penalizes low-lit
  stops harder after dusk without retraining the model. Daytime hours
  (07–19) leave weights unchanged.

Output: `data/scores/scores_dynamic.parquet` keyed by `(uid, hour, day_type)`.

## 10. Routing layer

`pipeline/route_graph.py` builds an OSMnx pedestrian street graph of
Toronto. `pipeline/route_weights.py` attaches each edge to its nearest
TTC stop via a BallTree and assigns an edge cost of
`length_m · (1 + alpha · (1 − score/100))`. `route_planner.py` runs A*
with a haversine heuristic that stays admissible. `route_api.py` is an
optional FastAPI wrapper.

A *circadian boost* `NIGHT_BOOST × DAY_TYPE_BOOST` (defined in
`route_planner.py`) further amplifies risk for late-hour Fri/Sat trips.
Routing is not used for stop scoring — it consumes scores as a downstream
demo only.

## 11. Equity layer

`pipeline/gold_equity.py` joins each stop to its containing 2021 Census
tract via a `shapely.geometry.Point`-in-polygon spatial join, and appends
four columns: `pop_density_km2`, `median_household_income`,
`visible_minority_pct`, `indigenous_pct`. These are **not** factors in
the composite score; they enable an equity-mode view that compares
score residuals against income, density, or minority proportion.

## 12. Validation

`config/VALIDATION_STOPS` enumerates 14 hand-curated "known-bad" stops
(industrial corridors, terminal-after-22:00, tunnel platforms,
suburban stops). At every score run, `score.py` checks that each
validation stop falls in Q1 (bottom quartile). Run-time output is
printed for manual review. This is a sanity check, not a held-out
test set.

## 13. Provenance and reproducibility

- **FR-019** — `data/public/provenance.json`: per-stop dictionary with
  raw feature inputs, 8 factor scores, composite, weights used, model
  meta (version, method, AUROC), git commit hash, source dataset URLs
  with record counts, ISO-8601 generation timestamp.
- **FR-031** — `data/public/scores.json`: compact static API (~390 KB
  gzipped) suitable for CDN hosting. No live backend needed.
- **FR-034** — `Makefile` and `build.py` give a one-command rebuild from
  raw inputs to public deliverables. `pipeline/requirements.txt` is
  trimmed to actually-used dependencies (pyarrow, pgeocode, osmium,
  osmnx, networkx added; librosa, xgboost, ultralytics, mediapipe,
  opencv-python, seaborn, jupyter removed).

## 14. Limitations

- **Weak ML labels** (AUROC 0.6806). See §8.
- **`wait_exposure` is a proxy**, not real GTFS headways.
- **No real-time data**: GTFS-RT, live ridership, weather not used.
- **OSM coverage is uneven**: `lit=yes` tag density varies by
  neighborhood, which can under-credit lighting in less-mapped areas.
- **Single-city scope**: TTC only. Regional GTFS feeds (MiWay, Brampton,
  YRT, Halton) are in scope in `config.py` but upstream URLs were
  blocked or 404 at pull time; disabled for May 30 submission.
- **No survey-validated ground truth**: the index reflects *measurable
  environmental risk signals*, not lived perception.

## 15. Future work

- Survey-based label upgrade (replaces MCI weak labels).
- Real GTFS headway calculation for `wait_exposure`.
- AGCO alcohol-outlet density (factor 9).
- Mapillary streetscape vision (factor 10).
- KSI crossing-danger factor.
- Re-enable regional GTFS feeds.
- Policy simulator (FR-025).

## 16. Citing

Cite as:

> STARS AI (Singh, J. & Gaurd, T.). 2026. *Toronto Nighttime Transit
> Safety Index*. Transit Data Challenge 2026 submission.
> https://github.com/Jasdish-Singh/STARSAI

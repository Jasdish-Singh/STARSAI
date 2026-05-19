# STARS — Safety Transit Analytics & Risk System

**Women's nighttime safety index for TTC stops**

Team: Jasdish Singh (Centennial College) + Tiana Gaurd (UofT)
Competition: Transit Data Challenge 2026 | Deadline: May 30, 2026

---

## What it does

AI-powered composite safety score (0–100) per TTC stop per time window.
Interactive web app with heatmap + safe route planner.

## Score factors

- Street lighting density
- Crime history (Toronto Police MCI data)
- Commercial activity (open businesses nearby)
- Stop isolation (distance to next stop/shelter)
- Wait exposure (bus frequency / headways)

## Stack

| Layer | Tech |
|-------|------|
| Backend | FastAPI + GeoPandas + scikit-learn |
| Model | Random Forest classifier |
| Frontend | React + Deck.gl + Mapbox GL JS |
| Data | Toronto Open Data + TTC GTFS + StatCan |
| Hosting | Render (free tier) |

## Data sources

- [Toronto Police Major Crime Indicators](https://open.toronto.ca)
- [TTC GTFS static feed](https://open.toronto.ca)
- [Toronto Street Lighting](https://open.toronto.ca)
- [OpenStreetMap](https://openstreetmap.org)
- [Statistics Canada demographics](https://statcan.gc.ca)

## Project structure

```
STARSAI/
├── data/           # raw + processed datasets
├── pipeline/       # data ingestion + cleaning scripts
├── model/          # ML model training + scoring
├── api/            # FastAPI backend
├── frontend/       # React app
└── docs/           # technical report + presentation
```

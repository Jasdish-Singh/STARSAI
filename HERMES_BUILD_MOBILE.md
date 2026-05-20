# STARSAI — Mobile PWA Build Brief (for Hermes)

You are building the STARSAI mobile app. Model: deepseek-v4-pro. Project dir: `C:\Jasdish-IMP\STARSAI` (git, public on GitHub).

## Project
STARSAI — women's nighttime safety index for Toronto TTC stops. Transit Data Challenge 2026, submission May 30 2026 (~10 days). 9,378 stops, 0–100 safety score per stop per time window.
Obsidian node: `C:\Jasdish-IMP\Jasdish-Vault\STARSAI.md` (read for context).

## What already exists (do NOT rebuild)
- Static data in `data/public/`: `scores.json` (2.9 MB, per-stop scores), `provenance.json` (4.6 MB, per-stop factor attribution), `manifest.json`.
- Pipeline (bronze/silver/gold, DuckDB+H3), ML model v0.3.1 (AUROC 0.68).
- A* route planner in `pipeline/` (`route_graph.py`, `route_weights.py`, `route_planner.py`, `route_api.py`). Street graph `data/route/toronto_street.graphml` is **326 MB**.

## Task
Build a mobile-first installable PWA frontend that surfaces all features. Frontend not built yet.

## Architecture (validated with a second-AI review — follow exactly)
- Vite + React + TypeScript in `frontend/`
- `vite-plugin-pwa`: manifest + service worker. **PRECACHE ONLY app shell + `scores.json`.** Do NOT precache `provenance.json` — fetch on demand when a stop is tapped.
- Map: MapLibre GL (free tiles, no Mapbox token) + deck.gl in **OVERLAID** mode (not interleaved).
- Stops layer: deck.gl **ScatterplotLayer** (NOT HeatmapLayer). Fixed pixel radius, no animation, no per-stop text labels. Color by score (green→red).
- **NO backend server. NO serverless functions.** Everything static.

## Features (mobile UX)
1. **SafetyMap** — full-screen, MapLibre + ScatterplotLayer of 9,378 stops colored by score. Touch pan/zoom.
2. **Time presets** — 4 buttons, NOT a 64-bin slider: `Weekday 10pm`, `Friday 11pm`, `Saturday 1am`, `Sunday 9pm`. Each swaps the score field used for coloring. Large touch targets, bottom of screen.
3. **StopPanel** — tap a stop → draggable bottom sheet: score, factor breakdown, provenance (fetch that stop's entry from `provenance.json` on demand).
4. **Routing** — DO NOT call A* live (326 MB graph = cold-start death). Instead: precompute 3–5 demo origin→destination safe routes offline using the existing Python A* and save as static GeoJSON in `frontend/public/routes/`. App loads + draws those GeoJSON lines. Build a "demo routes" selector that draws the chosen precomputed route. (If precomputed GeoJSON not present yet, stub the selector and leave a TODO.)
5. **PWA installable** — manifest (icons 192/512, display standalone, theme color), works offline for map+scores.

## Deliverables
- `frontend/` Vite+React+TS project, `npm run dev` works, viewable on phone over LAN.
- Components: `SafetyMap.tsx`, `TimePresets.tsx`, `StopPanel.tsx`, `RouteSelector.tsx`
- `vite.config.ts` with PWA plugin, `public/manifest.webmanifest` + placeholder icons
- `pipeline/bake_demo_routes.py` — runs the existing A* for a handful of OD pairs and writes `frontend/public/routes/*.geojson`

## Constraints
- Read `data/public/manifest.json` FIRST to learn the exact `scores.json` schema before coding the loader.
- Dense code, minimal comments. Match repo conventions.
- This is REMAINING task #1 (frontend MVP), built mobile-first.

## Start
Read `STARSAI.md` + `data/public/manifest.json`, report the `scores.json` schema in one line, then scaffold `frontend/` and build the 4 features. Show `npm run dev` output when done.

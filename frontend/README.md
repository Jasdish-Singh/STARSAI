# Frontend (scaffold, in progress)

**Status:** package.json present, `src/` not yet implemented.

React + Vite + deck.gl + MapLibre GL planned. Will read static
`/data/scores.json` (FR-031) and `/data/provenance.json` (FR-019)
from the public CDN — no backend required.

## Planned setup (once `src/` lands)

```bash
cd frontend
npm install
npm run dev
```

## Planned components (MVP for submission)

```
frontend/
├── src/
│   ├── App.jsx              # root
│   ├── components/
│   │   ├── SafetyMap.jsx    # deck.gl ScatterplotLayer on stops_scores.geojson
│   │   ├── TimeSlider.jsx   # 17:00 → 08:00 scrubber, weekday/fri/sat/sun
│   │   ├── StopCard.jsx     # stop detail panel: factors + provenance link
│   │   └── EquityToggle.jsx # color stops by score vs median-income residual
│   ├── store/
│   │   └── useStore.js      # zustand: selectedStop, hour, dayType, equityOn
│   └── data/                # fetched from /data/scores.json at runtime
└── public/
    └── style.css
```

## Map layers

1. `ScatterplotLayer` — stops colored by composite score (green→red)
2. Optional `H3HexagonLayer` for aggregated view

Heavier visualization (radar charts, policy simulator) is out of scope for
the May 30 submission. See root README "Out of scope" section.

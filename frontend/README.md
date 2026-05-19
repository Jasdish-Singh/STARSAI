# Frontend

React + deck.gl + MapLibre GL — deployed on Vercel

## Setup

```bash
cd frontend
npm install
npm run dev
```

## Key files (to build)

```
frontend/
├── src/
│   ├── App.jsx              # root
│   ├── components/
│   │   ├── SafetyMap.jsx    # deck.gl H3 hex layer + stop markers
│   │   ├── TimeSlider.jsx   # 18:00 → 04:00 scrubber
│   │   ├── FactorRadar.jsx  # 12-factor radar chart on stop click
│   │   ├── EquityPanel.jsx  # score by income decile bar chart
│   │   ├── PolicySim.jsx    # intervention simulator
│   │   └── StopCard.jsx     # stop info sidebar
│   ├── store/
│   │   └── useStore.js      # zustand — selectedStop, timebin, daytype
│   └── data/
│       └── index.geojson    # pre-computed scores (copied from pipeline output)
└── public/
    └── style.css
```

## Map layers (deck.gl)

1. `H3HexagonLayer` — hex grid colored by T-NTSI score (green→red)
2. `ScatterplotLayer` — stop markers sized by ridership
3. `IconLayer` — flag high-risk stops (score < 30)

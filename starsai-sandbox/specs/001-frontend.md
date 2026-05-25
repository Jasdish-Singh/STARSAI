# Spec 001-frontend

## Goal
Mobile-first installable PWA for STARSAI. Replaces wiped `frontend/`. Builds inside sandbox; promoted to repo `frontend/` on PASS.

## Working dir
`starsai-sandbox/src/001-frontend/` (Codex writes ONLY here).

## Stack
- Vite 5 + React 18 + TypeScript 5
- MapLibre GL 5 (no Mapbox token; OSM tiles via `https://tile.openstreetmap.org/{z}/{x}/{y}.png` or Carto Voyager basemap)
- `@deck.gl/react` + `@deck.gl/layers` v9, **OVERLAID** mode (NOT interleaved)
- `zustand` for state
- `vite-plugin-pwa`
- No backend. No serverless. No mapbox-gl. No tailwind unless trivial.

## Data contracts

`/scores.json` shape (from `data/public/manifest.json` + sampling):
```ts
{
  schema_version: number,
  generated_at: string,
  commit: string,
  model: { version: string, method: string, auroc: number },
  n_stops: number,
  stops: Array<{
    uid: string,           // "ttc:13805"
    id: string,
    name: string,
    sys: string,
    lat: number,
    lon: number,
    score: number,         // 0-100
    rank: number,
    q: "Q1"|"Q2"|"Q3"|"Q4",
    f: {                   // factor breakdown 0-100
      lighting: number,
      crime: number,
      eyes_on_street: number,
      isolation: number,
      wait_exposure: number,
      sightline: number,
      disorder_311: number,
      lit_way_supplement: number
    }
  }>
}
```

`/provenance.json` — large object keyed by `uid`. Fetched on demand only when a stop is tapped; cache fetched entries in memory.

`/routes/*.geojson` — optional precomputed demo routes (may be absent; stub gracefully).

Place a minimal **fixture** `public/scores.json` with 5 hand-picked stops in sandbox build (enough to dev against). Promote step swaps for real file.

## Components

### `SafetyMap.tsx`
- Full-screen MapLibre, centered Toronto `[-79.3832, 43.6532]`, zoom 11
- Deck.gl `ScatterplotLayer`:
  - data = stops
  - getPosition `d => [d.lon, d.lat]`
  - getFillColor by score (green→yellow→red ramp; pass `score` or selected preset's score field)
  - getRadius fixed 60m, radiusMinPixels 4, radiusMaxPixels 12
  - pickable, onClick → setSelectedUid
- Touch pan/zoom enabled; no per-stop label

### `TimePresets.tsx`
- Bottom-anchored row, 4 buttons, ≥44px touch height
- Buttons: `Weekday 10pm`, `Fri 11pm`, `Sat 1am`, `Sun 9pm`
- Active button visually distinct
- For v1 the four presets all read `score` (single field today). Wired so swapping field name later is one-liner. Define `PRESETS = [{id, label, field}]` constant — `field` defaults to `"score"`.

### `StopPanel.tsx`
- Draggable bottom sheet, opens when `selectedUid` set, closes on backdrop tap or drag-down
- Header: stop name, score badge, rank `(N of 9378)`
- Body: factor bars (eight values from `f`), 0-100 width, color-coded
- Provenance section: on open fetch `/provenance.json` once (cache result), look up entry by uid, render summary fields if present (graceful fallback if missing). Show spinner while loading.

### `RouteSelector.tsx`
- Lists files from a hardcoded array `DEMO_ROUTES = []` (empty for now, TODO comment)
- If empty, render `<small>Demo routes not baked yet.</small>` and nothing else
- If populated, selecting one fetches `/routes/<file>` and adds GeoJsonLayer to map

### `App.tsx`
- Layout: `<SafetyMap>` full bleed, `<TimePresets>` bottom, `<StopPanel>` overlay when open, `<RouteSelector>` small top-right
- Loads `/scores.json` on mount via fetch (no useState boilerplate — zustand store)

### `store/useStore.ts` (zustand)
```ts
{
  stops: Stop[] | null,
  selectedUid: string | null,
  presetId: string,
  provenance: Record<string, any>,  // cache
  setStops, setSelectedUid, setPreset, setProvenanceEntry
}
```

## PWA config

`vite.config.ts`:
```ts
VitePWA({
  registerType: 'autoUpdate',
  workbox: {
    globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
    runtimeCaching: [{
      urlPattern: /scores\.json$/,
      handler: 'CacheFirst',
      options: { cacheName: 'scores', expiration: { maxEntries: 1 } }
    }, {
      urlPattern: /provenance\.json$/,
      handler: 'CacheFirst',
      options: { cacheName: 'provenance', expiration: { maxEntries: 1 } }
    }]
  },
  manifest: {
    name: 'STARSAI',
    short_name: 'STARSAI',
    description: 'TTC nighttime safety',
    theme_color: '#0b0f1a',
    background_color: '#0b0f1a',
    display: 'standalone',
    start_url: '/',
    icons: [
      { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
      { src: 'icon-512.png', sizes: '512x512', type: 'image/png' }
    ]
  }
})
```

Placeholder icons OK (1x1 PNG or simple SVG converted).

## Acceptance criteria
1. `cd starsai-sandbox/src/001-frontend && npm install && npm run build` succeeds, no TS errors.
2. `npm run dev -- --host` serves on `:5173`, dev page loads without console errors against fixture.
3. Five components exist with the named exports.
4. ScatterplotLayer renders the 5 fixture stops at correct lat/lon.
5. Tapping a stop opens StopPanel, shows score + factor bars.
6. TimePresets renders four buttons, clicking changes active state in store.
7. RouteSelector renders fallback message (empty DEMO_ROUTES).
8. `dist/` after build contains `manifest.webmanifest` + service worker `sw.js`.
9. Total bundle ≤ 800 KB gzipped (deck.gl is heavy; that's the budget).

## Constraints
- No Mapbox token, no `mapbox-gl`, no API keys required.
- No file writes outside `src/001-frontend/`.
- No `node_modules/` in your output (npm install runs locally).
- Code dense, comments only where non-obvious.
- No emojis in code or comments.

## Files Codex must produce
```
src/001-frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── public/
│   ├── scores.json          (5-stop fixture)
│   ├── icon-192.png         (placeholder; can be 1px gray PNG)
│   └── icon-512.png         (placeholder)
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── App.css
    ├── types.ts
    ├── store/useStore.ts
    └── components/
        ├── SafetyMap.tsx
        ├── TimePresets.tsx
        ├── StopPanel.tsx
        └── RouteSelector.tsx
```

## Fixture content for `public/scores.json`
Generate a valid 5-stop subset following the schema above. Stops near downtown Toronto (varied lat/lon and varied scores 20–85). Same top-level structure as real file.

# Spec 004-provenance-pretty

## Goal
Replace raw JSON dump in `StopPanel.tsx` provenance section with grouped, humanized rows.

## Target file
`C:\Jasdish-IMP\STARSAI\frontend\src\components\StopPanel.tsx`

## Current behavior
`renderProvenance(value)` walks `Object.entries(value)` and dumps every key with raw `JSON.stringify` of nested objects. Result: a wall of unreadable text including duplicated `factors` (already shown as bars above) and a `raw` blob of opaque integers.

## Desired behavior
- Show ONLY useful pieces. Skip `stop_id`, `stop_name` (already in header), `composite` (already as score badge), `factors` (already as bars).
- Group `raw` counts into named sections:
  - **Lighting** — `lights_50m`, `poles_total_50m`, `lit_yes_100m`
  - **Crime (500m)** — `crime_count_500m`, `crime_assault_500m`, `crime_robbery_500m`
  - **Disorder (200m)** — `disorder_count_200m`
  - **Activity (150m)** — `pois_150m`, `food_drink_150m`
  - **Buildings (50m)** — `buildings_50m`, `building_nodes_50m`
- Display each row as `<dt>label</dt><dd>value</dd>` (use existing `provenance-list` class)
- Humanize keys: `lights_50m` → "Streetlights" (with subscript distance unit if relevant), `lit_yes_100m` → "Lit-tagged ways", etc. Use this exact mapping table:

```ts
const RAW_LABELS: Record<string, string> = {
  lights_50m: 'Streetlights',
  poles_total_50m: 'Total poles',
  lit_yes_100m: 'Lit-tagged ways',
  crime_count_500m: 'All crime',
  crime_assault_500m: 'Assaults',
  crime_robbery_500m: 'Robberies',
  disorder_count_200m: '311 disorder calls',
  pois_150m: 'POIs',
  food_drink_150m: 'Food / drink',
  buildings_50m: 'Buildings',
  building_nodes_50m: 'Building corners'
};
```

- Render groups in the order above. Each group is a `<section className="prov-group">` with `<h3>` heading.
- If `raw` is missing or empty, show `<p className="muted">no provenance available</p>`.
- Drop the existing `renderProvenance` function entirely; replace with new code path.

## Data contract
Provenance entry shape:
```ts
type Provenance = {
  stop_id: string;
  stop_name: string;
  composite: number;
  factors: Record<string, number>;
  raw: Record<string, number>;
};
```

## Acceptance
1. `npm run build` clean, no TS errors.
2. StopPanel for any stop with provenance shows 5 named groups, each with `<h3>` and `<dl>`.
3. No `JSON.stringify` output visible in panel.
4. Order matches spec.
5. Missing `raw` → graceful fallback message.

## Constraints
- Edit ONLY `StopPanel.tsx`. No CSS file changes required (will inherit existing styling).
- Keep loading/cache logic intact (no behavior change there).
- Keep keyboard a11y additions (Escape close + drag-handle role=button) intact.
- Dense code, no comments.

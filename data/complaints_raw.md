# GTA Transit Safety Complaints — Raw Research Data
**Sources:** Grok (X/Twitter) + Gemini (Google/Reddit)
**Collected:** 2026-05-14
**Scope:** TTC, MiWay, Brampton Transit, Milton/Halton Transit, YRT
**Purpose:** Real-world validation dataset for T-NTSI safety index

---

## Priority Validation Stops (Flagged 2+ times or severe incident)

| Stop / Location | System | Incident Type | Severity | Source | Date |
|---|---|---|---|---|---|
| Dundas St & Hurontario St (Routes 5 & 10) / Hillcrest Ave | MiWay | Violent crime, gun incident, general unease | CRITICAL | Reddit r/mississauga | Feb 2025 |
| Route 30 (Brampton Transit) | Brampton Transit | Physical assault, overcrowding | HIGH | Reddit r/Brampton | Sep 2023 |
| Christie Station | TTC | Stalking — women followed home from station | HIGH | Reddit r/askTO | Historical |
| Islington Ave & Eglinton Ave W | TTC | Unprovoked assault + theft on bus | HIGH | CTV News | Apr 2026 |
| Route 109N (towards Meadowvale Town Centre) | MiWay | Harassment/intimidation on empty bus — man cornered woman in seat | HIGH | Reddit r/mississauga | Jan 2025 |
| Downtown Brampton Terminal | Brampton Transit | Buses leaving early, riders stranded in cold/dark | MEDIUM | Reddit r/Brampton | Jan 2022 |
| Routes: Mississauga Airport area → Brampton | Brampton Transit | Predatory staring/suspected recording of women | MEDIUM | Reddit r/Brampton | Sep 2025 |
| Finch Station (YRT/GO connector) | YRT | Escalator outages → dark isolated stairwells at night | MEDIUM | YRT advisories | May 2026 |
| Ontario St area & general stops | Milton/Halton | Service ends 8pm, construction destroying shelters, unlit isolated stops | MEDIUM | Reddit r/Milton | Apr–May 2026 |
| General TTC surface routes (night buses/streetcars) | TTC | Erratic behavior, enclosed spaces, reduced foot traffic at night | MEDIUM | Reddit r/askTO | Sep 2025–Feb 2026 |

---

## Key Patterns

### 1. Empty Vehicle Effect
Women on nearly empty late-night buses are disproportionately targeted.
- MiWay Route 109N: man cornered woman in empty bus at 9 PM
- Empty buses: multiple reports of men deliberately sitting against women
- **Model implication:** co-presence / ridership factor critical — empty vehicles score LOW

### 2. Service Cut-Off = Stranding Risk
Early service termination leaves women isolated at stops.
- Milton/Halton: service ends 8 PM — any miss = stranded in dark for hours
- Brampton Terminal: buses leaving early or refusing stops
- **Model implication:** wait-exposure + time-of-day + service frequency combine dangerously after 9 PM

### 3. Infrastructure Failure = Unexpected Isolation
Broken escalators, missing shelters, construction = sudden unsafe conditions
- YRT Finch Station: months of escalator outages → dark stairwells
- Milton: construction destroying bus shelters
- **Model implication:** static infrastructure data insufficient — need 311 + service advisories layer

### 4. Perpetrator Profile at Stops
- Unhoused/mentally ill individuals: dominant TTC pattern
- Predatory men on empty vehicles: dominant suburban pattern
- **Model implication:** different risk factors dominate by system — TTC = disorder signals (311, visible encampments), suburban = isolation + ridership signals

### 5. Reporting Gap
- Women report privately (SafeTTC app, police) not publicly
- X/Twitter complaints sparse and often not stop-specific
- **Model implication:** complaint volume ≠ safety level. Silence ≠ safety. Low-complaint suburban stops may be riskier than they appear.

---

## Scope Expansion Note
Original scope: TTC only.
Real-world data shows MiWay and Brampton Transit have documented serious incidents.
**Recommended:** expand T-NTSI coverage to all 5 systems.

| System | GTFS Feed Available | Priority |
|---|---|---|
| TTC | Yes — open.toronto.ca | P0 |
| MiWay | Yes — mississauga.ca | P0 |
| Brampton Transit | Yes — brampton.ca | P1 |
| YRT | Yes — yrt.ca | P1 |
| Milton/Halton Transit | Yes — halton.ca | P2 |

---

## Source Details

### Grok (X/Twitter) — Key Findings
- TTC dominates overwhelmingly. Suburban systems have far quieter public discourse.
- TTC themes: homeless/drug use, aggressive behavior, harassment, security ineffectiveness
- Women-specific: avoidance, fear for female riders, pervs/homeless as primary concerns
- Specific mentions: Sankofa Square/Eaton Centre area, streetcar stops with no shelter
- Limitation: X captures vocal complaints only — many incidents go unreported publicly

### Gemini (Google/Reddit) — Key Findings
- More specific stop-level data than X
- r/mississauga: Dundas/Hurontario critical zone (gun incident)
- r/Brampton: Route 30 repeat physical assaults
- r/askTO: Christie Station stalking, night bus isolation
- r/Milton: service cut-off + construction creating unsafe conditions
- YRT Finch: infrastructure failure creating nighttime isolation

---

## Model Validation Plan
These stops should score in BOTTOM QUARTILE of T-NTSI when model is complete:
1. Dundas & Hurontario (MiWay) — night, weekday + weekend
2. Route 30 corridor stops (Brampton) — peak hours + night
3. Christie Station (TTC) — late night
4. Islington & Eglinton W (TTC) — any hour
5. Finch Station YRT connector — when escalators flagged down
6. Milton Ontario St stops — after 20:00

If model does NOT flag these, recheck weights and input data.

---

## Batch 2 — Hyper-Local Reddit Data (2026-05-14)
**Source:** Gemini deep Reddit scrape (r/toronto, r/askTO, r/mississauga, r/Brampton, r/york)
**Note:** TTC disambiguation required — "TTC" = "Trying to Conceive" in non-GTA subreddits. Filter to GTA subs only.

### New Priority Locations

| Stop / Location | System | Incident Type | Severity | Source |
|---|---|---|---|---|
| Dundas & Sherbourne / Queen & Sherbourne | TTC | Erratic behavior, drug use, harassment — women abandon 501/505 for rideshare | HIGH | r/toronto, r/askTO |
| Spadina Station — lower streetcar tunnel | TTC | Environmental isolation — long tiled walkway, terrible sightlines, echoing acoustics, no exits | HIGH | r/askTO |
| Bloor-Yonge Station platforms | TTC | Platform edge anxiety — fear of being pushed, erratic individuals pacing | HIGH | r/toronto |
| City Centre Transit Terminal (Square One) | MiWay | After 10pm: loitering, aggressive catcalling, women followed to connecting buses | HIGH | r/mississauga |
| Goreway & Derry / Industrial Park stops | MiWay | Pitch-black stops, no shelters, long headways — late shift workers | MEDIUM | r/mississauga |
| Bramalea Terminal | Brampton Transit | No security after dark, aggressive approach for money/conversation | HIGH | r/Brampton |
| Züm 502 Main (nighttime) | Brampton Transit | Extreme overcrowding → groping, men using crowd as cover | SERIOUS | r/Brampton |
| Richmond Hill Centre Terminal | YRT | Sprawling empty concrete at 11pm — hyper-visible, stalking fears, car park connection | HIGH | r/york |

---

## Critical Model Insights from Batch 2

### INSIGHT 1: Co-Presence is NON-LINEAR (most important finding)
Current model: more people = safer (linear assumption).
Reality: **both extremes are dangerous in different ways.**

- **Too few people** (empty bus, desolate terminal) → isolation risk, stalking, following
- **Too many people** (Züm 502, Route 30, packed streetcar) → groping, boundary violations, crowd-as-cover

**Fix:** Co-presence factor must be a **quadratic/inverted-U curve**, not linear.
- Score peaks at moderate ridership (~30-60% capacity)
- Score drops at both near-empty AND near-crush-load
- Different risk types but both score LOW

### INSIGHT 2: Enclosed Transit Infrastructure = Separate Factor Needed
Spadina tunnel and Richmond Hill Terminal reveal a factor not in current model:
**"Infrastructure enclosure"** — the degree to which a waiting/transfer area traps you.

Metrics:
- Number of exits within 50m
- Corridor width (narrow = trapped)
- Acoustic isolation (underground/tunnel = no help heard)
- Visibility to staffed areas

Affects: subway station connectors, underground platforms, enclosed terminals
Does NOT affect: open-air surface stops

### INSIGHT 3: Terminal Desolation ≠ Stop Isolation
Big empty terminals (Richmond Hill Centre, Bramalea, City Centre) score worse than small isolated stops because:
- You are VISIBLE to predators from far away
- You cannot easily leave (waiting for bus)
- Security is centralized but coverage is poor across large footprint

**Fix:** Terminals need their own scoring sub-model. Terminal size (sq meters) × occupancy rate at time bin = desolation score.

### INSIGHT 4: Data Cleaning Rule
Filter "TTC" keyword searches to GTA-specific subreddits only.
Blocklist for scraper: r/TTC (trying to conceive), r/infertility, r/pregnant, r/BabyBumps.

---

## Updated Model Validation Stops (14 total)

Batch 1:
1. Dundas & Hurontario (MiWay) — gun incident
2. Route 30 corridor (Brampton) — repeat assaults
3. Christie Station (TTC) — stalking
4. Islington & Eglinton W (TTC) — assault
5. Finch Station YRT connector — infrastructure trap
6. Milton Ontario St stops after 20:00 — stranding risk

Batch 2 (new):
7. Dundas & Sherbourne / Queen & Sherbourne (TTC) — disorder hotspot
8. Spadina Station lower tunnel (TTC) — enclosure trap
9. Bloor-Yonge platforms (TTC) — platform edge + erratic behavior
10. City Centre Transit Terminal after 22:00 (MiWay) — desolation + harassment
11. Goreway & Derry industrial stops (MiWay) — no infrastructure, dark
12. Bramalea Terminal after dark (Brampton) — no security
13. Züm 502 Main nighttime (Brampton) — overcrowding
14. Richmond Hill Centre Terminal after 23:00 (YRT) — terminal desolation

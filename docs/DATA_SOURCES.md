# Data Sources

All open data, zero PII.

## GTFS Feeds (transit stop locations + schedules)

| System | URL | Licence |
|---|---|---|
| TTC | https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/ttc-routes-and-schedules | Open Government |
| MiWay | https://www.miway.ca/gtfs/google_transit.zip | Open Government |
| Brampton Transit | https://www.brampton.ca/EN/City-Hall/OpenGov/Open-Data-Catalogue/Documents/Google_Transit.zip | Open Government |
| YRT | https://www.yrt.ca/en/about-us/resources/google_transit.zip | Open Government |
| Halton Transit | https://www.halton.ca/Repository/Google_Transit.zip | Open Government |

## Toronto Open Data (open.toronto.ca)

| Dataset | Resource ID | What it gives |
|---|---|---|
| Toronto Police Major Crime Indicators | TBD — find at open.toronto.ca | Assault/harassment geocoded |
| Street Lighting | TBD | Light point locations |
| 311 Service Requests | TBD | Disorder signals (needles, graffiti, broken lights) |
| TTC Ridership by Stop | TBD | Co-presence proxy |

**To find resource IDs:** go to open.toronto.ca → search dataset → click API → copy `resource_id`

## Ontario Open Data

| Dataset | URL | What it gives |
|---|---|---|
| AGCO Licensed Premises | https://data.ontario.ca/dataset/liquor-sales-licence | Alcohol outlet density |

## OpenStreetMap

Download Toronto extract from Geofabrik (do NOT query Overpass API live — rate limits):
```
https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf
```
Filter to Toronto bounding box: `-79.6394, 43.5781, -79.1163, 43.8554`

Tags needed:
- `amenity=*` (restaurants, bars, convenience stores)
- `opening_hours=*` (night-open businesses)
- `highway=footway` (pedestrian paths)
- `lit=*` (streetlight tags)
- `building=*` (footprints for sightline calc)

## Statistics Canada

| Dataset | URL | What it gives |
|---|---|---|
| 2021 Census — Income by CT | https://www12.statcan.gc.ca/census-recensement/2021 | Income decile by neighborhood (equity layer only — NOT in safety score) |

## Real-Time (stretch)

| Dataset | URL | What it gives |
|---|---|---|
| TTC GTFS-RT | https://bustime.ttc.ca/api/where/vehicles-for-route.json | Live bus positions → bunching detection |

## Data Vintage

All datasets pinned to pull date. Document in pipeline output:
```python
PULL_DATE = "2026-05-15"  # update when re-pulling
```

from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"

# H3 resolution — ~150m hex edge
H3_RESOLUTION = 9

# Spatial buffer rings (metres)
BUFFER_INNER = 50    # lighting, sightline
BUFFER_MID = 200     # eyes-on-street, alcohol outlets, 311
BUFFER_OUTER = 500   # crime density, ridership

# Time bins (hour ranges, 24h)
TIME_BINS = {
    "evening":   (18, 21),
    "night":     (21, 0),
    "late_night": (0, 3),
    "pre_dawn":  (3, 6),
}

DAY_TYPES = ["weekday", "fri_sat", "sunday"]
SEASONS = ["winter", "summer"]

# Transit systems in scope
SYSTEMS = ["ttc", "miway", "brampton", "yrt", "halton"]

# GTFS feed URLs — re-resolved 2026-05-17.
# TTC verified via CKAN package_show. Regional feeds (miway/brampton/yrt/halton)
# disabled: upstream URLs in DATA_SOURCES.md returned 404/502/cloudflare-blocked.
# SDLC FR-001 only requires TTC. Regional re-enable is a downstream task.
GTFS_URLS = {
    "ttc": "https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/7795b45e-e65a-4465-81fc-c36b9dfff169/resource/cfb6b2b8-6191-41e3-bda1-b175c51148cb/download/opendata_ttc_schedules.zip",
}

# Disabled regional feeds — known broken URLs (record as blocker).
GTFS_URLS_DISABLED = {
    "miway":    "https://www.miway.ca/gtfs/google_transit.zip",        # 0-byte / hotlink-blocked
    "brampton": "https://www.brampton.ca/EN/City-Hall/OpenGov/Open-Data-Catalogue/Documents/Google_Transit.zip",  # 404
    "yrt":      "https://www.yrt.ca/en/about-us/resources/google_transit.zip",  # 502
    "halton":   "https://www.halton.ca/Repository/Google_Transit.zip", # 404
}

# Toronto Open Data — CKAN API + datastore dump endpoints
TORONTO_CKAN_BASE = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
TORONTO_DATASTORE_DUMP = TORONTO_CKAN_BASE + "/datastore/dump/{resource_id}?bom=true"
TORONTO_RESOURCE_SHOW = TORONTO_CKAN_BASE + "/api/3/action/resource_show?id={resource_id}"

# Toronto Open Data resources — verified 2026-05-17 via CKAN package_search
TORONTO_RESOURCES = {
    "major-crime-indicators.csv": {
        "resource_id": "8084057c-b2da-486c-b517-38f4e314b820",
        # MCI is not datastore-active — must fetch via resource_show -> file URL.
        "kind": "ckan_file",
        "dataset": "Community Safety Indicators (MCI)",
    },
    "311-service-requests-2025.zip": {
        "resource_id": "f3db05ab-2588-4159-89f7-56c74d1d8201",
        "kind": "ckan_file",
        "dataset": "311 Service Requests - Customer Initiated (2025)",
    },
    "311-service-requests-2024.zip": {
        "resource_id": "f46b640d-d465-4f8b-9db5-5000a08295cd",
        "kind": "ckan_file",
        "dataset": "311 Service Requests - Customer Initiated (2024)",
    },
    "topographic-poles.csv": {
        "resource_id": "5ce5f150-f0be-4417-af94-d531594d61f4",
        "kind": "ckan_file",
        "dataset": "Topographic Mapping - Poles (street-lighting proxy)",
    },
}

# OSM extract — Geofabrik Ontario PBF (~400 MB)
OSM_PBF_URL = "https://download.geofabrik.de/north-america/canada/ontario-latest.osm.pbf"
OSM_PBF_FILENAME = "ontario-latest.osm.pbf"

# Toronto bounding box for OSM clip: minLon, minLat, maxLon, maxLat
TORONTO_BBOX = (-79.6394, 43.5781, -79.1163, 43.8554)

# HTTP defaults
HTTP_USER_AGENT = "STARSAI-Pipeline/0.1 (Transit Data Challenge 2026; contact: jasdishsingh55@gmail.com)"
HTTP_TIMEOUT_SECONDS = 300
HTTP_RETRY_TOTAL = 5
HTTP_RETRY_BACKOFF = 1.5

# GTFS files required for valid feed
GTFS_REQUIRED_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "calendar.txt")

PULL_DATE = "2026-05-17"

# Validation stops — must score bottom quartile or model is wrong
VALIDATION_STOPS = [
    {"name": "Dundas & Hurontario (MiWay)", "lat": 43.5890, "lon": -79.6441, "system": "miway"},
    {"name": "Christie Station (TTC)", "lat": 43.6648, "lon": -79.4218, "system": "ttc"},
    {"name": "Islington & Eglinton W (TTC)", "lat": 43.6472, "lon": -79.5262, "system": "ttc"},
    {"name": "Dundas & Sherbourne (TTC)", "lat": 43.6558, "lon": -79.3717, "system": "ttc"},
    {"name": "Spadina Station lower tunnel (TTC)", "lat": 43.6675, "lon": -79.4040, "system": "ttc"},
    {"name": "Bloor-Yonge Station (TTC)", "lat": 43.6712, "lon": -79.3857, "system": "ttc"},
    {"name": "City Centre Transit Terminal after 22:00 (MiWay)", "lat": 43.5933, "lon": -79.6418, "system": "miway"},
    {"name": "Goreway & Derry industrial stops (MiWay)", "lat": 43.7023, "lon": -79.6301, "system": "miway"},
    {"name": "Bramalea Terminal (Brampton)", "lat": 43.7315, "lon": -79.6923, "system": "brampton"},
    {"name": "Zum 502 Main nighttime (Brampton)", "lat": 43.6851, "lon": -79.7600, "system": "brampton"},
    {"name": "Finch Station YRT connector (YRT)", "lat": 43.7800, "lon": -79.4147, "system": "yrt"},
    {"name": "Richmond Hill Centre Terminal (YRT)", "lat": 43.8720, "lon": -79.4284, "system": "yrt"},
    {"name": "Route 30 corridor (Brampton)", "lat": 43.7315, "lon": -79.7600, "system": "brampton"},
    {"name": "Milton Ontario St stops after 20:00 (Halton)", "lat": 43.5183, "lon": -79.8774, "system": "halton"},
]

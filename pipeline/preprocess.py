"""Step 2 — Strip raw downloads to factor-essential columns; write data/bronze/*.parquet.

Per SDLC §4.2 (ingest -> bronze) and §5.1 (factor catalogue), keep only what factors need.
Downstream (clean/silver, transform/gold) handles CRS normalize, dedupe, joins.

Outputs (data/bronze/):
  stops.parquet               — unified GTFS stops across 5 systems
  stop_times.parquet          — for wait-exposure (FR-012)
  trips.parquet, routes.parquet, calendar.parquet  (per-system, system-prefixed)
  crime_night.parquet         — MCI filtered to night hours, last 36 months (FR-009)
  service311.parquet          — 311 disorder categories, last 12 months (FR-016)
  lighting_poles.parquet      — pole points (FR-008 proxy)
  osm/toronto.osm.pbf         — Ontario PBF clipped to Toronto bbox (FR-004 input)

Run after ingest.py.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from config import (
    DATA_PROCESSED,
    DATA_RAW,
    GTFS_URLS,
    OSM_PBF_FILENAME,
    PULL_DATE,
    SYSTEMS,
    TIME_BINS,
    TORONTO_BBOX,
    TORONTO_RESOURCES,
)

BRONZE = DATA_PROCESSED.parent / "bronze"
BRONZE.mkdir(parents=True, exist_ok=True)
(BRONZE / "osm").mkdir(parents=True, exist_ok=True)

PULL = datetime.fromisoformat(PULL_DATE).replace(tzinfo=timezone.utc)
NIGHT_HOURS = {21, 22, 23, 0, 1, 2, 3}  # per TIME_BINS evening->pre_dawn, FR-002

DISORDER_311_KEYWORDS = (
    "graffiti", "noise", "drug", "needle", "syringe", "dumping",
    "encampment", "vandalism", "litter", "human waste",
)


def _find_col(df: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
    cols_l = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in cols_l:
            return cols_l[c.lower()]
    return None


# ---------- GTFS ----------

GTFS_STOP_COLS = ("stop_id", "stop_code", "stop_name", "stop_lat", "stop_lon",
                  "location_type", "parent_station", "wheelchair_boarding")
GTFS_STOP_TIMES_COLS = ("trip_id", "arrival_time", "departure_time", "stop_id",
                       "stop_sequence", "pickup_type", "drop_off_type")
GTFS_TRIPS_COLS = ("route_id", "service_id", "trip_id", "direction_id",
                  "shape_id", "trip_headsign")
GTFS_ROUTES_COLS = ("route_id", "route_short_name", "route_long_name",
                   "route_type", "agency_id")
GTFS_CALENDAR_COLS = ("service_id", "monday", "tuesday", "wednesday",
                     "thursday", "friday", "saturday", "sunday",
                     "start_date", "end_date")


def _read_gtfs_csv(path: Path, keep_cols: tuple[str, ...]) -> pd.DataFrame | None:
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path, dtype=str, low_memory=False, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(path, dtype=str, low_memory=False, encoding="latin-1")
    keep = [c for c in keep_cols if c in df.columns]
    return df[keep]


def preprocess_gtfs() -> dict[str, int]:
    counts: dict[str, int] = {}
    stops_frames, st_frames, trips_frames, routes_frames, cal_frames = [], [], [], [], []

    for system in GTFS_URLS:
        d = DATA_RAW / "gtfs" / system
        if not d.exists():
            print(f"[SKIP gtfs] {system} not downloaded")
            continue

        stops = _read_gtfs_csv(d / "stops.txt", GTFS_STOP_COLS)
        if stops is not None and not stops.empty:
            stops["stop_lat"] = pd.to_numeric(stops["stop_lat"], errors="coerce")
            stops["stop_lon"] = pd.to_numeric(stops["stop_lon"], errors="coerce")
            stops = stops.dropna(subset=["stop_lat", "stop_lon"])
            stops["system"] = system
            stops["uid"] = system + ":" + stops["stop_id"].astype(str)
            stops_frames.append(stops)
            counts[f"gtfs/{system}/stops"] = len(stops)

        st = _read_gtfs_csv(d / "stop_times.txt", GTFS_STOP_TIMES_COLS)
        if st is not None and not st.empty:
            st["system"] = system
            st_frames.append(st)
            counts[f"gtfs/{system}/stop_times"] = len(st)

        trips = _read_gtfs_csv(d / "trips.txt", GTFS_TRIPS_COLS)
        if trips is not None and not trips.empty:
            trips["system"] = system
            trips_frames.append(trips)

        routes = _read_gtfs_csv(d / "routes.txt", GTFS_ROUTES_COLS)
        if routes is not None and not routes.empty:
            routes["system"] = system
            routes_frames.append(routes)

        cal = _read_gtfs_csv(d / "calendar.txt", GTFS_CALENDAR_COLS)
        if cal is not None and not cal.empty:
            cal["system"] = system
            cal_frames.append(cal)

    if stops_frames:
        out = pd.concat(stops_frames, ignore_index=True)
        out.to_parquet(BRONZE / "stops.parquet", index=False)
        counts["bronze/stops"] = len(out)
    if st_frames:
        out = pd.concat(st_frames, ignore_index=True)
        out.to_parquet(BRONZE / "stop_times.parquet", index=False)
        counts["bronze/stop_times"] = len(out)
    if trips_frames:
        pd.concat(trips_frames, ignore_index=True).to_parquet(
            BRONZE / "trips.parquet", index=False)
    if routes_frames:
        pd.concat(routes_frames, ignore_index=True).to_parquet(
            BRONZE / "routes.parquet", index=False)
    if cal_frames:
        pd.concat(cal_frames, ignore_index=True).to_parquet(
            BRONZE / "calendar.parquet", index=False)

    return counts


# ---------- Toronto MCI (crime) ----------

def preprocess_mci() -> int:
    src = DATA_RAW / "toronto" / "major-crime-indicators.csv"
    if not src.exists():
        print("[SKIP mci] missing")
        return 0
    df = pd.read_csv(src, low_memory=False)

    date_col = _find_col(df, ("OCC_DATE", "occurrencedate", "OCC_DATETIME"))
    hour_col = _find_col(df, ("OCC_HOUR", "occurrencehour"))
    mci_col = _find_col(df, ("MCI_CATEGORY", "mci_category"))
    off_col = _find_col(df, ("OFFENCE", "offence"))
    lat_col = _find_col(df, ("LAT_WGS84", "Latitude", "lat", "latitude"))
    lon_col = _find_col(df, ("LONG_WGS84", "Longitude", "lon", "long", "longitude"))
    id_col = _find_col(df, ("EVENT_UNIQUE_ID", "event_unique_id", "_id"))

    if not all((date_col, hour_col, mci_col, lat_col, lon_col)):
        print(f"[FAIL mci] missing cols. have: {list(df.columns)[:25]}")
        return 0

    keep = {
        "event_id": df[id_col] if id_col else range(len(df)),
        "occ_date": pd.to_datetime(df[date_col], errors="coerce", utc=True),
        "occ_hour": pd.to_numeric(df[hour_col], errors="coerce"),
        "mci_category": df[mci_col].astype(str),
        "offence": df[off_col].astype(str) if off_col else "",
        "lat": pd.to_numeric(df[lat_col], errors="coerce"),
        "lon": pd.to_numeric(df[lon_col], errors="coerce"),
    }
    out = pd.DataFrame(keep)
    cutoff = PULL - timedelta(days=365 * 3)  # 36 months
    out = out[
        out["occ_hour"].isin(NIGHT_HOURS)
        & out["occ_date"].ge(cutoff)
        & out["lat"].notna() & out["lon"].notna()
        & out["lat"].between(43.55, 43.90) & out["lon"].between(-79.70, -79.10)
    ]
    out.to_parquet(BRONZE / "crime_night.parquet", index=False)
    return len(out)


# ---------- Toronto 311 ----------

def _read_311_zip(zip_path: Path) -> pd.DataFrame | None:
    """311 CSVs have variable column counts across years; use python engine
    + skip bad lines + tolerant encoding."""
    try:
        with zipfile.ZipFile(zip_path) as z:
            csvs = [n for n in z.namelist() if n.lower().endswith(".csv")]
            if not csvs:
                return None
            frames = []
            for name in csvs:
                data = z.read(name)
                for enc in ("utf-8", "utf-8-sig", "latin-1"):
                    try:
                        df = pd.read_csv(
                            io.BytesIO(data),
                            engine="python",
                            encoding=enc,
                            on_bad_lines="skip",
                            quoting=0,  # QUOTE_MINIMAL
                            sep=",",
                        )
                        frames.append(df)
                        break
                    except (UnicodeDecodeError, pd.errors.ParserError):
                        continue
            return pd.concat(frames, ignore_index=True) if frames else None
    except zipfile.BadZipFile:
        return None


def preprocess_311() -> int:
    frames = []
    for fname in ("311-service-requests-2025.zip", "311-service-requests-2024.zip"):
        src = DATA_RAW / "toronto" / fname
        if not src.exists():
            continue
        df = _read_311_zip(src)
        if df is None or df.empty:
            continue
        frames.append(df)
    if not frames:
        print("[SKIP 311] none readable")
        return 0
    df = pd.concat(frames, ignore_index=True)

    date_col = _find_col(df, ("Creation Date", "Created Date", "creation_date", "Created"))
    type_col = _find_col(df, ("Service Request Type", "service_request_type", "Description"))
    lat_col = _find_col(df, ("Latitude", "Lat", "lat", "latitude"))
    lon_col = _find_col(df, ("Longitude", "Long", "lon", "longitude"))

    if not all((date_col, type_col)):
        print(f"[FAIL 311] missing cols. have: {list(df.columns)[:25]}")
        return 0

    out = pd.DataFrame({
        "created_date": pd.to_datetime(df[date_col], errors="coerce", utc=True),
        "request_type": df[type_col].astype(str),
        "lat": pd.to_numeric(df[lat_col], errors="coerce") if lat_col else pd.NA,
        "lon": pd.to_numeric(df[lon_col], errors="coerce") if lon_col else pd.NA,
        "ward": df[_find_col(df, ("Ward", "ward"))] if _find_col(df, ("Ward", "ward")) else pd.NA,
        "postal_fsa": df[_find_col(df, ("First 3 Chars of Postal Code", "FSA", "fsa"))]
                       if _find_col(df, ("First 3 Chars of Postal Code", "FSA", "fsa")) else pd.NA,
    })

    cutoff = PULL - timedelta(days=365)  # last 12 months
    rt_lower = out["request_type"].str.lower().fillna("")
    disorder_mask = rt_lower.apply(lambda s: any(k in s for k in DISORDER_311_KEYWORDS))
    out = out[out["created_date"].ge(cutoff) & disorder_mask]
    out.to_parquet(BRONZE / "service311.parquet", index=False)
    return len(out)


# ---------- Lighting poles ----------

def preprocess_poles() -> int:
    src = DATA_RAW / "toronto" / "topographic-poles.csv"
    if not src.exists():
        print("[SKIP poles] missing")
        return 0

    # Some Toronto topographic files are GeoJSON-in-CSV (geometry col).
    # Try CSV first; if it parses as GeoJSON, fall back.
    try:
        df = pd.read_csv(src, low_memory=False)
    except Exception as e:
        print(f"[FAIL poles] read csv: {e}")
        return 0

    lat_col = _find_col(df, ("Latitude", "lat", "y", "Y"))
    lon_col = _find_col(df, ("Longitude", "lon", "x", "X", "long"))
    geom_col = _find_col(df, ("geometry", "the_geom"))
    type_col = _find_col(df, ("SUBTYPE_DESC", "FEATURE_CODE_DESC", "FEATURE_CODE",
                             "TYPE", "POLE_TYPE", "feature_code_desc", "pole_type"))

    lats: pd.Series
    lons: pd.Series
    if lat_col and lon_col:
        lats = pd.to_numeric(df[lat_col], errors="coerce")
        lons = pd.to_numeric(df[lon_col], errors="coerce")
    elif geom_col:
        def _xy(s: str) -> tuple[float, float]:
            try:
                g = json.loads(s)
                coords = g.get("coordinates")
                if g.get("type") == "Point" and coords:
                    x, y = coords[:2]
                    return float(y), float(x)
                if g.get("type") == "MultiPoint" and coords:
                    x, y = coords[0][:2]
                    return float(y), float(x)
            except Exception:
                pass
            return float("nan"), float("nan")
        xy = df[geom_col].astype(str).map(_xy)
        lats = xy.map(lambda t: t[0])
        lons = xy.map(lambda t: t[1])
    else:
        print(f"[FAIL poles] no geometry. have: {list(df.columns)[:25]}")
        return 0

    out = pd.DataFrame({
        "lat": lats,
        "lon": lons,
        "feature_type": df[type_col].astype(str) if type_col else "POLE",
    })
    out = out.dropna(subset=["lat", "lon"])
    out = out[out["lat"].between(43.55, 43.90) & out["lon"].between(-79.70, -79.10)]
    # SDLC: street-lighting proxy — keep poles likely to carry lights
    if type_col:
        mask = out["feature_type"].str.contains(
            "LIGHT|LAMP|STREET|UTIL|HYDRO", case=False, na=True)
        light_subset = out[mask]
        if len(light_subset) > 0:
            out = light_subset
    out.to_parquet(BRONZE / "lighting_poles.parquet", index=False)
    return len(out)


# ---------- OSM PBF clip to Toronto bbox ----------

def clip_osm_to_toronto() -> int:
    src = DATA_RAW / "osm" / OSM_PBF_FILENAME
    if not src.exists():
        print("[SKIP osm] PBF missing")
        return 0
    dest = BRONZE / "osm" / "toronto.osm.pbf"
    if dest.exists() and dest.stat().st_size > (1 << 20):
        print(f"[SKIP osm clip] exists ({dest.stat().st_size/(1<<20):.0f} MB)")
        return dest.stat().st_size

    try:
        import osmium
    except ImportError:
        print("[FAIL osm] osmium not installed")
        return 0

    minlon, minlat, maxlon, maxlat = TORONTO_BBOX
    # osmium 4.x BBox filter via FileProcessor + handler
    try:
        # Geographic bounding box filter using osmium SimpleHandler is heavy;
        # use osmium.io with NodeLocationsForWays + region filter.
        from osmium import SimpleWriter
        from osmium.osm import Box
        bbox = (minlon, minlat, maxlon, maxlat)

        class BoxFilter(osmium.SimpleHandler):
            def __init__(self, writer, box):
                super().__init__()
                self.w = writer
                self.minlon, self.minlat, self.maxlon, self.maxlat = box
                self.n = self.wcount = self.r = 0

            def node(self, n):
                if n.location.valid():
                    lon, lat = n.location.lon, n.location.lat
                    if self.minlon <= lon <= self.maxlon and self.minlat <= lat <= self.maxlat:
                        self.w.add_node(n)
                        self.n += 1

            def way(self, w):
                # Pass all ways; downstream can filter by node membership.
                self.w.add_way(w)
                self.wcount += 1

            def relation(self, r):
                self.w.add_relation(r)
                self.r += 1

        writer = SimpleWriter(str(dest))
        handler = BoxFilter(writer, bbox)
        handler.apply_file(str(src), locations=False)
        writer.close()
        return dest.stat().st_size
    except Exception as e:
        print(f"[FAIL osm clip] {e}")
        if dest.exists():
            dest.unlink()
        return 0


# ---------- Driver ----------

def main() -> int:
    print(f"=== PREPROCESS start (pull_date={PULL_DATE}) ===")
    summary: dict[str, int] = {}

    summary.update(preprocess_gtfs())
    summary["bronze/crime_night"] = preprocess_mci()
    summary["bronze/service311"] = preprocess_311()
    summary["bronze/lighting_poles"] = preprocess_poles()
    summary["bronze/osm_bytes"] = clip_osm_to_toronto()

    print("\n=== PREPROCESS summary ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pull_date": PULL_DATE,
        "rows": {k: int(v) for k, v in summary.items() if isinstance(v, (int, float))},
    }
    (BRONZE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nBronze manifest: {BRONZE / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

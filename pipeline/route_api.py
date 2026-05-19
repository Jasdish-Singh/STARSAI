"""FastAPI route planner for STARSAI safe routing.

POST /api/route  — plan safest path between two stops
GET  /api/health — health check

Concurrency-safe: graph is read-only, all per-request danger lookups go
through closure-captured dicts. No shared mutation, no per-request iterrows.

Usage:
    uvicorn route_api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent.parent
GRAPHML = ROOT / "data" / "route" / "toronto_street.graphml"
EDGE_WEIGHTS_PATH = ROOT / "data" / "route" / "edge_weights.parquet"
STOP_NODES_PATH = ROOT / "data" / "route" / "stop_nodes.parquet"
SCORES_DYNAMIC_PATH = ROOT / "data" / "scores" / "scores_dynamic.parquet"

# Lazy-loaded immutables — populated once by _init()
_G = None
_edge_meta: dict = {}      # (u, v) -> (length_m, nearest_stop_uid)
_dyn_scores: dict = {}     # (hour, day_type) -> {uid: t_ntsi_score}
_stops = None
_stop_tree = None
_stop_names = None

app = FastAPI(title="STARSAI Route Planner", version="0.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


class RouteRequest(BaseModel):
    origin: str = Field(..., description="Origin stop name (substring match)")
    destination: str = Field(..., description="Destination stop name (substring match)")
    alpha: float = Field(2.0, description="Safety weight. Higher = avoid danger more")
    time: str = Field("23:00", description="Time of travel (HH:MM)")
    day_type: str = Field("sat", description="weekday, fri, sat, sun")


class SegmentOut(BaseModel):
    from_: str = Field(..., alias="from")
    to: str = Field(...)
    length_m: float
    danger: float
    score: float

    class Config:
        populate_by_name = True


class RouteResponse(BaseModel):
    route: dict[str, Any]
    stops_along: list[dict[str, Any]]
    segments: list[SegmentOut]
    overall_score: float
    total_length_km: float
    walking_time_min: float


def _init() -> None:
    """Load graph + build per-bin score dicts + edge meta dict + BallTree. Idempotent."""
    global _G, _edge_meta, _dyn_scores, _stops, _stop_tree, _stop_names
    if _G is not None:
        return

    import networkx as nx
    import numpy as np
    import pandas as pd
    from sklearn.neighbors import BallTree

    _G = nx.read_graphml(str(GRAPHML), node_type=int)
    if _G.is_directed():
        _G = _G.to_undirected()

    ew = pd.read_parquet(EDGE_WEIGHTS_PATH)
    ew["nearest_stop_uid"] = ew["nearest_stop_uid"].astype(str)
    _edge_meta = {
        (int(u), int(v)): (float(l), s)
        for u, v, l, s in ew[["u", "v", "length_m", "nearest_stop_uid"]].itertuples(
            index=False, name=None
        )
    }

    _stops = pd.read_parquet(STOP_NODES_PATH)

    dyn = pd.read_parquet(SCORES_DYNAMIC_PATH)
    dyn["uid"] = dyn["uid"].astype(str)
    _dyn_scores = {
        (int(h), str(dt)): dict(zip(g["uid"], g["t_ntsi_score"].astype(float)))
        for (h, dt), g in dyn.groupby(["hour", "day_type"])
    }

    coords = np.radians(_stops[["stop_lat", "stop_lon"]].to_numpy(dtype=np.float64))
    _stop_tree = BallTree(coords, metric="haversine")
    _stop_names = _stops["stop_name"].to_numpy()


def _nearest_stop_fn(lat: float, lon: float) -> str:
    import numpy as np
    _, idx = _stop_tree.query(np.radians([[lat, lon]]), k=1)
    return str(_stop_names[idx[0, 0]])


def _snap_hour(hour: int, day_type: str) -> int:
    """Find nearest available hour for (hour, day_type) — labels skip daytime hours."""
    avail = sorted(h for (h, dt) in _dyn_scores if dt == day_type)
    if not avail or hour in avail:
        return hour
    return min(avail, key=lambda h: min(abs(h - hour), 24 - abs(h - hour)))


def _make_weight_fn(alpha: float, hour: int, day_type: str):
    """Return per-edge cost callable for nx.astar_path. Closure-isolated per request."""
    from route_planner import _circadian
    eff_hour = _snap_hour(hour, day_type)
    bin_scores = _dyn_scores.get((eff_hour, day_type), {})
    mult = _circadian(hour, day_type)  # boost uses ORIGINAL hour, not snapped
    edge_meta = _edge_meta

    def w(u, v, _data):
        meta = edge_meta.get((u, v)) or edge_meta.get((v, u))
        if meta is None:
            return 1e9
        length, stop_uid = meta
        score = bin_scores.get(stop_uid, 50.0)
        danger = min(1.0, ((100.0 - score) / 100.0) * mult)
        return length * (1.0 + alpha * danger)
    return w


def _make_meta_fn(hour: int, day_type: str):
    """Return (u,v) -> (length_m, danger) for route_to_geojson — same closure as weight_fn."""
    from route_planner import _circadian
    eff_hour = _snap_hour(hour, day_type)
    bin_scores = _dyn_scores.get((eff_hour, day_type), {})
    mult = _circadian(hour, day_type)
    edge_meta = _edge_meta

    def m(u, v):
        meta = edge_meta.get((u, v)) or edge_meta.get((v, u))
        if meta is None:
            return 0.0, 0.0
        length, stop_uid = meta
        score = bin_scores.get(stop_uid, 50.0)
        danger = min(1.0, ((100.0 - score) / 100.0) * mult)
        return length, danger
    return m


@app.post("/api/route", response_model=RouteResponse)
def plan_route(body: RouteRequest) -> RouteResponse:
    from route_planner import safe_route, route_to_geojson, find_stop_node

    _init()

    alpha = body.alpha
    try:
        hour = int(body.time.split(":")[0])
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail=f"Invalid time format: {body.time!r}, expected HH:MM")
    day_type = body.day_type

    weight_fn = _make_weight_fn(alpha, hour, day_type)
    meta_fn = _make_meta_fn(hour, day_type)

    origin_node = find_stop_node(_stops, body.origin)
    dest_node = find_stop_node(_stops, body.destination)
    if origin_node is None:
        raise HTTPException(status_code=404, detail=f"Origin stop not found: {body.origin}")
    if dest_node is None:
        raise HTTPException(status_code=404, detail=f"Destination stop not found: {body.destination}")

    path = safe_route(_G, origin_node, dest_node, weight=weight_fn)
    geojson = route_to_geojson(path, _G, stops=_stops,
                               meta_fn=meta_fn, nearest_fn=_nearest_stop_fn)

    total_len = geojson["properties"]["total_length_m"]
    score = geojson["properties"]["overall_safety_score"]

    segments = []
    for f in geojson["features"]:
        p = f["properties"]
        seg_idx = p["segment"]
        segments.append(SegmentOut(
            from_=p.get("nearest_stop") or str(path[seg_idx - 1]),
            to=p.get("nearest_stop") or str(path[seg_idx]),
            length_m=p["length_m"],
            danger=p["danger_score"],
            score=round(100 / (1 + p["danger_score"]), 1),
        ))

    return RouteResponse(
        route=geojson,
        stops_along=[{"node": n} for n in path],
        segments=segments,
        overall_score=score,
        total_length_km=round(total_len / 1000, 2),
        walking_time_min=round(total_len / 83.33, 1),  # 5 km/h
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def _startup() -> None:
    """Eager-init at server boot so first request isn't cold."""
    _init()

"""Route planner — A* shortest-safe path on TTC street graph.

Reads OSMnx graph + edge danger weights, finds safe routes between stops
via weighted A* (edge weight = composite safety cost). Outputs GeoJSON.

D1 — circadian risk multiplier inflates danger 1.0-2.1x by hour-of-day +
0.95-1.25x by day_type. Keeps A* heuristic admissible (haversine in metres
remains <= length * (1 + alpha*danger) for alpha >= 0, danger >= 0).

B3 — single BallTree singleton replaces per-segment O(N) nearest-stop scan.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Callable

import networkx as nx
import numpy as np
import pandas as pd

ROOT = Path(__file__).parent.parent
GRAPHML = ROOT / "data" / "route" / "toronto_street.graphml"
EDGE_WEIGHTS = ROOT / "data" / "route" / "edge_weights.parquet"
STOP_NODES = ROOT / "data" / "route" / "stop_nodes.parquet"
SCORES_DYNAMIC = ROOT / "data" / "scores" / "scores_dynamic.parquet"
ROUTE_OUT = ROOT / "data" / "route" / "route.geojson"
R_EARTH = 6_371_000  # metres


# ── Circadian risk amplifier ─────────────────────────────────────────────────

NIGHT_BOOST = {h: 1.0 for h in range(24)}
for _h, _b in [(20, 1.15), (21, 1.30), (22, 1.50), (23, 1.70), (0, 1.90),
               (1, 2.00), (2, 2.10), (3, 2.00), (4, 1.70), (5, 1.40), (6, 1.15)]:
    NIGHT_BOOST[_h] = _b

DAY_TYPE_BOOST = {"weekday": 1.0, "fri": 1.15, "sat": 1.25, "sun": 0.95}


def _circadian(hour: int | None, day_type: str | None) -> float:
    """Risk multiplier for (hour, day_type). 1.0 = neutral, >1 = riskier window."""
    if hour is None:
        return 1.0
    return NIGHT_BOOST.get(int(hour), 1.0) * DAY_TYPE_BOOST.get(day_type, 1.0)


_SNAP_CACHE: dict = {}


def _snap_hour(hour: int, dyn: pd.DataFrame) -> int:
    """Return nearest available hour in dyn['hour'] to *hour* (wrap-around on 24h clock).

    Labels cover only night-relevant hours (0-8, 17-23); daytime queries snap to
    closest covered hour rather than silently flatlining at neutral 50.
    """
    cache_key = id(dyn)
    if cache_key not in _SNAP_CACHE:
        _SNAP_CACHE[cache_key] = sorted(int(h) for h in dyn["hour"].unique())
    available = _SNAP_CACHE[cache_key]
    if hour in available:
        return hour
    return min(available, key=lambda h: min(abs(h - hour), 24 - abs(h - hour)))


# ── Geometry ────────────────────────────────────────────────────────────────

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R_EARTH * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Loaders ──────────────────────────────────────────────────────────────────

def load_graph() -> nx.MultiGraph:
    """Load OSMnx street graph from GraphML, convert to undirected."""
    G = nx.read_graphml(str(GRAPHML), node_type=int)
    if G.is_directed():
        G = G.to_undirected()
    return G


def attach_edge_weights(
    G: nx.MultiGraph, df: pd.DataFrame, alpha: float = 2.0,
    hour: int | None = None, day_type: str | None = None,
) -> None:
    """Set weight = length * (1 + alpha * danger) on every edge, vectorized.

    Dynamic path: looks up nearest_stop_uid -> per-bin t_ntsi_score from
    scores_dynamic.parquet, applies circadian multiplier, never silently
    defaults (warns if uids miss).

    Static fallback: uses df["danger"] column verbatim.
    """
    if hour is not None and day_type is not None and "nearest_stop_uid" in df.columns:
        dyn = pd.read_parquet(SCORES_DYNAMIC)
        dyn["uid"] = dyn["uid"].astype(str)
        eff_hour = _snap_hour(int(hour), dyn)
        if eff_hour != int(hour):
            print(f"[info] hour={hour} absent from labels — snapped to nearest available hour={eff_hour}",
                  file=sys.stderr)
        bin_scores = dyn[(dyn["hour"] == eff_hour) & (dyn["day_type"] == day_type)]
        score_map = dict(zip(bin_scores["uid"], bin_scores["t_ntsi_score"].astype(float)))

        uid_series = df["nearest_stop_uid"].astype(str)
        scores = uid_series.map(score_map)
        miss = int(scores.isna().sum())
        if miss:
            print(f"[warn] {miss}/{len(df)} edges missing in scores_dynamic"
                  f" (hour={eff_hour}, day_type={day_type}) — using neutral 50.0",
                  file=sys.stderr)
        scores = scores.fillna(50.0).to_numpy(dtype=float)
        mult = _circadian(hour, day_type)
        d = np.clip(((100.0 - scores) / 100.0) * mult, 0.0, 1.0)
    else:
        d = df["danger"].to_numpy(dtype=float)

    lengths = df["length_m"].to_numpy(dtype=float)
    weights = lengths * (1.0 + alpha * d)
    u_arr = df["u"].to_numpy(dtype=np.int64)
    v_arr = df["v"].to_numpy(dtype=np.int64)

    is_multi = G.is_multigraph()
    attr_updates: dict = {}
    for i in range(len(df)):
        u, v = int(u_arr[i]), int(v_arr[i])
        if not G.has_edge(u, v):
            continue
        rec = {"weight": float(weights[i]),
               "danger": float(d[i]),
               "length_m": float(lengths[i])}
        if is_multi:
            for key in G[u][v]:
                attr_updates[(u, v, key)] = rec
        else:
            attr_updates[(u, v)] = rec

    nx.set_edge_attributes(G, attr_updates)


def load_stops() -> pd.DataFrame:
    return pd.read_parquet(STOP_NODES)


def find_stop_node(stops: pd.DataFrame, name: str) -> int | None:
    """Return graph_node_id of first stop matching *name* (case-insensitive substring)."""
    hits = stops[stops["stop_name"].str.contains(name, case=False, na=False)]
    return int(hits.iloc[0]["graph_node_id"]) if len(hits) else None


# ── A* routing ──────────────────────────────────────────────────────────────

def make_heuristic(G: nx.MultiGraph, dest: int):
    """Admissible A* heuristic: haversine distance to *dest* node (metres).

    Admissibility: edge cost >= length_m * 1.0 >= haversine(u,v). Therefore
    haversine(n, dest) <= true min-cost path n -> dest, for all alpha >= 0,
    danger >= 0, circadian multiplier >= 1.0.
    """
    dy = float(G.nodes[dest].get("y", 0))
    dx = float(G.nodes[dest].get("x", 0))

    def _h(n: int, _target=None) -> float:
        ny = float(G.nodes[n].get("y", 0))
        nx_ = float(G.nodes[n].get("x", 0))
        return haversine(ny, nx_, dy, dx)
    return _h


def safe_route(
    G: nx.MultiGraph, origin_node: int, dest_node: int,
    alpha: float = 2.0, hour: int | None = None, day_type: str | None = None,
    weight: str | Callable = "weight",
) -> list[int]:
    """A* shortest-safe path.

    weight: either attribute name (default "weight" — uses values attached by
    attach_edge_weights) or callable(u, v, data) -> float for caller-supplied
    per-edge cost (used by route_api to avoid mutating the shared graph).
    """
    del alpha, hour, day_type  # kept for backward-compat signature
    h = make_heuristic(G, dest_node)
    try:
        return nx.astar_path(G, origin_node, dest_node, heuristic=h, weight=weight)
    except nx.NetworkXNoPath:
        print(f"ERROR: no path between node {origin_node} and {dest_node}", file=sys.stderr)
        sys.exit(1)


# ── Nearest-stop (BallTree singleton) ────────────────────────────────────────

_stop_tree = None
_stop_names = None


def _ensure_tree(stops: pd.DataFrame) -> None:
    """Build BallTree once per process. Reused across all _nearest_stop_name calls."""
    global _stop_tree, _stop_names
    if _stop_tree is not None:
        return
    from sklearn.neighbors import BallTree
    coords = np.radians(stops[["stop_lat", "stop_lon"]].to_numpy(dtype=np.float64))
    _stop_tree = BallTree(coords, metric="haversine")
    _stop_names = stops["stop_name"].to_numpy()


def _nearest_stop_name(lat: float, lon: float, stops: pd.DataFrame | None) -> str:
    if stops is None or stops.empty:
        return ""
    _ensure_tree(stops)
    _, idx = _stop_tree.query(np.radians([[lat, lon]]), k=1)
    return str(_stop_names[idx[0, 0]])


# ── GeoJSON output ──────────────────────────────────────────────────────────

def route_to_geojson(
    path: list[int],
    G: nx.MultiGraph,
    stops: pd.DataFrame | None = None,
    meta_fn: Callable[[int, int], tuple[float, float]] | None = None,
    nearest_fn: Callable[[float, float], str] | None = None,
) -> dict:
    """Build GeoJSON FeatureCollection from path node list.

    meta_fn(u, v) -> (length_m, danger) — used by route_api to read from its
    edge_meta dict instead of graph attrs (which aren't set when using a
    weight callable).

    nearest_fn(lat, lon) -> stop_name — overrides default BallTree lookup so
    route_api can share its own preloaded tree.
    """
    features: list[dict] = []
    total_len = 0.0
    total_danger_len = 0.0

    for i in range(len(path) - 1):
        u, v = path[i], path[i + 1]
        y1, x1 = float(G.nodes[u].get("y", 0)), float(G.nodes[u].get("x", 0))
        y2, x2 = float(G.nodes[v].get("y", 0)), float(G.nodes[v].get("x", 0))

        if meta_fn is not None:
            seg_len, seg_danger = meta_fn(u, v)
            if seg_len <= 0:
                seg_len = haversine(y1, x1, y2, x2)
        else:
            edge_data = G.get_edge_data(u, v)
            if edge_data is None:
                attrs = {}
            elif G.is_multigraph():
                attrs = next(iter(edge_data.values())) if edge_data else {}
            else:
                attrs = edge_data
            seg_len = float(attrs.get("length_m", haversine(y1, x1, y2, x2)))
            seg_danger = float(attrs.get("danger", 0))

        total_len += seg_len
        total_danger_len += seg_danger * seg_len

        mid_lat, mid_lon = (y1 + y2) / 2, (x1 + x2) / 2
        if nearest_fn is not None:
            near = nearest_fn(mid_lat, mid_lon)
        else:
            near = _nearest_stop_name(mid_lat, mid_lon, stops)

        features.append({
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": [[x1, y1], [x2, y2]]},
            "properties": {
                "segment": i + 1,
                "length_m": round(seg_len, 1),
                "danger_score": round(seg_danger, 4),
                "nearest_stop": near,
            },
        })

    avg_danger = total_danger_len / total_len if total_len else 0
    overall_safety = round(100 / (1 + avg_danger), 1)

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "num_segments": len(features),
            "total_length_m": round(total_len, 1),
            "overall_safety_score": overall_safety,
        },
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="STARSAI safe route planner")
    p.add_argument("origin", help="Origin stop name (case-insensitive substring)")
    p.add_argument("dest", help="Destination stop name (case-insensitive substring)")
    p.add_argument("--alpha", type=float, default=2.0, help="Danger exponent in edge cost (default: 2.0)")
    p.add_argument("--time", type=int, default=None, help="Hour (0-23) for time-aware danger scoring")
    p.add_argument("--day-type", type=str, default=None,
                   choices=["weekday", "fri", "sat", "sun"],
                   help="Day type for time-aware danger scoring")
    return p.parse_args(argv)


def print_summary(geojson: dict, origin_name: str, dest_name: str) -> None:
    p = geojson["properties"]
    print(f"\n  Route: {origin_name} -> {dest_name}")
    print(f"  Segments:         {p['num_segments']}")
    print(f"  Total length:     {p['total_length_m']:,.1f} m")
    print(f"  Overall safety:   {p['overall_safety_score']:.1f} / 100")
    print("\n  Per-segment breakdown:")
    for f in geojson["features"]:
        pr = f["properties"]
        print(f"    #{pr['segment']:>3}  {pr['length_m']:>8.1f} m  "
              f"danger={pr['danger_score']:.4f}  near={pr['nearest_stop']}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print("Loading graph ...")
    G = load_graph()
    print(f"  {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    time_info = ""
    if args.time is not None and args.day_type is not None:
        time_info = f", time={args.time}:00 ({args.day_type})"
    print(f"Loading edge weights (alpha={args.alpha}{time_info}) ...")
    eweights = pd.read_parquet(EDGE_WEIGHTS)
    attach_edge_weights(G, eweights, alpha=args.alpha, hour=args.time, day_type=args.day_type)
    print(f"  {len(eweights):,} weighted edges")

    print("Loading stops ...")
    stops = load_stops()
    print(f"  {len(stops):,} stops")

    origin_node = find_stop_node(stops, args.origin)
    dest_node = find_stop_node(stops, args.dest)
    if origin_node is None:
        print(f"ERROR: no stop matches '{args.origin}'")
        return 1
    if dest_node is None:
        print(f"ERROR: no stop matches '{args.dest}'")
        return 1

    path = safe_route(G, origin_node, dest_node)
    print(f"  Path: {len(path)} graph nodes\n")

    geojson = route_to_geojson(path, G, stops)
    print_summary(geojson, args.origin, args.dest)

    ROUTE_OUT.parent.mkdir(parents=True, exist_ok=True)
    ROUTE_OUT.write_text(json.dumps(geojson, indent=2))
    print(f"\n  -> GeoJSON saved: {ROUTE_OUT}")
    return 0


# ── Demo & entry point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(main())

    BANNER = "STARSAI Route Planner -- Demo: Bloor Station -> Kipling Station (alpha=2.0)"
    print("=" * 70)
    print(BANNER)
    print("=" * 70)

    G = load_graph()
    eweights = pd.read_parquet(EDGE_WEIGHTS)
    attach_edge_weights(G, eweights, alpha=2.0)
    stops = load_stops()

    orig_node = find_stop_node(stops, "Bloor Station")
    dest_node = find_stop_node(stops, "Kipling Station")
    if orig_node is None:
        print("  [SKIP] 'Bloor Station' not found in stop_nodes.")
    elif dest_node is None:
        print("  [SKIP] 'Kipling Station' not found in stop_nodes.")
    else:
        path = safe_route(G, orig_node, dest_node)
        geojson = route_to_geojson(path, G, stops)
        print_summary(geojson, "Bloor Station", "Kipling Station")
        ROUTE_OUT.parent.mkdir(parents=True, exist_ok=True)
        ROUTE_OUT.write_text(json.dumps(geojson, indent=2))
        print(f"\n  -> GeoJSON saved: {ROUTE_OUT}")

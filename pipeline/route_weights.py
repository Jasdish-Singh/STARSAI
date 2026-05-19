"""Compute edge weights for STARSAI route planner (SDLC FR-018 safe routing).

Reads stop_nodes + scores + OSMnx graph, assigns each graph edge a danger score
from nearest stop, computes weighted edge cost = length * (1 + alpha * danger).

Inputs:
  data/route/stop_nodes.parquet      — stops with graph_node_id mapping
  data/scores/scores.parquet         — t_ntsi_score per stop uid
  data/route/toronto_street.graphml  — OSMnx street network

Output:
  data/route/edge_weights.parquet    — u, v, length_m, danger, weight
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ROUTE_DIR = ROOT / "data" / "route"
SCORES_PATH = ROOT / "data" / "scores" / "scores.parquet"
STOPS_PATH = ROUTE_DIR / "stop_nodes.parquet"
GRAPH_PATH = ROUTE_DIR / "toronto_street.graphml"
OUT_PATH = ROUTE_DIR / "edge_weights.parquet"

ALPHA = 2.0  # safety weight penalty multiplier
R_EARTH = 6_371_000  # metres


def _haversine(
    lat1: np.ndarray, lon1: np.ndarray,
    lat2: np.ndarray, lon2: np.ndarray,
) -> np.ndarray:
    """Element-wise haversine distance in metres."""
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return R_EARTH * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def load_scores() -> pd.DataFrame:
    """Load t_ntsi_score per stop uid."""
    return pd.read_parquet(SCORES_PATH)[["uid", "t_ntsi_score"]]


def load_stops() -> pd.DataFrame:
    """Load stop_nodes, merge with scores, keep graph-mapped stops only."""
    stops = pd.read_parquet(STOPS_PATH)
    scores = load_scores()
    merged = stops.merge(scores, on="uid", how="inner")
    if merged.empty:
        print("[FATAL] no stops matched scores — check uid alignment")
        sys.exit(1)
    return merged[["uid", "stop_lat", "stop_lon", "graph_node_id", "t_ntsi_score"]]


def load_graph_edges() -> pd.DataFrame:
    """Load OSMnx graphml, extract edges with node coords and length.

    Returns DataFrame with columns: u, v, length_m, mid_lat, mid_lon.
    """
    import networkx as nx

    G = nx.read_graphml(GRAPH_PATH, node_type=int)
    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()

    # Node coord lookup: OSMnx stores lon as x, lat as y
    lats: dict[int, float] = {}
    lons: dict[int, float] = {}
    for n, d in G.nodes(data=True):
        lats[n] = float(d.get("y", 0))
        lons[n] = float(d.get("x", 0))

    rows: list[tuple[int, int, float, float, float]] = []
    for u, v, d in G.edges(data=True):
        length = float(d.get("length", 0))
        if length <= 0:
            continue
        lat_u, lon_u = lats[u], lons[u]
        lat_v, lon_v = lats[v], lons[v]
        rows.append((u, v, length, (lat_u + lat_v) / 2, (lon_u + lon_v) / 2))

    edges = pd.DataFrame(rows, columns=["u", "v", "length_m", "mid_lat", "mid_lon"])
    print(f"Graph: {n_nodes} nodes, {n_edges} raw edges, {len(edges)} valid edges extracted")
    return edges


def nearest_stop_danger(edges: pd.DataFrame, stops: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """For each edge midpoint, find nearest stop's t_ntsi_score and uid.

    Uses BallTree (haversine) when sklearn is available, otherwise brute force.
    Returns (scores (N,), stop_uids (N,)) arrays.
    """
    mid = edges[["mid_lat", "mid_lon"]].to_numpy(dtype=np.float64)
    sc = stops[["stop_lat", "stop_lon"]].to_numpy(dtype=np.float64)
    scores_arr = stops["t_ntsi_score"].to_numpy(dtype=np.float64)
    uids_arr = stops["uid"].to_numpy(dtype=str)

    try:
        from sklearn.neighbors import BallTree

        tree = BallTree(np.radians(sc), metric="haversine")
        _, idx = tree.query(np.radians(mid), k=1)
        flat_idx = idx[:, 0]
        return scores_arr[flat_idx], uids_arr[flat_idx]
    except ImportError:
        # Chunked numpy broadcast — keeps peak RAM bounded for ~30k edges x ~9k stops
        print("  BallTree unavailable — chunked numpy brute-force")
        nearest_scores = np.empty(len(edges), dtype=np.float64)
        nearest_uids = np.empty(len(edges), dtype=object)
        CHUNK = 2000
        for start in range(0, len(edges), CHUNK):
            end = min(start + CHUNK, len(edges))
            d = _haversine(
                mid[start:end, 0:1], mid[start:end, 1:2],
                sc[None, :, 0],      sc[None, :, 1],
            )  # (chunk, n_stops)
            j = d.argmin(axis=1)
            nearest_scores[start:end] = scores_arr[j]
            nearest_uids[start:end] = uids_arr[j]
        return nearest_scores, nearest_uids


def main() -> int:
    ROUTE_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load data
    stops = load_stops()
    print(f"Stops with scores: {len(stops)}")

    # 2. Build edge DataFrame with midpoints
    edges = load_graph_edges()

    # 3. Score each edge by nearest stop
    nearest_scores, nearest_uids = nearest_stop_danger(edges, stops)
    edges["danger"] = np.clip((100.0 - nearest_scores) / 100.0, 0.0, 1.0)
    edges["weight"] = edges["length_m"] * (1.0 + ALPHA * edges["danger"])
    edges["nearest_stop_uid"] = pd.Series(nearest_uids, dtype="string")

    # 4. Write output
    out = edges[["u", "v", "length_m", "danger", "weight", "nearest_stop_uid"]].copy()
    out.to_parquet(OUT_PATH, compression="snappy", index=False)
    size_kb = OUT_PATH.stat().st_size / 1024

    # 5. Print summary
    w = out["weight"]
    d = out["danger"]
    print(f"\nOutput: {OUT_PATH}  ({size_kb:,.1f} KB)")
    print(f"Rows:   {len(out):,}")
    print(f"Weight: min={w.min():.1f}  mean={w.mean():.1f}  max={w.max():.1f}")
    print(f"Danger: min={d.min():.4f}  mean={d.mean():.4f}  max={d.max():.4f}")
    print(f"\nTop 10 most dangerous edges:")
    top10 = out.nlargest(10, "danger")
    for _, r in top10.iterrows():
        print(f"  u={r['u']:>8}  v={r['v']:>8}  length={r['length_m']:>7.0f}m  danger={r['danger']:.4f}  weight={r['weight']:>8.1f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build OSM street graph for Toronto and snap transit stops to nearest nodes.

Outputs:
  data/route/toronto_street.graphml  — street network graph (cached)
  data/route/stop_nodes.parquet      — stop-to-node mapping with snap distances

Run after score.py (requires data/scores/scores.parquet).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import osmnx as ox
import pandas as pd

ROOT = Path(__file__).parent.parent
ROUTE_DIR = ROOT / "data" / "route"
ROUTE_DIR.mkdir(parents=True, exist_ok=True)

# Toronto bounding box
NORTH, SOUTH, EAST, WEST = 43.86, 43.58, -79.12, -79.64

GRAPHML_PATH = ROUTE_DIR / "toronto_street.graphml"
STOP_NODES_PATH = ROUTE_DIR / "stop_nodes.parquet"
SCORES_PATH = ROOT / "data" / "scores" / "scores.parquet"


def _haversine_km(
    lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def load_or_build_graph() -> ox.MultiDiGraph:
    if GRAPHML_PATH.exists():
        print(f"Loading cached graph: {GRAPHML_PATH}")
        return ox.load_graphml(GRAPHML_PATH)
    print("Downloading OSM street network for Toronto bbox...")
    G = ox.graph_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), network_type="walk")
    print(f"Saving graph to {GRAPHML_PATH}")
    ox.save_graphml(G, GRAPHML_PATH)
    return G


def main() -> int:
    print("=== ROUTE GRAPH BUILD ===\n")

    # 1. Load or download graph
    G = load_or_build_graph()
    n = G.number_of_nodes()
    e = G.number_of_edges()
    print(f"Graph stats: {n:,} nodes, {e:,} edges\n")

    # 2. Load stops
    print(f"Loading stops: {SCORES_PATH}")
    stops = pd.read_parquet(
        SCORES_PATH,
        columns=["uid", "stop_id", "stop_name", "stop_lat", "stop_lon"],
    )
    print(f"  {len(stops):,} stops loaded\n")

    # 3. Snap each stop to nearest graph node
    print("Snapping stops to nearest graph nodes...")
    node_ids = ox.nearest_nodes(
        G, X=stops["stop_lon"].values, Y=stops["stop_lat"].values,
    )

    # 4. Compute snap distances via haversine
    nodes_df = ox.graph_to_gdfs(G, nodes=True, edges=False)
    snap_lats = nodes_df.loc[node_ids].geometry.y.values
    snap_lons = nodes_df.loc[node_ids].geometry.x.values
    snap_km = _haversine_km(
        stops["stop_lat"].values, stops["stop_lon"].values, snap_lats, snap_lons,
    )
    snap_m = snap_km * 1000

    print(f"  Snap distance (m):  min={snap_m.min():.1f}  "
          f"mean={snap_m.mean():.1f}  max={snap_m.max():.1f}\n")

    # 5. Write output
    out = stops.copy()
    out["graph_node_id"] = node_ids
    out.to_parquet(STOP_NODES_PATH, index=False)
    print(f"Output: {STOP_NODES_PATH}  "
          f"({STOP_NODES_PATH.stat().st_size / 1024:.0f} KB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())

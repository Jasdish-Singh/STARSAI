"""Bake 3-5 demo safe routes as static GeoJSON for the mobile PWA.

Run once offline: loads the 311 MB street graph, computes safe A* routes
for pre-selected origin→destination pairs, and writes GeoJSON to
frontend/public/routes/.

Usage: python pipeline/bake_demo_routes.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

from route_planner import (
    load_graph, attach_edge_weights, load_stops,
    find_stop_node, safe_route, route_to_geojson,
)

ROUTES_OUT = ROOT / "frontend" / "public" / "routes"
EDGE_WEIGHTS = ROOT / "data" / "route" / "edge_weights.parquet"

# Demo OD pairs — use stop names that exist in stop_nodes.parquet
DEMO_PAIRS = [
    ("union-to-bloor",     "Union Station",              "Bloor Station"),
    ("spadina-to-queen",   "Spadina Station",            "Queen Station"),
    ("eglinton-to-fin",    "Eglinton Station",           "Finch Station"),
    ("dundas-to-kipling",  "Dundas Station",             "Kipling Station"),
    ("king-to-kennedy",    "King Station",               "Kennedy Station"),
]


def bake():
    print("Loading graph (311 MB) ...")
    G = load_graph()
    print(f"  {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    print("Loading edge weights ...")
    import pandas as pd
    eweights = pd.read_parquet(EDGE_WEIGHTS)
    attach_edge_weights(G, eweights, alpha=2.0)
    print(f"  {len(eweights):,} weighted edges")

    print("Loading stops ...")
    stops = load_stops()
    print(f"  {len(stops):,} stops")

    ROUTES_OUT.mkdir(parents=True, exist_ok=True)
    baked = 0
    skipped = 0

    for route_id, origin_name, dest_name in DEMO_PAIRS:
        print(f"\n[{route_id}] {origin_name} -> {dest_name}")
        orig_node = find_stop_node(stops, origin_name)
        dest_node = find_stop_node(stops, dest_name)

        if orig_node is None:
            print(f"  SKIP: origin '{origin_name}' not found")
            skipped += 1
            continue
        if dest_node is None:
            print(f"  SKIP: dest '{dest_name}' not found")
            skipped += 1
            continue

        path = safe_route(G, orig_node, dest_node)
        if not path:
            print(f"  SKIP: no path found")
            skipped += 1
            continue

        geojson = route_to_geojson(path, G, stops)
        out_path = ROUTES_OUT / f"{route_id}.geojson"
        out_path.write_text(json.dumps(geojson))
        print(f"  -> {out_path} ({len(path)} nodes)")
        baked += 1

    print(f"\nDone. {baked} routes baked, {skipped} skipped.")


if __name__ == "__main__":
    bake()

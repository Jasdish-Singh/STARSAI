"""Silver — OSM tag extract from clipped PBF. One pass, three output parquets.

Per SDLC §4.2 silver stage, §5.1 factor catalogue:
- osm_pois.parquet    -> amenity/shop/leisure/tourism nodes -> FR-010 eyes-on-street
- osm_buildings.parquet -> building ways with centroid -> FR-013 sightline
- osm_lit_ways.parquet  -> highway+lit ways with midpoint -> FR-008 lighting (supplement)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import osmium
import pandas as pd

ROOT = Path(__file__).parent.parent
# USE FULL PBF — clipped PBF has Ontario-wide ways but only Toronto nodes,
# so way centroid resolution fails. Filter to Toronto bbox in-handler instead.
PBF = ROOT / "data" / "raw" / "osm" / "ontario-latest.osm.pbf"
SILVER = ROOT / "data" / "silver"
BBOX_LON = (-79.6394, -79.1163)
BBOX_LAT = (43.5781, 43.8554)
SILVER.mkdir(parents=True, exist_ok=True)

POI_TAGS = {"amenity", "shop", "leisure", "tourism"}


class ExtractHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.pois: list[dict] = []
        self.buildings: list[dict] = []
        self.lit_ways: list[dict] = []

    def node(self, n):
        lon, lat = n.location.lon, n.location.lat
        if not (BBOX_LON[0] <= lon <= BBOX_LON[1] and BBOX_LAT[0] <= lat <= BBOX_LAT[1]):
            return
        tags = {t.k: t.v for t in n.tags}
        if POI_TAGS & tags.keys():
            self.pois.append({
                "osm_id": n.id,
                "lon": lon,
                "lat": lat,
                "amenity": tags.get("amenity"),
                "shop": tags.get("shop"),
                "leisure": tags.get("leisure"),
                "tourism": tags.get("tourism"),
                "opening_hours": tags.get("opening_hours"),
                "name": tags.get("name"),
            })

    def way(self, w):
        tags = {t.k: t.v for t in w.tags}
        nodes = [n.ref for n in w.nodes]
        if not nodes:
            return
        n = len(nodes)

        # Building — store centroid from node sequence index (no location data in
        # simple mode; we compute centroid from node IDs as a hash proxy, then
        # downstream consumer snaps to actual coords). For now: store start/end
        # node refs so gold stage can join with node locations from PBF re-read.
        if "building" in tags:
            self.buildings.append({
                "osm_id": w.id,
                "building": tags["building"],
                "height": tags.get("height"),
                "levels": tags.get("levels"),
                "num_nodes": n,
                "node_start": nodes[0],
                "node_end": nodes[-1],
            })

        # Lit highway
        if "highway" in tags and "lit" in tags:
            self.lit_ways.append({
                "osm_id": w.id,
                "highway": tags["highway"],
                "lit": tags["lit"],
                "lighting": tags.get("lighting"),
                "name": tags.get("name"),
                "num_nodes": n,
                "node_start": nodes[0],
                "node_end": nodes[-1],
            })


# ── Second pass with location index for way centroid geometry ──

class WayGeomHandler(osmium.SimpleHandler):
    """Build node_id -> (lon,lat) map from nodes, then resolve way centroids."""

    def __init__(self, node_ids_needed: set[int],
                 bldg_way_ids: set[int], lit_way_ids: set[int]):
        super().__init__()
        self.node_coords: dict[int, tuple[float, float]] = {}
        self.bldg_ways: dict[int, dict] = {}
        self.lit_ways: dict[int, dict] = {}
        self.buildings: list[dict] = []
        self.lit_hwys: list[dict] = []
        self._nodes_needed = node_ids_needed
        self._bldg_way_ids = bldg_way_ids
        self._lit_way_ids = lit_way_ids

    def node(self, n):
        if n.id in self._nodes_needed:
            self.node_coords[n.id] = (n.location.lon, n.location.lat)

    def way(self, w):
        tags = {t.k: t.v for t in w.tags}
        if "building" in tags and w.id in self._bldg_way_ids:
            self.bldg_ways[w.id] = {
                "building": tags["building"],
                "height": tags.get("height"),
                "levels": tags.get("levels"),
                "node_refs": [n.ref for n in w.nodes],
            }
        if "highway" in tags and "lit" in tags and w.id in self._lit_way_ids:
            self.lit_ways[w.id] = {
                "highway": tags["highway"],
                "lit": tags["lit"],
                "lighting": tags.get("lighting"),
                "name": tags.get("name"),
                "node_refs": [n.ref for n in w.nodes],
            }

    def resolve(self):
        # Buildings: centroid of all node coords
        for wid, d in self.bldg_ways.items():
            coords = [self.node_coords.get(r) for r in d["node_refs"]]
            coords = [c for c in coords if c is not None]
            if not coords:
                continue
            lon = sum(c[0] for c in coords) / len(coords)
            lat = sum(c[1] for c in coords) / len(coords)
            self.buildings.append({
                "osm_id": wid,
                "lon": lon,
                "lat": lat,
                "building": d["building"],
                "height": d["height"],
                "levels": d["levels"],
                "num_nodes": len(d["node_refs"]),
            })

        # Lit highways: midpoint of first+last node
        for wid, d in self.lit_ways.items():
            first = self.node_coords.get(d["node_refs"][0])
            last = self.node_coords.get(d["node_refs"][-1])
            if first is None or last is None:
                continue
            self.lit_hwys.append({
                "osm_id": wid,
                "mid_lon": (first[0] + last[0]) / 2,
                "mid_lat": (first[1] + last[1]) / 2,
                "highway": d["highway"],
                "lit": d["lit"],
                "lighting": d.get("lighting"),
                "name": d.get("name"),
                "num_nodes": len(d["node_refs"]),
            })


def main() -> int:
    print(f"PBF: {PBF} ({PBF.stat().st_size / (1<<20):.0f} MB)")

    # Pass 1: collect POI nodes + way node-ref lists (no location needed)
    print("Pass 1: tag scan...")
    h1 = ExtractHandler()
    h1.apply_file(str(PBF), locations=False)  # fast, no location index
    print(f"  POIs: {len(h1.pois):,}")
    print(f"  Buildings (ways, no geom): {len(h1.buildings):,}")
    print(f"  Lit highways (ways, no geom): {len(h1.lit_ways):,}")

    # Write POIs immediately — no second pass needed
    pois_df = pd.DataFrame(h1.pois)
    pois_path = SILVER / "osm_pois.parquet"
    pois_df.to_parquet(pois_path, index=False, engine="pyarrow")
    print(f"\n  -> {pois_path} ({pois_path.stat().st_size / 1024:.0f} KB)")

    # Collect all node refs needed for building + lit-way geometry
    bldg_node_ids: set[int] = set()
    lit_node_ids: set[int] = set()
    bldg_way_ids: set[int] = set()
    lit_way_ids: set[int] = set()

    for d in h1.buildings:
        bldg_node_ids.add(d["node_start"])
        bldg_node_ids.add(d["node_end"])
        bldg_way_ids.add(d["osm_id"])

    for d in h1.lit_ways:
        lit_node_ids.add(d["node_start"])
        lit_node_ids.add(d["node_end"])
        lit_way_ids.add(d["osm_id"])

    all_needed = bldg_node_ids | lit_node_ids
    total_ways = len(bldg_way_ids) + len(lit_way_ids)
    print(f"\nPass 2: geometry resolve ({total_ways:,} ways, {len(all_needed):,} nodes)...")

    h2 = WayGeomHandler(all_needed, bldg_way_ids, lit_way_ids)
    h2.apply_file(str(PBF), locations=True)  # location index for node coords
    h2.resolve()

    bldg_full = h2.buildings
    bldg_toronto = [b for b in bldg_full
                    if BBOX_LON[0] <= b["lon"] <= BBOX_LON[1]
                    and BBOX_LAT[0] <= b["lat"] <= BBOX_LAT[1]]
    bldg_df = pd.DataFrame(bldg_toronto) if bldg_toronto else pd.DataFrame(
        columns=["osm_id", "lon", "lat", "building", "height", "levels", "num_nodes"])
    bldg_path = SILVER / "osm_buildings.parquet"
    bldg_df.to_parquet(bldg_path, index=False, engine="pyarrow")
    print(f"  Buildings resolved: {len(bldg_full):,} (in Toronto: {len(bldg_toronto):,})")
    print(f"  -> {bldg_path} ({bldg_path.stat().st_size / 1024:.0f} KB)")

    lit_full = h2.lit_hwys
    lit_toronto = [l for l in lit_full
                   if BBOX_LON[0] <= l["mid_lon"] <= BBOX_LON[1]
                   and BBOX_LAT[0] <= l["mid_lat"] <= BBOX_LAT[1]]
    lit_df = pd.DataFrame(lit_toronto) if lit_toronto else pd.DataFrame(
        columns=["osm_id", "mid_lon", "mid_lat", "highway", "lit", "lighting", "name", "num_nodes"])
    lit_path = SILVER / "osm_lit_ways.parquet"
    lit_df.to_parquet(lit_path, index=False, engine="pyarrow")
    print(f"  Lit ways resolved: {len(lit_full):,} (in Toronto: {len(lit_toronto):,})")
    print(f"  -> {lit_path} ({lit_path.stat().st_size / 1024:.0f} KB)")

    # Summary
    print("\n=== OSM silver summary ===")
    print(f"  osm_pois:       {len(pois_df):>8,}")
    if len(pois_df):
        top = pois_df["amenity"].value_counts().head(8).to_dict()
        print(f"    top amenity: {top}")
    print(f"  osm_buildings:  {len(bldg_df):>8,}  (bbox centroid from way nodes)")
    if len(bldg_df):
        top = bldg_df["building"].value_counts().head(5).to_dict()
        print(f"    top type: {top}")
    print(f"  osm_lit_ways:   {len(lit_df):>8,}  (midpoint from first+last node)")
    if len(lit_df):
        top = lit_df["highway"].value_counts().head(5).to_dict()
        print(f"    top highway: {top}")
        lit_vals = lit_df["lit"].value_counts().to_dict()
        print(f"    lit values: {lit_vals}")

    # Manifest
    manifest = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
        "files": {
            "osm_pois.parquet": {"rows": len(pois_df), "bytes": pois_path.stat().st_size},
            "osm_buildings.parquet": {"rows": len(bldg_df), "bytes": bldg_path.stat().st_size},
            "osm_lit_ways.parquet": {"rows": len(lit_df), "bytes": lit_path.stat().st_size},
        },
    }
    mpath = SILVER / "manifest.json"
    # Merge with existing if present
    if mpath.exists():
        existing = json.loads(mpath.read_text())
        existing["files"].update(manifest["files"])
        existing["generated_at"] = manifest["generated_at"]
        manifest = existing
    mpath.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"\nManifest: {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

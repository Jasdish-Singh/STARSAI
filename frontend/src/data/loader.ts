import type { ScoresData, ProvenanceEntry } from "../types";

const DATA_BASE = "/data";

export async function loadScores(): Promise<ScoresData> {
  const res = await fetch(`${DATA_BASE}/scores.json`);
  if (!res.ok) throw new Error(`Failed to load scores: ${res.status}`);
  return res.json();
}

export async function loadProvenance(uid: string): Promise<ProvenanceEntry | null> {
  try {
    const res = await fetch(`${DATA_BASE}/provenance.json`);
    if (!res.ok) return null;
    const data = await res.json();
    const entry = data.stops?.find((s: ProvenanceEntry) => s.uid === uid);
    return entry || null;
  } catch {
    return null;
  }
}

export async function loadRoute(id: string): Promise<GeoJSON.FeatureCollection | null> {
  try {
    const res = await fetch(`/routes/${id}.geojson`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

import { useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { useStore } from '../store/useStore';
import type { StopFactors } from '../types';

const RAW_LABELS: Record<string, string> = {
  lights_50m: 'Streetlights',
  poles_total_50m: 'Total poles',
  lit_yes_100m: 'Lit-tagged ways',
  crime_count_500m: 'All crime',
  crime_assault_500m: 'Assaults',
  crime_robbery_500m: 'Robberies',
  disorder_count_200m: '311 disorder calls',
  pois_150m: 'POIs',
  food_drink_150m: 'Food / drink',
  buildings_50m: 'Buildings',
  building_nodes_50m: 'Building corners'
};

const RAW_GROUPS: Array<{ title: string; keys: string[] }> = [
  { title: 'Lighting', keys: ['lights_50m', 'poles_total_50m', 'lit_yes_100m'] },
  { title: 'Crime (500m)', keys: ['crime_count_500m', 'crime_assault_500m', 'crime_robbery_500m'] },
  { title: 'Disorder (200m)', keys: ['disorder_count_200m'] },
  { title: 'Activity (150m)', keys: ['pois_150m', 'food_drink_150m'] },
  { title: 'Buildings (50m)', keys: ['buildings_50m', 'building_nodes_50m'] }
];

const FACTOR_LABELS: Record<keyof StopFactors, string> = {
  lighting: 'Lighting',
  crime: 'Crime',
  eyes_on_street: 'Eyes on street',
  isolation: 'Isolation',
  wait_exposure: 'Wait exposure',
  sightline: 'Sightline',
  disorder_311: '311 disorder',
  lit_way_supplement: 'Lit way supplement'
};

let provenanceCache: Record<string, any> | null = null;
let provenancePromise: Promise<Record<string, any>> | null = null;

function loadProvenance() {
  if (provenanceCache) return Promise.resolve(provenanceCache);
  if (!provenancePromise) {
    provenancePromise = fetch('/provenance.json')
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => {
        provenanceCache = data;
        return data;
      })
      .catch(() => {
        provenanceCache = {};
        return {};
      });
  }
  return provenancePromise;
}

export function StopPanel() {
  const stops = useStore((state) => state.stops);
  const selectedUid = useStore((state) => state.selectedUid);
  const provenance = useStore((state) => state.provenance);
  const setSelectedUid = useStore((state) => state.setSelectedUid);
  const setProvenanceEntry = useStore((state) => state.setProvenanceEntry);
  const [dragY, setDragY] = useState(0);
  const [loading, setLoading] = useState(false);
  const dragStart = useRef<number | null>(null);

  const stop = useMemo(() => stops?.find((item) => item.uid === selectedUid) ?? null, [selectedUid, stops]);
  const provenanceEntry = selectedUid ? provenance[selectedUid] : null;
  const raw = provenanceEntry?.raw;
  const total = stops?.length ?? 0;

  useEffect(() => {
    if (!selectedUid || provenance[selectedUid] !== undefined) return;
    let cancelled = false;
    setLoading(true);
    loadProvenance().then((data) => {
      if (cancelled) return;
      const bucket = (data && typeof data === 'object' && 'stops' in data) ? (data as any).stops : data;
      setProvenanceEntry(selectedUid, bucket?.[selectedUid] ?? null);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [provenance, selectedUid, setProvenanceEntry]);

  useEffect(() => {
    if (!selectedUid) return;
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') { setDragY(0); setSelectedUid(null); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [selectedUid, setSelectedUid]);

  if (!selectedUid || !stop) return null;

  const close = () => {
    setDragY(0);
    setSelectedUid(null);
  };

  const onHandleKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Escape') { e.preventDefault(); close(); }
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    dragStart.current = event.clientY;
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (dragStart.current === null) return;
    setDragY(Math.max(0, event.clientY - dragStart.current));
  };

  const onPointerUp = () => {
    if (dragY > 90) close();
    else setDragY(0);
    dragStart.current = null;
  };

  return (
    <div className="panel-layer" role="presentation">
      <button className="panel-backdrop" type="button" aria-label="Close stop details" onClick={close} />
      <section
        className="stop-panel"
        aria-label="Stop safety details"
        style={{ transform: `translateY(${dragY}px)` }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <div className="drag-handle" role="button" tabIndex={0} aria-label="Close stop details (Enter or Esc)" onKeyDown={onHandleKey} />
        <header className="stop-header">
          <div>
            <h1>{stop.name}</h1>
            <p>{stop.sys} rank ({stop.rank} of {total})</p>
          </div>
          <strong className="score-badge">{stop.score}</strong>
        </header>
        <div className="factor-bars">
          {(Object.entries(stop.f) as Array<[keyof StopFactors, number]>).map(([key, value]) => (
            <div className="factor-row" key={key}>
              <span>{FACTOR_LABELS[key]}</span>
              <div className="factor-track" aria-hidden="true">
                <div className="factor-fill" style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
              </div>
              <b>{value}</b>
            </div>
          ))}
        </div>
        <section className="provenance">
          <h2>Provenance</h2>
          {loading ? (
            <p className="muted">Loading provenance...</p>
          ) : raw && typeof raw === 'object' ? (
            RAW_GROUPS.map((group) => (
              <section className="prov-group" key={group.title}>
                <h3>{group.title}</h3>
                <dl className="provenance-list">
                  {group.keys.map((k) => (
                    <div key={k}>
                      <dt>{RAW_LABELS[k]}</dt>
                      <dd>{raw[k] ?? '—'}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))
          ) : (
            <p className="muted">no provenance available</p>
          )}
        </section>
      </section>
    </div>
  );
}

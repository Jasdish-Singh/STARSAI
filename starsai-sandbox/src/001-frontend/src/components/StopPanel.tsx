import { useEffect, useMemo, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { useStore } from '../store/useStore';
import type { StopFactors } from '../types';

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

function renderProvenance(value: any) {
  if (!value) return <p className="muted">no provenance available</p>;
  if (typeof value !== 'object') return <p>{String(value)}</p>;
  return (
    <dl className="provenance-list">
      {Object.entries(value).map(([key, item]) => (
        <div key={key}>
          <dt>{key.replaceAll('_', ' ')}</dt>
          <dd>{typeof item === 'object' ? JSON.stringify(item) : String(item)}</dd>
        </div>
      ))}
    </dl>
  );
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
  const total = stops?.length ?? 0;

  useEffect(() => {
    if (!selectedUid || provenance[selectedUid] !== undefined) return;
    let cancelled = false;
    setLoading(true);
    loadProvenance().then((data) => {
      if (cancelled) return;
      setProvenanceEntry(selectedUid, data[selectedUid] ?? null);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [provenance, selectedUid, setProvenanceEntry]);

  if (!selectedUid || !stop) return null;

  const close = () => {
    setDragY(0);
    setSelectedUid(null);
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
        <div className="drag-handle" />
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
          {loading ? <p className="muted">Loading provenance...</p> : renderProvenance(provenanceEntry)}
        </section>
      </section>
    </div>
  );
}

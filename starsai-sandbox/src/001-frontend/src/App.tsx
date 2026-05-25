import { useEffect } from 'react';
import { RouteSelector } from './components/RouteSelector';
import { SafetyMap } from './components/SafetyMap';
import { StopPanel } from './components/StopPanel';
import { TimePresets } from './components/TimePresets';
import { useStore } from './store/useStore';
import type { ScoresPayload } from './types';

export default function App() {
  const setStops = useStore((state) => state.setStops);

  useEffect(() => {
    let cancelled = false;
    fetch('/scores.json')
      .then((res) => {
        if (!res.ok) throw new Error('scores fetch failed');
        return res.json() as Promise<ScoresPayload>;
      })
      .then((data) => {
        if (!cancelled) setStops(data.stops);
      })
      .catch(() => {
        if (!cancelled) setStops([]);
      });
    return () => {
      cancelled = true;
    };
  }, [setStops]);

  return (
    <main className="app-shell">
      <SafetyMap />
      <RouteSelector />
      <TimePresets />
      <StopPanel />
    </main>
  );
}

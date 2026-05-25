import { ChangeEvent } from 'react';
import { useStore } from '../store/useStore';

type DemoRoute = { id: string; label: string; file: string };

export const DEMO_ROUTES: DemoRoute[] = []; // TODO: bake demo route GeoJSON files.

export function RouteSelector() {
  const setRouteFeature = useStore((state) => state.setRouteFeature);

  const onRouteChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const route = DEMO_ROUTES.find((item) => item.id === event.target.value);
    if (!route) {
      setRouteFeature(null);
      return;
    }
    fetch(`/routes/${route.file}`)
      .then((res) => {
        if (!res.ok) throw new Error('route fetch failed');
        return res.json();
      })
      .then(setRouteFeature)
      .catch(() => setRouteFeature(null));
  };

  return (
    <aside className="route-selector" aria-label="Route selector">
      {DEMO_ROUTES.length === 0 ? (
        <small>Demo routes not baked yet.</small>
      ) : (
        <select defaultValue="" onChange={onRouteChange} aria-label="Demo route">
          <option value="">No route</option>
          {DEMO_ROUTES.map((route) => (
            <option key={route.id} value={route.id}>{route.label}</option>
          ))}
        </select>
      )}
    </aside>
  );
}

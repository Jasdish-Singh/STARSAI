import DeckGL from '@deck.gl/react';
import { GeoJsonLayer, ScatterplotLayer } from '@deck.gl/layers';
import { Map } from '@vis.gl/react-maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useMemo } from 'react';
import { useStore } from '../store/useStore';
import type { Stop } from '../types';

const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json';
const INITIAL_VIEW_STATE = { longitude: -79.3832, latitude: 43.6532, zoom: 11, pitch: 0, bearing: 0 };

function scoreColor(score: number): [number, number, number, number] {
  if (score >= 70) return [24, 164, 99, 230];
  if (score >= 45) return [238, 195, 65, 230];
  return [214, 64, 55, 230];
}

export function SafetyMap() {
  const stops = useStore((state) => state.stops);
  const routeFeature = useStore((state) => state.routeFeature);
  const setSelectedUid = useStore((state) => state.setSelectedUid);

  const layers = useMemo(() => {
    const baseLayers: any[] = [
      new ScatterplotLayer<Stop>({
        id: 'starsai-stops',
        data: stops ?? [],
        getPosition: (d) => [d.lon, d.lat],
        getFillColor: (d) => scoreColor(d.score),
        getLineColor: [11, 15, 26, 240],
        getLineWidth: 1,
        getRadius: 60,
        radiusMinPixels: 4,
        radiusMaxPixels: 12,
        pickable: true,
        stroked: true,
        lineWidthMinPixels: 1,
        onClick: (info) => {
          const stop = info.object as Stop | undefined;
          if (stop) setSelectedUid(stop.uid);
        }
      })
    ];

    if (routeFeature) {
      baseLayers.push(
        new GeoJsonLayer({
          id: 'starsai-route',
          data: routeFeature,
          getLineColor: [32, 101, 209, 220],
          getLineWidth: 5,
          lineWidthMinPixels: 3,
          pickable: false
        })
      );
    }

    return baseLayers;
  }, [routeFeature, setSelectedUid, stops]);

  return (
    <DeckGL controller initialViewState={INITIAL_VIEW_STATE} layers={layers}>
      <Map reuseMaps mapStyle={MAP_STYLE} />
    </DeckGL>
  );
}

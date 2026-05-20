import { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer } from "@deck.gl/layers";
import { Map } from "@vis.gl/react-maplibre";
import { useStore } from "../store/useStore";
import type { StopScore } from "../types";
import "maplibre-gl/dist/maplibre-gl.css";

const TORONTO_CENTER: [number, number] = [-79.3832, 43.6532];
const SCORE_COLORS = [
  [220, 50, 50],
  [220, 120, 50],
  [220, 180, 50],
  [180, 200, 50],
  [100, 200, 60],
  [50, 180, 70],
  [30, 150, 70],
  [20, 120, 60],
];

function scoreColor(score: number): [number, number, number] {
  const clamped = Math.max(0, Math.min(100, score));
  const idx = (clamped / 100) * (SCORE_COLORS.length - 1);
  const lo = SCORE_COLORS[Math.floor(idx)];
  const hi = SCORE_COLORS[Math.ceil(idx)];
  const t = idx - Math.floor(idx);
  return [
    Math.round(lo[0] + (hi[0] - lo[0]) * t),
    Math.round(lo[1] + (hi[1] - lo[1]) * t),
    Math.round(lo[2] + (hi[2] - lo[2]) * t),
  ];
}

export default function SafetyMap() {
  const { scores, selectStop, timePreset } = useStore();
  const [viewState, setViewState] = useState({
    longitude: TORONTO_CENTER[0],
    latitude: TORONTO_CENTER[1],
    zoom: 12,
    pitch: 0,
    bearing: 0,
  });

  const getScore = useCallback(
    (stop: StopScore) => stop.score,
    [timePreset]
  );

  const layer = new ScatterplotLayer<StopScore>({
    id: "stops",
    data: scores,
    getPosition: (d: StopScore) => [d.lon, d.lat],
    getRadius: 5,
    radiusMinPixels: 2.5,
    radiusMaxPixels: 8,
    getFillColor: (d: StopScore) => scoreColor(getScore(d)),
    opacity: 0.7,
    pickable: true,
    onClick: (info: { object?: StopScore }) => {
      if (info.object) selectStop(info.object);
    },
    updateTriggers: { getFillColor: [timePreset] },
  });

  const handleMapClick = useCallback(() => {
    selectStop(null);
  }, [selectStop]);

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <Map
        initialViewState={viewState}
        mapStyle="https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json"
        style={{ width: "100%", height: "100%" }}
        onClick={handleMapClick}
        attributionControl={false}
      >
        <DeckGL
          viewState={viewState}
          layers={[layer]}
          onViewStateChange={({ viewState: vs }) => setViewState(vs as typeof viewState)}
          controller={{ touchRotate: false, keyboard: false }}
          getCursor={() => "crosshair"}
        />
      </Map>
    </div>
  );
}

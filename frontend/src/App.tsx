import { useEffect } from "react";
import { useStore } from "./store/useStore";
import SafetyMap from "./components/SafetyMap";
import TimePresets from "./components/TimePresets";
import StopPanel from "./components/StopPanel";
import RouteSelector from "./components/RouteSelector";
import "./App.css";

export default function App() {
  const { loading, init } = useStore();

  useEffect(() => { init(); }, []);

  return (
    <div className="app">
      {loading && (
        <div className="loading">
          <div className="spinner" />
          <span>Loading 9,378 stops...</span>
        </div>
      )}
      <SafetyMap />
      <RouteSelector />
      <StopPanel />
      <TimePresets />
    </div>
  );
}

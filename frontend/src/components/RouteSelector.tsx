import { useState, useEffect } from "react";
import { useStore } from "../store/useStore";
import { loadRoute } from "../data/loader";
import type { DemoRoute } from "../types";

const DEMO_ROUTES = [
  { id: "union-to-bloor", name: "Union → Bloor-Yonge" },
  { id: "spadina-to-queen", name: "Spadina → Queen" },
  { id: "eglinton-to-fin", name: "Eglinton → Finch" },
];

export default function RouteSelector() {
  const { activeRoute, setActiveRoute } = useStore();
  const [expanded, setExpanded] = useState(false);
  const [routes, setRoutes] = useState<DemoRoute[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (expanded && routes.length === 0) {
      setLoading(true);
      Promise.all(
        DEMO_ROUTES.map(async (r) => {
          const geojson = await loadRoute(r.id);
          return { ...r, geojson };
        })
      ).then((loaded) => {
        setRoutes(loaded);
        setLoading(false);
      });
    }
  }, [expanded]);

  return (
    <div style={{
      position: "absolute", top: 12, right: 12, zIndex: 10,
    }}>
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: "rgba(10,10,26,0.85)", backdropFilter: "blur(8px)",
          WebkitBackdropFilter: "blur(8px)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: 12, padding: "10px 14px",
          color: "#ccc", fontSize: 12, fontWeight: 600, cursor: "pointer",
        }}
      >
        🗺️ Routes {expanded ? "▲" : "▼"}
      </button>

      {expanded && (
        <div style={{
          marginTop: 6, background: "rgba(10,10,26,0.9)", backdropFilter: "blur(10px)",
          borderRadius: 12, padding: 8, border: "1px solid rgba(255,255,255,0.08)",
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {loading && <span style={{ fontSize: 11, color: "#666", padding: 4 }}>Loading...</span>}
          {!loading && routes.length === 0 && (
            <span style={{ fontSize: 11, color: "#666", padding: 4 }}>
              No routes baked yet — run <code>bake_demo_routes.py</code>
            </span>
          )}
          {routes.map((r) => (
            <button
              key={r.id}
              onClick={() => setActiveRoute(activeRoute === r.id ? null : r.id)}
              style={{
                padding: "8px 12px", borderRadius: 8,
                border: "none",
                background: activeRoute === r.id
                  ? "rgba(100,200,255,0.2)"
                  : "rgba(255,255,255,0.05)",
                color: activeRoute === r.id ? "#88ccff" : "#aaa",
                fontSize: 12, cursor: "pointer", textAlign: "left",
              }}
            >
              {r.geojson ? "📍 " : "⏳ "}{r.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

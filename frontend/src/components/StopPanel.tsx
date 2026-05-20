import { useStore } from "../store/useStore";

const FACTOR_LABELS: Record<string, string> = {
  lighting: "Lighting",
  crime: "Crime",
  eyes_on_street: "Eyes on Street",
  isolation: "Isolation",
  wait_exposure: "Wait Exposure",
  sightline: "Sightline",
  disorder_311: "311 Disorder",
  lit_way_supplement: "Lit Way",
};

function scoreBar(score: number, max = 100) {
  const pct = Math.min(100, Math.max(0, (score / max) * 100));
  const color = pct > 66 ? "#4caf50" : pct > 33 ? "#ff9800" : "#f44336";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
      <div style={{
        flex: 1, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.1)",
        overflow: "hidden",
      }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3, background: color }} />
      </div>
      <span style={{ fontSize: 11, width: 36, textAlign: "right", color: "#ccc" }}>
        {score.toFixed(0)}
      </span>
    </div>
  );
}

export default function StopPanel() {
  const { selectedStop, provenance, selectStop } = useStore();

  if (!selectedStop) return null;

  return (
    <div style={{
      position: "absolute", bottom: 110, left: 8, right: 8,
      background: "rgba(10,10,26,0.92)", backdropFilter: "blur(12px)",
      WebkitBackdropFilter: "blur(12px)",
      borderRadius: 16, padding: "16px 14px 20px",
      zIndex: 10, maxHeight: "50vh", overflowY: "auto",
      border: "1px solid rgba(255,255,255,0.08)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <div>
          <h3 style={{ margin: 0, fontSize: 15, color: "#fff", lineHeight: 1.3 }}>
            {selectedStop.name}
          </h3>
          <p style={{ margin: "2px 0 0", fontSize: 11, color: "#888" }}>
            Stop {selectedStop.id} · {selectedStop.sys.toUpperCase()}
          </p>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{
            fontSize: 28, fontWeight: 700,
            color: selectedStop.score > 66 ? "#4caf50" : selectedStop.score > 33 ? "#ff9800" : "#f44336",
          }}>
            {selectedStop.score.toFixed(0)}
          </div>
          <div style={{ fontSize: 10, color: "#666" }}>Rank #{selectedStop.rank.toLocaleString()}</div>
        </div>
        <button
          onClick={() => selectStop(null)}
          style={{
            position: "absolute", top: 8, right: 8,
            background: "none", border: "none", color: "#666", fontSize: 18, cursor: "pointer",
          }}
        >
          ✕
        </button>
      </div>

      <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 6 }}>
        {Object.entries(selectedStop.f).map(([key, val]) => (
          <div key={key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 11, width: 100, color: "#aaa" }}>
              {FACTOR_LABELS[key] || key}
            </span>
            {scoreBar(val)}
          </div>
        ))}
      </div>

      {provenance && (
        <details style={{ marginTop: 12 }}>
          <summary style={{ fontSize: 11, color: "#666", cursor: "pointer" }}>
            Provenance
          </summary>
          <pre style={{ fontSize: 10, color: "#888", overflow: "auto", marginTop: 4 }}>
            {JSON.stringify(provenance, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
}

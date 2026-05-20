import { useStore } from "../store/useStore";
import { TIME_PRESETS } from "../types";

export default function TimePresets() {
  const { timePreset, setTimePreset } = useStore();

  return (
    <div style={{
      position: "absolute", bottom: 24, left: 12, right: 12,
      display: "flex", gap: 8, justifyContent: "center", zIndex: 10,
    }}>
      {TIME_PRESETS.map((tp) => (
        <button
          key={tp.id}
          onClick={() => setTimePreset(tp.id)}
          style={{
            flex: 1, maxWidth: 100, padding: "12px 8px",
            border: "none", borderRadius: 12,
            background: timePreset === tp.id
              ? "rgba(100,200,100,0.25)"
              : "rgba(255,255,255,0.08)",
            color: timePreset === tp.id ? "#a0ffa0" : "#aaa",
            fontSize: 12, fontWeight: 600,
            backdropFilter: "blur(8px)",
            WebkitBackdropFilter: "blur(8px)",
            cursor: "pointer",
            display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
          }}
        >
          <span style={{ fontSize: 10, opacity: 0.7 }}>{tp.label}</span>
          <span style={{ fontSize: 16 }}>{tp.short}</span>
        </button>
      ))}
    </div>
  );
}

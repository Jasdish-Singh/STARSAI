import { create } from "zustand";
import type { StopScore, TimePreset, DemoRoute } from "../types";
import { loadScores, loadProvenance } from "../data/loader";

interface Store {
  scores: StopScore[];
  loading: boolean;
  selectedStop: StopScore | null;
  provenance: Record<string, unknown> | null;
  timePreset: TimePreset;
  routes: DemoRoute[];
  activeRoute: string | null;

  init: () => Promise<void>;
  selectStop: (stop: StopScore | null) => Promise<void>;
  setTimePreset: (t: TimePreset) => void;
  setActiveRoute: (id: string | null) => void;
}

export const useStore = create<Store>((set, get) => ({
  scores: [],
  loading: true,
  selectedStop: null,
  provenance: null,
  timePreset: "weekday-22",
  routes: [],
  activeRoute: null,

  init: async () => {
    try {
      const data = await loadScores();
      set({ scores: data.stops, loading: false });
    } catch (e) {
      console.error("Failed to load scores:", e);
      set({ loading: false });
    }
  },

  selectStop: async (stop) => {
    set({ selectedStop: stop, provenance: null });
    if (stop) {
      const prov = await loadProvenance(stop.uid);
      set({ provenance: prov });
    }
  },

  setTimePreset: (t) => set({ timePreset: t }),

  setActiveRoute: (id) => set({ activeRoute: id }),
}));

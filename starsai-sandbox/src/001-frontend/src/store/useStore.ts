import { create } from 'zustand';
import type { PresetId, Stop } from '../types';

type StoreState = {
  stops: Stop[] | null;
  selectedUid: string | null;
  presetId: PresetId;
  provenance: Record<string, any>;
  routeFeature: any | null;
  setStops: (stops: Stop[]) => void;
  setSelectedUid: (uid: string | null) => void;
  setPreset: (presetId: PresetId) => void;
  setProvenanceEntry: (uid: string, data: any) => void;
  setRouteFeature: (feature: any | null) => void;
};

export const useStore = create<StoreState>((set) => ({
  stops: null,
  selectedUid: null,
  presetId: 'wk22',
  provenance: {},
  routeFeature: null,
  setStops: (stops) => set({ stops }),
  setSelectedUid: (selectedUid) => set({ selectedUid }),
  setPreset: (presetId) => set({ presetId }),
  setProvenanceEntry: (uid, data) => set((state) => ({ provenance: { ...state.provenance, [uid]: data } })),
  setRouteFeature: (routeFeature) => set({ routeFeature })
}));

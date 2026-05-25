import { useStore } from '../store/useStore';
import type { PresetId } from '../types';

export const PRESETS: Array<{ id: PresetId; label: string; field: 'score' }> = [
  { id: 'wk22', label: 'Weekday 10pm', field: 'score' },
  { id: 'fr23', label: 'Fri 11pm', field: 'score' },
  { id: 'sa01', label: 'Sat 1am', field: 'score' },
  { id: 'su21', label: 'Sun 9pm', field: 'score' }
];

export function TimePresets() {
  const presetId = useStore((state) => state.presetId);
  const setPreset = useStore((state) => state.setPreset);

  return (
    <nav className="time-presets" aria-label="Time preset">
      {PRESETS.map((preset) => (
        <button
          key={preset.id}
          type="button"
          className={presetId === preset.id ? 'time-preset active' : 'time-preset'}
          onClick={() => setPreset(preset.id)}
        >
          {preset.label}
        </button>
      ))}
    </nav>
  );
}

export interface FactorBreakdown {
  lighting: number;
  crime: number;
  eyes_on_street: number;
  isolation: number;
  wait_exposure: number;
  sightline: number;
  disorder_311: number;
  lit_way_supplement: number;
}

export interface StopScore {
  uid: string;
  id: number;
  name: string;
  sys: string;
  lat: number;
  lon: number;
  score: number;
  rank: number;
  q: string;
  f: FactorBreakdown;
}

export interface ScoresData {
  schema_version: string;
  generated_at: string;
  commit: string;
  model: { version: string; method: string; auroc: number };
  n_stops: number;
  stops: StopScore[];
}

export interface ProvenanceEntry {
  uid: string;
  stop_id: number;
  stop_name: string;
  score: number;
  factors: FactorBreakdown;
  weights: FactorBreakdown;
  contributions: FactorBreakdown;
}

export type TimePreset = "weekday-22" | "friday-23" | "saturday-1" | "sunday-21";

export const TIME_PRESETS: { id: TimePreset; label: string; short: string }[] = [
  { id: "weekday-22", label: "Weekday", short: "10PM" },
  { id: "friday-23", label: "Friday", short: "11PM" },
  { id: "saturday-1", label: "Saturday", short: "1AM" },
  { id: "sunday-21", label: "Sunday", short: "9PM" },
];

export interface DemoRoute {
  id: string;
  name: string;
  geojson: GeoJSON.FeatureCollection | null;
}

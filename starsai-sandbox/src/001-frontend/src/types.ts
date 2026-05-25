export type SafetyQuartile = 'Q1' | 'Q2' | 'Q3' | 'Q4';

export type StopFactors = {
  lighting: number;
  crime: number;
  eyes_on_street: number;
  isolation: number;
  wait_exposure: number;
  sightline: number;
  disorder_311: number;
  lit_way_supplement: number;
};

export type Stop = {
  uid: string;
  id: string;
  name: string;
  sys: string;
  lat: number;
  lon: number;
  score: number;
  rank: number;
  q: SafetyQuartile;
  f: StopFactors;
};

export type ScoresPayload = {
  schema_version: number;
  generated_at: string;
  commit: string;
  model: { version: string; method: string; auroc: number };
  n_stops: number;
  stops: Stop[];
};

export type PresetId = 'wk22' | 'fr23' | 'sa01' | 'su21';

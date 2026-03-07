export interface ImpactFactors {
  geo: number;
  sec: number;
  eco: number;
}

// Phase 1: 10개 주요국 기준 (calibration.py IMPACT_FACTORS와 동기화)
export const IMPACT: Record<string, Record<string, ImpactFactors>> = {
  KR: {
    KP: { geo: 1.0, sec: 1.0, eco: 0.1 },
    KR: { geo: 1.0, sec: 1.0, eco: 1.0 },
    JP: { geo: 0.9, sec: 0.6, eco: 0.8 },
    CN: { geo: 0.8, sec: 0.5, eco: 0.9 },
    TW: { geo: 0.6, sec: 0.6, eco: 0.7 },
    US: { geo: 0.3, sec: 0.8, eco: 0.7 },
    RU: { geo: 0.5, sec: 0.5, eco: 0.4 },
    SA: { geo: 0.2, sec: 0.2, eco: 0.6 },
    IR: { geo: 0.2, sec: 0.3, eco: 0.5 },
    UA: { geo: 0.2, sec: 0.3, eco: 0.3 },
    DE: { geo: 0.2, sec: 0.2, eco: 0.5 },
    GB: { geo: 0.2, sec: 0.3, eco: 0.4 },
    AU: { geo: 0.3, sec: 0.2, eco: 0.4 },
    VN: { geo: 0.4, sec: 0.2, eco: 0.5 },
    IN: { geo: 0.3, sec: 0.2, eco: 0.4 },
    ID: { geo: 0.3, sec: 0.2, eco: 0.4 },
  },
  US: {
    US: { geo: 1.0, sec: 1.0, eco: 1.0 },
    CN: { geo: 0.3, sec: 0.8, eco: 0.9 },
    RU: { geo: 0.3, sec: 0.9, eco: 0.4 },
    IR: { geo: 0.2, sec: 0.7, eco: 0.5 },
    KP: { geo: 0.2, sec: 0.6, eco: 0.1 },
    UA: { geo: 0.2, sec: 0.7, eco: 0.3 },
    TW: { geo: 0.3, sec: 0.7, eco: 0.6 },
    MX: { geo: 0.9, sec: 0.4, eco: 0.7 },
    CA: { geo: 0.9, sec: 0.3, eco: 0.8 },
    GB: { geo: 0.4, sec: 0.6, eco: 0.7 },
    IL: { geo: 0.2, sec: 0.7, eco: 0.4 },
    SA: { geo: 0.2, sec: 0.5, eco: 0.7 },
    JP: { geo: 0.3, sec: 0.5, eco: 0.6 },
    DE: { geo: 0.2, sec: 0.4, eco: 0.6 },
  },
  JP: {
    JP: { geo: 1.0, sec: 1.0, eco: 1.0 },
    CN: { geo: 0.9, sec: 0.8, eco: 0.9 },
    KP: { geo: 0.8, sec: 0.9, eco: 0.1 },
    KR: { geo: 0.9, sec: 0.5, eco: 0.7 },
    TW: { geo: 0.7, sec: 0.7, eco: 0.6 },
    US: { geo: 0.3, sec: 0.8, eco: 0.7 },
    RU: { geo: 0.6, sec: 0.6, eco: 0.3 },
    AU: { geo: 0.4, sec: 0.3, eco: 0.5 },
    IN: { geo: 0.3, sec: 0.3, eco: 0.4 },
  },
  CN: {
    CN: { geo: 1.0, sec: 1.0, eco: 1.0 },
    TW: { geo: 0.9, sec: 1.0, eco: 0.7 },
    US: { geo: 0.3, sec: 0.9, eco: 0.9 },
    JP: { geo: 0.8, sec: 0.6, eco: 0.7 },
    KR: { geo: 0.7, sec: 0.4, eco: 0.6 },
    IN: { geo: 0.8, sec: 0.6, eco: 0.5 },
    RU: { geo: 0.7, sec: 0.5, eco: 0.5 },
    KP: { geo: 0.7, sec: 0.5, eco: 0.2 },
    AU: { geo: 0.3, sec: 0.4, eco: 0.6 },
  },
  TW: {
    TW: { geo: 1.0, sec: 1.0, eco: 1.0 },
    CN: { geo: 1.0, sec: 1.0, eco: 0.9 },
    US: { geo: 0.3, sec: 0.9, eco: 0.7 },
    JP: { geo: 0.7, sec: 0.5, eco: 0.7 },
    KR: { geo: 0.5, sec: 0.3, eco: 0.5 },
  },
  DE: {
    DE: { geo: 1.0, sec: 1.0, eco: 1.0 },
    RU: { geo: 0.5, sec: 0.8, eco: 0.6 },
    UA: { geo: 0.5, sec: 0.8, eco: 0.4 },
    FR: { geo: 0.9, sec: 0.4, eco: 0.8 },
    CN: { geo: 0.2, sec: 0.5, eco: 0.8 },
    US: { geo: 0.2, sec: 0.6, eco: 0.7 },
    TR: { geo: 0.4, sec: 0.4, eco: 0.5 },
    IR: { geo: 0.2, sec: 0.5, eco: 0.4 },
  },
  GB: {
    GB: { geo: 1.0, sec: 1.0, eco: 1.0 },
    US: { geo: 0.3, sec: 0.8, eco: 0.8 },
    RU: { geo: 0.4, sec: 0.8, eco: 0.4 },
    UA: { geo: 0.4, sec: 0.7, eco: 0.3 },
    FR: { geo: 0.8, sec: 0.4, eco: 0.7 },
    DE: { geo: 0.6, sec: 0.4, eco: 0.7 },
    CN: { geo: 0.2, sec: 0.5, eco: 0.7 },
    IR: { geo: 0.2, sec: 0.6, eco: 0.4 },
  },
  AU: {
    AU: { geo: 1.0, sec: 1.0, eco: 1.0 },
    CN: { geo: 0.4, sec: 0.7, eco: 0.9 },
    ID: { geo: 0.8, sec: 0.4, eco: 0.5 },
    US: { geo: 0.3, sec: 0.7, eco: 0.6 },
    JP: { geo: 0.4, sec: 0.3, eco: 0.6 },
    NZ: { geo: 0.9, sec: 0.2, eco: 0.5 },
    PH: { geo: 0.5, sec: 0.3, eco: 0.3 },
  },
  IN: {
    IN: { geo: 1.0, sec: 1.0, eco: 1.0 },
    PK: { geo: 0.9, sec: 1.0, eco: 0.3 },
    CN: { geo: 0.8, sec: 0.8, eco: 0.7 },
    AF: { geo: 0.7, sec: 0.6, eco: 0.2 },
    BD: { geo: 0.8, sec: 0.4, eco: 0.4 },
    LK: { geo: 0.7, sec: 0.3, eco: 0.3 },
    US: { geo: 0.2, sec: 0.5, eco: 0.6 },
    SA: { geo: 0.3, sec: 0.3, eco: 0.7 },
    IR: { geo: 0.4, sec: 0.4, eco: 0.5 },
  },
  BR: {
    BR: { geo: 1.0, sec: 1.0, eco: 1.0 },
    VE: { geo: 0.8, sec: 0.5, eco: 0.4 },
    AR: { geo: 0.8, sec: 0.3, eco: 0.6 },
    CO: { geo: 0.7, sec: 0.4, eco: 0.4 },
    US: { geo: 0.3, sec: 0.5, eco: 0.7 },
    CN: { geo: 0.2, sec: 0.3, eco: 0.8 },
  },
};

export const SUPPORTED_HOME_COUNTRIES = Object.keys(IMPACT);

export const TOPIC_WEIGHTS: Record<string, ImpactFactors> = {
  conflict:  { geo: 0.35, sec: 0.45, eco: 0.20 },
  terror:    { geo: 0.40, sec: 0.40, eco: 0.20 },
  coup:      { geo: 0.30, sec: 0.50, eco: 0.20 },
  sanctions: { geo: 0.20, sec: 0.25, eco: 0.55 },
  cyber:     { geo: 0.20, sec: 0.30, eco: 0.50 },
  protest:   { geo: 0.40, sec: 0.30, eco: 0.30 },
  diplomacy: { geo: 0.30, sec: 0.40, eco: 0.30 },
  maritime:  { geo: 0.40, sec: 0.30, eco: 0.30 },
  disaster:  { geo: 0.60, sec: 0.10, eco: 0.30 },
  health:    { geo: 0.50, sec: 0.10, eco: 0.40 },
  unknown:   { geo: 0.33, sec: 0.34, eco: 0.33 },
};

const DEFAULT_FACTOR = 0.5;

export function calcImpactFactor(
  eventCountry: string,
  topic: string,
  homeCountry = "KR",
): number {
  const countryFactors = IMPACT[homeCountry];
  if (!countryFactors) return DEFAULT_FACTOR;
  const f = countryFactors[eventCountry];
  if (!f) return DEFAULT_FACTOR;
  const w = TOPIC_WEIGHTS[topic] || TOPIC_WEIGHTS.unknown;
  return w.geo * f.geo + w.sec * f.sec + w.eco * f.eco;
}

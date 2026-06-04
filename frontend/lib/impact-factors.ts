import generatedData from "./impact-factors.generated.json";

export interface ImpactFactors {
  geo: number;
  sec: number;
  eco: number;
}

// Generated JSON에서 데이터 로드 (scripts/sync_impact_factors.py로 동기화)
export const IMPACT: Record<string, Record<string, ImpactFactors>> =
  generatedData.impact as Record<string, Record<string, ImpactFactors>>;

export const SUPPORTED_HOME_COUNTRIES = Object.keys(IMPACT);

export const TOPIC_WEIGHTS: Record<string, ImpactFactors> =
  generatedData.topic_weights as Record<string, ImpactFactors>;

const DEFAULT_FACTOR = generatedData.default_factor;

export function calcImpactFactor(
  eventCountry: string,
  topic: string,
  homeCountry = "KR",
): number {
  // BASIC 모드: homeCountry가 빈 문자열이면 raw KScore (factor=1.0)
  if (!homeCountry) return 1.0;
  const countryFactors = IMPACT[homeCountry];
  if (!countryFactors) return DEFAULT_FACTOR;
  const f = countryFactors[eventCountry];
  if (!f) return DEFAULT_FACTOR;
  const w = TOPIC_WEIGHTS[topic] || TOPIC_WEIGHTS.unknown;
  return w.geo * f.geo + w.sec * f.sec + w.eco * f.eco;
}

import { calcImpactFactor } from "@/lib/impact-factors";
import type { Lang } from "@/lib/i18n";

// ── 공통 타입 ─────────────────────────────────────────────────────────────
export interface TrendingItem {
  id: number;
  keyword: string;
  keyword_ko?: string | null;
  kscore: number;
  raw_score?: number;
  topic: string | null;
  country_codes: string[];
  cluster_ids?: string[];
  event_count?: number;
  severity?: number;
  reason?: string;
  calculated_at?: string;
  first_event_at?: string | null;
  independent_sources?: number;
  kscore_delta_24h?: number | null;
  is_spike?: boolean;
  confidence?: number;
}

// ── 토픽 컬러 ─────────────────────────────────────────────────────────────
export const TOPIC_COLORS: Record<string, string> = {
  conflict:  "bg-red-500/20 text-red-600 dark:text-red-400",
  terror:    "bg-red-700/20 text-red-700 dark:text-red-600",
  coup:      "bg-purple-500/20 text-purple-600 dark:text-purple-400",
  sanctions: "bg-blue-500/20 text-blue-600 dark:text-blue-400",
  cyber:     "bg-cyan-500/20 text-cyan-600 dark:text-cyan-400",
  protest:   "bg-orange-500/20 text-orange-600 dark:text-orange-400",
  diplomacy: "bg-green-500/20 text-green-600 dark:text-green-400",
  maritime:  "bg-teal-500/20 text-teal-600 dark:text-teal-400",
  disaster:  "bg-sky-500/20 text-sky-600 dark:text-sky-400",
  health:    "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400",
  unknown:   "bg-muted text-muted-foreground",
};

// ── KScore 유틸리티 ──────────────────────────────────────────────────────
/** KScore 반올림: 표시값과 색상 판별에 동일한 값 사용 */
export function roundKScore(kscore: number): number {
  return Math.round(kscore * 100) / 100;
}

/** 개인화 KScore: kscore(decay 포함) × impact_factor */
export function personalizedKScore(item: TrendingItem, homeCountry: string): number {
  const country = item.country_codes?.[0] || "";
  const factor = calcImpactFactor(country, item.topic || "unknown", homeCountry);
  return Math.round(item.kscore * factor * 100) / 100;
}

/** KScore에 따른 카드 좌측 강조선 색 (0-10 스케일, 5단계) */
export function kscoreAccent(kscore?: number): string {
  if (!kscore) return "border-l-border";
  const k = roundKScore(kscore);
  if (k >= 8) return "border-l-red-900";
  if (k >= 6) return "border-l-red-500";
  if (k >= 4) return "border-l-orange-500";
  if (k >= 2) return "border-l-amber-500";
  return "border-l-emerald-500";
}

/** KScore 상태 뱃지 — 색상 + 라벨 (0-10 스케일, 5단계) */
export function getKScoreBadge(kscore: number, lang: "ko" | "en"): { label: string; bg: string; text: string; glow: string } {
  const k = roundKScore(kscore);
  if (k >= 8) return {
    label: lang === "ko" ? "극심" : "Extreme",
    bg: "bg-red-900/20", text: "text-red-700 dark:text-red-300",
    glow: "shadow-red-900/30 shadow-lg",
  };
  if (k >= 6) return {
    label: lang === "ko" ? "심각" : "Severe",
    bg: "bg-red-500/15", text: "text-red-600 dark:text-red-400",
    glow: "shadow-red-500/20 shadow-lg",
  };
  if (k >= 4) return {
    label: lang === "ko" ? "경계" : "Alert",
    bg: "bg-orange-500/15", text: "text-orange-600 dark:text-orange-300",
    glow: "shadow-orange-500/15 shadow-md",
  };
  if (k >= 2) return {
    label: lang === "ko" ? "주의" : "Caution",
    bg: "bg-amber-500/10", text: "text-amber-600 dark:text-amber-300",
    glow: "",
  };
  return {
    label: lang === "ko" ? "안정" : "Stable",
    bg: "bg-emerald-500/10", text: "text-emerald-600 dark:text-emerald-400",
    glow: "",
  };
}

// ── 태그 헬퍼 ─────────────────────────────────────────────────────────────
/** NEW 태그 기준: 2시간 이내 */
export function isNew(isoString?: string | null): boolean {
  if (!isoString) return false;
  return Date.now() - new Date(isoString).getTime() < 2 * 60 * 60 * 1000;
}

/** RISING 태그 기준: 6시간 이내 + raw KScore >= 3 */
export function isRising(firstEventAt?: string | null, kscore?: number): boolean {
  if (!firstEventAt || !kscore) return false;
  const ageMs = Date.now() - new Date(firstEventAt).getTime();
  return ageMs < 6 * 60 * 60 * 1000 && kscore >= 3;
}

/** UPDATED 태그 기준: 생성은 2시간 이전이지만, 최근 2시간 내 이벤트 편입 */
export function isUpdated(firstEventAt?: string | null, calculatedAt?: string): boolean {
  if (!firstEventAt || !calculatedAt) return false;
  const now = Date.now();
  const firstAge = now - new Date(firstEventAt).getTime();
  const lastAge = now - new Date(calculatedAt).getTime();
  return firstAge > 2 * 60 * 60 * 1000 && lastAge < 2 * 60 * 60 * 1000;
}

/** 날짜+시분 포맷 */
export function formatFirstSeen(isoString?: string | null, lang: Lang = "ko"): string | null {
  if (!isoString) return null;
  const d = new Date(isoString);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const locale = lang === "en" ? "en-US" : "ko-KR";
  if (isToday) {
    const time = d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    return lang === "en" ? `First reported at ${time}` : `${time} 최초 발생`;
  }
  const date = d.toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  return lang === "en" ? `First reported ${date}` : `${date} 최초 발생`;
}

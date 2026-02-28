import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const TENSION_LEVELS = {
  0: { label: "안정", color: "text-emerald-400", bg: "bg-emerald-500/20", border: "border-emerald-500/50" },
  1: { label: "주의", color: "text-amber-300",   bg: "bg-amber-500/25",   border: "border-amber-400/60" },
  2: { label: "경계", color: "text-orange-300",  bg: "bg-orange-500/30",  border: "border-orange-400/70" },
  3: { label: "심각", color: "text-red-400",     bg: "bg-red-500/35",     border: "border-red-500/80" },
  4: { label: "극심", color: "text-red-100",     bg: "bg-red-900/50",     border: "border-red-800/90" },
} as const;

export const SOURCE_TIERS = {
  A: { label: "공식", color: "text-yellow-400", bg: "bg-yellow-400/10" },
  B: { label: "검증", color: "text-slate-400", bg: "bg-slate-400/10" },
  C: { label: "OSINT", color: "text-amber-700", bg: "bg-amber-700/10" },
  D: { label: "미확인", color: "text-gray-500", bg: "bg-gray-500/10" },
} as const;

/**
 * 제목 정리: 접두어 제거 + 해시태그 전용 쓰레기 제목 감지.
 * 의미있는 제목이면 그대로, 쓰레기면 빈 문자열 반환.
 */
export function stripTitlePrefix(title: string): string {
  // 1) "[국가] 토픽 · " 접두어 제거
  let cleaned = title.replace(/^\[.+?\]\s*.+?\s*·\s*/, "");
  // 2) 해시태그 제거
  cleaned = cleaned.replace(/#\S+/g, "").trim();
  // 3) 남은 글자가 4자 미만이면 쓰레기 → 빈 문자열
  if (cleaned.length < 4) return "";
  return cleaned;
}

export const TOPIC_LABELS: Record<string, string> = {
  conflict:  "분쟁",
  terror:    "테러",
  coup:      "쿠데타",
  sanctions: "제재",
  cyber:     "사이버",
  protest:   "시위",
  diplomacy: "외교",
  maritime:  "해상",
  disaster:  "재난·재해",
  health:    "감염병·보건",
  unknown:   "기타",
};

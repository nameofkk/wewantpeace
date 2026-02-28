import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const TENSION_LEVELS = {
  0: { label: "안정", color: "text-green-400",  bg: "bg-green-500/20",  border: "border-green-500/50" },
  1: { label: "관심", color: "text-blue-400",   bg: "bg-blue-500/20",   border: "border-blue-500/50" },
  2: { label: "주의", color: "text-yellow-300", bg: "bg-yellow-500/30", border: "border-yellow-400/60" },
  3: { label: "경계", color: "text-orange-300", bg: "bg-orange-500/40", border: "border-orange-400/80" },
  4: { label: "심각", color: "text-purple-300", bg: "bg-purple-500/40", border: "border-purple-400/80" },
  5: { label: "위기", color: "text-red-200",    bg: "bg-red-500/50",    border: "border-red-500/90" },
} as const;

export const SOURCE_TIERS = {
  A: { label: "공식", color: "text-yellow-400", bg: "bg-yellow-400/10" },
  B: { label: "검증", color: "text-slate-400", bg: "bg-slate-400/10" },
  C: { label: "OSINT", color: "text-amber-700", bg: "bg-amber-700/10" },
  D: { label: "미확인", color: "text-gray-500", bg: "bg-gray-500/10" },
} as const;

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

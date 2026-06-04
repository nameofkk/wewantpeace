"use client";

import { useAppStore } from "@/lib/store";

interface KScoreBarProps {
  kscore: number;   // 0 ~ 10 스케일
  showLabel?: boolean;
  className?: string;
}

const KSCORE_MAX = 10.0;  // 바 100% 기준값

function kscoreColor(k: number): string {
  if (k >= 8) return "from-red-900 to-red-800";
  if (k >= 6) return "from-red-500 to-red-400";
  if (k >= 4) return "from-orange-500 to-orange-400";
  if (k >= 2) return "from-amber-500 to-amber-400";
  return "from-emerald-500 to-emerald-400";
}

const LABELS = {
  ko: ["안정", "주의", "경계", "심각", "극심"],
  en: ["Stable", "Caution", "Alert", "Severe", "Extreme"],
} as const;

function kscoreLabel(rounded: number, lang: "ko" | "en"): string {
  const l = LABELS[lang];
  if (rounded >= 8) return l[4];
  if (rounded >= 6) return l[3];
  if (rounded >= 4) return l[2];
  if (rounded >= 2) return l[1];
  return l[0];
}

export function KScoreBar({ kscore, showLabel = true, className = "" }: KScoreBarProps) {
  const lang = useAppStore((s) => s.lang);
  const rounded = Math.round(kscore * 100) / 100;
  const pct = Math.min(100, Math.round((kscore / KSCORE_MAX) * 100));
  const gradient = kscoreColor(rounded);
  const label = kscoreLabel(rounded, lang);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showLabel && (
        <span className="text-[10px] text-muted-foreground w-10 shrink-0">KScore</span>
      )}
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${gradient} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-medium text-right w-16 shrink-0 text-muted-foreground">
        {rounded.toFixed(1)} <span className="text-foreground">{label}</span>
      </span>
    </div>
  );
}

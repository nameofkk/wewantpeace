"use client";

import { cn } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
import { useTensionMine, useTensionAll, type TensionAllItem } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Shield } from "lucide-react";

function tensionLabel(score: number, lang: "ko" | "en") {
  if (score >= 80) return lang === "ko" ? "극심" : "Extreme";
  if (score >= 60) return lang === "ko" ? "심각" : "Severe";
  if (score >= 40) return lang === "ko" ? "경계" : "Alert";
  if (score >= 20) return lang === "ko" ? "주의" : "Caution";
  return lang === "ko" ? "안정" : "Stable";
}

function tensionColor(score: number) {
  if (score >= 80) return { bar: "bg-red-900", text: "text-red-700 dark:text-red-300", bg: "bg-red-900/10" };
  if (score >= 60) return { bar: "bg-red-500", text: "text-red-600 dark:text-red-400", bg: "bg-red-500/10" };
  if (score >= 40) return { bar: "bg-orange-500", text: "text-orange-600 dark:text-orange-300", bg: "bg-orange-500/10" };
  if (score >= 20) return { bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-300", bg: "bg-amber-500/10" };
  return { bar: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10" };
}

export function RiskSummaryHeader() {
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);

  const { data: homeTension } = useTensionMine(homeCountry ? [homeCountry] : null);
  const { data: allTension } = useTensionAll();

  const homeData = Array.isArray(homeTension) ? homeTension[0] : null;
  const homeScore = homeData?.raw_score ?? 0;
  const color = tensionColor(homeScore);
  const label = tensionLabel(homeScore, lang);

  // 글로벌 현황 카운트
  const allItems = (allTension as TensionAllItem[] | undefined) ?? [];
  const extremeCount = allItems.filter((i) => i.raw_score >= 80).length;
  const severeCount = allItems.filter((i) => i.raw_score >= 60 && i.raw_score < 80).length;
  const alertCount = allItems.filter((i) => i.raw_score >= 40 && i.raw_score < 60).length;

  return (
    <div className="rounded-xl border border-border bg-card p-4 fade-in-up">
      {/* Home Country */}
      <div className="flex items-center gap-3 mb-3">
        <div className={cn("flex items-center justify-center h-10 w-10 rounded-lg", color.bg)}>
          <Shield className={cn("h-5 w-5", color.text)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-base">{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
            <span className="text-sm font-semibold truncate">
              {homeCountry ? getCountryName(homeCountry, lang) : (lang === "ko" ? "홈 국가 미설정" : "No home country")}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className={cn("text-xs font-bold", color.text)}>{label}</span>
            <span className={cn("text-lg font-bold tabular-nums", color.text)}>
              {homeScore}
            </span>
            <span className="text-[10px] text-muted-foreground">/100</span>
          </div>
        </div>
      </div>

      {/* Gauge Bar */}
      <div className="h-2 rounded-full bg-muted overflow-hidden mb-3">
        <div
          className={cn("h-full rounded-full transition-all duration-1000", color.bar)}
          style={{ width: `${Math.min(homeScore, 100)}%` }}
        />
      </div>

      {/* Global Overview */}
      <div className="flex items-center gap-3 text-[11px]">
        <span className="text-muted-foreground">🌐</span>
        {extremeCount > 0 && (
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-red-900" />
            <span className="text-red-700 dark:text-red-300 font-medium">
              {t(lang, "dash_extreme_count", { n: extremeCount })}
            </span>
          </span>
        )}
        {severeCount > 0 && (
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            <span className="text-red-600 dark:text-red-400 font-medium">
              {t(lang, "dash_severe_count", { n: severeCount })}
            </span>
          </span>
        )}
        {alertCount > 0 && (
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-orange-500" />
            <span className="text-orange-600 dark:text-orange-300 font-medium">
              {t(lang, "dash_alert_count", { n: alertCount })}
            </span>
          </span>
        )}
        {extremeCount === 0 && severeCount === 0 && alertCount === 0 && (
          <span className="text-emerald-600 dark:text-emerald-400 font-medium">
            {lang === "ko" ? "글로벌 안정" : "Global Stable"}
          </span>
        )}
      </div>
    </div>
  );
}

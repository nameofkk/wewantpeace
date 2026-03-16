"use client";

import { cn } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
import { useTensionMine, useTensionAll, type TensionAllItem } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Shield, Radio } from "lucide-react";
import { SectionHeader } from "./SectionHeader";
import { useCountUp } from "@/hooks/useCountUp";

function tensionLabel(score: number, lang: "ko" | "en") {
  if (score >= 80) return lang === "ko" ? "극심" : "Extreme";
  if (score >= 60) return lang === "ko" ? "심각" : "Severe";
  if (score >= 40) return lang === "ko" ? "경계" : "Alert";
  if (score >= 20) return lang === "ko" ? "주의" : "Caution";
  return lang === "ko" ? "안정" : "Stable";
}

function tensionColor(score: number) {
  if (score >= 80) return { bar: "bg-red-900", text: "text-red-700 dark:text-red-300", bg: "bg-red-900/10", ring: "ring-red-900/30" };
  if (score >= 60) return { bar: "bg-red-500", text: "text-red-600 dark:text-red-400", bg: "bg-red-500/10", ring: "ring-red-500/30" };
  if (score >= 40) return { bar: "bg-orange-500", text: "text-orange-600 dark:text-orange-300", bg: "bg-orange-500/10", ring: "ring-orange-500/30" };
  if (score >= 20) return { bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-300", bg: "bg-amber-500/10", ring: "ring-amber-500/30" };
  return { bar: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10", ring: "ring-emerald-500/30" };
}

export function RiskSummaryHeader() {
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);

  const { data: homeTension, dataUpdatedAt } = useTensionMine(homeCountry ? [homeCountry] : null);
  const { data: allTension } = useTensionAll();

  const homeData = Array.isArray(homeTension) ? homeTension[0] : null;
  const homeScore = homeData?.raw_score ?? 0;
  const color = tensionColor(homeScore);
  const label = tensionLabel(homeScore, lang);
  const animatedScore = useCountUp(homeScore, 1000);

  // 글로벌 현황 카운트
  const allItems = (allTension as TensionAllItem[] | undefined) ?? [];
  const extremeCount = allItems.filter((i) => i.raw_score >= 80).length;
  const severeCount = allItems.filter((i) => i.raw_score >= 60 && i.raw_score < 80).length;
  const alertCount = allItems.filter((i) => i.raw_score >= 40 && i.raw_score < 60).length;

  // 마지막 갱신 시간
  const updatedTime = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(lang === "ko" ? "ko-KR" : "en-US", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  return (
    <div>
      <SectionHeader
        icon={<Shield className="h-3.5 w-3.5 text-muted-foreground" />}
        titleKey="dash_home_tension"
        descKey="dash_risk_desc"
      />
      <div className="rounded-xl border border-border bg-card p-4 fade-in-up">
        {/* Home Country */}
        <div className="flex items-center gap-3 mb-3">
          <div className={cn("flex items-center justify-center h-12 w-12 rounded-xl ring-2", color.bg, color.ring)}>
            <span className="text-xl">{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-sm font-semibold truncate block">
              {homeCountry ? getCountryName(homeCountry, lang) : (lang === "ko" ? "홈 국가 미설정" : "No home country")}
            </span>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={cn("text-xs font-bold px-2 py-0.5 rounded-full", color.bg, color.text)}>
                {label}
              </span>
            </div>
          </div>
          <div className="text-right">
            <span className={cn("text-2xl font-bold tabular-nums leading-none", color.text)}>
              {Math.round(animatedScore)}
            </span>
            <span className="text-[10px] text-muted-foreground block">/100</span>
          </div>
        </div>

        {/* Gauge Bar */}
        <div className="h-2.5 rounded-full bg-muted overflow-hidden mb-3">
          <div
            className={cn("h-full rounded-full transition-all duration-1000 ease-out", color.bar)}
            style={{ width: `${Math.min(homeScore, 100)}%` }}
          />
        </div>

        {/* Global Overview */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 text-[11px]">
            <span className="text-muted-foreground">🌐</span>
            {extremeCount > 0 && (
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-red-900 animate-pulse" />
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
          {updatedTime && (
            <span className="flex items-center gap-1 text-[9px] text-muted-foreground/60">
              <Radio className="h-2.5 w-2.5" />
              {t(lang, "dash_last_updated", { time: updatedTime })}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

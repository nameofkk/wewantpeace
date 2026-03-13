"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useImpactBrief } from "@/lib/api";
import { t } from "@/lib/i18n";
import { TrendingUp, Plane, ShoppingCart, Briefcase, ChevronDown, ChevronUp, Info, Loader2 } from "lucide-react";

function riskColor(score: number) {
  if (score >= 75) return "text-red-700 dark:text-red-300";
  if (score >= 50) return "text-orange-600 dark:text-orange-300";
  if (score >= 25) return "text-amber-600 dark:text-amber-300";
  return "text-emerald-600 dark:text-emerald-400";
}

function riskBarColor(score: number) {
  if (score >= 75) return "bg-red-900";
  if (score >= 50) return "bg-orange-500";
  if (score >= 25) return "bg-amber-500";
  return "bg-emerald-500";
}

export function ImpactBriefCard({ clusterId }: { clusterId: string }) {
  const lang = useAppStore((s) => s.lang);
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, error } = useImpactBrief(expanded ? clusterId : undefined);

  // 403 = 플랜 부족
  const is403 = (error as any)?.status === 403;

  return (
    <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-card/80 transition-colors"
      >
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-blue-400" />
          <span className="text-xs font-bold">{t(lang, "dash_impact_brief")}</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 font-medium">Pro</span>
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-border/40">
          {isLoading && (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-xs text-muted-foreground">
                {lang === "ko" ? "AI 분석 중..." : "Analyzing..."}
              </span>
            </div>
          )}

          {is403 && (
            <div className="py-4 text-center">
              <p className="text-xs text-muted-foreground mb-2">
                {lang === "ko" ? "Pro 플랜 이상에서 이용 가능합니다" : "Available for Pro plan and above"}
              </p>
              <a
                href="/upgrade"
                className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
                style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
              >
                {t(lang, "dash_unlock_pro")}
              </a>
            </div>
          )}

          {isError && !is403 && (
            <p className="py-4 text-xs text-muted-foreground text-center">
              {lang === "ko" ? "분석을 불러올 수 없습니다" : "Failed to load analysis"}
            </p>
          )}

          {data && (
            <div className="space-y-3 mt-3">
              {/* Impact Score */}
              <div className="flex items-center gap-3">
                <span className={cn("text-2xl font-bold tabular-nums", riskColor(data.score))}>
                  {data.score}
                </span>
                <div className="flex-1">
                  <div className="h-2 rounded-full bg-muted overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all duration-1000", riskBarColor(data.score))}
                      style={{ width: `${data.score}%` }}
                    />
                  </div>
                  <p className="text-[9px] text-muted-foreground mt-0.5">{t(lang, "dash_impact_score")} /100</p>
                </div>
              </div>

              {/* Summary */}
              <p className="text-[11px] text-foreground/80 leading-relaxed">{data.summary}</p>

              {/* 3 dimensions */}
              <div className="space-y-2">
                <div className="flex items-start gap-2 rounded-lg bg-muted/20 p-2.5">
                  <Briefcase className="h-3.5 w-3.5 text-blue-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-[10px] font-bold text-blue-400 mb-0.5">
                      {lang === "ko" ? "경제" : "Economy"}
                    </p>
                    <p className="text-[11px] text-foreground/70 leading-relaxed">{data.economy}</p>
                  </div>
                </div>

                <div className="flex items-start gap-2 rounded-lg bg-muted/20 p-2.5">
                  <ShoppingCart className="h-3.5 w-3.5 text-orange-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-[10px] font-bold text-orange-400 mb-0.5">
                      {lang === "ko" ? "무역" : "Trade"}
                    </p>
                    <p className="text-[11px] text-foreground/70 leading-relaxed">{data.trade}</p>
                  </div>
                </div>

                <div className="flex items-start gap-2 rounded-lg bg-muted/20 p-2.5">
                  <Plane className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                  <div>
                    <p className="text-[10px] font-bold text-emerald-400 mb-0.5">
                      {lang === "ko" ? "여행" : "Travel"}
                    </p>
                    <p className="text-[11px] text-foreground/70 leading-relaxed">{data.travel}</p>
                  </div>
                </div>
              </div>

              {/* Data sources + AI disclaimer */}
              <div className="flex items-start gap-1.5 pt-1 border-t border-border/30">
                <Info className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
                <div>
                  <p className="text-[9px] text-muted-foreground">
                    {t(lang, "dash_ai_estimate")}
                  </p>
                  {data.data_sources.length > 0 && (
                    <p className="text-[9px] text-muted-foreground/60 mt-0.5">
                      {lang === "ko" ? "출처: " : "Sources: "}{data.data_sources.join(", ")}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

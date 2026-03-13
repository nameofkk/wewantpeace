"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useSectorAnalysis } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Sparkles, ChevronDown, ChevronUp, Info, Loader2, Lock } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

const RISK_COLORS: Record<string, { text: string; bg: string; bar: string }> = {
  critical: { text: "text-red-700 dark:text-red-300", bg: "bg-red-900/10", bar: "bg-red-900" },
  high: { text: "text-red-600 dark:text-red-400", bg: "bg-red-500/10", bar: "bg-red-500" },
  medium: { text: "text-orange-600 dark:text-orange-300", bg: "bg-orange-500/10", bar: "bg-orange-500" },
  low: { text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10", bar: "bg-emerald-500" },
};

const RISK_LABELS: Record<string, Record<string, string>> = {
  ko: { critical: "위험", high: "높음", medium: "보통", low: "낮음" },
  en: { critical: "Critical", high: "High", medium: "Medium", low: "Low" },
};

export function SectorImpactCard({ clusterId }: { clusterId: string }) {
  const lang = useAppStore((s) => s.lang);
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, error } = useSectorAnalysis(expanded ? clusterId : undefined);

  const is403 = (error as any)?.status === 403;

  return (
    <div>
      <SectionHeader
        icon={<Sparkles className="h-3.5 w-3.5 text-purple-400" />}
        titleKey="dash_sector_impact"
        descKey="dash_sector_desc"
        badge={{ label: "Pro+", color: "bg-purple-500/10 text-purple-400" }}
      />
      <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-card/80 transition-colors"
        >
          <span className="text-xs font-medium text-foreground/80">
            {expanded
              ? (lang === "ko" ? "접기" : "Collapse")
              : (lang === "ko" ? "산업별 리스크 분석 보기" : "View sector risk analysis")}
          </span>
          {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </button>

        {expanded && (
          <div className="px-4 pb-4 border-t border-border/40">
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-purple-400" />
              </div>
            )}

            {is403 && (
              <div className="py-4 text-center">
                <Lock className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground mb-2">
                  {lang === "ko" ? "Pro+ 플랜에서 이용 가능합니다" : "Available for Pro+ plan"}
                </p>
                <a
                  href="/upgrade"
                  className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
                  style={{ background: "linear-gradient(to right, #7c3aed, #6366f1)" }}
                >
                  {t(lang, "dash_unlock_pro_plus")}
                </a>
              </div>
            )}

            {isError && !is403 && (
              <p className="py-4 text-xs text-muted-foreground text-center">
                {lang === "ko" ? "분석을 불러올 수 없습니다" : "Failed to load analysis"}
              </p>
            )}

            {data && (
              <div className="space-y-2 mt-3">
                {/* Overall Risk */}
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-[10px] text-muted-foreground">
                    {lang === "ko" ? "전체 리스크:" : "Overall Risk:"}
                  </span>
                  <span className={cn(
                    "text-xs font-bold px-2 py-0.5 rounded-full",
                    RISK_COLORS[data.overall_risk]?.bg,
                    RISK_COLORS[data.overall_risk]?.text,
                  )}>
                    {RISK_LABELS[lang]?.[data.overall_risk] || data.overall_risk}
                  </span>
                </div>

                {/* Sector list */}
                {data.sectors.map((sector, idx) => {
                  const colors = RISK_COLORS[sector.risk_level] || RISK_COLORS.low;
                  return (
                    <div
                      key={sector.sector}
                      className="rounded-lg bg-muted/20 p-2.5 fade-in-up"
                      style={{ animationDelay: `${idx * 50}ms` }}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-[11px] font-semibold">{sector.sector}</span>
                        <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded-full", colors.bg, colors.text)}>
                          {RISK_LABELS[lang]?.[sector.risk_level] || sector.risk_level}
                        </span>
                      </div>

                      {/* Trade dependency bar */}
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[9px] text-muted-foreground w-16 shrink-0">
                          {lang === "ko" ? "교역 의존" : "Trade dep."}
                        </span>
                        <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                          <div
                            className={cn("h-full rounded-full transition-all duration-700 ease-out", colors.bar)}
                            style={{ width: `${Math.round(sector.trade_dependency * 100)}%` }}
                          />
                        </div>
                        <span className="text-[9px] text-muted-foreground tabular-nums w-8 text-right">
                          {Math.round(sector.trade_dependency * 100)}%
                        </span>
                      </div>

                      <p className="text-[10px] text-muted-foreground/80 leading-relaxed">{sector.description}</p>
                    </div>
                  );
                })}

                {/* AI disclaimer */}
                <div className="flex items-start gap-1.5 pt-2 border-t border-border/30">
                  <Info className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
                  <p className="text-[9px] text-muted-foreground">
                    {t(lang, "dash_ai_estimate")}
                    {" · "}
                    {lang === "ko" ? "출처: World Bank, UN Comtrade" : "Sources: World Bank, UN Comtrade"}
                  </p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

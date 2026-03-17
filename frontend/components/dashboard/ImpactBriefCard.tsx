"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useImpactSummary, useImpactBrief } from "@/lib/api";
import { t } from "@/lib/i18n";
import { getFlag } from "@/lib/countries";
import {
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Loader2,
  Info,
  Lock,
  Briefcase,
  ShoppingCart,
  Plane,
  Shield,
} from "lucide-react";
import { useCountUp } from "@/hooks/useCountUp";
import dynamic from "next/dynamic";

const RadialBarChart = dynamic(
  () => import("recharts").then((m) => m.RadialBarChart),
  { ssr: false },
);
const RadialBar = dynamic(
  () => import("recharts").then((m) => m.RadialBar),
  { ssr: false },
);
const PolarAngleAxis = dynamic(
  () => import("recharts").then((m) => m.PolarAngleAxis),
  { ssr: false },
);

function scoreColor(score: number) {
  if (score >= 75) return "#dc2626";
  if (score >= 50) return "#f97316";
  if (score >= 25) return "#f59e0b";
  return "#10b981";
}

function scoreLabel(level: string, lang: string) {
  const labels: Record<string, Record<string, string>> = {
    ko: { high: "높음", elevated: "경계", guarded: "주의", low: "안정" },
    en: { high: "High", elevated: "Elevated", guarded: "Guarded", low: "Low" },
  };
  return labels[lang]?.[level] || labels["en"]?.[level] || level;
}

const DIM_CONFIG = [
  { key: "economy" as const, icon: Briefcase, color: "text-blue-400", bg: "bg-blue-500/8" },
  { key: "trade" as const, icon: ShoppingCart, color: "text-orange-400", bg: "bg-orange-500/8" },
  { key: "travel" as const, icon: Plane, color: "text-emerald-400", bg: "bg-emerald-500/8" },
] as const;

const DIM_LABELS: Record<string, Record<string, string>> = {
  ko: { economy: "경제", trade: "무역", travel: "여행" },
  en: { economy: "Economy", trade: "Trade", travel: "Travel" },
};

const DEMO_BRIEF = {
  score: 72,
  level: "elevated",
  summary_ko: "글로벌 분쟁 확산으로 에너지·곡물 공급망에 중대한 영향이 감지됩니다. 원유 및 천연가스 가격 상승 압력이 지속되고 있습니다.",
  summary_en: "Significant supply chain impacts detected in energy and grain sectors due to escalating global conflicts. Upward pressure on oil and gas prices continues.",
  economy_ko: "에너지 의존도가 높은 산업을 중심으로 비용 상승 우려",
  economy_en: "Cost concerns rising in energy-dependent industries",
  trade_ko: "곡물·원자재 수입 경로 다변화 필요성 증가",
  trade_en: "Growing need for grain/commodity import route diversification",
  travel_ko: "분쟁 지역 인접국 여행 경보 단계 상향 가능성",
  travel_en: "Potential travel advisory upgrades for countries near conflict zones",
  data_sources: ["AI Analysis", "World Bank", "UN Comtrade"],
};

export function ImpactBriefCard({ clusterId }: { clusterId?: string } = {}) {
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  // clusterId가 있으면 per-cluster 분석, 없으면 홀리스틱 summary
  const summaryQuery = useImpactSummary(homeCountry, lang, !clusterId && expanded);
  const briefQuery = useImpactBrief(clusterId && expanded ? clusterId : undefined, homeCountry, lang);

  const isPerCluster = !!clusterId;
  const activeQuery = isPerCluster ? briefQuery : summaryQuery;
  const { isLoading, isError } = activeQuery;

  // 통합 데이터 형태로 변환
  const data = isPerCluster && briefQuery.data
    ? {
        score: briefQuery.data.score,
        level: briefQuery.data.score >= 75 ? "high" : briefQuery.data.score >= 50 ? "elevated" : briefQuery.data.score >= 25 ? "guarded" : "low",
        summary: briefQuery.data.summary,
        economy: briefQuery.data.economy,
        trade: briefQuery.data.trade,
        travel: briefQuery.data.travel,
        top_issues: [],
        affected_sectors_count: 0,
        critical_issues_count: 0,
        total_active_issues: 0,
        data_sources: briefQuery.data.data_sources,
      }
    : summaryQuery.data
      ? summaryQuery.data
      : null;

  const animatedScore = useCountUp(data?.score ?? 0, 900);
  const color = scoreColor(data?.score ?? 0);
  const hasPro = !!(data?.economy || data?.trade || data?.travel);

  return (
    <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
      {/* 헤더 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-muted/5 transition-colors"
      >
        <div className="w-1 h-4 rounded-full bg-blue-500 shrink-0" />
        <h3 className="text-xs font-bold text-foreground flex-1 text-left">
          {lang === "ko" ? "영향 분석" : "Impact Analysis"}
        </h3>
        <span className="text-[8px] px-1.5 py-0.5 rounded border border-border text-muted-foreground font-medium shrink-0">Pro</span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-border">
          {isLoading && (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          )}

          {isError && (() => {
            const errStatus = (activeQuery.error as any)?.status;
            const isAuthOrPlan = errStatus === 401 || errStatus === 403;
            if (isAuthOrPlan) {
              const demoScore = DEMO_BRIEF.score;
              const demoColor = scoreColor(demoScore);
              const demoSummary = lang === "ko" ? DEMO_BRIEF.summary_ko : DEMO_BRIEF.summary_en;
              const demoDims = {
                economy: lang === "ko" ? DEMO_BRIEF.economy_ko : DEMO_BRIEF.economy_en,
                trade: lang === "ko" ? DEMO_BRIEF.trade_ko : DEMO_BRIEF.trade_en,
                travel: lang === "ko" ? DEMO_BRIEF.travel_ko : DEMO_BRIEF.travel_en,
              };
              return (
                <div className="relative mt-3">
                  {/* Blurred demo content */}
                  <div className="opacity-60" style={{ filter: "blur(3px)" }}>
                    <div className="space-y-3">
                      <div className="flex items-center gap-3">
                        <div className="relative w-16 h-16 shrink-0">
                          <RadialBarChart
                            width={64} height={64} cx={32} cy={32}
                            innerRadius={22} outerRadius={30} barSize={6}
                            data={[{ value: demoScore, fill: demoColor }]}
                            startAngle={90} endAngle={-270}
                          >
                            <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
                            <RadialBar background={{ fill: "hsl(var(--muted) / 0.3)" }} dataKey="value" cornerRadius={3} />
                          </RadialBarChart>
                          <div className="absolute inset-0 flex flex-col items-center justify-center">
                            <span className="text-sm font-bold tabular-nums leading-none" style={{ color: demoColor }}>
                              {demoScore}
                            </span>
                          </div>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5 mb-1">
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full" style={{ color: demoColor, backgroundColor: `${demoColor}15` }}>
                              {scoreLabel(DEMO_BRIEF.level, lang)}
                            </span>
                          </div>
                          <p className="text-[11px] text-foreground/70 leading-relaxed">{demoSummary}</p>
                        </div>
                      </div>
                      <div className="space-y-2">
                        {DIM_CONFIG.map((dim, idx) => (
                          <div key={dim.key} className={cn("rounded-lg p-2.5", dim.bg)}>
                            <div className="flex items-center gap-1.5 mb-1">
                              <dim.icon className={cn("h-3 w-3 shrink-0", dim.color)} />
                              <span className={cn("text-[10px] font-bold", dim.color)}>
                                {DIM_LABELS[lang]?.[dim.key] || dim.key}
                              </span>
                            </div>
                            <p className="text-[10px] text-foreground/70 leading-relaxed">
                              {demoDims[dim.key]}
                            </p>
                          </div>
                        ))}
                      </div>
                      <div className="flex items-start gap-1.5 pt-2 border-t border-border/30">
                        <Info className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
                        <div className="text-[9px] text-muted-foreground">
                          <span>{t(lang, "dash_ai_estimate")}</span>
                          <span className="text-muted-foreground/60">{" · "}{DEMO_BRIEF.data_sources.join(", ")}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                  {/* Upgrade overlay */}
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/30 rounded-lg">
                    <Lock className="h-5 w-5 text-muted-foreground mb-2" />
                    <p className="text-xs text-muted-foreground mb-2 font-medium">
                      {lang === "ko"
                        ? "Pro 플랜에서 이용 가능합니다"
                        : "Available for Pro plan"}
                    </p>
                    <a
                      href="/upgrade?source=demo_impact"
                      className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      {t(lang, "dash_unlock_pro")}
                    </a>
                  </div>
                </div>
              );
            }
            return (
              <p className="py-4 text-xs text-muted-foreground text-center">
                {lang === "ko" ? "분석을 불러올 수 없습니다" : "Failed to load analysis"}
              </p>
            );
          })()}

          {data && (
            <div className="space-y-3 mt-3">
              {/* Score + Summary */}
              <div className="flex items-center gap-3">
                <div className="relative w-16 h-16 shrink-0">
                  <RadialBarChart
                    width={64}
                    height={64}
                    cx={32}
                    cy={32}
                    innerRadius={22}
                    outerRadius={30}
                    barSize={6}
                    data={[{ value: data.score, fill: color }]}
                    startAngle={90}
                    endAngle={-270}
                  >
                    <PolarAngleAxis
                      type="number"
                      domain={[0, 100]}
                      angleAxisId={0}
                      tick={false}
                    />
                    <RadialBar
                      background={{ fill: "hsl(var(--muted) / 0.3)" }}
                      dataKey="value"
                      cornerRadius={3}
                    />
                  </RadialBarChart>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="text-sm font-bold tabular-nums leading-none" style={{ color }}>
                      {Math.round(animatedScore)}
                    </span>
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span
                      className="text-[9px] font-bold px-1.5 py-0.5 rounded-full"
                      style={{ color, backgroundColor: `${color}15` }}
                    >
                      {scoreLabel(data.level, lang)}
                    </span>
                  </div>
                  <p className="text-[11px] text-foreground/70 leading-relaxed">
                    {data.summary}
                  </p>
                </div>
              </div>

              {/* Pro: Economy/Trade/Travel */}
              {hasPro && (
                <div className="space-y-2">
                  {DIM_CONFIG.map((dim, idx) => {
                    const text = data[dim.key];
                    if (!text) return null;
                    return (
                      <div
                        key={dim.key}
                        className={cn("rounded-lg p-2.5 fade-in-up", dim.bg)}
                        style={{ animationDelay: `${idx * 60}ms` }}
                      >
                        <div className="flex items-center gap-1.5 mb-1">
                          <dim.icon className={cn("h-3 w-3 shrink-0", dim.color)} />
                          <span className={cn("text-[10px] font-bold", dim.color)}>
                            {DIM_LABELS[lang]?.[dim.key] || dim.key}
                          </span>
                        </div>
                        <p className="text-[10px] text-foreground/70 leading-relaxed">
                          {text}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Non-Pro: Demo data + blur + Upgrade CTA */}
              {!hasPro && (
                <div className="relative">
                  <div className="opacity-60" style={{ filter: "blur(3px)" }}>
                    <div className="space-y-2">
                      {DIM_CONFIG.map((dim) => {
                        const demoText = lang === "ko"
                          ? DEMO_BRIEF[`${dim.key}_ko` as keyof typeof DEMO_BRIEF]
                          : DEMO_BRIEF[`${dim.key}_en` as keyof typeof DEMO_BRIEF];
                        return (
                          <div key={dim.key} className={cn("rounded-lg p-2.5", dim.bg)}>
                            <div className="flex items-center gap-1.5 mb-1">
                              <dim.icon className={cn("h-3 w-3 shrink-0", dim.color)} />
                              <span className={cn("text-[10px] font-bold", dim.color)}>
                                {DIM_LABELS[lang]?.[dim.key] || dim.key}
                              </span>
                            </div>
                            <p className="text-[10px] text-foreground/70 leading-relaxed">
                              {demoText}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/30 rounded-lg">
                    <Lock className="h-5 w-5 text-muted-foreground mb-2" />
                    <p className="text-[10px] text-muted-foreground mb-2 font-medium">
                      {lang === "ko"
                        ? "경제/무역/여행 상세 분석은 Pro 플랜에서 이용 가능합니다"
                        : "Detailed economy/trade/travel analysis available on Pro plan"}
                    </p>
                    <a
                      href="/upgrade"
                      className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      {t(lang, "dash_unlock_pro")}
                    </a>
                  </div>
                </div>
              )}

              {/* Footer */}
              <div className="flex items-start gap-1.5 pt-2 border-t border-border/30">
                <Info className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
                <div className="text-[9px] text-muted-foreground">
                  <span>{t(lang, "dash_ai_estimate")}</span>
                  {data.data_sources.length > 0 && (
                    <span className="text-muted-foreground/60">
                      {" · "}
                      {data.data_sources.join(", ")}
                    </span>
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

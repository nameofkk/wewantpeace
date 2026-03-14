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
  Briefcase,
  ShoppingCart,
  Plane,
  AlertTriangle,
  Shield,
} from "lucide-react";
import { SectionHeader } from "./SectionHeader";
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

export function ImpactBriefCard({ clusterId }: { clusterId?: string } = {}) {
  const lang = useAppStore((s) => s.lang);
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  // clusterId가 있으면 per-cluster 분석, 없으면 홀리스틱 summary
  const summaryQuery = useImpactSummary(undefined, !clusterId && expanded);
  const briefQuery = useImpactBrief(clusterId && expanded ? clusterId : undefined);

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
    <div>
      <SectionHeader
        icon={<TrendingUp className="h-3.5 w-3.5 text-blue-400" />}
        titleKey="dash_impact_brief"
        descKey="dash_impact_brief_desc"
      />
      <div className="rounded-xl border border-border bg-card fade-in-up overflow-hidden">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-card/80 transition-colors"
        >
          <span className="text-xs font-medium text-foreground/80">
            {expanded
              ? lang === "ko"
                ? "접기"
                : "Collapse"
              : lang === "ko"
                ? "나에게 미치는 영향 보기"
                : "View impact on me"}
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </button>

        {expanded && (
          <div className="px-4 pb-4 border-t border-border/40">
            {isLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="flex flex-col items-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin text-blue-400" />
                  <span className="text-xs text-muted-foreground">
                    {lang === "ko" ? "영향도 분석 중..." : "Analyzing impact..."}
                  </span>
                </div>
              </div>
            )}

            {isError && (
              <p className="py-4 text-xs text-muted-foreground text-center">
                {lang === "ko"
                  ? "분석을 불러올 수 없습니다"
                  : "Failed to load analysis"}
              </p>
            )}

            {data && (
              <div className="space-y-4 mt-3">
                {/* Score Gauge + Summary */}
                <div className="flex items-center gap-4">
                  <div className="relative w-20 h-20 shrink-0">
                    <RadialBarChart
                      width={80}
                      height={80}
                      cx={40}
                      cy={40}
                      innerRadius={28}
                      outerRadius={38}
                      barSize={8}
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
                        cornerRadius={4}
                      />
                    </RadialBarChart>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span
                        className="text-lg font-bold tabular-nums leading-none"
                        style={{ color }}
                      >
                        {Math.round(animatedScore)}
                      </span>
                      <span className="text-[8px] text-muted-foreground mt-0.5">
                        /100
                      </span>
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span
                        className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                        style={{
                          color,
                          backgroundColor: `${color}15`,
                        }}
                      >
                        {scoreLabel(data.level, lang)}
                      </span>
                      <span className="text-[10px] text-muted-foreground">
                        {t(lang, "dash_impact_score")}
                      </span>
                    </div>
                    <p className="text-[11px] text-foreground/80 leading-relaxed line-clamp-3">
                      {data.summary}
                    </p>
                  </div>
                </div>

                {/* Stats Row */}
                <div className="flex items-center gap-2">
                  <div className="flex-1 rounded-lg bg-muted/15 px-3 py-2 text-center">
                    <p className="text-lg font-bold tabular-nums">{data.total_active_issues}</p>
                    <p className="text-[9px] text-muted-foreground">
                      {lang === "ko" ? "활성 이슈" : "Active Issues"}
                    </p>
                  </div>
                  <div className="flex-1 rounded-lg bg-muted/15 px-3 py-2 text-center">
                    <p className="text-lg font-bold tabular-nums text-red-400">
                      {data.critical_issues_count}
                    </p>
                    <p className="text-[9px] text-muted-foreground">
                      {lang === "ko" ? "고영향" : "High Impact"}
                    </p>
                  </div>
                  <div className="flex-1 rounded-lg bg-muted/15 px-3 py-2 text-center">
                    <p className="text-lg font-bold tabular-nums text-orange-400">
                      {data.affected_sectors_count}
                    </p>
                    <p className="text-[9px] text-muted-foreground">
                      {lang === "ko" ? "영향 산업" : "Sectors"}
                    </p>
                  </div>
                </div>

                {/* Top Issues (All Plans) */}
                {data.top_issues.length > 0 && (
                  <div>
                    <p className="text-[10px] font-bold text-muted-foreground mb-1.5">
                      {lang === "ko"
                        ? "나에게 영향이 큰 이슈"
                        : "Issues affecting you most"}
                    </p>
                    <div className="space-y-1">
                      {data.top_issues.map((issue, idx) => (
                        <div
                          key={issue.cluster_id}
                          onClick={() => router.push(`/issues/${issue.cluster_id}`)}
                          className="flex items-center gap-2 rounded-lg bg-muted/10 px-2.5 py-2 cursor-pointer hover:bg-muted/20 transition-colors fade-in-up"
                          style={{ animationDelay: `${idx * 40}ms` }}
                        >
                          <span className="text-[10px] font-bold text-muted-foreground w-4">
                            {idx + 1}
                          </span>
                          <span className="text-[11px]">
                            {issue.country_codes.map((cc) => getFlag(cc)).join(" ")}
                          </span>
                          <span className="flex-1 text-[11px] font-medium truncate">
                            {issue.title}
                          </span>
                          <span
                            className="text-[9px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
                            style={{
                              color: scoreColor(issue.impact_score),
                              backgroundColor: `${scoreColor(issue.impact_score)}15`,
                            }}
                          >
                            {issue.impact_score}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Pro: Economy/Trade/Travel Detail */}
                {hasPro && (
                  <div className="space-y-2">
                    <p className="text-[10px] font-bold text-muted-foreground flex items-center gap-1">
                      <Shield className="h-3 w-3 text-blue-400" />
                      {lang === "ko" ? "상세 영향 분석" : "Detailed Impact Analysis"}
                      <span className="text-[8px] px-1 py-0.5 rounded-full bg-blue-500/10 text-blue-400 font-bold">
                        Pro
                      </span>
                    </p>
                    {DIM_CONFIG.map((dim, idx) => {
                      const text = data[dim.key];
                      if (!text) return null;
                      return (
                        <div
                          key={dim.key}
                          className={cn(
                            "rounded-lg p-3 fade-in-up",
                            dim.bg,
                          )}
                          style={{ animationDelay: `${idx * 60}ms` }}
                        >
                          <div className="flex items-center gap-2 mb-1.5">
                            <dim.icon
                              className={cn("h-3.5 w-3.5 shrink-0", dim.color)}
                            />
                            <span
                              className={cn("text-[10px] font-bold", dim.color)}
                            >
                              {DIM_LABELS[lang]?.[dim.key] || dim.key}
                            </span>
                          </div>
                          <p className="text-[11px] text-foreground/70 leading-relaxed">
                            {text}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Non-Pro: Upgrade CTA */}
                {!hasPro && (
                  <div className="rounded-lg bg-gradient-to-r from-blue-500/5 to-indigo-500/5 border border-blue-500/10 p-3 text-center fade-in-up">
                    <p className="text-[10px] text-muted-foreground mb-2">
                      {lang === "ko"
                        ? "경제/무역/여행 상세 분석은 Pro 플랜에서 이용 가능합니다"
                        : "Detailed economy/trade/travel analysis available on Pro plan"}
                    </p>
                    <a
                      href="/upgrade"
                      className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
                      style={{
                        background: "linear-gradient(to right, #2563eb, #6366f1)",
                      }}
                    >
                      {t(lang, "dash_unlock_pro")}
                    </a>
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
    </div>
  );
}

"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useImpactBrief } from "@/lib/api";
import { t } from "@/lib/i18n";
import {
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Loader2,
  Lock,
  Info,
  Briefcase,
  ShoppingCart,
  Plane,
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

function scoreLabel(score: number, lang: string) {
  if (lang === "ko") {
    if (score >= 75) return "높음";
    if (score >= 50) return "경계";
    if (score >= 25) return "주의";
    return "낮음";
  }
  if (score >= 75) return "High";
  if (score >= 50) return "Elevated";
  if (score >= 25) return "Guarded";
  return "Low";
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

export function ImpactBriefCard({ clusterId }: { clusterId: string }) {
  const lang = useAppStore((s) => s.lang);
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, error } = useImpactBrief(
    expanded ? clusterId : undefined,
  );

  const is403 = (error as any)?.status === 403;
  const animatedScore = useCountUp(data?.score ?? 0, 900);
  const color = scoreColor(data?.score ?? 0);

  return (
    <div>
      <SectionHeader
        icon={<TrendingUp className="h-3.5 w-3.5 text-blue-400" />}
        titleKey="dash_impact_brief"
        descKey="dash_impact_brief_desc"
        badge={{ label: "Pro", color: "bg-blue-500/10 text-blue-400" }}
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
                ? "AI 영향도 분석 보기"
                : "View AI impact analysis"}
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
                    {lang === "ko" ? "AI 분석 중..." : "Analyzing..."}
                  </span>
                </div>
              </div>
            )}

            {is403 && (
              <div className="py-4 text-center">
                <Lock className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground mb-2">
                  {lang === "ko"
                    ? "Pro 플랜 이상에서 이용 가능합니다"
                    : "Available for Pro plan and above"}
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

            {isError && !is403 && (
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
                        {scoreLabel(data.score, lang)}
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

                {/* 3 Dimensions */}
                <div className="space-y-2">
                  {DIM_CONFIG.map((dim, idx) => (
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
                        {data[dim.key]}
                      </p>
                    </div>
                  ))}
                </div>

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

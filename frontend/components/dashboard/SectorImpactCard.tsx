"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useSectorAnalysis } from "@/lib/api";
import { t } from "@/lib/i18n";
import {
  Sparkles,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  Lock,
} from "lucide-react";
import { SectionHeader } from "./SectionHeader";
import dynamic from "next/dynamic";

const BarChart = dynamic(
  () => import("recharts").then((m) => m.BarChart),
  { ssr: false },
);
const Bar = dynamic(
  () => import("recharts").then((m) => m.Bar),
  { ssr: false },
);
const XAxis = dynamic(
  () => import("recharts").then((m) => m.XAxis),
  { ssr: false },
);
const YAxis = dynamic(
  () => import("recharts").then((m) => m.YAxis),
  { ssr: false },
);
const ResponsiveContainer = dynamic(
  () => import("recharts").then((m) => m.ResponsiveContainer),
  { ssr: false },
);
const Cell = dynamic(
  () => import("recharts").then((m) => m.Cell),
  { ssr: false },
);
const Tooltip = dynamic(
  () => import("recharts").then((m) => m.Tooltip),
  { ssr: false },
);

const RISK_COLORS: Record<string, { text: string; bg: string; bar: string }> = {
  critical: {
    text: "text-red-700 dark:text-red-300",
    bg: "bg-red-900/10",
    bar: "#7f1d1d",
  },
  high: {
    text: "text-red-600 dark:text-red-400",
    bg: "bg-red-500/10",
    bar: "#ef4444",
  },
  medium: {
    text: "text-orange-600 dark:text-orange-300",
    bg: "bg-orange-500/10",
    bar: "#f97316",
  },
  low: {
    text: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-emerald-500/10",
    bar: "#10b981",
  },
};

const RISK_LABELS: Record<string, Record<string, string>> = {
  ko: { critical: "위험", high: "높음", medium: "보통", low: "낮음" },
  en: { critical: "Critical", high: "High", medium: "Medium", low: "Low" },
};

export function SectorImpactCard({ clusterId }: { clusterId: string }) {
  const lang = useAppStore((s) => s.lang);
  const [expanded, setExpanded] = useState(false);
  const { data, isLoading, isError, error } = useSectorAnalysis(
    expanded ? clusterId : undefined,
  );

  const is403 = (error as any)?.status === 403;

  const chartData = data?.sectors.map((s) => ({
    name: s.sector.length > 5 ? s.sector.slice(0, 5) + ".." : s.sector,
    fullName: s.sector,
    dependency: Math.round(s.trade_dependency * 100),
    gdp: s.exposure_pct,
    risk: s.risk_level,
  }));

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
              ? lang === "ko"
                ? "접기"
                : "Collapse"
              : lang === "ko"
                ? "산업별 리스크 분석 보기"
                : "View sector risk analysis"}
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
                <Loader2 className="h-5 w-5 animate-spin text-purple-400" />
              </div>
            )}

            {is403 && (
              <div className="py-4 text-center">
                <Lock className="h-5 w-5 text-muted-foreground mx-auto mb-2" />
                <p className="text-xs text-muted-foreground mb-2">
                  {lang === "ko"
                    ? "Pro+ 플랜에서 이용 가능합니다"
                    : "Available for Pro+ plan"}
                </p>
                <a
                  href="/upgrade"
                  className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
                  style={{
                    background: "linear-gradient(to right, #7c3aed, #6366f1)",
                  }}
                >
                  {t(lang, "dash_unlock_pro_plus")}
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
                {/* Overall Risk Badge */}
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground">
                    {lang === "ko" ? "전체 리스크:" : "Overall:"}
                  </span>
                  <span
                    className={cn(
                      "text-[10px] font-bold px-2 py-0.5 rounded-full",
                      RISK_COLORS[data.overall_risk]?.bg,
                      RISK_COLORS[data.overall_risk]?.text,
                    )}
                  >
                    {RISK_LABELS[lang]?.[data.overall_risk] ||
                      data.overall_risk}
                  </span>
                </div>

                {/* Bar Chart — Trade Dependency by Sector */}
                {chartData && chartData.length > 0 && (
                  <div className="h-[180px] w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={chartData}
                        layout="vertical"
                        margin={{ top: 4, right: 30, bottom: 4, left: 4 }}
                      >
                        <XAxis
                          type="number"
                          domain={[0, 100]}
                          tick={{ fontSize: 9, fill: "#94a3b8" }}
                          tickFormatter={(v: number) => `${v}%`}
                        />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={50}
                          tick={{ fontSize: 9, fill: "#94a3b8" }}
                        />
                        <Tooltip
                          contentStyle={{
                            background: "#1e293b",
                            border: "none",
                            borderRadius: "8px",
                            fontSize: 11,
                            color: "#e2e8f0",
                          }}
                          formatter={(value: any, _name: any, props: any) => [
                            `${value}%`,
                            lang === "ko"
                              ? `${props?.payload?.fullName || ""} 교역 의존도`
                              : `${props?.payload?.fullName || ""} Trade Dep.`,
                          ]}
                        />
                        <Bar dataKey="dependency" radius={[0, 4, 4, 0]}>
                          {chartData.map((entry, index) => (
                            <Cell
                              key={index}
                              fill={
                                RISK_COLORS[entry.risk]?.bar || "#94a3b8"
                              }
                            />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}

                {/* Sector Detail Cards */}
                <div className="space-y-1.5">
                  {data.sectors.map((sector, idx) => {
                    const colors =
                      RISK_COLORS[sector.risk_level] || RISK_COLORS.low;
                    return (
                      <div
                        key={sector.sector}
                        className="flex items-center gap-2 rounded-lg bg-muted/15 px-3 py-2 fade-in-up"
                        style={{ animationDelay: `${idx * 50}ms` }}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="text-[11px] font-semibold truncate">
                              {sector.sector}
                            </span>
                            <span
                              className={cn(
                                "text-[9px] font-bold px-1.5 py-0.5 rounded-full shrink-0",
                                colors.bg,
                                colors.text,
                              )}
                            >
                              {RISK_LABELS[lang]?.[sector.risk_level] ||
                                sector.risk_level}
                            </span>
                          </div>
                          <p className="text-[9px] text-muted-foreground mt-0.5 line-clamp-1">
                            {sector.description}
                          </p>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="text-[11px] font-bold tabular-nums">
                            {Math.round(sector.trade_dependency * 100)}%
                          </span>
                          <p className="text-[8px] text-muted-foreground">
                            {lang === "ko" ? "의존도" : "dep."}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Footer */}
                <div className="flex items-start gap-1.5 pt-2 border-t border-border/30">
                  <Info className="h-3 w-3 text-muted-foreground shrink-0 mt-0.5" />
                  <p className="text-[9px] text-muted-foreground">
                    {t(lang, "dash_ai_estimate")}
                    {" · "}
                    {lang === "ko"
                      ? "출처: World Bank, UN Comtrade"
                      : "Sources: World Bank, UN Comtrade"}
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

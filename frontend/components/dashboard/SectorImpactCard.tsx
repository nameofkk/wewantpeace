"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useSectorAnalysis, useSectorOverview, useImpactSummary } from "@/lib/api";
import { t, type Lang } from "@/lib/i18n";
import {
  Sparkles,
  ChevronDown,
  ChevronUp,
  Info,
  Loader2,
  Lock,
} from "lucide-react";
import dynamic from "next/dynamic";
import { Cell } from "recharts";

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
const Tooltip = dynamic(
  () => import("recharts").then((m) => m.Tooltip),
  { ssr: false },
);

const RISK_COLORS: Record<string, { text: string; bg: string; bar: string }> = {
  critical: {
    text: "text-red-700 dark:text-red-300",
    bg: "bg-red-900/10",
    bar: "#dc2626",
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

const DEMO_SECTOR = {
  sectors: [
    { sector_ko: "에너지", sector_en: "Energy", exposure_pct: 35, trade_dependency: 0.72, risk_level: "critical", description_ko: "원유·천연가스 공급 불안정으로 가격 급등", description_en: "Price surge due to oil/gas supply instability" },
    { sector_ko: "농업·식품", sector_en: "Agriculture", exposure_pct: 28, trade_dependency: 0.58, risk_level: "high", description_ko: "곡물 수출국 분쟁으로 공급 차질", description_en: "Grain supply disruption from conflict in exporting nations" },
    { sector_ko: "반도체", sector_en: "Semiconductors", exposure_pct: 22, trade_dependency: 0.45, risk_level: "medium", description_ko: "희토류 공급망 다변화 필요", description_en: "Rare earth supply chain diversification needed" },
    { sector_ko: "물류·운송", sector_en: "Logistics", exposure_pct: 18, trade_dependency: 0.38, risk_level: "medium", description_ko: "해운 경로 우회로 비용 증가", description_en: "Shipping cost increase due to route diversions" },
    { sector_ko: "관광", sector_en: "Tourism", exposure_pct: 12, trade_dependency: 0.15, risk_level: "low", description_ko: "분쟁 인접 지역 여행 수요 감소", description_en: "Travel demand decline near conflict zones" },
  ],
  overall_risk: "high",
};

/** 섹터 분석 내부 콘텐츠 — embedded/standalone 모두에서 재사용 */
function SectorContent({
  data,
  chartData,
  lang,
  isDark,
}: {
  data: { sectors: { sector: string; exposure_pct: number; trade_dependency: number; risk_level: string; description: string }[]; overall_risk: string };
  chartData: { name: string; fullName: string; dependency: number; gdp: number; risk: string }[];
  lang: Lang;
  isDark: boolean;
}) {
  return (
    <div className="space-y-3">
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
          {RISK_LABELS[lang]?.[data.overall_risk] || data.overall_risk}
        </span>
      </div>

      {/* Bar Chart — Trade Dependency by Sector */}
      {chartData.length > 0 && (
        <div className="h-[160px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="vertical"
              margin={{ top: 4, right: 30, bottom: 4, left: 4 }}
            >
              <XAxis
                type="number"
                domain={[0, 100]}
                tick={{ fontSize: 9, fill: isDark ? "#94a3b8" : "#475569" }}
                tickFormatter={(v: number) => `${v}%`}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={lang === "en" ? 85 : 50}
                tick={{ fontSize: 9, fill: isDark ? "#94a3b8" : "#475569" }}
              />
              <Tooltip
                contentStyle={{
                  background: isDark ? "#1e293b" : "#ffffff",
                  border: isDark ? "none" : "1px solid #e2e8f0",
                  borderRadius: "8px",
                  fontSize: 11,
                  color: isDark ? "#e2e8f0" : "#1e293b",
                  boxShadow: isDark ? "none" : "0 2px 8px rgba(0,0,0,0.08)",
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
                    fill={RISK_COLORS[entry.risk]?.bar || "#94a3b8"}
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
          const colors = RISK_COLORS[sector.risk_level] || RISK_COLORS.low;
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
                    {RISK_LABELS[lang]?.[sector.risk_level] || sector.risk_level}
                  </span>
                </div>
                <p className="text-[9px] text-muted-foreground mt-0.5 line-clamp-2">
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
  );
}

function buildDemoData(lang: Lang) {
  const sectors = DEMO_SECTOR.sectors.map((s) => ({
    sector: lang === "ko" ? s.sector_ko : s.sector_en,
    exposure_pct: s.exposure_pct,
    trade_dependency: s.trade_dependency,
    risk_level: s.risk_level,
    description: lang === "ko" ? s.description_ko : s.description_en,
  }));
  const maxLabel = lang === "en" ? 12 : 5;
  const chartData = sectors.map((s) => ({
    name: s.sector.length > maxLabel ? s.sector.slice(0, maxLabel) + ".." : s.sector,
    fullName: s.sector,
    dependency: Math.round(s.trade_dependency * 100),
    gdp: s.exposure_pct,
    risk: s.risk_level,
  }));
  return {
    data: { sectors, overall_risk: DEMO_SECTOR.overall_risk },
    chartData,
  };
}

interface SectorImpactCardProps {
  clusterId?: string;
  /** embedded=true 이면 expand/collapse 없이 직접 표시 (홈 탭 내부용) */
  embedded?: boolean;
}

export function SectorImpactCard({ clusterId, embedded }: SectorImpactCardProps) {
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);
  const isDark = useAppStore((s) => s.theme) === "dark";
  const [expanded, setExpanded] = useState(false);

  // embedded 모드: 뷰포트 진입 시에만 API 호출 (홈 초기 로드 최적화)
  const containerRef = useRef<HTMLDivElement>(null);
  const [inView, setInView] = useState(!embedded); // embedded 아니면 즉시 true
  useEffect(() => {
    if (!embedded || !containerRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setInView(true); observer.disconnect(); } },
      { rootMargin: "200px" },
    );
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [embedded]);

  const shouldFetch = (embedded ? inView : expanded);
  const useOverview = embedded && !clusterId; // 홈: 전체 이슈 기반 overview

  // clusterId가 있으면 직접 사용, 없으면 Impact Summary에서 top issue 가져오기
  const { data: summaryData } = useImpactSummary(homeCountry, lang, !clusterId && !useOverview && shouldFetch);
  const effectiveClusterId = clusterId || summaryData?.top_issues?.[0]?.cluster_id;

  // 전체 이슈 기반 overview (홈 embedded 모드)
  const overviewQuery = useSectorOverview(homeCountry, lang, useOverview && shouldFetch);
  // 개별 클러스터 기반 (이슈 상세 페이지)
  const clusterQuery = useSectorAnalysis(
    !useOverview && shouldFetch && effectiveClusterId ? effectiveClusterId : undefined,
    homeCountry,
    lang,
  );

  const activeQuery = useOverview ? overviewQuery : clusterQuery;
  const { data, isLoading, isError, error } = activeQuery;

  const is403 = [401, 403].includes((error as any)?.status);

  const maxLabel = lang === "en" ? 12 : 5;
  const chartData = data?.sectors.map((s) => ({
    name: s.sector.length > maxLabel ? s.sector.slice(0, maxLabel) + ".." : s.sector,
    fullName: s.sector,
    dependency: Math.round(s.trade_dependency * 100),
    gdp: s.exposure_pct,
    risk: s.risk_level,
  })) ?? [];

  // ── Embedded mode: 탭 안에서 직접 표시 ──
  if (embedded) {
    if (!inView || isLoading || (!effectiveClusterId && !is403 && !isError)) {
      return (
        <div ref={containerRef} className="flex items-center justify-center py-6">
          <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
        </div>
      );
    }
    if (is403) {
      const demo = buildDemoData(lang);
      return (
        <div className="relative">
          <div className="opacity-60" style={{ filter: "blur(3px)" }}>
            <SectorContent data={demo.data} chartData={demo.chartData} lang={lang} isDark={isDark} />
          </div>
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/30 rounded-lg">
            <Lock className="h-5 w-5 text-muted-foreground mb-2" />
            <p className="text-xs text-muted-foreground mb-2 font-medium">
              {lang === "ko"
                ? "Pro 플랜에서 이용 가능합니다"
                : "Available for Pro plan"}
            </p>
            <a
              href="/upgrade?source=demo_sector"
              className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
              style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
            >
              {t(lang, "dash_unlock_pro")}
            </a>
          </div>
        </div>
      );
    }
    if (isError) {
      return (
        <p className="py-3 text-xs text-muted-foreground text-center">
          {lang === "ko" ? "분석을 불러올 수 없습니다" : "Failed to load analysis"}
        </p>
      );
    }
    if (!data) return null;
    return <SectorContent data={data} chartData={chartData} lang={lang} isDark={isDark} />;
  }

  // ── Standalone mode: 이슈 상세 스타일 ──
  return (
    <div className="rounded-xl border border-purple-500/20 bg-card fade-in-up overflow-hidden">
      {/* 헤더 — 이슈 상세 스타일 */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-muted/5 transition-colors"
      >
        <Sparkles className="h-3.5 w-3.5 text-purple-400 shrink-0" />
        <h3 className="text-xs font-semibold text-purple-400 flex-1 text-left">
          {lang === "ko" ? "산업별 리스크 분석" : "Sector Risk Analysis"}
        </h3>
        <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 font-bold shrink-0">Pro+</span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        )}
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-purple-500/10">
          {(isLoading || (expanded && !effectiveClusterId && !is403 && !isError)) && (
            <div className="flex items-center justify-center py-6">
              <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
            </div>
          )}

          {is403 && (() => {
            const demo = buildDemoData(lang);
            return (
              <div className="relative mt-3">
                <div className="opacity-60" style={{ filter: "blur(3px)" }}>
                  <SectorContent data={demo.data} chartData={demo.chartData} lang={lang} isDark={isDark} />
                </div>
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/30 rounded-lg">
                  <Lock className="h-5 w-5 text-muted-foreground mb-2" />
                  <p className="text-xs text-muted-foreground mb-2 font-medium">
                    {lang === "ko"
                      ? "Pro+ 플랜에서 이용 가능합니다"
                      : "Available for Pro+ plan"}
                  </p>
                  <a
                    href="/upgrade"
                    className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
                    style={{ background: "linear-gradient(to right, #7c3aed, #6366f1)" }}
                  >
                    {t(lang, "dash_unlock_pro_plus")}
                  </a>
                </div>
              </div>
            );
          })()}

          {isError && !is403 && (
            <p className="py-4 text-xs text-muted-foreground text-center">
              {lang === "ko" ? "분석을 불러올 수 없습니다" : "Failed to load analysis"}
            </p>
          )}

          {data && (
            <div className="mt-3">
              <SectorContent data={data} chartData={chartData} lang={lang} isDark={isDark} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

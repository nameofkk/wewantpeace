"use client";

import React, { Suspense, useMemo, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
import {
  useMe,
  useTrackBehavior,
  useImpactSummary,
  usePrefetchImpactSummary,
  useTensionMine,
  useTensionAll,
  type TensionAllItem,
} from "@/lib/api";
import { t } from "@/lib/i18n";
import {
  personalizedKScore,
  type TrendingItem,
} from "@/lib/kscore-utils";
import { SUPPORTED_HOME_COUNTRIES } from "@/lib/impact-factors";
import { useCountUp } from "@/hooks/useCountUp";
import { NoticeTicker } from "@/components/dashboard/NoticeTicker";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { Disclaimer } from "@/components/ui/Disclaimer";
import { SmartSummaryCardFull, SmartSummaryCompact } from "@/components/dashboard/SmartSummaryCard";
import { RiskRadar } from "@/components/dashboard/RiskRadar";
import { ImpactFlowSankey } from "@/components/dashboard/ImpactFlowSankey";
import { ProDemoWrapper } from "@/components/dashboard/ProDemoWrapper";
import { SectorImpactCard } from "@/components/dashboard/SectorImpactCard";
import { LazyMotion, domAnimation, m, AnimatePresence } from "framer-motion";
import {
  MapPin,
  Plus,
  Briefcase,
  ShoppingCart,
  Plane,
  Activity,
  AlertTriangle,
  TrendingUp,
  ExternalLink,
  Fuel,
  BarChart3,
  Globe2,
  Sparkles,
  ChevronDown,
  X,
  Check,
} from "lucide-react";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { LogoIcon } from "@/components/ui/logo-icon";
import AppTour from "@/components/ui/AppTour";
import TourHelpButton from "@/components/ui/TourHelpButton";
import type { Step } from "react-joyride";

export default function HomePage() {
  return (
    <Suspense fallback={<div className="p-4"><DashboardSkeleton /></div>}>
      <LazyMotion features={domAnimation}>
        <ReportContent />
      </LazyMotion>
    </Suspense>
  );
}

/* ───────────────────────── 색상/레벨 유틸 ───────────────────────── */

function impactColor(score: number) {
  if (score >= 75) return "#dc2626";
  if (score >= 50) return "#f97316";
  if (score >= 25) return "#f59e0b";
  return "#10b981";
}

function tensionColor(score: number) {
  if (score >= 80) return { bar: "bg-red-900", text: "text-red-700 dark:text-red-300", dot: "bg-red-900 animate-pulse" };
  if (score >= 60) return { bar: "bg-red-500", text: "text-red-600 dark:text-red-400", dot: "bg-red-500" };
  if (score >= 40) return { bar: "bg-orange-500", text: "text-orange-600 dark:text-orange-300", dot: "bg-orange-500" };
  if (score >= 20) return { bar: "bg-amber-500", text: "text-amber-600 dark:text-amber-300", dot: "bg-amber-500" };
  return { bar: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400", dot: "bg-emerald-500" };
}

function tensionLabelShort(score: number, lang: "ko" | "en") {
  if (score >= 80) return lang === "ko" ? "극심" : "Ext.";
  if (score >= 60) return lang === "ko" ? "심각" : "Sev.";
  if (score >= 40) return lang === "ko" ? "경계" : "Alt.";
  if (score >= 20) return lang === "ko" ? "주의" : "Cau.";
  return lang === "ko" ? "안정" : "OK";
}

function travelLevelColor(level: number) {
  if (level >= 4) return { bg: "bg-red-500/15", text: "text-red-600 dark:text-red-400", border: "border-red-500/30" };
  if (level >= 3) return { bg: "bg-orange-500/15", text: "text-orange-600 dark:text-orange-300", border: "border-orange-500/30" };
  if (level >= 2) return { bg: "bg-amber-500/15", text: "text-amber-600 dark:text-amber-300", border: "border-amber-500/30" };
  return { bg: "bg-emerald-500/15", text: "text-emerald-600 dark:text-emerald-400", border: "border-emerald-500/30" };
}

function changePctColor(pct: number) {
  if (pct > 0) return "text-red-500";
  if (pct < 0) return "text-blue-500";
  return "text-muted-foreground";
}

function formatTradeVolume(usd: number) {
  if (usd >= 1e9) return `$${(usd / 1e9).toFixed(1)}B`;
  if (usd >= 1e6) return `$${(usd / 1e6).toFixed(0)}M`;
  if (usd >= 1e3) return `$${(usd / 1e3).toFixed(0)}K`;
  return `$${usd.toLocaleString()}`;
}

/* ───────────────────────── Section Header with InfoTooltip ───────────────────────── */

function SectionHeader({ icon: Icon, title, desc, tooltip }: {
  icon: React.ElementType;
  title: string;
  desc: string;
  tooltip: string;
  lang?: "ko" | "en";
}) {
  return (
    <div className="flex items-center gap-1.5 mb-2.5 flex-wrap">
      <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      <h2 className="text-[11px] font-bold text-foreground shrink-0">{title}</h2>
      <span className="text-[9px] text-muted-foreground/50 shrink-0">·</span>
      <span className="text-[9px] text-muted-foreground/50">{desc}</span>
      <InfoTooltip text={tooltip} direction="down" />
    </div>
  );
}

/* ───────────────────────── Section stagger variants ───────────────────────── */

const sectionVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: (i: number) => ({
    opacity: 1, y: 0,
    transition: { delay: i * 0.1, duration: 0.4, ease: "easeOut" as const },
  }),
};

/* ───────────────────────── 메인 리포트 ───────────────────────── */

function ReportContent() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);
  const setHomeCountry = useAppStore((s) => s.setHomeCountry);
  const myCountries = useAppStore((s) => s.myCountries);

  const { data: me, isLoading: meLoading } = useMe();
  const meObj = me as { plan?: string; nickname?: string; display_name?: string } | undefined;
  const userPlan = meObj?.plan ?? "free";
  const nickname = meObj?.nickname || meObj?.display_name || (lang === "ko" ? "사용자" : "User");

  const { data: summary, isLoading: summaryLoading, isError: summaryError, error: summaryErrorObj } = useImpactSummary(homeCountry ?? "", lang);
  const { data: homeTension, dataUpdatedAt } = useTensionMine(homeCountry ? [homeCountry] : null);
  const { data: allTension } = useTensionAll();
  const { data: watchlistTension } = useTensionMine(myCountries.length > 0 ? myCountries : null);

  const [activeTab, setActiveTab] = useState<"market" | "trade" | "travel" | "detail">("market");
  const [showCountryPicker, setShowCountryPicker] = useState(false);
  const [tourRun, setTourRun] = useState(false);
  const isPro = userPlan === "pro" || userPlan === "pro_plus";

  const dashTourSteps: Step[] = useMemo(() => [
    {
      target: "[data-tour='dash-page']",
      content: t(lang, "tour_dash_page_role"),
      placement: "center" as const,
      disableBeacon: true,
    },
    {
      target: "[data-tour='dash-risk']",
      content: t(lang, "tour_dash_risk"),
      disableBeacon: true,
    },
    {
      target: "[data-tour='dash-watchlist']",
      content: t(lang, "tour_dash_watchlist"),
      disableBeacon: true,
    },
    {
      target: "[data-tour='dash-top-issues']",
      content: t(lang, "tour_dash_top_issues"),
      disableBeacon: true,
    },
  ], [lang]);
  const availableCountries = isPro ? SUPPORTED_HOME_COUNTRIES : [];
  const prefetchSummary = usePrefetchImpactSummary();

  const trackBehavior = useTrackBehavior();
  useEffect(() => {
    trackBehavior.mutate({ event_name: "dashboard_view", props: { plan: userPlan } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 바텀시트 열릴 때 배경 스크롤 방지 + 전 국가 데이터 prefetch
  useEffect(() => {
    if (showCountryPicker) {
      document.body.style.overflow = "hidden";
      // 모든 국가 + 글로벌 데이터를 백그라운드에서 미리 로드
      prefetchSummary(["", ...availableCountries], lang);
      return () => { document.body.style.overflow = ""; };
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showCountryPicker]);

  const isGlobalMode = !homeCountry;
  const homeData = Array.isArray(homeTension) ? homeTension[0] : null;
  const singleCountryScore = (homeData as TensionAllItem | null)?.raw_score ?? 0;
  const allItems = (allTension as TensionAllItem[] | undefined) ?? [];

  const globalAvgScore = useMemo(() => {
    if (!isGlobalMode || !allItems.length) return 0;
    // Top 15 국가 평균 — 안정 국가가 평균을 희석하는 문제 해결
    const sorted = [...allItems].sort((a, b) => b.raw_score - a.raw_score);
    const top15 = sorted.slice(0, 15);
    return Math.round(top15.reduce((s, i) => s + i.raw_score, 0) / top15.length);
  }, [isGlobalMode, allItems]);

  const homeScore = isGlobalMode ? globalAvgScore : singleCountryScore;
  const animatedHomeScore = useCountUp(homeScore, 1000);
  const extremeCount = allItems.filter((i) => i.raw_score >= 80).length;
  const severeCount = allItems.filter((i) => i.raw_score >= 60 && i.raw_score < 80).length;
  const alertCount = allItems.filter((i) => i.raw_score >= 40 && i.raw_score < 60).length;

  const updatedTime = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(lang === "ko" ? "ko-KR" : "en-US", { hour: "2-digit", minute: "2-digit" })
    : null;

  const watchlistItems = (watchlistTension as TensionAllItem[] | undefined) ?? [];
  const tensionMap = new Map(watchlistItems.map((t: any) => [t.country_code, t]));
  const allTensionMap = new Map(allItems.map((t) => [t.country_code, t]));

  const impactScore = summary?.score ?? 0;
  const animatedImpact = useCountUp(impactScore, 900);
  const color = impactColor(impactScore);
  const levelKey = `dash_impact_level_${summary?.level || "low"}` as Parameters<typeof t>[1];
  const hasPro = !!(summary?.economy || summary?.trade || summary?.travel);

  const topItems = useMemo(() => {
    if (!summary?.top_issues?.length) return [];
    return summary.top_issues.map((ti: any, i: number) => ({
      id: i,
      keyword: lang === "en" && ti.title_en ? ti.title_en : ti.title,
      keyword_ko: ti.title,
      kscore: ti.kscore ?? 0,
      topic: ti.topic,
      country_codes: ti.country_codes,
      cluster_ids: [ti.cluster_id],
      event_count: ti.event_count ?? 0,
      severity: ti.severity ?? 0,
      reason: ti.reason || "",
      calculated_at: ti.last_event_at,
      first_event_at: ti.first_event_at,
      independent_sources: ti.independent_sources ?? 1,
      is_spike: ti.is_spike ?? false,
      confidence: ti.confidence ?? 0,
    } as TrendingItem));
  }, [summary, lang]);

  if (summaryLoading) {
    return <div className="p-4"><DashboardSkeleton /></div>;
  }

  if (summaryError && !summary) {
    return (
      <div className="p-6 text-center">
        <Activity className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
        <p className="text-sm font-medium text-foreground mb-1">
          {lang === "ko" ? "데이터를 불러올 수 없습니다" : "Failed to load data"}
        </p>
        <p className="text-xs text-muted-foreground mb-3">
          {lang === "ko" ? "잠시 후 다시 시도해주세요" : "Please try again later"}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="inline-flex items-center gap-1 rounded-full bg-primary px-4 py-2 text-xs font-bold text-primary-foreground"
        >
          {lang === "ko" ? "새로고침" : "Refresh"}
        </button>
      </div>
    );
  }

  const topIssue = topItems[0];
  const restIssues = topItems.slice(1);

  return (
    <div className="flex flex-col" data-tour="dash-page" style={{ height: "calc(100dvh - 60px)" }}>
      <AppTour tourId="dashboard" steps={dashTourSteps} run={tourRun} onComplete={() => setTourRun(false)} />
      <TourHelpButton tourId="dashboard" onStartTour={() => setTourRun(true)} />
      {/* ═══════════════ Header ═══════════════ */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 pt-4 pb-3">
        <div className="grid grid-cols-3 items-center">
          {/* 왼쪽 — 타이틀 + LIVE */}
          <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
            <h1 className="text-sm font-bold truncate">{t(lang, "dash_title")}</h1>
            <span className="shrink-0 flex items-center gap-0.5 rounded-full bg-red-500/10 px-1.5 py-0.5 border border-red-500/20">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-500" />
              <span className="text-[9px] font-bold text-red-600 dark:text-red-400">LIVE</span>
            </span>
          </div>
          {/* 중앙 — 로고 */}
          <div className="flex justify-center">
            <LogoIcon height={26} hideText />
          </div>
          {/* 오른쪽 — 기준 국가 + 업데이트 시간 */}
          <div className="flex items-center justify-end gap-1.5">
            <button
              onClick={() => setShowCountryPicker(true)}
              className="flex items-center gap-0.5 rounded-full bg-muted/20 border border-border px-1.5 py-0.5 hover:bg-muted/40 transition-colors"
            >
              <span className="text-xs">{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
              <span className="text-[9px] font-bold text-foreground">{homeCountry || (lang === "ko" ? "전체" : "ALL")}</span>
              <ChevronDown className="h-2.5 w-2.5 text-muted-foreground" />
            </button>
            {updatedTime && (
              <span className="text-[9px] text-muted-foreground whitespace-nowrap">{updatedTime}</span>
            )}
          </div>
        </div>
        {/* 로딩 진행 바 */}
        {summaryLoading && (
          <div className="h-0.5 w-full bg-muted overflow-hidden">
            <div className="h-full w-1/3 bg-primary rounded-full animate-loading-bar" />
          </div>
        )}
      </div>

      <NoticeTicker />

      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-4 space-y-5">

          {/* ═══════════════ SECTION A: Unified Hero (Impact + Radar + Watchlist) ═══════════════ */}
          <m.section
            custom={0}
            initial="hidden"
            animate="visible"
            variants={sectionVariants}
            className="rounded-xl border border-border bg-card p-4"
            data-tour="dash-risk"
          >
            <SectionHeader
              icon={BarChart3}
              title={t(lang, "dash_section_hero_title" as any)}
              desc={t(lang, "dash_section_hero_desc" as any)}
              tooltip={t(lang, "dash_section_hero_tooltip" as any)}
            />
            {/* Impact Score + Risk Radar */}
            <div className="flex items-start gap-3">
              {/* Left: Impact Score */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl font-bold tabular-nums leading-none score-reveal" style={{ color }}>
                    {Math.round(animatedImpact)}
                  </span>
                  <span
                    className="text-[9px] font-bold px-1.5 py-0.5 rounded-full shrink-0"
                    style={{ color, backgroundColor: `${color}15` }}
                  >
                    {t(lang, levelKey)}
                  </span>
                </div>

                <div className="h-1.5 rounded-full bg-muted overflow-hidden mb-2">
                  <div
                    className="h-full rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${Math.min(impactScore, 100)}%`, backgroundColor: color }}
                  />
                </div>

                <p className="text-[10px] text-foreground/60 leading-relaxed line-clamp-2 mb-2">
                  {summary?.summary || (lang === "ko" ? "분석 데이터를 불러오는 중..." : "Loading analysis...")}
                </p>
              </div>

              {/* Right: Risk Radar (compact) */}
              {summary?.risk_radar && (
                <div className="shrink-0">
                  <RiskRadar data={summary.risk_radar} lang={lang} />
                </div>
              )}
            </div>

            {/* Home tension + global counts */}
            <div className="flex items-center gap-1.5 text-[10px] mb-1.5 flex-wrap">
              <span className="text-sm">{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
              <span className={cn("font-bold tabular-nums", tensionColor(homeScore).text)}>
                {Math.round(animatedHomeScore)}
              </span>
              <div className="h-1.5 w-12 rounded-full bg-muted overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all duration-1000 ease-out", tensionColor(homeScore).bar)}
                  style={{ width: `${Math.min(homeScore, 100)}%` }}
                />
              </div>
              <span className={cn("text-[9px]", tensionColor(homeScore).text)}>
                {tensionLabelShort(homeScore, lang)}
              </span>
              <span className="text-muted-foreground/30">|</span>
              {extremeCount > 0 && (
                <span className="flex items-center gap-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-900 animate-pulse" />
                  <span className="text-[9px] text-red-300 font-medium">{extremeCount}</span>
                </span>
              )}
              {severeCount > 0 && (
                <span className="flex items-center gap-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-red-500" />
                  <span className="text-[9px] text-red-400 font-medium">{severeCount}</span>
                </span>
              )}
              {alertCount > 0 && (
                <span className="flex items-center gap-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                  <span className="text-[9px] text-orange-300 font-medium">{alertCount}</span>
                </span>
              )}
              {extremeCount === 0 && severeCount === 0 && alertCount === 0 && (
                <span className="text-[9px] text-emerald-400 font-medium">
                  {t(lang, "dash_global_stable")}
                </span>
              )}
            </div>

            {/* Issue stats + time */}
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground mb-3">
              <span>{lang === "ko" ? "이슈" : "Issues"} <strong>{summary?.total_active_issues ?? 0}</strong></span>
              <span className="text-red-400">{t(lang, "dash_high_impact")} <strong>{summary?.critical_issues_count ?? 0}</strong></span>
              {updatedTime && <span className="ml-auto">{updatedTime}</span>}
            </div>

            {/* Watchlist chips */}
            <div data-tour="dash-watchlist">
            {myCountries.length > 0 ? (
              <div className="space-y-1">
              <span className="text-[9px] text-muted-foreground/60 font-medium">
                {lang === "ko" ? "관심 국가 긴장도" : "Watchlist Tension"}
              </span>
              <div className="flex gap-1.5 overflow-x-auto scrollbar-hide pb-0.5">
                {myCountries.map((code) => {
                  const data = tensionMap.get(code) as TensionAllItem | undefined;
                  const allData = allTensionMap.get(code);
                  const score = data?.raw_score ?? allData?.raw_score ?? 0;
                  const tc = tensionColor(score);
                  const isAnomaly = (allData?.anomaly_z ?? 0) >= 2.0;
                  const isConverging = (allData?.convergence_bonus ?? 0) >= 5.0;
                  return (
                    <div
                      key={code}
                      onClick={() => router.push(`/tension?country=${code}`)}
                      className="shrink-0 flex items-center gap-1 rounded-full bg-muted/15 px-2 py-1 cursor-pointer hover:bg-muted/25 transition-colors"
                    >
                      <span className="text-xs">{getFlag(code)}</span>
                      <span className={cn("text-[10px] font-bold tabular-nums", tc.text)}>{score}</span>
                      {isAnomaly && <span className="text-[7px] px-1 rounded bg-red-500/20 text-red-400 font-bold">{t(lang, "dash_badge_anomaly" as any)}</span>}
                      {isConverging && <span className="text-[7px] px-1 rounded bg-purple-500/20 text-purple-400 font-bold">{t(lang, "dash_badge_convergence" as any)}</span>}
                    </div>
                  );
                })}
                <Link
                  href="/settings?section=countries"
                  className="shrink-0 flex items-center gap-0.5 rounded-full bg-muted/10 px-2 py-1 text-[9px] text-muted-foreground hover:bg-muted/20"
                >
                  <Plus className="h-2.5 w-2.5" />
                </Link>
              </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 justify-center py-1">
                <MapPin className="h-3 w-3 text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground">{t(lang, "dash_watchlist_empty")}</span>
                <Link
                  href="/settings?section=countries"
                  className="inline-flex items-center gap-1 rounded-full bg-primary px-2 py-0.5 text-[9px] font-bold text-primary-foreground"
                >
                  <Plus className="h-2 w-2" />
                  {t(lang, "dash_watchlist_add")}
                </Link>
              </div>
            )}
            </div>
          </m.section>

          {/* ═══════════════ SECTION B: Impact Stories (Sankey + Smart Cards) ═══════════════ */}
          <m.section custom={1} initial="hidden" animate="visible" variants={sectionVariants}>
            {/* Impact Flow Sankey */}
            {summary?.impact_flow && (
              <div className="rounded-xl border border-border bg-card mb-5">
                <div className="px-4 pt-3 pb-1">
                  <SectionHeader
                    icon={Activity}
                    title={t(lang, "dash_flow_title" as any)}
                    desc={t(lang, "dash_flow_desc" as any)}
                    tooltip={t(lang, "dash_section_flow_tooltip" as any)}
                  />
                </div>
                <div className="overflow-x-auto">
                  <ImpactFlowSankey
                    data={summary.impact_flow}
                    isPro={isPro}
                    lang={lang}
                    conflictIssues={summary.top_issues?.slice(0, 3).map((ti: any) => ({
                      clusterId: ti.cluster_id,
                      title: lang === "en" && ti.title_en ? ti.title_en : ti.title,
                      countryCodes: ti.country_codes ?? [],
                    }))}
                  />
                </div>
              </div>
            )}

            {/* #1 Issue: SmartSummaryCard Full */}
            <div data-tour="dash-top-issues">
            {topIssue && (
              <div className="rounded-xl border border-border bg-card mt-5">
                <div className="px-4 pt-3 pb-1">
                  <SectionHeader
                    icon={AlertTriangle}
                    title={lang === "ko" ? "가장 영향이 큰 이슈" : "Top Impact Issue"}
                    desc={lang === "ko" ? "종합 영향도 1위" : "#1 by impact score"}
                    tooltip={lang === "ko"
                      ? "현재 활성 이슈 중 설정한 기준국가에 가장 영향이 큰 이슈의 요약입니다. 무슨 일인지, 나에게 어떤 영향이 있는지, 언제 영향이 올지를 3줄로 보여줍니다."
                      : "Summary of the issue with highest impact on your home country. Shows what happened, how it affects you, and when to expect effects."}
                  />
                </div>
                <div className="px-4 pb-4">
                  <SmartSummaryCardFull
                    item={topIssue}
                    homeCountry={homeCountry ?? ""}
                    lang={lang}
                    market={summary?.market_snapshot}
                    topIssueRaw={summary?.top_issues?.[0]}
                    isPro={isPro}
                  />
                </div>
              </div>
            )}
            </div>

            {/* #2-#5 Issues: Compact */}
            {restIssues.length > 0 && (
              <div className="rounded-xl border border-border bg-card mt-5">
                <div className="px-4 pt-3 pb-1">
                  <SectionHeader
                    icon={AlertTriangle}
                    title={t(lang, "dash_section_stories_title" as any)}
                    desc={t(lang, "dash_section_stories_desc" as any)}
                    tooltip={t(lang, "dash_section_stories_tooltip" as any)}
                  />
                </div>
                <div className="px-4 pb-3">
                  {restIssues.map((item, idx) => (
                    <SmartSummaryCompact
                      key={item.id}
                      item={item}
                      index={idx}
                      homeCountry={homeCountry ?? ""}
                      lang={lang}
                      topIssueRaw={summary?.top_issues?.[idx + 1]}
                      isLast={idx === restIssues.length - 1}
                    />
                  ))}
                </div>
                <Link
                  href="/feed"
                  className="flex items-center justify-center gap-1.5 border-t border-border/30 py-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/10 transition-colors rounded-b-xl"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  {t(lang, "dash_view_all_issues")}
                </Link>
              </div>
            )}

            {topItems.length === 0 && (
              <div className="rounded-xl border border-border bg-card/50 p-5 text-center">
                <Activity className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
                <p className="text-[11px] text-muted-foreground">{t(lang, "dash_no_issues")}</p>
              </div>
            )}
          </m.section>

          {/* ═══════════════ SECTION C: Data Dashboard (4탭 통합) ═══════════════ */}
          <m.section
            custom={2}
            initial="hidden"
            animate="visible"
            variants={sectionVariants}
            className="rounded-xl border border-border bg-card p-4"
          >
            <SectionHeader
              icon={BarChart3}
              title={t(lang, "dash_section_dashboard_title" as any)}
              desc={t(lang, "dash_section_dashboard_desc" as any)}
              tooltip={t(lang, `dash_tab_${activeTab}_desc` as any)}
            />
            {/* Tab buttons — 4 tabs */}
            <div className="flex gap-1 mb-3">
              {(["market", "trade", "travel", "detail"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={cn(
                    "flex-1 text-[10px] font-bold py-1.5 rounded-lg transition-colors",
                    activeTab === tab
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/15 text-muted-foreground hover:bg-muted/25"
                  )}
                >
                  {t(lang, `dash_tab_${tab}` as Parameters<typeof t>[1])}
                </button>
              ))}
            </div>

            <AnimatePresence mode="wait">
              <m.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
              >
                {/* ── Market Tab ── */}
                {activeTab === "market" && (
                  <div>
                    {summary?.market_snapshot && (summary.market_snapshot.commodities.length > 0 || summary.market_snapshot.indices.length > 0) ? (
                      <>
                        <div className="mb-2 rounded-lg bg-blue-500/5 px-3 py-1.5">
                          <p className="text-[10px] text-foreground/60 leading-relaxed">
                            {isPro && summary?.economy
                              ? summary.economy.split(". ").slice(0, 1).join(". ")
                              : t(lang, "dash_market_free_comment" as any)}
                          </p>
                        </div>
                        <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
                          {summary.market_snapshot.commodities.map((c) => (
                            <div key={c.symbol} className="shrink-0 rounded-lg bg-muted/15 px-3 py-2 min-w-[110px]">
                              <div className="flex items-center gap-1 mb-1">
                                <Fuel className="h-3 w-3 text-muted-foreground" />
                                <span className="text-[9px] text-muted-foreground font-medium">{c.name}</span>
                              </div>
                              <p className="text-sm font-bold tabular-nums">${c.price_usd.toLocaleString()}</p>
                              <span className={cn("text-[10px] font-medium tabular-nums", changePctColor(c.change_pct))}>
                                {c.change_pct > 0 ? "+" : ""}{c.change_pct.toFixed(2)}%
                              </span>
                            </div>
                          ))}
                          {summary.market_snapshot.exchange_rates.map((r) => (
                            <div key={r.target_currency} className="shrink-0 rounded-lg bg-muted/15 px-3 py-2 min-w-[100px]">
                              <div className="flex items-center gap-1 mb-1">
                                <Globe2 className="h-3 w-3 text-muted-foreground" />
                                <span className="text-[9px] text-muted-foreground font-medium">USD/{r.target_currency}</span>
                              </div>
                              <p className="text-sm font-bold tabular-nums">{r.rate.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                              {r.change_pct != null && (
                                <span className={cn("text-[10px] font-medium tabular-nums", changePctColor(r.change_pct))}>
                                  {r.change_pct > 0 ? "+" : ""}{r.change_pct.toFixed(2)}%
                                </span>
                              )}
                            </div>
                          ))}
                          {summary.market_snapshot.indices.map((i) => (
                            <div key={i.symbol} className="shrink-0 rounded-lg bg-muted/15 px-3 py-2 min-w-[110px]">
                              <div className="flex items-center gap-1 mb-1">
                                <TrendingUp className="h-3 w-3 text-muted-foreground" />
                                <span className="text-[9px] text-muted-foreground font-medium">{i.name}</span>
                              </div>
                              <p className="text-sm font-bold tabular-nums">{i.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                              <span className={cn("text-[10px] font-medium tabular-nums", changePctColor(i.change_pct))}>
                                {i.change_pct > 0 ? "+" : ""}{i.change_pct.toFixed(2)}%
                              </span>
                            </div>
                          ))}
                        </div>
                        <p className="text-[8px] text-muted-foreground/50 mt-2 text-center">
                          {t(lang, "dash_market_disclaimer" as Parameters<typeof t>[1])}
                        </p>
                      </>
                    ) : (
                      <p className="text-[11px] text-muted-foreground text-center py-4">
                        {lang === "ko" ? "시장 데이터를 불러오는 중..." : "Loading market data..."}
                      </p>
                    )}
                  </div>
                )}

                {/* ── Trade Tab (ProDemoWrapper) ── */}
                {activeTab === "trade" && (
                  <div>
                    {summary?.trade_exposure ? (
                      <ProDemoWrapper
                        isPro={isPro}
                        demoCount={1}
                        totalCount={summary.trade_exposure.top_partners.length}
                        ctaText={t(lang, "dash_pro_demo_trade" as any, { n: Math.max(0, summary.trade_exposure.top_partners.length - 1) })}
                        ctaHref="/upgrade?source=demo_trade"
                        lang={lang}
                      >
                        {summary.trade && isPro && (
                          <div className="mb-2 rounded-lg bg-orange-500/5 px-3 py-1.5">
                            <p className="text-[10px] text-foreground/60 leading-relaxed">
                              {summary.trade.split(". ").slice(0, 1).join(". ")}
                            </p>
                          </div>
                        )}
                        {summary.trade_exposure.top_partners.map((p: any) => (
                          <div key={p.country_code} className="mb-2">
                            <div className="flex items-center gap-1.5">
                              <span className="text-xs shrink-0">{getFlag(p.country_code)}</span>
                              <span className="text-[10px] font-medium truncate min-w-0 flex-1">
                                {getCountryName(p.country_code, lang)}
                              </span>
                              {isPro && p.trade_balance && (
                                <span className={cn("text-[7px] font-bold px-1 rounded shrink-0", p.trade_balance === "surplus" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400")}>
                                  {t(lang, p.trade_balance === "surplus" ? "dash_trade_surplus" as any : "dash_trade_deficit" as any)}
                                </span>
                              )}
                              <span className="text-[10px] font-bold tabular-nums text-orange-400 shrink-0">
                                {p.dependency_pct.toFixed(1)}%
                              </span>
                            </div>
                            <div className="flex items-center gap-1.5 mt-1">
                              <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-orange-400 transition-all duration-700"
                                  style={{ width: `${Math.min(p.dependency_pct, 100)}%` }}
                                />
                              </div>
                              {isPro && p.export_usd != null && p.import_usd != null && (
                                <span className="text-[7px] text-muted-foreground shrink-0">
                                  ↑{formatTradeVolume(p.export_usd)} ↓{formatTradeVolume(p.import_usd)}
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </ProDemoWrapper>
                    ) : (
                      <p className="text-[11px] text-muted-foreground text-center py-4">
                        {!summary
                          ? (lang === "ko" ? "교역 데이터를 불러오는 중..." : "Loading trade data...")
                          : (lang === "ko" ? "교역 데이터가 없습니다" : "No trade data available")}
                      </p>
                    )}
                  </div>
                )}

                {/* ── Travel Tab ── */}
                {activeTab === "travel" && (
                  <div>
                    {summary?.travel_advisories && summary.travel_advisories.length > 0 ? (
                      <>
                        {(() => {
                          const sorted = [...summary.travel_advisories].sort((a, b) => b.level - a.level);
                          const worst = sorted[0];
                          return (
                            <div className="mb-2 rounded-lg bg-amber-500/5 px-3 py-1.5">
                              <p className="text-[10px] text-foreground/60">
                                {t(lang, "dash_travel_comment" as any, { n: sorted.length })}
                                {worst && ` · ${t(lang, "dash_travel_comment_severe" as any, {
                                  country: getCountryName(worst.country_code, lang), level: worst.level
                                })}`}
                              </p>
                            </div>
                          );
                        })()}
                        <div className="space-y-1.5">
                          {summary.travel_advisories
                            .sort((a, b) => b.level - a.level)
                            .slice(0, 8)
                            .map((ta) => {
                              const tc = travelLevelColor(ta.level);
                              const lvlKey = `dash_travel_level_${ta.level}` as Parameters<typeof t>[1];
                              return (
                                <div
                                  key={`${ta.country_code}-${ta.source}`}
                                  className={cn("flex items-center gap-2 rounded-lg px-3 py-2 border", tc.bg, tc.border)}
                                >
                                  <span className="text-sm">{getFlag(ta.country_code)}</span>
                                  <span className="text-[11px] font-medium flex-1 truncate">
                                    {getCountryName(ta.country_code, lang)}
                                  </span>
                                  <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full", tc.text, tc.bg)}>
                                    Lv.{ta.level} {t(lang, lvlKey)}
                                  </span>
                                  {isPro && ta.title && (
                                    <span className="text-[9px] text-muted-foreground truncate max-w-[140px]">{ta.title}</span>
                                  )}
                                </div>
                              );
                            })}
                        </div>
                        <p className="text-[8px] text-muted-foreground/50 mt-2 text-center">
                          {t(lang, "dash_travel_source" as Parameters<typeof t>[1])}
                        </p>
                      </>
                    ) : (
                      <p className="text-[11px] text-muted-foreground text-center py-4">
                        {lang === "ko" ? "여행 경보 데이터 없음" : "No travel advisories"}
                      </p>
                    )}
                  </div>
                )}

                {/* ── Detail Analysis Tab (was Section 5, now ProDemoWrapper) ── */}
                {activeTab === "detail" && (
                  <div>
                    <ProDemoWrapper
                      isPro={isPro}
                      demoCount={1}
                      totalCount={3}
                      ctaText={t(lang, "dash_pro_demo_analysis" as any)}
                      ctaHref="/upgrade?source=demo_analysis"
                      lang={lang}
                    >
                      {/* Economy */}
                      <div className="rounded-lg border-l-2 border-blue-400 bg-blue-500/[0.03] p-3 mb-3">
                        <div className="flex items-center gap-2 mb-2">
                          <Briefcase className="h-3.5 w-3.5 shrink-0 text-blue-400" />
                          <span className="text-[10px] font-bold text-blue-400">{t(lang, "dash_pro_economy")}</span>
                        </div>
                        {hasPro && summary?.economy ? (
                          <div className="space-y-1">
                            {summary.economy.split(". ").filter(Boolean).map((sentence, i) => (
                              <div key={i} className="flex items-start gap-1.5">
                                <span className="mt-[5px] h-1 w-1 rounded-full bg-blue-400 shrink-0" />
                                <p className="text-[11px] text-foreground/70 leading-relaxed">{sentence.replace(/\.$/, "")}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="space-y-1.5">
                            <div className="h-3 rounded bg-muted/30 w-full" />
                            <div className="h-3 rounded bg-muted/30 w-3/4" />
                          </div>
                        )}
                      </div>

                      {/* Trade */}
                      <div className="rounded-lg border-l-2 border-orange-400 bg-orange-500/[0.03] p-3 mb-3">
                        <div className="flex items-center gap-2 mb-2">
                          <ShoppingCart className="h-3.5 w-3.5 shrink-0 text-orange-400" />
                          <span className="text-[10px] font-bold text-orange-400">{t(lang, "dash_pro_trade")}</span>
                        </div>
                        {hasPro && summary?.trade ? (
                          <div className="space-y-1">
                            {summary.trade.split(". ").filter(Boolean).map((sentence, i) => (
                              <div key={i} className="flex items-start gap-1.5">
                                <span className="mt-[5px] h-1 w-1 rounded-full bg-orange-400 shrink-0" />
                                <p className="text-[11px] text-foreground/70 leading-relaxed">{sentence.replace(/\.$/, "")}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="space-y-1.5">
                            <div className="h-3 rounded bg-muted/30 w-full" />
                            <div className="h-3 rounded bg-muted/30 w-2/3" />
                          </div>
                        )}
                      </div>

                      {/* Travel */}
                      <div className="rounded-lg border-l-2 border-emerald-400 bg-emerald-500/[0.03] p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <Plane className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                          <span className="text-[10px] font-bold text-emerald-400">{t(lang, "dash_pro_travel")}</span>
                        </div>
                        {hasPro && summary?.travel ? (
                          <div className="space-y-1">
                            {summary.travel.split(". ").filter(Boolean).map((sentence, i) => (
                              <div key={i} className="flex items-start gap-1.5">
                                <span className="mt-[5px] h-1 w-1 rounded-full bg-emerald-400 shrink-0" />
                                <p className="text-[11px] text-foreground/70 leading-relaxed">{sentence.replace(/\.$/, "")}</p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="space-y-1.5">
                            <div className="h-3 rounded bg-muted/30 w-full" />
                            <div className="h-3 rounded bg-muted/30 w-4/5" />
                          </div>
                        )}
                      </div>
                    </ProDemoWrapper>

                    {/* (SectorImpactCard moved to standalone section below) */}
                  </div>
                )}
              </m.div>
            </AnimatePresence>
          </m.section>

          {/* ═══════════════ SECTION D: 산업별 리스크 분석 ═══════════════ */}
          <m.section custom={3} initial="hidden" animate="visible" variants={sectionVariants}
            className="rounded-xl border border-purple-500/20 bg-card p-4"
          >
            <SectionHeader
              icon={Sparkles}
              title={lang === "ko" ? "산업별 리스크" : "Sector Risk"}
              desc={lang === "ko" ? "전체 활성 이슈 기반" : "Based on all active issues"}
              tooltip={lang === "ko"
                ? "현재 모든 활성 분쟁 이슈의 영향을 종합하여, 기준국가의 산업별 교역 의존도와 리스크를 분석합니다."
                : "Aggregated analysis of trade dependency and risk across all active conflict issues."}
            />
            <SectorImpactCard embedded />
          </m.section>

          {/* ═══════════════ Disclaimer ═══════════════ */}
          <Disclaimer />

        </div>
      </div>

      {/* ═══════════════ 기준 국가 선택 바텀시트 ═══════════════ */}
      {showCountryPicker && (
        <>
          <div className="fixed inset-0 z-50 bg-black/40" onClick={() => setShowCountryPicker(false)} />
          <div className="fixed bottom-[60px] left-0 right-0 z-50 rounded-t-2xl border-t border-border bg-card shadow-2xl animate-in slide-in-from-bottom duration-200 max-w-lg mx-auto max-h-[60vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
              <h3 className="text-sm font-bold">
                {lang === "ko" ? "기준 국가 선택" : "Select Base Country"}
              </h3>
              <button
                onClick={() => setShowCountryPicker(false)}
                className="p-1 rounded-full hover:bg-muted/50 transition-colors"
              >
                <X className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
            <div className="overflow-y-auto flex-1 py-2 overscroll-contain">
              {/* 글로벌 옵션 */}
              <button
                onClick={() => {
                  setHomeCountry("");
                  setShowCountryPicker(false);
                }}
                className={cn(
                  "w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-muted/10 transition-colors",
                  !homeCountry && "bg-primary/5"
                )}
              >
                <span className="text-lg">🌐</span>
                <span className="text-sm flex-1">{lang === "ko" ? "글로벌 (전체)" : "Global (All)"}</span>
                <span className="text-[10px] text-muted-foreground">ALL</span>
                {!homeCountry && <Check className="h-4 w-4 text-primary" />}
              </button>
              {/* 대륙별 그룹 */}
              {([
                { label: lang === "ko" ? "동아시아" : "East Asia", codes: ["KR", "JP", "CN", "TW"] },
                { label: lang === "ko" ? "동남아 · 오세아니아" : "SE Asia · Oceania", codes: ["TH", "VN", "SG", "ID", "PH", "AU"] },
                { label: lang === "ko" ? "남아시아 · 중동" : "South Asia · Middle East", codes: ["IN", "SA", "AE", "IL", "EG", "TR"] },
                { label: lang === "ko" ? "유럽" : "Europe", codes: ["DE", "GB", "FR", "PL", "RU"] },
                { label: lang === "ko" ? "아메리카" : "Americas", codes: ["US", "CA", "MX", "BR"] },
              ] as { label: string; codes: string[] }[]).map((group) => {
                const groupCountries = group.codes.filter((c) => availableCountries.includes(c));
                if (!groupCountries.length) return null;
                return (
                  <div key={group.label}>
                    <div className="px-5 pt-3 pb-1">
                      <span className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider">{group.label}</span>
                    </div>
                    {groupCountries.map((cc) => (
                      <button
                        key={cc}
                        onClick={() => {
                          setHomeCountry(cc);
                          setShowCountryPicker(false);
                        }}
                        className={cn(
                          "w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-muted/10 transition-colors",
                          homeCountry === cc && "bg-primary/5"
                        )}
                      >
                        <span className="text-lg">{getFlag(cc)}</span>
                        <span className="text-sm flex-1">{getCountryName(cc, lang)}</span>
                        <span className="text-[10px] text-muted-foreground">{cc}</span>
                        {homeCountry === cc && <Check className="h-4 w-4 text-primary" />}
                      </button>
                    ))}
                  </div>
                );
              })}
              {!isPro && availableCountries.length === 0 && (
                <div className="px-5 py-4 text-center border-t border-border/30 mt-2">
                  <p className="text-[10px] text-muted-foreground mb-2">
                    {lang === "ko"
                      ? "Pro 플랜에서 특정 국가를 기준으로 개인화된 분석을 받을 수 있습니다"
                      : "Get personalized analysis from specific countries' perspective with Pro"}
                  </p>
                  <a
                    href="/upgrade?source=home_country_picker"
                    className="inline-flex rounded-full px-4 py-1.5 text-[10px] font-bold text-white"
                    style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
                  >
                    {lang === "ko" ? "Pro로 업그레이드" : "Upgrade to Pro"}
                  </a>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

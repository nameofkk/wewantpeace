"use client";

import React, { Suspense, useMemo, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
import {
  useMe,
  useTrackBehavior,
  useImpactSummary,
  useTensionMine,
  useTensionAll,
  type TensionAllItem,
  type MarketSnapshot,
  type TravelAlert,
  type TradeExposure,
} from "@/lib/api";
import { t } from "@/lib/i18n";
import {
  TOPIC_COLORS,
  personalizedKScore,
  roundKScore,
  kscoreAccent,
  getKScoreBadge,
  type TrendingItem,
} from "@/lib/kscore-utils";
import { useCountUp } from "@/hooks/useCountUp";
import { NoticeTicker } from "@/components/dashboard/NoticeTicker";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { Disclaimer } from "@/components/ui/Disclaimer";
import {
  Shield,
  ChevronRight,
  MapPin,
  Plus,
  Briefcase,
  ShoppingCart,
  Plane,
  Lock,
  Radio,
  Activity,
  AlertTriangle,
  TrendingUp,
  ExternalLink,
  Fuel,
  BarChart3,
  Globe2,
  Zap,
  ArrowRight,
} from "lucide-react";

export default function HomePage() {
  return (
    <Suspense fallback={<div className="p-4"><DashboardSkeleton /></div>}>
      <ReportContent />
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

function tensionLabel(score: number, lang: "ko" | "en") {
  if (score >= 80) return lang === "ko" ? "극심" : "Extreme";
  if (score >= 60) return lang === "ko" ? "심각" : "Severe";
  if (score >= 40) return lang === "ko" ? "경계" : "Alert";
  if (score >= 20) return lang === "ko" ? "주의" : "Caution";
  return lang === "ko" ? "안정" : "Stable";
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
  // 한국 주식 관례: 양수=빨강, 음수=파랑
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

/* ───────────────────────── Impact Chain 유틸 ───────────────────────── */

function getRelevantMarketData(issue: TrendingItem, market: MarketSnapshot | null | undefined) {
  if (!market) return [];
  const cc = issue.country_codes?.[0] ?? "";
  if (["IL", "IR", "IQ", "SA", "SY", "LB", "YE"].includes(cc))
    return market.commodities.filter((c) => ["WTI", "BRENT"].includes(c.symbol));
  if (["CN", "TW", "JP", "KP", "KR"].includes(cc))
    return market.indices.filter((i) => ["KOSPI", "NKY"].includes(i.symbol)).map((i) => ({
      symbol: i.symbol, name: i.name, price_usd: i.value, change_pct: i.change_pct,
    }));
  if (["UA", "RU", "DE", "FR", "GB"].includes(cc))
    return market.indices.filter((i) => ["DAX", "FTSE"].includes(i.symbol)).map((i) => ({
      symbol: i.symbol, name: i.name, price_usd: i.value, change_pct: i.change_pct,
    }));
  return market.commodities.slice(0, 1);
}

/* ───────────────────────── 메인 리포트 ───────────────────────── */

function ReportContent() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const homeCountry = useAppStore((s) => s.homeCountry);
  const myCountries = useAppStore((s) => s.myCountries);

  const { data: me, isLoading: meLoading } = useMe();
  const meObj = me as { plan?: string; nickname?: string; display_name?: string } | undefined;
  const userPlan = meObj?.plan ?? "free";
  const nickname = meObj?.nickname || meObj?.display_name || (lang === "ko" ? "사용자" : "User");

  // 데이터 훅 — 모두 병렬 실행
  const { data: summary, isLoading: summaryLoading } = useImpactSummary();
  const { data: homeTension, dataUpdatedAt } = useTensionMine(homeCountry ? [homeCountry] : null);
  const { data: allTension } = useTensionAll();
  const { data: watchlistTension } = useTensionMine(myCountries.length > 0 ? myCountries : null);
  // useClusters 제거 — top_issues에서 직접 사용

  // Insight Tabs state
  const [activeTab, setActiveTab] = useState<"market" | "trade" | "travel">("market");

  // 트래킹
  const trackBehavior = useTrackBehavior();
  useEffect(() => {
    trackBehavior.mutate({ event_name: "dashboard_view", props: { plan: userPlan } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 파생 데이터
  const isGlobalMode = !homeCountry;

  const homeData = Array.isArray(homeTension) ? homeTension[0] : null;
  const singleCountryScore = (homeData as TensionAllItem | null)?.raw_score ?? 0;

  const allItems = (allTension as TensionAllItem[] | undefined) ?? [];

  // 글로벌 모드: allTension 평균 사용
  const globalAvgScore = useMemo(() => {
    if (!isGlobalMode || !allItems.length) return 0;
    return Math.round(allItems.reduce((s, i) => s + i.raw_score, 0) / allItems.length);
  }, [isGlobalMode, allItems]);

  const homeScore = isGlobalMode ? globalAvgScore : singleCountryScore;
  const animatedHomeScore = useCountUp(homeScore, 1000);
  const extremeCount = allItems.filter((i) => i.raw_score >= 80).length;
  const severeCount = allItems.filter((i) => i.raw_score >= 60 && i.raw_score < 80).length;
  const alertCount = allItems.filter((i) => i.raw_score >= 40 && i.raw_score < 60).length;

  const updatedTime = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(lang === "ko" ? "ko-KR" : "en-US", { hour: "2-digit", minute: "2-digit" })
    : null;

  // 관심국가 텐션 매핑
  const watchlistItems = (watchlistTension as TensionAllItem[] | undefined) ?? [];
  const tensionMap = new Map(watchlistItems.map((t: any) => [t.country_code, t]));
  // allTension 매핑 (anomaly_z, convergence_bonus 뱃지용)
  const allTensionMap = new Map(allItems.map((t) => [t.country_code, t]));

  // Impact Summary 파생
  const impactScore = summary?.score ?? 0;
  const animatedImpact = useCountUp(impactScore, 900);
  const color = impactColor(impactScore);
  const levelKey = `dash_impact_level_${summary?.level || "low"}` as Parameters<typeof t>[1];
  const hasPro = !!(summary?.economy || summary?.trade || summary?.travel);
  const isPro = userPlan === "pro" || userPlan === "pro_plus";

  // Top Issues (summary.top_issues 기반 — useClusters 제거)
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

  if (meLoading || summaryLoading) {
    return <div className="p-4"><DashboardSkeleton /></div>;
  }

  // #1 이슈 데이터
  const topIssue = topItems[0];
  const restIssues = topItems.slice(1);

  return (
    <div className="flex flex-col" style={{ height: "calc(100dvh - 60px)" }}>
      <NoticeTicker />

      {/* ──── Scrollable Report Body ──── */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-4 space-y-5">

          {/* ═══════════════ SECTION 1: Compact Hero (영향도 + 긴장도 통합) ═══════════════ */}
          <section className="rounded-xl border border-border bg-card p-4 stagger-item" style={{ "--stagger-delay": "0ms" } as React.CSSProperties}>
            {/* Impact Score + Level + LIVE */}
            <div className="flex items-center gap-3 mb-2">
              <span className="text-3xl font-bold tabular-nums leading-none" style={{ color }}>
                {Math.round(animatedImpact)}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{ color, backgroundColor: `${color}15` }}
                  >
                    {t(lang, levelKey)}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {t(lang, "dash_impact_score")} · {isGlobalMode
                      ? t(lang, "dash_global_impact_desc" as any)
                      : t(lang, "dash_impact_score_desc" as any)}
                  </span>
                </div>
              </div>
            </div>

            {/* Horizontal bar gauge */}
            <div className="h-2 rounded-full bg-muted overflow-hidden mb-2">
              <div
                className="h-full rounded-full transition-all duration-1000 ease-out"
                style={{ width: `${Math.min(impactScore, 100)}%`, backgroundColor: color }}
              />
            </div>

            {/* 1줄 요약 */}
            <p className="text-[11px] text-foreground/80 leading-relaxed line-clamp-2 mb-3">
              {summary?.summary || (lang === "ko" ? "분석 데이터를 불러오는 중..." : "Loading analysis...")}
            </p>

            {/* Row 4a: 홈 긴장도 + 글로벌 현황 (통합) */}
            <div className="flex items-center gap-2 text-[11px] mb-1.5 flex-wrap">
              <span className="text-base">{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
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

            {/* Row 4b: 이슈 통계 + 업데이트 시간 */}
            <div className="flex items-center gap-3 text-[10px] text-muted-foreground mb-3">
              <span>{lang === "ko" ? "이슈" : "Issues"} <strong>{summary?.total_active_issues ?? 0}</strong></span>
              <span className="text-red-400">{t(lang, "dash_high_impact")} <strong>{summary?.critical_issues_count ?? 0}</strong></span>
              {updatedTime && <span className="ml-auto">{updatedTime}</span>}
            </div>

            {/* 관심국가 칩 */}
            {myCountries.length > 0 ? (
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
          </section>

          {/* ═══════════════ SECTION 2: Impact Chain Card (#1 이슈) ═══════════════ */}
          {topIssue && (() => {
            const topic = topIssue.topic ?? "unknown";
            const pKScore = personalizedKScore(topIssue, homeCountry);
            const k = roundKScore(pKScore);
            const badge = getKScoreBadge(pKScore, lang);
            const clusterId = topIssue.cluster_ids?.[0];
            const rawTitle = lang === "en" ? topIssue.keyword : (topIssue.keyword_ko ?? topIssue.keyword);
            const topicKey = `topic_${topic}` as Parameters<typeof t>[1];
            const topicLabel = t(lang, topicKey) || topic;
            const displayTitle = isJunkTitle(rawTitle)
              ? buildSmartTitle(topIssue.keyword, topic, lang, getCountryName, topIssue.country_codes[0])
              : (stripTitlePrefix(rawTitle) || topicLabel);

            const relevantMarket = getRelevantMarketData(topIssue, summary?.market_snapshot);
            const reason = summary?.top_issues?.[0]?.reason;

            return (
              <section
                className="rounded-xl border border-border bg-card overflow-hidden stagger-item card-interactive cursor-pointer"
                style={{ "--stagger-delay": "80ms" } as React.CSSProperties}
                onClick={clusterId ? () => router.push(`/issues/${clusterId}`) : undefined}
              >
                {/* Header */}
                <div className={cn("px-4 pt-3 pb-2 border-b border-border/30", kscoreAccent(pKScore))}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[9px] font-bold text-muted-foreground uppercase tracking-wider">
                      {t(lang, "dash_top_issue_label" as Parameters<typeof t>[1])}
                    </span>
                    <span className={cn(
                      "inline-flex items-center h-4 rounded-full px-1.5 text-[9px] font-medium leading-none",
                      TOPIC_COLORS[topic]
                    )}>
                      {topicLabel}
                    </span>
                    {topIssue.is_spike && (
                      <span className="text-[8px] px-1 py-0.5 rounded bg-red-500/10 text-red-400 font-medium">
                        {t(lang, "dash_badge_spike" as any)}
                      </span>
                    )}
                    {(topIssue.confidence ?? 0) >= 0.7 && (
                      <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
                        {t(lang, "dash_badge_verified" as any)}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      {topIssue.country_codes.length > 0 && (
                        <span className="text-base">
                          {topIssue.country_codes.map((code: string) => getFlag(code)).join(" ")}
                        </span>
                      )}
                      <h3 className="text-[13px] font-bold leading-snug line-clamp-1">{displayTitle}</h3>
                    </div>
                    <div className="shrink-0 ml-2 text-right">
                      <span className={cn("text-[9px]", badge.text)}>KScore</span>
                      <span className={cn("text-lg font-bold tabular-nums leading-none", badge.text)}>
                        {k.toFixed(1)}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Impact Chain */}
                <div className="px-4 py-3 space-y-2">
                  {/* Chain: 분쟁 → 지표 → 내 영향 */}
                  <div className="flex items-start gap-2">
                    <div className="flex flex-col items-center shrink-0">
                      <span className="text-[10px]">&#9876;&#65039;</span>
                      <div className="w-px h-3 bg-border" />
                    </div>
                    <div className="text-[11px]">
                      <span className="font-bold text-red-500">{t(lang, "dash_chain_conflict" as Parameters<typeof t>[1])}</span>
                      <span className="text-foreground/70 ml-1">{displayTitle}</span>
                    </div>
                  </div>

                  {relevantMarket.length > 0 && (
                    <div className="flex items-start gap-2">
                      <div className="flex flex-col items-center shrink-0">
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        <div className="w-px h-3 bg-border" />
                      </div>
                      <div className="text-[11px] flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-orange-500">{t(lang, "dash_chain_indicator" as Parameters<typeof t>[1])}</span>
                        {relevantMarket.map((m) => (
                          <span key={m.symbol} className="inline-flex items-center gap-1 rounded bg-muted/20 px-1.5 py-0.5">
                            <span className="font-medium">{m.name}</span>
                            <span className="tabular-nums">${m.price_usd.toLocaleString()}</span>
                            <span className={cn("font-medium tabular-nums", changePctColor(m.change_pct))}>
                              {m.change_pct > 0 ? "+" : ""}{m.change_pct.toFixed(1)}%
                            </span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {reason && (
                    <div className="flex items-start gap-2">
                      <div className="flex flex-col items-center shrink-0">
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      </div>
                      <div className="text-[11px]">
                        <span className="font-bold text-blue-500">{t(lang, "dash_chain_your_impact" as Parameters<typeof t>[1])}</span>
                        <span className="text-foreground/70 ml-1">{reason}</span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer */}
                <div className="px-4 pb-3 flex justify-end">
                  <span className="text-[10px] text-primary font-medium flex items-center gap-1">
                    {t(lang, "dash_chain_detail" as Parameters<typeof t>[1])}
                    <ChevronRight className="h-3 w-3" />
                  </span>
                </div>
              </section>
            );
          })()}

          {/* ═══════════════ SECTION 3: Top Issues #2-#5 (콤팩트) ═══════════════ */}
          {restIssues.length > 0 && (
            <section className="rounded-xl border border-border bg-card stagger-item" style={{ "--stagger-delay": "160ms" } as React.CSSProperties}>
              <div className="px-4 pt-3 pb-1">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" />
                  <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                    {t(lang, "dash_top_issues", { name: nickname })}
                  </h2>
                </div>
              </div>
              <div className="px-4 pb-3">
                {restIssues.map((item, idx) => {
                  const topic = item.topic ?? "unknown";
                  const pKScore = personalizedKScore(item, homeCountry);
                  const k = roundKScore(pKScore);
                  const badge = getKScoreBadge(pKScore, lang);
                  const clusterId = item.cluster_ids?.[0];
                  const rawTitle = lang === "en" ? item.keyword : (item.keyword_ko ?? item.keyword);
                  const topicKey = `topic_${topic}` as Parameters<typeof t>[1];
                  const topicLabel = t(lang, topicKey) || topic;
                  const displayTitle = isJunkTitle(rawTitle)
                    ? buildSmartTitle(item.keyword, topic, lang, getCountryName, item.country_codes[0])
                    : (stripTitlePrefix(rawTitle) || topicLabel);

                  return (
                    <div
                      key={item.id}
                      onClick={clusterId ? () => router.push(`/issues/${clusterId}`) : undefined}
                      className={cn(
                        "flex items-center gap-2 py-2.5 cursor-pointer hover:bg-muted/10 transition-all duration-200 rounded-lg px-1 -mx-1",
                        idx < restIssues.length - 1 && "border-b border-border/30",
                      )}
                    >
                      <span className="text-[10px] font-bold text-muted-foreground w-5 text-center">#{idx + 2}</span>
                      {item.country_codes.length > 0 && (
                        <span className="text-[11px]">
                          {item.country_codes.map((code: string) => getFlag(code)).join("")}
                        </span>
                      )}
                      <div className="flex-1 min-w-0">
                        <span className="text-[11px] font-medium truncate block">{displayTitle}</span>
                        {item.reason && (
                          <div className="flex items-center gap-1 mt-0.5">
                            <Zap className="h-2.5 w-2.5 text-blue-400 shrink-0" />
                            <span className="text-[9px] text-blue-400 font-medium shrink-0">
                              {t(lang, "dash_chain_your_impact" as any)}
                            </span>
                            <span className="text-[9px] text-foreground/50 truncate">
                              {item.reason}
                            </span>
                          </div>
                        )}
                      </div>
                      <div className="shrink-0 flex items-center gap-0.5">
                        <span className="text-[8px] text-muted-foreground">K</span>
                        <span className={cn("text-sm font-bold tabular-nums", badge.text)}>
                          {k.toFixed(1)}
                        </span>
                      </div>
                      <ChevronRight className="h-3 w-3 text-muted-foreground shrink-0" />
                    </div>
                  );
                })}
              </div>
              <Link
                href="/feed"
                className="flex items-center justify-center gap-1.5 border-t border-border/30 py-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted/10 transition-colors rounded-b-xl"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                {t(lang, "dash_view_all_issues")}
              </Link>
            </section>
          )}

          {topItems.length === 0 && (
            <section className="rounded-xl border border-border bg-card/50 p-5 text-center stagger-item" style={{ "--stagger-delay": "160ms" } as React.CSSProperties}>
              <Activity className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
              <p className="text-[11px] text-muted-foreground">{t(lang, "dash_no_issues")}</p>
            </section>
          )}

          {/* ═══════════════ SECTION 4: Insight Tabs (시장/교역/여행 통합) ═══════════════ */}
          <section className="rounded-xl border border-border bg-card p-4 stagger-item" style={{ "--stagger-delay": "240ms" } as React.CSSProperties}>
            {/* 탭 버튼 */}
            <div className="flex gap-1 mb-3">
              {(["market", "trade", "travel"] as const).map((tab) => (
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

            {/* 시장 동향 탭 */}
            {activeTab === "market" && (
              <div>
                {summary?.market_snapshot && (summary.market_snapshot.commodities.length > 0 || summary.market_snapshot.indices.length > 0) ? (
                  <>
                    {summary?.market_snapshot && (
                      <div className="mb-2 rounded-lg bg-blue-500/5 px-3 py-1.5">
                        <p className="text-[10px] text-foreground/60 leading-relaxed">
                          {isPro && summary?.economy
                            ? summary.economy.split(". ").slice(0, 1).join(". ")
                            : t(lang, "dash_market_free_comment" as any)}
                        </p>
                      </div>
                    )}
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

            {/* 교역 노출 탭 */}
            {activeTab === "trade" && (
              <div>
                {summary?.trade_exposure && isPro ? (
                  <div className="space-y-2">
                    {isPro && summary?.trade && (
                      <div className="mb-2 rounded-lg bg-orange-500/5 px-3 py-1.5">
                        <p className="text-[10px] text-foreground/60 leading-relaxed">
                          {summary.trade.split(". ").slice(0, 1).join(". ")}
                        </p>
                      </div>
                    )}
                    {summary.trade_exposure.top_partners.map((p: any) => (
                      <div key={p.country_code} className="flex items-center gap-2">
                        <span className="text-sm">{getFlag(p.country_code)}</span>
                        <span className="text-[11px] font-medium w-16 truncate">
                          {getCountryName(p.country_code, lang)}
                        </span>
                        {p.trade_balance && (
                          <span className={cn("text-[8px] font-bold px-1 rounded", p.trade_balance === "surplus" ? "bg-emerald-500/10 text-emerald-400" : "bg-red-500/10 text-red-400")}>
                            {t(lang, p.trade_balance === "surplus" ? "dash_trade_surplus" as any : "dash_trade_deficit" as any)}
                          </span>
                        )}
                        <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden">
                          <div
                            className="h-full rounded-full bg-orange-400 transition-all duration-700"
                            style={{ width: `${Math.min(p.dependency_pct, 100)}%` }}
                          />
                        </div>
                        <span className="text-[10px] font-bold tabular-nums text-orange-400 w-12 text-right">
                          {p.dependency_pct.toFixed(1)}%
                        </span>
                        <span className="text-[9px] text-muted-foreground tabular-nums w-16 text-right">
                          {formatTradeVolume(p.trade_volume_usd)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : !isPro ? (
                  <div className="relative">
                    <div className="space-y-2 opacity-40 blur-[2px] select-none pointer-events-none">
                      {[1,2,3,4,5].map((i) => (
                        <div key={i} className="flex items-center gap-2">
                          <div className="h-5 w-5 rounded bg-muted/30" />
                          <div className="h-3 w-16 rounded bg-muted/30" />
                          <div className="flex-1 h-2 rounded-full bg-muted/20" />
                          <div className="h-3 w-12 rounded bg-muted/30" />
                        </div>
                      ))}
                    </div>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <Lock className="h-4 w-4 text-muted-foreground mb-1.5" />
                      <Link
                        href="/upgrade"
                        className="inline-flex rounded-full px-3 py-1 text-[9px] font-bold text-white"
                        style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
                      >
                        {t(lang, "dash_unlock_pro")}
                      </Link>
                    </div>
                  </div>
                ) : (
                  <p className="text-[11px] text-muted-foreground text-center py-4">
                    {lang === "ko" ? "교역 데이터를 불러오는 중..." : "Loading trade data..."}
                  </p>
                )}
              </div>
            )}

            {/* 여행 경보 탭 */}
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
                                <span className="text-[9px] text-muted-foreground truncate max-w-[80px]">{ta.title}</span>
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
          </section>

          {/* ═══════════════ SECTION 5: 상세 영향 분석 (Pro) ═══════════════ */}
          <section className="rounded-xl border border-border bg-card overflow-hidden stagger-item" style={{ "--stagger-delay": "320ms" } as React.CSSProperties}>
            {/* Report Header Band */}
            <div className="px-4 pt-3 pb-2 border-b border-border/30 bg-gradient-to-r from-blue-500/5 via-transparent to-indigo-500/5">
              <div className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-blue-400" />
                <h2 className="text-xs font-bold tracking-wide">
                  {t(lang, "dash_pro_detail", { name: nickname })}
                </h2>
                <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-gradient-to-r from-blue-500/15 to-indigo-500/15 text-blue-400 font-bold">Pro</span>
              </div>
              <p className="text-[9px] text-muted-foreground/60 mt-0.5 ml-6">
                {t(lang, "dash_impact_brief_desc")}
              </p>
            </div>

            <div className="p-4">
              {hasPro && isPro ? (
                <div className="space-y-3">

                  {/* ── 경제 영향 ── */}
                  {summary?.economy && (
                    <div className="rounded-lg border-l-2 border-blue-400 bg-blue-500/[0.03] p-3 stagger-item" style={{ "--stagger-delay": "400ms" } as React.CSSProperties}>
                      <div className="flex items-center gap-2 mb-2">
                        <Briefcase className="h-3.5 w-3.5 shrink-0 text-blue-400" />
                        <span className="text-[10px] font-bold text-blue-400">{t(lang, "dash_pro_economy")}</span>
                      </div>
                      {/* 핵심 지표 칩 */}
                      {summary.market_snapshot && (
                        <div className="flex gap-1.5 overflow-x-auto scrollbar-hide mb-2.5 pb-0.5">
                          {summary.market_snapshot.commodities.slice(0, 2).map((c) => (
                            <div key={c.symbol} className="shrink-0 flex items-center gap-1.5 bg-background/60 rounded-md px-2 py-1 border border-border/30">
                              <Fuel className="h-2.5 w-2.5 text-muted-foreground/60" />
                              <span className="text-[9px] text-muted-foreground font-medium">{c.name}</span>
                              <span className="text-[10px] font-bold tabular-nums">${c.price_usd.toLocaleString()}</span>
                              <span className={cn("text-[9px] font-bold tabular-nums", changePctColor(c.change_pct))}>
                                {c.change_pct > 0 ? "+" : ""}{c.change_pct.toFixed(1)}%
                              </span>
                            </div>
                          ))}
                          {summary.market_snapshot.indices.slice(0, 2).map((i) => (
                            <div key={i.symbol} className="shrink-0 flex items-center gap-1.5 bg-background/60 rounded-md px-2 py-1 border border-border/30">
                              <TrendingUp className="h-2.5 w-2.5 text-muted-foreground/60" />
                              <span className="text-[9px] text-muted-foreground font-medium">{i.name}</span>
                              <span className="text-[10px] font-bold tabular-nums">{i.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                              <span className={cn("text-[9px] font-bold tabular-nums", changePctColor(i.change_pct))}>
                                {i.change_pct > 0 ? "+" : ""}{i.change_pct.toFixed(1)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* 분석 불릿 */}
                      <div className="space-y-1">
                        {summary.economy.split(". ").filter(Boolean).map((sentence, i) => (
                          <div key={i} className="flex items-start gap-1.5">
                            <span className="mt-[5px] h-1 w-1 rounded-full bg-blue-400 shrink-0" />
                            <p className="text-[11px] text-foreground/70 leading-relaxed">{sentence.replace(/\.$/, "")}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ── 교역 영향 ── */}
                  {summary?.trade && (
                    <div className="rounded-lg border-l-2 border-orange-400 bg-orange-500/[0.03] p-3 stagger-item" style={{ "--stagger-delay": "480ms" } as React.CSSProperties}>
                      <div className="flex items-center gap-2 mb-2">
                        <ShoppingCart className="h-3.5 w-3.5 shrink-0 text-orange-400" />
                        <span className="text-[10px] font-bold text-orange-400">{t(lang, "dash_pro_trade")}</span>
                      </div>
                      {/* 교역국 리스크 바 */}
                      {summary.trade_exposure?.top_partners && summary.trade_exposure.top_partners.length > 0 && (
                        <div className="space-y-1.5 mb-2.5">
                          {summary.trade_exposure.top_partners.slice(0, 3).map((p) => (
                            <div key={p.country_code} className="flex items-center gap-2">
                              <span className="text-xs">{getFlag(p.country_code)}</span>
                              <span className="text-[10px] font-medium w-14 truncate">{getCountryName(p.country_code, lang)}</span>
                              <div className="flex-1 h-1.5 rounded-full bg-background/50 overflow-hidden">
                                <div className="h-full rounded-full bg-orange-400/60 transition-all duration-700" style={{ width: `${Math.min(p.dependency_pct, 100)}%` }} />
                              </div>
                              <span className="text-[9px] font-bold tabular-nums text-orange-400 w-10 text-right">{p.dependency_pct.toFixed(1)}%</span>
                            </div>
                          ))}
                        </div>
                      )}
                      {/* 분석 불릿 */}
                      <div className="space-y-1">
                        {summary.trade.split(". ").filter(Boolean).map((sentence, i) => (
                          <div key={i} className="flex items-start gap-1.5">
                            <span className="mt-[5px] h-1 w-1 rounded-full bg-orange-400 shrink-0" />
                            <p className="text-[11px] text-foreground/70 leading-relaxed">{sentence.replace(/\.$/, "")}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ── 여행 안전 ── */}
                  {summary?.travel && (
                    <div className="rounded-lg border-l-2 border-emerald-400 bg-emerald-500/[0.03] p-3 stagger-item" style={{ "--stagger-delay": "560ms" } as React.CSSProperties}>
                      <div className="flex items-center gap-2 mb-2">
                        <Plane className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
                        <span className="text-[10px] font-bold text-emerald-400">{t(lang, "dash_pro_travel")}</span>
                      </div>
                      {/* 여행 경보 뱃지 */}
                      {summary.travel_advisories && summary.travel_advisories.length > 0 && (
                        <div className="flex gap-1.5 flex-wrap mb-2.5">
                          {[...summary.travel_advisories].sort((a, b) => b.level - a.level).slice(0, 5).map((ta) => {
                            const tc = travelLevelColor(ta.level);
                            return (
                              <div key={`pro-${ta.country_code}-${ta.source}`} className={cn("flex items-center gap-1 rounded-full px-2 py-0.5 border", tc.bg, tc.border)}>
                                <span className="text-[10px]">{getFlag(ta.country_code)}</span>
                                <span className={cn("text-[9px] font-bold", tc.text)}>Lv.{ta.level}</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                      {/* 분석 불릿 */}
                      <div className="space-y-1">
                        {summary.travel.split(". ").filter(Boolean).map((sentence, i) => (
                          <div key={i} className="flex items-start gap-1.5">
                            <span className="mt-[5px] h-1 w-1 rounded-full bg-emerald-400 shrink-0" />
                            <p className="text-[11px] text-foreground/70 leading-relaxed">{sentence.replace(/\.$/, "")}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                </div>
              ) : (
                <div className="relative">
                  <div className="space-y-3 opacity-40 blur-[2px] select-none pointer-events-none">
                    {/* 블러 처리된 경제 카드 */}
                    <div className="rounded-lg border-l-2 border-blue-400 bg-blue-500/[0.03] p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <Briefcase className="h-3.5 w-3.5 text-blue-400" />
                        <span className="text-[10px] font-bold text-blue-400">{t(lang, "dash_pro_economy")}</span>
                      </div>
                      <div className="flex gap-1.5 mb-2">
                        <div className="h-6 w-24 rounded bg-muted/30" />
                        <div className="h-6 w-24 rounded bg-muted/30" />
                      </div>
                      <div className="space-y-1.5">
                        <div className="h-3 rounded bg-muted/30 w-full" />
                        <div className="h-3 rounded bg-muted/30 w-3/4" />
                      </div>
                    </div>
                    {/* 블러 처리된 교역 카드 */}
                    <div className="rounded-lg border-l-2 border-orange-400 bg-orange-500/[0.03] p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <ShoppingCart className="h-3.5 w-3.5 text-orange-400" />
                        <span className="text-[10px] font-bold text-orange-400">{t(lang, "dash_pro_trade")}</span>
                      </div>
                      <div className="space-y-1.5 mb-2">
                        <div className="flex items-center gap-2"><div className="h-4 w-4 rounded bg-muted/30" /><div className="flex-1 h-1.5 rounded-full bg-muted/20" /><div className="h-3 w-8 rounded bg-muted/30" /></div>
                        <div className="flex items-center gap-2"><div className="h-4 w-4 rounded bg-muted/30" /><div className="flex-1 h-1.5 rounded-full bg-muted/20" /><div className="h-3 w-8 rounded bg-muted/30" /></div>
                      </div>
                      <div className="space-y-1.5">
                        <div className="h-3 rounded bg-muted/30 w-full" />
                        <div className="h-3 rounded bg-muted/30 w-2/3" />
                      </div>
                    </div>
                    {/* 블러 처리된 여행 카드 */}
                    <div className="rounded-lg border-l-2 border-emerald-400 bg-emerald-500/[0.03] p-3">
                      <div className="flex items-center gap-2 mb-2">
                        <Plane className="h-3.5 w-3.5 text-emerald-400" />
                        <span className="text-[10px] font-bold text-emerald-400">{t(lang, "dash_pro_travel")}</span>
                      </div>
                      <div className="flex gap-1.5 mb-2">
                        <div className="h-5 w-16 rounded-full bg-muted/30" />
                        <div className="h-5 w-16 rounded-full bg-muted/30" />
                        <div className="h-5 w-16 rounded-full bg-muted/30" />
                      </div>
                      <div className="space-y-1.5">
                        <div className="h-3 rounded bg-muted/30 w-full" />
                        <div className="h-3 rounded bg-muted/30 w-4/5" />
                      </div>
                    </div>
                  </div>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <Lock className="h-5 w-5 text-muted-foreground mb-2" />
                    <p className="text-[11px] text-muted-foreground mb-3 text-center px-4">
                      {t(lang, "dash_pro_locked")}
                    </p>
                    <Link
                      href="/upgrade"
                      className="inline-flex rounded-full px-4 py-1.5 text-[10px] font-bold text-white"
                      style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
                    >
                      {t(lang, "dash_unlock_pro")}
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* ═══════════════ Disclaimer ═══════════════ */}
          <Disclaimer />

        </div>
      </div>
    </div>
  );
}

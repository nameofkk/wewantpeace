"use client";

import React, { Suspense, useMemo, useEffect } from "react";
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
  useClusters,
  type TensionAllItem,
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
  const { data: clusterData } = useClusters({ limit: "2000" });

  // 트래킹
  const trackBehavior = useTrackBehavior();
  useEffect(() => {
    trackBehavior.mutate({ event_name: "dashboard_view", props: { plan: userPlan } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 파생 데이터
  const homeData = Array.isArray(homeTension) ? homeTension[0] : null;
  const homeScore = (homeData as TensionAllItem | null)?.raw_score ?? 0;
  const animatedHomeScore = useCountUp(homeScore, 1000);

  const allItems = (allTension as TensionAllItem[] | undefined) ?? [];
  const extremeCount = allItems.filter((i) => i.raw_score >= 80).length;
  const severeCount = allItems.filter((i) => i.raw_score >= 60 && i.raw_score < 80).length;
  const alertCount = allItems.filter((i) => i.raw_score >= 40 && i.raw_score < 60).length;

  const updatedTime = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString(lang === "ko" ? "ko-KR" : "en-US", { hour: "2-digit", minute: "2-digit" })
    : null;

  // 관심국가 텐션 매핑
  const watchlistItems = (watchlistTension as TensionAllItem[] | undefined) ?? [];
  const tensionMap = new Map(watchlistItems.map((t: any) => [t.country_code, t]));

  // Impact Summary 파생
  const impactScore = summary?.score ?? 0;
  const animatedImpact = useCountUp(impactScore, 900);
  const color = impactColor(impactScore);
  const levelKey = `dash_impact_level_${summary?.level || "low"}` as Parameters<typeof t>[1];
  const hasPro = !!(summary?.economy || summary?.trade || summary?.travel);
  const isPro = userPlan === "pro" || userPlan === "pro_plus";

  // Top Issues (클러스터 기반, personalizedKScore 정렬)
  const topItems = useMemo(() => {
    if (!clusterData || !Array.isArray(clusterData)) return [];
    return (clusterData as any[])
      .filter((c) => c.severity > 0 && c.kscore > 0)
      .map((c, i) => ({
        id: i,
        keyword: c.title,
        keyword_ko: c.title_ko,
        kscore: c.kscore,
        topic: c.topic,
        country_codes: c.country_code ? [c.country_code] : [],
        cluster_ids: [c.id],
        event_count: c.event_count,
        severity: c.severity,
        reason: "",
        calculated_at: c.last_event_at,
        first_event_at: c.first_event_at,
        independent_sources: c.independent_sources ?? 1,
      } as TrendingItem))
      .sort((a, b) => personalizedKScore(b, homeCountry) - personalizedKScore(a, homeCountry))
      .slice(0, 5);
  }, [clusterData, homeCountry]);

  if (meLoading || summaryLoading) {
    return <div className="p-4"><DashboardSkeleton /></div>;
  }

  return (
    <div className="flex flex-col" style={{ height: "calc(100dvh - 60px)" }}>
      {/* ──── Header ──── */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 pt-4 pb-3">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-sm font-bold">
              {t(lang, "dash_report_title", { name: nickname })}
            </h1>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {t(lang, "dash_report_subtitle")}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {updatedTime && (
              <span className="flex items-center gap-1 text-[9px] text-muted-foreground/60">
                <Radio className="h-2.5 w-2.5 text-emerald-500 animate-pulse" />
                <span>LIVE</span>
              </span>
            )}
          </div>
        </div>
      </div>

      <NoticeTicker />

      {/* ──── Scrollable Report Body ──── */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-4 py-4 space-y-5">

          {/* ═══════════════ SECTION 1: 종합 영향도 Hero ═══════════════ */}
          <section className="rounded-xl border border-border bg-card p-4 fade-in-up">
            {/* 개인화 라벨 */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                {t(lang, "dash_personalized_for", { name: nickname })}
              </span>
              <span className="text-[9px] text-muted-foreground">
                {t(lang, "dash_monitoring_worldwide")}
              </span>
            </div>

            {/* Big Number + Gauge */}
            <div className="flex items-center gap-4">
              <div className="relative shrink-0">
                {/* 원형 게이지 (SVG) */}
                <svg width="80" height="80" viewBox="0 0 80 80" className="transform -rotate-90">
                  <circle cx="40" cy="40" r="34" fill="none" stroke="hsl(var(--muted) / 0.2)" strokeWidth="6" />
                  <circle
                    cx="40" cy="40" r="34" fill="none"
                    stroke={color} strokeWidth="6"
                    strokeLinecap="round"
                    strokeDasharray={`${(impactScore / 100) * 213.6} 213.6`}
                    className="transition-all duration-1000 ease-out"
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-2xl font-bold tabular-nums leading-none" style={{ color }}>
                    {Math.round(animatedImpact)}
                  </span>
                  <span className="text-[8px] text-muted-foreground mt-0.5">/100</span>
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                    style={{ color, backgroundColor: `${color}15` }}
                  >
                    {t(lang, levelKey)}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {t(lang, "dash_impact_score")}
                  </span>
                </div>
                <p className="text-[11px] text-foreground/80 leading-relaxed line-clamp-3">
                  {summary?.summary || (lang === "ko" ? "분석 데이터를 불러오는 중..." : "Loading analysis...")}
                </p>
              </div>
            </div>

            {/* Stats Row */}
            <div className="grid grid-cols-3 gap-2 mt-4">
              <div className="rounded-lg bg-muted/15 px-3 py-2 text-center">
                <p className="text-lg font-bold tabular-nums">{summary?.total_active_issues ?? 0}</p>
                <p className="text-[9px] text-muted-foreground">{t(lang, "dash_active_issues")}</p>
              </div>
              <div className="rounded-lg bg-muted/15 px-3 py-2 text-center">
                <p className="text-lg font-bold tabular-nums text-red-400">{summary?.critical_issues_count ?? 0}</p>
                <p className="text-[9px] text-muted-foreground">{t(lang, "dash_high_impact")}</p>
              </div>
              <div className="rounded-lg bg-muted/15 px-3 py-2 text-center">
                <p className="text-lg font-bold tabular-nums text-orange-400">{summary?.affected_sectors_count ?? 0}</p>
                <p className="text-[9px] text-muted-foreground">{t(lang, "dash_affected_sectors")}</p>
              </div>
            </div>
          </section>

          {/* ═══════════════ SECTION 2: 홈 국가 + 글로벌 현황 ═══════════════ */}
          <section className="rounded-xl border border-border bg-card p-4 fade-in-up" style={{ animationDelay: "80ms" }}>
            <div className="flex items-center gap-2 mb-3">
              <Shield className="h-3.5 w-3.5 text-muted-foreground" />
              <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                {t(lang, "dash_home_tension")}
              </h2>
            </div>

            {/* Home Country */}
            <div className="flex items-center gap-3 mb-3">
              <span className="text-2xl">{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-semibold block truncate">
                  {homeCountry ? getCountryName(homeCountry, lang) : (lang === "ko" ? "홈 국가 미설정" : "No home country")}
                </span>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={cn("text-[10px] font-bold px-2 py-0.5 rounded-full", tensionColor(homeScore).text)}
                    style={{ backgroundColor: `${homeScore >= 60 ? "#ef4444" : homeScore >= 40 ? "#f97316" : homeScore >= 20 ? "#f59e0b" : "#10b981"}15` }}
                  >
                    {tensionLabel(homeScore, lang)}
                  </span>
                </div>
              </div>
              <div className="text-right">
                <span className={cn("text-2xl font-bold tabular-nums leading-none", tensionColor(homeScore).text)}>
                  {Math.round(animatedHomeScore)}
                </span>
                <span className="text-[10px] text-muted-foreground block">/100</span>
              </div>
            </div>

            {/* Gauge */}
            <div className="h-2 rounded-full bg-muted overflow-hidden mb-3">
              <div
                className={cn("h-full rounded-full transition-all duration-1000 ease-out", tensionColor(homeScore).bar)}
                style={{ width: `${Math.min(homeScore, 100)}%` }}
              />
            </div>

            {/* Global Overview */}
            <div className="flex items-center gap-3 text-[11px] flex-wrap">
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
                  {t(lang, "dash_global_stable")}
                </span>
              )}
            </div>

            {/* Watchlist (인라인 — 별도 섹션 아님) */}
            {myCountries.length > 0 && (
              <div className="mt-4 pt-3 border-t border-border/30">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-wider">
                    {t(lang, "dash_watchlist")}
                  </span>
                  <Link href="/settings?section=countries" className="text-[9px] text-primary hover:underline">
                    {lang === "ko" ? "편집" : "Edit"}
                  </Link>
                </div>
                <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
                  {myCountries.map((code, idx) => {
                    const data = tensionMap.get(code) as TensionAllItem | undefined;
                    const score = data?.raw_score ?? 0;
                    const tc = tensionColor(score);
                    return (
                      <div
                        key={code}
                        onClick={() => router.push(`/tension?country=${code}`)}
                        className="shrink-0 rounded-lg bg-muted/15 px-3 py-2 cursor-pointer hover:bg-muted/25 transition-colors fade-in-up"
                        style={{ animationDelay: `${idx * 40}ms` }}
                      >
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="text-sm">{getFlag(code)}</span>
                          <span className="text-[10px] font-medium">{getCountryName(code, lang)}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={cn("text-sm font-bold tabular-nums", tc.text)}>{score}</span>
                          <span className={cn("h-1.5 w-1.5 rounded-full", tc.dot)} />
                          <span className={cn("text-[9px] font-medium", tc.text)}>
                            {tensionLabel(score, lang)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {myCountries.length === 0 && (
              <div className="mt-4 pt-3 border-t border-border/30">
                <div className="flex items-center gap-2 justify-center py-2">
                  <MapPin className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[11px] text-muted-foreground">{t(lang, "dash_watchlist_empty")}</span>
                  <Link
                    href="/settings?section=countries"
                    className="inline-flex items-center gap-1 rounded-full bg-primary px-2.5 py-1 text-[10px] font-bold text-primary-foreground"
                  >
                    <Plus className="h-2.5 w-2.5" />
                    {t(lang, "dash_watchlist_add")}
                  </Link>
                </div>
              </div>
            )}
          </section>

          {/* ═══════════════ SECTION 3: 나에게 영향이 큰 이슈 ═══════════════ */}
          <section className="fade-in-up" style={{ animationDelay: "160ms" }}>
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-3.5 w-3.5 text-muted-foreground" />
              <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                {t(lang, "dash_top_issues", { name: nickname })}
              </h2>
            </div>
            <p className="text-[10px] text-muted-foreground/70 mb-2 ml-6">
              {t(lang, "dash_top_issues_sub")}
            </p>

            {topItems.length === 0 ? (
              <div className="rounded-xl border border-border bg-card/50 p-5 text-center">
                <Activity className="h-6 w-6 text-muted-foreground mx-auto mb-2" />
                <p className="text-[11px] text-muted-foreground">{t(lang, "dash_no_issues")}</p>
              </div>
            ) : (
              <div className="space-y-2">
                {topItems.map((item, idx) => {
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
                        "flex items-center gap-3 rounded-xl border border-border bg-card p-3 cursor-pointer",
                        "hover:bg-card/80 transition-all border-l-4 fade-in-up",
                        kscoreAccent(pKScore),
                      )}
                      style={{ animationDelay: `${(idx + 4) * 60}ms` }}
                    >
                      <div className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[11px] font-bold",
                        idx === 0 ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"
                      )}>
                        {idx + 1}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          {item.country_codes.length > 0 && (
                            <span className="text-[11px]">
                              {item.country_codes.map((code: string) => getFlag(code)).join(" ")}
                            </span>
                          )}
                          <span className={cn(
                            "inline-flex items-center h-4 rounded-full px-1.5 text-[9px] font-medium leading-none",
                            TOPIC_COLORS[topic]
                          )}>
                            {topicLabel}
                          </span>
                          {(item.independent_sources ?? 0) >= 3 && (
                            <span className="text-[8px] px-1 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium">
                              {lang === "ko" ? "검증됨" : "Verified"}
                            </span>
                          )}
                        </div>
                        <h4 className="text-[12px] font-semibold leading-snug line-clamp-1">{displayTitle}</h4>
                      </div>

                      <div className="shrink-0 text-right">
                        <span className={cn("text-sm font-bold tabular-nums", badge.text)}>
                          {k.toFixed(1)}
                        </span>
                        <p className="text-[9px] text-muted-foreground">{t(lang, "dash_impact_score")}</p>
                      </div>
                      <ChevronRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    </div>
                  );
                })}
              </div>
            )}

            <Link
              href="/feed"
              className="flex items-center justify-center gap-1.5 mt-3 rounded-xl border border-border bg-card/50 py-2.5 text-xs text-muted-foreground hover:text-foreground hover:bg-card/80 transition-colors"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              {t(lang, "dash_view_all_issues")}
            </Link>
          </section>

          {/* ═══════════════ SECTION 4: 상세 영향 분석 (Pro) ═══════════════ */}
          <section className="rounded-xl border border-border bg-card overflow-hidden fade-in-up" style={{ animationDelay: "240ms" }}>
            <div className="p-4">
              <div className="flex items-center gap-2 mb-1">
                <TrendingUp className="h-3.5 w-3.5 text-blue-400" />
                <h2 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
                  {t(lang, "dash_pro_detail", { name: nickname })}
                </h2>
                <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 font-bold">Pro</span>
              </div>
              <p className="text-[10px] text-muted-foreground/70 ml-6 mb-3">
                {t(lang, "dash_impact_brief_desc")}
              </p>

              {hasPro && isPro ? (
                /* Pro: 실제 분석 표시 */
                <div className="space-y-2">
                  {[
                    { key: "economy" as const, icon: Briefcase, label: t(lang, "dash_pro_economy"), color: "text-blue-400", bg: "bg-blue-500/8" },
                    { key: "trade" as const, icon: ShoppingCart, label: t(lang, "dash_pro_trade"), color: "text-orange-400", bg: "bg-orange-500/8" },
                    { key: "travel" as const, icon: Plane, label: t(lang, "dash_pro_travel"), color: "text-emerald-400", bg: "bg-emerald-500/8" },
                  ].map((dim, idx) => {
                    const text = summary?.[dim.key];
                    if (!text) return null;
                    return (
                      <div
                        key={dim.key}
                        className={cn("rounded-lg p-3 fade-in-up", dim.bg)}
                        style={{ animationDelay: `${(idx + 6) * 60}ms` }}
                      >
                        <div className="flex items-center gap-2 mb-1.5">
                          <dim.icon className={cn("h-3.5 w-3.5 shrink-0", dim.color)} />
                          <span className={cn("text-[10px] font-bold", dim.color)}>{dim.label}</span>
                        </div>
                        <p className="text-[11px] text-foreground/70 leading-relaxed">{text}</p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                /* Free/비Pro: 잠금 상태 */
                <div className="relative">
                  {/* 블러 미리보기 */}
                  <div className="space-y-2 opacity-40 blur-[2px] select-none pointer-events-none">
                    {[
                      { icon: Briefcase, color: "text-blue-400", bg: "bg-blue-500/8", label: t(lang, "dash_pro_economy") },
                      { icon: ShoppingCart, color: "text-orange-400", bg: "bg-orange-500/8", label: t(lang, "dash_pro_trade") },
                      { icon: Plane, color: "text-emerald-400", bg: "bg-emerald-500/8", label: t(lang, "dash_pro_travel") },
                    ].map((dim) => (
                      <div key={dim.label} className={cn("rounded-lg p-3", dim.bg)}>
                        <div className="flex items-center gap-2 mb-1.5">
                          <dim.icon className={cn("h-3.5 w-3.5", dim.color)} />
                          <span className={cn("text-[10px] font-bold", dim.color)}>{dim.label}</span>
                        </div>
                        <div className="h-3 rounded bg-muted/30 w-3/4" />
                        <div className="h-3 rounded bg-muted/30 w-1/2 mt-1" />
                      </div>
                    ))}
                  </div>
                  {/* 잠금 오버레이 */}
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

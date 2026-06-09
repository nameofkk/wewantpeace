"use client";

import { Suspense } from "react";
import Link from "next/link";
import {
  FileText,
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  AlertTriangle,
  Globe2,
  Lock,
  Download,
  ChevronRight,
  Loader2,
  RefreshCw,
  ArrowLeft,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useMe, useWeeklyReport, useWeeklyPdf } from "@/lib/api";
import { cn } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { TOPIC_COLORS } from "@/lib/kscore-utils";
import { TOPIC_LABELS, TOPIC_LABELS_EN } from "@/lib/utils";
import { getKScoreBadge } from "@/lib/kscore-utils";

export default function WeeklyReportPage() {
  return (
    <Suspense fallback={<WeeklyReportSkeleton />}>
      <WeeklyReportContent />
    </Suspense>
  );
}

function WeeklyReportSkeleton() {
  return (
    <div className="min-h-screen bg-background p-4 space-y-4 animate-pulse">
      <div className="h-6 w-40 bg-muted rounded" />
      <div className="h-16 bg-card rounded-xl border border-border" />
      <div className="h-24 bg-card rounded-xl border border-border" />
      <div className="space-y-2">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-16 bg-card rounded-xl border border-border" />
        ))}
      </div>
    </div>
  );
}

function WeeklyReportContent() {
  const lang = (useAppStore((s) => s.lang) || "ko") as Lang;
  const { data: me, isLoading: meLoading } = useMe();
  const isPro = me?.plan === "pro" || me?.plan === "pro_plus";
  const isProPlus = me?.plan === "pro_plus";

  const { data, isLoading, isError, refetch } = useWeeklyReport(isProPlus);
  const { data: pdfData } = useWeeklyPdf(isProPlus);

  if (meLoading) return <WeeklyReportSkeleton />;

  if (!me) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center space-y-4">
          <Lock className="h-10 w-10 text-muted-foreground mx-auto" />
          <p className="text-muted-foreground text-sm">
            {lang === "ko" ? "로그인이 필요합니다" : "Login required"}
          </p>
          <Link
            href="/login?returnUrl=/reports/weekly"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-primary text-primary-foreground text-sm font-semibold"
          >
            {lang === "ko" ? "로그인" : "Log in"}
          </Link>
        </div>
      </div>
    );
  }

  if (!isProPlus) {
    return <ProPlusPaywall lang={lang} isPro={isPro} />;
  }

  if (isLoading) return <WeeklyReportSkeleton />;

  if (isError || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="text-center space-y-4">
          <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto" />
          <p className="text-muted-foreground text-sm">
            {lang === "ko" ? "리포트를 불러올 수 없습니다" : "Could not load report"}
          </p>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-border text-sm font-medium hover:bg-card transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            {lang === "ko" ? "다시 시도" : "Retry"}
          </button>
        </div>
      </div>
    );
  }

  const weekStart = new Date(data.week_start);
  const weekEnd = new Date(data.week_end);
  const formatDate = (d: Date) =>
    lang === "ko"
      ? `${d.getMonth() + 1}월 ${d.getDate()}일`
      : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });

  const periodLabel = `${formatDate(weekStart)} – ${formatDate(weekEnd)}`;
  const tension = data.tension_summary;
  const trendUp = tension.delta > 0;
  const trendDown = tension.delta < 0;

  return (
    <div className="min-h-screen bg-background pb-20">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/50">
        <div className="flex items-center gap-3 px-4 h-12">
          <Link href="/" className="p-1 -ml-1 rounded-lg hover:bg-card transition-colors">
            <ArrowLeft className="h-4 w-4 text-muted-foreground" />
          </Link>
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <FileText className="h-4 w-4 text-cyan-400 shrink-0" />
            <span className="font-semibold text-sm truncate">
              {t(lang, "weekly_report_title")}
            </span>
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 text-white shrink-0">
              Pro+
            </span>
          </div>
          {pdfData?.available && pdfData.url && (
            <a
              href={pdfData.url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-lg hover:bg-card transition-colors text-muted-foreground hover:text-foreground"
              title={lang === "ko" ? "PDF 다운로드" : "Download PDF"}
            >
              <Download className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>

      <div className="px-4 pt-4 space-y-4 max-w-lg mx-auto">
        {/* Period + highlight */}
        <div className="rounded-xl bg-card border border-border/70 px-4 py-3 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-muted-foreground font-medium">
              {lang === "ko" ? "분석 기간" : "Period"}
            </span>
            <span className="text-[10px] text-muted-foreground tabular-nums">
              {periodLabel}
            </span>
          </div>
          <p className="text-sm font-medium leading-relaxed text-foreground/90">
            {data.highlight}
          </p>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-card border border-border/70 px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center shrink-0">
              <Activity className="h-4 w-4 text-blue-400" />
            </div>
            <div>
              <p className="text-lg font-bold tabular-nums">
                {data.total_events.toLocaleString()}
              </p>
              <p className="text-[10px] text-muted-foreground">
                {t(lang, "weekly_report_total_events")}
              </p>
            </div>
          </div>

          <div className="rounded-xl bg-card border border-border/70 px-4 py-3 flex items-center gap-3">
            <div
              className={cn(
                "w-8 h-8 rounded-lg flex items-center justify-center shrink-0",
                trendUp ? "bg-red-500/10" : trendDown ? "bg-blue-500/10" : "bg-emerald-500/10",
              )}
            >
              {trendUp ? (
                <TrendingUp className="h-4 w-4 text-red-400" />
              ) : trendDown ? (
                <TrendingDown className="h-4 w-4 text-blue-400" />
              ) : (
                <Minus className="h-4 w-4 text-emerald-400" />
              )}
            </div>
            <div>
              <p className={cn(
                "text-lg font-bold tabular-nums",
                trendUp ? "text-red-500 dark:text-red-400" : trendDown ? "text-blue-500 dark:text-blue-400" : "text-emerald-500 dark:text-emerald-400",
              )}>
                {tension.current}
                <span className="text-xs font-normal text-muted-foreground ml-0.5">/100</span>
              </p>
              <p className="text-[10px] text-muted-foreground">
                {lang === "ko" ? "긴장도" : "Tension"}
                {tension.delta !== 0 && (
                  <span className={cn(
                    "ml-1 tabular-nums",
                    trendUp ? "text-red-500" : "text-blue-500",
                  )}>
                    {trendUp ? "+" : ""}{tension.delta}
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Top issues */}
        <div className="space-y-2">
          <div className="flex items-center gap-2 px-1">
            <Globe2 className="h-3.5 w-3.5 text-cyan-400" />
            <span className="text-xs font-semibold text-foreground/80">
              {t(lang, "weekly_report_top_issues")}
            </span>
            <span className="text-[10px] text-muted-foreground ml-auto">
              {data.top_issues.length}{lang === "ko" ? "건" : " issues"}
            </span>
          </div>

          {data.top_issues.length === 0 ? (
            <div className="rounded-xl bg-card border border-border/70 px-4 py-6 text-center">
              <Globe2 className="h-8 w-8 text-muted-foreground/40 mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                {lang === "ko" ? "이번 주 주요 이슈가 없습니다" : "No major issues this week"}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {data.top_issues.map((issue, idx) => (
                <IssueRow key={issue.cluster_id} issue={issue} rank={idx + 1} lang={lang} />
              ))}
            </div>
          )}
        </div>

        {/* Generated at */}
        <p className="text-center text-[10px] text-muted-foreground/60 pb-4">
          {lang === "ko" ? "생성 시각" : "Generated"}{" "}
          {new Date(data.generated_at).toLocaleString(lang === "ko" ? "ko-KR" : "en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </div>
  );
}

interface IssueRowProps {
  issue: {
    cluster_id: string;
    title: string;
    kscore: number;
    impact_score: number;
    country_codes: string[];
    topic: string;
  };
  rank: number;
  lang: Lang;
}

function IssueRow({ issue, rank, lang }: IssueRowProps) {
  const badge = getKScoreBadge(issue.kscore, lang);
  const topicColor = TOPIC_COLORS[issue.topic] || TOPIC_COLORS.unknown;
  const topicLabel =
    lang === "ko"
      ? TOPIC_LABELS[issue.topic] || issue.topic
      : TOPIC_LABELS_EN[issue.topic] || issue.topic;

  const primaryCountry = issue.country_codes[0] || "";
  const flag = primaryCountry ? getFlag(primaryCountry) : "🌐";
  const countryName = primaryCountry
    ? getCountryName(primaryCountry, lang)
    : lang === "ko"
    ? "글로벌"
    : "Global";

  const impactPct = Math.min(100, Math.max(0, issue.impact_score));
  const impactColor =
    impactPct >= 75
      ? "bg-red-500"
      : impactPct >= 50
      ? "bg-orange-500"
      : impactPct >= 25
      ? "bg-amber-500"
      : "bg-emerald-500";

  return (
    <Link
      href={`/issues/${issue.cluster_id}`}
      className="flex items-start gap-3 rounded-xl bg-card border border-border/70 px-3 py-3 hover:bg-card/80 active:scale-[0.99] transition-all group"
    >
      {/* Rank */}
      <span className="text-[10px] font-bold text-muted-foreground/50 w-4 pt-0.5 shrink-0 tabular-nums text-right">
        {rank}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-1.5">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-semibold leading-tight line-clamp-2 flex-1">
            {issue.title}
          </p>
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 shrink-0 mt-0.5 group-hover:text-muted-foreground transition-colors" />
        </div>

        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Country */}
          <span className="text-[10px] text-muted-foreground">
            {flag} {countryName}
          </span>
          <span className="text-muted-foreground/30">·</span>
          {/* Topic */}
          <span className={cn("text-[9px] font-medium px-1.5 py-0.5 rounded-full", topicColor)}>
            {topicLabel}
          </span>
          <span className="text-muted-foreground/30">·</span>
          {/* KScore */}
          <span className={cn("text-[9px] font-bold px-1.5 py-0.5 rounded-full", badge.bg, badge.text)}>
            K{issue.kscore.toFixed(1)}
          </span>
        </div>

        {/* Impact bar */}
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1 rounded-full bg-muted/40">
            <div
              className={cn("h-full rounded-full transition-all", impactColor)}
              style={{ width: `${impactPct}%` }}
            />
          </div>
          <span className="text-[9px] text-muted-foreground tabular-nums shrink-0">
            {impactPct}
          </span>
        </div>
      </div>
    </Link>
  );
}

interface PaywallProps {
  lang: Lang;
  isPro: boolean;
}

function ProPlusPaywall({ lang, isPro }: PaywallProps) {
  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <div className="sticky top-0 z-20 bg-background/95 backdrop-blur border-b border-border/50">
        <div className="flex items-center gap-3 px-4 h-12">
          <Link href="/" className="p-1 -ml-1 rounded-lg hover:bg-card transition-colors">
            <ArrowLeft className="h-4 w-4 text-muted-foreground" />
          </Link>
          <div className="flex items-center gap-2">
            <FileText className="h-4 w-4 text-cyan-400" />
            <span className="font-semibold text-sm">
              {t(lang, "weekly_report_title")}
            </span>
          </div>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-sm text-center space-y-6">
          {/* Lock icon */}
          <div className="relative mx-auto w-20 h-20">
            <div
              className="absolute inset-0 rounded-full opacity-20 blur-xl"
              style={{ background: "linear-gradient(135deg, #a855f7, #ec4899)" }}
            />
            <div
              className="relative w-20 h-20 rounded-full flex items-center justify-center"
              style={{ background: "linear-gradient(135deg, rgba(168,85,247,0.15), rgba(236,72,153,0.15))" }}
            >
              <Lock className="h-8 w-8 text-purple-400" />
            </div>
          </div>

          <div className="space-y-2">
            <h1 className="text-xl font-bold">
              {lang === "ko" ? "Pro+ 전용 기능입니다" : "Pro+ Feature"}
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {lang === "ko"
                ? "주간 리포트는 Pro+ 플랜에서 이용할 수 있어요. 지난 7일간 핵심 이슈와 긴장도 변화를 한눈에 확인하세요."
                : "The weekly report is available on the Pro+ plan. Get a clear view of key issues and tension changes over the past 7 days."}
            </p>
          </div>

          {/* Features */}
          <div className="space-y-2 text-left">
            {[
              lang === "ko" ? "Top 10 개인화 이슈 분석" : "Top 10 personalized issue analysis",
              lang === "ko" ? "긴장도 주간 변화 요약" : "Weekly tension change summary",
              lang === "ko" ? "영향도 기반 이슈 순위" : "Impact-scored issue ranking",
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-card border border-border/50">
                <div className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span className="text-sm font-medium">{item}</span>
              </div>
            ))}
          </div>

          <Link
            href={`/upgrade?source=weekly_report${isPro ? "&from=pro" : ""}`}
            className="flex items-center justify-center gap-2 w-full py-3.5 rounded-xl text-white font-semibold text-sm transition-transform active:scale-[0.98]"
            style={{ background: "linear-gradient(135deg, #a855f7, #ec4899)" }}
          >
            {lang === "ko" ? "Pro+로 업그레이드" : "Upgrade to Pro+"}
            <ChevronRight className="h-4 w-4" />
          </Link>

          <Link href="/" className="block text-xs text-muted-foreground hover:text-foreground transition-colors">
            {lang === "ko" ? "나중에 하기" : "Maybe later"}
          </Link>
        </div>
      </div>
    </div>
  );
}

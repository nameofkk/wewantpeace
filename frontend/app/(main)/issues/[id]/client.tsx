"use client";

import { useState } from "react";
import { ArrowLeft, CheckCircle, Clock, AlertTriangle, Loader2, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { useClusterDetail, useKScoreHistory, type KScoreHistoryPoint } from "@/lib/api";
import { SourceBadge } from "@/components/issue/SourceBadge";
import { KScoreBar } from "@/components/issue/KScoreBar";
import { ShareButton } from "@/components/issue/ShareButton";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { getCountryName } from "@/lib/countries";

function isNew(isoString: string): boolean {
  return Date.now() - new Date(isoString).getTime() < 2 * 60 * 60 * 1000;
}

function formatDateTime(isoString: string, lang: Lang): string {
  const locale = lang === "en" ? "en-US" : "ko-KR";
  return new Date(isoString).toLocaleString(locale, {
    month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

interface EventOut {
  id: string;
  title: string;
  title_ko?: string | null;
  body: string;
  topic: string;
  severity: number;
  confidence: number;
  source_tier: string | null;
  source_name: string | null;
  source_url: string | null;
  event_time: string;
  country_code: string | null;
  entity_anchor: string | null;
}

interface ClusterDetail {
  id: string;
  cluster_key: string;
  topic: string;
  title: string;
  title_ko?: string | null;
  lat: number | null;
  lon: number | null;
  country_code: string | null;
  severity: number;
  confidence: number;
  event_count: number;
  is_spike: boolean;
  is_verified: boolean;
  kscore: number;
  first_event_at: string;
  last_event_at: string;
  events: EventOut[];
}

interface Props {
  initialData?: ClusterDetail;
}

function KScoreHistorySection({ clusterId, lang }: { clusterId: string; lang: Lang }) {
  const { data, isPending } = useKScoreHistory(clusterId, 7);

  if (isPending) {
    return (
      <div className="mt-4 pt-4 border-t border-border">
        <div className="h-32 flex items-center justify-center">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  return <KScoreHistoryChart data={data ?? []} lang={lang} />;
}

function KScoreHistoryChart({ data, lang }: { data: KScoreHistoryPoint[]; lang: Lang }) {
  if (data.length < 2) {
    return (
      <div className="h-32 flex items-center justify-center text-xs text-muted-foreground">
        {lang === "ko" ? "히스토리 데이터가 부족합니다" : "Not enough history data"}
      </div>
    );
  }

  const maxKscore = Math.max(...data.map((d) => d.kscore), 1);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div className="mt-4 pt-4 border-t border-border fade-in-up">
      <p className="text-xs font-medium text-muted-foreground mb-3">{t(lang, "issue_kscore_history_section")}</p>
      <div className="relative h-32">
        <svg viewBox={`0 0 ${data.length - 1} 100`} className="w-full h-full" preserveAspectRatio="none">
          <defs>
            <linearGradient id="kscoreGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.3" />
              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <path
            d={`M0,${100 - (data[0].kscore / maxKscore) * 90} ${data.map((d, i) => `L${i},${100 - (d.kscore / maxKscore) * 90}`).join(" ")} L${data.length - 1},100 L0,100 Z`}
            fill="url(#kscoreGrad)"
            className="kscore-area"
          />
          <polyline
            points={data.map((d, i) => `${i},${100 - (d.kscore / maxKscore) * 90}`).join(" ")}
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth="1.5"
            vectorEffect="non-scaling-stroke"
            pathLength={1}
            className="kscore-line"
          />
        </svg>
        <div className="absolute bottom-0 left-0 right-0 flex justify-between px-1 kscore-label">
          <span className="text-[9px] text-muted-foreground">
            {new Date(data[0].time).toLocaleDateString(locale, { month: "short", day: "numeric" })}
          </span>
          <span className="text-[9px] text-muted-foreground">
            {new Date(data[data.length - 1].time).toLocaleDateString(locale, { month: "short", day: "numeric" })}
          </span>
        </div>
        <div className="absolute top-0 right-1 kscore-label">
          <span className="text-[9px] text-muted-foreground">max {maxKscore.toFixed(1)}</span>
        </div>
      </div>
    </div>
  );
}

export default function IssueDetailClient({ initialData }: Props) {
  const id = initialData?.id ?? "";
  const router = useRouter();
  const { data, isPending, isError } = useClusterDetail(id);
  const issue = (data as ClusterDetail | undefined) ?? initialData;
  const lang = useAppStore((s) => s.lang);
  const [showHistory, setShowHistory] = useState(false);

  if (!initialData && isPending) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!issue) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-3">
        <AlertTriangle className="h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">{t(lang, "issue_not_found")}</p>
        <Link href="/map" className="text-xs text-primary hover:underline">{t(lang, "issue_back_map")}</Link>
      </div>
    );
  }

  const rawIssueTitle = lang === "en" ? issue.title : (issue.title_ko ?? issue.title);
  const issueTopicKey = `topic_${issue.topic}` as Parameters<typeof t>[1];
  const displayTitle = isJunkTitle(rawIssueTitle)
    ? buildSmartTitle(issue.title, issue.topic, lang, getCountryName, issue.country_code)
    : (stripTitlePrefix(rawIssueTitle) || t(lang, issueTopicKey));

  const statusLabel = issue.confidence >= 0.70
    ? t(lang, "issue_status_confirmed")
    : issue.confidence >= 0.35
    ? t(lang, "issue_status_partial")
    : t(lang, "issue_status_unverified");
  const statusColor = issue.confidence >= 0.70
    ? "text-green-400 bg-green-400/10"
    : issue.confidence >= 0.35
    ? "text-yellow-400 bg-yellow-400/10"
    : "text-red-400 bg-red-400/10";

  const topicKey = `topic_${issue.topic}` as Parameters<typeof t>[1];
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div className="flex flex-col min-h-screen">
      {/* 헤더 */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => window.history.length > 1 ? router.back() : router.push("/")} className="rounded-lg p-1.5 hover:bg-secondary transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-sm font-bold flex-1 truncate">{displayTitle}</h1>
          <ShareButton issueId={issue.id} title={displayTitle} />
        </div>
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* 요약 카드 */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 flex-wrap mb-3">
            {issue.is_spike && (
              <span className="flex items-center gap-1 rounded-full bg-red-500/20 px-2 py-0.5 text-[10px] font-bold text-red-400">
                <AlertTriangle className="h-2.5 w-2.5" />
                {t(lang, "issue_spike")}
              </span>
            )}
            <span className={cn("flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium", statusColor)}>
              {issue.is_verified && <CheckCircle className="h-2.5 w-2.5" />}
              {statusLabel}
            </span>
            <span className="text-[10px] text-muted-foreground">
              {t(lang, topicKey)}
              {issue.country_code && ` · ${issue.country_code}`}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center mb-4">
            <div className="rounded-lg bg-secondary p-2">
              <p className="text-lg font-bold">{issue.severity}</p>
              <p className="text-[10px] text-muted-foreground">{t(lang, "issue_stat_severity")}</p>
            </div>
            <div className="rounded-lg bg-secondary p-2">
              <p className="text-lg font-bold">{Math.round(issue.confidence * 100)}%</p>
              <p className="text-[10px] text-muted-foreground">{t(lang, "issue_stat_confidence")}</p>
            </div>
            <div className="rounded-lg bg-secondary p-2">
              <p className="text-lg font-bold">{issue.event_count}</p>
              <p className="text-[10px] text-muted-foreground">{t(lang, "issue_stat_events")}</p>
            </div>
          </div>

          <div>
            <KScoreBar kscore={issue.kscore} />
          </div>

          <div className="flex items-center justify-between mt-3 text-[10px] text-muted-foreground">
            <span>{t(lang, "issue_first_report")} {new Date(issue.first_event_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
            <span>{t(lang, "issue_last_report")} {new Date(issue.last_event_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
          </div>

          {/* 공유하기 + 히스토리 버튼 */}
          <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border">
            <ShareButton issueId={issue.id} title={displayTitle} />
            <button
              onClick={() => setShowHistory((v) => !v)}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors py-1"
            >
              {showHistory ? (
                <><ChevronUp className="h-3 w-3" /> {t(lang, "issue_kscore_history_collapse")}</>
              ) : (
                <><ChevronDown className="h-3 w-3" /> {t(lang, "issue_kscore_history_expand")}</>
              )}
            </button>
          </div>

          {showHistory && <KScoreHistorySection clusterId={issue.id} lang={lang} />}
        </div>

        {/* 타임라인 */}
        {issue.events.length === 0 ? (
          <div className="text-center py-8 text-sm text-muted-foreground">
            {t(lang, "issue_no_events")}
          </div>
        ) : (
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              {t(lang, "issue_timeline", { n: issue.event_count })}
              {issue.events.length < issue.event_count && (
                <span className="ml-1 normal-case text-[10px] font-normal text-muted-foreground/60">
                  {t(lang, "issue_timeline_showing", { n: issue.events.length })}
                </span>
              )}
            </h2>
            <div className="space-y-3">
              {[...issue.events]
                .sort((a, b) => b.severity - a.severity)
                .map((event, idx, arr) => {
                const tier = event.source_tier ?? "C";
                const eventNew = isNew(event.event_time);
                const eventTopicKey = `topic_${event.topic}` as Parameters<typeof t>[1];
                const rawEventTitle = lang === "en" ? event.title : (event.title_ko ?? event.title);
                const eventTitle = isJunkTitle(rawEventTitle)
                  ? buildSmartTitle(event.title, event.topic, lang, getCountryName, event.country_code)
                  : (stripTitlePrefix(rawEventTitle) || t(lang, eventTopicKey));
                return (
                  <div key={event.id} className="flex gap-3">
                    <div className="flex flex-col items-center w-7 shrink-0">
                      <SourceBadge tier={tier} className="shrink-0" showDesc />
                      {idx < arr.length - 1 && (
                        <div className="flex-1 w-px bg-border mt-1" />
                      )}
                    </div>

                    <div className="flex-1 rounded-lg border border-border bg-secondary/30 p-3 mb-1">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center gap-1.5 flex-1 min-w-0">
                          {eventNew && (
                            <span className="shrink-0 rounded-full bg-blue-500/20 px-1.5 py-0.5 text-[9px] font-bold text-blue-400 leading-none">
                              NEW
                            </span>
                          )}
                          <p className="text-xs font-medium">{eventTitle}</p>
                        </div>
                        <span className="shrink-0 text-[10px] text-muted-foreground">
                          {t(lang, eventTopicKey)}
                        </span>
                      </div>

                      <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                        <Clock className="h-2.5 w-2.5 text-muted-foreground shrink-0" />
                        <span className="text-[10px] text-muted-foreground">
                          {formatDateTime(event.event_time, lang)}
                        </span>
                        <span className="text-[10px] text-muted-foreground/60">·</span>
                        <span className={cn(
                          "text-[10px] font-medium px-1.5 py-0.5 rounded-full",
                          event.severity >= 80 ? "bg-red-900/25 text-red-800 dark:text-red-100" :
                          event.severity >= 60 ? "bg-red-500/20 text-red-600 dark:text-red-400" :
                          event.severity >= 40 ? "bg-orange-500/20 text-orange-600 dark:text-orange-300" :
                          event.severity >= 20 ? "bg-amber-500/20 text-amber-600 dark:text-amber-300" :
                          "bg-green-600/20 text-green-700 dark:text-green-400"
                        )}>
                          {t(lang, "issue_severity_badge", { n: event.severity })}
                        </span>
                        <span className="text-[10px] text-muted-foreground/60">·</span>
                        <span className="text-[10px] text-muted-foreground">
                          {t(lang, "issue_confidence_badge", { n: Math.round(event.confidence * 100) })}
                        </span>
                        {event.source_url && (
                          <a
                            href={event.source_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="ml-auto flex items-center gap-0.5 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 transition-colors"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <ExternalLink className="h-2.5 w-2.5" />
                            {event.source_name ?? t(lang, "issue_source_fallback")}
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

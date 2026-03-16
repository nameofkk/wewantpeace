"use client";

import React, { useState } from "react";
import { ArrowLeft, CheckCircle, Clock, AlertTriangle, Loader2, ExternalLink, ChevronDown, ChevronUp, Shield, FileText, Flame, Globe, Radio, Activity, Lock } from "lucide-react";
import {
  LineChart as RCLineChart,
  Line as RCLine,
  XAxis as RCXAxis,
  YAxis as RCYAxis,
  CartesianGrid as RCCartesianGrid,
  Tooltip as RCTooltip,
  ResponsiveContainer as RCContainer,
} from "recharts";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cn, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { useClusterDetail, useKScoreHistory, useTrackBehavior, useClusterSignals, useClusterContext, useMe, type KScoreHistoryPoint, type ClusterSignalMatch, type HistoricalContext } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ImpactBriefCard } from "@/components/dashboard/ImpactBriefCard";
import { SectorImpactCard } from "@/components/dashboard/SectorImpactCard";
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
  body_ko?: string | null;
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

interface ChangeLog {
  field: string;
  old_value?: string | null;
  new_value?: string | null;
  reason: string;
  updated_by: string;
  created_at: string;
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
  is_verified: boolean;
  kscore: number;
  independent_sources?: number;
  source_tiers?: string[];
  first_event_at: string;
  last_event_at: string;
  events: EventOut[];
  change_logs?: ChangeLog[];
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

function KScoreTooltip({ active, payload, lang }: { active?: boolean; payload?: { payload: KScoreHistoryPoint }[]; lang: Lang }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const locale = lang === "en" ? "en-US" : "ko-KR";
  const scoreColor = d.kscore >= 7 ? "#ef4444" : d.kscore >= 4 ? "#f59e0b" : "#10b981";
  return (
    <div className="rounded-lg border border-border bg-card/95 backdrop-blur-sm px-3 py-2 text-xs shadow-lg">
      <p className="text-muted-foreground mb-1">
        {new Date(d.time).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
      </p>
      <p className="font-bold" style={{ color: scoreColor }}>
        KScore <span className="font-normal text-foreground">{d.kscore.toFixed(1)}</span>
      </p>
    </div>
  );
}

function KScoreHistoryChart({ data, lang }: { data: KScoreHistoryPoint[]; lang: Lang }) {
  if (data.length < 2) {
    return (
      <div className="h-32 flex items-center justify-center text-xs text-muted-foreground">
        {lang === "ko" ? "히스토리 데이터가 부족합니다" : "Not enough history data"}
      </div>
    );
  }

  const locale = lang === "en" ? "en-US" : "ko-KR";
  const maxKscore = Math.max(...data.map((d) => d.kscore), 1);
  const lineColor = maxKscore >= 7 ? "#ef4444" : maxKscore >= 4 ? "#f59e0b" : "#10b981";

  return (
    <div className="mt-4 pt-4 border-t border-border fade-in-up">
      <p className="text-xs font-medium text-muted-foreground mb-3">{t(lang, "issue_kscore_history_section")}</p>
      <div className="h-36">
        <RCContainer width="100%" height="100%">
          <RCLineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
            <RCCartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
            <RCXAxis
              dataKey="time"
              tickFormatter={(v: string) => new Date(v).toLocaleDateString(locale, { month: "numeric", day: "numeric" })}
              tick={{ fontSize: 9, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <RCYAxis
              domain={[0, Math.ceil(maxKscore + 1)]}
              tick={{ fontSize: 9, fill: "#6b7280" }}
              axisLine={false}
              tickLine={false}
            />
            <RCTooltip content={<KScoreTooltip lang={lang} />} />
            <RCLine
              type="monotone"
              dataKey="kscore"
              stroke={lineColor}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: lineColor }}
              animationDuration={400}
            />
          </RCLineChart>
        </RCContainer>
      </div>
    </div>
  );
}

// ── 교차검증 데모 데이터 (Free 유저용) ──
const DEMO_CROSS_MATCHES = [
  { signal_type: "firms_hotspot", count: 3, avg_distance_km: 12, avg_time_gap: "2h" },
  { signal_type: "ioda_outage", count: 1, avg_distance_km: 0, avg_time_gap: "4h" },
];

// ── 교차검증 증거 섹션 ──
function CrossValidationSection({ clusterId, lang }: { clusterId: string; lang: Lang }) {
  const { data: signals, isPending } = useClusterSignals(clusterId);
  const { data: me, isLoading: meLoading } = useMe();
  const { loading: authLoading } = useAuth();
  const userPlan = useAppStore((s) => s.userPlan);
  const plan = (me as { plan?: string })?.plan ?? userPlan ?? "free";
  const isPro = !meLoading && !authLoading && (plan === "pro" || plan === "pro_plus");

  const ICONS: Record<string, React.ReactNode> = {
    firms_hotspot: <Flame className="h-3.5 w-3.5 text-orange-400" />,
    ioda_outage: <Globe className="h-3.5 w-3.5 text-indigo-400" />,
    cf_anomaly: <Activity className="h-3.5 w-3.5 text-purple-400" />,
    gps_jam: <Radio className="h-3.5 w-3.5 text-cyan-400" />,
  };

  if (isPending) {
    return (
      <div className="rounded-xl border border-indigo-500/20 bg-card p-4">
        <div className="h-16 flex items-center justify-center">
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  // Pro 유저: 실제 데이터 표시 (기존 로직)
  if (isPro && signals && signals.length > 0) {
    const grouped: Record<string, ClusterSignalMatch[]> = {};
    for (const s of signals) {
      (grouped[s.signal_type] ??= []).push(s);
    }

    return (
      <div className="rounded-xl border border-indigo-500/20 bg-card p-4 fade-in-up">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="h-3.5 w-3.5 text-indigo-400" />
          <h3 className="text-xs font-semibold text-indigo-400">{t(lang, "cross_validation_title")}</h3>
        </div>
        <div className="space-y-2">
          {Object.entries(grouped).map(([type, items]) => {
            const avgDist = items.reduce((s, i) => s + (i.distance_km ?? 0), 0) / items.length;
            const avgDelta = items.reduce((s, i) => s + (i.time_delta_h ?? 0), 0) / items.length;
            const timeLabel = avgDelta < 1 ? `${Math.round(avgDelta * 60)}m` : `${avgDelta.toFixed(1)}h`;
            return (
              <div key={type} className="flex items-start gap-2 text-[11px]">
                {ICONS[type] ?? <Activity className="h-3.5 w-3.5 text-muted-foreground" />}
                <div>
                  {type === "firms_hotspot" && (
                    <span>{t(lang, "cross_validation_firms_match", { count: items.length, distance: Math.round(avgDist), time: timeLabel })}</span>
                  )}
                  {type === "ioda_outage" && (
                    <span>{t(lang, "cross_validation_outage_match", { country: items[0]?.country_code ?? "?", impact: Math.round(items[0].intensity * 100) })}</span>
                  )}
                  {type === "cf_anomaly" && (
                    <span>{t(lang, "cross_validation_cf_match", { country: items[0]?.country_code ?? "?" })}</span>
                  )}
                  {type === "gps_jam" && (
                    <span>{t(lang, "cross_validation_gps_match", { region: items[0]?.country_code ?? "?" })}</span>
                  )}
                  {items.length > 1 && type !== "firms_hotspot" && (
                    <span className="text-muted-foreground ml-1">({items.length}건)</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 pt-2 border-t border-border/50 text-[10px] text-indigo-300/70">
          {t(lang, "cross_validation_boost", { boost: Math.min(15, Object.keys(grouped).length * 5) })}
        </div>
      </div>
    );
  }

  // Free 유저: 데모 데이터 + blur 오버레이 (다른 화면과 동일 패턴)
  if (!isPro) {
    return (
      <div className="rounded-xl border border-indigo-500/20 bg-card p-4 fade-in-up relative overflow-hidden">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="h-3.5 w-3.5 text-indigo-400" />
          <h3 className="text-xs font-semibold text-indigo-400">{t(lang, "cross_validation_title")}</h3>
        </div>
        <div className="relative">
          <div className="opacity-60 pointer-events-none select-none" style={{ filter: "blur(3px)" }}>
            <div className="space-y-2">
              {DEMO_CROSS_MATCHES.map((demo) => (
                <div key={demo.signal_type} className="flex items-start gap-2 text-[11px]">
                  {ICONS[demo.signal_type] ?? <Activity className="h-3.5 w-3.5 text-muted-foreground" />}
                  <div>
                    {demo.signal_type === "firms_hotspot" && (
                      <span>{t(lang, "cross_validation_firms_match", { count: demo.count, distance: demo.avg_distance_km, time: demo.avg_time_gap })}</span>
                    )}
                    {demo.signal_type === "ioda_outage" && (
                      <span>{t(lang, "cross_validation_outage_match", { country: "UA", impact: 75 })}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-2 border-t border-border/50 text-[10px] text-indigo-300/70">
              {t(lang, "cross_validation_boost", { boost: 10 })}
            </div>
          </div>
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/30 rounded-lg">
            <Lock className="h-5 w-5 text-muted-foreground mb-2" />
            <p className="text-xs text-muted-foreground mb-2 font-medium">
              {lang === "ko"
                ? "Pro 플랜에서 이용 가능합니다"
                : "Available for Pro plan"}
            </p>
            <a
              href="/upgrade?source=demo_cross"
              className="inline-flex rounded-full px-3 py-1.5 text-[10px] font-bold text-white no-underline"
              style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
            >
              {t(lang, "dash_unlock_pro")}
            </a>
          </div>
        </div>
      </div>
    );
  }

  // Pro 유저이지만 시그널 데이터 없음
  return (
    <div className="rounded-xl border border-indigo-500/20 bg-card p-4 fade-in-up">
      <div className="flex items-center gap-2 mb-3">
        <Shield className="h-3.5 w-3.5 text-indigo-400" />
        <h3 className="text-xs font-semibold text-indigo-400">{t(lang, "cross_validation_title")}</h3>
      </div>
      <p className="text-[11px] text-muted-foreground">{t(lang, "cross_validation_none")}</p>
    </div>
  );
}

// ── 역사적 맥락 섹션 ──
function HistoricalContextSection({ clusterId, lang }: { clusterId: string; lang: Lang }) {
  const { data: ctx, isPending } = useClusterContext(clusterId);

  if (isPending || !ctx || ctx.total_events === 0) return null;

  const locale = lang === "en" ? "en-US" : "ko-KR";
  const startYear = ctx.period_start ? new Date(ctx.period_start).getFullYear() : "?";
  const endYear = ctx.period_end ? new Date(ctx.period_end).getFullYear() : "?";

  return (
    <div className="rounded-xl border border-emerald-500/20 bg-card p-4 fade-in-up">
      <div className="flex items-center gap-2 mb-3">
        <FileText className="h-3.5 w-3.5 text-emerald-400" />
        <h3 className="text-xs font-semibold text-emerald-400">{t(lang, "historical_context_title")}</h3>
      </div>
      <div className="space-y-1.5 text-[11px] text-muted-foreground">
        <p>{t(lang, "historical_context_events")}</p>
        <p className="text-foreground">
          {t(lang, "historical_context_recorded", { start: startYear, end: endYear, count: ctx.total_events })}
        </p>
        {ctx.top_actors.length > 0 && (
          <p>{t(lang, "historical_context_actors", { actors: ctx.top_actors.join(", ") })}</p>
        )}
        {ctx.recent_fatalities > 0 && (
          <p>{t(lang, "historical_context_fatalities", { count: ctx.recent_fatalities })}</p>
        )}
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
  const [expandedBodies, setExpandedBodies] = useState<Record<string, boolean>>({});
  const [expandedFullBodies, setExpandedFullBodies] = useState<Record<string, boolean>>({});

  // Phase 5: 이슈 열람 행동 트래킹
  const trackBehavior = useTrackBehavior();
  React.useEffect(() => {
    if (issue) {
      trackBehavior.mutate({
        event_name: "issue_view",
        props: {
          cluster_id: id,
          country_code: issue.country_code || "",
          topic: issue.topic || "",
        },
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

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
      <div className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => window.history.length > 1 ? router.back() : router.push("/")} className="rounded-lg p-1.5 hover:bg-secondary transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-sm font-bold flex-1 truncate">{displayTitle}</h1>
        </div>
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* 요약 카드 */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 flex-wrap mb-3">
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

          {/* T14: 출처 투명성 배지 */}
          {(issue.independent_sources || issue.source_tiers?.length) && (
            <div className="flex items-center gap-2 mt-3 flex-wrap">
              <Shield className="h-3 w-3 text-muted-foreground" />
              {issue.independent_sources != null && issue.independent_sources > 0 && (
                <span className="text-[10px] font-medium text-blue-400 bg-blue-400/10 rounded-full px-2 py-0.5">
                  {t(lang, "issue_independent_sources", { n: issue.independent_sources })}
                </span>
              )}
              {(() => {
                const gradeA = issue.source_tiers?.filter(t => t === "A").length ?? 0;
                return gradeA > 0 ? (
                  <span className="text-[10px] font-medium text-green-400 bg-green-400/10 rounded-full px-2 py-0.5">
                    {t(lang, "issue_grade_a_count", { n: gradeA })}
                  </span>
                ) : null;
              })()}
              {issue.is_verified && (
                <span className="text-[10px] font-medium text-emerald-400 bg-emerald-400/10 rounded-full px-2 py-0.5" title={t(lang, "issue_verified_tooltip")}>
                  Verified
                </span>
              )}
              {issue.change_logs && issue.change_logs.length > 0 && (
                <span className="text-[10px] font-medium text-amber-400 bg-amber-400/10 rounded-full px-2 py-0.5">
                  {t(lang, "issue_updated_badge")}
                </span>
              )}
            </div>
          )}

          <div className="flex items-center justify-between mt-3 text-[10px] text-muted-foreground">
            <span>{t(lang, "issue_first_report")} {new Date(issue.first_event_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
            <span>{t(lang, "issue_last_report")} {new Date(issue.last_event_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
          </div>

          {/* 공유하기 + 히스토리 버튼 */}
          <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border">
            <ShareButton issueId={issue.id} title={displayTitle} />
            <button
              onClick={() => setShowHistory((v) => !v)}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors py-1 ml-auto"
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

        {/* 교차검증 증거 */}
        <CrossValidationSection clusterId={id} lang={lang} />

        {/* 역사적 맥락 (UCDP) */}
        <HistoricalContextSection clusterId={id} lang={lang} />

        {/* Impact Analysis — 요약 바로 아래 배치 */}
        <ImpactBriefCard clusterId={id} />
        <SectorImpactCard clusterId={id} />

        {/* T15: 정정/업데이트 이력 */}
        {issue.change_logs && issue.change_logs.length > 0 && (
          <div className="rounded-xl border border-amber-500/20 bg-card p-4">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="h-3.5 w-3.5 text-amber-400" />
              <h3 className="text-xs font-semibold text-amber-400">{t(lang, "issue_correction_history")}</h3>
            </div>
            <div className="space-y-2">
              {issue.change_logs.map((log, idx) => (
                <div key={idx} className="flex items-start gap-2 text-[10px]">
                  <div className="w-1.5 h-1.5 rounded-full bg-amber-400/50 mt-1 shrink-0" />
                  <div>
                    <span className="text-muted-foreground">
                      {new Date(log.created_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </span>
                    <span className="text-muted-foreground mx-1">·</span>
                    <span className="font-medium text-foreground">{log.field}</span>
                    {log.old_value && log.new_value && (
                      <span className="text-muted-foreground">
                        {" "}{log.old_value.length > 30 ? log.old_value.slice(0, 30) + "..." : log.old_value}
                        {" → "}
                        {log.new_value.length > 30 ? log.new_value.slice(0, 30) + "..." : log.new_value}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

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
                .sort((a, b) => new Date(b.event_time).getTime() - new Date(a.event_time).getTime())
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

                      {/* 본문 보기 토글 */}
                      {event.body && event.body.trim() !== "" && (
                        <div className="mt-2">
                          <button
                            onClick={() => setExpandedBodies((prev) => ({ ...prev, [event.id]: !prev[event.id] }))}
                            className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                          >
                            {expandedBodies[event.id] ? (
                              <><ChevronUp className="h-2.5 w-2.5" /> {t(lang, "event_hide_body")}</>
                            ) : (
                              <><ChevronDown className="h-2.5 w-2.5" /> {t(lang, "event_show_body")}</>
                            )}
                          </button>
                          {expandedBodies[event.id] && (() => {
                            const displayBody = lang === "ko" ? (event.body_ko ?? event.body) : event.body;
                            return (
                            <div className="mt-2 pt-2 border-t border-border/50">
                              <p className="text-[11px] text-muted-foreground leading-relaxed whitespace-pre-line">
                                {displayBody.length > 300 && !expandedFullBodies[event.id]
                                  ? displayBody.slice(0, 300) + "..."
                                  : displayBody}
                              </p>
                              {displayBody.length > 300 && (
                                <button
                                  onClick={() => setExpandedFullBodies((prev) => ({ ...prev, [event.id]: !prev[event.id] }))}
                                  className="mt-1 text-[10px] text-primary hover:text-primary/80 transition-colors font-medium"
                                >
                                  {expandedFullBodies[event.id] ? t(lang, "event_show_less") : t(lang, "event_show_more")}
                                </button>
                              )}
                            </div>
                            );
                          })()}
                        </div>
                      )}
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

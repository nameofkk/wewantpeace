"use client";

import { useQuery } from "@tanstack/react-query";
import { useAppStore } from "@/lib/store";
import { t, getTensionLevelLabel } from "@/lib/i18n";
import { getCountryName, getFlag } from "@/lib/countries";
import { cn } from "@/lib/utils";
import { adminFetch } from "@/lib/admin-utils";
import { BarChart3, Layers, AlertTriangle, Mail, Eye } from "lucide-react";
import Link from "next/link";

const SEVERITY_COLORS: Record<string, string> = {
  extreme: "border-l-red-800",
  severe: "border-l-red-500",
  warning: "border-l-orange-500",
  caution: "border-l-amber-500",
  stable: "border-l-green-500",
};

function severityClass(s: number) {
  if (s >= 80) return SEVERITY_COLORS.extreme;
  if (s >= 60) return SEVERITY_COLORS.severe;
  if (s >= 40) return SEVERITY_COLORS.warning;
  if (s >= 20) return SEVERITY_COLORS.caution;
  return SEVERITY_COLORS.stable;
}

const TENSION_BAR_COLORS: Record<number, string> = {
  0: "bg-green-500",
  1: "bg-amber-500",
  2: "bg-orange-500",
  3: "bg-red-500",
  4: "bg-red-800",
};

interface WeeklySummary {
  period: { start: string; end: string };
  top_issues: {
    id: string;
    title: string;
    title_ko: string | null;
    severity: number;
    kscore: number;
    event_count: number;
    country_code: string | null;
    topic: string;
  }[];
  top_tension: {
    country_code: string;
    raw_score: number;
    tension_level: number;
  }[];
  stats: {
    total_events: number;
    new_clusters: number;
    crisis_countries: number;
  };
  prev_stats?: {
    total_events: number;
    new_clusters: number;
  };
}

function WowDelta({ current, previous }: { current: number; previous: number }) {
  if (!previous || previous === 0) return null;
  const diff = current - previous;
  const pct = Math.round((diff / previous) * 100);
  const isUp = diff > 0;
  const isDown = diff < 0;
  return (
    <span className={cn(
      "text-xs font-bold tabular-nums ml-1",
      isUp ? "text-red-500" : isDown ? "text-emerald-500" : "text-muted-foreground",
    )}>
      {isUp ? "+" : ""}{pct}%
    </span>
  );
}

const TOPIC_KO: Record<string, string> = {
  conflict: "무장 충돌", terror: "폭력·테러", coup: "정변·쿠데타",
  sanctions: "경제 제재", cyber: "사이버 공격", protest: "시위·집회",
  diplomacy: "외교", maritime: "해상 분쟁", disaster: "재난·재해",
  health: "감염병·보건", unknown: "이슈",
};

export default function AdminWeeklyReportPage() {
  const lang = useAppStore((s) => s.lang);

  const { data, isLoading, error } = useQuery<WeeklySummary>({
    queryKey: ["admin-weekly-report-preview"],
    queryFn: () => adminFetch<WeeklySummary>("/public/weekly-summary"),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-20 text-muted-foreground">
        데이터를 불러올 수 없습니다.
      </div>
    );
  }

  const locale = lang === "en" ? "en-US" : "ko-KR";
  const periodStart = new Date(data.period.start).toLocaleDateString(locale, {
    year: "numeric", month: "short", day: "numeric",
  });
  const periodEnd = new Date(data.period.end).toLocaleDateString(locale, {
    year: "numeric", month: "short", day: "numeric",
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Eye className="h-5 w-5 text-primary" />
            {t(lang, "admin_weekly_report")} — 미리보기
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {periodStart} — {periodEnd} · 이메일 발송 전 내용을 확인합니다
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground bg-card border border-border rounded-lg px-3 py-2">
          <Mail className="h-3.5 w-3.5" />
          매주 월 09:00 UTC 자동 발송
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          {
            label: t(lang, "weekly_report_total_events"),
            value: data.stats.total_events,
            prev: data.prev_stats?.total_events,
            icon: BarChart3,
            color: "text-blue-400",
            bg: "bg-blue-500/10",
          },
          {
            label: t(lang, "weekly_report_new_clusters"),
            value: data.stats.new_clusters,
            prev: data.prev_stats?.new_clusters,
            icon: Layers,
            color: "text-emerald-400",
            bg: "bg-emerald-500/10",
          },
          {
            label: t(lang, "weekly_report_crisis_countries"),
            value: data.stats.crisis_countries,
            prev: undefined,
            icon: AlertTriangle,
            color: data.stats.crisis_countries > 0 ? "text-red-400" : "text-muted-foreground",
            bg: data.stats.crisis_countries > 0 ? "bg-red-500/10" : "bg-secondary",
          },
        ].map((s) => (
          <div key={s.label} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className={cn("inline-flex rounded-lg p-1.5", s.bg)}>
                <s.icon className={cn("h-4 w-4", s.color)} />
              </div>
              <span className="text-xs text-muted-foreground">{s.label}</span>
            </div>
            <p className="text-2xl font-bold tabular-nums">
              {s.value.toLocaleString()}
              {s.prev != null && <WowDelta current={s.value} previous={s.prev} />}
            </p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* TOP 10 Issues */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "weekly_report_top_issues")}
          </h2>
          <div className="space-y-2">
            {data.top_issues.map((issue, idx) => {
              const title = lang === "en" ? issue.title : (issue.title_ko ?? issue.title);
              const topicLabel = TOPIC_KO[issue.topic] || issue.topic;
              return (
                <Link
                  key={issue.id}
                  href={`/admin/clusters?search=${encodeURIComponent(issue.title.slice(0, 30))}`}
                  className={cn(
                    "flex items-start gap-3 rounded-xl border bg-card p-3 hover:border-primary/30 transition-colors border-l-[3px]",
                    severityClass(issue.severity),
                  )}
                >
                  <span className="text-xs font-bold text-muted-foreground tabular-nums w-5 shrink-0 pt-0.5">
                    {idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold leading-snug line-clamp-2">{title}</p>
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 mt-1.5 text-[11px] text-muted-foreground">
                      {issue.country_code && (
                        <span>{getFlag(issue.country_code)} {getCountryName(issue.country_code, lang)}</span>
                      )}
                      <span>{topicLabel}</span>
                      <span>Sev {issue.severity}</span>
                      <span>K {issue.kscore.toFixed(1)}</span>
                      <span>{issue.event_count} events</span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>

        {/* TOP 10 Tension */}
        <div>
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "weekly_report_tension_rank")}
          </h2>
          <div className="space-y-2">
            {data.top_tension.map((item, idx) => {
              const barWidth = Math.max(item.raw_score, 5);
              const levelLabel = getTensionLevelLabel(item.tension_level as 0 | 1 | 2 | 3 | 4, lang);
              return (
                <div
                  key={item.country_code}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3"
                >
                  <span className="text-xs font-bold text-muted-foreground tabular-nums w-5 shrink-0">
                    {idx + 1}
                  </span>
                  <span className="text-sm shrink-0">{getFlag(item.country_code)}</span>
                  <span className="text-sm font-medium w-24 shrink-0 truncate">
                    {getCountryName(item.country_code, lang)}
                  </span>
                  <div className="flex-1 h-5 bg-secondary rounded-full overflow-hidden">
                    <div
                      className={cn("h-full rounded-full transition-all", TENSION_BAR_COLORS[item.tension_level] ?? "bg-gray-500")}
                      style={{ width: `${barWidth}%` }}
                    />
                  </div>
                  <span className="text-xs font-bold tabular-nums w-10 text-right">
                    {item.raw_score.toFixed(1)}
                  </span>
                  <span className="text-[10px] text-muted-foreground w-10 shrink-0">
                    {levelLabel}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

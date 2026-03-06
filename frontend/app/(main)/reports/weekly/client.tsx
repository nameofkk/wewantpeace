"use client";

import { useAppStore } from "@/lib/store";
import { t, getTensionLevelLabel } from "@/lib/i18n";
import { getCountryName } from "@/lib/countries";
import { cn } from "@/lib/utils";
import { BarChart3, Globe, Layers, AlertTriangle, ExternalLink } from "lucide-react";
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
}

export default function WeeklyReportClient({ data }: { data: WeeklySummary | null }) {
  const lang = useAppStore((s) => s.lang);

  if (!data) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">
          {lang === "ko" ? "데이터를 불러올 수 없습니다." : "Unable to load data."}
        </p>
      </div>
    );
  }

  const locale = lang === "en" ? "en-US" : "ko-KR";
  const periodStart = new Date(data.period.start).toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
  });
  const periodEnd = new Date(data.period.end).toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
  });

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background/95 backdrop-blur-sm px-4 py-4">
        <h1 className="text-xl font-bold">{t(lang, "weekly_report_title")}</h1>
        <p className="text-xs text-muted-foreground mt-0.5">
          {periodStart} — {periodEnd}
        </p>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 max-w-3xl mx-auto w-full">
        {/* Stats Summary */}
        <div className="grid grid-cols-3 gap-3">
          {[
            {
              label: t(lang, "weekly_report_total_events"),
              value: data.stats.total_events,
              icon: BarChart3,
              color: "text-blue-400",
              bg: "bg-blue-500/10",
            },
            {
              label: t(lang, "weekly_report_new_clusters"),
              value: data.stats.new_clusters,
              icon: Layers,
              color: "text-emerald-400",
              bg: "bg-emerald-500/10",
            },
            {
              label: t(lang, "weekly_report_crisis_countries"),
              value: data.stats.crisis_countries,
              icon: AlertTriangle,
              color: data.stats.crisis_countries > 0 ? "text-red-400" : "text-muted-foreground",
              bg: data.stats.crisis_countries > 0 ? "bg-red-500/10" : "bg-secondary",
            },
          ].map((s) => (
            <div key={s.label} className="rounded-xl border border-border bg-card p-3 text-center">
              <div className={cn("inline-flex rounded-lg p-1.5 mb-1.5", s.bg)}>
                <s.icon className={cn("h-4 w-4", s.color)} />
              </div>
              <p className="text-2xl font-bold tabular-nums">{s.value.toLocaleString()}</p>
              <p className="text-[10px] text-muted-foreground mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>

        {/* TOP 10 Issues */}
        <div>
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "weekly_report_top_issues")}
          </h2>
          <div className="space-y-2">
            {data.top_issues.map((issue, idx) => {
              const title = lang === "en" ? issue.title : (issue.title_ko ?? issue.title);
              return (
                <Link
                  key={issue.id}
                  href={`/issues/${issue.id}`}
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
                    <div className="flex items-center gap-2 mt-1.5 text-[11px] text-muted-foreground">
                      {issue.country_code && (
                        <span>{getCountryName(issue.country_code, lang)}</span>
                      )}
                      <span>Severity {issue.severity}</span>
                      <span>KScore {issue.kscore}</span>
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
          <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "weekly_report_tension_rank")}
          </h2>
          <div className="space-y-2">
            {data.top_tension.map((item, idx) => {
              const barWidth = Math.max(item.raw_score, 5);
              const levelLabel = getTensionLevelLabel(item.tension_level as 0 | 1 | 2 | 3 | 4, lang);
              return (
                <Link
                  key={item.country_code}
                  href={`/issues/country/${item.country_code.toLowerCase()}`}
                  className="flex items-center gap-3 rounded-lg border border-border bg-card p-3 hover:border-primary/30 transition-colors"
                >
                  <span className="text-xs font-bold text-muted-foreground tabular-nums w-5 shrink-0">
                    {idx + 1}
                  </span>
                  <Globe className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
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
                </Link>
              );
            })}
          </div>
        </div>

        {/* CTA */}
        <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 text-center">
          <p className="text-sm font-medium mb-2">{t(lang, "weekly_report_cta")}</p>
          <div className="flex justify-center gap-3">
            <a
              href="https://play.google.com/store/apps/details?id=live.wewantpeace.twa"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              Google Play <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

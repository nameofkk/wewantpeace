"use client";

import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery } from "@tanstack/react-query";
import {
  Users, Flag, Layers, FileText, Activity, CreditCard,
  AlertTriangle, Bell, Workflow, TrendingUp, ArrowUpRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getCountryName } from "@/lib/countries";
import Link from "next/link";
import { adminFetch } from "@/lib/admin-utils";

interface WeekComparisonItem {
  this: number;
  last: number;
}

interface AdminStats {
  total_users: number;
  new_today: number;
  dau: number;
  subscribers: number;
  pending_reports: number;
  monthly_revenue: number;
  active_clusters: number;
  events_today: number;
  crisis_countries: number;
  push_tokens: number;
  unclassified_rate: number;
  translation_fail_rate: number;
  geo_fail_rate: number;
  week_comparison?: {
    new_users: WeekComparisonItem;
    events: WeekComparisonItem;
    subscriptions: WeekComparisonItem;
    trials: WeekComparisonItem;
  };
}

interface PipelineStats {
  error_sources: number;
  unclassified_rate: number;
  noise_clusters: number;
  spike_clusters: number;
  crisis_countries: number;
  push_tokens: number;
}

const LEVEL_COLORS = ["#22c55e", "#eab308", "#f97316", "#ef4444"];

/* ── health logic (같은 로직을 파이프라인과 공유) ── */
type Health = "green" | "yellow" | "red";
function stageHealth(ps: PipelineStats | undefined, stage: number): Health {
  if (!ps) return "green";
  switch (stage) {
    case 0: return ps.error_sources > 3 ? "red" : ps.error_sources > 0 ? "yellow" : "green";
    case 1: return ps.unclassified_rate > 0.1 ? "red" : ps.unclassified_rate > 0.05 ? "yellow" : "green";
    case 2: return "green";
    case 3: return ps.noise_clusters > 20 ? "red" : ps.noise_clusters > 10 ? "yellow" : "green";
    case 4: return ps.spike_clusters > 5 ? "red" : ps.spike_clusters > 2 ? "yellow" : "green";
    case 5: return "green";
    case 6: return ps.crisis_countries > 3 ? "red" : ps.crisis_countries > 1 ? "yellow" : "green";
    case 7: return "green";
    case 8: return ps.push_tokens === 0 ? "red" : "green";
    case 9: return "green";
    default: return "green";
  }
}

const HEALTH_BG: Record<Health, string> = { green: "bg-green-500", yellow: "bg-yellow-500", red: "bg-red-500" };
const HEALTH_RING: Record<Health, string> = { green: "ring-green-500/30", yellow: "ring-yellow-500/30", red: "ring-red-500/30" };

const STAGE_LABELS_KO = ["수집", "정규화", "중복제거", "클러스터", "KScore 알림", "KScore", "긴장도", "트렌딩", "푸시", "오펀"];
const STAGE_LABELS_EN = ["Collect", "Normalize", "Dedup", "Cluster", "KScore Alert", "KScore", "Tension", "Trending", "Push", "Orphan"];

export default function AdminDashboard() {
  const { lang } = useAppStore();

  const { data: stats, isLoading } = useQuery<AdminStats>({
    queryKey: ["admin-stats"],
    queryFn: () => adminFetch("/admin/stats"),
    refetchInterval: 60_000,
  });

  const { data: dailyCounts } = useQuery<{ date: string; count: number }[]>({
    queryKey: ["admin-events-daily"],
    queryFn: () => adminFetch("/admin/events/daily-counts?days=7"),
    refetchInterval: 5 * 60_000,
  });

  const { data: tensionData } = useQuery<
    { country_code: string; raw_score: number; tension_level: number }[]
  >({
    queryKey: ["admin-tension-all"],
    queryFn: () => adminFetch("/admin/tension"),
    refetchInterval: 5 * 60_000,
  });

  const { data: pipelineStats } = useQuery<PipelineStats>({
    queryKey: ["pipeline-stats-dash"],
    queryFn: () => adminFetch("/admin/pipeline/stats"),
    refetchInterval: 60_000,
  });

  const top10Tension = (tensionData ?? []).slice(0, 10);
  const stageLabels = lang === "ko" ? STAGE_LABELS_KO : STAGE_LABELS_EN;

  const kpiCards = [
    {
      label: t(lang, "admin_total_users"),
      value: stats?.total_users ?? 0,
      sub: `+${stats?.new_today ?? 0} ${t(lang, "admin_new_24h")}`,
      icon: Users,
      color: "text-blue-400",
      bg: "bg-blue-500/10",
      href: "/admin/users",
    },
    {
      label: t(lang, "admin_active_subs"),
      value: stats?.subscribers ?? 0,
      sub: `₩${(stats?.monthly_revenue ?? 0).toLocaleString()} ${t(lang, "admin_monthly_revenue")}`,
      icon: CreditCard,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
      href: "/admin/users",
    },
    {
      label: t(lang, "admin_active_clusters"),
      value: stats?.active_clusters ?? 0,
      icon: Layers,
      color: "text-emerald-400",
      bg: "bg-emerald-500/10",
      href: "/admin/clusters",
    },
    {
      label: t(lang, "admin_events_today"),
      value: stats?.events_today ?? 0,
      icon: FileText,
      color: "text-cyan-400",
      bg: "bg-cyan-500/10",
      href: "/admin/events",
    },
    {
      label: t(lang, "admin_crisis_countries"),
      value: stats?.crisis_countries ?? 0,
      icon: AlertTriangle,
      color: stats?.crisis_countries ? "text-red-400" : "text-muted-foreground",
      bg: stats?.crisis_countries ? "bg-red-500/10" : "bg-secondary",
      href: "/admin/tension",
    },
    {
      label: t(lang, "admin_pending_reports"),
      value: stats?.pending_reports ?? 0,
      icon: Flag,
      color: (stats?.pending_reports ?? 0) > 0 ? "text-orange-400" : "text-muted-foreground",
      bg: (stats?.pending_reports ?? 0) > 0 ? "bg-orange-500/10" : "bg-secondary",
      href: "/admin/content",
    },
    {
      label: t(lang, "admin_push_tokens"),
      value: stats?.push_tokens ?? 0,
      icon: Bell,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
      href: "/admin/pipeline",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_dashboard")}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">{t(lang, "admin_overview")}</p>
        </div>
        <Link
          href="/admin/pipeline"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
        >
          <Workflow className="h-3.5 w-3.5" />
          {t(lang, "admin_pipeline")}
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </div>

      {/* Pipeline Health Bar */}
      {pipelineStats && (
        <Link
          href="/admin/pipeline"
          className="flex items-center gap-3 px-4 py-3 rounded-xl border border-border bg-card hover:border-primary/30 transition-colors"
        >
          <Workflow className="h-4 w-4 text-muted-foreground shrink-0" />
          <span className="text-xs font-medium text-muted-foreground shrink-0">
            {t(lang, "dashboard_pipeline_health")}
          </span>
          <div className="flex items-center gap-1.5 flex-1 flex-wrap">
            {Array.from({ length: 10 }).map((_, i) => {
              const h = stageHealth(pipelineStats, i);
              return (
                <div key={i} className="flex items-center gap-1" title={stageLabels[i]}>
                  <div className={cn("h-2.5 w-2.5 rounded-full ring-1.5", HEALTH_BG[h], HEALTH_RING[h])} />
                  <span className="text-[9px] text-muted-foreground hidden lg:inline">{stageLabels[i]}</span>
                </div>
              );
            })}
          </div>
          <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        </Link>
      )}

      {/* KPI Cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse">
              <div className="h-4 w-20 rounded bg-secondary mb-2" />
              <div className="h-7 w-14 rounded bg-secondary" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {kpiCards.map((card) => (
            <Link
              key={card.label}
              href={card.href}
              className="group rounded-xl border border-border bg-card p-4 hover:border-primary/30 transition-all hover:shadow-sm"
            >
              <div className="flex items-center justify-between mb-2">
                <div className={cn("rounded-lg p-1.5", card.bg)}>
                  <card.icon className={cn("h-3.5 w-3.5", card.color)} />
                </div>
                <ArrowUpRight className="h-3 w-3 text-muted-foreground/0 group-hover:text-muted-foreground transition-colors" />
              </div>
              <p className="text-2xl font-bold tabular-nums">{card.value.toLocaleString()}</p>
              <p className="text-[11px] text-muted-foreground mt-0.5">{card.label}</p>
              {card.sub && (
                <p className="text-[10px] text-muted-foreground/60 mt-0.5">{card.sub}</p>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Week Comparison */}
      {stats?.week_comparison && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "dashboard_week_comparison")}
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {([
              { key: "new_users" as const, label: t(lang, "dashboard_wc_users"), icon: Users, color: "text-blue-400" },
              { key: "events" as const, label: t(lang, "dashboard_wc_events"), icon: FileText, color: "text-cyan-400" },
              { key: "subscriptions" as const, label: t(lang, "dashboard_wc_subs"), icon: CreditCard, color: "text-purple-400" },
              { key: "trials" as const, label: t(lang, "dashboard_wc_trials"), icon: Activity, color: "text-emerald-400" },
            ] as const).map((item) => {
              const wc = stats.week_comparison![item.key];
              const diff = wc.this - wc.last;
              const pct = wc.last > 0 ? Math.round((diff / wc.last) * 100) : (wc.this > 0 ? 100 : 0);
              return (
                <div key={item.key} className="rounded-lg border border-border p-3">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <item.icon className={cn("h-3.5 w-3.5", item.color)} />
                    <span className="text-[11px] text-muted-foreground">{item.label}</span>
                  </div>
                  <p className="text-xl font-bold tabular-nums">{wc.this.toLocaleString()}</p>
                  <p className={cn(
                    "text-[11px] font-medium mt-0.5",
                    diff > 0 ? "text-green-400" : diff < 0 ? "text-red-400" : "text-muted-foreground"
                  )}>
                    {diff > 0 ? "↑" : diff < 0 ? "↓" : "→"} {Math.abs(diff)} ({pct > 0 ? "+" : ""}{pct}%)
                    <span className="text-muted-foreground/60 font-normal ml-1">
                      {t(lang, "dashboard_vs_last_week")}
                    </span>
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Data Quality */}
      {stats && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
            {t(lang, "dashboard_data_quality")}
          </h3>
          <div className="grid grid-cols-3 gap-3">
            {[
              {
                label: lang === "ko" ? "미분류" : "Unclassified",
                value: stats.unclassified_rate,
                warn: stats.unclassified_rate > 15,
              },
              {
                label: lang === "ko" ? "번역 실패" : "Translation Fail",
                value: stats.translation_fail_rate,
                warn: stats.translation_fail_rate > 10,
              },
              {
                label: lang === "ko" ? "지오 실패" : "Geo Fail",
                value: stats.geo_fail_rate,
                warn: stats.geo_fail_rate > 20,
              },
            ].map((q) => (
              <div key={q.label} className="text-center">
                <p className={cn(
                  "text-xl font-bold tabular-nums",
                  q.warn ? "text-orange-400" : "text-foreground"
                )}>
                  {q.value}%
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">{q.label}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 7-day event trend */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {t(lang, "admin_event_chart_title")}
            </h3>
            <Link href="/admin/events" className="text-[10px] text-primary hover:underline flex items-center gap-0.5">
              {t(lang, "pipeline_view_all")} <ArrowUpRight className="h-2.5 w-2.5" />
            </Link>
          </div>
          {dailyCounts && dailyCounts.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={dailyCounts}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "hsl(215 20% 65%)" }}
                  tickFormatter={(v) => v.slice(5)}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "hsl(215 20% 65%)" }}
                  width={36}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(222 47% 11%)",
                    border: "1px solid hsl(217 32% 17%)",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-xs text-muted-foreground">
              {t(lang, "admin_no_data")}
            </div>
          )}
        </div>

        {/* Tension top 10 */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              {t(lang, "admin_tension_heatmap")}
            </h3>
            <Link href="/admin/tension" className="text-[10px] text-primary hover:underline flex items-center gap-0.5">
              {t(lang, "pipeline_view_all")} <ArrowUpRight className="h-2.5 w-2.5" />
            </Link>
          </div>
          {top10Tension.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={top10Tension} layout="vertical">
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fontSize: 10, fill: "hsl(215 20% 65%)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="country_code"
                  tick={{ fontSize: 10, fill: "hsl(215 20% 65%)" }}
                  width={36}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(222 47% 11%)",
                    border: "1px solid hsl(217 32% 17%)",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                  formatter={(value) => [(value as number).toFixed(1), lang === "ko" ? "긴장점수" : "Score"]}
                  labelFormatter={(v) => getCountryName(v, lang)}
                />
                <Bar dataKey="raw_score" radius={[0, 6, 6, 0]}>
                  {top10Tension.map((entry, i) => (
                    <Cell key={i} fill={LEVEL_COLORS[entry.tension_level] ?? "#6b7280"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[200px] flex items-center justify-center text-xs text-muted-foreground">
              {t(lang, "admin_no_data")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

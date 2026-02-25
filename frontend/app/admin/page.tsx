"use client";

import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery } from "@tanstack/react-query";
import {
  Users, Flag, Layers, FileText, Activity, CreditCard,
  AlertTriangle, Bell,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { getCountryName } from "@/lib/countries";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function adminFetch<T>(path: string): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("firebase_token") : null;
  const devUid =
    typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (devUid) headers["X-Dev-UID"] = devUid;
  else if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`Admin API error: ${res.status}`);
  return res.json();
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
}

const LEVEL_COLORS = ["#22c55e", "#eab308", "#f97316", "#ef4444"];

export default function AdminDashboard() {
  const { user } = useAuth();
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

  const top10Tension = (tensionData ?? []).slice(0, 10);

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
      href: "/admin/reports",
    },
    {
      label: t(lang, "admin_active_subs"),
      value: stats?.subscribers ?? 0,
      sub: `₩${(stats?.monthly_revenue ?? 0).toLocaleString()} ${t(lang, "admin_monthly_revenue")}`,
      icon: CreditCard,
      color: "text-purple-400",
      bg: "bg-purple-500/10",
      href: "/admin/subscriptions",
    },
    {
      label: t(lang, "admin_push_tokens"),
      value: stats?.push_tokens ?? 0,
      icon: Bell,
      color: "text-amber-400",
      bg: "bg-amber-500/10",
      href: "#",
    },
  ];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{t(lang, "admin_dashboard")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t(lang, "admin_overview")}
        </p>
      </div>

      {/* KPI Cards */}
      {isLoading ? (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {[...Array(7)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-5 animate-pulse">
              <div className="h-4 w-24 rounded bg-secondary mb-3" />
              <div className="h-8 w-16 rounded bg-secondary" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
          {kpiCards.map((card) => (
            <Link
              key={card.label}
              href={card.href}
              className="rounded-xl border border-border bg-card p-5 hover:border-primary/30 transition-colors"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className={cn("rounded-lg p-2", card.bg)}>
                  <card.icon className={cn("h-4 w-4", card.color)} />
                </div>
                <p className="text-sm text-muted-foreground">{card.label}</p>
              </div>
              <p className="text-3xl font-bold tabular-nums">{card.value.toLocaleString()}</p>
              {card.sub && (
                <p className="text-xs text-muted-foreground mt-1">{card.sub}</p>
              )}
            </Link>
          ))}
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 7일 이벤트 수집 추이 */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-medium mb-4">{t(lang, "admin_event_chart_title")}</h3>
          {dailyCounts && dailyCounts.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={dailyCounts}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis tick={{ fontSize: 11 }} width={40} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(222 47% 11%)",
                    border: "1px solid hsl(217 32% 17%)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Bar dataKey="count" radius={[4, 4, 0, 0]} fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">
              {t(lang, "admin_no_data")}
            </div>
          )}
        </div>

        {/* 긴장도 Top 10 */}
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="text-sm font-medium mb-4">{t(lang, "admin_tension_heatmap")}</h3>
          {top10Tension.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={top10Tension} layout="vertical">
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="country_code"
                  tick={{ fontSize: 11 }}
                  width={40}
                  tickFormatter={(v) => v}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(222 47% 11%)",
                    border: "1px solid hsl(217 32% 17%)",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  formatter={(value: number) => [value.toFixed(1), lang === "ko" ? "긴장점수" : "Score"]}
                  labelFormatter={(v) => getCountryName(v, lang)}
                />
                <Bar dataKey="raw_score" radius={[0, 4, 4, 0]}>
                  {top10Tension.map((entry, i) => (
                    <Cell key={i} fill={LEVEL_COLORS[entry.tension_level] ?? "#6b7280"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-sm text-muted-foreground">
              {t(lang, "admin_no_data")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

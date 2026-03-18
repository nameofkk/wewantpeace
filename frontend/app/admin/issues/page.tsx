"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Layers, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { getCountryName, getFlag } from "@/lib/countries";
import { useAdminToast } from "@/components/ui/admin-toast";
import { API_BASE } from "@/lib/admin-utils";
import { useSearchParams, useRouter } from "next/navigation";
import { TabBar } from "@/components/admin/TabBar";
import { StatCard } from "@/components/admin/StatCard";
import { Pagination } from "@/components/admin/Pagination";
import { SeverityBadge, SEVERITY_COLORS } from "@/components/admin/SeverityBadge";

/* ── Types ── */
interface ClusterItem {
  id: string;
  title: string;
  title_ko: string | null;
  country_code: string | null;
  topic: string;
  severity: number;
  kscore: number;
  event_count: number;
  confidence: number;
  first_event_at: string;
  last_event_at: string;
  created_at: string;
}

interface EventItem {
  id: string;
  title: string;
  title_ko: string | null;
  country_code: string | null;
  topic: string;
  severity: number;
  source_tier: string;
  confidence: number;
  event_time: string;
  created_at: string;
}

/* ── Constants ── */
const TOPICS = ["conflict", "terror", "coup", "sanctions", "cyber", "protest", "diplomacy", "maritime", "disaster", "health", "unknown"];

const TIER_LABELS: Record<string, { label: string; color: string }> = {
  A: { label: "Official", color: "bg-yellow-500/20 text-yellow-400" },
  B: { label: "Verified", color: "bg-blue-500/20 text-blue-400" },
  C: { label: "OSINT", color: "bg-amber-500/20 text-amber-400" },
  D: { label: "Unverified", color: "bg-secondary text-muted-foreground" },
};

/* ── Clusters Tab ── */
function ClustersTab() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const { toast } = useAdminToast();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [topicFilter, setTopicFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [countryFilter, setCountryFilter] = useState("");

  const { data, isLoading } = useQuery<{ total: number; items: ClusterItem[] }>({
    queryKey: ["admin-clusters", page, search, topicFilter, severityFilter, countryFilter],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "20" });
      if (search) params.append("search", search);
      if (topicFilter) params.append("topic", topicFilter);
      if (severityFilter) params.append("severity", severityFilter);
      if (countryFilter) params.append("country", countryFilter);
      const res = await fetch(`${API_BASE}/admin/clusters?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Load failed");
      return res.json();
    },
    enabled: !!user,
  });

  const patchMutation = useMutation({
    mutationFn: async ({ id, body }: { id: string; body: Record<string, unknown> }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/clusters/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Update failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-clusters"] });
      toast(t(lang, "admin_toast_updated"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  const totalPages = Math.ceil((data?.total ?? 0) / 20);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder={t(lang, "admin_search")}
            className="w-full rounded-lg border border-border bg-card pl-9 pr-4 py-2 text-sm outline-none focus:border-primary"
          />
        </div>
        <select
          value={topicFilter}
          onChange={(e) => { setTopicFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_topic")}: {t(lang, "admin_all")}</option>
          {TOPICS.map((tp) => (<option key={tp} value={tp}>{tp}</option>))}
        </select>
        <select
          value={severityFilter}
          onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_severity")}: {t(lang, "admin_all")}</option>
          {[0, 1, 2, 3, 4, 5].map((s) => (<option key={s} value={s}>{s}</option>))}
        </select>
        <input
          type="text"
          value={countryFilter}
          onChange={(e) => { setCountryFilter(e.target.value.toUpperCase()); setPage(1); }}
          placeholder={t(lang, "admin_country") + " (UA, PS...)"}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none w-32"
          maxLength={4}
        />
      </div>

      {/* Content */}
      {isLoading ? (
        <>
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 p-3 border-t border-border animate-pulse">
                <div className="h-4 w-48 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
              </div>
            ))}
          </div>
          <div className="md:hidden space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
                <div className="h-4 w-48 rounded bg-secondary" />
                <div className="h-3 w-24 rounded bg-secondary" />
                <div className="flex gap-2"><div className="h-5 w-16 rounded bg-secondary" /><div className="h-5 w-12 rounded bg-secondary" /></div>
              </div>
            ))}
          </div>
        </>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <Layers className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_title_col")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_country")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_topic")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_severity")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">KScore</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_event_count")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_updated_at")}</th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">{t(lang, "admin_actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((c) => (
                  <tr key={c.id} className="hover:bg-secondary/20">
                    <td className="px-3 py-3 max-w-[250px]">
                      <p className="text-sm truncate font-medium">{lang === "ko" && c.title_ko ? c.title_ko : c.title}</p>
                    </td>
                    <td className="px-3 py-3 text-xs">
                      {c.country_code ? `${getFlag(c.country_code)} ${c.country_code}` : "\u2014"}
                    </td>
                    <td className="px-3 py-3">
                      <select
                        value={c.topic}
                        onChange={(e) => patchMutation.mutate({ id: c.id, body: { topic: e.target.value } })}
                        className="rounded px-2 py-0.5 text-xs font-medium border-0 outline-none cursor-pointer bg-secondary"
                      >
                        {TOPICS.map((tp) => (<option key={tp} value={tp}>{tp}</option>))}
                      </select>
                    </td>
                    <td className="px-3 py-3">
                      <select
                        value={c.severity}
                        onChange={(e) => patchMutation.mutate({ id: c.id, body: { severity: Number(e.target.value) } })}
                        className={cn("rounded px-2 py-0.5 text-xs font-medium border-0 outline-none cursor-pointer", SEVERITY_COLORS[c.severity] ?? "")}
                      >
                        {[0, 1, 2, 3, 4, 5].map((s) => (<option key={s} value={s}>{s}</option>))}
                      </select>
                    </td>
                    <td className="px-3 py-3">
                      <span className={cn(
                        "text-xs font-bold tabular-nums",
                        c.kscore >= 7 ? "text-red-400" : c.kscore >= 5 ? "text-orange-400" : c.kscore >= 3 ? "text-yellow-400" : "text-muted-foreground"
                      )}>
                        {c.kscore.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-xs tabular-nums">{c.event_count}</td>
                    <td className="px-3 py-3 text-xs text-muted-foreground">
                      {new Date(c.last_event_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    </td>
                    <td className="px-3 py-3 text-right">
                      {c.severity > 0 ? (
                        <button
                          onClick={() => patchMutation.mutate({ id: c.id, body: { is_active: false } })}
                          className="text-xs text-red-400 hover:underline"
                        >
                          {t(lang, "admin_deactivate")}
                        </button>
                      ) : (
                        <span className="text-xs text-muted-foreground">{t(lang, "admin_inactive")}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile card layout */}
          <div className="md:hidden space-y-3">
            {data.items.map((c) => (
              <div key={c.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-start justify-between mb-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{lang === "ko" && c.title_ko ? c.title_ko : c.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {c.country_code ? `${getFlag(c.country_code)} ${c.country_code}` : "\u2014"}
                    </p>
                  </div>
                  <span className={cn("text-xs font-bold tabular-nums", c.kscore >= 7 ? "text-red-400" : c.kscore >= 5 ? "text-orange-400" : c.kscore >= 3 ? "text-yellow-400" : "text-muted-foreground")}>
                    {c.kscore.toFixed(2)}
                  </span>
                </div>
                <div className="flex flex-wrap gap-2 mb-2">
                  <select
                    value={c.topic}
                    onChange={(e) => patchMutation.mutate({ id: c.id, body: { topic: e.target.value } })}
                    className="rounded px-2 py-0.5 text-xs font-medium border-0 outline-none cursor-pointer bg-secondary"
                  >
                    {TOPICS.map((tp) => (<option key={tp} value={tp}>{tp}</option>))}
                  </select>
                  <select
                    value={c.severity}
                    onChange={(e) => patchMutation.mutate({ id: c.id, body: { severity: Number(e.target.value) } })}
                    className={cn("rounded px-2 py-0.5 text-xs font-medium border-0 outline-none cursor-pointer", SEVERITY_COLORS[c.severity] ?? "")}
                  >
                    {[0, 1, 2, 3, 4, 5].map((s) => (<option key={s} value={s}>{s}</option>))}
                  </select>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{c.event_count} events</span>
                  <span>{new Date(c.last_event_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                </div>
                {c.severity > 0 && (
                  <button
                    onClick={() => patchMutation.mutate({ id: c.id, body: { is_active: false } })}
                    className="mt-2 text-xs text-red-400 hover:underline"
                  >
                    {t(lang, "admin_deactivate")}
                  </button>
                )}
              </div>
            ))}
          </div>
        </>
      )}

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        prevLabel={t(lang, "admin_prev")}
        nextLabel={t(lang, "admin_next")}
      />
    </>
  );
}

/* ── Events Tab ── */
function EventsTab() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const [page, setPage] = useState(1);
  const [sourceFilter, setSourceFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [titleSearch, setTitleSearch] = useState("");

  const { data, isLoading } = useQuery<{ total: number; items: EventItem[] }>({
    queryKey: ["admin-events", page, sourceFilter, countryFilter, severityFilter, titleSearch],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "30" });
      if (sourceFilter) params.append("source", sourceFilter);
      if (countryFilter) params.append("country", countryFilter);
      if (severityFilter) params.append("severity", severityFilter);
      if (titleSearch) params.append("search", titleSearch);
      const res = await fetch(`${API_BASE}/admin/events?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Load failed");
      return res.json();
    },
    enabled: !!user,
  });

  const totalPages = Math.ceil((data?.total ?? 0) / 30);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <>
      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={titleSearch}
            onChange={(e) => { setTitleSearch(e.target.value); setPage(1); }}
            placeholder={t(lang, "admin_search")}
            className="w-full rounded-lg border border-border bg-card pl-9 pr-4 py-2 text-sm outline-none focus:border-primary"
          />
        </div>
        <select
          value={sourceFilter}
          onChange={(e) => { setSourceFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_source")}: {t(lang, "admin_all")}</option>
          <option value="A">A (Official)</option>
          <option value="B">B (Verified)</option>
          <option value="C">C (OSINT)</option>
          <option value="D">D (Unverified)</option>
        </select>
        <input
          type="text"
          value={countryFilter}
          onChange={(e) => { setCountryFilter(e.target.value.toUpperCase()); setPage(1); }}
          placeholder={t(lang, "admin_country") + " (UA, PS...)"}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none w-32"
          maxLength={4}
        />
        <select
          value={severityFilter}
          onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_severity")}: {t(lang, "admin_all")}</option>
          {[1, 2, 3, 4, 5].map((s) => (<option key={s} value={s}>&ge; {s}</option>))}
        </select>
      </div>

      {/* Content */}
      {isLoading ? (
        <>
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 p-3 border-t border-border animate-pulse">
                <div className="h-4 w-48 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-8 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
              </div>
            ))}
          </div>
          <div className="md:hidden space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-2">
                <div className="h-4 w-full rounded bg-secondary" />
                <div className="flex gap-2"><div className="h-4 w-12 rounded bg-secondary" /><div className="h-4 w-16 rounded bg-secondary" /></div>
                <div className="h-3 w-24 rounded bg-secondary" />
              </div>
            ))}
          </div>
        </>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <FileText className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_title_col")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_country")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_topic")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_severity")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_confidence")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_event_time")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((e) => {
                  const tier = TIER_LABELS[e.source_tier] ?? TIER_LABELS.D;
                  return (
                    <tr key={e.id} className="hover:bg-secondary/20">
                      <td className="px-3 py-2.5 max-w-[300px]">
                        <p className="text-sm truncate">{lang === "ko" && e.title_ko ? e.title_ko : e.title}</p>
                      </td>
                      <td className="px-3 py-2.5 text-xs">
                        {e.country_code ? `${getFlag(e.country_code)} ${e.country_code}` : "\u2014"}
                      </td>
                      <td className="px-3 py-2.5 text-xs">{e.topic}</td>
                      <td className="px-3 py-2.5">
                        <SeverityBadge severity={e.severity} />
                      </td>
                      <td className="px-3 py-2.5">
                        <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", tier.color)}>
                          {tier.label}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums text-muted-foreground">
                        {(e.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">
                        {new Date(e.event_time).toLocaleString(locale, {
                          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                        })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {data.items.map((e) => {
              const tier = TIER_LABELS[e.source_tier] ?? TIER_LABELS.D;
              return (
                <div key={e.id} className="rounded-xl border border-border bg-card p-4">
                  <p className="text-sm font-medium mb-1 line-clamp-2">{lang === "ko" && e.title_ko ? e.title_ko : e.title}</p>
                  <div className="flex flex-wrap gap-2 mb-2">
                    {e.country_code && <span className="text-xs">{getFlag(e.country_code)} {e.country_code}</span>}
                    <span className="text-xs text-muted-foreground">{e.topic}</span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", tier.color)}>{tier.label}</span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <div className="flex gap-3">
                      <SeverityBadge severity={e.severity} />
                      <span className="tabular-nums">{(e.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <span>{new Date(e.event_time).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}

      <Pagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        prevLabel={t(lang, "admin_prev")}
        nextLabel={t(lang, "admin_next")}
      />
    </>
  );
}

/* ── Main Page ── */
export default function AdminIssuesPage() {
  const { lang } = useAppStore();
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeTab = searchParams.get("tab") || "clusters";

  // Summary stats
  const { user } = useAuth();
  const { data: statsData } = useQuery<{ active_clusters: number; events_today: number }>({
    queryKey: ["admin-stats-mini"],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Load failed");
      return res.json();
    },
    enabled: !!user,
  });

  const handleTabChange = (tab: string) => {
    router.push(`/admin/issues?tab=${tab}`);
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{t(lang, "admin_issues")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? "클러스터와 이벤트를 통합 관리합니다" : "Manage clusters and events in one place"}
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <StatCard
          label={t(lang, "admin_active_clusters")}
          value={statsData?.active_clusters ?? 0}
          icon={Layers}
          iconColor="text-emerald-400"
          iconBg="bg-emerald-500/10"
        />
        <StatCard
          label={t(lang, "admin_events_today")}
          value={statsData?.events_today ?? 0}
          icon={FileText}
          iconColor="text-cyan-400"
          iconBg="bg-cyan-500/10"
        />
      </div>

      {/* Tabs */}
      <TabBar
        tabs={[
          { key: "clusters", label: t(lang, "admin_issues_tab_clusters"), icon: Layers },
          { key: "events", label: t(lang, "admin_issues_tab_events"), icon: FileText },
        ]}
        activeTab={activeTab}
        onChange={handleTabChange}
      />

      {activeTab === "clusters" ? <ClustersTab /> : <EventsTab />}
    </div>
  );
}

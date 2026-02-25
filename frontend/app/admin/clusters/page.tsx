"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Loader2, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import { getCountryName, getFlag } from "@/lib/countries";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
  is_spike: boolean;
  first_event_at: string;
  last_event_at: string;
  created_at: string;
}

const SEVERITY_COLORS: Record<number, string> = {
  0: "bg-secondary text-muted-foreground",
  1: "bg-green-500/20 text-green-400",
  2: "bg-yellow-500/20 text-yellow-400",
  3: "bg-orange-500/20 text-orange-400",
  4: "bg-red-500/20 text-red-400",
  5: "bg-red-600/30 text-red-300",
};

export default function AdminClustersPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin-clusters"] }),
  });

  const totalPages = Math.ceil((data?.total ?? 0) / 20);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  const TOPICS = ["conflict", "terror", "coup", "sanctions", "cyber", "protest", "diplomacy", "maritime", "disaster", "health", "unknown"];

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{t(lang, "admin_clusters")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {data?.total ?? 0} {lang === "ko" ? "개 클러스터" : "clusters"}
        </p>
      </div>

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
          {TOPICS.map((tp) => (
            <option key={tp} value={tp}>{tp}</option>
          ))}
        </select>
        <select
          value={severityFilter}
          onChange={(e) => { setSeverityFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_severity")}: {t(lang, "admin_all")}</option>
          {[0, 1, 2, 3, 4, 5].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
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

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <Layers className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <div className="rounded-xl border border-border overflow-x-auto">
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
                    {c.is_spike && (
                      <span className="text-[9px] rounded-full bg-amber-500/20 text-amber-400 px-1.5 py-0.5 font-bold">SPIKE</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-xs">
                    {c.country_code ? `${getFlag(c.country_code)} ${c.country_code}` : "—"}
                  </td>
                  <td className="px-3 py-3 text-xs">{c.topic}</td>
                  <td className="px-3 py-3">
                    <select
                      value={c.severity}
                      onChange={(e) => patchMutation.mutate({ id: c.id, body: { severity: Number(e.target.value) } })}
                      className={cn("rounded px-2 py-0.5 text-xs font-medium border-0 outline-none cursor-pointer", SEVERITY_COLORS[c.severity] ?? "")}
                    >
                      {[0, 1, 2, 3, 4, 5].map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-3">
                    <span className={cn(
                      "text-xs font-bold tabular-nums",
                      c.kscore >= 3 ? "text-red-400" : c.kscore >= 2 ? "text-orange-400" : c.kscore >= 1 ? "text-yellow-400" : "text-muted-foreground"
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
                        {lang === "ko" ? "비활성화" : "Deactivate"}
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
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-4">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {t(lang, "admin_prev")}
          </button>
          <span className="flex items-center px-3 text-sm text-muted-foreground">
            {t(lang, "admin_page_of", { page, total: totalPages })}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
          >
            {t(lang, "admin_next")}
          </button>
        </div>
      )}
    </div>
  );
}

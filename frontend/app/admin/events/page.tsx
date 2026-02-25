"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery } from "@tanstack/react-query";
import { Search, Loader2, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import { getFlag } from "@/lib/countries";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

const TIER_LABELS: Record<string, { label: string; color: string }> = {
  A: { label: "Official", color: "bg-yellow-500/20 text-yellow-400" },
  B: { label: "Verified", color: "bg-blue-500/20 text-blue-400" },
  C: { label: "OSINT", color: "bg-amber-500/20 text-amber-400" },
  D: { label: "Unverified", color: "bg-secondary text-muted-foreground" },
};

export default function AdminEventsPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const [page, setPage] = useState(1);
  const [sourceFilter, setSourceFilter] = useState("");
  const [countryFilter, setCountryFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("");

  const { data, isLoading } = useQuery<{ total: number; items: EventItem[] }>({
    queryKey: ["admin-events", page, sourceFilter, countryFilter, severityFilter],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "30" });
      if (sourceFilter) params.append("source", sourceFilter);
      if (countryFilter) params.append("country", countryFilter);
      if (severityFilter) params.append("severity", severityFilter);
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
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{t(lang, "admin_events")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {data?.total ?? 0} {lang === "ko" ? "개 이벤트" : "events"}
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
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
          {[1, 2, 3, 4, 5].map((s) => (
            <option key={s} value={s}>≥ {s}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <FileText className="h-10 w-10 mb-3" />
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
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source")}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "신뢰도" : "Conf."}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "이벤트 시간" : "Event Time"}</th>
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
                      {e.country_code ? `${getFlag(e.country_code)} ${e.country_code}` : "—"}
                    </td>
                    <td className="px-3 py-2.5 text-xs">{e.topic}</td>
                    <td className="px-3 py-2.5">
                      <span className={cn(
                        "text-xs font-bold tabular-nums",
                        e.severity >= 4 ? "text-red-400" : e.severity >= 3 ? "text-orange-400" : e.severity >= 2 ? "text-yellow-400" : "text-muted-foreground"
                      )}>
                        {e.severity}
                      </span>
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

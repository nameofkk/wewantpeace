"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Activity, RefreshCw, Loader2, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { getCountryName, getFlag } from "@/lib/countries";
import { useAdminToast } from "@/components/ui/admin-toast";
import { API_BASE } from "@/lib/admin-utils";

interface TensionRow {
  country_code: string;
  raw_score: number;
  tension_level: number;
  percentile_30d: number;
  event_score: number;
  accel_score: number;
  spillover_score: number;
  updated_at: string;
}

const LEVEL_LABELS_KO = ["안정", "주의", "경계", "심각", "극심"];
const LEVEL_LABELS_EN = ["Stable", "Caution", "Alert", "Severe", "Extreme"];
const LEVEL_COLORS = [
  "bg-green-500/20 text-green-400 border-green-500/50",
  "bg-yellow-500/20 text-yellow-300 border-yellow-400/60",
  "bg-orange-500/20 text-orange-300 border-orange-400/80",
  "bg-red-500/20 text-red-400 border-red-500/80",
  "bg-red-600/20 text-red-200 border-red-600/90",
];

const ROW_BG = [
  "",
  "",
  "bg-orange-500/[0.03]",
  "bg-red-500/[0.04]",
  "bg-red-600/[0.06]",
];

export default function AdminTensionPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const { toast } = useAdminToast();
  const levelLabels = lang === "ko" ? LEVEL_LABELS_KO : LEVEL_LABELS_EN;

  const [countrySearch, setCountrySearch] = useState("");

  const { data, isLoading, refetch } = useQuery<TensionRow[]>({
    queryKey: ["admin-tension-all"],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/tension`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Load failed");
      return res.json();
    },
    enabled: !!user,
    refetchInterval: 5 * 60_000,
  });

  const recalcTension = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/tension/recalculate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
    onSuccess: (data) => {
      refetch();
      toast(`${t(lang, "admin_recalc_done")} — ${(data as { countries: number })?.countries ?? 0} ${t(lang, "admin_count_countries")}`, "success");
    },
    onError: () => toast(t(lang, "admin_recalc_fail"), "error"),
  });

  const recalcTrending = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/trending/recalculate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
    onSuccess: (data) => {
      toast(`${t(lang, "admin_recalc_done")} — ${(data as { keywords: number })?.keywords ?? 0} keywords`, "success");
    },
    onError: () => toast(t(lang, "admin_recalc_fail"), "error"),
  });

  const [sortBy, setSortBy] = useState<"score" | "level" | "country">("score");
  const sorted = [...(data ?? [])].sort((a, b) => {
    if (sortBy === "score") return b.raw_score - a.raw_score;
    if (sortBy === "level") return b.tension_level - a.tension_level || b.raw_score - a.raw_score;
    return a.country_code.localeCompare(b.country_code);
  });

  const filtered = sorted.filter((row) => {
    if (!countrySearch) return true;
    const q = countrySearch.toLowerCase();
    return row.country_code.toLowerCase().includes(q) || getCountryName(row.country_code, lang).toLowerCase().includes(q);
  });

  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div>
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_tension")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.length ?? 0} {t(lang, "admin_count_countries")}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => recalcTension.mutate()}
            disabled={recalcTension.isPending}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary transition-colors disabled:opacity-50"
          >
            {recalcTension.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {t(lang, "admin_tension_recalc_all")}
          </button>
          <button
            onClick={() => recalcTrending.mutate()}
            disabled={recalcTrending.isPending}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary transition-colors disabled:opacity-50"
          >
            {recalcTrending.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Activity className="h-4 w-4" />
            )}
            {t(lang, "admin_trending_recalc")}
          </button>
        </div>
      </div>

      {/* Sort + Search */}
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        {([["score", t(lang, "admin_by_score")], ["level", t(lang, "admin_by_level")], ["country", t(lang, "admin_by_country")]] as const).map(
          ([key, label]) => (
            <button
              key={key}
              onClick={() => setSortBy(key)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-xs transition-colors",
                sortBy === key
                  ? "border-primary bg-primary/10 text-primary font-medium"
                  : "border-border text-muted-foreground hover:text-foreground"
              )}
            >
              {label}
            </button>
          )
        )}
        <div className="relative flex-1 min-w-[160px] ml-auto">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={countrySearch}
            onChange={(e) => setCountrySearch(e.target.value)}
            placeholder={t(lang, "admin_search_country")}
            className="w-full rounded-lg border border-border bg-card pl-9 pr-4 py-2 text-sm outline-none focus:border-primary"
          />
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <>
          {/* Desktop skeleton */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 p-3 border-t border-border animate-pulse">
                <div className="h-4 w-8 rounded bg-secondary" />
                <div className="h-4 w-32 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
              </div>
            ))}
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
                <div className="flex justify-between"><div className="h-4 w-32 rounded bg-secondary" /><div className="h-4 w-12 rounded bg-secondary" /></div>
                <div className="flex gap-4"><div className="h-3 w-16 rounded bg-secondary" /><div className="h-3 w-16 rounded bg-secondary" /></div>
                <div className="h-1.5 rounded-full bg-secondary" />
              </div>
            ))}
          </div>
        </>
      ) : !filtered.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <Activity className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">#</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_country")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_tension_raw_score")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_tension_level")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_tension_percentile")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "이벤트" : "Events"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_accel")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_spillover")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_updated_at")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((row, i) => (
                  <tr key={row.country_code} className={cn("hover:bg-secondary/20", ROW_BG[row.tension_level])}>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">{i + 1}</td>
                    <td className="px-3 py-2.5">
                      <span className="text-sm font-medium">
                        {getFlag(row.country_code)} {getCountryName(row.country_code, lang)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="text-sm font-bold tabular-nums">{row.raw_score.toFixed(1)}</span>
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-bold border", LEVEL_COLORS[row.tension_level])}>
                        {levelLabels[row.tension_level]}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-1.5 rounded-full bg-secondary overflow-hidden">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              row.percentile_30d >= 80 ? "bg-red-600" : row.percentile_30d >= 60 ? "bg-red-400" : row.percentile_30d >= 40 ? "bg-amber-400" : row.percentile_30d >= 20 ? "bg-yellow-500" : "bg-green-500"
                            )}
                            style={{ width: `${row.percentile_30d}%` }}
                          />
                        </div>
                        <span className="text-xs tabular-nums text-muted-foreground">{row.percentile_30d.toFixed(0)}%</span>
                      </div>
                    </td>
                    <td className="px-3 py-2.5 text-xs tabular-nums">{row.event_score.toFixed(1)}</td>
                    <td className="px-3 py-2.5 text-xs tabular-nums">{row.accel_score.toFixed(1)}</td>
                    <td className="px-3 py-2.5 text-xs tabular-nums">{row.spillover_score.toFixed(1)}</td>
                    <td className="px-3 py-2.5 text-xs text-muted-foreground">
                      {new Date(row.updated_at).toLocaleString(locale, {
                        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                      })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {filtered.map((row, i) => (
              <div key={row.country_code} className={cn("rounded-xl border border-border bg-card p-4", ROW_BG[row.tension_level])}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{getFlag(row.country_code)} {getCountryName(row.country_code, lang)}</span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-bold border", LEVEL_COLORS[row.tension_level])}>
                      {levelLabels[row.tension_level]}
                    </span>
                  </div>
                  <span className="text-sm font-bold tabular-nums">{row.raw_score.toFixed(1)}</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground mb-2">
                  <div><span className="text-[10px]">{t(lang, "admin_accel")}</span><br/><span className="tabular-nums font-medium text-foreground">{row.accel_score.toFixed(1)}</span></div>
                  <div><span className="text-[10px]">{t(lang, "admin_spillover")}</span><br/><span className="tabular-nums font-medium text-foreground">{row.spillover_score.toFixed(1)}</span></div>
                  <div><span className="text-[10px]">{t(lang, "admin_tension_percentile")}</span><br/><span className="tabular-nums font-medium text-foreground">{row.percentile_30d.toFixed(0)}%</span></div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                    <div className={cn("h-full rounded-full", row.percentile_30d >= 80 ? "bg-red-600" : row.percentile_30d >= 60 ? "bg-red-400" : row.percentile_30d >= 40 ? "bg-amber-400" : row.percentile_30d >= 20 ? "bg-yellow-500" : "bg-green-500")} style={{ width: `${row.percentile_30d}%` }} />
                  </div>
                  <span className="text-[10px] text-muted-foreground tabular-nums">{row.percentile_30d.toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

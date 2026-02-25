"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation } from "@tanstack/react-query";
import { Activity, RefreshCw, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { getCountryName, getFlag } from "@/lib/countries";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

const LEVEL_LABELS_KO = ["안정", "주의", "경계", "위기"];
const LEVEL_LABELS_EN = ["Normal", "Watch", "Alert", "Crisis"];
const LEVEL_COLORS = [
  "bg-green-500/20 text-green-400 border-green-500/50",
  "bg-yellow-500/20 text-yellow-300 border-yellow-400/60",
  "bg-orange-500/20 text-orange-300 border-orange-400/80",
  "bg-red-500/20 text-red-200 border-red-500/90",
];

const ROW_BG = [
  "",
  "",
  "bg-orange-500/[0.03]",
  "bg-red-500/[0.06]",
];

export default function AdminTensionPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const levelLabels = lang === "ko" ? LEVEL_LABELS_KO : LEVEL_LABELS_EN;

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
      if (!res.ok) throw new Error("Recalculate failed");
      return res.json();
    },
    onSuccess: () => refetch(),
  });

  const recalcTrending = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/trending/recalculate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Recalculate failed");
      return res.json();
    },
  });

  const [sortBy, setSortBy] = useState<"score" | "level" | "country">("score");
  const sorted = [...(data ?? [])].sort((a, b) => {
    if (sortBy === "score") return b.raw_score - a.raw_score;
    if (sortBy === "level") return b.tension_level - a.tension_level || b.raw_score - a.raw_score;
    return a.country_code.localeCompare(b.country_code);
  });

  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div>
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_tension")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.length ?? 0} {lang === "ko" ? "개국" : "countries"}
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

      {/* Status messages */}
      {recalcTension.isSuccess && (
        <div className="mb-4 rounded-lg bg-green-500/10 border border-green-500/30 px-4 py-2 text-sm text-green-400">
          {t(lang, "admin_recalc_done")} — {(recalcTension.data as { countries: number })?.countries ?? 0} {lang === "ko" ? "개국" : "countries"}
        </div>
      )}
      {recalcTrending.isSuccess && (
        <div className="mb-4 rounded-lg bg-green-500/10 border border-green-500/30 px-4 py-2 text-sm text-green-400">
          {t(lang, "admin_recalc_done")} — {(recalcTrending.data as { keywords: number })?.keywords ?? 0} {lang === "ko" ? "개 키워드" : "keywords"}
        </div>
      )}

      {/* Sort */}
      <div className="flex gap-2 mb-4">
        {([["score", lang === "ko" ? "점수순" : "By Score"], ["level", lang === "ko" ? "레벨순" : "By Level"], ["country", lang === "ko" ? "국가순" : "By Country"]] as const).map(
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
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !sorted.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <Activity className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <div className="rounded-xl border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-secondary/50">
              <tr>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">#</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_country")}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_tension_raw_score")}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_tension_level")}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_tension_percentile")}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "이벤트" : "Events"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "가속도" : "Accel"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "파급" : "Spillover"}</th>
                <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_updated_at")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {sorted.map((row, i) => (
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
                            row.percentile_30d >= 75 ? "bg-amber-400" : row.percentile_30d >= 50 ? "bg-yellow-500" : "bg-green-500"
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
      )}
    </div>
  );
}

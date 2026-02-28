"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation } from "@tanstack/react-query";
import { TrendingUp, RefreshCw, Loader2, Search, Zap, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { getCountryName, getFlag } from "@/lib/countries";
import { useAdminToast } from "@/components/ui/admin-toast";
import { API_BASE } from "@/lib/admin-utils";

interface TrendingRow {
  id: number;
  keyword: string;
  keyword_ko: string | null;
  kscore: number;
  topic: string | null;
  country_codes: string[];
  event_count: number;
  severity: number;
  is_spike: boolean;
  independent_sources: number;
  confidence: number;
  calculated_at: string;
  is_expired: boolean;
}

const KSCORE_COLORS = [
  "bg-green-500/20 text-green-400 border-green-500/50",    // < 2
  "bg-yellow-500/20 text-yellow-300 border-yellow-400/60",  // 2 ~ 4
  "bg-orange-500/20 text-orange-300 border-orange-400/80",  // 4 ~ 6
  "bg-red-500/20 text-red-400 border-red-500/80",           // 6 ~ 8
  "bg-red-600/20 text-red-200 border-red-600/90",           // >= 8
];

function kscoreColorIdx(k: number): number {
  if (k >= 8) return 4;
  if (k >= 6) return 3;
  if (k >= 4) return 2;
  if (k >= 2) return 1;
  return 0;
}

function kscoreBarColor(k: number): string {
  if (k >= 8) return "bg-red-600";
  if (k >= 6) return "bg-red-500";
  if (k >= 4) return "bg-orange-500";
  if (k >= 2) return "bg-yellow-500";
  return "bg-green-500";
}

const KSCORE_LABELS_KO = ["안정", "주의", "경계", "심각", "극심"];
const KSCORE_LABELS_EN = ["Stable", "Caution", "Alert", "Severe", "Extreme"];

const TOPIC_COLORS: Record<string, string> = {
  military: "bg-red-500/20 text-red-300",
  diplomacy: "bg-blue-500/20 text-blue-300",
  economy: "bg-amber-500/20 text-amber-300",
  politics: "bg-purple-500/20 text-purple-300",
  humanitarian: "bg-emerald-500/20 text-emerald-300",
  security: "bg-orange-500/20 text-orange-300",
  nuclear: "bg-pink-500/20 text-pink-300",
  terrorism: "bg-rose-500/20 text-rose-300",
};

export default function AdminKScorePage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const { toast } = useAdminToast();
  const kscoreLabels = lang === "ko" ? KSCORE_LABELS_KO : KSCORE_LABELS_EN;

  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"kscore" | "severity" | "events">("kscore");
  const [topicFilter, setTopicFilter] = useState<string | null>(null);

  const { data, isLoading, refetch } = useQuery<TrendingRow[]>({
    queryKey: ["admin-trending"],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/trending`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Load failed");
      return res.json();
    },
    enabled: !!user,
    refetchInterval: 5 * 60_000,
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
    onSuccess: (d) => {
      refetch();
      toast(`${t(lang, "admin_recalc_done")} — ${(d as { keywords: number })?.keywords ?? 0} keywords`, "success");
    },
    onError: () => toast(t(lang, "admin_recalc_fail"), "error"),
  });

  // 토픽 목록 추출
  const topics = [...new Set((data ?? []).map((r) => r.topic).filter(Boolean))] as string[];

  // 정렬
  const sorted = [...(data ?? [])].sort((a, b) => {
    if (sortBy === "kscore") return b.kscore - a.kscore;
    if (sortBy === "severity") return b.severity - a.severity || b.kscore - a.kscore;
    return b.event_count - a.event_count || b.kscore - a.kscore;
  });

  // 필터
  const filtered = sorted.filter((row) => {
    if (topicFilter && row.topic !== topicFilter) return false;
    if (!search) return true;
    const q = search.toLowerCase();
    const kw = (row.keyword_ko || row.keyword).toLowerCase();
    const cc = row.country_codes.map((c) => getCountryName(c, lang).toLowerCase()).join(" ");
    return kw.includes(q) || cc.includes(q) || row.keyword.toLowerCase().includes(q);
  });

  // 통계
  const activeCount = (data ?? []).filter((r) => !r.is_expired).length;
  const spikeCount = (data ?? []).filter((r) => r.is_spike).length;
  const avgKscore = data?.length ? (data.reduce((s, r) => s + r.kscore, 0) / data.length) : 0;
  const maxKscore = data?.length ? Math.max(...data.map((r) => r.kscore)) : 0;

  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div>
      {/* 헤더 */}
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_kscore")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.length ?? 0}{lang === "ko" ? "개 트렌딩" : " trending"} · {activeCount}{lang === "ko" ? "개 활성" : " active"}
          </p>
        </div>
        <button
          onClick={() => recalcTrending.mutate()}
          disabled={recalcTrending.isPending}
          className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm hover:bg-secondary transition-colors disabled:opacity-50"
        >
          {recalcTrending.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          {t(lang, "admin_trending_recalc")}
        </button>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[
          { label: lang === "ko" ? "총 트렌딩" : "Total", value: String(data?.length ?? 0), icon: TrendingUp },
          { label: lang === "ko" ? "스파이크" : "Spikes", value: String(spikeCount), icon: Zap },
          { label: lang === "ko" ? "평균 KScore" : "Avg KScore", value: avgKscore.toFixed(2), icon: TrendingUp },
          { label: lang === "ko" ? "최고 KScore" : "Max KScore", value: maxKscore.toFixed(2), icon: AlertTriangle },
        ].map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-xl border border-border bg-card p-3">
            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
              <Icon className="h-3.5 w-3.5" />
              {label}
            </div>
            <p className="text-lg font-bold tabular-nums">{value}</p>
          </div>
        ))}
      </div>

      {/* 정렬 + 토픽 필터 + 검색 */}
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        {([
          ["kscore", "KScore"],
          ["severity", lang === "ko" ? "심각도" : "Severity"],
          ["events", lang === "ko" ? "이벤트수" : "Events"],
        ] as const).map(([key, label]) => (
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
        ))}

        {/* 토픽 필터 */}
        {topics.length > 0 && (
          <select
            value={topicFilter ?? ""}
            onChange={(e) => setTopicFilter(e.target.value || null)}
            className="rounded-lg border border-border bg-card px-2 py-1.5 text-xs outline-none focus:border-primary"
          >
            <option value="">{lang === "ko" ? "모든 토픽" : "All Topics"}</option>
            {topics.map((tp) => (
              <option key={tp} value={tp}>{tp}</option>
            ))}
          </select>
        )}

        <div className="relative flex-1 min-w-[160px] ml-auto">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={lang === "ko" ? "키워드 / 국가 검색..." : "Search keyword / country..."}
            className="w-full rounded-lg border border-border bg-card pl-9 pr-4 py-2 text-sm outline-none focus:border-primary"
          />
        </div>
      </div>

      {/* 콘텐츠 */}
      {isLoading ? (
        <>
          {/* Desktop skeleton */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 p-3 border-t border-border animate-pulse">
                <div className="h-4 w-8 rounded bg-secondary" />
                <div className="h-4 w-40 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
              </div>
            ))}
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
                <div className="flex justify-between"><div className="h-4 w-40 rounded bg-secondary" /><div className="h-4 w-12 rounded bg-secondary" /></div>
                <div className="flex gap-4"><div className="h-3 w-16 rounded bg-secondary" /><div className="h-3 w-16 rounded bg-secondary" /></div>
                <div className="h-1.5 rounded-full bg-secondary" />
              </div>
            ))}
          </div>
        </>
      ) : !filtered.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <TrendingUp className="h-10 w-10 mb-3" />
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
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "키워드" : "Keyword"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">KScore</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "토픽" : "Topic"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_country")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "심각도" : "Severity"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "이벤트" : "Events"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "출처" : "Sources"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_updated_at")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {filtered.map((row, i) => {
                  const idx = kscoreColorIdx(row.kscore);
                  return (
                    <tr key={row.id} className={cn(
                      "hover:bg-secondary/20",
                      row.is_expired && "opacity-50",
                      row.kscore >= 8 && "bg-red-600/[0.06]",
                      row.kscore >= 6 && row.kscore < 8 && "bg-red-500/[0.04]",
                      row.kscore >= 4 && row.kscore < 6 && "bg-orange-500/[0.03]",
                    )}>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">{i + 1}</td>
                      <td className="px-3 py-2.5 max-w-[260px]">
                        <div className="flex items-center gap-2">
                          {row.is_spike && <Zap className="h-3.5 w-3.5 text-amber-400 shrink-0" />}
                          <span className="text-sm font-medium truncate">
                            {lang === "ko" ? (row.keyword_ko || row.keyword) : row.keyword}
                          </span>
                          {row.is_expired && (
                            <span className="text-[9px] text-muted-foreground border border-border rounded px-1">expired</span>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-bold border", KSCORE_COLORS[idx])}>
                            {row.kscore.toFixed(2)}
                          </span>
                          <div className="w-12 h-1.5 rounded-full bg-secondary overflow-hidden">
                            <div
                              className={cn("h-full rounded-full", kscoreBarColor(row.kscore))}
                              style={{ width: `${Math.min(100, (row.kscore / 5) * 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2.5">
                        {row.topic && (
                          <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", TOPIC_COLORS[row.topic] || "bg-secondary text-foreground")}>
                            {row.topic}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-xs">
                        {row.country_codes.slice(0, 3).map((cc) => (
                          <span key={cc} className="mr-1">{getFlag(cc)}</span>
                        ))}
                        {row.country_codes.length > 3 && (
                          <span className="text-muted-foreground">+{row.country_codes.length - 3}</span>
                        )}
                      </td>
                      <td className="px-3 py-2.5 text-xs tabular-nums">{row.severity}</td>
                      <td className="px-3 py-2.5 text-xs tabular-nums">{row.event_count}</td>
                      <td className="px-3 py-2.5 text-xs tabular-nums">{row.independent_sources}</td>
                      <td className="px-3 py-2.5 text-xs text-muted-foreground">
                        {new Date(row.calculated_at).toLocaleString(locale, {
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
            {filtered.map((row, i) => {
              const idx = kscoreColorIdx(row.kscore);
              return (
                <div key={row.id} className={cn(
                  "rounded-xl border border-border bg-card p-4",
                  row.is_expired && "opacity-50",
                  row.kscore >= 6 && "bg-red-500/[0.06]",
                  row.kscore >= 4 && row.kscore < 6 && "bg-orange-500/[0.03]",
                )}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      {row.is_spike && <Zap className="h-3.5 w-3.5 text-amber-400 shrink-0" />}
                      <span className="text-sm font-medium truncate">
                        {lang === "ko" ? (row.keyword_ko || row.keyword) : row.keyword}
                      </span>
                    </div>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-bold border shrink-0 ml-2", KSCORE_COLORS[idx])}>
                      {row.kscore.toFixed(2)} {kscoreLabels[idx]}
                    </span>
                  </div>

                  <div className="flex items-center gap-2 mb-2">
                    {row.topic && (
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", TOPIC_COLORS[row.topic] || "bg-secondary text-foreground")}>
                        {row.topic}
                      </span>
                    )}
                    <span className="text-xs text-muted-foreground">
                      {row.country_codes.slice(0, 3).map((cc) => getFlag(cc)).join(" ")}
                    </span>
                    {row.is_expired && (
                      <span className="text-[9px] text-muted-foreground border border-border rounded px-1">expired</span>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-2 text-xs text-muted-foreground mb-2">
                    <div>
                      <span className="text-[10px]">{lang === "ko" ? "심각도" : "Severity"}</span><br />
                      <span className="tabular-nums font-medium text-foreground">{row.severity}</span>
                    </div>
                    <div>
                      <span className="text-[10px]">{lang === "ko" ? "이벤트" : "Events"}</span><br />
                      <span className="tabular-nums font-medium text-foreground">{row.event_count}</span>
                    </div>
                    <div>
                      <span className="text-[10px]">{lang === "ko" ? "출처" : "Sources"}</span><br />
                      <span className="tabular-nums font-medium text-foreground">{row.independent_sources}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-secondary overflow-hidden">
                      <div
                        className={cn("h-full rounded-full", kscoreBarColor(row.kscore))}
                        style={{ width: `${Math.min(100, (row.kscore / 5) * 100)}%` }}
                      />
                    </div>
                    <span className="text-[10px] text-muted-foreground tabular-nums">{row.kscore.toFixed(2)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { t, type Lang } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Radio } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminToast } from "@/components/ui/admin-toast";
import { useAdminStore, API_BASE } from "@/lib/admin-utils";

interface CollectStatus {
  status: "ok" | "error";
  collected: number;
  skipped: number;
  error: string;
  last_collected_at: string;
}

interface SourceItem {
  id: number;
  channel_id: number | null;
  username: string | null;
  display_name: string;
  source_type: string;
  tier: string;
  base_confidence: number;
  language: string | null;
  feed_url: string | null;
  api_endpoint: string | null;
  topics: string[];
  geo_focus: string[];
  is_active: boolean;
  created_at: string;
  collect_status: CollectStatus | null;
}

const TIER_COLORS: Record<string, string> = {
  A: "bg-green-500/20 text-green-400",
  B: "bg-blue-500/20 text-blue-400",
  C: "bg-yellow-500/20 text-yellow-400",
  D: "bg-red-500/20 text-red-400",
};

const TYPE_COLORS: Record<string, string> = {
  rss: "bg-orange-500/20 text-orange-400",
  telegram: "bg-blue-500/20 text-blue-400",
  api: "bg-purple-500/20 text-purple-400",
};

// 소스 카테고리 자동 판별
function getCategory(ch: SourceItem): string {
  if (ch.source_type === "api") return "api";
  if (ch.source_type === "telegram") return "osint";
  // RSS 세분화
  const name = ch.display_name.toLowerCase();
  const govKeywords = ["state dept", "fcdo", "un security", "un news", "government"];
  if (govKeywords.some(k => name.includes(k))) return "gov";
  const thinkKeywords = ["crisis group", "icg", "iiss", "carnegie", "bellingcat", "foreign policy"];
  if (thinkKeywords.some(k => name.includes(k))) return "think";
  const wireKeywords = ["reuters", "ap news", "afp", "anadolu", "tass", "efe", "nhk"];
  if (wireKeywords.some(k => name.includes(k))) return "wire";
  const regionalKeywords = ["dawn", "daily sabah", "moscow times", "irrawaddy", "ethiopia insight",
    "caucasus", "libya observer", "sudan tribune", "kurdistan", "sana", "syria direct",
    "jerusalem post", "iran international", "meduza", "global voices"];
  if (regionalKeywords.some(k => name.includes(k))) return "regional";
  return "news";
}

const CAT_COLORS: Record<string, string> = {
  news: "bg-slate-500/20 text-slate-400",
  gov: "bg-emerald-500/20 text-emerald-400",
  think: "bg-indigo-500/20 text-indigo-400",
  regional: "bg-amber-500/20 text-amber-400",
  wire: "bg-cyan-500/20 text-cyan-400",
  osint: "bg-rose-500/20 text-rose-400",
  api: "bg-purple-500/20 text-purple-400",
};

function catLabel(lang: Lang, cat: string): string {
  const key = `admin_source_cat_${cat}` as Parameters<typeof t>[1];
  return t(lang, key) || cat.toUpperCase();
}

function StatusDot({ status }: { status: CollectStatus | null }) {
  if (!status) return <span className="text-gray-500" title="Idle">&#9679;</span>;
  if (status.status === "ok") return <span className="text-green-400" title="OK">&#9679;</span>;
  return <span className="text-red-400" title="Error">&#9679;</span>;
}

// 비활성 사유 추정
function getInactiveReason(ch: SourceItem, lang: Lang): string {
  if (ch.is_active) return "";
  const cs = ch.collect_status;
  if (ch.source_type === "api" && ch.display_name === "ACLED") {
    return t(lang, "admin_source_reason_no_access");
  }
  if (cs?.error) {
    if (cs.error.includes("404") || cs.error.includes("410") || cs.error.includes("비활성화")) {
      return t(lang, "admin_source_reason_feed_error");
    }
    if (cs.error.includes("연속") || cs.error.includes("consecutive")) {
      return t(lang, "admin_source_reason_consecutive");
    }
  }
  return t(lang, "admin_source_reason_manual");
}

export default function AdminSourcesPage() {
  const { user } = useAuth();
  const { lang } = useAdminStore();
  const queryClient = useQueryClient();
  const { toast } = useAdminToast();
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [tierFilter, setTierFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState<string>("");

  const { data, isLoading } = useQuery<{ total: number; active_count: number; inactive_count: number; items: SourceItem[] }>({
    queryKey: ["admin-sources", page, typeFilter, tierFilter, activeFilter],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "20" });
      if (typeFilter) params.append("source_type", typeFilter);
      if (tierFilter) params.append("tier", tierFilter);
      if (activeFilter) params.append("is_active", activeFilter);
      const res = await fetch(`${API_BASE}/admin/sources?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Load failed");
      return res.json();
    },
    enabled: !!user,
  });

  const patchMutation = useMutation({
    mutationFn: async ({ id, body }: { id: number; body: Record<string, unknown> }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/sources/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("Update failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-sources"] });
      toast(t(lang, "admin_toast_updated"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  const totalPages = Math.ceil((data?.total ?? 0) / 20);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  // 요약 통계 (전체 기준, 백엔드에서 계산)
  const activeCount = data?.active_count ?? 0;
  const inactiveCount = data?.inactive_count ?? 0;

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{t(lang, "admin_sources_title")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t(lang, "admin_sources_subtitle")}</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div className="rounded-xl border border-border bg-card p-3 text-center">
          <p className="text-2xl font-bold">{activeCount + inactiveCount}</p>
          <p className="text-xs text-muted-foreground">{lang === "ko" ? "전체 소스" : "Total"}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-3 text-center">
          <p className="text-2xl font-bold text-green-400">{activeCount}</p>
          <p className="text-xs text-muted-foreground">{t(lang, "admin_source_active_count")}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-3 text-center">
          <p className="text-2xl font-bold text-red-400">{inactiveCount}</p>
          <p className="text-xs text-muted-foreground">{t(lang, "admin_source_inactive_count")}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-3 text-center">
          <p className="text-2xl font-bold text-blue-400">
            {data?.items.filter(i => i.collect_status?.status === "error").length ?? 0}
          </p>
          <p className="text-xs text-muted-foreground">{t(lang, "admin_source_status_error")}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={typeFilter}
          onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_source_all_types")}</option>
          <option value="rss">RSS</option>
          <option value="telegram">Telegram</option>
          <option value="api">API</option>
        </select>
        <select
          value={tierFilter}
          onChange={(e) => { setTierFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_source_all_tiers")}</option>
          {["A", "B", "C", "D"].map((tier) => (
            <option key={tier} value={tier}>{tier}</option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) => { setActiveFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none"
        >
          <option value="">{t(lang, "admin_all")}</option>
          <option value="true">{t(lang, "admin_active")}</option>
          <option value="false">{t(lang, "admin_inactive")}</option>
        </select>
        <span className="flex items-center text-xs text-muted-foreground ml-auto">
          {data?.total ?? 0} {lang === "ko" ? "개 채널" : "channels"}
        </span>
      </div>

      {/* Content */}
      {isLoading ? (
        <>
          {/* Desktop skeleton */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {[...Array(5)].map((_, i) => (
              <div key={i} className="flex gap-4 p-3 border-t border-border animate-pulse">
                <div className="h-4 w-6 rounded bg-secondary" />
                <div className="h-4 w-36 rounded bg-secondary" />
                <div className="h-4 w-16 rounded bg-secondary" />
                <div className="h-4 w-8 rounded bg-secondary" />
                <div className="h-4 w-8 rounded bg-secondary" />
                <div className="h-4 w-12 rounded bg-secondary" />
              </div>
            ))}
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
                <div className="flex justify-between"><div className="h-4 w-36 rounded bg-secondary" /><div className="h-5 w-9 rounded-full bg-secondary" /></div>
                <div className="flex gap-2"><div className="h-5 w-16 rounded bg-secondary" /><div className="h-5 w-8 rounded bg-secondary" /></div>
                <div className="h-3 w-24 rounded bg-secondary" />
              </div>
            ))}
          </div>
        </>
      ) : !data?.items.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <Radio className="h-10 w-10 mb-3" />
          <p className="text-sm">{t(lang, "admin_no_data")}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_status")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_name")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_type")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_category")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_tier")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_language")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_confidence")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_topics")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_last_collected")}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{t(lang, "admin_source_error")}</th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">{t(lang, "admin_source_active_toggle")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((ch) => {
                  const cs = ch.collect_status;
                  const cat = getCategory(ch);
                  const inactiveReason = getInactiveReason(ch, lang);
                  return (
                    <tr key={ch.id} className={cn("hover:bg-secondary/20", !ch.is_active && "opacity-50")}>
                      {/* 상태 dot */}
                      <td className="px-3 py-3 text-center text-sm">
                        <StatusDot status={ch.is_active ? cs : null} />
                      </td>
                      {/* 채널명 */}
                      <td className="px-3 py-3 max-w-[220px]">
                        <p className="text-sm font-medium truncate">{ch.display_name}</p>
                        <p className="text-[10px] text-muted-foreground truncate">
                          {ch.source_type === "telegram"
                            ? `@${ch.username}`
                            : ch.source_type === "api"
                              ? ch.api_endpoint
                              : ch.feed_url}
                        </p>
                        {!ch.is_active && inactiveReason && (
                          <p className="text-[10px] text-red-400 mt-0.5">{inactiveReason}</p>
                        )}
                      </td>
                      {/* 유형 */}
                      <td className="px-3 py-3">
                        <span className={cn(
                          "text-xs rounded-full px-2 py-0.5 font-medium",
                          TYPE_COLORS[ch.source_type] ?? "bg-gray-500/20 text-gray-400"
                        )}>
                          {ch.source_type}
                        </span>
                      </td>
                      {/* 분류 */}
                      <td className="px-3 py-3">
                        <span className={cn(
                          "text-[10px] rounded-full px-2 py-0.5 font-medium",
                          CAT_COLORS[cat] ?? ""
                        )}>
                          {catLabel(lang, cat)}
                        </span>
                      </td>
                      {/* 등급 (드롭다운) */}
                      <td className="px-3 py-3">
                        <select
                          value={ch.tier}
                          onChange={(e) => patchMutation.mutate({ id: ch.id, body: { tier: e.target.value } })}
                          className={cn("rounded px-2 py-0.5 text-xs font-medium border-0 outline-none cursor-pointer", TIER_COLORS[ch.tier] ?? "")}
                        >
                          {["A", "B", "C", "D"].map((tier) => (
                            <option key={tier} value={tier}>{tier}</option>
                          ))}
                        </select>
                      </td>
                      {/* 언어 */}
                      <td className="px-3 py-3 text-xs text-muted-foreground">{ch.language ?? "—"}</td>
                      {/* 신뢰도 (인라인 편집) */}
                      <td className="px-3 py-3">
                        <input
                          type="number"
                          min={0}
                          max={1}
                          step={0.05}
                          value={ch.base_confidence}
                          onChange={(e) => {
                            const val = parseFloat(e.target.value);
                            if (!isNaN(val) && val >= 0 && val <= 1) {
                              patchMutation.mutate({ id: ch.id, body: { base_confidence: val } });
                            }
                          }}
                          className="w-16 rounded border border-border bg-background px-2 py-0.5 text-xs tabular-nums outline-none focus:border-primary"
                        />
                      </td>
                      {/* 주제 */}
                      <td className="px-3 py-3 max-w-[140px]">
                        <div className="flex flex-wrap gap-0.5">
                          {(ch.topics || []).slice(0, 3).map((topic) => (
                            <span key={topic} className="text-[9px] rounded bg-secondary px-1.5 py-0.5 text-muted-foreground">
                              {topic}
                            </span>
                          ))}
                          {(ch.topics || []).length > 3 && (
                            <span className="text-[9px] text-muted-foreground">+{ch.topics.length - 3}</span>
                          )}
                        </div>
                        {ch.geo_focus?.length > 0 && (
                          <div className="flex flex-wrap gap-0.5 mt-0.5">
                            {ch.geo_focus.slice(0, 3).map((geo) => (
                              <span key={geo} className="text-[9px] rounded bg-blue-500/10 px-1.5 py-0.5 text-blue-400">
                                {geo}
                              </span>
                            ))}
                            {ch.geo_focus.length > 3 && (
                              <span className="text-[9px] text-blue-400">+{ch.geo_focus.length - 3}</span>
                            )}
                          </div>
                        )}
                      </td>
                      {/* 최근 수집 */}
                      <td className="px-3 py-3 text-xs text-muted-foreground">
                        {cs?.last_collected_at
                          ? new Date(cs.last_collected_at).toLocaleString(locale, {
                              month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                            })
                          : "—"
                        }
                        {cs && cs.status === "ok" && (
                          <span className="ml-1 text-green-400 text-[10px]">({cs.collected}/{cs.skipped})</span>
                        )}
                      </td>
                      {/* 오류 */}
                      <td className="px-3 py-3 max-w-[150px]">
                        {cs?.error ? (
                          <p className="text-[10px] text-red-400 truncate" title={cs.error}>{cs.error}</p>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </td>
                      {/* 활성 토글 */}
                      <td className="px-3 py-3 text-right">
                        <button
                          onClick={() => patchMutation.mutate({ id: ch.id, body: { is_active: !ch.is_active } })}
                          className={cn(
                            "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                            ch.is_active ? "bg-primary" : "bg-secondary"
                          )}
                        >
                          <span
                            className={cn(
                              "inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform",
                              ch.is_active ? "translate-x-[18px]" : "translate-x-[3px]"
                            )}
                          />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile card layout */}
          <div className="md:hidden space-y-3">
            {data.items.map((ch) => {
              const cs = ch.collect_status;
              const cat = getCategory(ch);
              const inactiveReason = getInactiveReason(ch, lang);
              return (
                <div key={ch.id} className={cn("rounded-xl border border-border bg-card p-4", !ch.is_active && "opacity-50")}>
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <StatusDot status={ch.is_active ? cs : null} />
                        <p className="text-sm font-medium truncate">{ch.display_name}</p>
                      </div>
                      <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                        {ch.source_type === "telegram"
                          ? `@${ch.username}`
                          : ch.source_type === "api"
                            ? ch.api_endpoint
                            : ch.feed_url}
                      </p>
                      {!ch.is_active && inactiveReason && (
                        <p className="text-[10px] text-red-400 mt-0.5">{inactiveReason}</p>
                      )}
                    </div>
                    <button
                      onClick={() => patchMutation.mutate({ id: ch.id, body: { is_active: !ch.is_active } })}
                      className={cn("relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0", ch.is_active ? "bg-primary" : "bg-secondary")}
                    >
                      <span className={cn("inline-block h-3.5 w-3.5 rounded-full bg-white transition-transform", ch.is_active ? "translate-x-[18px]" : "translate-x-[3px]")} />
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2 mb-2">
                    <span className={cn("text-xs rounded-full px-2 py-0.5 font-medium", TYPE_COLORS[ch.source_type] ?? "bg-gray-500/20 text-gray-400")}>{ch.source_type}</span>
                    <span className={cn("text-[10px] rounded-full px-2 py-0.5 font-medium", CAT_COLORS[cat] ?? "")}>{catLabel(lang, cat)}</span>
                    <select
                      value={ch.tier}
                      onChange={(e) => patchMutation.mutate({ id: ch.id, body: { tier: e.target.value } })}
                      className={cn("rounded px-2 py-0.5 text-xs font-medium border-0 outline-none cursor-pointer", TIER_COLORS[ch.tier] ?? "")}
                    >
                      {["A","B","C","D"].map((tier) => (<option key={tier} value={tier}>{tier}</option>))}
                    </select>
                    <span className="text-xs text-muted-foreground">{ch.language ?? "—"}</span>
                  </div>
                  {/* Topics & Geo */}
                  {((ch.topics?.length ?? 0) > 0 || (ch.geo_focus?.length ?? 0) > 0) && (
                    <div className="flex flex-wrap gap-1 mb-2">
                      {(ch.topics || []).slice(0, 4).map((topic) => (
                        <span key={topic} className="text-[9px] rounded bg-secondary px-1.5 py-0.5 text-muted-foreground">{topic}</span>
                      ))}
                      {(ch.geo_focus || []).slice(0, 3).map((geo) => (
                        <span key={geo} className="text-[9px] rounded bg-blue-500/10 px-1.5 py-0.5 text-blue-400">{geo}</span>
                      ))}
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-muted-foreground">{t(lang, "admin_confidence")}</span>
                      <input
                        type="number"
                        min={0} max={1} step={0.05}
                        value={ch.base_confidence}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          if (!isNaN(val) && val >= 0 && val <= 1) patchMutation.mutate({ id: ch.id, body: { base_confidence: val } });
                        }}
                        className="mt-0.5 w-full rounded border border-border bg-background px-2 py-0.5 text-xs tabular-nums outline-none focus:border-primary"
                      />
                    </div>
                    <div>
                      <span className="text-muted-foreground">{t(lang, "admin_source_last_collected")}</span>
                      <p className="mt-0.5 tabular-nums">
                        {cs?.last_collected_at ? new Date(cs.last_collected_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                      </p>
                    </div>
                  </div>
                  {cs?.error && <p className="mt-2 text-[10px] text-red-400 truncate">{cs.error}</p>}
                </div>
              );
            })}
          </div>
        </>
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

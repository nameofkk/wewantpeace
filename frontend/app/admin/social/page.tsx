"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { API_BASE } from "@/lib/admin-utils";
import {
  Share2, Search, ChevronLeft, ChevronRight, HelpCircle,
  ChevronDown, X, CheckCircle, XCircle, RefreshCw, Eye,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface PlatformInfo {
  platform: string;
  status: string;
  platform_post_id: string | null;
  error_message: string | null;
  published_at: string | null;
}

interface SocialPostItem {
  id: string;
  content_type: string;
  lang: string;
  body_text: string;
  hashtags: string[];
  image_url: string | null;
  risk_level: string;
  source_cluster_id: string | null;
  source_spike_id: string | null;
  dedup_key: string;
  status: string;
  created_at: string;
  approved_at: string | null;
  approved_by: string | null;
  published_at: string | null;
  platforms: PlatformInfo[];
}

interface SocialResponse {
  items: SocialPostItem[];
  total: number;
}

interface SocialStats {
  pending: number;
  published_today: number;
  published_week: number;
  failed: number;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const STATUS_TABS = ["all", "pending_review", "approved", "published", "rejected", "failed"] as const;

const STATUS_COLORS: Record<string, string> = {
  pending_review: "bg-yellow-500/20 text-yellow-400",
  approved: "bg-blue-500/20 text-blue-400",
  published: "bg-green-500/20 text-green-400",
  rejected: "bg-red-500/20 text-red-400",
  failed: "bg-orange-500/20 text-orange-400",
};

const STATUS_LABELS: Record<string, { ko: string; en: string }> = {
  pending_review: { ko: "대기", en: "Pending" },
  approved: { ko: "승인", en: "Approved" },
  published: { ko: "발행", en: "Published" },
  rejected: { ko: "거절", en: "Rejected" },
  failed: { ko: "실패", en: "Failed" },
};

const RISK_COLORS: Record<string, string> = {
  low: "bg-green-500/20 text-green-400",
  medium: "bg-yellow-500/20 text-yellow-400",
  high: "bg-red-500/20 text-red-400",
};

const CONTENT_TYPE_LABELS: Record<string, { ko: string; en: string }> = {
  daily_movers: { ko: "Daily Movers", en: "Daily Movers" },
  spike_alert: { ko: "Spike Alert", en: "Spike Alert" },
  weekly_recap: { ko: "Weekly Recap", en: "Weekly Recap" },
};

const PLATFORM_ICONS: Record<string, string> = {
  x: "𝕏",
  threads: "🧵",
  instagram: "📷",
};

/* ------------------------------------------------------------------ */
/*  Inline Guide                                                       */
/* ------------------------------------------------------------------ */
function InlineGuide({ lang }: { lang: Lang }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-4 rounded-xl border border-border/50 bg-card/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <span className="flex items-center gap-1.5">
          <HelpCircle className="h-3.5 w-3.5" />
          {t(lang, "admin_social")}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-border/50 px-4 py-3 text-xs text-muted-foreground space-y-1">
          <p>{t(lang, "admin_social_guide")}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Detail Modal                                                       */
/* ------------------------------------------------------------------ */
function DetailModal({
  post,
  lang,
  onClose,
}: {
  post: SocialPostItem;
  lang: Lang;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">{CONTENT_TYPE_LABELS[post.content_type]?.[lang] || post.content_type}</h3>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <p className="text-xs text-muted-foreground mb-1">{t(lang, "admin_social_body")}</p>
            <p className="text-sm whitespace-pre-wrap">{post.body_text}</p>
          </div>

          {post.hashtags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {post.hashtags.map((h, i) => (
                <span key={i} className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">{h}</span>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">{t(lang, "admin_status")}:</span>{" "}
              <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[post.status])}>
                {STATUS_LABELS[post.status]?.[lang] || post.status}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">{t(lang, "admin_social_risk")}:</span>{" "}
              <span className={cn("px-1.5 py-0.5 rounded text-[10px]", RISK_COLORS[post.risk_level])}>
                {post.risk_level}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">{t(lang, "admin_created_at")}:</span>{" "}
              {new Date(post.created_at).toLocaleString(lang === "en" ? "en-US" : "ko-KR")}
            </div>
            {post.approved_by && (
              <div>
                <span className="text-muted-foreground">Approved by:</span> {post.approved_by}
              </div>
            )}
          </div>

          {post.platforms.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">{t(lang, "admin_social_platform")}</p>
              <div className="space-y-1">
                {post.platforms.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span>{PLATFORM_ICONS[p.platform] || p.platform}</span>
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[p.status] || "bg-gray-500/20 text-gray-400")}>
                      {p.status}
                    </span>
                    {p.error_message && (
                      <span className="text-red-400 truncate max-w-[200px]">{p.error_message}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function AdminSocialPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const qc = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [contentTypeFilter, setContentTypeFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selectedPost, setSelectedPost] = useState<SocialPostItem | null>(null);

  const fetchWithToken = async <T,>(path: string, opts?: { method?: string; body?: unknown }): Promise<T> => {
    const token = await user?.getIdToken();
    if (!token) throw new Error("No token");
    const res = await fetch(`${API_BASE}${path}`, {
      method: opts?.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      ...(opts?.body ? { body: JSON.stringify(opts.body) } : {}),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  };

  // Stats
  const { data: stats } = useQuery<SocialStats>({
    queryKey: ["social-stats"],
    queryFn: () => fetchWithToken("/admin/social/stats"),
    refetchInterval: 30_000,
  });

  // List
  const params = new URLSearchParams();
  params.set("page", String(page));
  if (statusFilter !== "all") params.set("status", statusFilter);
  if (contentTypeFilter) params.set("content_type", contentTypeFilter);
  if (search) params.set("q", search);

  const { data, isLoading } = useQuery<SocialResponse>({
    queryKey: ["social-posts", page, statusFilter, contentTypeFilter, search],
    queryFn: () => fetchWithToken(`/admin/social?${params.toString()}`),
    refetchInterval: 15_000,
  });

  const perPage = 20;
  const totalPages = Math.ceil((data?.total || 0) / perPage);

  // Mutations
  const approveMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/approve`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });
  const rejectMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/reject`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });
  const retryMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/retry`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Share2 className="h-5 w-5 text-primary" />
        <h1 className="text-lg font-bold">{t(lang, "admin_social")}</h1>
      </div>

      <InlineGuide lang={lang} />

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_pending")}</p>
            <p className="text-xl font-bold text-yellow-400">{stats.pending}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_today")}</p>
            <p className="text-xl font-bold text-green-400">{stats.published_today}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_week")}</p>
            <p className="text-xl font-bold text-blue-400">{stats.published_week}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_failed")}</p>
            <p className="text-xl font-bold text-orange-400">{stats.failed}</p>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Status tabs */}
        <div className="flex gap-1 overflow-x-auto">
          {STATUS_TABS.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); }}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs whitespace-nowrap transition-colors",
                statusFilter === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              {s === "all"
                ? t(lang, "admin_all")
                : STATUS_LABELS[s]?.[lang] || s}
            </button>
          ))}
        </div>

        {/* Content type dropdown */}
        <select
          value={contentTypeFilter}
          onChange={(e) => { setContentTypeFilter(e.target.value); setPage(1); }}
          className="px-2 py-1.5 rounded-lg bg-secondary text-xs border-none"
        >
          <option value="">{t(lang, "admin_all")}</option>
          <option value="daily_movers">Daily Movers</option>
          <option value="spike_alert">Spike Alert</option>
          <option value="weekly_recap">Weekly Recap</option>
        </select>

        {/* Search */}
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder={t(lang, "admin_search")}
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-secondary text-xs border-none placeholder:text-muted-foreground/50"
          />
        </div>
      </div>

      {/* Table (desktop) / Cards (mobile) */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-5 w-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : !data?.items.length ? (
        <p className="text-center text-sm text-muted-foreground py-12">{t(lang, "admin_no_data")}</p>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-card/50">
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">Type</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">Lang</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground max-w-[300px]">{t(lang, "admin_social_body")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_status")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_social_risk")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_social_platform")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_created_at")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_actions")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((post) => (
                  <tr key={post.id} className="border-b border-border/50 hover:bg-card/30">
                    <td className="px-3 py-2">
                      <span className="text-[10px] font-medium">
                        {CONTENT_TYPE_LABELS[post.content_type]?.[lang] || post.content_type}
                      </span>
                    </td>
                    <td className="px-3 py-2 uppercase">{post.lang}</td>
                    <td className="px-3 py-2 max-w-[300px] truncate">{post.body_text}</td>
                    <td className="px-3 py-2">
                      <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[post.status])}>
                        {STATUS_LABELS[post.status]?.[lang] || post.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className={cn("px-1.5 py-0.5 rounded text-[10px]", RISK_COLORS[post.risk_level])}>
                        {post.risk_level}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-1">
                        {post.platforms.map((p, i) => (
                          <span key={i} title={`${p.platform}: ${p.status}`} className="text-sm">
                            {PLATFORM_ICONS[p.platform] || p.platform}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {new Date(post.created_at).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR")}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setSelectedPost(post)}
                          className="p-1 text-muted-foreground hover:text-foreground"
                          title="View"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        {post.status === "pending_review" && (
                          <>
                            <button
                              onClick={() => approveMut.mutate(post.id)}
                              className="p-1 text-green-400 hover:text-green-300"
                              title={t(lang, "admin_social_approve")}
                            >
                              <CheckCircle className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => rejectMut.mutate(post.id)}
                              className="p-1 text-red-400 hover:text-red-300"
                              title={t(lang, "admin_social_reject")}
                            >
                              <XCircle className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                        {post.status === "failed" && (
                          <button
                            onClick={() => retryMut.mutate(post.id)}
                            className="p-1 text-orange-400 hover:text-orange-300"
                            title={t(lang, "admin_social_retry")}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {data.items.map((post) => (
              <div
                key={post.id}
                onClick={() => setSelectedPost(post)}
                className="rounded-xl border border-border bg-card p-3 space-y-2 cursor-pointer active:bg-card/80"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-medium">
                    {CONTENT_TYPE_LABELS[post.content_type]?.[lang] || post.content_type}
                  </span>
                  <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[post.status])}>
                    {STATUS_LABELS[post.status]?.[lang] || post.status}
                  </span>
                </div>
                <p className="text-xs line-clamp-2">{post.body_text}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px]", RISK_COLORS[post.risk_level])}>
                      {post.risk_level}
                    </span>
                    {post.platforms.map((p, i) => (
                      <span key={i} className="text-xs">{PLATFORM_ICONS[p.platform] || p.platform}</span>
                    ))}
                  </div>
                  <div className="flex items-center gap-1">
                    {post.status === "pending_review" && (
                      <>
                        <button
                          onClick={(e) => { e.stopPropagation(); approveMut.mutate(post.id); }}
                          className="p-1 text-green-400"
                        >
                          <CheckCircle className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); rejectMut.mutate(post.id); }}
                          className="p-1 text-red-400"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                      </>
                    )}
                    {post.status === "failed" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); retryMut.mutate(post.id); }}
                        className="p-1 text-orange-400"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="p-1.5 rounded-lg border border-border disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-xs text-muted-foreground">
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="p-1.5 rounded-lg border border-border disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}

      {/* Detail Modal */}
      {selectedPost && (
        <DetailModal post={selectedPost} lang={lang} onClose={() => setSelectedPost(null)} />
      )}
    </div>
  );
}

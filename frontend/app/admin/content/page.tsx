"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Search, Loader2, MessageSquare, Eye, EyeOff, ExternalLink,
  Flag, CheckCircle, X, ChevronLeft, ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminToast } from "@/components/ui/admin-toast";
import { API_BASE } from "@/lib/admin-utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface PostItem {
  id: string;
  title: string;
  post_type: string;
  status: string;
  views: number;
  likes: number;
  comment_count: number;
  report_count?: number;
  author_nickname: string | null;
  created_at: string;
}

interface Report {
  id: number;
  reporter_nickname: string | null;
  target_type: "post" | "comment" | "user";
  target_id: string;
  reason: string;
  status: "pending" | "resolved" | "dismissed";
  created_at: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const TYPE_COLORS: Record<string, string> = {
  discussion: "bg-blue-500/20 text-blue-400",
  question: "bg-purple-500/20 text-purple-400",
  analysis: "bg-green-500/20 text-green-400",
};

const POST_STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  hidden: "bg-yellow-500/20 text-yellow-400",
  deleted: "bg-red-500/20 text-red-400",
};

const REPORT_STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  resolved: "bg-green-500/20 text-green-400",
  dismissed: "bg-secondary text-muted-foreground",
};

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function AdminContentPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const queryClient = useQueryClient();
  const { toast } = useAdminToast();

  const [tab, setTab] = useState<"posts" | "reports">("posts");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [reportStatusFilter, setReportStatusFilter] = useState<"pending" | "all">("pending");

  const locale = lang === "en" ? "en-US" : "ko-KR";

  /* ---- Posts Query ---- */
  const { data: postsData, isLoading: postsLoading } = useQuery<{ items: PostItem[]; total: number }>({
    queryKey: ["admin-posts", page, statusFilter, search],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page), limit: "20" });
      if (statusFilter) params.append("status", statusFilter);
      if (search) params.append("search", search);
      const res = await fetch(`${API_BASE}/admin/posts?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load posts");
      return res.json();
    },
    enabled: !!user && tab === "posts",
  });

  /* ---- Reports Query ---- */
  const { data: reports = [], isLoading: reportsLoading } = useQuery<Report[]>({
    queryKey: ["admin-reports", reportStatusFilter],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const params = new URLSearchParams({ limit: "50" });
      if (reportStatusFilter !== "all") params.append("status", reportStatusFilter);
      const res = await fetch(`${API_BASE}/admin/reports?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load reports");
      return res.json();
    },
    enabled: !!user && tab === "reports",
  });

  /* ---- Pending report count for badge ---- */
  const { data: pendingReports } = useQuery<Report[]>({
    queryKey: ["admin-reports", "pending"],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/reports?status=pending&limit=100`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return [];
      return res.json();
    },
    enabled: !!user,
  });

  const pendingCount = pendingReports?.length ?? 0;

  /* ---- Mutations ---- */
  const hideMutation = useMutation({
    mutationFn: async ({ postId, hide }: { postId: string; hide: boolean }) => {
      const token = await user!.getIdToken();
      const res = await fetch(`${API_BASE}/admin/posts/${postId}/hide`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ hide }),
      });
      if (!res.ok) throw new Error("Failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-posts"] });
      toast(t(lang, "admin_toast_updated"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  const reviewMutation = useMutation({
    mutationFn: async ({ reportId, action }: { reportId: number; action: "resolve" | "dismiss" }) => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const status = action === "resolve" ? "resolved" : "dismissed";
      const res = await fetch(`${API_BASE}/admin/reports/${reportId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status }),
      });
      if (!res.ok) throw new Error("Failed to update report");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-reports"] });
      toast(t(lang, "admin_toast_updated"), "success");
    },
    onError: () => toast(t(lang, "admin_toast_error"), "error"),
  });

  /* ---- Helpers ---- */
  const getTargetLabel = (type: string) => {
    const map: Record<string, string> = {
      post: t(lang, "admin_report_target_post"),
      comment: t(lang, "admin_report_target_comment"),
      user: t(lang, "admin_report_target_user"),
    };
    return map[type] ?? type;
  };

  const getStatusLabel = (status: string) => {
    if (status === "pending") return t(lang, "admin_report_pending");
    if (status === "resolved") return t(lang, "admin_report_resolved");
    return t(lang, "admin_report_dismissed");
  };

  const postItems = postsData?.items ?? [];
  const postTotal = postsData?.total ?? 0;
  const totalPages = Math.ceil(postTotal / 20);

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">{t(lang, "admin_content_moderation")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? "게시글 관리 및 신고 처리" : "Manage posts and handle reports"}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-border">
        <button
          onClick={() => setTab("posts")}
          className={cn(
            "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
            tab === "posts" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <MessageSquare className="h-3.5 w-3.5" />
          {t(lang, "admin_posts")}
        </button>
        <button
          onClick={() => setTab("reports")}
          className={cn(
            "flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
            tab === "reports" ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          <Flag className="h-3.5 w-3.5" />
          {t(lang, "admin_reports_title")}
          {pendingCount > 0 && (
            <span className="ml-1 rounded-full bg-red-500 text-white text-[10px] font-bold px-1.5 py-0.5 min-w-[18px] text-center">
              {pendingCount}
            </span>
          )}
        </button>
      </div>

      {/* ══════════════ Posts Tab ══════════════ */}
      {tab === "posts" && (
        <>
          {/* Filters */}
          <div className="mb-4 flex items-center justify-between flex-wrap gap-3">
            <div className="text-sm text-muted-foreground">
              {postTotal} {lang === "ko" ? "건" : "posts"}
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              <select
                value={statusFilter}
                onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary"
              >
                <option value="">{t(lang, "admin_all")}</option>
                <option value="active">{t(lang, "admin_active")}</option>
                <option value="hidden">{t(lang, "admin_post_hidden")}</option>
                <option value="deleted">{t(lang, "admin_post_deleted")}</option>
              </select>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="text"
                  value={search}
                  onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                  placeholder={t(lang, "admin_search")}
                  className="rounded-lg border border-border bg-card pl-9 pr-4 py-2 text-sm outline-none focus:border-primary w-56"
                />
              </div>
            </div>
          </div>

          {postsLoading ? (
            <div className="flex justify-center py-16">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : !postItems.length ? (
            <div className="flex flex-col items-center py-16 text-muted-foreground">
              <MessageSquare className="h-10 w-10 mb-3" />
              <p className="text-sm">{t(lang, "admin_no_data")}</p>
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/50">
                    <tr>
                      <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_title_col")}
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_post_type")}
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_status")}
                      </th>
                      <th className="px-3 py-3 text-center text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_post_views")}
                      </th>
                      <th className="px-3 py-3 text-center text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_post_likes")}
                      </th>
                      <th className="px-3 py-3 text-center text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_post_comments")}
                      </th>
                      <th className="px-3 py-3 text-center text-xs font-medium text-muted-foreground">
                        <Flag className="h-3 w-3 inline" />
                      </th>
                      <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_created_at")}
                      </th>
                      <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">
                        {t(lang, "admin_actions")}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {postItems.map((post) => (
                      <tr key={post.id} className="hover:bg-secondary/20">
                        <td className="px-4 py-3 max-w-[280px]">
                          <p className="font-medium truncate">{post.title}</p>
                          <p className="text-xs text-muted-foreground">
                            {post.author_nickname || (lang === "ko" ? "익명" : "Anonymous")}
                          </p>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[10px] font-medium",
                              TYPE_COLORS[post.post_type] || "bg-secondary text-muted-foreground"
                            )}
                          >
                            {post.post_type}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[10px] font-medium",
                              POST_STATUS_COLORS[post.status] || "bg-secondary text-muted-foreground"
                            )}
                          >
                            {post.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center text-muted-foreground">
                          {post.views.toLocaleString(locale)}
                        </td>
                        <td className="px-4 py-3 text-center text-muted-foreground">
                          {post.likes.toLocaleString(locale)}
                        </td>
                        <td className="px-4 py-3 text-center text-muted-foreground">
                          {post.comment_count.toLocaleString(locale)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {(post.report_count ?? 0) > 0 ? (
                            <span className="rounded-full bg-red-500/20 text-red-400 px-2 py-0.5 text-[10px] font-medium">
                              {post.report_count}
                            </span>
                          ) : (
                            <span className="text-muted-foreground/30 text-xs">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">
                          {new Date(post.created_at).toLocaleDateString(locale)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-2">
                            {post.status !== "deleted" && (
                              <button
                                onClick={() =>
                                  hideMutation.mutate({
                                    postId: post.id,
                                    hide: post.status !== "hidden",
                                  })
                                }
                                disabled={hideMutation.isPending}
                                className="text-muted-foreground hover:text-foreground"
                                title={
                                  post.status === "hidden"
                                    ? t(lang, "admin_post_unhide")
                                    : t(lang, "admin_post_hide")
                                }
                              >
                                {post.status === "hidden" ? (
                                  <Eye className="h-4 w-4 hover:text-green-400" />
                                ) : (
                                  <EyeOff className="h-4 w-4 hover:text-yellow-400" />
                                )}
                              </button>
                            )}
                            <a
                              href={`/community/${post.id}`}
                              target="_blank"
                              rel="noreferrer"
                              className="text-muted-foreground hover:text-primary"
                              title={t(lang, "admin_post_view_original")}
                            >
                              <ExternalLink className="h-4 w-4" />
                            </a>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Mobile cards */}
              <div className="md:hidden space-y-3">
                {postItems.map((post) => (
                  <div key={post.id} className="rounded-xl border border-border bg-card p-4">
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{post.title}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {post.author_nickname || (lang === "ko" ? "익명" : "Anonymous")}
                        </p>
                      </div>
                      {(post.report_count ?? 0) > 0 && (
                        <span className="rounded-full bg-red-500/20 text-red-400 px-2 py-0.5 text-[10px] font-medium shrink-0">
                          <Flag className="h-2.5 w-2.5 inline mr-0.5" />{post.report_count}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap mb-3">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium",
                          TYPE_COLORS[post.post_type] || "bg-secondary text-muted-foreground"
                        )}
                      >
                        {post.post_type}
                      </span>
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium",
                          POST_STATUS_COLORS[post.status] || "bg-secondary text-muted-foreground"
                        )}
                      >
                        {post.status}
                      </span>
                      <span className="text-[11px] text-muted-foreground ml-auto">
                        {new Date(post.created_at).toLocaleDateString(locale)}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3">
                      <span>{t(lang, "admin_post_views")} {post.views.toLocaleString(locale)}</span>
                      <span>{t(lang, "admin_post_likes")} {post.likes.toLocaleString(locale)}</span>
                      <span>{t(lang, "admin_post_comments")} {post.comment_count.toLocaleString(locale)}</span>
                    </div>
                    <div className="flex items-center gap-2 pt-2 border-t border-border">
                      {post.status !== "deleted" && (
                        <button
                          onClick={() =>
                            hideMutation.mutate({
                              postId: post.id,
                              hide: post.status !== "hidden",
                            })
                          }
                          disabled={hideMutation.isPending}
                          className={cn(
                            "flex items-center gap-1 rounded-lg px-3 py-1.5 text-xs",
                            post.status === "hidden"
                              ? "bg-green-500/10 text-green-400 hover:bg-green-500/20"
                              : "bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20"
                          )}
                        >
                          {post.status === "hidden" ? (
                            <><Eye className="h-3 w-3" />{t(lang, "admin_post_unhide")}</>
                          ) : (
                            <><EyeOff className="h-3 w-3" />{t(lang, "admin_post_hide")}</>
                          )}
                        </button>
                      )}
                      <a
                        href={`/community/${post.id}`}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-1 rounded-lg bg-secondary px-3 py-1.5 text-xs text-muted-foreground hover:bg-border"
                      >
                        <ExternalLink className="h-3 w-3" />
                        {t(lang, "admin_post_view_original")}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Pagination */}
          {postTotal > 20 && (
            <div className="flex justify-center gap-2 mt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="flex items-center px-3 text-sm text-muted-foreground">
                {t(lang, "admin_page_of", { page, total: totalPages })}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}

      {/* ══════════════ Reports Tab ══════════════ */}
      {tab === "reports" && (
        <>
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm text-muted-foreground">
              {t(lang, "admin_reports_subtitle", { n: reports.filter((r) => r.status === "pending").length })}
            </p>
            <div className="flex gap-2">
              {(["pending", "all"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setReportStatusFilter(s)}
                  className={cn(
                    "rounded-lg border px-3 py-1.5 text-sm",
                    reportStatusFilter === s
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground"
                  )}
                >
                  {s === "pending" ? t(lang, "admin_report_pending") : t(lang, "admin_all")}
                </button>
              ))}
            </div>
          </div>

          {reportsLoading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
                  <div className="flex gap-2">
                    <div className="h-5 w-24 rounded-full bg-secondary" />
                    <div className="h-5 w-12 rounded-full bg-secondary" />
                  </div>
                  <div className="h-4 w-3/4 rounded bg-secondary" />
                  <div className="h-3 w-32 rounded bg-secondary" />
                </div>
              ))}
            </div>
          ) : reports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Flag className="h-10 w-10 mb-3" />
              <p className="text-sm">{t(lang, "admin_reports_empty")}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="rounded-xl border border-border bg-card p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="text-xs font-medium bg-secondary rounded-full px-2 py-0.5">
                          {getTargetLabel(report.target_type)} #{report.target_id.slice(0, 8)}...
                        </span>
                        <span className={cn("text-[10px] rounded-full px-2 py-0.5 font-medium", REPORT_STATUS_COLORS[report.status])}>
                          {getStatusLabel(report.status)}
                        </span>
                      </div>
                      <p className="text-sm">
                        <span className="font-medium">{report.reporter_nickname || t(lang, "admin_report_anonymous")}</span>
                        {" — "}
                        <span className="text-muted-foreground">{report.reason}</span>
                      </p>
                      <div className="flex items-center gap-2 mt-1">
                        <p className="text-[11px] text-muted-foreground">
                          {new Date(report.created_at).toLocaleString(locale)}
                        </p>
                        {report.target_type === "post" && (
                          <a
                            href={`/community/${report.target_id}`}
                            target="_blank"
                            rel="noreferrer"
                            className="flex items-center gap-1 text-[11px] text-primary hover:underline"
                          >
                            <ExternalLink className="h-3 w-3" />
                            {t(lang, "admin_report_view_original")}
                          </a>
                        )}
                      </div>
                    </div>

                    {report.status === "pending" && (
                      <div className="flex gap-2 shrink-0">
                        <button
                          onClick={() => reviewMutation.mutate({ reportId: report.id, action: "resolve" })}
                          disabled={reviewMutation.isPending}
                          className="flex items-center gap-1 rounded-lg bg-green-500/10 px-3 py-1.5 text-xs text-green-400 hover:bg-green-500/20"
                        >
                          <CheckCircle className="h-3 w-3" />
                          {t(lang, "admin_report_resolve")}
                        </button>
                        <button
                          onClick={() => reviewMutation.mutate({ reportId: report.id, action: "dismiss" })}
                          disabled={reviewMutation.isPending}
                          className="flex items-center gap-1 rounded-lg bg-secondary px-3 py-1.5 text-xs text-muted-foreground hover:bg-border"
                        >
                          <X className="h-3 w-3" />
                          {t(lang, "admin_report_dismiss")}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

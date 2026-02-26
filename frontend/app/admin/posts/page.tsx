"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, Loader2, MessageSquare, Eye, EyeOff, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminToast } from "@/components/ui/admin-toast";
import { API_BASE } from "@/lib/admin-utils";

interface PostItem {
  id: string;
  title: string;
  post_type: string;
  status: string;
  views: number;
  likes: number;
  comment_count: number;
  author_nickname: string | null;
  created_at: string;
}

const TYPE_COLORS: Record<string, string> = {
  discussion: "bg-blue-500/20 text-blue-400",
  question: "bg-purple-500/20 text-purple-400",
  analysis: "bg-green-500/20 text-green-400",
};

const STATUS_COLORS: Record<string, string> = {
  active: "bg-green-500/20 text-green-400",
  hidden: "bg-yellow-500/20 text-yellow-400",
  deleted: "bg-red-500/20 text-red-400",
};

export default function AdminPostsPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const queryClient = useQueryClient();
  const { toast } = useAdminToast();
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);

  const locale = lang === "en" ? "en-US" : "ko-KR";

  const { data, isLoading } = useQuery<{ items: PostItem[]; total: number }>({
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
    enabled: !!user,
  });

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

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t(lang, "admin_posts")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {total} {lang === "ko" ? "건" : "posts"}
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Status filter */}
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

          {/* Search input */}
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

      {/* Loading skeleton */}
      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : !items.length ? (
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
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">
                    {t(lang, "admin_created_at")}
                  </th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-muted-foreground">
                    {t(lang, "admin_actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((post) => (
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
                          STATUS_COLORS[post.status] || "bg-secondary text-muted-foreground"
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
            {items.map((post) => (
              <div key={post.id} className="rounded-xl border border-border bg-card p-4">
                {/* Title & author */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-sm truncate">{post.title}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {post.author_nickname || (lang === "ko" ? "익명" : "Anonymous")}
                    </p>
                  </div>
                </div>

                {/* Badges */}
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
                      STATUS_COLORS[post.status] || "bg-secondary text-muted-foreground"
                    )}
                  >
                    {post.status}
                  </span>
                  <span className="text-[11px] text-muted-foreground ml-auto">
                    {new Date(post.created_at).toLocaleDateString(locale)}
                  </span>
                </div>

                {/* Stats */}
                <div className="flex items-center gap-4 text-xs text-muted-foreground mb-3">
                  <span>{t(lang, "admin_post_views")} {post.views.toLocaleString(locale)}</span>
                  <span>{t(lang, "admin_post_likes")} {post.likes.toLocaleString(locale)}</span>
                  <span>{t(lang, "admin_post_comments")} {post.comment_count.toLocaleString(locale)}</span>
                </div>

                {/* Actions */}
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
                        <>
                          <Eye className="h-3 w-3" />
                          {t(lang, "admin_post_unhide")}
                        </>
                      ) : (
                        <>
                          <EyeOff className="h-3 w-3" />
                          {t(lang, "admin_post_hide")}
                        </>
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
      {total > 20 && (
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

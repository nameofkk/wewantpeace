"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { t } from "@/lib/i18n";
import { useAdminStore, API_BASE } from "@/lib/admin-utils";
import { useAuth } from "@/lib/auth";
import { Eye, EyeOff, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";

interface AdminComment {
  id: string;
  post_id: string;
  post_title: string;
  content: string;
  author_nickname: string | null;
  status: string;
  like_count: number;
  created_at: string;
}

export default function AdminCommentsPage() {
  const lang = "ko" as const;
  const { user } = useAuth();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["admin-comments", page, statusFilter],
    queryFn: async () => {
      const token = await user?.getIdToken();
      const params = new URLSearchParams({ page: String(page) });
      if (statusFilter) params.append("status", statusFilter);
      const res = await fetch(`${API_BASE}/admin/comments?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json() as Promise<{ total: number; items: AdminComment[] }>;
    },
    enabled: !!user,
  });

  const toggleHide = useMutation({
    mutationFn: async (id: string) => {
      const token = await user?.getIdToken();
      const res = await fetch(`${API_BASE}/admin/comments/${id}/hide`, {
        method: "PATCH",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-comments"] }),
  });

  const totalPages = Math.ceil((data?.total ?? 0) / 20);
  const locale = lang === "en" ? "en-US" : "ko-KR";

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-lg font-bold">{t(lang, "admin_comments")}</h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? "댓글을 관리하고 부적절한 댓글을 숨길 수 있습니다" : "Manage comments and hide inappropriate ones"}
        </p>
      </div>

      {/* 필터 */}
      <div className="flex gap-2 mb-4">
        {["", "active", "hidden"].map((s) => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(1); }}
            className={cn(
              "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
              statusFilter === s ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground hover:text-foreground"
            )}
          >
            {s === "" ? t(lang, "admin_all") : s === "active" ? t(lang, "admin_active") : (lang === "ko" ? "숨김" : "Hidden")}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-muted-foreground">{t(lang, "admin_loading")}</div>
      ) : !data || data.items.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t(lang, "admin_no_data")}</div>
      ) : (
        <div className="space-y-2">
          {data.items.map((c) => (
            <div key={c.id} className={cn("rounded-lg border border-border p-4", c.status === "hidden" && "opacity-50")}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-muted-foreground mb-1">
                    {c.author_nickname ?? (lang === "ko" ? "익명" : "Anonymous")}
                    {" · "}
                    {new Date(c.created_at).toLocaleString(locale, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                    {c.status === "hidden" && (
                      <span className="ml-1.5 text-red-400 font-medium">[{lang === "ko" ? "숨김" : "Hidden"}]</span>
                    )}
                  </p>
                  <p className="text-sm">{c.content.length > 200 ? c.content.slice(0, 200) + "..." : c.content}</p>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {lang === "ko" ? "게시글" : "Post"}: {c.post_title}
                  </p>
                </div>
                <button
                  onClick={() => toggleHide.mutate(c.id)}
                  disabled={toggleHide.isPending}
                  className="shrink-0 p-2 rounded-lg hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
                  title={c.status === "hidden" ? t(lang, "admin_post_unhide") : t(lang, "admin_post_hide")}
                >
                  {c.status === "hidden" ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-6">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-muted-foreground">{t(lang, "admin_page_of", { page, total: totalPages })}</span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}

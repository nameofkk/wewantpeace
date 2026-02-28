"use client";

import { useState, useEffect, useCallback } from "react";
import { MessageCircleQuestion, Reply, Check, X, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/admin-utils";

interface FeedbackItem {
  id: number;
  user_nickname: string;
  message: string;
  category: string;
  status: string;
  admin_reply: string | null;
  created_at: string;
}

export default function AdminFeedbacksPage() {
  const { lang } = useAppStore();
  const { user } = useAuth();
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");

  // 답변 모달
  const [replyTarget, setReplyTarget] = useState<FeedbackItem | null>(null);
  const [replyText, setReplyText] = useState("");
  const [replying, setReplying] = useState(false);

  const fetchFeedbacks = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const token = await user.getIdToken();
      const params = new URLSearchParams({ page: String(page) });
      if (statusFilter) params.set("status", statusFilter);
      const res = await fetch(`${API_BASE}/admin/feedbacks?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setFeedbacks(data.items);
        setTotal(data.total);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [user, page, statusFilter]);

  useEffect(() => { fetchFeedbacks(); }, [fetchFeedbacks]);

  async function handleReply() {
    if (!user || !replyTarget) return;
    setReplying(true);
    try {
      const token = await user.getIdToken();
      await fetch(`${API_BASE}/admin/feedbacks/${replyTarget.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ admin_reply: replyText.trim(), status: "replied" }),
      });
      setReplyTarget(null);
      setReplyText("");
      fetchFeedbacks();
    } catch {
      // ignore
    } finally {
      setReplying(false);
    }
  }

  async function handleResolve(id: number) {
    if (!user) return;
    try {
      const token = await user.getIdToken();
      await fetch(`${API_BASE}/admin/feedbacks/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: "resolved" }),
      });
      fetchFeedbacks();
    } catch {
      // ignore
    }
  }

  const totalPages = Math.ceil(total / 20);

  const STATUS_COLORS: Record<string, string> = {
    pending: "bg-amber-500/15 text-amber-400",
    replied: "bg-blue-500/15 text-blue-400",
    resolved: "bg-green-500/15 text-green-400",
  };

  return (
    <div className="space-y-6">
      {/* 헤더 */}
      <div>
        <h1 className="text-lg font-bold flex items-center gap-2">
          <MessageCircleQuestion className="h-5 w-5 text-primary" />
          {t(lang, "admin_feedbacks")}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? `총 ${total}건의 피드백` : `${total} feedbacks total`}
        </p>
      </div>

      {/* 필터 */}
      <div className="flex gap-2">
        {["", "pending", "replied", "resolved"].map((s) => (
          <button
            key={s}
            onClick={() => { setStatusFilter(s); setPage(1); }}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-medium border transition-colors",
              statusFilter === s
                ? "bg-primary/10 border-primary/30 text-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            )}
          >
            {s === "" ? (lang === "ko" ? "전체" : "All")
              : s === "pending" ? (lang === "ko" ? "대기" : "Pending")
              : s === "replied" ? (lang === "ko" ? "답변완료" : "Replied")
              : (lang === "ko" ? "처리완료" : "Resolved")}
          </button>
        ))}
      </div>

      {/* 목록 */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : feedbacks.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground text-sm">
          {lang === "ko" ? "피드백이 없습니다" : "No feedbacks"}
        </div>
      ) : (
        <div className="space-y-3">
          {feedbacks.map((fb) => (
            <div key={fb.id} className="rounded-xl border border-border bg-card p-4 space-y-2">
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className="font-medium text-foreground">{fb.user_nickname}</span>
                <span>·</span>
                <span>{new Date(fb.created_at).toLocaleString(lang === "en" ? "en-US" : "ko-KR")}</span>
                <span className={cn("ml-auto rounded-full px-2 py-0.5 text-[10px] font-medium", STATUS_COLORS[fb.status] || "")}>
                  {fb.status}
                </span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{fb.message}</p>
              {fb.admin_reply && (
                <div className="rounded-lg bg-primary/5 border border-primary/20 p-3 mt-2">
                  <p className="text-[10px] text-primary font-medium mb-1">
                    {lang === "ko" ? "관리자 답변" : "Admin Reply"}
                  </p>
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">{fb.admin_reply}</p>
                </div>
              )}
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => { setReplyTarget(fb); setReplyText(fb.admin_reply || ""); }}
                  className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"
                >
                  <Reply className="h-3 w-3" />
                  {lang === "ko" ? "답변" : "Reply"}
                </button>
                {fb.status !== "resolved" && (
                  <button
                    onClick={() => handleResolve(fb.id)}
                    className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-green-500 hover:border-green-500/40 transition-colors"
                  >
                    <Check className="h-3 w-3" />
                    {lang === "ko" ? "처리완료" : "Resolve"}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 페이지네이션 */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-30"
          >
            {t(lang, "admin_prev")}
          </button>
          <span className="text-xs text-muted-foreground">
            {t(lang, "admin_page_of", { page, total: totalPages })}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
            className="rounded-lg border border-border px-3 py-1.5 text-xs disabled:opacity-30"
          >
            {t(lang, "admin_next")}
          </button>
        </div>
      )}

      {/* 답변 모달 */}
      {replyTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={() => setReplyTarget(null)}>
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">{lang === "ko" ? "피드백 답변" : "Reply to Feedback"}</p>
              <button onClick={() => setReplyTarget(null)} className="p-1 text-muted-foreground hover:text-foreground">
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="rounded-lg bg-muted/30 p-3">
              <p className="text-[10px] text-muted-foreground mb-1">{replyTarget.user_nickname}</p>
              <p className="text-sm">{replyTarget.message}</p>
            </div>
            <textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              rows={4}
              placeholder={lang === "ko" ? "답변을 입력하세요..." : "Write your reply..."}
              autoFocus
              className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleReply}
                disabled={replying || !replyText.trim()}
                className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 flex items-center justify-center gap-1.5"
              >
                {replying && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {lang === "ko" ? "답변 저장" : "Save Reply"}
              </button>
              <button
                onClick={() => setReplyTarget(null)}
                className="flex-1 rounded-lg border border-border py-2.5 text-sm text-muted-foreground"
              >
                {t(lang, "admin_cancel")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

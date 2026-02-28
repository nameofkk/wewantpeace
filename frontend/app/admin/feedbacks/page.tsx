"use client";

import { useState, useEffect, useCallback } from "react";
import { MessageCircleQuestion, Loader2 } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { API_BASE } from "@/lib/admin-utils";

interface FeedbackItem {
  id: number;
  user_nickname: string;
  message: string;
  created_at: string;
}

export default function AdminFeedbacksPage() {
  const { lang } = useAppStore();
  const { user } = useAuth();
  const [feedbacks, setFeedbacks] = useState<FeedbackItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const fetchFeedbacks = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/feedbacks?page=${page}`, {
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
  }, [user, page]);

  useEffect(() => { fetchFeedbacks(); }, [fetchFeedbacks]);

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-bold flex items-center gap-2">
          <MessageCircleQuestion className="h-5 w-5 text-primary" />
          {t(lang, "admin_feedbacks")}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {lang === "ko" ? `총 ${total}건` : `${total} total`}
        </p>
      </div>

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
            <div key={fb.id} className="rounded-xl border border-border bg-card p-4 space-y-1.5">
              <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className="font-medium text-foreground">{fb.user_nickname}</span>
                <span>·</span>
                <span>{new Date(fb.created_at).toLocaleString(lang === "en" ? "en-US" : "ko-KR")}</span>
              </div>
              <p className="text-sm whitespace-pre-wrap">{fb.message}</p>
            </div>
          ))}
        </div>
      )}

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
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import { Bell, ArrowLeft, CheckCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { useNotifications, useMarkRead, useMarkAllRead, useSubmitFeedback, NotificationItem } from "@/lib/api";
import { ThumbsUp, ThumbsDown } from "lucide-react";
import { t, Lang } from "@/lib/i18n";
import { useAppStore } from "@/lib/store";

function timeAgo(iso: string, lang: Lang): string {
  const diff = Date.now() - new Date(iso).getTime();
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return lang === "ko" ? "방금 전" : "just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return lang === "ko" ? `${min}분 전` : `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return lang === "ko" ? `${hr}시간 전` : `${hr}h ago`;
  const day = Math.floor(hr / 24);
  return lang === "ko" ? `${day}일 전` : `${day}d ago`;
}

export default function NotificationsPage() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang) as Lang;
  const { data: notifications, isLoading } = useNotifications();
  const markRead = useMarkRead();
  const markAllRead = useMarkAllRead();
  const submitFeedback = useSubmitFeedback();

  const hasUnread = notifications?.some((n) => !n.is_read);

  const handleClick = (notif: NotificationItem) => {
    if (!notif.is_read) {
      markRead.mutate(notif.id);
    }
    if (notif.cluster_id) {
      router.push(`/issues/${notif.cluster_id}`);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* 헤더 */}
      <div className="sticky top-0 z-30 bg-background/90 backdrop-blur-md border-b border-border/50">
        <div className="flex items-center justify-between h-[52px] px-4">
          <button onClick={() => router.back()} className="p-1">
            <ArrowLeft className="w-5 h-5 text-muted-foreground" />
          </button>
          <h1 className="text-[15px] font-semibold">{t(lang, "notif_page_title")}</h1>
          {hasUnread ? (
            <button
              onClick={() => markAllRead.mutate()}
              className="flex items-center gap-1 text-xs text-primary"
            >
              <CheckCheck className="w-4 h-4" />
              <span>{t(lang, "notif_mark_all_read")}</span>
            </button>
          ) : (
            <div className="w-16" />
          )}
        </div>
      </div>

      {/* 알림 목록 */}
      <div className="pb-[80px]">
        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : !notifications || notifications.length === 0 ? (
          /* 빈 상태 */
          <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
            <Bell className="w-12 h-12 opacity-30" />
            <p className="text-sm font-medium">{t(lang, "notif_page_empty")}</p>
            <p className="text-xs">{t(lang, "notif_page_empty_sub")}</p>
          </div>
        ) : (
          <ul className="divide-y divide-border/40">
            {notifications.map((notif) => (
              <li
                key={notif.id}
                onClick={() => handleClick(notif)}
                className={cn(
                  "flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors",
                  !notif.is_read && "bg-primary/5"
                )}
              >
                {/* 읽지 않은 표시 */}
                <div className="flex-shrink-0 pt-1.5">
                  {!notif.is_read ? (
                    <div className="w-2 h-2 rounded-full bg-blue-500" />
                  ) : (
                    <div className="w-2 h-2" />
                  )}
                </div>

                {/* 내용 */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    {/* 타입 뱃지 */}
                    <span
                      className={cn(
                        "text-[10px] font-bold px-1.5 py-0.5 rounded-full",
                        notif.type === "verified"
                          ? "bg-green-500/20 text-green-400"
                          : "bg-red-500/20 text-red-400"
                      )}
                    >
                      {notif.type === "verified"
                        ? t(lang, "notif_type_verified")
                        : t(lang, "notif_type_spike")}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {timeAgo(notif.created_at, lang)}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-foreground truncate">
                    {notif.title}
                  </p>
                  <p className="text-xs text-muted-foreground truncate mt-0.5">
                    {notif.body}
                  </p>
                  {/* 피드백 버튼 */}
                  <div className="flex items-center gap-2 mt-1.5">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        submitFeedback.mutate({ id: notif.id, feedback: "thumbs_up" });
                      }}
                      className={cn(
                        "flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] transition-colors",
                        notif.feedback === "thumbs_up"
                          ? "bg-green-500/20 text-green-400"
                          : "text-muted-foreground hover:text-green-400"
                      )}
                    >
                      <ThumbsUp className="w-3 h-3" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        submitFeedback.mutate({ id: notif.id, feedback: "thumbs_down" });
                      }}
                      className={cn(
                        "flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] transition-colors",
                        notif.feedback === "thumbs_down"
                          ? "bg-red-500/20 text-red-400"
                          : "text-muted-foreground hover:text-red-400"
                      )}
                    >
                      <ThumbsDown className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

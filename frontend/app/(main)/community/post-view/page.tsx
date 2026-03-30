"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect } from "react";
import { ChevronLeft, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE, useMe } from "@/lib/api";

function relativeTime(iso: string, lang: Lang): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return t(lang, "home_just_now");
  if (m < 60) return t(lang, "home_minutes_ago", { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t(lang, "home_hours_ago", { n: h });
  const locale = lang === "en" ? "en-US" : "ko-KR";
  return new Date(iso).toLocaleDateString(locale);
}

function PostViewInner() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);

  const { data: post, isLoading, isError } = useQuery<{
    id: string;
    title: string;
    title_en?: string | null;
    content: string;
    content_en?: string | null;
    post_type: string;
    author_nickname: string | null;
    created_at: string;
    view_count: number;
    comment_count: number;
    like_count: number;
  }>({
    queryKey: ["community", "post", id],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/community/posts/${id}`);
      if (!res.ok) throw new Error("Failed");
      return res.json();
    },
    enabled: !!id,
    staleTime: 60 * 1000,
  });

  if (!id) {
    return <div className="flex items-center justify-center min-h-screen text-muted-foreground">{lang === "ko" ? "게시글을 찾을 수 없습니다." : "Post not found."}</div>;
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <button onClick={() => router.back()} className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-5 w-5" />
        </button>
        <h1 className="text-base font-bold truncate">{t(lang, "community_title")}</h1>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      )}

      {isError && (
        <div className="flex items-center justify-center py-12 text-muted-foreground text-sm">
          {t(lang, "error_generic")}
        </div>
      )}

      {post && (
        <div className="flex-1 px-4 py-4 space-y-4">
          <div>
            <h2 className="text-lg font-bold">{lang === "en" ? (post.title_en || post.title) : post.title}</h2>
            <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
              <span>{post.author_nickname || "Anonymous"}</span>
              <span>·</span>
              <span>{relativeTime(post.created_at, lang)}</span>
              <span>·</span>
              <span>{t(lang, "community_views")} {post.view_count}</span>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-sm">
              {lang === "en" ? (post.content_en || post.content) : post.content}
            </div>
          </div>

          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>{t(lang, "community_likes")} {post.like_count}</span>
            <span>{t(lang, "community_comments")} {post.comment_count}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PostViewPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col min-h-screen animate-pulse">
        <div className="sticky top-0 z-20 flex items-center gap-3 px-4 py-3 border-b border-border bg-background">
          <div className="h-5 w-5 rounded bg-muted" />
          <div className="h-5 w-32 rounded bg-muted" />
        </div>
        <div className="flex-1 p-4 space-y-4">
          <div className="h-6 w-3/4 rounded bg-muted" />
          <div className="h-40 rounded-xl border border-border bg-card" />
        </div>
      </div>
    }>
      <PostViewInner />
    </Suspense>
  );
}

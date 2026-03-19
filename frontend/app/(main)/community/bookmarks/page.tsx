"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Heart, MessageCircle, Eye, Bookmark, BookmarkX, Loader2 } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { fetchBookmarks, toggleBookmark, Post } from "@/lib/api";
import Avatar from "@/components/community/Avatar";
import { communityPostPath } from "@/lib/toss-nav";

function relativeTime(iso: string, lang: "ko" | "en"): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return t(lang, "home_just_now");
  if (m < 60) return t(lang, "home_minutes_ago", { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t(lang, "home_hours_ago", { n: h });
  const locale = lang === "en" ? "en-US" : "ko-KR";
  return new Date(iso).toLocaleDateString(locale);
}

export default function BookmarksPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const lang = useAppStore((s) => s.lang);

  const { data: bookmarks, isLoading, isError } = useQuery<Post[]>({
    queryKey: ["bookmarks"],
    queryFn: () => fetchBookmarks(),
    enabled: !!user && !authLoading,
  });

  async function handleUnbookmark(postId: string) {
    try {
      await toggleBookmark(postId);
      queryClient.invalidateQueries({ queryKey: ["bookmarks"] });
      queryClient.invalidateQueries({ queryKey: ["community-posts"] });
    } catch {
      // silently ignore
    }
  }

  if (!authLoading && !user) {
    router.replace("/login");
    return null;
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Sticky header */}
      <div className="sticky top-0 z-10 bg-background/95 backdrop-blur-sm border-b border-border px-4 py-3 flex items-center gap-3">
        <button onClick={() => router.back()} className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-bold">{t(lang, "community_bookmarks_title")}</h1>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Loading */}
        {(isLoading || authLoading) && (
          <div className="flex justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            {lang === "en" ? "Failed to load bookmarks" : "북마크를 불러오지 못했습니다"}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && bookmarks?.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground">
            <BookmarkX className="w-12 h-12 mb-3 opacity-40" />
            <p className="text-sm">{t(lang, "community_bookmarks_empty")}</p>
          </div>
        )}

        {/* Bookmark list */}
        {bookmarks && bookmarks.length > 0 && (
          <div className="divide-y divide-border">
            {bookmarks.map((post: Post) => (
              <Link
                key={post.id}
                href={communityPostPath(post.id)}
                className="block px-4 py-3.5 active:bg-muted/30 transition-colors"
              >
                {/* Author row */}
                <div className="flex items-center gap-2.5 mb-2">
                  <Avatar nickname={post.author_nickname ?? null} plan={post.author_plan} size="sm" />
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium">
                      {post.author_nickname || t(lang, "community_anonymous")}
                    </span>
                    <span className="text-xs text-muted-foreground ml-2">
                      {relativeTime(post.created_at, lang)}
                    </span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleUnbookmark(post.id);
                    }}
                    className="text-primary p-1"
                  >
                    <Bookmark className="w-4 h-4 fill-primary" />
                  </button>
                </div>

                {/* Title */}
                <h3 className="text-[15px] font-semibold line-clamp-2 mb-1">
                  {lang === "en" && post.title_en ? post.title_en : post.title}
                </h3>

                {/* Content preview */}
                {post.content && (
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-2">
                    {lang === "en" && post.content_en ? post.content_en : post.content}
                  </p>
                )}

                {/* Stats */}
                <div className="flex items-center gap-3 text-[11px] text-muted-foreground mt-2">
                  <span className="flex items-center gap-1">
                    <Heart className="w-3.5 h-3.5" /> {post.like_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <MessageCircle className="w-3.5 h-3.5" /> {post.comment_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <Eye className="w-3.5 h-3.5" /> {post.view_count}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, MessageCircle, Eye, Bookmark, Loader2 } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { fetchBookmarks, toggleBookmark, type Post } from "@/lib/api";
import { communityPostPath } from "@/lib/toss-nav";

function relativeTime(iso: string, lang: Lang): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return t(lang, "home_just_now");
  if (m < 60) return t(lang, "home_minutes_ago", { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t(lang, "home_hours_ago", { n: h });
  const locale = lang === "en" ? "en-US" : "ko-KR";
  return new Date(iso).toLocaleDateString(locale, { month: "short", day: "numeric" });
}

export default function BookmarksPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const lang = useAppStore((s) => s.lang);

  const {
    data: bookmarks,
    isLoading,
    isError,
  } = useQuery<Post[]>({
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
      /* silent */
    }
  }

  // 렌더 도중 router.replace()를 부르면 서버 프리렌더에서 location에 접근해
  // "ReferenceError: location is not defined"로 이 페이지의 정적 생성이 실패한다
  // (빌드 로그에서 확인). 리다이렉트는 이펙트에서 하고 렌더는 null만 반환한다.
  const needsLogin = !authLoading && !user;
  useEffect(() => {
    if (needsLogin) router.replace("/login");
  }, [needsLogin, router]);

  if (needsLogin) {
    return null;
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-background border-b border-border px-2 h-11 flex items-center gap-2">
        <button
          onClick={() => router.back()}
          className="p-2 text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
        </button>
        <h1 className="text-[15px] font-semibold">
          {t(lang, "community_bookmarks_title")}
        </h1>
      </header>

      <div className="flex-1 overflow-y-auto">
        {(isLoading || authLoading) && (
          <div className="flex justify-center py-16">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/50" />
          </div>
        )}

        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            {t(lang, "error_generic")}
          </div>
        )}

        {!isLoading && !isError && bookmarks?.length === 0 && (
          <div className="py-20 text-center">
            <Bookmark className="w-8 h-8 mx-auto mb-2 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground">
              {t(lang, "community_bookmarks_empty")}
            </p>
          </div>
        )}

        {bookmarks && bookmarks.length > 0 && (
          <div className="divide-y divide-border/60">
            {bookmarks.map((post) => {
              const title =
                lang === "en" && post.title_en ? post.title_en : post.title;
              const preview = post.content
                ? post.content.replace(/[#*>\-\[\]()]/g, "").slice(0, 80)
                : "";

              return (
                <Link
                  key={post.id}
                  href={communityPostPath(post.id)}
                  className="flex gap-3 px-4 py-3.5 cursor-pointer active:bg-gray-50 dark:active:bg-white/5 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[15px] font-semibold leading-snug line-clamp-2 text-foreground">
                      {title}
                    </p>
                    {preview && (
                      <p className="mt-1 text-[13px] text-muted-foreground line-clamp-1">
                        {preview}
                      </p>
                    )}
                    <div className="flex items-center gap-1.5 mt-2 text-[11px] text-muted-foreground/80">
                      <span className="font-medium text-foreground/60">
                        {post.author_nickname || t(lang, "community_anonymous")}
                      </span>
                      <span className="text-muted-foreground/40">·</span>
                      <span>{relativeTime(post.created_at, lang)}</span>
                      <span className="ml-auto flex items-center gap-2.5">
                        {post.comment_count > 0 && (
                          <span className="flex items-center gap-0.5">
                            <MessageCircle className="w-3 h-3" />
                            {post.comment_count}
                          </span>
                        )}
                        <span className="flex items-center gap-0.5">
                          <Eye className="w-3 h-3" />
                          {post.view_count}
                        </span>
                        <button
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            handleUnbookmark(post.id);
                          }}
                          className="p-0.5 -m-0.5 cursor-pointer"
                        >
                          <Bookmark className="w-3 h-3 fill-primary text-primary" />
                        </button>
                      </span>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

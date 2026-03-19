"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  MessageCircle,
  Eye,
  Bookmark,
  Plus,
  Pin,
  ArrowUpDown,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE, fetchPostsCursor, toggleBookmark, type Post } from "@/lib/api";
import { communityPostPath } from "@/lib/toss-nav";

type PostType = "all" | "discussion" | "analysis" | "question" | "notice";
type SortBy = "latest" | "popular";

const TYPES: { value: PostType; labelKey: string }[] = [
  { value: "all", labelKey: "community_type_all" },
  { value: "discussion", labelKey: "community_type_discussion" },
  { value: "analysis", labelKey: "community_type_analysis" },
  { value: "question", labelKey: "community_type_question" },
  { value: "notice", labelKey: "community_type_notice" },
];

const TYPE_LABEL_KEYS: Record<string, string> = {
  discussion: "community_type_discussion",
  analysis: "community_type_analysis",
  question: "community_type_question",
  notice: "community_type_notice",
};

function relativeTime(iso: string, lang: Lang): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return t(lang, "home_just_now");
  if (m < 60) return t(lang, "home_minutes_ago", { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t(lang, "home_hours_ago", { n: h });
  return t(lang, "community_days_ago", { n: Math.floor(h / 24) });
}

function PostCard({
  post,
  lang,
  onBookmarkToggle,
}: {
  post: Post;
  lang: Lang;
  onBookmarkToggle: (postId: string) => void;
}) {
  const title = lang === "en" && post.title_en ? post.title_en : post.title;
  const typeKey = TYPE_LABEL_KEYS[post.post_type] || post.post_type;
  const typeLabel = t(lang, typeKey as Parameters<typeof t>[1]) || post.post_type;
  const time = relativeTime(post.created_at, lang);

  const imgUrl =
    post.images && post.images.length > 0
      ? post.images[0].startsWith("http")
        ? post.images[0]
        : `${API_BASE}${post.images[0]}`
      : null;

  return (
    <Link href={communityPostPath(post.id)} className="block px-4 py-3 active:bg-muted/30 transition-colors">
      {/* Title row */}
      <div className="flex gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium leading-snug line-clamp-2">
            {post.is_pinned && <Pin className="inline w-3 h-3 text-primary mr-1 -mt-0.5" />}
            {title}
          </h3>
          {post.content && (
            <p className="text-xs text-muted-foreground line-clamp-1 mt-1">
              {post.content.slice(0, 100)}
            </p>
          )}
        </div>
        {imgUrl && (
          <div className="w-12 h-12 rounded-lg overflow-hidden shrink-0 bg-muted">
            <img src={imgUrl} alt="" className="w-full h-full object-cover" />
          </div>
        )}
      </div>

      {/* Meta row */}
      <div className="flex items-center gap-2 mt-2 text-[11px] text-muted-foreground">
        <span className="font-medium text-foreground/70">
          {post.author_nickname || t(lang, "community_anonymous")}
        </span>
        <span>{time}</span>
        <span className="px-1 py-0.5 rounded bg-muted/60 text-[10px]">{typeLabel}</span>
        <div className="flex items-center gap-2.5 ml-auto">
          <span className="flex items-center gap-0.5">
            <MessageCircle className="w-3 h-3" /> {post.comment_count}
          </span>
          <span className="flex items-center gap-0.5">
            <Eye className="w-3 h-3" /> {post.view_count}
          </span>
          <button
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              onBookmarkToggle(post.id);
            }}
            className="p-0.5 -m-0.5"
          >
            <Bookmark
              className={`w-3 h-3 ${
                post.is_bookmarked ? "fill-primary text-primary" : ""
              }`}
            />
          </button>
        </div>
      </div>
    </Link>
  );
}

export default function CommunityPage() {
  const { user } = useAuth();
  const lang = useAppStore((s) => s.lang);
  const queryClient = useQueryClient();

  const [activeType, setActiveType] = useState<PostType>("all");
  const [sortBy, setSortBy] = useState<SortBy>("latest");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [showSearch, setShowSearch] = useState(false);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Infinite scroll query
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    isError,
  } = useInfiniteQuery({
    queryKey: ["community-posts", activeType, sortBy, debouncedSearch],
    queryFn: ({ pageParam }) =>
      fetchPostsCursor({
        cursor: pageParam,
        limit: 20,
        post_type: activeType,
        sort_by: sortBy,
        q: debouncedSearch || undefined,
      }),
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
    initialPageParam: undefined as string | undefined,
  });

  // Hot topics
  const { data: hotTopics } = useQuery<Post[]>({
    queryKey: ["hot-topics", activeType],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (activeType !== "all") params.append("post_type", activeType);
      const res = await fetch(`${API_BASE}/community/hot-topics?${params}`);
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 60000,
  });

  // Pinned notices
  const { data: pinnedNotices } = useQuery<Post[]>({
    queryKey: ["pinned-notices"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/community/pinned-notices`);
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 60000,
    enabled: activeType !== "notice",
  });

  // IntersectionObserver
  const observerRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = observerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
          fetchNextPage();
        }
      },
      { threshold: 0.1 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  const handleBookmarkToggle = useCallback(
    async (postId: string) => {
      if (!user) return;
      try {
        const result = await toggleBookmark(postId);
        queryClient.setQueriesData<{
          pages: { posts: Post[]; next_cursor: string | null }[];
          pageParams: (string | undefined)[];
        }>({ queryKey: ["community-posts"] }, (old) => {
          if (!old) return old;
          return {
            ...old,
            pages: old.pages.map((page) => ({
              ...page,
              posts: page.posts.map((p) =>
                p.id === postId ? { ...p, is_bookmarked: result.bookmarked } : p
              ),
            })),
          };
        });
      } catch {}
    },
    [user, queryClient]
  );

  const allPosts = data?.pages.flatMap((page) => page.posts) ?? [];

  return (
    <div className="flex flex-col" style={{ height: "calc(100dvh - 60px)" }}>
      {/* Header */}
      <div className="sticky top-0 z-10 bg-background border-b border-border">
        <div className="flex items-center justify-between px-4 h-12">
          <h1 className="text-base font-bold">{t(lang, "community_title")}</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowSearch(!showSearch)}
              className="p-1.5 text-muted-foreground hover:text-foreground"
            >
              <Search className="w-4.5 h-4.5" />
            </button>
            {user && (
              <Link href="/community/bookmarks" className="p-1.5 text-muted-foreground hover:text-foreground">
                <Bookmark className="w-4.5 h-4.5" />
              </Link>
            )}
            <button
              onClick={() => setSortBy(sortBy === "latest" ? "popular" : "latest")}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              <ArrowUpDown className="h-3.5 w-3.5" />
              {sortBy === "latest"
                ? t(lang, "community_sort_latest")
                : t(lang, "community_sort_popular")}
            </button>
          </div>
        </div>

        {/* Search bar (toggled) */}
        {showSearch && (
          <div className="px-4 pb-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                autoFocus
                placeholder={t(lang, "community_search_placeholder")}
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-muted/50 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary/30"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex overflow-x-auto scrollbar-hide">
          {TYPES.map((type) => (
            <button
              key={type.value}
              onClick={() => setActiveType(type.value)}
              className={`shrink-0 px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
                activeType === type.value
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground"
              }`}
            >
              {t(lang, type.labelKey as Parameters<typeof t>[1])}
            </button>
          ))}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Pinned notices */}
        {activeType !== "notice" && pinnedNotices && pinnedNotices.length > 0 && (
          <div className="border-b border-border">
            {pinnedNotices.map((notice) => (
              <Link key={notice.id} href={communityPostPath(notice.id)} className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-muted/30 transition-colors">
                <Pin className="w-3 h-3 text-primary shrink-0" />
                <span className="font-medium truncate flex-1">
                  {lang === "en" && notice.title_en ? notice.title_en : notice.title}
                </span>
                <ChevronRight className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
              </Link>
            ))}
          </div>
        )}

        {/* Hot topics */}
        {hotTopics && hotTopics.length > 0 && (
          <div className="px-4 py-3 border-b border-border">
            <h2 className="text-xs font-semibold text-muted-foreground mb-2">{t(lang, "community_hot_topics")}</h2>
            <div className="space-y-1">
              {hotTopics.slice(0, 5).map((post, i) => (
                <Link key={post.id} href={communityPostPath(post.id)} className="flex items-center gap-2 py-1 hover:text-foreground transition-colors">
                  <span className="text-xs font-bold text-primary w-4 text-center">{i + 1}</span>
                  <span className="text-sm truncate flex-1">
                    {lang === "en" && post.title_en ? post.title_en : post.title}
                  </span>
                </Link>
              ))}
            </div>
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="py-20 flex justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Error */}
        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            {t(lang, "error_generic")}
          </div>
        )}

        {/* Empty */}
        {!isLoading && !isError && allPosts.length === 0 && (
          <div className="py-16 text-center text-sm text-muted-foreground">
            {t(lang, "community_no_posts")}
          </div>
        )}

        {/* Post list */}
        {allPosts.length > 0 && (
          <div className="divide-y divide-border/50">
            {allPosts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                lang={lang}
                onBookmarkToggle={handleBookmarkToggle}
              />
            ))}
          </div>
        )}

        <div ref={observerRef} className="h-10" />

        {isFetchingNextPage && (
          <div className="py-4 flex justify-center">
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
          </div>
        )}

        {!hasNextPage && allPosts.length > 0 && !isLoading && (
          <div className="py-6 text-center text-xs text-muted-foreground">
            {t(lang, "community_no_more")}
          </div>
        )}
      </div>

      {/* FAB */}
      {user && (
        <Link
          href="/community/new"
          className="fixed bottom-20 right-4 z-30 w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center active:scale-95 transition-transform"
        >
          <Plus className="w-5 h-5" />
        </Link>
      )}
    </div>
  );
}

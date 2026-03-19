"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  Heart,
  MessageCircle,
  Eye,
  Bookmark,
  Plus,
  Pin,
  ArrowUpDown,
  Flame,
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Megaphone,
  MessageSquare,
  FileText,
  HelpCircle,
} from "lucide-react";
import { motion } from "framer-motion";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE, fetchPostsCursor, toggleBookmark, type Post } from "@/lib/api";
import { communityPostPath } from "@/lib/toss-nav";
import Avatar from "@/components/community/Avatar";

type PostType = "all" | "discussion" | "analysis" | "question" | "notice";
type SortBy = "latest" | "popular";

const TYPES: { value: PostType; icon: string; labelKey: string }[] = [
  { value: "all", icon: "", labelKey: "community_type_all" },
  { value: "discussion", icon: "💬", labelKey: "community_type_discussion" },
  { value: "analysis", icon: "📊", labelKey: "community_type_analysis" },
  { value: "question", icon: "❓", labelKey: "community_type_question" },
  { value: "notice", icon: "📢", labelKey: "community_type_notice" },
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
  index = 0,
  lang,
  isFirstPage,
  onBookmarkToggle,
}: {
  post: Post;
  index?: number;
  lang: Lang;
  isFirstPage: boolean;
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

  const inner = (
    <div className="px-4 py-3.5">
      {/* Top row: avatar + author + time */}
      <div className="flex items-center gap-2.5 mb-2">
        <Avatar nickname={post.author_nickname ?? null} plan={post.author_plan} size="sm" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium truncate">
              {post.author_nickname || t(lang, "community_anonymous")}
            </span>
            <span className="text-[10px] text-muted-foreground">{time}</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-muted/60 text-muted-foreground">
              {typeLabel}
            </span>
            {post.cluster_title_ko && (
              <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-500/10 text-blue-400 truncate max-w-[140px]">
                {lang === "en"
                  ? post.cluster_title || post.cluster_title_ko
                  : post.cluster_title_ko}
              </span>
            )}
          </div>
        </div>
        {/* Image thumbnail */}
        {imgUrl && (
          <div className="w-14 h-14 rounded-xl overflow-hidden shrink-0 bg-muted">
            <img src={imgUrl} alt="" className="w-full h-full object-cover" />
          </div>
        )}
      </div>

      {/* Title */}
      <Link href={communityPostPath(post.id)}>
        <h3 className="text-[15px] font-semibold leading-snug line-clamp-2 mb-1 hover:underline">
          {post.is_pinned && <Pin className="inline w-3.5 h-3.5 text-yellow-500 mr-1 -mt-0.5" />}
          {title}
        </h3>
      </Link>

      {/* Content preview */}
      {post.content && (
        <p className="text-xs text-muted-foreground line-clamp-2 mb-2.5">
          {post.content.slice(0, 120)}
        </p>
      )}

      {/* Bottom stats */}
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <Heart className="w-3.5 h-3.5" /> {post.like_count}
        </span>
        <span className="flex items-center gap-1">
          <MessageCircle className="w-3.5 h-3.5" /> {post.comment_count}
        </span>
        <span className="flex items-center gap-1">
          <Eye className="w-3.5 h-3.5" /> {post.view_count}
        </span>
        <button
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onBookmarkToggle(post.id);
          }}
          className="ml-auto p-1 -m-1"
        >
          <Bookmark
            className={`w-3.5 h-3.5 transition-colors ${
              post.is_bookmarked ? "fill-primary text-primary" : "hover:text-foreground"
            }`}
          />
        </button>
      </div>
    </div>
  );

  if (isFirstPage && index < 20) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: index * 0.03, duration: 0.2 }}
      >
        {inner}
      </motion.div>
    );
  }

  return inner;
}

export default function CommunityPage() {
  const { user } = useAuth();
  const lang = useAppStore((s) => s.lang);
  const queryClient = useQueryClient();

  const [activeType, setActiveType] = useState<PostType>("all");
  const [sortBy, setSortBy] = useState<SortBy>("latest");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [hotTopicsOpen, setHotTopicsOpen] = useState(true);

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

  // IntersectionObserver for auto-loading
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

  // Bookmark toggle handler
  const handleBookmarkToggle = useCallback(
    async (postId: string) => {
      if (!user) return;
      try {
        const result = await toggleBookmark(postId);
        // Optimistically update the post in cache
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
      } catch {
        // silent fail
      }
    },
    [user, queryClient]
  );

  const allPosts = data?.pages.flatMap((page) => page.posts) ?? [];

  return (
    <div className="flex flex-col" style={{ height: "calc(100dvh - 60px)" }}>
      {/* Header (sticky) */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm">
        <div className="flex items-center justify-between px-4 pt-4 pb-2">
          <h1 className="text-lg font-bold">{t(lang, "community_title")}</h1>
          <button
            onClick={() => setSortBy(sortBy === "latest" ? "popular" : "latest")}
            className={`flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
              sortBy === "popular"
                ? "border-primary bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
          >
            <ArrowUpDown className="h-3 w-3" />
            {sortBy === "latest"
              ? t(lang, "community_sort_latest")
              : t(lang, "community_sort_popular")}
          </button>
        </div>

        {/* Search bar */}
        <div className="px-4 py-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder={t(lang, "community_search_placeholder")}
              className="w-full pl-9 pr-4 py-2.5 rounded-full bg-muted/50 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/30"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>

        {/* Filter chips */}
        <div className="flex gap-2 px-4 pb-2 overflow-x-auto scrollbar-hide">
          {TYPES.map((type) => (
            <button
              key={type.value}
              onClick={() => setActiveType(type.value)}
              className={`shrink-0 px-3.5 py-1.5 rounded-full text-xs font-medium transition-colors ${
                activeType === type.value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted"
              }`}
            >
              {type.icon ? `${type.icon} ` : ""}
              {t(lang, type.labelKey as Parameters<typeof t>[1])}
            </button>
          ))}
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">
        {/* Pinned notices */}
        {activeType !== "notice" && pinnedNotices && pinnedNotices.length > 0 && (
          <div className="px-4 pt-3 pb-2 space-y-2 border-b border-yellow-500/20">
            {pinnedNotices.map((notice) => (
              <Link key={notice.id} href={communityPostPath(notice.id)}>
                <div className="flex items-center gap-2 rounded-xl border border-yellow-500/30 bg-yellow-500/5 px-3.5 py-2.5 hover:bg-yellow-500/10 transition-colors cursor-pointer">
                  <Megaphone className="h-3.5 w-3.5 text-yellow-500 shrink-0" />
                  <span className="text-sm font-medium truncate flex-1">
                    {lang === "en" && notice.title_en ? notice.title_en : notice.title}
                  </span>
                  <span className="text-[10px] text-muted-foreground shrink-0">
                    {relativeTime(notice.created_at, lang)}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}

        {/* Hot topics section */}
        {hotTopics && hotTopics.length > 0 && (
          <div className="border-b border-border">
            <button
              onClick={() => setHotTopicsOpen(!hotTopicsOpen)}
              className="flex items-center justify-between w-full px-4 py-3 text-sm font-semibold hover:bg-secondary/30 transition-colors"
            >
              <div className="flex items-center gap-2">
                <Flame className="h-4 w-4 text-orange-400" />
                <span>{t(lang, "community_hot_topics")}</span>
              </div>
              {hotTopicsOpen ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </button>
            {hotTopicsOpen && (
              <div className="overflow-x-auto scrollbar-hide px-4 pb-4">
                <div className="flex gap-3" style={{ minWidth: "max-content" }}>
                  {hotTopics.map((post, i) => (
                    <Link key={post.id} href={communityPostPath(post.id)}>
                      <div className="rounded-2xl bg-card/80 p-3 shadow-sm min-w-[200px] max-w-[200px] hover:bg-card transition-colors cursor-pointer border border-border/50">
                        <div className="flex items-center gap-1.5 mb-1.5">
                          <span className="text-[11px] font-bold text-orange-400">#{i + 1}</span>
                          <span className="text-[10px] text-muted-foreground truncate flex-1">
                            {post.author_nickname || t(lang, "community_anonymous")}
                          </span>
                        </div>
                        <p className="text-xs font-medium line-clamp-2 leading-snug">
                          {lang === "en" && post.title_en ? post.title_en : post.title}
                        </p>
                        <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
                          <span className="flex items-center gap-0.5">
                            <Heart className="h-2.5 w-2.5" />
                            {post.like_count}
                          </span>
                          <span className="flex items-center gap-0.5">
                            <Eye className="h-2.5 w-2.5" />
                            {post.view_count}
                          </span>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Loading skeleton */}
        {isLoading && (
          <div className="divide-y divide-border/50">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="px-4 py-3.5 animate-pulse">
                <div className="flex items-center gap-2.5 mb-2">
                  <div className="w-8 h-8 rounded-full bg-muted" />
                  <div className="flex-1">
                    <div className="h-3.5 w-24 rounded bg-muted mb-1" />
                    <div className="h-2.5 w-16 rounded bg-muted" />
                  </div>
                </div>
                <div className="h-4 w-3/4 rounded bg-muted mb-1.5" />
                <div className="h-3 w-1/2 rounded bg-muted" />
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            {t(lang, "community_load_error")}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && allPosts.length === 0 && (
          <div className="py-16 text-center">
            <MessageSquare className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm font-medium">{t(lang, "community_no_posts")}</p>
            <p className="text-sm text-muted-foreground mt-1">
              {t(lang, "community_no_posts_sub")}
            </p>
          </div>
        )}

        {/* Post list with dividers */}
        {allPosts.length > 0 && (
          <div className="divide-y divide-border/50">
            {allPosts.map((post, i) => {
              const pageIndex = data?.pages.findIndex((page) =>
                page.posts.some((p) => p.id === post.id)
              );
              const isFirstPage = pageIndex === 0;
              return (
                <PostCard
                  key={post.id}
                  post={post}
                  index={i}
                  lang={lang}
                  isFirstPage={isFirstPage}
                  onBookmarkToggle={handleBookmarkToggle}
                />
              );
            })}
          </div>
        )}

        {/* Infinite scroll observer target */}
        <div ref={observerRef} className="h-10" />

        {/* Loading more indicator */}
        {isFetchingNextPage && (
          <div className="py-4 text-center text-xs text-muted-foreground">
            {t(lang, "community_loading_more")}
          </div>
        )}

        {/* No more posts */}
        {!hasNextPage && allPosts.length > 0 && !isLoading && (
          <div className="py-6 text-center text-xs text-muted-foreground">
            {t(lang, "community_no_more")}
          </div>
        )}
      </div>

      {/* FAB button */}
      {user && (
        <Link
          href="/community/new"
          className="fixed bottom-20 right-4 z-30 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center hover:bg-primary/90 active:scale-95 transition-all"
        >
          <Plus className="w-6 h-6" />
        </Link>
      )}
    </div>
  );
}

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
  ChevronRight,
  Loader2,
  X,
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

const TYPE_LABEL: Record<string, string> = {
  discussion: "community_type_discussion",
  analysis: "community_type_analysis",
  question: "community_type_question",
  notice: "community_type_notice",
};

function PlanBadge({ plan }: { plan?: string | null }) {
  if (!plan || plan === "free") return null;
  if (plan === "pro_plus")
    return (
      <span className="inline-flex items-center rounded-full px-1.5 py-px text-[9px] font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-sm">
        Pro+
      </span>
    );
  return (
    <span className="inline-flex items-center rounded-full px-1.5 py-px text-[9px] font-bold bg-gradient-to-r from-blue-500 to-cyan-400 text-white shadow-sm">
      Pro
    </span>
  );
}

function relativeTime(iso: string, lang: Lang): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return t(lang, "home_just_now");
  if (m < 60) return t(lang, "home_minutes_ago", { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t(lang, "home_hours_ago", { n: h });
  const d = Math.floor(h / 24);
  if (d < 30) return t(lang, "community_days_ago", { n: d });
  const locale = lang === "en" ? "en-US" : "ko-KR";
  return new Date(iso).toLocaleDateString(locale, { month: "short", day: "numeric" });
}

/* ── Post row ── */
function PostRow({
  post,
  lang,
  onBookmark,
}: {
  post: Post;
  lang: Lang;
  onBookmark: (id: string) => void;
}) {
  const title = lang === "en" && post.title_en ? post.title_en : post.title;
  const typeLabelKey = TYPE_LABEL[post.post_type];
  const typeText = typeLabelKey
    ? t(lang, typeLabelKey as Parameters<typeof t>[1])
    : post.post_type;
  const preview = post.content ? post.content.replace(/[#*>\-\[\]()]/g, "").slice(0, 80) : "";
  const imgUrl =
    post.images && post.images.length > 0
      ? post.images[0].startsWith("http")
        ? post.images[0]
        : `${API_BASE}${post.images[0]}`
      : null;

  return (
    <Link
      href={communityPostPath(post.id)}
      className="flex gap-3 px-4 py-3.5 cursor-pointer active:bg-gray-50 dark:active:bg-white/5 transition-colors"
    >
      {/* Text content */}
      <div className="flex-1 min-w-0">
        {/* Title */}
        <p className="text-[15px] font-semibold leading-snug text-foreground line-clamp-2">
          {post.is_pinned && (
            <Pin className="inline w-3.5 h-3.5 text-primary mr-1 -mt-0.5 shrink-0" />
          )}
          {title}
        </p>

        {/* Content preview */}
        {preview && (
          <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground line-clamp-2">
            {preview}
          </p>
        )}

        {/* Meta */}
        <div className="flex items-center gap-1.5 mt-2 text-[11px] text-muted-foreground/80">
          <span className="font-medium text-foreground/60">
            {post.author_nickname || t(lang, "community_anonymous")}
          </span>
          <PlanBadge plan={post.author_plan} />
          <span className="text-muted-foreground/40">·</span>
          <span>{relativeTime(post.created_at, lang)}</span>
          <span className="text-muted-foreground/40">·</span>
          <span>{typeText}</span>
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
                onBookmark(post.id);
              }}
              className="p-0.5 -m-0.5 cursor-pointer"
            >
              <Bookmark
                className={`w-3 h-3 transition-colors ${
                  post.is_bookmarked
                    ? "fill-primary text-primary"
                    : "text-muted-foreground/60 hover:text-muted-foreground"
                }`}
              />
            </button>
          </span>
        </div>
      </div>

      {/* Thumbnail */}
      {imgUrl && (
        <div className="w-14 h-14 rounded-md overflow-hidden shrink-0 bg-muted self-start mt-0.5">
          <img
            src={imgUrl}
            alt=""
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>
      )}
    </Link>
  );
}

/* ── Main page ── */
export default function CommunityPage() {
  const { user } = useAuth();
  const lang = useAppStore((s) => s.lang);
  const queryClient = useQueryClient();

  const [activeType, setActiveType] = useState<PostType>("all");
  const [sortBy, setSortBy] = useState<SortBy>("latest");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery.trim()), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    if (showSearch) searchInputRef.current?.focus();
  }, [showSearch]);

  /* Infinite scroll */
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
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    initialPageParam: undefined as string | undefined,
  });

  /* Hot topics */
  const { data: hotTopics } = useQuery<Post[]>({
    queryKey: ["hot-topics", activeType],
    queryFn: async () => {
      const p = new URLSearchParams();
      if (activeType !== "all") p.append("post_type", activeType);
      const res = await fetch(`${API_BASE}/community/hot-topics?${p}`);
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 60_000,
  });

  /* Pinned notices */
  const { data: pinnedNotices } = useQuery<Post[]>({
    queryKey: ["pinned-notices"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/community/pinned-notices`);
      if (!res.ok) return [];
      return res.json();
    },
    staleTime: 60_000,
    enabled: activeType !== "notice",
  });

  /* Observer */
  const sentinelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([e]) => {
        if (e.isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage();
      },
      { threshold: 0.1 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  /* Bookmark toggle */
  const handleBookmark = useCallback(
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
                p.id === postId ? { ...p, is_bookmarked: result.bookmarked } : p,
              ),
            })),
          };
        });
      } catch { /* silent */ }
    },
    [user, queryClient],
  );

  const allPosts = data?.pages.flatMap((p) => p.posts) ?? [];

  return (
    <div className="flex flex-col bg-background" style={{ height: "calc(100dvh - 60px)" }}>
      {/* ── Header ── */}
      <header className="sticky top-0 z-20 bg-background border-b border-border">
        {/* Title bar */}
        <div className="flex items-center justify-between px-4 h-11">
          <h1 className="text-[17px] font-bold tracking-tight">
            {t(lang, "community_title")}
          </h1>
          <div className="flex items-center gap-1">
            <button
              onClick={() => {
                setShowSearch(!showSearch);
                if (showSearch) setSearchQuery("");
              }}
              className="p-2 rounded-full text-muted-foreground hover:bg-muted/50 cursor-pointer transition-colors"
              aria-label="Search"
            >
              {showSearch ? <X className="w-[18px] h-[18px]" /> : <Search className="w-[18px] h-[18px]" />}
            </button>
            {user && (
              <Link
                href="/community/bookmarks"
                className="p-2 rounded-full text-muted-foreground hover:bg-muted/50 cursor-pointer transition-colors"
                aria-label="Bookmarks"
              >
                <Bookmark className="w-[18px] h-[18px]" />
              </Link>
            )}
          </div>
        </div>

        {/* Search */}
        {showSearch && (
          <div className="px-4 pb-2.5">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/50" />
              <input
                ref={searchInputRef}
                type="text"
                placeholder={t(lang, "community_search_placeholder")}
                className="w-full pl-9 pr-4 py-2 rounded-lg bg-muted/40 text-sm placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Tabs + Sort */}
        <div className="flex items-center">
          <div className="flex flex-1 overflow-x-auto scrollbar-hide">
            {TYPES.map((tp) => (
              <button
                key={tp.value}
                onClick={() => setActiveType(tp.value)}
                className={`shrink-0 px-4 py-2.5 text-[13px] font-medium border-b-2 cursor-pointer transition-colors ${
                  activeType === tp.value
                    ? "border-foreground text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground/70"
                }`}
              >
                {t(lang, tp.labelKey as Parameters<typeof t>[1])}
              </button>
            ))}
          </div>
          <button
            onClick={() => setSortBy(sortBy === "latest" ? "popular" : "latest")}
            className="shrink-0 px-3 py-2.5 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
          >
            {sortBy === "latest"
              ? t(lang, "community_sort_latest")
              : t(lang, "community_sort_popular")}
          </button>
        </div>
      </header>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto">
        {/* Pinned notices */}
        {activeType !== "notice" && pinnedNotices && pinnedNotices.length > 0 && (
          <div className="bg-primary/5 dark:bg-primary/10 border-b border-primary/10">
            {pinnedNotices.map((n) => (
              <Link
                key={n.id}
                href={communityPostPath(n.id)}
                className="flex items-center gap-2.5 px-4 py-2.5 cursor-pointer hover:bg-primary/10 dark:hover:bg-primary/15 transition-colors"
              >
                <span className="flex items-center justify-center w-5 h-5 rounded bg-primary/15 shrink-0">
                  <Pin className="w-3 h-3 text-primary" />
                </span>
                <span className="text-[13px] font-medium truncate flex-1 text-foreground">
                  {lang === "en" && n.title_en ? n.title_en : n.title}
                </span>
                <ChevronRight className="w-3.5 h-3.5 text-primary/40 shrink-0" />
              </Link>
            ))}
          </div>
        )}

        {/* Hot topics */}
        {hotTopics && hotTopics.length > 0 && !debouncedSearch && (
          <div className="bg-orange-50/80 dark:bg-orange-500/5 border-b border-orange-200/40 dark:border-orange-500/10 px-4 pt-3 pb-2">
            <h2 className="text-[11px] font-bold text-orange-600/70 dark:text-orange-400/70 uppercase tracking-wider mb-1.5">
              {t(lang, "community_hot_topics")}
            </h2>
            {hotTopics.slice(0, 5).map((post, i) => (
              <Link
                key={post.id}
                href={communityPostPath(post.id)}
                className="flex items-center gap-2.5 py-1.5 cursor-pointer group"
              >
                <span className={`text-[12px] font-bold w-4 text-center ${
                  i < 3 ? "text-orange-500 dark:text-orange-400" : "text-muted-foreground/50"
                }`}>
                  {i + 1}
                </span>
                <span className="text-[13px] text-foreground/90 truncate flex-1 group-hover:text-foreground transition-colors">
                  {lang === "en" && post.title_en ? post.title_en : post.title}
                </span>
              </Link>
            ))}
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="py-20 flex justify-center">
            <Loader2 className="w-5 h-5 animate-spin text-muted-foreground/50" />
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
          <div className="py-20 text-center">
            <p className="text-sm text-muted-foreground">{t(lang, "community_no_posts")}</p>
            <p className="text-xs text-muted-foreground/60 mt-1">{t(lang, "community_no_posts_sub")}</p>
          </div>
        )}

        {/* Post list */}
        {allPosts.length > 0 && (
          <div className="divide-y divide-border/60">
            {allPosts.map((post) => (
              <PostRow
                key={post.id}
                post={post}
                lang={lang}
                onBookmark={handleBookmark}
              />
            ))}
          </div>
        )}

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="h-10" />

        {isFetchingNextPage && (
          <div className="py-4 flex justify-center">
            <Loader2 className="w-4 h-4 animate-spin text-muted-foreground/50" />
          </div>
        )}

        {!hasNextPage && allPosts.length > 0 && !isLoading && (
          <div className="py-8 text-center text-[11px] text-muted-foreground/50">
            {t(lang, "community_no_more")}
          </div>
        )}
      </div>

      {/* FAB */}
      {user && (
        <Link
          href="/community/new"
          className="fixed bottom-20 right-4 z-30 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/25 flex items-center justify-center cursor-pointer active:scale-95 transition-transform"
        >
          <Plus className="w-6 h-6" />
        </Link>
      )}
    </div>
  );
}

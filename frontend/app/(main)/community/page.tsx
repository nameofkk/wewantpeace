"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { MessageSquare, Eye, ThumbsUp, ThumbsDown, Plus, FileText, HelpCircle, TrendingUp, ChevronDown, ChevronUp, ArrowUpDown } from "lucide-react";
import { LogoIcon } from "@/components/ui/logo-icon";
import { cn } from "@/lib/utils";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";

type PostType = "all" | "discussion" | "analysis" | "question";
type SortBy = "latest" | "popular";

const POST_TYPE_ICONS = {
  discussion: MessageSquare,
  analysis: FileText,
  question: HelpCircle,
};

interface Post {
  id: string;
  post_type: string;
  cluster_id?: string | null;
  cluster_title?: string | null;      // English
  cluster_title_ko?: string | null;   // Korean
  title: string;
  author_nickname?: string;
  author_plan?: string | null;
  created_at: string;
  view_count: number;
  comment_count: number;
  like_count: number;
  dislike_count: number;
}

function relativeTime(iso: string, lang: Lang): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return t(lang, "home_just_now");
  if (m < 60) return t(lang, "home_minutes_ago", { n: m });
  const h = Math.floor(m / 60);
  if (h < 24) return t(lang, "home_hours_ago", { n: h });
  return t(lang, "community_days_ago", { n: Math.floor(h / 24) });
}

function PlanBadge({ plan }: { plan?: string | null }) {
  if (!plan || plan === "free") return null;
  if (plan === "pro_plus") return (
    <span className="inline-flex items-center rounded-full bg-gradient-to-r from-blue-600 to-purple-600 px-1.5 py-0.5 text-[9px] font-bold text-white">Pro+</span>
  );
  return (
    <span className="inline-flex items-center rounded-full bg-yellow-500/20 px-1.5 py-0.5 text-[9px] font-bold text-yellow-400">Pro</span>
  );
}

function PostCard({ post, index = 0, lang }: { post: Post; index?: number; lang: Lang }) {
  const Icon = POST_TYPE_ICONS[post.post_type as keyof typeof POST_TYPE_ICONS] || MessageSquare;
  const typeKey = `community_type_${post.post_type}` as Parameters<typeof t>[1];
  return (
    <Link href={`/community/${post.id}`}>
      <div
        className="card-enter rounded-xl border border-border bg-card p-4 hover:bg-card/80 transition-colors cursor-pointer"
        style={{ animationDelay: `${index * 60}ms` }}
      >
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap mb-1">
              <span className="inline-flex items-center gap-1 rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium">
                <Icon className="h-2.5 w-2.5" />
                {t(lang, typeKey) || post.post_type}
              </span>
              {post.cluster_id && (
                <span className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] text-blue-400 max-w-[180px] truncate">
                  {lang === "en"
                    ? (post.cluster_title || t(lang, "community_linked_issue"))
                    : (post.cluster_title_ko || post.cluster_title || t(lang, "community_linked_issue"))}
                </span>
              )}
            </div>
            <h3 className="text-sm font-semibold leading-snug line-clamp-2">{post.title}</h3>
            <p className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
              {post.author_nickname || t(lang, "community_anonymous")}
              <PlanBadge plan={post.author_plan} />
              · {relativeTime(post.created_at, lang)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-2.5 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{post.view_count}</span>
          <span className="flex items-center gap-1"><MessageSquare className="h-3 w-3" />{post.comment_count}</span>
          <span className="flex items-center gap-1"><ThumbsUp className="h-3 w-3" />{post.like_count}</span>
          {post.dislike_count > 0 && (
            <span className="flex items-center gap-1 text-red-400/70"><ThumbsDown className="h-3 w-3" />{post.dislike_count}</span>
          )}
        </div>
      </div>
    </Link>
  );
}

export default function CommunityPage() {
  const router = useRouter();
  const { user } = useAuth();
  const lang = useAppStore((s) => s.lang);
  const [activeType, setActiveType] = useState<PostType>("all");
  const [sortBy, setSortBy] = useState<SortBy>("latest");
  const [hotTopicsOpen, setHotTopicsOpen] = useState(true);
  const { data: posts, isLoading, isError } = useQuery<Post[]>({
    queryKey: ["community-posts", activeType, sortBy],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "20", sort_by: sortBy });
      if (activeType !== "all") params.append("post_type", activeType);
      const res = await fetch(`${API_BASE}/community/posts?${params}`);
      if (!res.ok) throw new Error("게시글 로드 실패");
      return res.json();
    },
    refetchOnMount: "always",
    staleTime: 0,
  });

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

  const tabs: { key: PostType; label: string }[] = [
    { key: "all", label: t(lang, "community_type_all") },
    { key: "discussion", label: t(lang, "community_type_discussion") },
    { key: "analysis", label: t(lang, "community_type_analysis") },
    { key: "question", label: t(lang, "community_type_question") },
  ];

  return (
    <div className="flex flex-col" style={{ height: "calc(100dvh - 60px)" }}>
      {/* 헤더 */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 pt-4 pb-0">
        <div className="grid grid-cols-3 items-center mb-3">
          {/* 왼쪽 */}
          <div className="flex items-center min-w-0 overflow-hidden">
            <h1 className="text-sm font-bold truncate">{t(lang, "community_title")}</h1>
          </div>
          {/* 중앙 — 로고 */}
          <div className="flex justify-center">
            <LogoIcon height={26} hideText />
          </div>
          {/* 오른쪽 — 아이콘 버튼만 */}
          <div className="flex items-center justify-end gap-2">
            <button
              onClick={() => setSortBy(sortBy === "latest" ? "popular" : "latest")}
              className={cn(
                "flex items-center justify-center rounded-full border p-1.5 transition-colors",
                sortBy === "popular"
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              )}
              title={sortBy === "latest" ? t(lang, "community_sort_latest") : t(lang, "community_sort_popular")}
            >
              <ArrowUpDown className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={() => user ? router.push("/community/new") : router.push("/login")}
              className="flex items-center justify-center rounded-full bg-primary p-1.5"
            >
              <Plus className="h-3.5 w-3.5 text-primary-foreground" />
            </button>
          </div>
        </div>

        <p className="text-[11px] text-muted-foreground mb-3 -mt-1">
          {t(lang, "community_subtitle")}
        </p>

        {/* 탭 */}
        <div className="flex gap-0">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveType(tab.key)}
              className={cn(
                "flex-1 py-2.5 text-sm font-medium border-b-2 transition-colors",
                activeType === tab.key ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 게시글 목록 */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">

        {/* 핫토픽 섹션 */}
        {hotTopics && hotTopics.length > 0 && (
          <div className="rounded-xl border border-border bg-card overflow-hidden">
            <button
              onClick={() => setHotTopicsOpen(!hotTopicsOpen)}
              className="flex items-center justify-between w-full px-4 py-3 text-sm font-semibold hover:bg-secondary/30 transition-colors"
            >
              <div className="flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-orange-400" />
                <span>{t(lang, "community_hot_topics")}</span>
              </div>
              {hotTopicsOpen ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
            </button>
            {hotTopicsOpen && (
              <div className="overflow-x-auto">
                <div className="flex gap-3 px-4 pb-4" style={{ minWidth: "max-content" }}>
                  {hotTopics.map((post, i) => (
                    <Link key={post.id} href={`/community/${post.id}`}>
                      <div
                        className="fade-in-up w-48 rounded-lg border border-border bg-background p-3 hover:bg-secondary/30 transition-colors cursor-pointer flex-shrink-0"
                        style={{ animationDelay: `${i * 80}ms` }}
                      >
                        <div className="flex items-center gap-1 mb-1.5">
                          <span className="text-[11px] font-bold text-orange-400">#{i + 1}</span>
                          <span className="text-[10px] text-muted-foreground truncate flex-1">{post.author_nickname || t(lang, "community_anonymous")}</span>
                        </div>
                        <p className="text-xs font-medium line-clamp-2 leading-snug">{post.title}</p>
                        <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
                          <span className="flex items-center gap-0.5"><ThumbsUp className="h-2.5 w-2.5" />{post.like_count}</span>
                          <span className="flex items-center gap-0.5"><Eye className="h-2.5 w-2.5" />{post.view_count}</span>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {isLoading && (
          <div className="space-y-3">
            {[0, 1, 2].map(i => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse">
                <div className="h-4 w-3/4 rounded bg-secondary mb-2" />
                <div className="h-3 w-1/2 rounded bg-secondary" />
              </div>
            ))}
          </div>
        )}

        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            {t(lang, "community_load_error")}
          </div>
        )}

        {!isLoading && !isError && posts?.length === 0 && (
          <div className="py-16 text-center">
            <MessageSquare className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm font-medium">{t(lang, "community_no_posts")}</p>
            <p className="text-sm text-muted-foreground mt-1">{t(lang, "community_no_posts_sub")}</p>
          </div>
        )}

        {posts?.map((post, i) => <PostCard key={post.id} post={post} index={i} lang={lang} />)}
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, MessageSquare, Eye, ThumbsUp, Pencil, Trash2, Loader2 } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";

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

interface Post {
  id: string;
  post_type: string;
  title: string;
  created_at: string;
  view_count: number;
  comment_count: number;
  like_count: number;
}

export default function MyPostsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const lang = useAppStore((s) => s.lang);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const { data: posts, isLoading, isError } = useQuery<Post[]>({
    queryKey: ["my-posts"],
    queryFn: async () => {
      if (!user) throw new Error("Login required");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/community/my-posts?limit=50`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to fetch");
      return res.json();
    },
    enabled: !!user && !authLoading,
  });

  const deleteMutation = useMutation({
    mutationFn: async (postId: string) => {
      if (!user) throw new Error("Login required");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/community/posts/${postId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Delete failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["my-posts"] });
      queryClient.invalidateQueries({ queryKey: ["community-posts"] });
      setDeletingId(null);
    },
    onError: () => {
      setDeletingId(null);
    },
  });

  async function handleDelete(postId: string) {
    if (!window.confirm(t(lang, "my_posts_delete_confirm"))) return;
    setDeletingId(postId);
    deleteMutation.mutate(postId);
  }

  if (!authLoading && !user) {
    router.replace("/login");
    return null;
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* 헤더 */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <Link href="/community" className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-base font-bold flex-1">{t(lang, "my_posts_title")}</h1>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {(isLoading || authLoading) && (
          <div className="flex justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {isError && (
          <div className="py-16 text-center text-muted-foreground text-sm">
            {t(lang, "my_posts_error")}
          </div>
        )}

        {!isLoading && !isError && posts?.length === 0 && (
          <div className="py-16 text-center">
            <MessageSquare className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm font-medium">{t(lang, "my_posts_empty_title")}</p>
            <Link href="/community/new" className="mt-2 inline-block text-sm text-primary hover:underline">
              {t(lang, "my_posts_empty_link")}
            </Link>
          </div>
        )}

        {posts?.map((post) => (
          <div key={post.id} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-start gap-2">
              <Link href={`/community/${post.id}`} className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium">
                    {t(lang, `community_type_${post.post_type}` as Parameters<typeof t>[1]) || post.post_type}
                  </span>
                </div>
                <h3 className="text-sm font-semibold leading-snug line-clamp-2">{post.title}</h3>
                <p className="mt-1 text-xs text-muted-foreground">{relativeTime(post.created_at, lang)}</p>
                <div className="flex items-center gap-3 mt-2 text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{post.view_count}</span>
                  <span className="flex items-center gap-1"><MessageSquare className="h-3 w-3" />{post.comment_count}</span>
                  <span className="flex items-center gap-1"><ThumbsUp className="h-3 w-3" />{post.like_count}</span>
                </div>
              </Link>
              <div className="flex items-center gap-2 shrink-0 mt-1">
                <Link
                  href={`/community/${post.id}/edit`}
                  className="rounded-lg border border-border p-2 text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Link>
                <button
                  onClick={() => handleDelete(post.id)}
                  disabled={deletingId === post.id}
                  className="rounded-lg border border-border p-2 text-muted-foreground hover:text-destructive hover:border-destructive/40 transition-colors disabled:opacity-50"
                >
                  {deletingId === post.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

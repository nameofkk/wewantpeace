"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Flag,
  Trash2,
  Loader2,
  Send,
  Pencil,
  Check,
  X,
  Pin,
  Bookmark,
  Eye,
} from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE, useMe, toggleBookmark } from "@/lib/api";
import MarkdownContent from "@/components/community/MarkdownContent";

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

interface Comment {
  id: string;
  user_id: string | null;
  content: string;
  content_en?: string | null;
  author_nickname: string | null;
  created_at: string;
  like_count: number;
  parent_id: string | null;
  replies?: Comment[];
}

interface Post {
  id: string;
  user_id: string | null;
  title: string;
  title_en?: string | null;
  content: string;
  content_en?: string | null;
  post_type: string;
  author_nickname: string | null;
  author_plan: string | null;
  created_at: string;
  updated_at: string;
  view_count: number;
  comment_count: number;
  like_count: number;
  dislike_count: number;
  is_pinned: boolean;
  images: string[];
  cluster_id: string | null;
  cluster_title: string | null;
  cluster_title_ko: string | null;
}

function PlanBadge({ plan }: { plan?: string | null }) {
  if (!plan || plan === "free") return null;
  if (plan === "pro_plus")
    return (
      <span className="inline-flex items-center rounded px-1 py-px text-[9px] font-bold bg-blue-500/15 text-blue-500">
        Pro+
      </span>
    );
  return (
    <span className="inline-flex items-center rounded px-1 py-px text-[9px] font-bold bg-amber-500/15 text-amber-600 dark:text-amber-400">
      Pro
    </span>
  );
}

/* ── Comment ── */
function CommentItem({
  comment,
  onReply,
  onLike,
  onDelete,
  depth = 0,
  lang,
  myUserId,
  editingCommentId,
  editCommentText,
  onEditStart,
  onEditSave,
  onEditCancel,
  onEditTextChange,
}: {
  comment: Comment;
  onReply: (parentId: string, parentNick: string) => void;
  onLike: (commentId: string) => void;
  onDelete: (commentId: string) => void;
  depth?: number;
  lang: Lang;
  myUserId?: string | null;
  editingCommentId?: string | null;
  editCommentText?: string;
  onEditStart: (commentId: string, content: string) => void;
  onEditSave: (commentId: string) => void;
  onEditCancel: () => void;
  onEditTextChange: (text: string) => void;
}) {
  const isDeleted =
    comment.content === "[삭제된 댓글입니다]" || comment.content === "[Deleted comment]";
  const isMine = !!(myUserId && comment.user_id && comment.user_id === myUserId);
  const isEditing = editingCommentId === comment.id;

  return (
    <div className={cn("", depth > 0 && "ml-5 pl-3 border-l-2 border-border/60")}>
      <div className="py-3">
        {/* Header */}
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5">
            <span className="text-[13px] font-semibold text-foreground/90">
              {comment.author_nickname || t(lang, "community_anonymous")}
            </span>
            <span className="text-[11px] text-muted-foreground/60">
              {relativeTime(comment.created_at, lang)}
            </span>
          </div>
          {isMine && !isDeleted && !isEditing && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => onEditStart(comment.id, comment.content)}
                className="text-muted-foreground/50 hover:text-foreground cursor-pointer transition-colors"
              >
                <Pencil className="h-3 w-3" />
              </button>
              <button
                onClick={() => onDelete(comment.id)}
                className="text-muted-foreground/50 hover:text-destructive cursor-pointer transition-colors"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* Body */}
        {isEditing ? (
          <div className="mt-2">
            <textarea
              value={editCommentText}
              onChange={(e) => onEditTextChange(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-primary/40 bg-background px-3 py-2 text-sm outline-none resize-none focus:ring-2 focus:ring-primary/20"
              autoFocus
            />
            <div className="flex gap-2 mt-1.5 justify-end">
              <button
                onClick={() => onEditSave(comment.id)}
                className="flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground cursor-pointer"
              >
                <Check className="h-3 w-3" />
                {lang === "ko" ? "저장" : "Save"}
              </button>
              <button
                onClick={onEditCancel}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
              >
                <X className="h-3 w-3" />
                {lang === "ko" ? "취소" : "Cancel"}
              </button>
            </div>
          </div>
        ) : (
          <p
            className={cn(
              "mt-1 text-[14px] leading-relaxed",
              isDeleted && "text-muted-foreground italic",
            )}
          >
            {lang === "en" && comment.content_en ? comment.content_en : comment.content}
          </p>
        )}

        {/* Actions */}
        {!isEditing && (
          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={() => onLike(comment.id)}
              className="flex items-center gap-1 text-[11px] text-muted-foreground/70 hover:text-primary cursor-pointer transition-colors"
            >
              <ThumbsUp className="h-3 w-3" />
              {comment.like_count > 0 && comment.like_count}
            </button>
            {depth === 0 && !isDeleted && (
              <button
                onClick={() =>
                  onReply(comment.id, comment.author_nickname || t(lang, "community_anonymous"))
                }
                className="text-[11px] text-muted-foreground/70 hover:text-primary cursor-pointer transition-colors"
              >
                {t(lang, "post_reply")}
              </button>
            )}
          </div>
        )}
      </div>

      {comment.replies?.map((reply) => (
        <CommentItem
          key={reply.id}
          comment={reply}
          onReply={onReply}
          onLike={onLike}
          onDelete={onDelete}
          depth={depth + 1}
          lang={lang}
          myUserId={myUserId}
          editingCommentId={editingCommentId}
          editCommentText={editCommentText}
          onEditStart={onEditStart}
          onEditSave={onEditSave}
          onEditCancel={onEditCancel}
          onEditTextChange={onEditTextChange}
        />
      ))}
    </div>
  );
}

/* ── Detail page ── */
export default function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const lang = useAppStore((s) => s.lang);

  const { data: me } = useMe();
  const isAdmin = (me as { role?: string } | undefined)?.role === "admin";

  const { data: myUserId } = useQuery<string | null>({
    queryKey: ["my-user-id", user?.uid],
    queryFn: async () => {
      if (!user) return null;
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return null;
      const data = await res.json();
      return data.id as string;
    },
    enabled: !!user,
    staleTime: 5 * 60 * 1000,
  });

  const [commentText, setCommentText] = useState("");
  const [replyTo, setReplyTo] = useState<{ id: string; nick: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [lightboxIdx, setLightboxIdx] = useState<number | null>(null);
  const [editingCommentId, setEditingCommentId] = useState<string | null>(null);
  const [editCommentText, setEditCommentText] = useState("");
  const [isBookmarked, setIsBookmarked] = useState(false);

  const {
    data: post,
    isLoading: postLoading,
    isError: postError,
  } = useQuery<Post>({
    queryKey: ["post", postId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/community/posts/${postId}`);
      if (!res.ok) throw new Error("load failed");
      return res.json();
    },
  });

  const { data: comments = [], isLoading: commentsLoading } = useQuery<Comment[]>({
    queryKey: ["comments", postId],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/community/posts/${postId}/comments?limit=100`);
      if (!res.ok) throw new Error("load failed");
      return res.json();
    },
    enabled: !!postId,
  });

  const reactMutation = useMutation({
    mutationFn: async (reactionType: "like" | "dislike") => {
      if (!user) throw new Error("login required");
      const token = await user.getIdToken();
      await fetch(`${API_BASE}/community/posts/${postId}/react`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ reaction_type: reactionType }),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["post", postId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      if (!user) throw new Error("login required");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/community/posts/${postId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("delete failed");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["community-posts"] });
      router.push("/community");
    },
  });

  async function handleCommentSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!user) {
      router.push("/login");
      return;
    }
    if (!commentText.trim()) return;
    setSubmitting(true);
    try {
      const token = await user.getIdToken();
      const body: Record<string, unknown> = { content: commentText.trim() };
      if (replyTo) body.parent_id = replyTo.id;
      const res = await fetch(`${API_BASE}/community/posts/${postId}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error("comment failed");
      setCommentText("");
      setReplyTo(null);
      queryClient.invalidateQueries({ queryKey: ["comments", postId] });
      queryClient.invalidateQueries({ queryKey: ["post", postId] });
    } catch {
      /* silent */
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCommentLike(commentId: string) {
    if (!user) {
      router.push("/login");
      return;
    }
    const token = await user.getIdToken();
    await fetch(`${API_BASE}/community/comments/${commentId}/react`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ reaction_type: "like" }),
    });
    queryClient.invalidateQueries({ queryKey: ["comments", postId] });
  }

  async function handleCommentDelete(commentId: string) {
    if (!user) return;
    if (!window.confirm(lang === "ko" ? "댓글을 삭제할까요?" : "Delete this comment?")) return;
    const token = await user.getIdToken();
    await fetch(`${API_BASE}/community/comments/${commentId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    queryClient.invalidateQueries({ queryKey: ["comments", postId] });
  }

  async function handleCommentEditSave(commentId: string) {
    if (!user || !editCommentText.trim()) return;
    const token = await user.getIdToken();
    const res = await fetch(`${API_BASE}/community/comments/${commentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ content: editCommentText.trim() }),
    });
    if (res.ok) {
      setEditingCommentId(null);
      setEditCommentText("");
      queryClient.invalidateQueries({ queryKey: ["comments", postId] });
    }
  }

  async function handleReport() {
    if (!user) {
      router.push("/login");
      return;
    }
    const reason = window.prompt(t(lang, "post_report_prompt"));
    if (!reason) return;
    const token = await user.getIdToken();
    await fetch(`${API_BASE}/community/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ target_type: "post", target_id: postId, reason }),
    });
    alert(t(lang, "post_report_done"));
  }

  async function handleBookmarkToggle() {
    if (!user) return;
    try {
      const result = await toggleBookmark(post!.id);
      setIsBookmarked(result.bookmarked);
    } catch {
      /* silent */
    }
  }

  async function handleTogglePin() {
    if (!user) return;
    const token = await user.getIdToken();
    const res = await fetch(`${API_BASE}/community/posts/${postId}/pin`, {
      method: "PATCH",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      queryClient.invalidateQueries({ queryKey: ["post", postId] });
      queryClient.invalidateQueries({ queryKey: ["pinned-notices"] });
      queryClient.invalidateQueries({ queryKey: ["community-posts"] });
    }
  }

  async function handleDelete() {
    if (!window.confirm(t(lang, "post_delete_confirm"))) return;
    deleteMutation.mutate();
  }

  /* ── Loading / Error ── */
  if (postLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/50" />
      </div>
    );
  }

  if (postError || !post) {
    return (
      <div className="flex flex-col h-64 items-center justify-center gap-3">
        <p className="text-sm text-muted-foreground">{t(lang, "post_load_error")}</p>
        <Link href="/community" className="text-sm text-primary hover:underline cursor-pointer">
          {t(lang, "post_back")}
        </Link>
      </div>
    );
  }

  const isMyPost = !!(myUserId && post.user_id && post.user_id === myUserId);
  const topLevel = comments.filter((c) => !c.parent_id);
  const replies = comments.filter((c) => c.parent_id);
  const commentTree: Comment[] = topLevel.map((c) => ({
    ...c,
    replies: replies.filter((r) => r.parent_id === c.id),
  }));

  const typeKey = `community_type_${post.post_type}` as Parameters<typeof t>[1];
  const typeLabel = t(lang, typeKey) || post.post_type;
  const displayContent = lang === "en" && post.content_en ? post.content_en : post.content;

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* ── Header ── */}
      <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-border bg-background px-2 h-11">
        <button
          onClick={() => router.back()}
          className="p-2 text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
        <span className="text-[15px] font-semibold flex-1 truncate">
          {t(lang, "post_header")}
        </span>
        <div className="flex items-center gap-0.5">
          <button
            onClick={handleBookmarkToggle}
            className="p-2 cursor-pointer transition-colors"
          >
            <Bookmark
              className={`w-[18px] h-[18px] ${
                isBookmarked
                  ? "fill-primary text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            />
          </button>
          <button
            onClick={handleReport}
            className="p-2 text-muted-foreground hover:text-destructive cursor-pointer transition-colors"
          >
            <Flag className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* ── Post content ── */}
      <article className="px-4 pt-4 pb-3">
        {/* Type + Pinned + Cluster */}
        <div className="flex items-center gap-2 mb-3 flex-wrap">
          <span className="text-[11px] font-medium px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
            {typeLabel}
          </span>
          {post.is_pinned && (
            <span className="flex items-center gap-0.5 text-[11px] text-primary font-medium">
              <Pin className="h-2.5 w-2.5" />
              {t(lang, "community_pinned_notice")}
            </span>
          )}
          {post.cluster_id && (
            <Link
              href={`/issues/${post.cluster_id}`}
              className="text-[11px] text-blue-500 hover:underline truncate max-w-[200px] cursor-pointer"
            >
              {lang === "en"
                ? post.cluster_title || t(lang, "community_linked_issue")
                : post.cluster_title_ko || post.cluster_title || t(lang, "community_linked_issue")}
            </Link>
          )}
        </div>

        {/* Title */}
        <h1 className="text-[18px] font-bold leading-snug text-foreground mb-3">
          {lang === "en" && post.title_en ? post.title_en : post.title}
        </h1>

        {/* Author info */}
        <div className="flex items-center justify-between mb-4 pb-3 border-b border-border/60">
          <div className="flex items-center gap-1.5 text-[13px]">
            <span className="font-medium text-foreground/80">
              {post.author_nickname || t(lang, "community_anonymous")}
            </span>
            <PlanBadge plan={post.author_plan} />
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground/70">
            <span>{relativeTime(post.created_at, lang)}</span>
            <span className="text-muted-foreground/30">·</span>
            <span className="flex items-center gap-0.5">
              <Eye className="w-3 h-3" />
              {post.view_count}
            </span>
          </div>
        </div>

        {/* Body */}
        <MarkdownContent content={displayContent} className="mb-4" />

        {/* Images */}
        {post.images && post.images.length > 0 && (
          <div className="mt-4 space-y-2">
            {post.images.map((url, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setLightboxIdx(idx)}
                className="block w-full rounded-lg overflow-hidden border border-border/50 cursor-pointer"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${API_BASE}${url}`}
                  alt={t(lang, "post_img_alt", { n: idx + 1 })}
                  className="w-full object-cover hover:opacity-95 transition-opacity"
                  loading="lazy"
                />
              </button>
            ))}
          </div>
        )}

        {/* Reactions */}
        <div className="flex items-center gap-1 mt-5 pt-3 border-t border-border/60">
          <button
            onClick={() => reactMutation.mutate("like")}
            disabled={reactMutation.isPending}
            className="flex items-center gap-1 px-3 py-1.5 rounded-full text-[13px] text-muted-foreground hover:bg-muted/50 cursor-pointer transition-colors"
          >
            <ThumbsUp className="h-4 w-4" />
            {post.like_count > 0 && <span>{post.like_count}</span>}
          </button>
          <button
            onClick={() => reactMutation.mutate("dislike")}
            disabled={reactMutation.isPending}
            className="flex items-center gap-1 px-3 py-1.5 rounded-full text-[13px] text-muted-foreground hover:bg-muted/50 cursor-pointer transition-colors"
          >
            <ThumbsDown className="h-4 w-4" />
            {post.dislike_count > 0 && <span>{post.dislike_count}</span>}
          </button>
          <span className="flex items-center gap-1 px-3 py-1.5 text-[13px] text-muted-foreground">
            <MessageSquare className="h-4 w-4" />
            {post.comment_count}
          </span>

          {/* Admin / Author actions */}
          {(isMyPost || isAdmin) && (
            <div className="ml-auto flex items-center gap-1">
              {isAdmin && (
                <button
                  onClick={handleTogglePin}
                  className={cn(
                    "flex items-center gap-1 px-2 py-1 rounded-md text-[11px] cursor-pointer transition-colors",
                    post.is_pinned
                      ? "text-primary bg-primary/10"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
                  )}
                >
                  <Pin className="h-3 w-3" />
                  {post.is_pinned ? t(lang, "post_unpin") : t(lang, "post_pin")}
                </button>
              )}
              <Link
                href={`/community/${postId}/edit`}
                className="p-1.5 text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
              >
                <Pencil className="h-3.5 w-3.5" />
              </Link>
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="p-1.5 text-muted-foreground hover:text-destructive cursor-pointer transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          )}
        </div>
      </article>

      {/* ── Comments ── */}
      <section className="border-t-4 border-border/30 bg-background">
        <div className="px-4 pt-3 pb-2">
          <h2 className="text-[14px] font-bold">
            {t(lang, "post_comment_count", { n: comments.length })}
          </h2>
        </div>

        {commentsLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/50" />
          </div>
        )}

        {!commentsLoading && commentTree.length === 0 && (
          <p className="text-sm text-muted-foreground/60 py-8 text-center">
            {t(lang, "post_no_comments")}
          </p>
        )}

        <div className="px-4 divide-y divide-border/50">
          {commentTree.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              lang={lang}
              onReply={(id, nick) => {
                setReplyTo({ id, nick });
                document.getElementById("comment-input")?.focus();
              }}
              onLike={handleCommentLike}
              onDelete={handleCommentDelete}
              myUserId={myUserId}
              editingCommentId={editingCommentId}
              editCommentText={editCommentText}
              onEditStart={(id, content) => {
                setEditingCommentId(id);
                setEditCommentText(content);
              }}
              onEditSave={handleCommentEditSave}
              onEditCancel={() => {
                setEditingCommentId(null);
                setEditCommentText("");
              }}
              onEditTextChange={setEditCommentText}
            />
          ))}
        </div>
      </section>

      {/* ── Comment input ── */}
      <div className="sticky bottom-[60px] border-t border-border bg-background px-4 py-2.5">
        {replyTo && (
          <div className="flex items-center justify-between mb-2 rounded-md bg-muted/40 px-3 py-1.5">
            <span className="text-[12px] text-muted-foreground">
              {t(lang, "post_reply_to", { nick: replyTo.nick })}
            </span>
            <button
              onClick={() => setReplyTo(null)}
              className="text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        <form onSubmit={handleCommentSubmit} className="flex items-end gap-2">
          <textarea
            id="comment-input"
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder={
              user
                ? t(lang, "post_comment_placeholder")
                : t(lang, "post_comment_login_placeholder")
            }
            disabled={!user}
            rows={1}
            className="flex-1 rounded-lg border border-border bg-muted/20 px-3 py-2 text-[14px] outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20 resize-none disabled:opacity-50 transition-all"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey))
                handleCommentSubmit(e as unknown as React.FormEvent);
            }}
          />
          <button
            type="submit"
            disabled={!user || !commentText.trim() || submitting}
            className="rounded-lg bg-primary p-2.5 text-primary-foreground disabled:opacity-40 cursor-pointer transition-opacity"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
        {!user && (
          <button
            onClick={() => router.push("/login")}
            className="mt-1 text-[12px] text-primary hover:underline cursor-pointer"
          >
            {t(lang, "post_login_btn")}
          </button>
        )}
      </div>

      {/* ── Lightbox ── */}
      {lightboxIdx !== null && post.images && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          onClick={() => setLightboxIdx(null)}
        >
          <button
            className="absolute top-4 right-4 text-white/70 hover:text-white text-xl cursor-pointer"
            onClick={() => setLightboxIdx(null)}
          >
            <X className="w-6 h-6" />
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`${API_BASE}${post.images[lightboxIdx]}`}
            alt={t(lang, "post_fullscreen_alt")}
            className="max-w-full max-h-full object-contain"
            onClick={(e) => e.stopPropagation()}
          />
          {post.images.length > 1 && (
            <div className="absolute bottom-4 flex gap-2">
              {post.images.map((_, i) => (
                <button
                  key={i}
                  onClick={(e) => {
                    e.stopPropagation();
                    setLightboxIdx(i);
                  }}
                  className={cn(
                    "h-2 w-2 rounded-full cursor-pointer",
                    i === lightboxIdx ? "bg-white" : "bg-white/40",
                  )}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

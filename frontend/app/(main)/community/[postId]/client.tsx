"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, ThumbsUp, ThumbsDown, MessageSquare, Flag, Trash2, Loader2, Send, Pencil, Check, X } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";

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

interface Comment {
  id: string;
  user_id: string | null;
  content: string;
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
  content: string;
  post_type: string;
  author_nickname: string | null;
  author_plan: string | null;
  created_at: string;
  updated_at: string;
  view_count: number;
  comment_count: number;
  like_count: number;
  dislike_count: number;
  images: string[];
  cluster_id: string | null;
  cluster_title: string | null;      // English
  cluster_title_ko: string | null;   // Korean
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
  const isDeleted = comment.content === "[삭제된 댓글입니다]";
  const isMine = !!(myUserId && comment.user_id && comment.user_id === myUserId);
  const isEditing = editingCommentId === comment.id;

  return (
    <div className={cn("", depth > 0 && "ml-6 border-l-2 border-border pl-4")}>
      <div className="py-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <span className="text-xs font-semibold">{comment.author_nickname || t(lang, "community_anonymous")}</span>
            <span className="ml-2 text-[10px] text-muted-foreground">{relativeTime(comment.created_at, lang)}</span>
          </div>
          {/* 내 댓글 수정/삭제 버튼 */}
          {isMine && !isDeleted && !isEditing && (
            <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => onEditStart(comment.id, comment.content)}
                className="text-[10px] text-muted-foreground hover:text-primary flex items-center gap-0.5"
              >
                <Pencil className="h-3 w-3" />
              </button>
              <button
                onClick={() => onDelete(comment.id)}
                className="text-[10px] text-muted-foreground hover:text-destructive flex items-center gap-0.5"
              >
                <Trash2 className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* 수정 중 인라인 폼 */}
        {isEditing ? (
          <div className="mt-2">
            <textarea
              value={editCommentText}
              onChange={(e) => onEditTextChange(e.target.value)}
              rows={2}
              className="w-full rounded-xl border border-primary bg-card px-3 py-2 text-sm outline-none resize-none"
              autoFocus
            />
            <div className="flex gap-2 mt-1.5 justify-end">
              <button
                onClick={() => onEditSave(comment.id)}
                className="flex items-center gap-1 rounded-lg bg-primary px-2.5 py-1 text-[11px] font-medium text-primary-foreground"
              >
                <Check className="h-3 w-3" />
                {lang === "ko" ? "저장" : "Save"}
              </button>
              <button
                onClick={onEditCancel}
                className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-[11px] text-muted-foreground hover:text-foreground"
              >
                <X className="h-3 w-3" />
                {lang === "ko" ? "취소" : "Cancel"}
              </button>
            </div>
          </div>
        ) : (
          <p className={cn("mt-1 text-sm leading-relaxed", isDeleted && "text-muted-foreground italic")}>
            {comment.content}
          </p>
        )}

        {!isEditing && (
          <div className="flex items-center gap-3 mt-2">
            <button
              onClick={() => onLike(comment.id)}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-primary"
            >
              <ThumbsUp className="h-3 w-3" />
              {comment.like_count}
            </button>
            {depth === 0 && !isDeleted && (
              <button
                onClick={() => onReply(comment.id, comment.author_nickname || t(lang, "community_anonymous"))}
                className="text-[11px] text-muted-foreground hover:text-primary"
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

export default function PostDetailPage() {
  const { postId } = useParams<{ postId: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const lang = useAppStore((s) => s.lang);

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

  const { data: post, isLoading: postLoading, isError: postError } = useQuery<Post>({
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
    if (!user) { router.push("/login"); return; }
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
      // ignore
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCommentLike(commentId: string) {
    if (!user) { router.push("/login"); return; }
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
    if (!user) { router.push("/login"); return; }
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

  async function handleDelete() {
    if (!window.confirm(t(lang, "post_delete_confirm"))) return;
    deleteMutation.mutate();
  }

  if (postLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (postError || !post) {
    return (
      <div className="flex flex-col h-64 items-center justify-center gap-4">
        <p className="text-sm text-muted-foreground">{t(lang, "post_load_error")}</p>
        <Link href="/community" className="text-sm text-primary hover:underline">{t(lang, "post_back")}</Link>
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

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* 헤더 */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <button onClick={() => router.back()} className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-5 w-5" />
        </button>
        <span className="text-sm font-medium flex-1 truncate">{t(lang, "post_header")}</span>
        <button onClick={handleReport} className="text-muted-foreground hover:text-destructive">
          <Flag className="h-4 w-4" />
        </button>
      </div>

      {/* 게시글 */}
      <div className="px-4 pt-4 pb-2">
        <div className="flex items-center gap-2 mb-3">
          <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] font-medium">
            {t(lang, typeKey) || post.post_type}
          </span>
          {post.cluster_id && (
            <Link href={`/issues/${post.cluster_id}`} className="rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] text-blue-400 hover:underline max-w-[200px] truncate inline-block">
              {lang === "en"
                ? (post.cluster_title || t(lang, "community_linked_issue"))
                : (post.cluster_title_ko || post.cluster_title || t(lang, "community_linked_issue"))}
            </Link>
          )}
        </div>
        <h1 className="text-lg font-bold leading-snug">{post.title}</h1>
        <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground flex-wrap">
          <span className="flex items-center gap-1">
            {post.author_nickname || t(lang, "community_anonymous")}
            <PlanBadge plan={post.author_plan} />
          </span>
          <span>·</span>
          <span>{relativeTime(post.created_at, lang)}</span>
          <span>·</span>
          <span>{t(lang, "post_views", { n: post.view_count })}</span>
        </div>

        <div className="mt-4 text-sm leading-relaxed whitespace-pre-wrap">{post.content}</div>

        {/* 이미지 그리드 */}
        {post.images && post.images.length > 0 && (
          <div className="mt-4 grid grid-cols-3 gap-1.5">
            {post.images.map((url, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setLightboxIdx(idx)}
                className="aspect-square rounded-lg overflow-hidden border border-border"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${API_BASE}${url}`}
                  alt={t(lang, "post_img_alt", { n: idx + 1 })}
                  className="w-full h-full object-cover hover:opacity-90 transition-opacity"
                />
              </button>
            ))}
          </div>
        )}

        {/* 반응 + 내 글 수정/삭제 */}
        <div className="flex items-center gap-4 mt-4 pt-4 border-t border-border">
          <button
            onClick={() => reactMutation.mutate("like")}
            disabled={reactMutation.isPending}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary"
          >
            <ThumbsUp className="h-4 w-4" />
            <span>{post.like_count}</span>
          </button>
          <button
            onClick={() => reactMutation.mutate("dislike")}
            disabled={reactMutation.isPending}
            className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-red-400"
          >
            <ThumbsDown className="h-4 w-4" />
            <span>{post.dislike_count}</span>
          </button>
          <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <MessageSquare className="h-4 w-4" />
            <span>{post.comment_count}</span>
          </span>
          {isMyPost && (
            <div className="ml-auto flex items-center gap-2">
              <Link
                href={`/community/${postId}/edit`}
                className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-secondary/50 transition-colors"
              >
                <Pencil className="h-3 w-3" />
                {t(lang, "post_edit")}
              </Link>
              <button
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
                className="flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs text-muted-foreground hover:text-destructive hover:border-destructive/40 transition-colors disabled:opacity-50"
              >
                {deleteMutation.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
                {t(lang, "post_delete")}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 댓글 목록 */}
      <div className="flex-1 px-4 py-2 border-t border-border">
        <h2 className="text-sm font-bold mb-2">{t(lang, "post_comment_count", { n: comments.length })}</h2>

        {commentsLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {!commentsLoading && commentTree.length === 0 && (
          <p className="text-sm text-muted-foreground py-8 text-center">
            {t(lang, "post_no_comments")}
          </p>
        )}

        <div className="divide-y divide-border">
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
              onEditStart={(id, content) => { setEditingCommentId(id); setEditCommentText(content); }}
              onEditSave={handleCommentEditSave}
              onEditCancel={() => { setEditingCommentId(null); setEditCommentText(""); }}
              onEditTextChange={setEditCommentText}
            />
          ))}
        </div>
      </div>

      {/* 댓글 입력 */}
      <div className="sticky bottom-[60px] border-t border-border bg-background px-4 py-3">
        {replyTo && (
          <div className="flex items-center justify-between mb-2 rounded-lg bg-secondary px-3 py-2">
            <span className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">{t(lang, "post_reply_to", { nick: replyTo.nick })}</span>
            </span>
            <button onClick={() => setReplyTo(null)} className="text-muted-foreground hover:text-foreground">
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        )}
        <form onSubmit={handleCommentSubmit} className="flex items-end gap-2">
          <textarea
            id="comment-input"
            value={commentText}
            onChange={(e) => setCommentText(e.target.value)}
            placeholder={user ? t(lang, "post_comment_placeholder") : t(lang, "post_comment_login_placeholder")}
            disabled={!user}
            rows={2}
            className="flex-1 rounded-xl border border-border bg-card px-3 py-2 text-sm outline-none focus:border-primary resize-none disabled:opacity-50"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleCommentSubmit(e as unknown as React.FormEvent);
            }}
          />
          <button
            type="submit"
            disabled={!user || !commentText.trim() || submitting}
            className="rounded-xl bg-primary p-2.5 text-primary-foreground disabled:opacity-50"
          >
            {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </form>
        {!user && (
          <button onClick={() => router.push("/login")} className="mt-1 text-xs text-primary hover:underline">
            {t(lang, "post_login_btn")}
          </button>
        )}
      </div>

      {/* 라이트박스 */}
      {lightboxIdx !== null && post.images && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          onClick={() => setLightboxIdx(null)}
        >
          <button
            className="absolute top-4 right-4 text-white/80 hover:text-white text-2xl font-bold"
            onClick={() => setLightboxIdx(null)}
          >
            ✕
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
                  onClick={(e) => { e.stopPropagation(); setLightboxIdx(i); }}
                  className={cn("h-2 w-2 rounded-full", i === lightboxIdx ? "bg-white" : "bg-white/40")}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

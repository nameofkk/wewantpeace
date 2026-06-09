"use client";

import { useState, useEffect, useRef, useMemo, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ChevronLeft, Loader2, X, AlertCircle, ImagePlus } from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";
import RichEditor from "@/components/community/RichEditor";

type PostType = "discussion" | "analysis" | "question";

const POST_TYPE_KEYS = {
  discussion: "community_type_discussion",
  analysis: "community_type_analysis",
  question: "community_type_question",
} as const;

const MAX_IMAGES = 5;

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
  const editMode = searchParams.get("edit") === "1";
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();

  // ── 편집 모드 상태 ──────────────────────────────────────────
  const [postType, setPostType] = useState<PostType>("discussion");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [imageUrls, setImageUrls] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [fetching, setFetching] = useState(editMode);
  const [editError, setEditError] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
    images?: string[];
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

  // 편집 모드에서 기존 데이터 초기화
  useEffect(() => {
    if (!editMode || !post) return;
    if (post.post_type) setPostType(post.post_type as PostType);
    if (post.title) setTitle(post.title);
    if (post.content) setContent(post.content);
    if (post.images) setImageUrls(post.images);
    setFetching(false);
  }, [editMode, post]);

  async function handleImageSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const remaining = MAX_IMAGES - imageUrls.length;
    const toUpload = files.slice(0, remaining);
    if (!user) return;
    setImageUploading(true);
    try {
      const token = await user.getIdToken();
      const uploaded: string[] = [];
      for (const file of toUpload) {
        const formData = new FormData();
        formData.append("file", file);
        const res = await fetch(`${API_BASE}/community/upload`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: formData,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || t(lang, "community_edit_upload_fail"));
        }
        const data = await res.json();
        uploaded.push(data.url);
      }
      setImageUrls((prev) => [...prev, ...uploaded]);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setEditError(err.message || t(lang, "community_edit_upload_error"));
    } finally {
      setImageUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function removeImage(idx: number) {
    setImageUrls((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setEditError(null);
    if (!user) { router.push("/login"); return; }
    if (title.trim().length < 5) { setEditError(t(lang, "community_edit_title_min")); return; }
    if (content.trim().length < 10) { setEditError(t(lang, "community_edit_content_min")); return; }

    setSaving(true);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/community/posts/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim(),
          post_type: postType,
          images: imageUrls,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail;
        const msg = Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join(", ")
          : typeof detail === "string"
          ? detail
          : t(lang, "community_edit_fail");
        throw new Error(msg);
      }

      const data = await res.json();
      queryClient.setQueryData(["community", "post", id], data);
      queryClient.invalidateQueries({ queryKey: ["community-posts"] });
      queryClient.invalidateQueries({ queryKey: ["my-posts"] });
      router.replace(`/community/post-view?id=${id}`);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setEditError(err.message || t(lang, "community_edit_error"));
    } finally {
      setSaving(false);
    }
  }

  const canSave = !saving && !imageUploading && title.trim().length >= 5 && content.trim().length >= 10;

  if (!id) {
    return (
      <div className="flex items-center justify-center min-h-screen text-muted-foreground">
        {lang === "ko" ? "게시글을 찾을 수 없습니다." : "Post not found."}
      </div>
    );
  }

  // ── 편집 모드 UI ────────────────────────────────────────────
  if (editMode) {
    if (!authLoading && !user) {
      router.replace("/login");
      return null;
    }

    if (isLoading || fetching) {
      return (
        <div className="flex h-64 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      );
    }

    return (
      <div className="min-h-screen bg-background">
        <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
          <button
            onClick={() => router.replace(`/community/post-view?id=${id}`)}
            className="text-muted-foreground hover:text-foreground"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <h1 className="text-base font-bold flex-1">{t(lang, "community_edit_title")}</h1>
          <button
            onClick={handleSave}
            disabled={!canSave}
            className="rounded-full bg-primary px-4 py-1.5 text-sm font-bold text-primary-foreground disabled:opacity-40 flex items-center gap-1"
          >
            {saving && <Loader2 className="h-3 w-3 animate-spin" />}
            {t(lang, "community_edit_save")}
          </button>
        </div>

        <form onSubmit={handleSave} className="px-4 py-4 space-y-4">
          {editError && (
            <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive flex items-start gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              {editError}
            </div>
          )}

          <div className="flex gap-2">
            {(["discussion", "analysis", "question"] as const).map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setPostType(type)}
                className={cn(
                  "flex-1 rounded-xl border py-2 text-xs font-medium transition-colors",
                  postType === type
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground"
                )}
              >
                {t(lang, POST_TYPE_KEYS[type])}
              </button>
            ))}
          </div>

          <div>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t(lang, "community_edit_title_placeholder")}
              maxLength={200}
              className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm outline-none focus:border-primary"
            />
            <p className="mt-1 text-right text-[10px] text-muted-foreground">{title.length}/200</p>
          </div>

          <div>
            <RichEditor
              initialValue={content}
              onChange={setContent}
              placeholder={t(lang, "community_edit_content_placeholder")}
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                {t(lang, "community_edit_photo")}{" "}
                <span className="text-muted-foreground/60">
                  ({t(lang, "community_edit_photo_max", { n: MAX_IMAGES })})
                </span>
              </label>
              <span className="text-[10px] text-muted-foreground">
                {imageUrls.length}/{MAX_IMAGES}
              </span>
            </div>

            {imageUrls.length > 0 && (
              <div className="flex gap-2 flex-wrap mb-2">
                {imageUrls.map((url, idx) => (
                  <div
                    key={idx}
                    className="relative w-20 h-20 rounded-lg overflow-hidden border border-border"
                  >
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={url.startsWith("http") ? url : `${API_BASE}${url}`}
                      alt={`${t(lang, "community_edit_photo")} ${idx + 1}`}
                      className="w-full h-full object-cover"
                    />
                    <button
                      type="button"
                      onClick={() => removeImage(idx)}
                      className="absolute top-0.5 right-0.5 bg-black/60 rounded-full p-0.5 text-white hover:bg-black/80"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {imageUrls.length < MAX_IMAGES && (
              <>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/gif,image/webp"
                  multiple
                  className="hidden"
                  onChange={handleImageSelect}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={imageUploading}
                  className="flex items-center gap-2 rounded-xl border border-dashed border-border bg-card px-4 py-3 text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors disabled:opacity-50 w-full"
                >
                  {imageUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <ImagePlus className="h-4 w-4" />
                  )}
                  {imageUploading
                    ? t(lang, "community_edit_uploading")
                    : t(lang, "community_edit_add_photo")}
                </button>
              </>
            )}
          </div>
        </form>
      </div>
    );
  }

  // ── 보기 모드 UI ────────────────────────────────────────────
  return (
    <div className="flex flex-col min-h-screen bg-background">
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <button
          onClick={() => router.back()}
          className="text-muted-foreground hover:text-foreground"
        >
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
            <h2 className="text-lg font-bold">
              {lang === "en" ? (post.title_en || post.title) : post.title}
            </h2>
            <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
              <span>{post.author_nickname || "Anonymous"}</span>
              <span>·</span>
              <span>{relativeTime(post.created_at, lang)}</span>
              <span>·</span>
              <span>
                {t(lang, "community_views")} {post.view_count}
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <div className="prose prose-sm dark:prose-invert max-w-none whitespace-pre-wrap text-sm">
              {lang === "en" ? (post.content_en || post.content) : post.content}
            </div>
          </div>

          {post.images && post.images.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {post.images.map((url, idx) => (
                <div
                  key={idx}
                  className="w-24 h-24 rounded-lg overflow-hidden border border-border"
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={url.startsWith("http") ? url : `${API_BASE}${url}`}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                </div>
              ))}
            </div>
          )}

          <div className="flex items-center gap-4 text-xs text-muted-foreground">
            <span>
              {t(lang, "community_likes")} {post.like_count}
            </span>
            <span>
              {t(lang, "community_comments")} {post.comment_count}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function PostViewPage() {
  return (
    <Suspense
      fallback={
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
      }
    >
      <PostViewInner />
    </Suspense>
  );
}

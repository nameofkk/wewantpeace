"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, Loader2, X, AlertCircle, ImagePlus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useQueryClient } from "@tanstack/react-query";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";

type PostType = "discussion" | "analysis" | "question";

const POST_TYPE_KEYS = {
  discussion: "community_type_discussion",
  analysis: "community_type_analysis",
  question: "community_type_question",
} as const;

const MAX_IMAGES = 5;

export default function EditPostPage() {
  const { postId } = useParams<{ postId: string }>();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const { lang } = useAppStore();

  const [postType, setPostType] = useState<PostType>("discussion");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [imageUrls, setImageUrls] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imageUploading, setImageUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 기존 데이터 로드
  useEffect(() => {
    if (!postId) return;
    fetch(`${API_BASE}/community/posts/${postId}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.post_type) setPostType(data.post_type as PostType);
        if (data.title) setTitle(data.title);
        if (data.content) setContent(data.content);
        if (data.images) setImageUrls(data.images);
      })
      .catch(() => setError(t(lang, "community_load_error")))
      .finally(() => setFetching(false));
  }, [postId, API_BASE, lang]);

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
      setError(err.message || t(lang, "community_edit_upload_error"));
    } finally {
      setImageUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function removeImage(idx: number) {
    setImageUrls((prev) => prev.filter((_, i) => i !== idx));
  }

  if (!authLoading && !user) {
    router.replace("/login");
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!user) { router.push("/login"); return; }
    if (title.trim().length < 5) { setError(t(lang, "community_edit_title_min")); return; }
    if (content.trim().length < 10) { setError(t(lang, "community_edit_content_min")); return; }

    setLoading(true);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/community/posts/${postId}`, {
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

      await queryClient.invalidateQueries({ queryKey: ["post", postId] });
      await queryClient.invalidateQueries({ queryKey: ["community-posts"] });
      await queryClient.invalidateQueries({ queryKey: ["my-posts"] });
      router.replace(`/community/${postId}`);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || t(lang, "community_edit_error"));
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = !loading && !imageUploading && title.trim().length >= 5 && content.trim().length >= 10;

  if (fetching) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* 상단 바 */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <Link href={`/community/${postId}`} className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-base font-bold flex-1">{t(lang, "community_edit_title")}</h1>
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-full bg-primary px-4 py-1.5 text-sm font-bold text-primary-foreground disabled:opacity-40 flex items-center gap-1"
        >
          {loading && <Loader2 className="h-3 w-3 animate-spin" />}
          {t(lang, "community_edit_save")}
        </button>
      </div>

      <form onSubmit={handleSubmit} className="px-4 py-4 space-y-4">
        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {/* 게시글 유형 */}
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

        {/* 제목 */}
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

        {/* 내용 */}
        <div>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={t(lang, "community_edit_content_placeholder")}
            rows={10}
            className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm outline-none focus:border-primary resize-none"
          />
        </div>

        {/* 이미지 업로드 */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {t(lang, "community_edit_photo")}{" "}
              <span className="text-muted-foreground/60">({t(lang, "community_edit_photo_max", { n: MAX_IMAGES })})</span>
            </label>
            <span className="text-[10px] text-muted-foreground">{imageUrls.length}/{MAX_IMAGES}</span>
          </div>

          {imageUrls.length > 0 && (
            <div className="flex gap-2 flex-wrap mb-2">
              {imageUrls.map((url, idx) => (
                <div key={idx} className="relative w-20 h-20 rounded-lg overflow-hidden border border-border">
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
                {imageUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
                {imageUploading ? t(lang, "community_edit_uploading") : t(lang, "community_edit_add_photo")}
              </button>
            </>
          )}
        </div>
      </form>
    </div>
  );
}

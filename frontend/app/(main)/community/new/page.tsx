"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ChevronLeft, Loader2, Search, X, AlertCircle, ImagePlus } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useQueryClient } from "@tanstack/react-query";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { API_BASE, useMe } from "@/lib/api";
import { communityPostPath } from "@/lib/toss-nav";

type PostType = "discussion" | "analysis" | "question" | "notice";

const POST_TYPE_IDS: PostType[] = ["discussion", "analysis", "question"];

interface IssueItem {
  id: string;
  title: string;
  title_ko: string | null;
  country_code: string | null;
  severity: number;
  topic: string | null;
}

const TOPIC_COLOR: Record<string, string> = {
  conflict: "text-red-400",
  terror: "text-red-500",
  coup: "text-orange-400",
  sanctions: "text-yellow-400",
  diplomacy: "text-blue-400",
  maritime: "text-cyan-400",
  cyber: "text-purple-400",
  protest: "text-green-400",
};

const MAX_IMAGES = 5;

export default function NewPostPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const lang = useAppStore((s) => s.lang);
  const { data: me } = useMe();
  const isAdmin = (me as { role?: string } | undefined)?.role === "admin";
  const [postType, setPostType] = useState<PostType>("discussion");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [clusterId, setClusterId] = useState("");
  const [clusterTitle, setClusterTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 이슈 선택 UI
  const [issueSearch, setIssueSearch] = useState("");
  const [showIssuePicker, setShowIssuePicker] = useState(false);
  const [issues, setIssues] = useState<IssueItem[]>([]);
  const [issueLoading, setIssueLoading] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  // 이미지 업로드
  const [imageUrls, setImageUrls] = useState<string[]>([]);
  const [imageUploading, setImageUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 이슈 목록 로드
  useEffect(() => {
    if (!showIssuePicker) return;
    setIssueLoading(true);
    fetch(`${API_BASE}/issues?limit=50&severity_min=30`)
      .then((r) => r.json())
      .then((data) => setIssues(Array.isArray(data) ? data : []))
      .catch(() => setIssues([]))
      .finally(() => setIssueLoading(false));
  }, [showIssuePicker, API_BASE]);

  // picker 외부 클릭 시 닫기
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setShowIssuePicker(false);
      }
    }
    if (showIssuePicker) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showIssuePicker]);

  const filteredIssues = issueSearch.trim()
    ? issues.filter(
        (i) =>
          (i.title_ko || i.title).toLowerCase().includes(issueSearch.toLowerCase()) ||
          (i.country_code || "").toLowerCase().includes(issueSearch.toLowerCase())
      )
    : issues;

  function selectIssue(issue: IssueItem) {
    setClusterId(issue.id);
    setClusterTitle(lang === "en" ? issue.title : (issue.title_ko || issue.title));
    setShowIssuePicker(false);
    setIssueSearch("");
  }

  function clearIssue() {
    setClusterId("");
    setClusterTitle("");
  }

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
          throw new Error(err.detail || t(lang, "new_post_error_upload"));
        }
        const data = await res.json();
        uploaded.push(data.url);
      }
      setImageUrls((prev) => [...prev, ...uploaded]);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || t(lang, "new_post_error_upload"));
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

    if (!user) {
      setError(t(lang, "new_post_error_login"));
      router.push("/login");
      return;
    }
    if (title.trim().length < 5) {
      setError(t(lang, "new_post_error_title"));
      return;
    }
    if (content.trim().length < 10) {
      setError(t(lang, "new_post_error_content"));
      return;
    }

    setLoading(true);

    try {
      const token = await user.getIdToken();
      const body: Record<string, unknown> = {
        title: title.trim(),
        content: content.trim(),
        post_type: postType,
        images: imageUrls,
      };
      if (clusterId) body.cluster_id = clusterId;

      const res = await fetch(`${API_BASE}/community/posts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail;
        const msg = Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join(", ")
          : typeof detail === "string"
          ? detail
          : t(lang, "new_post_error_submit");
        throw new Error(msg);
      }

      const post = await res.json();
      await queryClient.invalidateQueries({ queryKey: ["community-posts"] });
      router.push(communityPostPath(post.id));
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || t(lang, "new_post_error_generic"));
    } finally {
      setLoading(false);
    }
  }

  const canSubmit = !loading && !imageUploading && title.trim().length >= 5 && content.trim().length >= 10;

  return (
    <div className="min-h-screen bg-background">
      {/* 상단 바 */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <Link href="/community" className="text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-base font-bold flex-1">{t(lang, "new_post_title")}</h1>
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-full bg-primary px-4 py-1.5 text-sm font-bold text-primary-foreground disabled:opacity-40 flex items-center gap-1"
        >
          {loading && <Loader2 className="h-3 w-3 animate-spin" />}
          {t(lang, "new_post_submit")}
        </button>
      </div>

      {/* 로그인 상태 배너 */}
      {!authLoading && user && (
        <div className="px-4 py-2 bg-primary/5 border-b border-border flex items-center gap-2 text-xs text-muted-foreground">
          <div className="h-2 w-2 rounded-full bg-green-400" />
          <span>{t(lang, "new_post_logged_in", { email: user.email || user.displayName || "" })}</span>
        </div>
      )}

      <form id="post-form" onSubmit={handleSubmit} className="px-4 py-4 space-y-4">
        {error && (
          <div className="rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            {error}
          </div>
        )}

        {/* 게시글 유형 */}
        <div className="flex gap-2">
          {(isAdmin ? [...POST_TYPE_IDS, "notice" as PostType] : POST_TYPE_IDS).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setPostType(id)}
              className={cn(
                "flex-1 rounded-xl border py-2 text-xs font-medium transition-colors",
                postType === id
                  ? id === "notice"
                    ? "border-yellow-500 bg-yellow-500/10 text-yellow-500"
                    : "border-primary bg-primary/10 text-primary"
                  : "border-border text-muted-foreground"
              )}
            >
              {t(lang, `community_type_${id}` as Parameters<typeof t>[1])}
            </button>
          ))}
        </div>

        {/* 제목 */}
        <div>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t(lang, "new_post_title_placeholder")}
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
            placeholder={t(lang, "new_post_content_placeholder")}
            rows={10}
            className="w-full rounded-xl border border-border bg-card px-4 py-3 text-sm outline-none focus:border-primary resize-none"
          />
        </div>

        {/* 이미지 업로드 */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              {t(lang, "new_post_images_label")}{" "}
              <span className="text-muted-foreground/60">{t(lang, "new_post_images_desc", { n: MAX_IMAGES })}</span>
            </label>
            <span className="text-[10px] text-muted-foreground">{imageUrls.length}/{MAX_IMAGES}</span>
          </div>

          {/* 이미지 미리보기 */}
          {imageUrls.length > 0 && (
            <div className="flex gap-2 flex-wrap mb-2">
              {imageUrls.map((url, idx) => (
                <div key={idx} className="relative w-20 h-20 rounded-lg overflow-hidden border border-border">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`${API_BASE}${url}`}
                    alt={t(lang, "post_img_alt", { n: idx + 1 })}
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
                {imageUploading ? t(lang, "new_post_uploading") : t(lang, "new_post_add_image")}
              </button>
            </>
          )}
        </div>

        {/* 연관 이슈 선택 */}
        <div ref={pickerRef} className="relative">
          <label className="block text-xs font-medium text-muted-foreground mb-1.5">
            {t(lang, "new_post_linked_label")}{" "}
            <span className="text-muted-foreground/60">{t(lang, "new_post_linked_optional")}</span>
          </label>

          {/* 선택된 이슈 표시 */}
          {clusterId ? (
            <div className="flex items-center gap-2 rounded-xl border border-primary/40 bg-primary/5 px-4 py-3">
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-primary truncate">{clusterTitle}</p>
                <p className="text-[10px] text-muted-foreground font-mono mt-0.5 truncate">{clusterId}</p>
              </div>
              <button type="button" onClick={clearIssue} className="text-muted-foreground hover:text-destructive">
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowIssuePicker(true)}
              className="w-full flex items-center gap-2 rounded-xl border border-dashed border-border bg-card px-4 py-3 text-sm text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors"
            >
              <Search className="h-4 w-4" />
              {t(lang, "new_post_issue_browse")}
            </button>
          )}

          {/* 이슈 선택 드롭다운 */}
          {showIssuePicker && (
            <div className="absolute left-0 right-0 top-full mt-1 z-20 rounded-xl border border-border bg-card shadow-xl overflow-hidden">
              <div className="p-3 border-b border-border">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                  <input
                    type="text"
                    placeholder={t(lang, "new_post_issue_search")}
                    value={issueSearch}
                    onChange={(e) => setIssueSearch(e.target.value)}
                    autoFocus
                    className="w-full rounded-lg border border-border bg-background pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-primary"
                  />
                </div>
              </div>

              <div className="max-h-64 overflow-y-auto">
                {issueLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  </div>
                ) : filteredIssues.length === 0 ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">{t(lang, "new_post_no_issues")}</p>
                ) : (
                  filteredIssues.map((issue) => {
                    const issueTitle = lang === "en" ? issue.title : (issue.title_ko || issue.title);
                    return (
                      <button
                        key={issue.id}
                        type="button"
                        onClick={() => selectIssue(issue)}
                        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-secondary/50 transition-colors border-b border-border/50 last:border-0"
                      >
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium leading-snug truncate">{issueTitle}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            {issue.country_code && (
                              <span className="text-[10px] text-muted-foreground">{issue.country_code}</span>
                            )}
                            {issue.topic && (
                              <span className={cn("text-[10px] font-medium", TOPIC_COLOR[issue.topic] || "text-muted-foreground")}>
                                {issue.topic}
                              </span>
                            )}
                            <span className="text-[10px] text-muted-foreground">
                              {t(lang, "new_post_severity")} {issue.severity}
                            </span>
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}

          <p className="mt-1 text-[10px] text-muted-foreground">
            {t(lang, "new_post_issue_hint")}
          </p>
        </div>
      </form>
    </div>
  );
}

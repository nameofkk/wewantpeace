"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAdminStore, API_BASE } from "@/lib/admin-utils";
import {
  Link2, Copy, Plus, ChevronLeft, ChevronRight, ChevronDown,
  HelpCircle, X, Check, ExternalLink, BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface ShortLink {
  id: number;
  code: string;
  title: string | null;
  target_url: string;
  click_count: number;
  is_active: boolean;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  expires_at: string | null;
  created_at: string;
}

interface LinksResponse {
  items: ShortLink[];
  total: number;
}

interface DailyClick {
  date: string;
  count: number;
}

interface ClickStatsResponse {
  daily: DailyClick[];
  recent: { ip: string; user_agent: string; clicked_at: string }[];
}

/* ------------------------------------------------------------------ */
/*  Inline Guide                                                       */
/* ------------------------------------------------------------------ */
function InlineGuide({ lang }: { lang: "ko" | "en" }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-4 rounded-xl border border-border/50 bg-card/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <span className="flex items-center gap-1.5">
          <HelpCircle className="h-3.5 w-3.5" />
          {lang === "ko" ? "이 페이지 가이드" : "Page Guide"}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="px-4 pb-3 text-xs text-muted-foreground space-y-1">
          <p>{lang === "ko"
            ? "- 단축 링크를 생성하고 클릭 수를 추적합니다."
            : "- Create short links and track click counts."}</p>
          <p>{lang === "ko"
            ? "- 코드를 비워두면 자동 생성됩니다."
            : "- Leave code empty to auto-generate."}</p>
          <p>{lang === "ko"
            ? "- UTM 파라미터를 설정하여 마케팅 추적이 가능합니다."
            : "- Set UTM parameters for marketing tracking."}</p>
          <p>{lang === "ko"
            ? "- 행을 클릭하면 일별 클릭 차트와 최근 클릭 내역을 볼 수 있습니다."
            : "- Click a row to see daily click chart and recent clicks."}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Create Modal                                                       */
/* ------------------------------------------------------------------ */
function CreateLinkModal({
  lang,
  onClose,
  onSubmit,
  isPending,
}: {
  lang: "ko" | "en";
  onClose: () => void;
  onSubmit: (data: Record<string, string>) => void;
  isPending: boolean;
}) {
  const [form, setForm] = useState({
    target_url: "",
    title: "",
    code: "",
    utm_source: "",
    utm_medium: "",
    utm_campaign: "",
    expires_at: "",
  });

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">{lang === "ko" ? "링크 생성" : "Create Link"}</h2>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "대상 URL *" : "Target URL *"}</label>
            <input
              value={form.target_url}
              onChange={(e) => set("target_url", e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="https://example.com/page"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "제목" : "Title"}</label>
              <input
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder={lang === "ko" ? "링크 설명" : "Link description"}
              />
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block">
                {lang === "ko" ? "코드 (선택)" : "Code (optional)"}
              </label>
              <input
                value={form.code}
                onChange={(e) => set("code", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder={lang === "ko" ? "자동 생성" : "Auto-generated"}
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium mb-1 block">UTM Source</label>
              <input
                value={form.utm_source}
                onChange={(e) => set("utm_source", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="newsletter"
              />
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block">UTM Medium</label>
              <input
                value={form.utm_medium}
                onChange={(e) => set("utm_medium", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="email"
              />
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block">UTM Campaign</label>
              <input
                value={form.utm_campaign}
                onChange={(e) => set("utm_campaign", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder="launch"
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "만료일" : "Expires At"}</label>
            <input
              type="datetime-local"
              value={form.expires_at}
              onChange={(e) => set("expires_at", e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-muted-foreground hover:bg-secondary"
          >
            {lang === "ko" ? "취소" : "Cancel"}
          </button>
          <button
            onClick={() => {
              if (!form.target_url.trim()) return;
              onSubmit(form);
            }}
            disabled={isPending || !form.target_url.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
            {isPending ? (lang === "ko" ? "생성 중..." : "Creating...") : (lang === "ko" ? "생성" : "Create")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Click Stats Expandable Row                                         */
/* ------------------------------------------------------------------ */
function ClickStats({ linkId, lang, user }: { linkId: number; lang: "ko" | "en"; user: any }) {
  const { data, isLoading } = useQuery<ClickStatsResponse>({
    queryKey: ["admin-link-stats", linkId],
    queryFn: async () => {
      if (!user) throw new Error("Unauthorized");
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/admin/links/${linkId}/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Failed to load stats");
      return res.json();
    },
    enabled: !!user,
  });

  const locale = lang === "en" ? "en-US" : "ko-KR";

  if (isLoading) {
    return (
      <div className="py-4 text-center text-xs text-muted-foreground">
        {lang === "ko" ? "통계 로딩 중..." : "Loading stats..."}
      </div>
    );
  }

  if (!data) return null;

  const maxCount = Math.max(1, ...data.daily.map((d) => d.count));

  return (
    <div className="px-4 py-4 bg-secondary/20">
      {/* Daily chart */}
      <p className="text-xs font-medium mb-2">
        {lang === "ko" ? "일별 클릭 (최근 14일)" : "Daily Clicks (Last 14 days)"}
      </p>
      {data.daily.length === 0 ? (
        <p className="text-xs text-muted-foreground">{lang === "ko" ? "데이터 없음" : "No data"}</p>
      ) : (
        <div className="flex items-end gap-1 h-16 mb-4">
          {data.daily.map((d) => (
            <div key={d.date} className="flex-1 flex flex-col items-center gap-0.5">
              <div
                className="w-full bg-primary/60 rounded-t"
                style={{ height: `${(d.count / maxCount) * 100}%`, minHeight: d.count > 0 ? "2px" : "0" }}
              />
              <span className="text-[8px] text-muted-foreground truncate w-full text-center">
                {new Date(d.date).toLocaleDateString(locale, { month: "numeric", day: "numeric" })}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Recent clicks */}
      <p className="text-xs font-medium mb-2">
        {lang === "ko" ? "최근 클릭" : "Recent Clicks"}
      </p>
      {data.recent.length === 0 ? (
        <p className="text-xs text-muted-foreground">{lang === "ko" ? "클릭 내역 없음" : "No clicks yet"}</p>
      ) : (
        <div className="space-y-1">
          {data.recent.slice(0, 5).map((c, i) => (
            <div key={i} className="flex items-center gap-3 text-[10px] text-muted-foreground">
              <span className="shrink-0">
                {new Date(c.clicked_at).toLocaleString(locale, {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
              </span>
              <span className="truncate">{c.user_agent.slice(0, 60)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function AdminLinksPage() {
  const { user } = useAuth();
  const { lang } = useAdminStore();
  const qc = useQueryClient();

  const [page, setPage] = useState(1);
  const [showCreate, setShowCreate] = useState(false);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [copied, setCopied] = useState<number | null>(null);

  const locale = lang === "en" ? "en-US" : "ko-KR";

  /* fetch helper */
  const fetchWithToken = async <T,>(path: string, opts?: { method?: string; body?: unknown }): Promise<T> => {
    if (!user) throw new Error("Unauthorized");
    const token = await user.getIdToken();
    const res = await fetch(`${API_BASE}${path}`, {
      method: opts?.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      ...(opts?.body ? { body: JSON.stringify(opts.body) } : {}),
    });
    if (!res.ok) throw new Error(`Admin API error: ${res.status}`);
    return res.json();
  };

  /* query */
  const { data, isLoading } = useQuery<LinksResponse>({
    queryKey: ["admin-links", page],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page) });
      return fetchWithToken<LinksResponse>(`/admin/links?${params}`);
    },
    enabled: !!user,
  });

  /* create mutation */
  const createMut = useMutation({
    mutationFn: (body: Record<string, string>) =>
      fetchWithToken("/admin/links", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-links"] });
      setShowCreate(false);
    },
  });

  const items = data?.items ?? [];
  const totalPages = Math.ceil((data?.total ?? 0) / 20);

  const handleCopy = (code: string, id: number) => {
    const url = `${typeof window !== "undefined" ? window.location.origin : ""}/r/${code}`;
    navigator.clipboard.writeText(url);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const truncateUrl = (url: string, max = 50) =>
    url.length > max ? url.slice(0, max) + "..." : url;

  const formatDate = (d: string | null) => {
    if (!d) return "\u2014";
    return new Date(d).toLocaleDateString(locale);
  };

  return (
    <div>
      <InlineGuide lang={lang} />

      {/* Header */}
      <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Link2 className="h-6 w-6 text-primary" />
            {lang === "ko" ? "단축 링크" : "Short Links"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.total ?? 0} {lang === "ko" ? "건" : "links"}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          {lang === "ko" ? "링크 생성" : "Create Link"}
        </button>
      </div>

      {/* Loading */}
      {isLoading ? (
        <>
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <div className="bg-secondary/50 h-10" />
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="border-t border-border px-4 py-4">
                <div className="h-4 bg-secondary/50 rounded animate-pulse w-full" />
              </div>
            ))}
          </div>
          <div className="md:hidden space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="h-4 bg-secondary/50 rounded animate-pulse w-3/4" />
                <div className="h-3 bg-secondary/50 rounded animate-pulse w-1/2" />
              </div>
            ))}
          </div>
        </>
      ) : !items.length ? (
        <div className="flex flex-col items-center py-16 text-muted-foreground">
          <Link2 className="h-10 w-10 mb-3" />
          <p className="text-sm">{lang === "ko" ? "링크가 없습니다" : "No links found"}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "코드" : "Code"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "제목" : "Title"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "대상 URL" : "Target URL"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "클릭" : "Clicks"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "상태" : "Status"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "생성일" : "Created"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground" />
                </tr>
              </thead>
              <tbody>
                {items.map((link) => (
                  <>
                    <tr
                      key={link.id}
                      className={cn(
                        "border-t border-border hover:bg-secondary/20 cursor-pointer",
                        expandedId === link.id && "bg-secondary/10"
                      )}
                      onClick={() => setExpandedId(expandedId === link.id ? null : link.id)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5">
                          <code className="text-xs font-mono text-primary">{link.code}</code>
                          <button
                            onClick={(e) => { e.stopPropagation(); handleCopy(link.code, link.id); }}
                            className="p-0.5 text-muted-foreground hover:text-foreground transition-colors"
                          >
                            {copied === link.id ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs">{link.title ?? "\u2014"}</td>
                      <td className="px-4 py-3">
                        <a
                          href={link.target_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-xs text-muted-foreground hover:text-primary flex items-center gap-1"
                        >
                          {truncateUrl(link.target_url)}
                          <ExternalLink className="h-3 w-3 shrink-0" />
                        </a>
                      </td>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-1 text-xs font-medium">
                          <BarChart3 className="h-3 w-3 text-primary" />
                          {link.click_count.toLocaleString(locale)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium",
                          link.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                        )}>
                          {link.is_active ? (lang === "ko" ? "활성" : "Active") : (lang === "ko" ? "비활성" : "Inactive")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(link.created_at)}</td>
                      <td className="px-4 py-3">
                        <ChevronDown className={cn(
                          "h-3.5 w-3.5 text-muted-foreground transition-transform",
                          expandedId === link.id && "rotate-180"
                        )} />
                      </td>
                    </tr>
                    {expandedId === link.id && (
                      <tr key={`${link.id}-stats`}>
                        <td colSpan={7}>
                          <ClickStats linkId={link.id} lang={lang} user={user} />
                        </td>
                      </tr>
                    )}
                  </>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {items.map((link) => (
              <div key={link.id} className="rounded-xl border border-border bg-card overflow-hidden">
                <div
                  className="p-4 cursor-pointer"
                  onClick={() => setExpandedId(expandedId === link.id ? null : link.id)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono text-primary">{link.code}</code>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleCopy(link.code, link.id); }}
                        className="p-0.5 text-muted-foreground hover:text-foreground"
                      >
                        {copied === link.id ? <Check className="h-3 w-3 text-green-400" /> : <Copy className="h-3 w-3" />}
                      </button>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-medium",
                        link.is_active ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                      )}>
                        {link.is_active ? (lang === "ko" ? "활성" : "Active") : (lang === "ko" ? "비활성" : "Inactive")}
                      </span>
                      <ChevronDown className={cn(
                        "h-3.5 w-3.5 text-muted-foreground transition-transform",
                        expandedId === link.id && "rotate-180"
                      )} />
                    </div>
                  </div>
                  {link.title && <p className="text-xs font-medium mb-1">{link.title}</p>}
                  <p className="text-[10px] text-muted-foreground truncate">{link.target_url}</p>
                  <div className="flex items-center gap-4 mt-2 text-xs">
                    <span className="flex items-center gap-1">
                      <BarChart3 className="h-3 w-3 text-primary" />
                      {link.click_count.toLocaleString(locale)} {lang === "ko" ? "클릭" : "clicks"}
                    </span>
                    <span className="text-muted-foreground">{formatDate(link.created_at)}</span>
                  </div>
                </div>
                {expandedId === link.id && (
                  <ClickStats linkId={link.id} lang={lang} user={user} />
                )}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3 mt-6">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-sm text-muted-foreground">
            {page} / {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="p-1.5 rounded-lg hover:bg-secondary disabled:opacity-30"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <CreateLinkModal
          lang={lang}
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMut.mutate(data)}
          isPending={createMut.isPending}
        />
      )}
    </div>
  );
}

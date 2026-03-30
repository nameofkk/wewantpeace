"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAdminStore, API_BASE } from "@/lib/admin-utils";
import {
  Handshake, Search, Plus, Trash2, ChevronLeft, ChevronRight,
  HelpCircle, ChevronDown, X, ExternalLink, CalendarCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface Partner {
  id: number;
  name: string;
  email: string | null;
  company_type: string;
  status: string;
  channel: string | null;
  segment: string | null;
  url: string | null;
  next_follow_up: string | null;
  notes: string | null;
  created_at: string;
}

interface PartnersResponse {
  items: Partner[];
  total: number;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const STATUSES = ["prospect", "contacted", "negotiating", "active", "churned", "rejected"] as const;
type PartnerStatus = (typeof STATUSES)[number];

const STATUS_COLORS: Record<string, string> = {
  prospect: "bg-blue-500/20 text-blue-400",
  contacted: "bg-cyan-500/20 text-cyan-400",
  negotiating: "bg-yellow-500/20 text-yellow-400",
  active: "bg-green-500/20 text-green-400",
  churned: "bg-red-500/20 text-red-400",
  rejected: "bg-gray-500/20 text-gray-400",
};

const STATUS_LABELS: Record<string, { ko: string; en: string }> = {
  prospect: { ko: "잠재", en: "Prospect" },
  contacted: { ko: "연락", en: "Contacted" },
  negotiating: { ko: "협상중", en: "Negotiating" },
  active: { ko: "활성", en: "Active" },
  churned: { ko: "이탈", en: "Churned" },
  rejected: { ko: "거절", en: "Rejected" },
};

const COMPANY_TYPE_COLORS: Record<string, string> = {
  media: "bg-purple-500/20 text-purple-400",
  ngo: "bg-emerald-500/20 text-emerald-400",
  gov: "bg-orange-500/20 text-orange-400",
  corp: "bg-indigo-500/20 text-indigo-400",
  edu: "bg-teal-500/20 text-teal-400",
  other: "bg-gray-500/20 text-gray-400",
};

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
            ? "- 파트너사를 리드 단계부터 활성 파트너까지 상태별로 관리합니다."
            : "- Manage partners from lead stage through active partnership."}</p>
          <p>{lang === "ko"
            ? "- 상태 드롭다운으로 즉시 단계 변경이 가능합니다."
            : "- Change status instantly via the inline dropdown."}</p>
          <p>{lang === "ko"
            ? "- 다음 팔로업 날짜가 지나면 빨간색으로 표시됩니다."
            : "- Overdue follow-up dates are highlighted in red."}</p>
          <p>{lang === "ko"
            ? "- 이름/이메일로 검색하고, 상태/세그먼트/채널별로 필터링하세요."
            : "- Search by name/email and filter by status, segment, or channel."}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Create Modal                                                       */
/* ------------------------------------------------------------------ */
function CreatePartnerModal({
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
    name: "",
    email: "",
    company_type: "other",
    status: "prospect",
    channel: "",
    segment: "",
    url: "",
    next_follow_up: "",
    notes: "",
  });

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">{lang === "ko" ? "파트너 추가" : "Add Partner"}</h2>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "이름 *" : "Name *"}</label>
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder={lang === "ko" ? "파트너/회사명" : "Partner / Company name"}
            />
          </div>
          <div>
            <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "이메일" : "Email"}</label>
            <input
              value={form.email}
              onChange={(e) => set("email", e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="contact@example.com"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "유형" : "Type"}</label>
              <select
                value={form.company_type}
                onChange={(e) => set("company_type", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              >
                {["media", "ngo", "gov", "corp", "edu", "other"].map((ct) => (
                  <option key={ct} value={ct}>{ct.toUpperCase()}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "상태" : "Status"}</label>
              <select
                value={form.status}
                onChange={(e) => set("status", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{STATUS_LABELS[s][lang]}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "채널" : "Channel"}</label>
              <input
                value={form.channel}
                onChange={(e) => set("channel", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder={lang === "ko" ? "예: 이메일, 소개" : "e.g. email, referral"}
              />
            </div>
            <div>
              <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "세그먼트" : "Segment"}</label>
              <input
                value={form.segment}
                onChange={(e) => set("segment", e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                placeholder={lang === "ko" ? "예: 동아시아" : "e.g. East Asia"}
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "URL" : "URL"}</label>
            <input
              value={form.url}
              onChange={(e) => set("url", e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
              placeholder="https://example.com"
            />
          </div>
          <div>
            <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "다음 팔로업" : "Next Follow-up"}</label>
            <input
              type="date"
              value={form.next_follow_up}
              onChange={(e) => set("next_follow_up", e.target.value)}
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="text-xs font-medium mb-1 block">{lang === "ko" ? "메모" : "Notes"}</label>
            <textarea
              value={form.notes}
              onChange={(e) => set("notes", e.target.value)}
              rows={3}
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
              if (!form.name.trim()) return;
              onSubmit(form);
            }}
            disabled={isPending || !form.name.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
            {isPending ? (lang === "ko" ? "저장 중..." : "Saving...") : (lang === "ko" ? "추가" : "Add")}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function AdminPartnersPage() {
  const { user } = useAuth();
  const { lang } = useAdminStore();
  const qc = useQueryClient();

  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  const [segmentFilter, setSegmentFilter] = useState("");
  const [channelFilter, setChannelFilter] = useState("");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [followUpThisWeek, setFollowUpThisWeek] = useState(false);

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
  const { data, isLoading } = useQuery<PartnersResponse>({
    queryKey: ["admin-partners", page, statusFilter, segmentFilter, channelFilter, search],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page) });
      if (statusFilter !== "all") params.append("status", statusFilter);
      if (segmentFilter) params.append("segment", segmentFilter);
      if (channelFilter) params.append("channel", channelFilter);
      if (search) params.append("q", search);
      return fetchWithToken<PartnersResponse>(`/admin/partners?${params}`);
    },
    enabled: !!user,
  });

  /* mutations */
  const createMut = useMutation({
    mutationFn: (body: Record<string, string>) =>
      fetchWithToken("/admin/partners", { method: "POST", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-partners"] });
      setShowCreate(false);
    },
  });

  const patchMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, string> }) =>
      fetchWithToken(`/admin/partners/${id}`, { method: "PATCH", body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-partners"] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) =>
      fetchWithToken(`/admin/partners/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-partners"] }),
  });

  const rawItems = data?.items ?? [];
  const items = followUpThisWeek
    ? rawItems.filter((p) => {
        if (!p.next_follow_up) return false;
        const d = new Date(p.next_follow_up);
        const now = new Date();
        const monday = new Date(now);
        monday.setDate(now.getDate() - now.getDay() + (now.getDay() === 0 ? -6 : 1));
        monday.setHours(0, 0, 0, 0);
        const sunday = new Date(monday);
        sunday.setDate(monday.getDate() + 6);
        sunday.setHours(23, 59, 59, 999);
        return d >= monday && d <= sunday;
      })
    : rawItems;
  const totalPages = Math.ceil((data?.total ?? 0) / 20);

  const isOverdue = (d: string | null) => {
    if (!d) return false;
    return new Date(d) < new Date();
  };

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
            <Handshake className="h-6 w-6 text-primary" />
            {lang === "ko" ? "파트너 관리" : "Partners"}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {data?.total ?? 0} {lang === "ko" ? "건" : "partners"}
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          <Plus className="h-4 w-4" />
          {lang === "ko" ? "파트너 추가" : "Add Partner"}
        </button>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {/* Status filter */}
        <div className="flex gap-1">
          {(["all", ...STATUSES] as const).map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); }}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
                statusFilter === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              {s === "all"
                ? (lang === "ko" ? "전체" : "All")
                : STATUS_LABELS[s][lang]}
            </button>
          ))}
        </div>

        {/* Segment */}
        <input
          value={segmentFilter}
          onChange={(e) => { setSegmentFilter(e.target.value); setPage(1); }}
          placeholder={lang === "ko" ? "세그먼트" : "Segment"}
          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs w-28 outline-none focus:border-primary"
        />

        {/* Channel */}
        <input
          value={channelFilter}
          onChange={(e) => { setChannelFilter(e.target.value); setPage(1); }}
          placeholder={lang === "ko" ? "채널" : "Channel"}
          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs w-28 outline-none focus:border-primary"
        />

        {/* This week follow-up */}
        <button
          onClick={() => setFollowUpThisWeek((v) => !v)}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors",
            followUpThisWeek
              ? "bg-primary text-primary-foreground"
              : "bg-secondary text-muted-foreground hover:text-foreground"
          )}
        >
          <CalendarCheck className="h-3.5 w-3.5" />
          {lang === "ko" ? "이번 주 팔로업" : "This Week"}
        </button>

        {/* Search */}
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder={lang === "ko" ? "이름/이메일 검색" : "Search name/email"}
            className="w-full rounded-lg border border-border bg-background pl-8 pr-3 py-1.5 text-xs outline-none focus:border-primary"
          />
        </div>
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
          <Handshake className="h-10 w-10 mb-3" />
          <p className="text-sm">{lang === "ko" ? "파트너가 없습니다" : "No partners found"}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block rounded-xl border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "이름" : "Name"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "유형" : "Type"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "상태" : "Status"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "채널" : "Channel"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">URL</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "다음 팔로업" : "Next Follow-up"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground">{lang === "ko" ? "등록일" : "Created"}</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-muted-foreground" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {items.map((p) => (
                  <tr key={p.id} className="hover:bg-secondary/20">
                    <td className="px-4 py-3">
                      <div className="text-xs font-medium">{p.name}</div>
                      {p.email && <div className="text-[10px] text-muted-foreground">{p.email}</div>}
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", COMPANY_TYPE_COLORS[p.company_type] || "bg-secondary")}>
                        {p.company_type.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={p.status}
                        onChange={(e) => patchMut.mutate({ id: p.id, body: { status: e.target.value } })}
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[10px] font-medium border-0 outline-none cursor-pointer appearance-none",
                          STATUS_COLORS[p.status] || "bg-secondary"
                        )}
                      >
                        {STATUSES.map((s) => (
                          <option key={s} value={s}>{STATUS_LABELS[s][lang]}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{p.channel ?? "\u2014"}</td>
                    <td className="px-4 py-3 text-xs">
                      {p.url ? (
                        <a href={p.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline inline-flex items-center gap-1">
                          <ExternalLink className="h-3 w-3" />
                          {lang === "ko" ? "링크" : "Link"}
                        </a>
                      ) : "\u2014"}
                    </td>
                    <td className={cn("px-4 py-3 text-xs", isOverdue(p.next_follow_up) ? "text-red-400 font-medium" : "text-muted-foreground")}>
                      {formatDate(p.next_follow_up)}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(p.created_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => {
                          if (confirm(lang === "ko" ? "이 파트너를 삭제하시겠습니까?" : "Delete this partner?")) {
                            deleteMut.mutate(p.id);
                          }
                        }}
                        className="p-1 text-muted-foreground hover:text-red-400 transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-3">
            {items.map((p) => (
              <div key={p.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{p.name}</p>
                    {p.email && <p className="text-[10px] text-muted-foreground truncate">{p.email}</p>}
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", COMPANY_TYPE_COLORS[p.company_type] || "bg-secondary")}>
                      {p.company_type.toUpperCase()}
                    </span>
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", STATUS_COLORS[p.status] || "bg-secondary")}>
                      {STATUS_LABELS[p.status]?.[lang] || p.status}
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-y-2 text-xs mt-2">
                  <div>
                    <span className="text-muted-foreground">{lang === "ko" ? "채널" : "Channel"}</span>
                    <p className="font-medium">{p.channel ?? "\u2014"}</p>
                  </div>
                  <div>
                    <span className={cn(isOverdue(p.next_follow_up) ? "text-red-400" : "text-muted-foreground")}>
                      {lang === "ko" ? "팔로업" : "Follow-up"}
                    </span>
                    <p className={cn("font-medium", isOverdue(p.next_follow_up) && "text-red-400")}>
                      {formatDate(p.next_follow_up)}
                    </p>
                  </div>
                  <div>
                    <span className="text-muted-foreground">{lang === "ko" ? "등록일" : "Created"}</span>
                    <p className="font-medium">{formatDate(p.created_at)}</p>
                  </div>
                </div>
                <div className="flex justify-end mt-2">
                  <button
                    onClick={() => {
                      if (confirm(lang === "ko" ? "삭제하시겠습니까?" : "Delete?")) deleteMut.mutate(p.id);
                    }}
                    className="p-1 text-muted-foreground hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
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
        <CreatePartnerModal
          lang={lang}
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMut.mutate(data)}
          isPending={createMut.isPending}
        />
      )}
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { API_BASE } from "@/lib/admin-utils";
import {
  Share2, Search, ChevronLeft, ChevronRight, HelpCircle,
  ChevronDown, X, CheckCircle, XCircle, RefreshCw, Eye,
  BarChart3, Edit3, Save,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { t, type Lang } from "@/lib/i18n";
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell, PieChart, Pie,
} from "recharts";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface PlatformInfo {
  platform: string;
  status: string;
  platform_post_id: string | null;
  error_message: string | null;
  published_at: string | null;
}

interface SocialPostItem {
  id: string;
  content_type: string;
  lang: string;
  body_text: string;
  hashtags: string[];
  image_url: string | null;
  risk_level: string;
  source_cluster_id: string | null;
  source_spike_id: string | null;
  dedup_key: string;
  status: string;
  created_at: string;
  approved_at: string | null;
  approved_by: string | null;
  published_at: string | null;
  platforms: PlatformInfo[];
}

interface SocialResponse {
  items: SocialPostItem[];
  total: number;
}

interface SocialStats {
  pending: number;
  published_today: number;
  published_week: number;
  failed: number;
}

interface ChartData {
  daily: { date: string; published: number; failed: number; pending: number; rejected: number; total: number }[];
  platforms: { platform: string; published: number; failed: number; skipped: number }[];
  content_types: { type: string; count: number }[];
  langs: { lang: string; count: number }[];
}

interface PreviewData {
  x: { text: string; char_count: number; max: number };
  threads: { text: string; char_count: number; max: number };
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */
const STATUS_TABS = ["all", "pending_review", "approved", "published", "rejected", "failed"] as const;

const STATUS_COLORS: Record<string, string> = {
  pending_review: "bg-yellow-500/20 text-yellow-400",
  approved: "bg-blue-500/20 text-blue-400",
  published: "bg-green-500/20 text-green-400",
  rejected: "bg-red-500/20 text-red-400",
  failed: "bg-orange-500/20 text-orange-400",
  skipped: "bg-gray-500/20 text-gray-400",
};

const STATUS_LABELS: Record<string, { ko: string; en: string }> = {
  pending_review: { ko: "대기", en: "Pending" },
  approved: { ko: "승인", en: "Approved" },
  published: { ko: "발행", en: "Published" },
  rejected: { ko: "거절", en: "Rejected" },
  failed: { ko: "실패", en: "Failed" },
  skipped: { ko: "스킵", en: "Skipped" },
};

const RISK_COLORS: Record<string, string> = {
  low: "bg-green-500/20 text-green-400",
  medium: "bg-yellow-500/20 text-yellow-400",
  high: "bg-red-500/20 text-red-400",
};

const CONTENT_TYPE_LABELS: Record<string, { ko: string; en: string }> = {
  daily_movers: { ko: "Daily Movers", en: "Daily Movers" },
  spike_alert: { ko: "Spike Alert", en: "Spike Alert" },
  weekly_recap: { ko: "Weekly Recap", en: "Weekly Recap" },
};

const PLATFORM_ICONS: Record<string, string> = {
  x: "\ud835\udd4f",
  threads: "\ud83e\uddf5",
  instagram: "\ud83d\udcf7",
};

const PLATFORM_FILTER_TABS = [
  { key: "", label: { ko: "전체", en: "All" } },
  { key: "x", label: { ko: "\ud835\udd4f X", en: "\ud835\udd4f X" } },
  { key: "threads", label: { ko: "\ud83e\uddf5 Threads", en: "\ud83e\uddf5 Threads" } },
];

const PIE_COLORS = ["#3b82f6", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6"];

/* ------------------------------------------------------------------ */
/*  Inline Guide                                                       */
/* ------------------------------------------------------------------ */
function InlineGuide({ lang }: { lang: Lang }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mb-4 rounded-xl border border-border/50 bg-card/50">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-xs text-muted-foreground hover:text-foreground"
      >
        <span className="flex items-center gap-1.5">
          <HelpCircle className="h-3.5 w-3.5" />
          {t(lang, "admin_social")}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="border-t border-border/50 px-4 py-3 text-xs text-muted-foreground space-y-1">
          <p>{t(lang, "admin_social_guide")}</p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Charts Section                                                     */
/* ------------------------------------------------------------------ */
function ChartsSection({ lang, chartData }: { lang: Lang; chartData: ChartData }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Daily Trend — Area Chart */}
      {chartData.daily.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4 md:col-span-2">
          <h3 className="text-xs font-medium text-muted-foreground mb-3">
            {t(lang, "admin_social_chart_daily")}
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData.daily}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.3} />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="total"
                  name={t(lang, "admin_social_total")}
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.1}
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="published"
                  name={t(lang, "admin_social_published_label")}
                  stroke="#22c55e"
                  fill="#22c55e"
                  fillOpacity={0.15}
                  strokeWidth={2}
                />
                <Area
                  type="monotone"
                  dataKey="failed"
                  name={t(lang, "admin_social_failed_label")}
                  stroke="#ef4444"
                  fill="#ef4444"
                  fillOpacity={0.1}
                  strokeWidth={1.5}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Platform Bar Chart */}
      {chartData.platforms.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-xs font-medium text-muted-foreground mb-3">
            {t(lang, "admin_social_chart_platform")}
          </h3>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData.platforms} barGap={4}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" strokeOpacity={0.3} />
                <XAxis dataKey="platform" tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
                <YAxis tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
                <Bar
                  dataKey="published"
                  name={t(lang, "admin_social_published_label")}
                  fill="#22c55e"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="failed"
                  name={t(lang, "admin_social_failed_label")}
                  fill="#ef4444"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Content Type Pie Chart */}
      {chartData.content_types.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-xs font-medium text-muted-foreground mb-3">
            {t(lang, "admin_social_chart_type")}
          </h3>
          <div className="h-40 flex items-center">
            <ResponsiveContainer width="60%" height="100%">
              <PieChart>
                <Pie
                  data={chartData.content_types}
                  dataKey="count"
                  nameKey="type"
                  cx="50%"
                  cy="50%"
                  outerRadius={55}
                  innerRadius={30}
                  strokeWidth={0}
                >
                  {chartData.content_types.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: 8,
                    fontSize: 11,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="flex-1 space-y-1.5">
              {chartData.content_types.map((ct, i) => (
                <div key={ct.type} className="flex items-center gap-2 text-[11px]">
                  <div
                    className="h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ background: PIE_COLORS[i % PIE_COLORS.length] }}
                  />
                  <span className="text-muted-foreground truncate">{ct.type}</span>
                  <span className="ml-auto font-medium">{ct.count}</span>
                </div>
              ))}
              {chartData.langs.length > 0 && (
                <>
                  <div className="border-t border-border/40 pt-1.5 mt-1.5">
                    <p className="text-[10px] text-muted-foreground/60 mb-1">
                      {t(lang, "admin_social_chart_lang")}
                    </p>
                  </div>
                  {chartData.langs.map((l) => (
                    <div key={l.lang} className="flex items-center gap-2 text-[11px]">
                      <span className="text-muted-foreground uppercase">{l.lang}</span>
                      <span className="ml-auto font-medium">{l.count}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Detail Modal                                                       */
/* ------------------------------------------------------------------ */
function DetailModal({
  post,
  lang,
  onClose,
  fetchWithToken,
  onRefresh,
}: {
  post: SocialPostItem;
  lang: Lang;
  onClose: () => void;
  fetchWithToken: <T>(path: string, opts?: { method?: string; body?: unknown }) => Promise<T>;
  onRefresh: () => void;
}) {
  const [previewTab, setPreviewTab] = useState<"source" | "x" | "threads">("source");
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(post.body_text);
  const [saving, setSaving] = useState(false);

  const loadPreview = async () => {
    if (preview) return;
    setLoadingPreview(true);
    try {
      const data = await fetchWithToken<PreviewData>(`/admin/social/${post.id}/preview`);
      setPreview(data);
    } catch {
      // silently fail
    } finally {
      setLoadingPreview(false);
    }
  };

  useEffect(() => {
    if (previewTab !== "source" && !preview) {
      loadPreview();
    }
  }, [previewTab]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetchWithToken(`/admin/social/${post.id}`, {
        method: "PATCH",
        body: { body_text: editText },
      });
      setEditing(false);
      setPreview(null); // force reload preview
      onRefresh();
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const previewTabs = [
    { key: "source" as const, label: t(lang, "admin_social_source_text") },
    { key: "x" as const, label: t(lang, "admin_social_preview_x") },
    { key: "threads" as const, label: t(lang, "admin_social_preview_threads") },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">{CONTENT_TYPE_LABELS[post.content_type]?.[lang] || post.content_type}</h3>
          <button onClick={onClose} className="p-1 text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-3">
          {/* Preview Tabs */}
          <div className="flex gap-1 border-b border-border pb-2">
            {previewTabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setPreviewTab(tab.key)}
                className={cn(
                  "px-3 py-1 rounded-lg text-xs transition-colors",
                  previewTab === tab.key
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary"
                )}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content Area */}
          <div>
            {previewTab === "source" && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs text-muted-foreground">{t(lang, "admin_social_body")}</p>
                  {(post.status === "pending_review" || post.status === "approved") && (
                    <button
                      onClick={() => { setEditing(!editing); setEditText(post.body_text); }}
                      className="flex items-center gap-1 text-xs text-primary hover:text-primary/80"
                    >
                      <Edit3 className="h-3 w-3" />
                      {t(lang, "admin_social_edit_body")}
                    </button>
                  )}
                </div>
                {editing ? (
                  <div className="space-y-2">
                    <textarea
                      value={editText}
                      onChange={(e) => setEditText(e.target.value)}
                      className="w-full h-32 p-2 text-sm rounded-lg border border-border bg-background resize-none"
                    />
                    <div className="flex items-center justify-between">
                      <span className={cn(
                        "text-xs",
                        editText.length > 500 ? "text-red-400" : "text-muted-foreground"
                      )}>
                        {editText.length}/500
                      </span>
                      <button
                        onClick={handleSave}
                        disabled={saving || editText.length > 500}
                        className="flex items-center gap-1 px-3 py-1 text-xs rounded-lg bg-primary text-primary-foreground disabled:opacity-50"
                      >
                        <Save className="h-3 w-3" />
                        {t(lang, "admin_social_save")}
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{post.body_text}</p>
                )}
              </div>
            )}

            {previewTab === "x" && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs text-muted-foreground">{t(lang, "admin_social_preview_x")}</p>
                  {preview && (
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded-full",
                      preview.x.char_count > preview.x.max
                        ? "bg-red-500/20 text-red-400"
                        : "bg-green-500/20 text-green-400"
                    )}>
                      {preview.x.char_count}/{preview.x.max}
                    </span>
                  )}
                </div>
                {loadingPreview ? (
                  <div className="flex justify-center py-4">
                    <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : preview ? (
                  <div className="bg-secondary/50 rounded-lg p-3">
                    <p className="text-sm whitespace-pre-wrap font-mono">{preview.x.text}</p>
                  </div>
                ) : null}
              </div>
            )}

            {previewTab === "threads" && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <p className="text-xs text-muted-foreground">{t(lang, "admin_social_preview_threads")}</p>
                  {preview && (
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded-full",
                      preview.threads.char_count > preview.threads.max
                        ? "bg-red-500/20 text-red-400"
                        : "bg-green-500/20 text-green-400"
                    )}>
                      {preview.threads.char_count}/{preview.threads.max}
                    </span>
                  )}
                </div>
                {loadingPreview ? (
                  <div className="flex justify-center py-4">
                    <div className="h-4 w-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  </div>
                ) : preview ? (
                  <div className="bg-secondary/50 rounded-lg p-3">
                    <p className="text-sm whitespace-pre-wrap font-mono">{preview.threads.text}</p>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {post.image_url && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">Card Image</p>
              <img
                src={post.image_url}
                alt="card"
                className="rounded-lg border border-border max-w-full"
              />
            </div>
          )}

          {post.hashtags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {post.hashtags.map((h, i) => (
                <span key={i} className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs">{h}</span>
              ))}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <span className="text-muted-foreground">{t(lang, "admin_status")}:</span>{" "}
              <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[post.status])}>
                {STATUS_LABELS[post.status]?.[lang] || post.status}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">{t(lang, "admin_social_risk")}:</span>{" "}
              <span className={cn("px-1.5 py-0.5 rounded text-[10px]", RISK_COLORS[post.risk_level])}>
                {post.risk_level}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground">{t(lang, "admin_created_at")}:</span>{" "}
              {new Date(post.created_at).toLocaleString(lang === "en" ? "en-US" : "ko-KR")}
            </div>
            {post.approved_by && (
              <div>
                <span className="text-muted-foreground">Approved by:</span> {post.approved_by}
              </div>
            )}
          </div>

          {post.platforms.length > 0 && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">{t(lang, "admin_social_platform")}</p>
              <div className="space-y-1">
                {post.platforms.map((p, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span>{PLATFORM_ICONS[p.platform] || p.platform}</span>
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[p.status] || "bg-gray-500/20 text-gray-400")}>
                      {STATUS_LABELS[p.status]?.[lang] || p.status}
                    </span>
                    {p.error_message && (
                      <span className="text-red-400 truncate max-w-[200px]">{p.error_message}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Auto-Approve Rules                                                 */
/* ------------------------------------------------------------------ */
interface AutoApproveRules {
  daily_movers: boolean;
  weekly_report: boolean;
  spike_alert: boolean;
}

function AutoApproveSection({
  lang,
  fetchWithToken,
}: {
  lang: "ko" | "en";
  fetchWithToken: <T>(path: string, opts?: { method?: string; body?: unknown }) => Promise<T>;
}) {
  const qc = useQueryClient();
  const { data: rules } = useQuery<AutoApproveRules>({
    queryKey: ["social-auto-approve"],
    queryFn: () => fetchWithToken("/admin/social/auto-approve-rules"),
  });

  const updateMut = useMutation({
    mutationFn: (newRules: AutoApproveRules) =>
      fetchWithToken("/admin/social/auto-approve-rules", {
        method: "PUT",
        body: newRules,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-auto-approve"] }),
  });

  if (!rules) return null;

  const items: { key: keyof AutoApproveRules; label: { ko: string; en: string }; locked?: boolean }[] = [
    { key: "daily_movers", label: { ko: "Daily Movers", en: "Daily Movers" } },
    { key: "weekly_report", label: { ko: "Weekly Report", en: "Weekly Report" } },
    { key: "spike_alert", label: { ko: "Spike Alert (수동)", en: "Spike Alert (Manual)" }, locked: true },
  ];

  return (
    <div className="rounded-xl border border-border bg-card p-4 mb-4">
      <h3 className="text-xs font-semibold text-muted-foreground mb-3">
        {lang === "ko" ? "자동 승인 규칙" : "Auto-Approve Rules"}
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {items.map((item) => (
          <div
            key={item.key}
            className={cn(
              "flex items-center justify-between rounded-lg border px-3 py-2.5",
              item.locked ? "border-border/50 opacity-60" : "border-border"
            )}
          >
            <span className="text-sm">{item.label[lang]}</span>
            <button
              disabled={item.locked || updateMut.isPending}
              onClick={() => {
                if (item.locked) return;
                updateMut.mutate({ ...rules, [item.key]: !rules[item.key] });
              }}
              className={cn(
                "relative inline-flex h-5 w-9 items-center rounded-full transition-colors",
                item.locked
                  ? "bg-secondary cursor-not-allowed"
                  : rules[item.key]
                    ? "bg-green-500 cursor-pointer"
                    : "bg-secondary cursor-pointer"
              )}
            >
              <span
                className={cn(
                  "inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform",
                  rules[item.key] ? "translate-x-4" : "translate-x-1"
                )}
              />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function AdminSocialPage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const qc = useQueryClient();

  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [contentTypeFilter, setContentTypeFilter] = useState<string>("");
  const [platformFilter, setPlatformFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selectedPost, setSelectedPost] = useState<SocialPostItem | null>(null);
  const [showCharts, setShowCharts] = useState(true);

  const fetchWithToken = async <T,>(path: string, opts?: { method?: string; body?: unknown }): Promise<T> => {
    const token = await user?.getIdToken();
    if (!token) throw new Error("No token");
    const res = await fetch(`${API_BASE}${path}`, {
      method: opts?.method ?? "GET",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      ...(opts?.body ? { body: JSON.stringify(opts.body) } : {}),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  };

  // Stats
  const { data: stats } = useQuery<SocialStats>({
    queryKey: ["social-stats"],
    queryFn: () => fetchWithToken("/admin/social/stats"),
    refetchInterval: 30_000,
  });

  // Chart data
  const { data: chartData } = useQuery<ChartData>({
    queryKey: ["social-chart"],
    queryFn: () => fetchWithToken("/admin/social/chart-data?days=14"),
    refetchInterval: 60_000,
  });

  // List
  const params = new URLSearchParams();
  params.set("page", String(page));
  if (statusFilter !== "all") params.set("status", statusFilter);
  if (contentTypeFilter) params.set("content_type", contentTypeFilter);
  if (platformFilter) params.set("platform", platformFilter);
  if (search) params.set("q", search);

  const { data, isLoading } = useQuery<SocialResponse>({
    queryKey: ["social-posts", page, statusFilter, contentTypeFilter, platformFilter, search],
    queryFn: () => fetchWithToken(`/admin/social?${params.toString()}`),
    refetchInterval: 15_000,
  });

  const perPage = 20;
  const totalPages = Math.ceil((data?.total || 0) / perPage);

  // Mutations
  const approveMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/approve`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });
  const approveXMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/approve/x`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });
  const approveThreadsMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/approve/threads`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });
  const rejectMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/reject`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });
  const retryMut = useMutation({
    mutationFn: (id: string) => fetchWithToken(`/admin/social/${id}/retry`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["social-posts"] }),
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Share2 className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-bold">{t(lang, "admin_social")}</h1>
        </div>
        <button
          onClick={() => setShowCharts(!showCharts)}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-colors",
            showCharts
              ? "bg-primary/10 text-primary"
              : "bg-secondary text-muted-foreground hover:text-foreground"
          )}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          {t(lang, "admin_social_chart_daily")}
        </button>
      </div>

      <InlineGuide lang={lang} />

      {/* Auto-Approve Rules */}
      <AutoApproveSection lang={lang} fetchWithToken={fetchWithToken} />

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_pending")}</p>
            <p className="text-xl font-bold text-yellow-400">{stats.pending}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_today")}</p>
            <p className="text-xl font-bold text-green-400">{stats.published_today}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_week")}</p>
            <p className="text-xl font-bold text-blue-400">{stats.published_week}</p>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <p className="text-xs text-muted-foreground">{t(lang, "admin_social_failed")}</p>
            <p className="text-xl font-bold text-orange-400">{stats.failed}</p>
          </div>
        </div>
      )}

      {/* Charts */}
      {showCharts && chartData && <ChartsSection lang={lang} chartData={chartData} />}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        {/* Status tabs */}
        <div className="flex gap-1 overflow-x-auto">
          {STATUS_TABS.map((s) => (
            <button
              key={s}
              onClick={() => { setStatusFilter(s); setPage(1); }}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs whitespace-nowrap transition-colors",
                statusFilter === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              {s === "all"
                ? t(lang, "admin_all")
                : STATUS_LABELS[s]?.[lang] || s}
            </button>
          ))}
        </div>

        {/* Platform filter tabs */}
        <div className="flex gap-1">
          {PLATFORM_FILTER_TABS.map((pf) => (
            <button
              key={pf.key}
              onClick={() => { setPlatformFilter(pf.key); setPage(1); }}
              className={cn(
                "px-2.5 py-1.5 rounded-lg text-xs whitespace-nowrap transition-colors",
                platformFilter === pf.key
                  ? "bg-primary/20 text-primary border border-primary/30"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              {pf.label[lang]}
            </button>
          ))}
        </div>

        {/* Content type dropdown */}
        <select
          value={contentTypeFilter}
          onChange={(e) => { setContentTypeFilter(e.target.value); setPage(1); }}
          className="px-2 py-1.5 rounded-lg bg-secondary text-xs border-none"
        >
          <option value="">{t(lang, "admin_all")}</option>
          <option value="daily_movers">Daily Movers</option>
          <option value="spike_alert">Spike Alert</option>
          <option value="weekly_recap">Weekly Recap</option>
        </select>

        {/* Search */}
        <div className="relative flex-1 min-w-[180px]">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder={t(lang, "admin_search")}
            className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-secondary text-xs border-none placeholder:text-muted-foreground/50"
          />
        </div>
      </div>

      {/* Table (desktop) / Cards (mobile) */}
      {isLoading ? (
        <div className="flex justify-center py-12">
          <div className="h-5 w-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : !data?.items.length ? (
        <p className="text-center text-sm text-muted-foreground py-12">{t(lang, "admin_no_data")}</p>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden md:block overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-border bg-card/50">
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">Type</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">Lang</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground max-w-[300px]">{t(lang, "admin_social_body")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_status")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_social_risk")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_social_platform")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_created_at")}</th>
                  <th className="px-3 py-2 text-left font-medium text-muted-foreground">{t(lang, "admin_actions")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((post) => (
                  <tr key={post.id} className="border-b border-border/50 hover:bg-card/30">
                    <td className="px-3 py-2">
                      <span className="text-[10px] font-medium">
                        {CONTENT_TYPE_LABELS[post.content_type]?.[lang] || post.content_type}
                      </span>
                    </td>
                    <td className="px-3 py-2 uppercase">{post.lang}</td>
                    <td className="px-3 py-2 max-w-[300px] truncate">{post.body_text}</td>
                    <td className="px-3 py-2">
                      <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[post.status])}>
                        {STATUS_LABELS[post.status]?.[lang] || post.status}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <span className={cn("px-1.5 py-0.5 rounded text-[10px]", RISK_COLORS[post.risk_level])}>
                        {post.risk_level}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex gap-1">
                        {post.platforms.map((p, i) => (
                          <span
                            key={i}
                            title={`${p.platform}: ${p.status}`}
                            className={cn("text-sm", p.status === "skipped" && "opacity-40")}
                          >
                            {PLATFORM_ICONS[p.platform] || p.platform}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {new Date(post.created_at).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR")}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => setSelectedPost(post)}
                          className="p-1 text-muted-foreground hover:text-foreground"
                          title="View"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>
                        {post.status === "pending_review" && (
                          <>
                            <button
                              onClick={() => approveMut.mutate(post.id)}
                              className="p-1 text-green-400 hover:text-green-300"
                              title={t(lang, "admin_social_approve_all")}
                            >
                              <CheckCircle className="h-3.5 w-3.5" />
                            </button>
                            <button
                              onClick={() => approveXMut.mutate(post.id)}
                              className="p-1 text-blue-400 hover:text-blue-300 text-[10px] font-bold"
                              title={t(lang, "admin_social_approve_x")}
                            >
                              {"\ud835\udd4f"}
                            </button>
                            <button
                              onClick={() => approveThreadsMut.mutate(post.id)}
                              className="p-1 text-purple-400 hover:text-purple-300 text-[10px]"
                              title={t(lang, "admin_social_approve_threads")}
                            >
                              {"\ud83e\uddf5"}
                            </button>
                            <button
                              onClick={() => rejectMut.mutate(post.id)}
                              className="p-1 text-red-400 hover:text-red-300"
                              title={t(lang, "admin_social_reject")}
                            >
                              <XCircle className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                        {post.status === "failed" && (
                          <button
                            onClick={() => retryMut.mutate(post.id)}
                            className="p-1 text-orange-400 hover:text-orange-300"
                            title={t(lang, "admin_social_retry")}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="md:hidden space-y-2">
            {data.items.map((post) => (
              <div
                key={post.id}
                onClick={() => setSelectedPost(post)}
                className="rounded-xl border border-border bg-card p-3 space-y-2 cursor-pointer active:bg-card/80"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-medium">
                    {CONTENT_TYPE_LABELS[post.content_type]?.[lang] || post.content_type}
                  </span>
                  <span className={cn("px-1.5 py-0.5 rounded text-[10px]", STATUS_COLORS[post.status])}>
                    {STATUS_LABELS[post.status]?.[lang] || post.status}
                  </span>
                </div>
                <p className="text-xs line-clamp-2">{post.body_text}</p>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={cn("px-1.5 py-0.5 rounded text-[10px]", RISK_COLORS[post.risk_level])}>
                      {post.risk_level}
                    </span>
                    {post.platforms.map((p, i) => (
                      <span
                        key={i}
                        className={cn("text-xs", p.status === "skipped" && "opacity-40")}
                      >
                        {PLATFORM_ICONS[p.platform] || p.platform}
                      </span>
                    ))}
                  </div>
                  <div className="flex items-center gap-1">
                    {post.status === "pending_review" && (
                      <>
                        <button
                          onClick={(e) => { e.stopPropagation(); approveMut.mutate(post.id); }}
                          className="p-1 text-green-400"
                          title={t(lang, "admin_social_approve_all")}
                        >
                          <CheckCircle className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); approveXMut.mutate(post.id); }}
                          className="p-1 text-blue-400 text-xs font-bold"
                          title={t(lang, "admin_social_approve_x")}
                        >
                          {"\ud835\udd4f"}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); approveThreadsMut.mutate(post.id); }}
                          className="p-1 text-purple-400 text-xs"
                          title={t(lang, "admin_social_approve_threads")}
                        >
                          {"\ud83e\uddf5"}
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); rejectMut.mutate(post.id); }}
                          className="p-1 text-red-400"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                      </>
                    )}
                    {post.status === "failed" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); retryMut.mutate(post.id); }}
                        className="p-1 text-orange-400"
                      >
                        <RefreshCw className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="p-1.5 rounded-lg border border-border disabled:opacity-30"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="text-xs text-muted-foreground">
                {page} / {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                className="p-1.5 rounded-lg border border-border disabled:opacity-30"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          )}
        </>
      )}

      {/* Detail Modal */}
      {selectedPost && (
        <DetailModal
          post={selectedPost}
          lang={lang}
          onClose={() => setSelectedPost(null)}
          fetchWithToken={fetchWithToken}
          onRefresh={() => {
            qc.invalidateQueries({ queryKey: ["social-posts"] });
          }}
        />
      )}
    </div>
  );
}

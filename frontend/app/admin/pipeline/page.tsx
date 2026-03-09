"use client";

import { useState, useRef, useCallback } from "react";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Radio, FileText, Copy, Layers, Zap, TrendingUp,
  Activity, Bell, RefreshCw, ChevronDown, ChevronUp,
  AlertTriangle, CheckCircle, ArrowUpRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAdminToast } from "@/components/ui/admin-toast";
import { adminFetch } from "@/lib/admin-utils";
import Link from "next/link";

/* ─── types ─── */
interface PipelineStats {
  total_sources: number;
  active_sources: number;
  error_sources: number;
  rss_count: number;
  telegram_count: number;
  events_24h: number;
  unclassified_rate: number;
  translation_fail_rate: number;
  geo_fail_rate: number;
  topic_distribution: { topic: string; count: number }[];
  raw_24h: number;
  duplicates_24h: number;
  active_clusters: number;
  noise_clusters: number;
  spike_clusters: number;  // backend API field name retained
  push_tokens: number;
  push_web: number;
  push_android: number;
  push_ios: number;
  crisis_countries: number;
  alert_sent_6h: number;
  alert_failed_6h: number;
  alert_pending: number;
  alert_suppressed_6h: number;
  spike_total_6h: number;
  spike_delivered_6h: number;
  spike_undelivered_6h: number;
  sns_pending_review: number;
  sns_approved: number;
  sns_published_24h: number;
  sns_failed_24h: number;
}

interface ClusterItem {
  id: number;
  title: string;
  title_ko: string;
  topic: string;
  severity: number;
  kscore: number;
  country_code: string;
}

interface TrendingItem {
  id: number;
  keyword: string;
  keyword_ko: string;
  kscore: number;
  event_count: number;
}

interface TensionItem {
  country_code: string;
  raw_score: number;
  tension_level: number;
}

interface SourceItem {
  id: number;
  display_name: string;
  source_type: string;
  is_active: boolean;
  collect_status: { status: string; error?: string } | null;
}

/* ─── health helpers ─── */
type Health = "green" | "yellow" | "red";

function getStageHealth(stats: PipelineStats | undefined, stage: number): Health {
  if (!stats) return "green";
  switch (stage) {
    case 0: return stats.error_sources > 3 ? "red" : stats.error_sources > 0 ? "yellow" : "green";
    case 1: return stats.unclassified_rate > 0.1 ? "red" : stats.unclassified_rate > 0.05 ? "yellow" : "green";
    case 2: return "green";
    case 3: return stats.noise_clusters > 20 ? "red" : stats.noise_clusters > 10 ? "yellow" : "green";
    case 4: return stats.spike_clusters > 5 ? "red" : stats.spike_clusters > 2 ? "yellow" : "green";
    case 5: {
      // Alert Delivery health
      const totalAlert = (stats.alert_sent_6h || 0) + (stats.alert_failed_6h || 0);
      if (totalAlert > 0) {
        const rate = stats.alert_sent_6h / totalAlert;
        if (rate < 0.7) return "red";
        if (rate < 0.9) return "yellow";
      }
      if ((stats.spike_undelivered_6h || 0) > 0) return "yellow";
      return "green";
    }
    case 6: return "green"; // KScore (was 5)
    case 7: return stats.crisis_countries > 3 ? "red" : stats.crisis_countries > 1 ? "yellow" : "green"; // Tension (was 6)
    case 8: return "green"; // Trending (was 7)
    case 9: return stats.push_tokens === 0 ? "red" : "green"; // Push (was 8)
    case 10: return "green"; // Orphan (was 9)
    default: return "green";
  }
}

const HEALTH_COLORS: Record<Health, string> = { green: "bg-green-500", yellow: "bg-yellow-500", red: "bg-red-500" };
const HEALTH_RING: Record<Health, string> = { green: "ring-green-500/30", yellow: "ring-yellow-500/30", red: "ring-red-500/30" };

/* ─── stage config ─── */
const STAGE_KEYS = [
  "pipeline_stage_collect", "pipeline_stage_normalize", "pipeline_stage_dedup",
  "pipeline_stage_cluster", "pipeline_stage_kscore_alert", "pipeline_stage_alert_delivery",
  "pipeline_stage_kscore", "pipeline_stage_tension", "pipeline_stage_trending",
  "pipeline_stage_push", "pipeline_stage_orphan",
] as const;

const STAGE_ICONS = [Radio, FileText, Copy, Layers, Zap, Bell, TrendingUp, Activity, TrendingUp, Bell, RefreshCw];

// 각 스테이지의 상세 관리 페이지 링크
const STAGE_DETAIL_HREFS = [
  "/admin/sources", "/admin/events", null, "/admin/clusters", "/admin/clusters",
  null, "/admin/kscore", "/admin/tension", "/admin/kscore", null, null,
];

const ARROW_LABELS = [
  "pipeline_label_raw", "pipeline_label_normalized", "pipeline_label_deduped",
  "pipeline_label_clustered", "pipeline_label_alerted", "pipeline_label_scored",
  "pipeline_label_tension", "pipeline_label_trending", "pipeline_label_notification",
  "pipeline_label_orphan",
] as const;

/* ─── stat pill ─── */
function Pill({ label, value, warn }: { label: string; value: string | number; warn?: boolean }) {
  return (
    <div className={cn(
      "flex items-center justify-between px-3 py-1.5 rounded-lg text-xs",
      warn ? "bg-red-500/10 text-red-400" : "bg-secondary"
    )}>
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-semibold">{value}</span>
    </div>
  );
}

/* ─── arrow connector ─── */
function Arrow({ label, lang }: { label: typeof ARROW_LABELS[number]; lang: Lang }) {
  return (
    <div className="flex flex-col items-center py-1">
      <div className="w-px h-4 bg-border" />
      <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">
        {t(lang, label)}
      </span>
      <div className="w-px h-4 bg-border" />
      <ChevronDown className="h-3 w-3 text-muted-foreground -mt-1" />
    </div>
  );
}

/* ─── stage card wrapper ─── */
function StageCard({
  index, lang, health, sectionRef, children,
}: {
  index: number; lang: Lang; health: Health;
  sectionRef: (el: HTMLDivElement | null) => void;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  const Icon = STAGE_ICONS[index];
  const detailHref = STAGE_DETAIL_HREFS[index];

  return (
    <div ref={sectionRef} className="w-full max-w-xl mx-auto">
      <div className={cn(
        "border rounded-xl bg-card overflow-hidden",
        health === "red" ? "border-red-500/40" : health === "yellow" ? "border-yellow-500/40" : "border-border"
      )}>
        <div className="flex items-center">
          <button
            onClick={() => setOpen(!open)}
            className="flex items-center flex-1 gap-3 px-4 py-3 text-left hover:bg-secondary/50 transition-colors"
          >
            <div className={cn("h-2.5 w-2.5 rounded-full ring-2", HEALTH_COLORS[health], HEALTH_RING[health])} />
            <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="text-sm font-semibold flex-1">{t(lang, STAGE_KEYS[index])}</span>
            {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
          </button>
          {detailHref && (
            <Link
              href={detailHref}
              className="px-3 py-3 text-muted-foreground hover:text-primary transition-colors border-l border-border"
              title={t(lang, "pipeline_view_all")}
            >
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          )}
        </div>
        {open && <div className="px-4 pb-4 space-y-2 border-t border-border pt-3">{children}</div>}
      </div>
    </div>
  );
}

/* ─── action button ─── */
function ActionBtn({
  label, onClick, loading, variant = "default",
}: {
  label: string; onClick: () => void; loading?: boolean;
  variant?: "default" | "destructive";
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={cn(
        "px-3 py-1.5 text-xs rounded-lg font-medium transition-colors disabled:opacity-50",
        variant === "destructive"
          ? "bg-red-500/10 text-red-400 hover:bg-red-500/20"
          : "bg-primary/10 text-primary hover:bg-primary/20"
      )}
    >
      {loading ? <RefreshCw className="h-3 w-3 animate-spin inline mr-1" /> : null}
      {label}
    </button>
  );
}

/* ═══ MAIN PAGE ═══ */
export default function AdminPipelinePage() {
  const { user } = useAuth();
  const { lang } = useAppStore();
  const queryClient = useQueryClient();
  const { toast } = useAdminToast();
  const sectionRefs = useRef<(HTMLDivElement | null)[]>([]);

  /* ─── queries ─── */
  const { data: stats, isLoading } = useQuery<PipelineStats>({
    queryKey: ["pipeline-stats"],
    queryFn: () => adminFetch("/admin/pipeline/stats"),
    refetchInterval: 30_000,
  });

  const { data: trendingData } = useQuery<TrendingItem[]>({
    queryKey: ["admin-trending-pipeline"],
    queryFn: () => adminFetch("/admin/trending"),
    refetchInterval: 60_000,
  });

  const { data: tensionData } = useQuery<TensionItem[]>({
    queryKey: ["admin-tension-pipeline"],
    queryFn: () => adminFetch("/admin/tension"),
    refetchInterval: 60_000,
  });

  const { data: clustersData } = useQuery<{ items: ClusterItem[] }>({
    queryKey: ["admin-clusters-pipeline"],
    queryFn: () => adminFetch("/admin/clusters?limit=5"),
    refetchInterval: 60_000,
  });

  const { data: spikeClustersData } = useQuery<{ items: ClusterItem[] }>({
    queryKey: ["admin-spike-clusters-pipeline"],
    queryFn: () => adminFetch("/admin/spike-clusters"),
    refetchInterval: 60_000,
  });

  const { data: sourcesData } = useQuery<{ items: SourceItem[] }>({
    queryKey: ["admin-sources-pipeline"],
    queryFn: () => adminFetch("/admin/sources?limit=100"),
    refetchInterval: 60_000,
  });

  /* ─── mutations ─── */
  const reprocessMut = useMutation({
    mutationFn: () => adminFetch("/admin/reprocess-events", { method: "POST" }),
    onSuccess: () => {
      toast(t(lang, "pipeline_reprocess_done"), "success");
      queryClient.invalidateQueries({ queryKey: ["pipeline-stats"] });
    },
    onError: () => toast(t(lang, "pipeline_reprocess_fail"), "error"),
  });

  const tensionRecalcMut = useMutation({
    mutationFn: () => adminFetch("/admin/tension/recalculate", { method: "POST" }),
    onSuccess: () => {
      toast(t(lang, "pipeline_tension_done"), "success");
      queryClient.invalidateQueries({ queryKey: ["admin-tension-pipeline"] });
    },
    onError: () => toast(t(lang, "pipeline_recalc_fail"), "error"),
  });

  const trendingRecalcMut = useMutation({
    mutationFn: () => adminFetch("/admin/trending/recalculate", { method: "POST" }),
    onSuccess: () => {
      toast(t(lang, "pipeline_trending_done"), "success");
      queryClient.invalidateQueries({ queryKey: ["admin-trending-pipeline"] });
    },
    onError: () => toast(t(lang, "pipeline_recalc_fail"), "error"),
  });

  const testPushMut = useMutation({
    mutationFn: () => adminFetch("/admin/test-push", { method: "POST", body: {} }),
    onSuccess: () => toast(t(lang, "pipeline_push_done"), "success"),
    onError: () => toast(t(lang, "pipeline_push_fail"), "error"),
  });

  const orphanMut = useMutation({
    mutationFn: () => adminFetch<{ reprocessed: number }>("/admin/trigger-orphan-reprocess", { method: "POST" }),
    onSuccess: (data) => {
      toast(`${t(lang, "pipeline_orphan_done")} (${data.reprocessed})`, "success");
      queryClient.invalidateQueries({ queryKey: ["pipeline-stats"] });
    },
    onError: () => toast(t(lang, "pipeline_orphan_fail"), "error"),
  });

  const deactivateClusterMut = useMutation({
    mutationFn: (id: number) =>
      adminFetch(`/admin/clusters/${id}`, { method: "PATCH", body: { severity: 0 } }),
    onSuccess: () => {
      toast(t(lang, "admin_toast_updated"), "success");
      queryClient.invalidateQueries({ queryKey: ["admin-clusters-pipeline"] });
      queryClient.invalidateQueries({ queryKey: ["admin-spike-clusters-pipeline"] });
      queryClient.invalidateQueries({ queryKey: ["pipeline-stats"] });
    },
  });

  const patchSourceMut = useMutation({
    mutationFn: (id: number) =>
      adminFetch(`/admin/sources/${id}`, { method: "PATCH", body: { is_active: false } }),
    onSuccess: () => {
      toast(t(lang, "admin_toast_updated"), "success");
      queryClient.invalidateQueries({ queryKey: ["admin-sources-pipeline"] });
      queryClient.invalidateQueries({ queryKey: ["pipeline-stats"] });
    },
  });

  /* ─── inline editing state ─── */
  const [editingCluster, setEditingCluster] = useState<number | null>(null);
  const [editTopic, setEditTopic] = useState("");
  const [editSeverity, setEditSeverity] = useState(0);

  const patchClusterMut = useMutation({
    mutationFn: ({ id, topic, severity }: { id: number; topic: string; severity: number }) =>
      adminFetch(`/admin/clusters/${id}`, { method: "PATCH", body: { topic, severity } }),
    onSuccess: () => {
      setEditingCluster(null);
      toast(t(lang, "admin_toast_updated"), "success");
      queryClient.invalidateQueries({ queryKey: ["admin-clusters-pipeline"] });
      queryClient.invalidateQueries({ queryKey: ["admin-spike-clusters-pipeline"] });
    },
  });

  const scrollTo = useCallback((idx: number) => {
    sectionRefs.current[idx]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  /* ─── derived data ─── */
  const errorSources = sourcesData?.items?.filter(
    (s) => s.is_active && s.collect_status?.status === "error"
  ) ?? [];
  const trending = trendingData ?? [];
  const tensions = tensionData ?? [];
  const clusters = clustersData?.items ?? [];
  const spikeClusters = spikeClustersData?.items ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      <h1 className="text-lg font-bold">{t(lang, "pipeline_title")}</h1>

      {/* Health Bar */}
      <div className="flex items-center gap-1.5 flex-wrap pb-2">
        <span className="text-xs text-muted-foreground mr-1">{t(lang, "pipeline_health")}:</span>
        {STAGE_KEYS.map((key, i) => {
          const h = getStageHealth(stats, i);
          return (
            <button
              key={i}
              onClick={() => scrollTo(i)}
              title={t(lang, key)}
              className={cn(
                "h-3.5 w-3.5 rounded-full ring-2 transition-transform hover:scale-125 cursor-pointer",
                HEALTH_COLORS[h], HEALTH_RING[h]
              )}
            />
          );
        })}
      </div>

      {/* Vertical Flow */}
      <div className="flex flex-col items-center gap-0">
        {/* Stage 0: 수집 */}
        <StageCard index={0} lang={lang} health={getStageHealth(stats, 0)} sectionRef={(el) => (sectionRefs.current[0] = el)}>
          <div className="grid grid-cols-2 gap-2">
            <Pill label={t(lang, "pipeline_active_sources")} value={`${stats?.active_sources ?? 0} / ${stats?.total_sources ?? 0}`} />
            <Pill label={t(lang, "pipeline_error_sources")} value={stats?.error_sources ?? 0} warn={(stats?.error_sources ?? 0) > 0} />
            <Pill label="RSS" value={stats?.rss_count ?? 0} />
            <Pill label="Telegram" value={stats?.telegram_count ?? 0} />
          </div>
          {errorSources.length > 0 && (
            <div className="mt-2 space-y-1">
              <p className="text-xs font-semibold text-red-400 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                {t(lang, "pipeline_error_sources_title")}
              </p>
              {errorSources.slice(0, 5).map((s) => (
                <div key={s.id} className="flex items-center justify-between text-xs bg-red-500/5 px-3 py-1.5 rounded-lg">
                  <span>{s.display_name} <span className="text-muted-foreground">({s.source_type})</span></span>
                  <ActionBtn
                    label={t(lang, "pipeline_disable")}
                    variant="destructive"
                    onClick={() => patchSourceMut.mutate(s.id)}
                    loading={patchSourceMut.isPending}
                  />
                </div>
              ))}
            </div>
          )}
        </StageCard>

        <Arrow label="pipeline_label_raw" lang={lang} />

        {/* Stage 1: 정규화 */}
        <StageCard index={1} lang={lang} health={getStageHealth(stats, 1)} sectionRef={(el) => (sectionRefs.current[1] = el)}>
          <div className="grid grid-cols-2 gap-2">
            <Pill label={t(lang, "pipeline_events_24h")} value={stats?.events_24h ?? 0} />
            <Pill label={t(lang, "pipeline_unclassified")} value={`${((stats?.unclassified_rate ?? 0) * 100).toFixed(1)}%`} warn={(stats?.unclassified_rate ?? 0) > 0.05} />
            <Pill label={t(lang, "pipeline_translation_fail")} value={`${((stats?.translation_fail_rate ?? 0) * 100).toFixed(1)}%`} warn={(stats?.translation_fail_rate ?? 0) > 0.05} />
            <Pill label={t(lang, "pipeline_geo_fail")} value={`${((stats?.geo_fail_rate ?? 0) * 100).toFixed(1)}%`} warn={(stats?.geo_fail_rate ?? 0) > 0.1} />
          </div>
          {stats?.topic_distribution && stats.topic_distribution.length > 0 && (
            <div className="mt-2">
              <p className="text-[10px] text-muted-foreground mb-1">{t(lang, "pipeline_topic_dist")}</p>
              <div className="flex flex-wrap gap-1">
                {stats.topic_distribution.slice(0, 8).map((td) => (
                  <span key={td.topic} className="text-[10px] px-2 py-0.5 rounded-full bg-secondary">
                    {td.topic}: {td.count}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="flex gap-2 mt-2">
            <ActionBtn label={t(lang, "pipeline_reprocess")} onClick={() => reprocessMut.mutate()} loading={reprocessMut.isPending} />
          </div>
        </StageCard>

        <Arrow label="pipeline_label_normalized" lang={lang} />

        {/* Stage 2: 중복제거 */}
        <StageCard index={2} lang={lang} health={getStageHealth(stats, 2)} sectionRef={(el) => (sectionRefs.current[2] = el)}>
          <div className="grid grid-cols-3 gap-2">
            <Pill label={t(lang, "pipeline_raw_events")} value={stats?.raw_24h ?? 0} />
            <Pill label={t(lang, "pipeline_unique_events")} value={stats?.events_24h ?? 0} />
            <Pill
              label={t(lang, "pipeline_dup_rate")}
              value={stats?.raw_24h ? `${((stats.duplicates_24h / stats.raw_24h) * 100).toFixed(1)}%` : "0%"}
            />
          </div>
        </StageCard>

        <Arrow label="pipeline_label_deduped" lang={lang} />

        {/* Stage 3: 클러스터링 */}
        <StageCard index={3} lang={lang} health={getStageHealth(stats, 3)} sectionRef={(el) => (sectionRefs.current[3] = el)}>
          <div className="grid grid-cols-3 gap-2">
            <Pill label={t(lang, "pipeline_active_clusters")} value={stats?.active_clusters ?? 0} />
            <Pill label={t(lang, "pipeline_noise_clusters")} value={stats?.noise_clusters ?? 0} warn={(stats?.noise_clusters ?? 0) > 10} />
            <Pill label={t(lang, "pipeline_kscore_alert_clusters")} value={stats?.spike_clusters ?? 0} />
          </div>
          {clusters.length > 0 && (
            <div className="mt-2 space-y-1">
              <p className="text-[10px] text-muted-foreground">{t(lang, "pipeline_recent_clusters")}</p>
              {clusters.slice(0, 5).map((c) => (
                <div key={c.id} className="flex items-center gap-2 text-xs bg-secondary/50 px-3 py-1.5 rounded-lg">
                  {editingCluster === c.id ? (
                    <div className="flex-1 flex items-center gap-2 flex-wrap">
                      <input
                        className="bg-background border border-border rounded px-2 py-0.5 text-xs w-24"
                        value={editTopic}
                        onChange={(e) => setEditTopic(e.target.value)}
                        placeholder="topic"
                      />
                      <input
                        type="number"
                        className="bg-background border border-border rounded px-2 py-0.5 text-xs w-16"
                        value={editSeverity}
                        onChange={(e) => setEditSeverity(Number(e.target.value))}
                      />
                      <ActionBtn
                        label={t(lang, "admin_save")}
                        onClick={() => patchClusterMut.mutate({ id: c.id, topic: editTopic, severity: editSeverity })}
                        loading={patchClusterMut.isPending}
                      />
                      <button className="text-[10px] text-muted-foreground" onClick={() => setEditingCluster(null)}>
                        {t(lang, "admin_cancel")}
                      </button>
                    </div>
                  ) : (
                    <>
                      <span className="flex-1 truncate">{lang === "ko" ? c.title_ko || c.title : c.title}</span>
                      <span className="text-[10px] text-muted-foreground">{c.topic}</span>
                      <span className="text-[10px] font-mono">{c.severity}</span>
                      <button
                        className="text-[10px] text-primary hover:underline"
                        onClick={() => { setEditingCluster(c.id); setEditTopic(c.topic); setEditSeverity(c.severity); }}
                      >
                        {t(lang, "admin_edit")}
                      </button>
                      <ActionBtn
                        label={t(lang, "pipeline_deactivate")}
                        variant="destructive"
                        onClick={() => deactivateClusterMut.mutate(c.id)}
                        loading={deactivateClusterMut.isPending}
                      />
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </StageCard>

        <Arrow label="pipeline_label_clustered" lang={lang} />

        {/* Stage 4: KScore 알림 */}
        <StageCard index={4} lang={lang} health={getStageHealth(stats, 4)} sectionRef={(el) => (sectionRefs.current[4] = el)}>
          <Pill label={t(lang, "pipeline_kscore_alert_clusters")} value={stats?.spike_clusters ?? 0} warn={(stats?.spike_clusters ?? 0) > 2} />
          {spikeClusters.length > 0 ? (
            <div className="mt-2 space-y-1">
              {spikeClusters.map((c) => (
                <div key={c.id} className="flex items-center justify-between text-xs bg-yellow-500/5 px-3 py-1.5 rounded-lg">
                  <span className="truncate flex-1">{lang === "ko" ? c.title_ko || c.title : c.title}</span>
                  <ActionBtn
                    label={t(lang, "pipeline_deactivate")}
                    variant="destructive"
                    onClick={() => deactivateClusterMut.mutate(c.id)}
                    loading={deactivateClusterMut.isPending}
                  />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
              <CheckCircle className="h-3 w-3 text-green-500" />
              {t(lang, "pipeline_no_kscore_alerts")}
            </p>
          )}
        </StageCard>

        <Arrow label="pipeline_label_alerted" lang={lang} />

        {/* Stage 5: 알림 전달 */}
        <StageCard index={5} lang={lang} health={getStageHealth(stats, 5)} sectionRef={(el) => (sectionRefs.current[5] = el)}>
          {/* FCM 전달 현황 */}
          <p className="text-[10px] font-medium text-muted-foreground mb-1">{t(lang, "pipeline_alert_fcm")}</p>
          <div className="grid grid-cols-4 gap-2">
            <Pill label={t(lang, "pipeline_alert_sent")} value={stats?.alert_sent_6h ?? 0} />
            <Pill label={t(lang, "pipeline_alert_failed")} value={stats?.alert_failed_6h ?? 0} warn={(stats?.alert_failed_6h ?? 0) > 5} />
            <Pill label={t(lang, "pipeline_alert_pending")} value={stats?.alert_pending ?? 0} warn={(stats?.alert_pending ?? 0) > 20} />
            <Pill label={t(lang, "pipeline_alert_suppressed")} value={stats?.alert_suppressed_6h ?? 0} />
          </div>

          {/* KScore 알림 전달 */}
          <p className="text-[10px] font-medium text-muted-foreground mb-1 mt-3">{t(lang, "pipeline_alert_kscore")}</p>
          <div className="grid grid-cols-3 gap-2">
            <Pill label={t(lang, "pipeline_alert_kscore_total")} value={stats?.spike_total_6h ?? 0} />
            <Pill label={t(lang, "pipeline_alert_kscore_delivered")} value={stats?.spike_delivered_6h ?? 0} />
            <Pill label={t(lang, "pipeline_alert_kscore_undelivered")} value={stats?.spike_undelivered_6h ?? 0} warn={(stats?.spike_undelivered_6h ?? 0) > 0} />
          </div>
          {(stats?.spike_undelivered_6h ?? 0) > 0 && (
            <p className="text-[10px] text-red-400 flex items-center gap-1 mt-1">
              <AlertTriangle className="h-3 w-3" />
              {t(lang, "pipeline_alert_kscore_warning")}
            </p>
          )}

          {/* SNS 소셜 포스트 현황 */}
          <p className="text-[10px] font-medium text-muted-foreground mb-1 mt-3">{t(lang, "pipeline_alert_sns")}</p>
          <div className="grid grid-cols-4 gap-2">
            <Pill label={t(lang, "pipeline_alert_sns_pending")} value={stats?.sns_pending_review ?? 0} />
            <Pill label={t(lang, "pipeline_alert_sns_approved")} value={stats?.sns_approved ?? 0} />
            <Pill label={t(lang, "pipeline_alert_sns_published")} value={stats?.sns_published_24h ?? 0} />
            <Pill label={t(lang, "pipeline_alert_sns_failed")} value={stats?.sns_failed_24h ?? 0} warn={(stats?.sns_failed_24h ?? 0) > 0} />
          </div>

          {/* 전체 알림 성공률 */}
          {((stats?.alert_sent_6h ?? 0) + (stats?.alert_failed_6h ?? 0)) > 0 && (
            <div className="mt-3 flex items-center gap-2">
              <div className="flex-1 h-2 bg-secondary rounded-full overflow-hidden">
                <div
                  className="h-full bg-green-500 rounded-full transition-all"
                  style={{
                    width: `${Math.round((stats!.alert_sent_6h / (stats!.alert_sent_6h + stats!.alert_failed_6h)) * 100)}%`,
                  }}
                />
              </div>
              <span className="text-[10px] font-mono text-muted-foreground">
                {Math.round((stats!.alert_sent_6h / (stats!.alert_sent_6h + stats!.alert_failed_6h)) * 100)}%
              </span>
            </div>
          )}
        </StageCard>

        <Arrow label="pipeline_label_scored" lang={lang} />

        {/* Stage 6: KScore */}
        <StageCard index={6} lang={lang} health={getStageHealth(stats, 6)} sectionRef={(el) => (sectionRefs.current[6] = el)}>
          {trending.length > 0 ? (
            <div className="space-y-1">
              <p className="text-[10px] text-muted-foreground">{t(lang, "pipeline_top5_trending")}</p>
              {trending.slice(0, 5).map((kw) => (
                <div key={kw.id} className="flex items-center justify-between text-xs bg-secondary/50 px-3 py-1.5 rounded-lg">
                  <span>{lang === "ko" ? kw.keyword_ko || kw.keyword : kw.keyword}</span>
                  <span className="font-mono text-primary">{kw.kscore?.toFixed(1)}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">{t(lang, "pipeline_no_trending")}</p>
          )}
          <div className="flex gap-2 mt-2">
            <ActionBtn label={t(lang, "pipeline_recalculate")} onClick={() => trendingRecalcMut.mutate()} loading={trendingRecalcMut.isPending} />
          </div>
        </StageCard>

        <Arrow label="pipeline_label_tension" lang={lang} />

        {/* Stage 7: 긴장도 */}
        <StageCard index={7} lang={lang} health={getStageHealth(stats, 7)} sectionRef={(el) => (sectionRefs.current[7] = el)}>
          <Pill label={t(lang, "pipeline_crisis_countries")} value={stats?.crisis_countries ?? 0} warn={(stats?.crisis_countries ?? 0) > 1} />
          {tensions.length > 0 && (
            <div className="mt-2 space-y-1">
              <p className="text-[10px] text-muted-foreground">{t(lang, "pipeline_top5_tension")}</p>
              {tensions
                .sort((a, b) => b.raw_score - a.raw_score)
                .slice(0, 5)
                .map((ti) => (
                  <div key={ti.country_code} className="flex items-center justify-between text-xs bg-secondary/50 px-3 py-1.5 rounded-lg">
                    <span className="font-mono">{ti.country_code}</span>
                    <span className={cn(
                      "px-1.5 py-0.5 rounded text-[10px] font-semibold",
                      ti.tension_level === 3 ? "bg-red-500/20 text-red-400" :
                      ti.tension_level === 2 ? "bg-yellow-500/20 text-yellow-400" :
                      "bg-green-500/20 text-green-400"
                    )}>
                      Lv.{ti.tension_level}
                    </span>
                    <span className="font-mono">{ti.raw_score?.toFixed(1)}</span>
                  </div>
                ))}
            </div>
          )}
          <div className="flex gap-2 mt-2">
            <ActionBtn label={t(lang, "pipeline_recalculate")} onClick={() => tensionRecalcMut.mutate()} loading={tensionRecalcMut.isPending} />
          </div>
        </StageCard>

        <Arrow label="pipeline_label_trending" lang={lang} />

        {/* Stage 8: 트렌딩 */}
        <StageCard index={8} lang={lang} health={getStageHealth(stats, 8)} sectionRef={(el) => (sectionRefs.current[8] = el)}>
          <Pill label={t(lang, "pipeline_active_keywords")} value={trending.length} />
          {trending.length > 0 && (
            <div className="mt-2 space-y-1">
              <p className="text-[10px] text-muted-foreground">{t(lang, "pipeline_top5_keywords")}</p>
              {trending.slice(0, 5).map((kw) => (
                <div key={kw.id} className="flex items-center justify-between text-xs bg-secondary/50 px-3 py-1.5 rounded-lg">
                  <span>{lang === "ko" ? kw.keyword_ko || kw.keyword : kw.keyword}</span>
                  <span className="text-muted-foreground">{kw.event_count} events</span>
                </div>
              ))}
            </div>
          )}
          <div className="flex gap-2 mt-2">
            <ActionBtn label={t(lang, "pipeline_recalculate")} onClick={() => trendingRecalcMut.mutate()} loading={trendingRecalcMut.isPending} />
          </div>
        </StageCard>

        <Arrow label="pipeline_label_notification" lang={lang} />

        {/* Stage 9: 푸시 */}
        <StageCard index={9} lang={lang} health={getStageHealth(stats, 9)} sectionRef={(el) => (sectionRefs.current[9] = el)}>
          <div className="grid grid-cols-2 gap-2">
            <Pill label={t(lang, "pipeline_push_tokens")} value={stats?.push_tokens ?? 0} />
            <Pill label="Web" value={stats?.push_web ?? 0} />
            <Pill label="Android" value={stats?.push_android ?? 0} />
            <Pill label="iOS" value={stats?.push_ios ?? 0} />
          </div>
          <div className="flex gap-2 mt-2">
            <ActionBtn label={t(lang, "pipeline_test_push")} onClick={() => testPushMut.mutate()} loading={testPushMut.isPending} />
          </div>
        </StageCard>

        <Arrow label="pipeline_label_orphan" lang={lang} />

        {/* Stage 10: 오펀 재처리 */}
        <StageCard index={10} lang={lang} health={getStageHealth(stats, 10)} sectionRef={(el) => (sectionRefs.current[10] = el)}>
          <p className="text-xs text-muted-foreground">{t(lang, "pipeline_orphan_schedule")}</p>
          <div className="flex gap-2 mt-2">
            <ActionBtn label={t(lang, "pipeline_trigger")} onClick={() => orphanMut.mutate()} loading={orphanMut.isPending} />
          </div>
        </StageCard>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { Layers, AlertTriangle, RefreshCw, Radio, Lock, Map as MapIcon, Shield, ChevronDown, Info, X } from "lucide-react";
import { cn, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useClusters, useMe, useTensionAll, useFirmsSignals, useOutageSignals, useGpsJamSignals, useSignalSummary, useMatchedSignals, useTradeFlow } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { t, type Lang } from "@/lib/i18n";
import { getFlag, getCountryName, COUNTRY_CENTERS } from "@/lib/countries";
import { PaywallModal, usePaywall } from "@/components/ui/PaywallModal";
import { ShareButton } from "@/components/issue/ShareButton";
import { LogoIcon } from "@/components/ui/logo-icon";
import AppTour from "@/components/ui/AppTour";
import TourHelpButton from "@/components/ui/TourHelpButton";
import type { Step } from "react-joyride";

// ── 데모 시그널 데이터 (Free 유저용) ─────────────────────────────────────
const DEMO_SIGNALS = {
  firms: {
    type: "FeatureCollection" as const,
    features: [
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [31.17, 48.38] }, properties: { intensity: 0.72, signal_type: "firms_hotspot" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [34.52, 49.01] }, properties: { intensity: 0.45, signal_type: "firms_hotspot" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [36.23, 50.45] }, properties: { intensity: 0.88, signal_type: "firms_hotspot" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [34.47, 31.50] }, properties: { intensity: 0.65, signal_type: "firms_hotspot" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [34.26, 31.25] }, properties: { intensity: 0.55, signal_type: "firms_hotspot" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [32.53, 15.60] }, properties: { intensity: 0.60, signal_type: "firms_hotspot" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [33.43, 12.86] }, properties: { intensity: 0.50, signal_type: "firms_hotspot" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [96.17, 16.87] }, properties: { intensity: 0.40, signal_type: "firms_hotspot" } },
    ],
  },
  outage: {
    type: "FeatureCollection" as const,
    features: [
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [30.52, 50.45] }, properties: { severity: 0.75, intensity: 0.75, signal_type: "ioda_outage" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [34.78, 31.25] }, properties: { severity: 0.60, intensity: 0.60, signal_type: "ioda_outage" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [32.53, 15.50] }, properties: { severity: 0.55, intensity: 0.55, signal_type: "ioda_outage" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [96.20, 19.76] }, properties: { severity: 0.45, intensity: 0.45, signal_type: "ioda_outage" } },
    ],
  },
  gps_jam: {
    type: "FeatureCollection" as const,
    features: [
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [35.22, 48.52] }, properties: { strength: 0.80, intensity: 0.80, signal_type: "gps_jamming" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [34.89, 31.95] }, properties: { strength: 0.65, intensity: 0.65, signal_type: "gps_jamming" } },
      { type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [44.37, 33.31] }, properties: { strength: 0.50, intensity: 0.50, signal_type: "gps_jamming" } },
    ],
  },
  trade_flow: {
    nodes: [
      { id: "KR_EXP" }, { id: "US" }, { id: "CN" }, { id: "RU" }, { id: "KR_IMP" },
    ],
    links: [
      { source: "KR_EXP", target: "US", value: 12000 },
      { source: "US", target: "KR_IMP", value: 8000 },
      { source: "KR_EXP", target: "CN", value: 18000 },
      { source: "CN", target: "KR_IMP", value: 24000 },
      { source: "KR_EXP", target: "RU", value: 1500 },
      { source: "RU", target: "KR_IMP", value: 3000 },
    ],
    home_country: "KR",
    generated_at: new Date().toISOString(),
    cached: false,
    demo_tensions: { US: 10, CN: 45, RU: 72 } as Record<string, number>,
  },
};

// ── 실시간 경과 시간 훅 ───────────────────────────────────────────────────
function useElapsed(isoString?: string, lang: Lang = "ko") {
  const [elapsed, setElapsed] = useState(0);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!isoString) return;
    const base = new Date(isoString).getTime();
    const tick = () => setElapsed(Math.floor((Date.now() - base) / 1000));
    tick();
    ref.current = setInterval(tick, 10000);
    return () => { if (ref.current) clearInterval(ref.current); };
  }, [isoString]);

  if (!isoString) return null;
  if (lang === "en") {
    if (elapsed < 60) return "just now";
    if (elapsed < 3600) return `${Math.floor(elapsed / 60)}m ago`;
    return `${Math.floor(elapsed / 3600)}h ago`;
  }
  if (elapsed < 60) return "방금 전";
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)}분 전`;
  return `${Math.floor(elapsed / 3600)}시간 전`;
}

interface Cluster {
  id: string;
  cluster_key: string;
  topic: string;
  title: string;
  title_ko: string | null;
  lat: number | null;
  lon: number | null;
  country_code: string | null;
  severity: number;
  confidence: number;
  event_count: number;
  is_verified: boolean;
  kscore: number;
  first_event_at: string;
  last_event_at: string;
  grouped_count?: number;
  grouped_total_events?: number;
}

// KScore 반올림: 표시값과 색상 판별에 동일한 값 사용 (0.98 vs 1.00 불일치 방지)
function roundKScore(kscore: number): number {
  return Math.round(kscore * 100) / 100;
}

function getKScoreColor(kscore: number): string {
  const k = roundKScore(kscore);
  if (k >= 8) return "#991b1b";  // 극심 - dark maroon
  if (k >= 6) return "#ef4444";  // 심각 - red
  if (k >= 4) return "#f97316";  // 경계 - orange
  if (k >= 2) return "#f59e0b";  // 주의 - amber
  return "#10b981";              // 안정 - emerald
}

function getKScoreLabel(kscore: number, lang: Lang): string {
  const k = roundKScore(kscore);
  if (k >= 8) return t(lang, "map_level_extreme");
  if (k >= 6) return t(lang, "map_level_severe");
  if (k >= 4) return t(lang, "map_level_alert");
  if (k >= 2) return t(lang, "map_level_caution");
  return t(lang, "map_level_stable");
}

function getTopicLabel(topic: string, lang: Lang): string {
  const key = `topic_${topic}` as Parameters<typeof t>[1];
  return t(lang, key) || topic;
}

function repScore(c: Cluster): number {
  // KScore 우선, severity 동점 처리 — 홈 트렌딩(kscore 내림차순)과 동일 기준
  return c.kscore * 1000 + c.severity;
}

function groupByPixelProximity(clusters: Cluster[], map: any, threshold: number): Cluster[] {
  if (clusters.length === 0) return [];
  if (!map || typeof map.project !== "function") return clusters;
  type Px = { x: number; y: number };
  const positions: Px[] = clusters.map((c) => {
    try { return map.project([c.lon!, c.lat!]); } catch { return { x: 0, y: 0 }; }
  });
  const assigned = new Array(clusters.length).fill(-1);
  const groups: number[][] = [];
  const order = clusters.map((c, i) => ({ i, score: repScore(c) })).sort((a, b) => b.score - a.score).map((x) => x.i);
  const thresholdSq = threshold * threshold; // 제곱 거리 비교 (Math.sqrt 제거)
  for (const i of order) {
    if (assigned[i] !== -1) continue;
    const gi = groups.length;
    groups.push([i]);
    assigned[i] = gi;
    const px = positions[i].x, py = positions[i].y;
    for (const j of order) {
      if (assigned[j] !== -1 || i === j) continue;
      const dx = px - positions[j].x;
      const dy = py - positions[j].y;
      if (dx * dx + dy * dy < thresholdSq) { groups[gi].push(j); assigned[j] = gi; }
    }
  }
  return groups.map((indices) => {
    const group = indices.map((i) => clusters[i]);
    const lead = group.reduce((a, b) => (repScore(a) > repScore(b) ? a : b));
    const totalEvents = group.reduce((s, c) => s + (c.grouped_total_events ?? c.event_count), 0);
    return { ...lead, grouped_total_events: totalEvents, severity: Math.max(...group.map((c) => c.severity)), kscore: Math.max(...group.map((c) => c.kscore)), grouped_count: group.reduce((sum, c) => sum + (c.grouped_count ?? 1), 0) };
  });
}

function groupClustersByCountry(clusters: Cluster[]): Cluster[] {
  const byCountry = new Map<string, Cluster[]>();
  const noCode: Cluster[] = [];
  for (const c of clusters) {
    if (c.lat == null || c.lon == null) continue; // 원본: 좌표 있는 것만 대상
    if (c.country_code) {
      const list = byCountry.get(c.country_code) ?? [];
      list.push(c);
      byCountry.set(c.country_code, list);
    } else {
      noCode.push(c);
    }
  }
  const result: Cluster[] = [];
  byCountry.forEach((group, cc) => {
    const lead = group.reduce((a, b) => (repScore(a) > repScore(b) ? a : b)); // 원본: repScore 기준
    const totalEvents = group.reduce((s, c) => s + c.event_count, 0);
    // COUNTRY_CENTERS 고정 좌표 우선, 없으면 lead 클러스터 좌표 fallback
    const center = COUNTRY_CENTERS[cc];
    const lat = center?.lat ?? lead.lat;
    const lon = center?.lon ?? lead.lon;
    result.push({
      ...lead,
      lat,
      lon,
      event_count: lead.event_count,
      grouped_total_events: totalEvents,
      severity: Math.max(...group.map((c) => c.severity)),
      kscore: Math.max(...group.map((c) => c.kscore)),
      grouped_count: group.length,
    });
  });
  noCode.forEach((c) => result.push({ ...c, grouped_count: 1 }));
  return result;
}

// ── 팝업 ──────────────────────────────────────────────────────────────────
function ClusterPopup({ cluster, onClose, isPreview = false }: { cluster: Cluster; onClose: () => void; isPreview?: boolean }) {
  const lang = useAppStore((s) => s.lang);
  const color = getKScoreColor(cluster.kscore);
  const kLabel = getKScoreLabel(cluster.kscore, lang);
  // 영어 모드: 원문 / 한국어 모드: 번역본 우선
  const rawTitle = lang === "en" ? cluster.title : (cluster.title_ko ?? cluster.title);
  const topicKey = `topic_${cluster.topic}` as Parameters<typeof t>[1];
  const displayTitle = isJunkTitle(rawTitle)
    ? buildSmartTitle(cluster.title, cluster.topic, lang, getCountryName, cluster.country_code)
    : (stripTitlePrefix(rawTitle) || t(lang, topicKey));

  return (
    <div className="w-full rounded-xl border bg-card p-4 shadow-2xl" style={{ borderColor: `${color}40` }}>
      <div className="h-1 w-full rounded-full mb-3" style={{ background: `linear-gradient(to right, ${color}, transparent)` }} />

      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-1.5 flex-wrap mb-1">
            {cluster.is_verified && (
              <span className="rounded-full bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-medium text-blue-400">
                {t(lang, "map_popup_verified")}
              </span>
            )}
            <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: `${color}20`, color }}>
              {kLabel}
            </span>
            <span className="rounded-full bg-secondary px-2 py-0.5 text-[10px] text-muted-foreground">
              {getTopicLabel(cluster.topic, lang)}
            </span>
            {(cluster.grouped_count ?? 1) > 1 && (
              <span className="rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary">
                {t(lang, "map_popup_grouped", { n: cluster.grouped_count ?? 1 })}
              </span>
            )}
          </div>
          <h3 className="text-sm font-bold leading-tight">{displayTitle}</h3>
          {(cluster.grouped_count ?? 1) > 1 ? (
            <p className="text-[10px] text-muted-foreground mt-1">{t(lang, "map_popup_rep_note")}</p>
          ) : (
            cluster.country_code && (
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {getFlag(cluster.country_code)} {getCountryName(cluster.country_code, lang)}
              </p>
            )
          )}
        </div>
        <button onClick={onClose} className="shrink-0 text-muted-foreground hover:text-foreground text-lg leading-none">×</button>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg p-2" style={{ background: `${color}15`, border: `1px solid ${color}30` }}>
          <p className="text-lg font-bold" style={{ color }}>{roundKScore(cluster.kscore).toFixed(1)}</p>
          <p className="flex items-center justify-center gap-0.5 text-[10px] text-muted-foreground">
            KScore
            <InfoTooltip direction="up" text={t(lang, "map_popup_kscore_tooltip")} />
          </p>
        </div>
        <div className="rounded-lg bg-secondary p-2">
          <p className="text-lg font-bold">{cluster.severity}</p>
          <p className="flex items-center justify-center gap-0.5 text-[10px] text-muted-foreground">
            {t(lang, "map_popup_severity")}
            <InfoTooltip direction="up" text={t(lang, "map_popup_severity_tooltip")} />
          </p>
        </div>
        <div className="rounded-lg bg-secondary p-2">
          <p className="text-lg font-bold">{cluster.event_count}</p>
          <p className="text-[10px] text-muted-foreground">
            {t(lang, "map_popup_events")}
            {(cluster.grouped_total_events ?? 0) > cluster.event_count && (
              <span className="text-primary/70"> /{cluster.grouped_total_events}</span>
            )}
          </p>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1">
          {t(lang, "map_popup_confidence", { n: Math.round(cluster.confidence * 100) })}
          <InfoTooltip direction="up" text={t(lang, "map_popup_confidence_tooltip")} />
        </span>
        <span>
          {new Date(cluster.last_event_at).toLocaleTimeString(lang === "en" ? "en-US" : "ko-KR", { hour: "2-digit", minute: "2-digit" })} {t(lang, "map_popup_latest")}
        </span>
      </div>

      <div className="mt-3 flex flex-col gap-2">
        {isPreview ? (
          <div
            className="w-full rounded-lg py-2.5 text-xs font-bold text-center"
            style={{ background: "var(--lock-btn-bg, rgba(255,255,255,0.05))", border: "1px solid var(--lock-btn-border, rgba(255,255,255,0.1))", color: "var(--lock-btn-text, rgba(255,255,255,0.3))", cursor: "default" }}
          >
            {lang === "ko" ? "🔒 상세보기 — Pro 플랜 전용" : "🔒 Details — Pro plan only"}
          </div>
        ) : (
          <>
            <button
              className="w-full rounded-lg py-2.5 text-xs font-bold transition-all"
              style={{ background: `${color}20`, color, border: `1px solid ${color}40` }}
              onClick={() => { window.location.href = `/issues/${cluster.id}`; }}
            >
              {t(lang, "map_popup_detail")}
            </button>
            {(cluster.grouped_count ?? 1) > 1 && cluster.country_code && (
              <button
                className="w-full rounded-lg py-2 text-xs text-muted-foreground border border-border transition-all hover:text-foreground"
                onClick={() => { window.location.href = `/issues/country/${cluster.country_code}`; }}
              >
                {t(lang, "map_popup_all_in_region", { n: cluster.grouped_count ?? 1 })}
              </button>
            )}
            <ShareButton
              url={`https://www.wewantpeace.live/issues/${cluster.id}`}
              title={cluster.title_ko ?? cluster.title}
              analyticsEvent="map_popup_share"
            />
          </>
        )}
      </div>
    </div>
  );
}

// ── 뉴스 티커 ─────────────────────────────────────────────────────────────
function NewsTicker({ clusters, isPreview = false }: { clusters: Cluster[]; isPreview?: boolean }) {
  const lang = useAppStore((s) => s.lang);
  const items = clusters.filter((c) =>
    (c.title_ko ?? c.title) &&
    c.severity > 0 &&
    !(c.topic === "unknown" && !c.country_code)
  );
  if (items.length === 0) return null;

  const content = items.map((c) => (
    <span
      key={c.id}
      className={`inline-flex items-center gap-2 px-6 transition-colors ${isPreview ? "cursor-default" : "cursor-pointer hover:text-white"}`}
      onClick={isPreview ? undefined : () => { window.location.href = `/issues/${c.id}`; }}
    >
      <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: getKScoreColor(c.kscore) }} />
      <span className="text-[11px] text-slate-300/80">
        {(() => {
          const raw = lang === "en" ? c.title : (c.title_ko ?? c.title);
          return isJunkTitle(raw)
            ? buildSmartTitle(c.title, c.topic, lang, getCountryName, c.country_code)
            : (stripTitlePrefix(raw) || t(lang, `topic_${c.topic}` as Parameters<typeof t>[1]));
        })()}
      </span>
    </span>
  ));

  return (
    <div className="absolute bottom-16 left-0 right-0 z-10 overflow-hidden border-t border-red-900/30 bg-black/70 backdrop-blur-sm h-9 flex items-center">
      <div className={isPreview ? "ticker-track-medium" : "ticker-track"}>
        {content}
        {content}
      </div>
    </div>
  );
}

// ── LayerToggleRow ──────────────────────────────────────────────────────────
function LayerToggleRow({
  icon, label, tooltip, enabled, isPro, count, onToggle, onShowTooltip, lang,
}: {
  icon: string; label: string; tooltip?: string; enabled: boolean; isPro: boolean;
  count?: number; onToggle: () => void; onShowTooltip?: (text: string) => void; lang: Lang;
}) {
  return (
    <div className="w-full flex items-center gap-2 rounded-lg px-2 py-1.5 hover:bg-muted/50 transition-colors">
      <button onClick={onToggle} className="flex items-center gap-2 flex-1 min-w-0 text-left">
        <span className="text-sm shrink-0">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="text-[11px] font-medium truncate">{label}</div>
          {count !== undefined && count > 0 && (
            <div className="text-[9px] text-muted-foreground">{t(lang, "layer_count", { count: String(count) })}</div>
          )}
        </div>
      </button>
      {tooltip && onShowTooltip && (
        <button
          onClick={(e) => { e.stopPropagation(); onShowTooltip(tooltip); }}
          className="shrink-0 p-0.5 rounded-full hover:bg-muted text-muted-foreground/60 hover:text-foreground transition-colors"
        >
          <Info className="h-3 w-3" />
        </button>
      )}
      {!isPro ? (
        <button onClick={onToggle} className="text-[9px] text-amber-500 flex items-center gap-0.5 shrink-0">
          <Lock className="h-2.5 w-2.5" /> Pro
        </button>
      ) : (
        <button onClick={onToggle} className="shrink-0">
          <div
            className={cn(
              "w-7 h-4 rounded-full transition-colors relative",
              enabled ? "bg-cyan-500" : "bg-muted-foreground/30"
            )}
          >
            <div
              className={cn(
                "absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-transform",
                enabled ? "translate-x-3.5" : "translate-x-0.5"
              )}
            />
          </div>
        </button>
      )}
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────────────────────
export default function MapPage() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const maplibreRef = useRef<any>(null);   // 모듈 캐시 (동기 사용용)
  const markersRef = useRef<any[]>([]);
  const [isMapReady, setIsMapReady] = useState(false);
  const [mapLoadError, setMapLoadError] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<Cluster | null>(null);
  // 줌 레벨 <4 여부만 추적 — ref로 관리하여 불필요한 re-render 방지
  const isCountryZoomRef = useRef(true);
  const [markerVersion, setMarkerVersion] = useState(0); // 국가줌 경계 변경 시만 증가
  const viewportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { mapViewport, setMapViewport, lang, userPlan, homeCountry } = useAppStore();
  const { data: me, isLoading: meLoading } = useMe();
  const { loading: authLoading } = useAuth();
  const plan = (me as { plan?: string })?.plan ?? userPlan ?? "free";
  // Free 플랜: 지도 열람 가능 (읽기 전용), 클러스터 상세 클릭 시 paywall
  const isFree = !meLoading && !authLoading && plan === "free";
  const isLocked = false; // 지도 자체는 항상 접근 가능
  const [showPreview, setShowPreview] = useState(false);
  const showPreviewRef = useRef(false);  // 클릭 핸들러에서 최신 값 참조
  const [showHeatmap, setShowHeatmap] = useState(false);
  const [markersVisible, setMarkersVisible] = useState(true);
  const [heatmapPulse, setHeatmapPulse] = useState(false);
  const { data: tensionAll } = useTensionAll();

  // ── Intelligence Layers ──
  const [showIntelPanel, setShowIntelPanel] = useState(false);
  const [intelTooltip, setIntelTooltip] = useState<string | null>(null);
  const [firmsEnabled, setFirmsEnabled] = useState(false);
  const [outageEnabled, setOutageEnabled] = useState(false);
  const [gpsJamEnabled, setGpsJamEnabled] = useState(false);
  const [tradeFlowEnabled, setTradeFlowEnabled] = useState(false);
  const firmsAnimRef = useRef<number | null>(null);
  const outageAnimRef = useRef<number | null>(null);
  const gpsJamAnimRef = useRef<number | null>(null);
  const tradeFlowAnimRef = useRef<number | null>(null);
  const tradeFlowPopupRef = useRef<any>(null);
  const isPro = !meLoading && !authLoading && (plan === "pro" || plan === "pro_plus");
  const [intelDemoMode, setIntelDemoMode] = useState(false);
  const { data: firmsData } = useFirmsSignals(firmsEnabled && isPro);
  const { data: outageData } = useOutageSignals(outageEnabled && isPro);
  const { data: gpsJamData } = useGpsJamSignals(gpsJamEnabled && isPro);
  const { data: tradeFlowData } = useTradeFlow(tradeFlowEnabled && isPro && !!homeCountry);
  const { data: signalSummary } = useSignalSummary();

  // ── 데모 모드: 모든 Intel 레이어 OFF 시 자동 해제 ──
  useEffect(() => {
    if (intelDemoMode && !firmsEnabled && !outageEnabled && !gpsJamEnabled && !tradeFlowEnabled) {
      setIntelDemoMode(false);
    }
  }, [intelDemoMode, firmsEnabled, outageEnabled, gpsJamEnabled, tradeFlowEnabled]);

  // ── 매칭 연결선 (아크) ──
  const { data: matchedGeo } = useMatchedSignals(selectedCluster?.id);
  const arcAnimRef = useRef<number | null>(null);

  // ── 가이드 투어 ──────────────────────────────────────────
  const [tourRun, setTourRun] = useState(false);
  const tourSteps: Step[] = useMemo(() => [
    {
      target: "[data-tour='map-page']",
      content: t(lang, "tour_map_page_role"),
      placement: "center" as const,
      disableBeacon: true,
    },
    {
      target: "[data-tour='map-heatmap']",
      content: t(lang, "tour_map_heatmap"),
    },
    {
      target: "[data-tour='map-filters']",
      content: t(lang, "tour_map_filters"),
    },
    {
      target: "[data-tour='map-markers-toggle']",
      content: t(lang, "tour_map_markers_toggle"),
    },
    {
      target: "[data-tour='map-intel-panel']",
      content: t(lang, "tour_map_intel_panel"),
    },
  ], [lang]);

  // 히트맵 버튼 펄스 애니메이션 (첫 방문 시 1회)
  useEffect(() => {
    if (typeof window === "undefined") return;
    const discovered = localStorage.getItem("heatmap_discovered");
    if (!discovered) {
      setHeatmapPulse(true);
      // 2초 후 펄스 중단 + localStorage 저장
      const timer = setTimeout(() => {
        setHeatmapPulse(false);
        localStorage.setItem("heatmap_discovered", "1");
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, []);

  // showPreview → ref 동기화
  useEffect(() => { showPreviewRef.current = showPreview; }, [showPreview]);

  // ── PaywallModal: 5초 프리뷰 후 blur + 모달 ────────────────────────────
  const mapPaywall = usePaywall("intel_locked");
  const [previewExpired, setPreviewExpired] = useState(false);
  const [countdown, setCountdown] = useState<number | null>(null);
  useEffect(() => {
    if (!isLocked || !showPreview) return;
    // 3초 전부터 카운트다운 표시 (2초 후 시작 = 남은 3초)
    const countdownTimer = setTimeout(() => {
      setCountdown(3);
    }, 2000);
    const timer = setTimeout(() => {
      setPreviewExpired(true);
      setCountdown(null);
      mapPaywall.show();
    }, 5000);
    return () => { clearTimeout(timer); clearTimeout(countdownTimer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLocked, showPreview]);

  // 카운트다운 틱 (3 -> 2 -> 1)
  useEffect(() => {
    if (countdown === null || countdown <= 0) return;
    const tick = setTimeout(() => setCountdown((c) => (c !== null && c > 1 ? c - 1 : null)), 1000);
    return () => clearTimeout(tick);
  }, [countdown]);

  const { data: apiClusters, isError, isLoading, refetch, isFetching } = useClusters({ limit: "2000" });
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastFetchedAt, setLastFetchedAt] = useState(() => new Date().toISOString());

  // 잠금 상태(Free)일 때는 mock 데이터 로드
  useEffect(() => {
    if (isLocked) {
      fetch("/mock-clusters.json").then((r) => r.json()).then(setClusters).catch(() => {});
    }
  }, [isLocked]);

  // API 데이터 → clusters 동기화
  useEffect(() => {
    if (isLocked) return;
    if (!apiClusters || !Array.isArray(apiClusters)) return;
    setClusters(apiClusters as Cluster[]);
    setLastFetchedAt(new Date().toISOString());
  }, [apiClusters, isLocked]);

  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;
    import("maplibre-gl").then((maplibregl) => {
      maplibreRef.current = maplibregl;  // 모듈 캐시
      if (!document.getElementById("maplibre-css")) {
        const link = document.createElement("link");
        link.id = "maplibre-css"; link.rel = "stylesheet";
        link.href = "https://unpkg.com/maplibre-gl@5/dist/maplibre-gl.css";
        document.head.appendChild(link);
      }
      const map = new maplibregl.Map({
        container: mapContainerRef.current!,
        style: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
        center: [mapViewport.longitude, mapViewport.latitude],
        zoom: mapViewport.zoom,
        attributionControl: false,
      });
      // 스크롤/트랙패드 줌 속도 2배 빠르게
      map.scrollZoom.setWheelZoomRate(1 / 200);
      map.scrollZoom.setZoomRate(1 / 50);
      map.addControl(new maplibregl.AttributionControl({ compact: true }), "bottom-left");
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");
      map.on("moveend", () => {
        const center = map.getCenter();
        const zoom = map.getZoom();
        // viewport persist를 debounce (300ms) — 줌/팬 중 연속 호출 방지
        if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current);
        viewportTimerRef.current = setTimeout(() => {
          setMapViewport({ longitude: center.lng, latitude: center.lat, zoom });
        }, 300);
        // 국가줌 경계(zoom=4)를 넘을 때만 마커 재그룹핑 트리거
        const newIsCountry = zoom < 4;
        if (newIsCountry !== isCountryZoomRef.current) {
          isCountryZoomRef.current = newIsCountry;
          setMarkerVersion((v) => v + 1);
        }
      });
      map.on("click", () => setSelectedCluster(null));
      map.on("load", () => { mapRef.current = map; setIsMapReady(true); });
    }).catch(() => {
      setMapLoadError(true);
    });
    return () => { if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current); mapRef.current?.remove(); mapRef.current = null; setIsMapReady(false); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── 히트맵 choropleth 레이어 ──────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    if (!showHeatmap || !tensionAll || tensionAll.length === 0) {
      // 히트맵 비활성화: 레이어/소스 제거
      try {
        if (map.getLayer("choropleth-fill")) map.removeLayer("choropleth-fill");
        if (map.getLayer("choropleth-line")) map.removeLayer("choropleth-line");
        if (map.getSource("countries")) map.removeSource("countries");
      } catch { /* noop */ }
      return;
    }

    // 국가별 color 매핑 구축
    const tensionMap = new Map<string, number>();
    for (const item of tensionAll as { country_code: string; raw_score: number }[]) {
      tensionMap.set(item.country_code, item.raw_score);
    }

    const scoreToColor = (s: number) => {
      if (s >= 80) return "rgba(153,27,27,0.5)";
      if (s >= 60) return "rgba(239,68,68,0.4)";
      if (s >= 40) return "rgba(249,115,22,0.35)";
      if (s >= 20) return "rgba(245,158,11,0.25)";
      return "rgba(16,185,129,0.15)";
    };

    const addChoropleth = async () => {
      try {
        if (!map.getSource("countries")) {
          map.addSource("countries", {
            type: "geojson",
            data: "/countries-110m.geojson",
          });
        }

        // 매치 표현식: [match, ["get", "cc"], cc1, color1, ..., default]
        const matchExpr: any[] = ["match", ["get", "cc"]];
        tensionMap.forEach((score, cc) => {
          matchExpr.push(cc, scoreToColor(score));
        });
        matchExpr.push("rgba(0,0,0,0)"); // default

        if (!map.getLayer("choropleth-fill")) {
          map.addLayer({
            id: "choropleth-fill",
            type: "fill",
            source: "countries",
            paint: {
              "fill-color": matchExpr as any,
              "fill-opacity": [
                "interpolate", ["linear"], ["zoom"],
                2, 0.6,
                5, 0.3,
                8, 0.1,
              ],
            },
          }, map.getLayer("waterway") ? "waterway" : undefined);
        }

        if (!map.getLayer("choropleth-line")) {
          map.addLayer({
            id: "choropleth-line",
            type: "line",
            source: "countries",
            paint: {
              "line-color": "rgba(255,255,255,0.08)",
              "line-width": 0.5,
            },
          }, map.getLayer("waterway") ? "waterway" : undefined);
        }
      } catch { /* noop */ }
    };

    addChoropleth();
  }, [showHeatmap, tensionAll, isMapReady]);

  // ── FIRMS Heatmap WebGL 레이어 ──────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    const cleanup = () => {
      if (firmsAnimRef.current) { cancelAnimationFrame(firmsAnimRef.current); firmsAnimRef.current = null; }
      try { if (map.getLayer("firms-heat")) map.removeLayer("firms-heat"); } catch {}
      try { if (map.getLayer("firms-circle")) map.removeLayer("firms-circle"); } catch {}
      try { if (map.getSource("firms-source")) map.removeSource("firms-source"); } catch {}
    };

    const effectiveFirmsData = intelDemoMode ? DEMO_SIGNALS.firms : firmsData;
    if (!firmsEnabled || !effectiveFirmsData || effectiveFirmsData.features.length === 0) {
      cleanup();
      return;
    }

    try {
      cleanup();
      map.addSource("firms-source", { type: "geojson", data: effectiveFirmsData });

      // 히트맵 레이어 (저줌) — intensity 평균 0.05이므로 weight 곡선 보정
      map.addLayer({
        id: "firms-heat",
        type: "heatmap",
        source: "firms-source",
        maxzoom: 10,
        paint: {
          // 낮은 intensity도 잘 보이도록 sqrt 스타일 보정
          "heatmap-weight": ["interpolate", ["linear"], ["get", "intensity"], 0, 0, 0.02, 0.3, 0.1, 0.6, 0.5, 0.85, 1, 1],
          "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 2, 10, 3],
          "heatmap-color": [
            "interpolate", ["linear"], ["heatmap-density"],
            0, "rgba(0,0,0,0)",
            0.1, "rgba(178,34,34,0.4)",
            0.3, "rgb(220,60,20)",
            0.5, "rgb(255,100,0)",
            0.7, "rgb(255,165,0)",
            0.9, "rgb(255,220,80)",
            1, "rgb(255,255,200)",
          ],
          "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 1, 15, 4, 25, 8, 35, 12, 50],
          "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 8, 0.8, 11, 0.4],
        },
      }, map.getLayer("choropleth-line") ? "choropleth-line" : undefined);

      // 서클 레이어 (고줌) — 개별 열점 표시
      map.addLayer({
        id: "firms-circle",
        type: "circle",
        source: "firms-source",
        minzoom: 7,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 3, 12, 8],
          "circle-color": ["interpolate", ["linear"], ["get", "intensity"], 0, "#ff6b35", 0.3, "#ff4500", 0.7, "#cc0000", 1, "#8b0000"],
          "circle-opacity": 0.8,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#ffd700",
          "circle-stroke-opacity": 0.6,
        },
      });

      // 펄스 애니메이션 (breathing) — 줌 레벨에 맞춰 base intensity 조정
      let phase = 0;
      const animate = () => {
        phase += 0.025;
        const z = map.getZoom?.() ?? 3;
        const base = z < 5 ? 1.5 : z < 8 ? 2.5 : 3;
        const val = base * (0.9 + 0.1 * Math.sin(phase));
        try { map.setPaintProperty("firms-heat", "heatmap-intensity", val); } catch {}
        firmsAnimRef.current = requestAnimationFrame(animate);
      };
      firmsAnimRef.current = requestAnimationFrame(animate);
    } catch {}

    return cleanup;
  }, [firmsEnabled, firmsData, isMapReady, intelDemoMode]);

  // ── Outage Bubble WebGL 레이어 ──────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    const cleanup = () => {
      if (outageAnimRef.current) { cancelAnimationFrame(outageAnimRef.current); outageAnimRef.current = null; }
      try { if (map.getLayer("outage-label")) map.removeLayer("outage-label"); } catch {}
      try { if (map.getLayer("outage-ripple")) map.removeLayer("outage-ripple"); } catch {}
      try { if (map.getLayer("outage-circle")) map.removeLayer("outage-circle"); } catch {}
      try { if (map.getSource("outage-source")) map.removeSource("outage-source"); } catch {}
    };

    const effectiveOutageData = intelDemoMode ? DEMO_SIGNALS.outage : outageData;
    if (!outageEnabled || !effectiveOutageData || effectiveOutageData.features.length === 0) {
      cleanup();
      return;
    }

    try {
      cleanup();

      // GeoJSON에 라벨 텍스트 추가
      const enriched = {
        ...effectiveOutageData,
        features: effectiveOutageData.features.map((f: any) => {
          const pct = Math.round((f.properties.intensity ?? 0) * 100);
          const cc = f.properties.country_code ?? "";
          return { ...f, properties: { ...f.properties, label: `${cc} ▼${pct}%` } };
        }),
      };

      map.addSource("outage-source", { type: "geojson", data: enriched });

      // 바깥 ripple 원 (큰 반투명)
      map.addLayer({
        id: "outage-ripple",
        type: "circle",
        source: "outage-source",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "intensity"], 0, 30, 1, 70],
          "circle-color": "#6366f1",
          "circle-opacity": 0.08,
          "circle-stroke-width": 1.5,
          "circle-stroke-color": "#818cf8",
          "circle-stroke-opacity": 0.3,
        },
      }, map.getLayer("firms-heat") ? "firms-heat" : undefined);

      // 안쪽 원 (진한 코어)
      map.addLayer({
        id: "outage-circle",
        type: "circle",
        source: "outage-source",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "intensity"], 0, 12, 1, 35],
          "circle-color": "#6366f1",
          "circle-opacity": 0.45,
          "circle-stroke-width": 2,
          "circle-stroke-color": "#a5b4fc",
          "circle-stroke-opacity": 0.8,
        },
      });

      // 국가 + 비율 라벨
      map.addLayer({
        id: "outage-label",
        type: "symbol",
        source: "outage-source",
        layout: {
          "text-field": ["get", "label"],
          "text-size": 12,
          "text-font": ["Open Sans Bold"],
          "text-anchor": "center",
          "text-allow-overlap": true,
        },
        paint: {
          "text-color": "#e0e7ff",
          "text-halo-color": "#312e81",
          "text-halo-width": 1.5,
        },
      });

      // 파동 애니메이션 (ripple)
      let phase = 0;
      const animate = () => {
        phase += 0.015;
        const rippleOpacity = 0.04 + 0.06 * Math.abs(Math.sin(phase));
        const strokeWidth = 1 + 2 * Math.abs(Math.sin(phase));
        try {
          map.setPaintProperty("outage-ripple", "circle-opacity", rippleOpacity);
          map.setPaintProperty("outage-ripple", "circle-stroke-width", strokeWidth);
        } catch {}
        outageAnimRef.current = requestAnimationFrame(animate);
      };
      outageAnimRef.current = requestAnimationFrame(animate);
    } catch {}

    return cleanup;
  }, [outageEnabled, outageData, isMapReady, intelDemoMode]);

  // ── GPS Jamming Zone WebGL 레이어 ───────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    const cleanup = () => {
      if (gpsJamAnimRef.current) { cancelAnimationFrame(gpsJamAnimRef.current); gpsJamAnimRef.current = null; }
      try { if (map.getLayer("gpsjam-fill")) map.removeLayer("gpsjam-fill"); } catch {}
      try { if (map.getLayer("gpsjam-line")) map.removeLayer("gpsjam-line"); } catch {}
      try { if (map.getSource("gpsjam-source")) map.removeSource("gpsjam-source"); } catch {}
    };

    const effectiveGpsJamData = intelDemoMode ? DEMO_SIGNALS.gps_jam : gpsJamData;
    if (!gpsJamEnabled || !effectiveGpsJamData || effectiveGpsJamData.features.length === 0) {
      cleanup();
      return;
    }

    try {
      cleanup();
      // 포인트를 원형 폴리곤으로 변환 (반경 ~100km 근사)
      const polygonFeatures = effectiveGpsJamData.features.map((f) => {
        const [lon, lat] = f.geometry.coordinates;
        const intensity = f.properties.intensity || 0.3;
        const steps = 24;
        const radius = 1.0; // ~100km in degrees
        const coords: [number, number][] = [];
        for (let i = 0; i <= steps; i++) {
          const angle = (i / steps) * 2 * Math.PI;
          coords.push([
            lon + radius * Math.cos(angle) / Math.cos((lat * Math.PI) / 180),
            lat + radius * Math.sin(angle),
          ]);
        }
        return {
          type: "Feature" as const,
          geometry: { type: "Polygon" as const, coordinates: [coords] },
          properties: { ...f.properties, intensity },
        };
      });

      const polygonGeoJSON = { type: "FeatureCollection" as const, features: polygonFeatures };
      map.addSource("gpsjam-source", { type: "geojson", data: polygonGeoJSON });

      map.addLayer({
        id: "gpsjam-fill",
        type: "fill",
        source: "gpsjam-source",
        paint: {
          "fill-color": "#06b6d4",
          "fill-opacity": ["interpolate", ["linear"], ["get", "intensity"], 0, 0.08, 1, 0.35],
        },
      }, map.getLayer("outage-circle") ? "outage-circle" : undefined);

      map.addLayer({
        id: "gpsjam-line",
        type: "line",
        source: "gpsjam-source",
        paint: {
          "line-color": "#22d3ee",
          "line-width": 1.5,
          "line-dasharray": [4, 4],
          "line-opacity": 0.7,
        },
      });

      // 파동 애니메이션 (전자파 느낌)
      let phase = 0;
      const animate = () => {
        phase += 0.015;
        const opacity = 0.15 + 0.2 * Math.abs(Math.sin(phase));
        try { map.setPaintProperty("gpsjam-fill", "fill-opacity", opacity); } catch {}
        gpsJamAnimRef.current = requestAnimationFrame(animate);
      };
      gpsJamAnimRef.current = requestAnimationFrame(animate);
    } catch {}

    return cleanup;
  }, [gpsJamEnabled, gpsJamData, isMapReady, intelDemoMode]);

  // ── Trade Flow Arc 레이어 (v2 — 파티클 애니메이션 + 끝점 마커) ─────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    // 이벤트 핸들러 참조를 저장 (cleanup에서 해제용)
    let _handleArcEnter: any = null;
    let _handleArcLeave: any = null;
    let _handleArcClick: any = null;
    let _handleEndpointClick: any = null;

    const LAYER_IDS = [
      "trade-flow-endpoint-labels",
      "trade-flow-endpoints",
      "trade-flow-particles",
      "trade-flow-hit",
      "trade-flow-arcs",
      "trade-flow-glow",
    ] as const;
    const SOURCE_IDS = [
      "trade-flow-endpoints-source",
      "trade-flow-particles-source",
      "trade-flow-source",
    ] as const;

    const cleanup = () => {
      if (tradeFlowAnimRef.current) { cancelAnimationFrame(tradeFlowAnimRef.current); tradeFlowAnimRef.current = null; }
      if (tradeFlowPopupRef.current) { try { tradeFlowPopupRef.current.remove(); } catch {} tradeFlowPopupRef.current = null; }
      try { if (_handleArcEnter) map.off("mouseenter", "trade-flow-hit", _handleArcEnter); } catch {}
      try { if (_handleArcLeave) map.off("mouseleave", "trade-flow-hit", _handleArcLeave); } catch {}
      try { if (_handleArcClick) map.off("click", "trade-flow-hit", _handleArcClick); } catch {}
      try { if (_handleEndpointClick) map.off("click", "trade-flow-endpoints", _handleEndpointClick); } catch {}
      for (const lid of LAYER_IDS) { try { if (map.getLayer(lid)) map.removeLayer(lid); } catch {} }
      for (const sid of SOURCE_IDS) { try { if (map.getSource(sid)) map.removeSource(sid); } catch {} }
    };

    // 데모 모드 데이터 또는 실제 데이터
    const isDemoTrade = intelDemoMode && tradeFlowEnabled;
    const effectiveData = isDemoTrade ? DEMO_SIGNALS.trade_flow : tradeFlowData;

    if (!tradeFlowEnabled || !effectiveData) {
      cleanup();
      return;
    }

    // ── 파트너 추출 ──
    const home = effectiveData.home_country;
    const exportSuffix = `${home}_EXP`;
    const importSuffix = `${home}_IMP`;

    const exportMap = new Map<string, number>();
    const importMap = new Map<string, number>();
    for (const link of effectiveData.links) {
      if (link.source === exportSuffix) {
        exportMap.set(link.target, (exportMap.get(link.target) || 0) + link.value);
      }
      if (link.target === importSuffix) {
        importMap.set(link.source, (importMap.get(link.source) || 0) + link.value);
      }
    }

    const partnerCodes = new Set([...exportMap.keys(), ...importMap.keys()]);
    const homeCenter = COUNTRY_CENTERS[home];
    if (!homeCenter) { cleanup(); return; }

    // tension scores — 실제 데이터 or 데모 고정값
    const tensionScores: Record<string, number> = {};
    if (isDemoTrade && (effectiveData as any).demo_tensions) {
      Object.assign(tensionScores, (effectiveData as any).demo_tensions);
    } else if (tensionAll) {
      for (const item of tensionAll as { country_code: string; raw_score: number }[]) {
        tensionScores[item.country_code] = item.raw_score;
      }
    }

    // ── Bezier 곡선 생성 (40 steps로 부드럽게) ──
    const STEPS = 40;
    const greatCircleArc = (from: [number, number], to: [number, number]): [number, number][] => {
      const pts: [number, number][] = [];
      for (let i = 0; i <= STEPS; i++) {
        const f = i / STEPS;
        const lng = from[0] + (to[0] - from[0]) * f;
        const lat = from[1] + (to[1] - from[1]) * f;
        const bulge = Math.sin(f * Math.PI) * Math.min(5, Math.abs(to[0] - from[0]) * 0.15 + 1);
        pts.push([lng, lat + bulge]);
      }
      return pts;
    };

    // ── 금액 포맷 헬퍼 ──
    const fmtUsd = (v: number): string => v >= 1000 ? `$${(v / 1000).toFixed(1)}B` : `$${Math.round(v)}M`;

    // ── 긴장도 라벨 ──
    const tensionLabel = (score: number): string =>
      score >= 80 ? (lang === "ko" ? "극심" : "Extreme")
        : score >= 60 ? (lang === "ko" ? "심각" : "Severe")
        : score >= 40 ? (lang === "ko" ? "경계" : "Alert")
        : score >= 20 ? (lang === "ko" ? "주의" : "Caution")
        : (lang === "ko" ? "안전" : "Stable");

    // ── 긴장도 색상 ──
    const getColor = (score: number): string =>
      score >= 80 ? "#dc2626" : score >= 60 ? "#ef4444" : score >= 40 ? "#f97316" : score >= 20 ? "#f59e0b" : "#10b981";

    // ── 아크 데이터 구조 ──
    interface ArcData {
      partner: string;
      exportUsd: number;
      importUsd: number;
      totalUsd: number;
      tensionScore: number;
      coords: [number, number][];
      toCoord: [number, number];
    }

    const fromCoord: [number, number] = [homeCenter.lon, homeCenter.lat];
    const arcs: ArcData[] = [];
    const arcFeatures: any[] = [];

    for (const code of partnerCodes) {
      const center = COUNTRY_CENTERS[code];
      if (!center) continue;
      const toCoord: [number, number] = [center.lon, center.lat];
      const exportUsd = exportMap.get(code) || 0;
      const importUsd = importMap.get(code) || 0;
      const totalUsd = exportUsd + importUsd;
      const tensionScore = tensionScores[code] || 0;
      const coords = greatCircleArc(fromCoord, toCoord);

      arcs.push({ partner: code, exportUsd, importUsd, totalUsd, tensionScore, coords, toCoord });
      arcFeatures.push({
        type: "Feature",
        properties: {
          partner: code,
          export_usd: exportUsd,
          import_usd: importUsd,
          total_usd: totalUsd,
          tension_score: tensionScore,
        },
        geometry: { type: "LineString", coordinates: coords },
      });
    }

    if (arcs.length === 0) { cleanup(); return; }

    // ── 끝점 GeoJSON ──
    const endpointFeatures: any[] = [];
    // Home 끝점
    endpointFeatures.push({
      type: "Feature",
      properties: { code: home, is_home: 1, tension_score: 0, total_usd: 0, export_usd: 0, import_usd: 0 },
      geometry: { type: "Point", coordinates: fromCoord },
    });
    // Partner 끝점
    for (const arc of arcs) {
      endpointFeatures.push({
        type: "Feature",
        properties: {
          code: arc.partner,
          is_home: 0,
          tension_score: arc.tensionScore,
          total_usd: arc.totalUsd,
          export_usd: arc.exportUsd,
          import_usd: arc.importUsd,
        },
        geometry: { type: "Point", coordinates: arc.toCoord },
      });
    }

    // ── 파티클 초기화 ──
    const PARTICLES_PER_ARC = 3;
    const particles: { arcIdx: number; progress: number; speed: number }[] = [];
    for (let i = 0; i < arcs.length; i++) {
      for (let j = 0; j < PARTICLES_PER_ARC; j++) {
        particles.push({
          arcIdx: i,
          progress: j / PARTICLES_PER_ARC,
          speed: 0.003 + Math.min(0.004, (arcs[i].totalUsd / 50000) * 0.002),
        });
      }
    }

    const getParticleCoord = (arcIdx: number, progress: number): [number, number] => {
      const coords = arcs[arcIdx].coords;
      const t = progress * (coords.length - 1);
      const idx = Math.min(Math.floor(t), coords.length - 2);
      const frac = t - idx;
      return [
        coords[idx][0] + (coords[idx + 1][0] - coords[idx][0]) * frac,
        coords[idx][1] + (coords[idx + 1][1] - coords[idx][1]) * frac,
      ];
    };

    const buildParticleGeoJson = () => ({
      type: "FeatureCollection" as const,
      features: particles.map((p) => {
        const coord = getParticleCoord(p.arcIdx, p.progress);
        return {
          type: "Feature" as const,
          properties: {
            tension_score: arcs[p.arcIdx].tensionScore,
            progress: p.progress,
          },
          geometry: { type: "Point" as const, coordinates: coord },
        };
      }),
    });

    const arcGeojson = { type: "FeatureCollection", features: arcFeatures };
    const endpointGeojson = { type: "FeatureCollection", features: endpointFeatures };

    try {
      cleanup();

      // ── 소스 추가 ──
      map.addSource("trade-flow-source", { type: "geojson", data: arcGeojson });
      map.addSource("trade-flow-particles-source", { type: "geojson", data: buildParticleGeoJson() });
      map.addSource("trade-flow-endpoints-source", { type: "geojson", data: endpointGeojson });

      const beforeLayer = map.getLayer("match-arcs") ? "match-arcs" : undefined;

      const tensionColorExpr: any = [
        "step", ["get", "tension_score"],
        "#10b981", 20, "#f59e0b", 40, "#f97316", 60, "#ef4444", 80, "#dc2626",
      ];

      // ── 1. Glow 레이어 (아크 아래 은은한 빛) ──
      map.addLayer({
        id: "trade-flow-glow",
        type: "line",
        source: "trade-flow-source",
        paint: {
          "line-color": tensionColorExpr,
          "line-width": [
            "interpolate", ["linear"], ["get", "total_usd"],
            100, 6, 1000, 10, 10000, 14, 50000, 18,
          ],
          "line-opacity": isDemoTrade ? 0.08 : 0.15,
          "line-blur": 6,
        },
      }, beforeLayer);

      // ── 2. 메인 아크 라인 ──
      map.addLayer({
        id: "trade-flow-arcs",
        type: "line",
        source: "trade-flow-source",
        paint: {
          "line-color": tensionColorExpr,
          "line-width": [
            "interpolate", ["linear"], ["get", "total_usd"],
            100, 1.2, 1000, 2, 10000, 3, 50000, 4,
          ],
          "line-opacity": isDemoTrade ? 0.25 : 0.7,
        },
      }, beforeLayer);

      // ── 3. Hit 레이어 (투명, 넓은 width — 터치/호버 감지용) ──
      map.addLayer({
        id: "trade-flow-hit",
        type: "line",
        source: "trade-flow-source",
        paint: {
          "line-color": "rgba(0,0,0,0)",
          "line-width": 14,
        },
      });

      // ── 4. 파티클 레이어 (흐르는 원형 점) ──
      map.addLayer({
        id: "trade-flow-particles",
        type: "circle",
        source: "trade-flow-particles-source",
        paint: {
          "circle-radius": [
            "interpolate", ["linear"], ["get", "progress"],
            0, 2, 0.5, 4, 1, 2,
          ],
          "circle-color": tensionColorExpr,
          "circle-opacity": isDemoTrade ? 0.3 : 0.85,
          "circle-blur": 0.3,
        },
      });

      // ── 5. 끝점 마커 ──
      map.addLayer({
        id: "trade-flow-endpoints",
        type: "circle",
        source: "trade-flow-endpoints-source",
        paint: {
          "circle-radius": [
            "case",
            ["==", ["get", "is_home"], 1], 7,
            ["interpolate", ["linear"], ["get", "total_usd"], 100, 4, 5000, 5, 20000, 6, 50000, 7],
          ],
          "circle-color": [
            "case",
            ["==", ["get", "is_home"], 1], "#3b82f6",
            tensionColorExpr,
          ],
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 1.5,
          "circle-opacity": isDemoTrade ? 0.4 : 0.9,
        },
      });

      // ── 6. 끝점 라벨 ──
      map.addLayer({
        id: "trade-flow-endpoint-labels",
        type: "symbol",
        source: "trade-flow-endpoints-source",
        layout: {
          "text-field": ["get", "code"],
          "text-size": 10,
          "text-offset": [0, 1.5],
          "text-anchor": "top",
          "text-allow-overlap": true,
        },
        paint: {
          "text-color": "#e5e7eb",
          "text-halo-color": "#1f2937",
          "text-halo-width": 1,
          "text-opacity": isDemoTrade ? 0.3 : 0.85,
        },
      });

      // ── 파티클 애니메이션 (requestAnimationFrame) ──
      let pulsePhase = 0;
      const animate = () => {
        // 파티클 이동
        for (const p of particles) {
          p.progress = (p.progress + p.speed) % 1;
        }
        try {
          const src = map.getSource("trade-flow-particles-source") as any;
          if (src) src.setData(buildParticleGeoJson());
        } catch {}

        // 고긴장도 아크 opacity 펄스 (비데모)
        pulsePhase += 0.03;
        if (!isDemoTrade) {
          const basePulse = 0.55 + 0.15 * Math.sin(pulsePhase);
          try {
            map.setPaintProperty("trade-flow-arcs", "line-opacity", [
              "case",
              [">=", ["get", "tension_score"], 80], basePulse,
              0.7,
            ]);
            map.setPaintProperty("trade-flow-glow", "line-opacity", [
              "case",
              [">=", ["get", "tension_score"], 80], 0.1 + 0.08 * Math.sin(pulsePhase),
              0.15,
            ]);
          } catch {}
        }

        tradeFlowAnimRef.current = requestAnimationFrame(animate);
      };
      tradeFlowAnimRef.current = requestAnimationFrame(animate);

      // ── 호버 상호작용 (아크) ──
      const handleArcEnter = (e: any) => {
        map.getCanvas().style.cursor = "pointer";
        if (!e.features || e.features.length === 0) return;
        const props = e.features[0].properties;
        const partnerCode = String(props.partner);
        const flag = getFlag(partnerCode);
        const name = getCountryName(partnerCode, lang);
        const expUsd = Number(props.export_usd);
        const impUsd = Number(props.import_usd);
        const score = Number(props.tension_score);
        const color = getColor(score);
        const scoreText = tensionLabel(score);

        const html = `<div style="font-size:12px;line-height:1.5;padding:6px 8px;background:#1f2937;color:#e5e7eb;border-radius:8px;white-space:nowrap;">
          <b style="font-size:13px;">${flag} ${name}</b>&nbsp;&nbsp;📤 ${fmtUsd(expUsd)}&nbsp;📥 ${fmtUsd(impUsd)}&nbsp;<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${color};vertical-align:middle;"></span> ${score}
        </div>`;

        if (maplibreRef.current) {
          if (tradeFlowPopupRef.current) { try { tradeFlowPopupRef.current.remove(); } catch {} }
          tradeFlowPopupRef.current = new maplibreRef.current.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: "trade-flow-popup" })
            .setLngLat(e.lngLat)
            .setHTML(html)
            .addTo(map);
          const hEl = tradeFlowPopupRef.current.getElement();
          if (hEl) {
            const hContent = hEl.querySelector(".maplibregl-popup-content") as HTMLElement;
            if (hContent) { hContent.style.cssText = "background:#1f2937!important;color:#e5e7eb!important;border:1px solid #374151!important;border-radius:8px!important;padding:0!important;box-shadow:0 4px 12px rgba(0,0,0,0.4)!important;"; }
            const hTip = hEl.querySelector(".maplibregl-popup-tip") as HTMLElement;
            if (hTip) { hTip.style.cssText = "border-top-color:#374151!important;"; }
          }
        }

        // 하이라이트: 해당 아크 opacity 높이고 나머지 낮춤 + 글로우 강화
        try {
          map.setPaintProperty("trade-flow-arcs", "line-opacity", [
            "case",
            ["==", ["get", "partner"], partnerCode], 1.0,
            isDemoTrade ? 0.12 : 0.3,
          ]);
          map.setPaintProperty("trade-flow-arcs", "line-width", [
            "case",
            ["==", ["get", "partner"], partnerCode],
            ["+", ["interpolate", ["linear"], ["get", "total_usd"], 100, 1.2, 1000, 2, 10000, 3, 50000, 4], 1.5],
            ["interpolate", ["linear"], ["get", "total_usd"], 100, 1.2, 1000, 2, 10000, 3, 50000, 4],
          ]);
          map.setPaintProperty("trade-flow-glow", "line-opacity", [
            "case",
            ["==", ["get", "partner"], partnerCode], 0.35,
            0.05,
          ]);
        } catch {}
      };

      const handleArcLeave = () => {
        map.getCanvas().style.cursor = "";
        if (tradeFlowPopupRef.current) { try { tradeFlowPopupRef.current.remove(); } catch {} tradeFlowPopupRef.current = null; }
        // 원래 스타일 복원
        try {
          map.setPaintProperty("trade-flow-arcs", "line-opacity", isDemoTrade ? 0.25 : 0.7);
          map.setPaintProperty("trade-flow-arcs", "line-width", [
            "interpolate", ["linear"], ["get", "total_usd"],
            100, 1.2, 1000, 2, 10000, 3, 50000, 4,
          ]);
          map.setPaintProperty("trade-flow-glow", "line-opacity", isDemoTrade ? 0.08 : 0.15);
        } catch {}
      };

      const handleArcClick = (e: any) => {
        // 모바일 터치용: enter와 동일한 팝업 표시
        handleArcEnter(e);
      };

      // ── 끝점 클릭 상호작용 ──
      const handleEndpointClick = (e: any) => {
        if (!e.features || e.features.length === 0) return;
        const props = e.features[0].properties;
        const isHome = Number(props.is_home);
        if (isHome === 1) return; // Home 마커 클릭 무시

        const code = String(props.code);
        const flag = getFlag(code);
        const name = getCountryName(code, lang);
        const expUsd = Number(props.export_usd);
        const impUsd = Number(props.import_usd);
        const balance = expUsd - impUsd;
        const score = Number(props.tension_score);
        const color = getColor(score);
        const scoreText = tensionLabel(score);
        const balanceColor = balance >= 0 ? "#10b981" : "#ef4444";
        const balanceSign = balance >= 0 ? "+" : "";

        const balStr = `${balanceSign}${fmtUsd(Math.abs(balance))}`;
        const html = `<div style="font-size:12px;line-height:1.6;padding:8px 10px;background:#1f2937;color:#e5e7eb;border-radius:8px;min-width:160px;">
          <div style="font-size:14px;font-weight:700;margin-bottom:4px;">${flag} ${name}</div>
          <div style="display:flex;gap:10px;white-space:nowrap;">
            <span>📤 ${fmtUsd(expUsd)}</span><span>📥 ${fmtUsd(impUsd)}</span><span style="color:${balanceColor};font-weight:600;">${balStr}</span>
          </div>
          <div style="margin-top:4px;padding-top:4px;border-top:1px solid #374151;">
            <span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${color};vertical-align:middle;margin-right:3px;"></span>${lang === "ko" ? "긴장도" : "Tension"} <b>${score}</b> (${scoreText})
          </div>
        </div>`;

        if (maplibreRef.current) {
          if (tradeFlowPopupRef.current) { try { tradeFlowPopupRef.current.remove(); } catch {} }
          const coords = e.features[0].geometry.coordinates.slice();
          tradeFlowPopupRef.current = new maplibreRef.current.Popup({ closeButton: true, closeOnClick: true, offset: 12, className: "trade-flow-popup" })
            .setLngLat(coords)
            .setHTML(html)
            .addTo(map);
          // MapLibre 기본 흰색 배경 강제 오버라이드
          const el = tradeFlowPopupRef.current.getElement();
          if (el) {
            const content = el.querySelector(".maplibregl-popup-content") as HTMLElement;
            if (content) { content.style.cssText = "background:#1f2937!important;color:#e5e7eb!important;border:1px solid #374151!important;border-radius:8px!important;padding:0!important;box-shadow:0 4px 12px rgba(0,0,0,0.4)!important;"; }
            const tip = el.querySelector(".maplibregl-popup-tip") as HTMLElement;
            if (tip) { tip.style.cssText = "border-top-color:#374151!important;"; }
            const closeBtn = el.querySelector(".maplibregl-popup-close-button") as HTMLElement;
            if (closeBtn) { closeBtn.style.cssText = "color:#9ca3af!important;font-size:16px;"; }
          }
        }
      };

      _handleArcEnter = handleArcEnter;
      _handleArcLeave = handleArcLeave;
      _handleArcClick = handleArcClick;
      _handleEndpointClick = handleEndpointClick;
      map.on("mouseenter", "trade-flow-hit", handleArcEnter);
      map.on("mouseleave", "trade-flow-hit", handleArcLeave);
      map.on("click", "trade-flow-hit", handleArcClick);
      map.on("click", "trade-flow-endpoints", handleEndpointClick);
    } catch {}

    return cleanup;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradeFlowEnabled, tradeFlowData, isMapReady, intelDemoMode, tensionAll, lang]);

  // ── 매칭 연결선 (Arc) — 클러스터 선택 시 시그널 포인트와의 아크 표시 ──
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    const cleanup = () => {
      if (arcAnimRef.current) { cancelAnimationFrame(arcAnimRef.current); arcAnimRef.current = null; }
      try { if (map.getLayer("match-arcs")) map.removeLayer("match-arcs"); } catch {}
      try { if (map.getSource("match-arcs")) map.removeSource("match-arcs"); } catch {}
    };
    cleanup();

    if (!selectedCluster || !matchedGeo || !matchedGeo.features || matchedGeo.features.length === 0) return;
    if (!selectedCluster.lat || !selectedCluster.lon) return;

    // 대원호 근사 (Bezier 곡선)
    const greatCircleArc = (from: [number, number], to: [number, number], steps = 20): [number, number][] => {
      const pts: [number, number][] = [];
      for (let i = 0; i <= steps; i++) {
        const f = i / steps;
        const lng = from[0] + (to[0] - from[0]) * f;
        const lat = from[1] + (to[1] - from[1]) * f;
        // 위도 방향으로 볼록하게 (중간점에서 최대 곡률)
        const bulge = Math.sin(f * Math.PI) * Math.min(5, Math.abs(to[0] - from[0]) * 0.15 + 1);
        pts.push([lng, lat + bulge]);
      }
      return pts;
    };

    const clusterCoord: [number, number] = [selectedCluster.lon, selectedCluster.lat];
    const lineFeatures = matchedGeo.features.map((f: any) => {
      const coords = f.geometry?.coordinates;
      if (!coords || coords.length < 2) return null;
      const signalCoord: [number, number] = [coords[0], coords[1]];
      return {
        type: "Feature" as const,
        properties: { score: f.properties?.match_score ?? 0.5 },
        geometry: { type: "LineString" as const, coordinates: greatCircleArc(signalCoord, clusterCoord) },
      };
    }).filter(Boolean);

    if (lineFeatures.length === 0) return;

    map.addSource("match-arcs", {
      type: "geojson",
      data: { type: "FeatureCollection", features: lineFeatures },
    });
    map.addLayer({
      id: "match-arcs",
      type: "line",
      source: "match-arcs",
      paint: {
        "line-color": ["interpolate", ["linear"], ["get", "score"], 0, "#6366f150", 0.5, "#818cf8", 1, "#a5b4fc"],
        "line-width": 2,
        "line-dasharray": [4, 4],
        "line-opacity": 0.7,
      },
    });

    // Dash 애니메이션
    let offset = 0;
    const animate = () => {
      offset = (offset + 0.3) % 8;
      try { map.setPaintProperty("match-arcs", "line-dasharray", [4, 4]); } catch {}
      arcAnimRef.current = requestAnimationFrame(animate);
    };
    arcAnimRef.current = requestAnimationFrame(animate);

    return cleanup;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCluster, matchedGeo, isMapReady]);

  const renderMarkers = useCallback(() => {
    const map = mapRef.current;
    if (!map || !isMapReady) return;

    // 마커 숨김 시 기존 마커만 제거
    if (!markersVisible || clusters.length === 0) {
      markersRef.current.forEach((m) => { try { m.remove(); } catch { /* noop */ } });
      markersRef.current = [];
      return;
    }

      const doRender = (maplibregl: any) => {
      const currentMap = mapRef.current;
      if (!currentMap) return;

      // 기존 마커 제거
      markersRef.current.forEach((m) => { try { m.remove(); } catch { /* noop */ } });
      markersRef.current = [];

      // 클러스터 그룹핑 — 원본 로직 복원
      const withCoords = clusters.filter((c) =>
        c.lat != null && c.lon != null &&
        c.severity > 0 &&
        !(c.topic === "unknown" && !c.country_code)
      );
      let displayClusters: Cluster[];
      try {
        const countryGrouped = isCountryZoomRef.current ? groupClustersByCountry(withCoords) : withCoords;
        displayClusters = groupByPixelProximity(countryGrouped, currentMap, 40);
      } catch {
        displayClusters = withCoords;
      }

      // 마커 생성
      displayClusters.forEach((cluster, idx) => {
        if (cluster.lat == null || cluster.lon == null) return;
        const m = mapRef.current;
        if (!m) return;
        const displayCount = (cluster.grouped_count ?? 1) > 1 ? cluster.grouped_count! : cluster.event_count;
        const sizeBase = cluster.grouped_total_events ?? cluster.event_count;
        const size = Math.max(28, Math.min(56, 22 + Math.sqrt(sizeBase) * 4));
        const color = getKScoreColor(cluster.kscore);
        const markerEl = document.createElement("div");
        // position:relative 사용 금지 — maplibre-gl이 .maplibregl-marker에
        // position:absolute를 적용하는데, inline position:relative가 이를 덮어써서
        // 마커들이 normal flow에 남아 줌 시 위치가 틀어짐
        markerEl.style.cssText = `width:${size}px;height:${size}px;overflow:visible;`;
        // 펄스 링: markerEl의 직접 자식으로 (innerEl 안에 넣으면 border-radius+will-change 조합이 클리핑)
        for (let ri = 0; ri < 2; ri++) {
          const ring = document.createElement("span");
          ring.style.cssText = `position:absolute;inset:0;border-radius:50%;border:2px solid ${color};pointer-events:none;`;
          ring.animate(
            [{ transform: "scale(1)", opacity: 0.5 }, { transform: "scale(2.2)", opacity: 0 }],
            { duration: 2000, easing: "ease-out", iterations: Infinity, delay: ri * 1000 },
          );
          markerEl.appendChild(ring);
        }
        const innerEl = document.createElement("div");
        innerEl.style.cssText = `width:100%;height:100%;border-radius:50%;background-color:${color}22;border:2.5px solid ${color};cursor:pointer;display:flex;align-items:center;justify-content:center;color:${color};font-size:11px;font-weight:bold;transition:transform 0.15s;opacity:1;position:relative;will-change:transform;`;
        // 애니메이션은 다음 프레임에 적용 (초기 opacity:0 문제 방지)
        requestAnimationFrame(() => {
          innerEl.className = "marker-enter";
        });
        innerEl.textContent = displayCount > 99 ? "99+" : String(displayCount);
        markerEl.appendChild(innerEl);
        innerEl.addEventListener("mouseenter", () => { innerEl.style.transform = "scale(1.2)"; });
        innerEl.addEventListener("mouseleave", () => { innerEl.style.transform = ""; });
        innerEl.addEventListener("click", (e) => {
          e.stopPropagation();
          setSelectedCluster(cluster);  // 미리보기에서도 팝업은 열림
        });
        try {
          const marker = new maplibregl.Marker({ element: markerEl, anchor: "center", offset: [0, 0] }).setLngLat([cluster.lon, cluster.lat]).addTo(m);
          markersRef.current.push(marker);
        } catch { /* noop */ }
      });

      // maplibre HTML 마커는 map render 이벤트 발생 시 위치가 갱신됨
      // panBy([0,0])으로 0픽셀 이동 → render 이벤트 강제 발생 → 마커 즉시 표시
      requestAnimationFrame(() => {
        try {
          currentMap.panBy([0, 0], { duration: 0, animate: false });
        } catch { /* noop */ }
      });
    };

    if (maplibreRef.current) {
      doRender(maplibreRef.current);
    } else {
      import("maplibre-gl").then((ml) => { maplibreRef.current = ml; doRender(ml); });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clusters, isMapReady, markerVersion, markersVisible]);

  useEffect(() => { renderMarkers(); }, [renderMarkers]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await refetch();
    setLastFetchedAt(new Date().toISOString());
    setIsRefreshing(false);
  }, [refetch]);

  const elapsed = useElapsed(lastFetchedAt, lang);

  const LEGEND = [
    [t(lang, "map_level_stable"), "#10b981"],
    [t(lang, "map_level_caution"), "#f59e0b"],
    [t(lang, "map_level_alert"), "#f97316"],
    [t(lang, "map_level_severe"), "#ef4444"],
    [t(lang, "map_level_extreme"), "#991b1b"],
  ] as const;

  return (
    <div className="relative h-[100dvh] w-full" data-tour="map-page">
      <AppTour tourId="map" steps={tourSteps} run={tourRun} onComplete={() => setTourRun(false)} />
      <TourHelpButton tourId="map" onStartTour={() => setTourRun(true)} />
      <div ref={mapContainerRef} className="h-full w-full" />
      {mapLoadError && (
        <div className="absolute inset-0 z-50 flex flex-col items-center justify-center bg-background/95 gap-3">
          <AlertTriangle className="h-10 w-10 text-yellow-500" />
          <p className="text-sm text-muted-foreground text-center px-6">
            {lang === "en" ? "Unable to load the map. Please check your connection and try again." : "지도를 불러올 수 없습니다. 연결 상태를 확인하고 다시 시도해주세요."}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="rounded-lg border border-border px-4 py-2 text-sm text-foreground hover:bg-secondary transition-colors"
          >
            {lang === "en" ? "Retry" : "다시 시도"}
          </button>
        </div>
      )}

      {/* ── 상단 헤더 바 ─────────────────────────────────────────── */}
      <div className="absolute left-3 right-3 z-10" style={{ top: "calc(12px + env(safe-area-inset-top, 0px))" }}>
        <div className="rounded-xl border border-border bg-background/90 px-3 py-2 backdrop-blur-sm space-y-1.5">
          {/* Row 1: 로고 + LIVE + 이슈 (왼쪽) | 새로고침 + 경과시간 (오른쪽) */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 overflow-hidden">
              <LogoIcon height={20} hideText />
              <span className="flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 border border-red-500/30 shrink-0">
                <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-500" />
                <span className="text-[10px] font-bold text-red-400">LIVE</span>
              </span>
              <span className="flex items-center gap-1 text-[11px] text-muted-foreground shrink-0">
                <Layers className="h-3 w-3" />
                {t(lang, "map_issues", { n: clusters.length })}
              </span>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                onClick={handleRefresh}
                disabled={isRefreshing || isFetching}
                className="text-muted-foreground hover:text-foreground disabled:opacity-40"
              >
                <RefreshCw className={cn("h-3.5 w-3.5", (isRefreshing || isFetching) && "animate-spin")} />
              </button>
              {elapsed && (
                <span className="text-[10px] text-muted-foreground whitespace-nowrap">{elapsed}</span>
              )}
            </div>
          </div>
          {/* Row 2: 범례 + 히트맵 */}
          <div className="flex items-center gap-1" data-tour="map-filters">
            {LEGEND.map(([label, col]) => (
              <span key={label} className="flex items-center gap-0.5 text-[9px] text-muted-foreground whitespace-nowrap">
                <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ backgroundColor: col }} />
                {label}
              </span>
            ))}
            <InfoTooltip direction="down" text={t(lang, "map_kscore_legend")} />
          </div>
          {/* Row 3: 마커 + 히트맵 + Intel 토글 (오른쪽 정렬) */}
          <div className="flex items-center justify-end gap-1.5">
            <button
              data-tour="map-markers-toggle"
              onClick={() => setMarkersVisible((v) => !v)}
              className={cn(
                "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold transition-colors border whitespace-nowrap",
                markersVisible
                  ? "bg-primary/15 text-primary border-primary/30"
                  : "text-muted-foreground border-border hover:text-foreground",
              )}
            >
              <Radio className="h-2.5 w-2.5" />
              {lang === "ko" ? "마커" : "Markers"}
            </button>
            <button
              data-tour="map-heatmap"
              onClick={() => {
                setShowHeatmap((v) => !v);
                if (heatmapPulse) {
                  setHeatmapPulse(false);
                  localStorage.setItem("heatmap_discovered", "1");
                }
              }}
              className={cn(
                "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold transition-colors border whitespace-nowrap",
                showHeatmap
                  ? "bg-primary/15 text-primary border-primary/30"
                  : "text-muted-foreground border-border hover:text-foreground",
                heatmapPulse && "animate-pulse"
              )}
            >
              <MapIcon className="h-2.5 w-2.5" />
              {lang === "ko" ? "히트맵" : "Heatmap"}
            </button>
            {/* Intel Layer Toggle */}
            <div className="relative" data-tour="map-intel-panel">
              <button
                onClick={() => { setShowIntelPanel((v) => !v); setIntelTooltip(null); }}
                className={cn(
                  "flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold transition-colors border whitespace-nowrap",
                  (firmsEnabled || outageEnabled || gpsJamEnabled || tradeFlowEnabled)
                    ? "bg-cyan-500/15 text-cyan-400 border-cyan-500/30"
                    : "text-muted-foreground border-border hover:text-foreground",
                )}
              >
                <Shield className="h-2.5 w-2.5" />
                {t(lang, "layer_panel_title")}
                <ChevronDown className={cn("h-2 w-2 transition-transform", showIntelPanel && "rotate-180")} />
              </button>
              {showIntelPanel && (
                <div className="absolute right-0 top-full mt-1 z-50 w-56 rounded-xl border border-border bg-background/95 backdrop-blur-md shadow-xl p-2 space-y-1">
                  {/* ⓘ 툴팁 (패널 최상단) */}
                  {intelTooltip && (
                    <div className="rounded-lg bg-muted/80 p-2 mb-1">
                      <div className="flex items-start gap-1.5">
                        <p className="text-[10px] text-muted-foreground leading-relaxed flex-1">{intelTooltip}</p>
                        <button onClick={() => setIntelTooltip(null)} className="shrink-0 p-0.5 rounded hover:bg-background">
                          <X className="h-2.5 w-2.5 text-muted-foreground" />
                        </button>
                      </div>
                    </div>
                  )}
                  <LayerToggleRow
                    icon="🔥" label={t(lang, "layer_firms")} tooltip={t(lang, "layer_firms_tooltip")}
                    enabled={firmsEnabled} isPro={isPro || intelDemoMode} count={signalSummary?.firms_hotspot}
                    onToggle={() => {
                      if (!isPro) { setIntelDemoMode(true); }
                      setFirmsEnabled((v) => !v);
                    }}
                    onShowTooltip={(text) => setIntelTooltip((prev) => prev === text ? null : text)}
                    lang={lang}
                  />
                  <LayerToggleRow
                    icon="🌐" label={t(lang, "layer_outage")} tooltip={t(lang, "layer_outage_tooltip")}
                    enabled={outageEnabled} isPro={isPro || intelDemoMode} count={signalSummary?.ioda_outage}
                    onToggle={() => {
                      if (!isPro) { setIntelDemoMode(true); }
                      setOutageEnabled((v) => !v);
                    }}
                    onShowTooltip={(text) => setIntelTooltip((prev) => prev === text ? null : text)}
                    lang={lang}
                  />
                  <LayerToggleRow
                    icon="📡" label={t(lang, "layer_gps_jam")} tooltip={t(lang, "layer_gps_jam_tooltip")}
                    enabled={gpsJamEnabled} isPro={isPro || intelDemoMode} count={signalSummary?.gps_jam}
                    onToggle={() => {
                      if (!isPro) { setIntelDemoMode(true); }
                      setGpsJamEnabled((v) => !v);
                    }}
                    onShowTooltip={(text) => setIntelTooltip((prev) => prev === text ? null : text)}
                    lang={lang}
                  />
                  {homeCountry ? (
                    <LayerToggleRow
                      icon="🚢" label={`${lang === "ko" ? "교역 흐름" : "Trade Flow"} ${getFlag(homeCountry)}`}
                      tooltip={lang === "ko" ? `${getCountryName(homeCountry, lang)} 기준 교역 흐름. 색상은 파트너국 긴장도 기반.` : `Trade flows from ${getCountryName(homeCountry, lang)}. Color = partner tension.`}
                      enabled={tradeFlowEnabled} isPro={isPro || intelDemoMode}
                      onToggle={() => {
                        if (!isPro) { setIntelDemoMode(true); }
                        setTradeFlowEnabled((v) => !v);
                      }}
                      onShowTooltip={(text) => setIntelTooltip((prev) => prev === text ? null : text)}
                      lang={lang}
                    />
                  ) : (
                    <a href="/settings" className="flex items-center gap-2 px-2 py-1.5 rounded text-xs text-muted-foreground opacity-60 hover:opacity-80 whitespace-nowrap">
                      <span>🚢</span>
                      <span>{lang === "ko" ? "교역 흐름 — 기준국가를 설정하세요 →" : "Trade Flow — Set a home country →"}</span>
                    </a>
                  )}
                </div>
              )}
            </div>
          </div>
          {/* 히트맵 ON 시 메트릭 안내 배너 */}
          {showHeatmap && (
            <div className="mt-1 rounded-lg bg-background/80 px-2.5 py-1 text-[10px] text-muted-foreground backdrop-blur-sm text-center">
              {lang === "ko"
                ? "히트맵: 국가별 긴장도 | 마커: 개별 이슈 KScore"
                : "Heatmap: Country tension | Markers: Issue KScore"}
            </div>
          )}
        </div>
      </div>

      {/* ── 지도 로딩 오버레이 ────────────────────────────────────── */}
      {!isMapReady && (
        <div className="absolute inset-0 z-20 flex items-center justify-center bg-background/80 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-3">
            <Radio className="h-8 w-8 text-red-400 animate-pulse" />
            <p className="text-sm font-medium text-muted-foreground">{t(lang, "map_loading")}</p>
          </div>
        </div>
      )}

      {/* ── 팝업 ─────────────────────────────────────────────────── */}
      {selectedCluster && (
        <div className="absolute inset-x-3 top-1/2 -translate-y-1/2 z-10 animate-in fade-in slide-in-from-bottom-4 duration-200">
          <ClusterPopup
            cluster={selectedCluster}
            onClose={() => setSelectedCluster(null)}
            isPreview={false}
          />
        </div>
      )}

      {isMapReady && clusters.length > 0 && !selectedCluster && (
        <NewsTicker clusters={clusters} isPreview={false} />
      )}

      {isLoading && isMapReady && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 rounded-full bg-background/90 px-4 py-2 text-[11px] text-muted-foreground border border-border backdrop-blur-sm flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
          {t(lang, "map_data_loading")}
        </div>
      )}

      {/* ── Pro/Pro+ 데이터 없음 안내 ─────────────────────────────── */}
      {!isLocked && !isLoading && isMapReady && clusters.length === 0 && (!apiClusters || !Array.isArray(apiClusters) || apiClusters.length === 0) && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 rounded-xl bg-background/95 px-6 py-5 border border-border backdrop-blur-sm text-center max-w-[280px]">
          <Layers className="h-8 w-8 text-muted-foreground/50 mx-auto mb-3" />
          <p className="text-sm font-medium mb-1">
            {lang === "ko" ? "현재 표시할 이슈가 없습니다" : "No issues to display"}
          </p>
          <p className="text-[11px] text-muted-foreground mb-3">
            {lang === "ko"
              ? "데이터가 수집되면 자동으로 표시됩니다"
              : "Issues will appear automatically when detected"}
          </p>
          <button
            onClick={handleRefresh}
            disabled={isFetching}
            className="rounded-lg border border-border px-4 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1.5 mx-auto"
          >
            <RefreshCw className={cn("h-3 w-3", isFetching && "animate-spin")} />
            {lang === "ko" ? "새로고침" : "Refresh"}
          </button>
        </div>
      )}

      {/* ── API 오류 안내 ─────────────────────────────────────────── */}
      {!isLocked && isError && isMapReady && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 rounded-xl bg-background/95 px-6 py-5 border border-red-500/30 backdrop-blur-sm text-center max-w-[280px]">
          <AlertTriangle className="h-8 w-8 text-red-400/70 mx-auto mb-3" />
          <p className="text-sm font-medium mb-1">
            {lang === "ko" ? "데이터를 불러오지 못했습니다" : "Failed to load data"}
          </p>
          <p className="text-[11px] text-muted-foreground mb-3">
            {lang === "ko"
              ? "잠시 후 다시 시도해 주세요"
              : "Please try again in a moment"}
          </p>
          <button
            onClick={handleRefresh}
            disabled={isFetching}
            className="rounded-lg bg-primary px-4 py-1.5 text-xs font-medium text-primary-foreground flex items-center gap-1.5 mx-auto"
          >
            <RefreshCw className={cn("h-3 w-3", isFetching && "animate-spin")} />
            {lang === "ko" ? "다시 시도" : "Retry"}
          </button>
        </div>
      )}

      {/* ── Pro 잠금 오버레이 ─────────────────────────────────────── */}
      {isLocked && !showPreview && (
        <div
          className="absolute inset-0 z-30 flex items-center justify-center"
          style={{ backdropFilter: "blur(14px)", backgroundColor: "rgba(0,0,0,0.68)" }}
        >
          <div
            style={{
              borderRadius: "20px",
              border: "1px solid rgba(255,255,255,0.12)",
              backgroundColor: "rgba(12,12,18,0.97)",
              padding: "32px 28px",
              textAlign: "center",
              maxWidth: "300px",
              margin: "0 16px",
              boxShadow: "0 30px 60px rgba(0,0,0,0.6)",
            }}
          >
            {/* 아이콘 */}
            <div
              style={{
                width: "56px",
                height: "56px",
                borderRadius: "16px",
                background: "linear-gradient(135deg, #2563eb 0%, #6366f1 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                margin: "0 auto 18px auto",
              }}
            >
              <Lock style={{ width: "26px", height: "26px", color: "#fff" }} />
            </div>

            <h2 style={{ fontSize: "17px", fontWeight: 700, color: "#fff", marginBottom: "10px" }}>
              {lang === "ko" ? "Pro 플랜 전용 기능" : "Pro Plan Feature"}
            </h2>

            <p
              style={{
                fontSize: "13px",
                color: "rgba(255,255,255,0.55)",
                marginBottom: "24px",
                lineHeight: "1.65",
                wordBreak: "keep-all",
              }}
            >
              {lang === "ko"
                ? "실시간 글로벌 이슈 지도는 Pro 플랜 이상에서 이용 가능해요."
                : "The real-time global issue map is available on Pro plan and above."}
            </p>

            {/* 미리보기 버튼 */}
            <button
              onClick={() => setShowPreview(true)}
              style={{
                display: "block",
                width: "100%",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.18)",
                backgroundColor: "rgba(255,255,255,0.07)",
                padding: "12px",
                fontSize: "13px",
                fontWeight: 600,
                color: "#fff",
                marginBottom: "10px",
                cursor: "pointer",
              }}
            >
              {lang === "ko" ? "👀 미리보기" : "👀 Preview"}
            </button>

            {/* 구독 버튼 */}
            <a
              href="/upgrade"
              style={{
                display: "block",
                width: "100%",
                borderRadius: "12px",
                background: "linear-gradient(to right, #2563eb, #6366f1)",
                padding: "13px",
                fontSize: "13px",
                fontWeight: 700,
                color: "#fff",
                textDecoration: "none",
              }}
            >
              {lang === "ko" ? "Pro 플랜 구독하러 가기 →" : "Upgrade to Pro →"}
            </a>
          </div>
        </div>
      )}

      {/* ── 더미 데이터 미리보기 배너 ──────────────────────────────── */}
      {isLocked && showPreview && (
        <div className="absolute z-20" style={{ top: "90px", left: "12px", right: "12px" }}>
          <div
            style={{
              borderRadius: "12px",
              border: "1px solid rgba(234,179,8,0.4)",
              backgroundColor: "rgba(20,16,0,0.88)",
              backdropFilter: "blur(8px)",
              padding: "10px 14px",
              display: "flex",
              alignItems: "center",
              gap: "10px",
            }}
          >
            <span style={{ fontSize: "14px", flexShrink: 0 }}>⚠️</span>
            <span
              style={{
                flex: 1,
                fontSize: "12px",
                color: "rgba(250,204,21,0.9)",
                fontWeight: 600,
                wordBreak: "keep-all",
                lineHeight: "1.5",
              }}
            >
              {lang === "ko" ? "더미 데이터 미리보기입니다. 실제 실시간 데이터는 프로 플랜에서 이용 가능해요." : "This is sample data only. Real-time data requires a Pro plan."}
            </span>
            <a
              href="/upgrade"
              style={{
                flexShrink: 0,
                fontSize: "11px",
                fontWeight: 700,
                color: "#fff",
                background: "linear-gradient(to right, #2563eb, #6366f1)",
                borderRadius: "8px",
                padding: "6px 10px",
                textDecoration: "none",
                whiteSpace: "nowrap",
              }}
            >
              {lang === "ko" ? "Pro 구독" : "Upgrade"}
            </a>
            <button
              onClick={() => setShowPreview(false)}
              style={{
                flexShrink: 0,
                fontSize: "18px",
                lineHeight: 1,
                color: "rgba(255,255,255,0.4)",
                cursor: "pointer",
                background: "none",
                border: "none",
                padding: "0",
              }}
            >
              ×
            </button>
          </div>
        </div>
      )}

      {/* ── 카운트다운 경고 배너 ───────────────────────────────────── */}
      {isLocked && showPreview && !previewExpired && countdown !== null && countdown > 0 && (
        <div
          className="absolute z-20 animate-in fade-in slide-in-from-top-2 duration-300"
          style={{ bottom: "80px", left: "12px", right: "12px" }}
        >
          <div
            style={{
              borderRadius: "12px",
              border: "1px solid rgba(239,68,68,0.5)",
              backgroundColor: "rgba(20,0,0,0.88)",
              backdropFilter: "blur(8px)",
              padding: "10px 14px",
              textAlign: "center",
            }}
          >
            <span
              style={{
                fontSize: "13px",
                color: "rgba(252,165,165,0.95)",
                fontWeight: 700,
              }}
            >
              {t(lang, "map_preview_countdown", { n: countdown })}
            </span>
          </div>
        </div>
      )}

      {/* ── 5초 프리뷰 만료 후 blur overlay ────────────────────────── */}
      {isLocked && showPreview && previewExpired && (
        <div
          className="absolute inset-0 z-25 flex items-center justify-center"
          style={{ backdropFilter: "blur(6px)", backgroundColor: "rgba(0,0,0,0.50)" }}
        >
          <div className="text-center px-6" style={{ maxWidth: "320px" }}>
            <Lock style={{ width: "32px", height: "32px", color: "rgba(255,255,255,0.5)", margin: "0 auto 16px" }} />
            <p style={{ fontSize: "14px", fontWeight: 700, color: "#fff", marginBottom: "8px" }}>
              {t(lang, "map_preview_expired_text")}
            </p>
            <a
              href="/upgrade"
              style={{
                display: "inline-block",
                borderRadius: "12px",
                background: "linear-gradient(to right, #2563eb, #6366f1)",
                padding: "12px 28px",
                fontSize: "13px",
                fontWeight: 700,
                color: "#fff",
                textDecoration: "none",
                marginTop: "8px",
              }}
            >
              {lang === "ko" ? "Pro 업그레이드" : "Upgrade to Pro"}
            </a>
          </div>
        </div>
      )}

      {/* ── Intel Demo Banner (Free 유저 데모 모드) ──────────────── */}
      {intelDemoMode && (
        <div className="absolute left-3 right-3 z-20" style={{ top: "calc(120px + env(safe-area-inset-top, 0px))" }}>
          <div className="rounded-xl border border-cyan-500/40 bg-cyan-950/90 backdrop-blur-sm px-4 py-2.5 flex items-center gap-3">
            <Shield className="h-4 w-4 text-cyan-400 shrink-0" />
            <p className="text-[11px] text-slate-300 flex-1">{t(lang, "demo_banner_intel")}</p>
            <a
              href="/upgrade?source=demo_intel"
              className="shrink-0 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-3 py-1 text-[10px] font-bold text-white no-underline"
            >
              {t(lang, "demo_cta_pro")}
            </a>
          </div>
        </div>
      )}

      {/* ── Signal Nudge Banner (Free 유저) ──────────────────────── */}
      {isFree && signalSummary && signalSummary.total > 0 && !intelDemoMode && (
        <SignalNudgeBanner summary={signalSummary} lang={lang} onUpgrade={() => mapPaywall.show()} />
      )}

      {/* ── PaywallModal ──────────────────────────────────────────── */}
      <PaywallModal trigger="intel_locked" isOpen={mapPaywall.isOpen} onClose={mapPaywall.close} />
    </div>
  );
}

// ── Signal Nudge Banner ─────────────────────────────────────────────────────
function SignalNudgeBanner({
  summary, lang, onUpgrade,
}: {
  summary: { firms_hotspot: number; gps_jam: number; total: number };
  lang: Lang; onUpgrade: () => void;
}) {
  const [dismissed, setDismissed] = useState(false);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setVisible(false), 8000);
    return () => clearTimeout(timer);
  }, []);

  if (dismissed || !visible || summary.total === 0) return null;

  return (
    <div
      className={cn(
        "absolute bottom-20 left-3 right-3 z-10 rounded-xl bg-indigo-950/90 backdrop-blur-sm border border-indigo-800/50 px-4 py-2.5 flex items-center gap-3 transition-opacity duration-500",
        !visible && "opacity-0 pointer-events-none",
      )}
    >
      <Shield className="h-4 w-4 text-cyan-400 shrink-0" />
      <p className="text-[11px] text-slate-300 flex-1">
        {t(lang, "signal_nudge", { firms: String(summary.firms_hotspot), gps: String(summary.gps_jam) })}
      </p>
      <button
        onClick={onUpgrade}
        className="shrink-0 rounded-full bg-gradient-to-r from-blue-600 to-indigo-600 px-3 py-1 text-[10px] font-bold text-white"
      >
        {t(lang, "signal_nudge_cta")}
      </button>
      <button onClick={() => setDismissed(true)} className="text-slate-500 hover:text-slate-300 text-xs">✕</button>
    </div>
  );
}

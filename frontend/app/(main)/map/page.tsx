"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Layers, AlertTriangle, RefreshCw, Radio, Lock } from "lucide-react";
import { cn, stripTitlePrefix, isJunkTitle, buildSmartTitle } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useClusters, useMe } from "@/lib/api";
import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { t, type Lang } from "@/lib/i18n";
import { getFlag, getCountryName, COUNTRY_CENTERS } from "@/lib/countries";
import { PaywallModal, usePaywall } from "@/components/ui/PaywallModal";

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
  is_spike: boolean;
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
    return { ...lead, grouped_total_events: totalEvents, severity: Math.max(...group.map((c) => c.severity)), kscore: Math.max(...group.map((c) => c.kscore)), is_spike: group.some((c) => c.is_spike), grouped_count: group.reduce((sum, c) => sum + (c.grouped_count ?? 1), 0) };
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
      is_spike: group.some((c) => c.is_spike),
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
    ? buildSmartTitle(cluster.title, cluster.topic, lang, getCountryName)
    : (stripTitlePrefix(rawTitle) || t(lang, topicKey));

  return (
    <div className="w-full rounded-xl border bg-card p-4 shadow-2xl" style={{ borderColor: `${color}40` }}>
      <div className="h-1 w-full rounded-full mb-3" style={{ background: `linear-gradient(to right, ${color}, transparent)` }} />

      <div className="flex items-start justify-between gap-2">
        <div className="flex-1">
          <div className="flex items-center gap-1.5 flex-wrap mb-1">
            {cluster.is_spike && (
              <span className="flex items-center gap-1 rounded-full bg-red-500/20 px-1.5 py-0.5 text-[10px] font-bold text-red-400">
                <AlertTriangle className="h-2.5 w-2.5" /> {t(lang, "map_popup_spike")}
              </span>
            )}
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
            ? buildSmartTitle(c.title, c.topic, lang, getCountryName)
            : (stripTitlePrefix(raw) || t(lang, `topic_${c.topic}` as Parameters<typeof t>[1]));
        })()}
      </span>
    </span>
  ));

  return (
    <div className="absolute bottom-16 left-0 right-0 z-10 overflow-hidden border-t border-red-900/30 bg-black/70 backdrop-blur-sm h-9 flex items-center">
      <div className="ticker-track">
        {content}
        {content}
      </div>
    </div>
  );
}

// ── 메인 ──────────────────────────────────────────────────────────────────
export default function MapPage() {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mapRef = useRef<any>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const maplibreRef = useRef<any>(null);   // 모듈 캐시 (동기 사용용)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const markersRef = useRef<any[]>([]);
  const [isMapReady, setIsMapReady] = useState(false);
  const [selectedCluster, setSelectedCluster] = useState<Cluster | null>(null);
  // 줌 레벨 <4 여부만 추적 — ref로 관리하여 불필요한 re-render 방지
  const isCountryZoomRef = useRef(true);
  const [markerVersion, setMarkerVersion] = useState(0); // 국가줌 경계 변경 시만 증가
  const viewportTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { mapViewport, setMapViewport, lang, userPlan } = useAppStore();
  const { data: me, isLoading: meLoading } = useMe();
  const plan = (me as { plan?: string })?.plan ?? userPlan ?? "free";
  const isLocked = !meLoading && plan === "free";
  const [showPreview, setShowPreview] = useState(false);
  const showPreviewRef = useRef(false);  // 클릭 핸들러에서 최신 값 참조

  // showPreview → ref 동기화
  useEffect(() => { showPreviewRef.current = showPreview; }, [showPreview]);

  // ── PaywallModal: 5초 프리뷰 후 blur + 모달 ────────────────────────────
  const mapPaywall = usePaywall("map_locked");
  const [previewExpired, setPreviewExpired] = useState(false);
  useEffect(() => {
    if (!isLocked || !showPreview) return;
    const timer = setTimeout(() => {
      setPreviewExpired(true);
      mapPaywall.show();
    }, 5000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isLocked, showPreview]);

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
    });
    return () => { if (viewportTimerRef.current) clearTimeout(viewportTimerRef.current); mapRef.current?.remove(); mapRef.current = null; setIsMapReady(false); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const renderMarkers = useCallback(() => {
    const map = mapRef.current;
    if (!map || !isMapReady || clusters.length === 0) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
          innerEl.className = "marker-enter"
            + (cluster.is_spike ? " marker-spike" : "");
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
  }, [clusters, isMapReady, markerVersion]);

  useEffect(() => { renderMarkers(); }, [renderMarkers]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await refetch();
    setLastFetchedAt(new Date().toISOString());
    setIsRefreshing(false);
  }, [refetch]);

  const elapsed = useElapsed(lastFetchedAt, lang);
  const spikeCount = clusters.filter((c) => c.is_spike).length;

  const LEGEND = [
    [t(lang, "map_level_stable"), "#10b981"],
    [t(lang, "map_level_caution"), "#f59e0b"],
    [t(lang, "map_level_alert"), "#f97316"],
    [t(lang, "map_level_severe"), "#ef4444"],
    [t(lang, "map_level_extreme"), "#991b1b"],
  ] as const;

  return (
    <div className="relative h-[100dvh] w-full">
      <div ref={mapContainerRef} className="h-full w-full" />

      {/* ── 상단 헤더 바 ─────────────────────────────────────────── */}
      <div className="absolute left-3 right-3 z-10" style={{ top: "calc(12px + env(safe-area-inset-top, 0px))" }}>
        <div className="rounded-xl border border-border bg-background/90 px-3 py-2 backdrop-blur-sm space-y-1.5">
          {/* Row 1: LIVE + 이슈/스파이크 (왼쪽) | 새로고침 + 경과시간 (오른쪽) */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 overflow-hidden">
              <span className="flex items-center gap-1 rounded-full bg-red-500/10 px-2 py-0.5 border border-red-500/30 shrink-0">
                <span className="live-dot h-1.5 w-1.5 rounded-full bg-red-500" />
                <span className="text-[10px] font-bold text-red-400">LIVE</span>
              </span>
              <span className="flex items-center gap-1 text-[11px] text-muted-foreground shrink-0">
                <Layers className="h-3 w-3" />
                {t(lang, "map_issues", { n: clusters.length })}
              </span>
              {spikeCount > 0 && (
                <span className="flex items-center gap-1 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold text-red-400 shrink-0">
                  <AlertTriangle className="h-2.5 w-2.5" />
                  {t(lang, "map_spike", { n: spikeCount })}
                </span>
              )}
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
          {/* Row 2: 범례 */}
          <div className="flex items-center gap-3">
            {LEGEND.map(([label, col]) => (
              <span key={label} className="flex items-center gap-1 text-[10px] text-muted-foreground">
                <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: col }} />
                {label}
              </span>
            ))}
            <InfoTooltip direction="down" text={t(lang, "map_kscore_legend")} />
          </div>
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
        <div className="absolute bottom-24 left-3 right-3 z-10">
          <ClusterPopup
            cluster={selectedCluster}
            onClose={() => setSelectedCluster(null)}
            isPreview={isLocked && showPreview}
          />
        </div>
      )}

      {isMapReady && clusters.length > 0 && !selectedCluster && (
        <NewsTicker clusters={clusters} isPreview={isLocked && showPreview} />
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

      {/* ── 5초 프리뷰 만료 후 blur overlay ────────────────────────── */}
      {isLocked && showPreview && previewExpired && (
        <div
          className="absolute inset-0 z-25 pointer-events-none"
          style={{ backdropFilter: "blur(6px)", backgroundColor: "rgba(0,0,0,0.35)" }}
        />
      )}

      {/* ── PaywallModal ──────────────────────────────────────────── */}
      <PaywallModal trigger="map_locked" isOpen={mapPaywall.isOpen} onClose={mapPaywall.close} />
    </div>
  );
}

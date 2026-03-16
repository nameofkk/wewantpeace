import { useQuery, useMutation, useQueryClient, keepPreviousData } from "@tanstack/react-query";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  const devUid = typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
  if (devUid) return { "X-Dev-UID": devUid };
  try {
    const { waitForAuth, getIdToken } = await import("./auth");
    await waitForAuth(); // Firebase auth 복원 완료까지 대기 (최대 5초)
    const token = await getIdToken();
    if (token) return { Authorization: `Bearer ${token}` };
  } catch {
    // fallback
  }
  return {};
}

async function apiFetch<T>(
  path: string,
  params?: Record<string, string>,
  options?: RequestInit,
  _retried?: boolean,
): Promise<T> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  }
  const authHeaders = await getAuthHeaders();
  const res = await fetch(url.toString(), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
  });
  if (!res.ok) {
    // 401이면 Firebase auth 복원 대기 후 1회 재시도
    if (res.status === 401 && !_retried) {
      await new Promise((r) => setTimeout(r, 1500));
      return apiFetch<T>(path, params, options, true);
    }
    const body = await res.json().catch(() => ({}));
    throw Object.assign(new Error(`API 오류: ${res.status}`), { status: res.status, body });
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// --- 트렌딩 훅 ---
export function useGlobalTrending() {
  return useQuery({
    queryKey: ["trending", "global"],
    queryFn: () => apiFetch("/trending/global"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 15 * 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

export interface KScoreHistoryPoint {
  time: string;
  kscore: number;
}

export function useKScoreHistory(
  clusterId: string | null | undefined,
  days: number = 7
) {
  return useQuery({
    queryKey: ["kscore-history", clusterId, days],
    queryFn: () =>
      apiFetch<KScoreHistoryPoint[]>(`/trending/kscore-history/${clusterId}`, {
        days: String(days),
      }),
    enabled: !!clusterId,
    staleTime: 15 * 60 * 1000,
  });
}

export function useMineTrending(countries?: string[] | null) {
  // null = 아직 hydration 전 → 쿼리 비활성화
  const param = countries && countries.length > 0 ? countries.join(",") : undefined;
  return useQuery({
    queryKey: ["trending", "mine", param],
    queryFn: () => apiFetch("/trending/mine", param ? { countries: param } : undefined),
    enabled: countries !== null,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 15 * 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

// --- 이슈 클러스터 훅 ---
export function useClusters(params?: Record<string, string>) {
  // queryKey에 객체 직접 포함 시 참조가 매번 바뀌어 캐시 미스 발생 → 정렬된 문자열로 직렬화
  const paramKey = params ? JSON.stringify(Object.entries(params).sort()) : "";
  return useQuery({
    queryKey: ["issues", paramKey],
    queryFn: () => apiFetch("/issues", params),
    staleTime: 2 * 60 * 1000,
    refetchInterval: 3 * 60 * 1000,
  });
}

export function useClusterDetail(id: string) {
  return useQuery({
    queryKey: ["issues", id],
    queryFn: () => apiFetch(`/issues/${id}`),
    enabled: !!id,
    staleTime: 3 * 60 * 1000,
  });
}

// --- 이슈 검색 훅 ---
export interface SearchResult {
  id: string;
  title: string;
  title_ko: string | null;
  topic: string;
  country_code: string | null;
  severity: number;
  event_count: number;
  kscore: number;
  first_event_at: string;
  last_event_at: string;
  image_url: string | null;
}

export function useSearchIssues(q: string, limit = 20) {
  return useQuery({
    queryKey: ["issues", "search", q, limit],
    queryFn: () =>
      apiFetch<SearchResult[]>("/issues/search", { q, limit: String(limit) }),
    enabled: q.length >= 2,
    staleTime: 30 * 1000,
    placeholderData: keepPreviousData,
  });
}

// --- 긴장도 훅 ---
export function useTensionMine(countries?: string[] | null) {
  const param = countries && countries.length > 0 ? countries.join(",") : undefined;
  return useQuery({
    queryKey: ["tension", "mine", param],
    queryFn: () => apiFetch("/tension/mine", param ? { countries: param } : undefined),
    enabled: countries !== null,
    staleTime: 2 * 60 * 1000,
    refetchInterval: 15 * 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

// --- 긴장도 히스토리 훅 ---
export interface TensionHistoryPoint {
  time: string;
  raw_score: number;
  tension_level: number;
  percentile_30d: number;
}

export function useTensionHistory(countryCode: string, range: "7d" | "30d" | "90d" = "7d") {
  return useQuery({
    queryKey: ["tension", "history", countryCode, range],
    queryFn: () =>
      apiFetch<TensionHistoryPoint[]>(`/tension/country/${countryCode}/history`, { range }),
    enabled: !!countryCode,
    staleTime: 5 * 60 * 1000,
  });
}

// --- 전체 국가 긴장도 (히트맵용) ---
export interface TensionAllItem {
  country_code: string;
  raw_score: number;
  tension_level: number;
  anomaly_z?: number | null;
  convergence_bonus?: number;
}

export function useTensionAll() {
  return useQuery({
    queryKey: ["tension", "all"],
    queryFn: () => apiFetch<TensionAllItem[]>("/tension/all"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 15 * 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

export function getTensionLevelColor(level: number): string {
  const colors: Record<number, string> = {
    0: "#10b981",
    1: "#f59e0b",
    2: "#f97316",
    3: "#ef4444",
    4: "#991b1b",
  };
  return colors[level] ?? "#6b7280";
}

/** @deprecated i18n.ts의 getTensionLevelLabel(level, lang) 사용 권장 */
export function getTensionLevelLabel(level: number, lang?: string): string {
  if (lang === "en") {
    const en: Record<number, string> = { 0: "Stable", 1: "Caution", 2: "Elevated", 3: "Severe", 4: "Critical" };
    return en[level] ?? "Unknown";
  }
  const ko: Record<number, string> = { 0: "안정", 1: "주의", 2: "경계", 3: "심각", 4: "극심" };
  return ko[level] ?? "알 수 없음";
}

// --- 사용자 훅 ---
interface MeData {
  id: string;
  firebase_uid: string;
  plan: string;
  role: string;
  email: string | null;
  nickname: string | null;
  display_name: string | null;
  bio: string | null;
  agreed_terms_at: string | null;
  marketing_agreed_at: string | null;
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<MeData>("/me"),
    retry: (count, error) => {
      if ((error as any)?.status === 401 && count < 2) return true;
      return false;
    },
    retryDelay: 2000,
    staleTime: 5 * 60 * 1000,
  });
}

export function usePatchProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch<MeData>("/me", undefined, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useMyAreas() {
  return useQuery({
    queryKey: ["me", "areas"],
    queryFn: () => apiFetch<UserArea[]>("/me/areas"),
    retry: false,
  });
}

export function useMyPreferences() {
  return useQuery({
    queryKey: ["me", "preferences"],
    queryFn: () => apiFetch<UserPreferences>("/me/preferences"),
    retry: false,
  });
}

export function useAddArea() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<UserArea>) =>
      apiFetch<UserArea>("/me/areas", undefined, {
        method: "POST",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me", "areas"] }),
  });
}

export function useDeleteArea() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/me/areas/${id}`, undefined, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me", "areas"] }),
  });
}

export function usePatchPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<UserPreferences>) =>
      apiFetch<UserPreferences>("/me/preferences", undefined, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me", "preferences"] }),
  });
}

export function usePatchArea() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: { area_type?: string; country_code?: string; notify_verified?: boolean; notify_fast?: boolean; label?: string } }) =>
      apiFetch<UserArea>(`/me/areas/${id}`, undefined, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onMutate: async ({ id, body }) => {
      await qc.cancelQueries({ queryKey: ["me", "areas"] });
      const prev = qc.getQueryData<UserArea[]>(["me", "areas"]);
      if (prev) {
        qc.setQueryData<UserArea[]>(["me", "areas"], prev.map((a) =>
          a.id === id ? { ...a, ...body } : a
        ));
      }
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(["me", "areas"], ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["me", "areas"] }),
  });
}

export function useRegisterPushToken() {
  return useMutation({
    mutationFn: (body: { fcm_token: string; platform: string }) =>
      apiFetch("/me/push-tokens", undefined, {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });
}

export function useDeletePushToken() {
  return useMutation({
    mutationFn: (body: { fcm_token: string }) =>
      apiFetch("/me/push-tokens", undefined, {
        method: "DELETE",
        body: JSON.stringify(body),
      }),
  });
}

// --- 알림 훅 ---
export interface NotificationItem {
  id: number;
  type: string;       // "verified" | "fast"
  cluster_id: string | null;
  title: string;
  body: string;
  is_read: boolean;
  feedback: string | null;  // "thumbs_up" | "thumbs_down" | null
  created_at: string;
}

export function useNotifications(limit = 30, offset = 0) {
  return useQuery({
    queryKey: ["me", "notifications", limit, offset],
    queryFn: () =>
      apiFetch<NotificationItem[]>("/me/notifications", {
        limit: String(limit),
        offset: String(offset),
      }),
    retry: false,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useUnreadCount(enabled = true) {
  return useQuery({
    queryKey: ["me", "notifications", "unread-count"],
    queryFn: () => apiFetch<{ unread: number }>("/me/notifications/unread-count"),
    enabled,
    retry: false,
    staleTime: 30 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/me/notifications/${id}/read`, undefined, { method: "PATCH" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me", "notifications"] });
    },
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch("/me/notifications/read-all", undefined, { method: "PATCH" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me", "notifications"] });
    },
  });
}

export function useSubmitFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, feedback }: { id: number; feedback: "thumbs_up" | "thumbs_down" }) =>
      apiFetch(`/me/notifications/${id}/feedback`, undefined, {
        method: "PATCH",
        body: JSON.stringify({ feedback }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["me", "notifications"] });
    },
  });
}

// --- 놓친 알림 훅 ---
export interface MissedAlert {
  id: string;
  cluster_id: string;
  reason: string;
  created_at: string;
}

export function useMissedAlerts() {
  return useQuery({
    queryKey: ["me", "missed-alerts"],
    queryFn: () => apiFetch<MissedAlert[]>("/me/missed-alerts"),
    retry: false,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
  });
}

// Backward compat aliases
/** @deprecated Use MissedAlert instead */
export type MissedSpike = MissedAlert;
/** @deprecated Use useMissedAlerts instead */
export const useMissedSpikes = useMissedAlerts;

// --- 어드민: 클러스터 제목 수정 훅 ---
export function usePatchCluster() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: { title_ko?: string; title?: string } }) =>
      apiFetch(`/admin/clusters/${id}`, undefined, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["trending"] });
      qc.invalidateQueries({ queryKey: ["tension"] });
    },
  });
}

// --- DodoPayments 웹 결제 ---
export async function createDodoCheckout(plan: string): Promise<{ checkout_url: string }> {
  return apiFetch("/payments/dodo/create-checkout", undefined, {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}

// --- 타입 ---
export interface UserArea {
  id: number;
  area_type: string;
  country_code: string;
  label: string;
  notify_verified: boolean;
  notify_fast: boolean;
  is_active: boolean;
}

export interface UserPreferences {
  language: string;
  min_severity: number;
  min_kscore: number;
  topics: string[];
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  timezone: string;
  home_country: string;
  notify_engagement: boolean;
}

// --- 구독 정보 ---
export interface MySubscription {
  plan: string;
  status: string;
  amount?: number;
  platform?: string;
  auto_renewing?: boolean;
  started_at?: string;
  expires_at?: string | null;
  next_billing_at?: string | null;
  cancelled_at?: string | null;
  trial_end?: string | null;
}

export function useMySubscription() {
  return useQuery({
    queryKey: ["me", "subscription"],
    queryFn: () => apiFetch<MySubscription>("/subscriptions/my"),
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

// --- Impact Dashboard hooks (Phase 2-5) ---

// 홀리스틱 종합 영향도 (모든 플랜)
export interface ImpactSummaryTopIssue {
  cluster_id: string;
  title: string;
  title_en?: string;
  impact_score: number;
  country_codes: string[];
  topic: string;
  reason?: string;
  kscore_delta?: number | null;
  event_count: number;
  severity: number;
  kscore: number;
  independent_sources: number;
  is_spike: boolean;
  confidence: number;
  first_event_at?: string | null;
  last_event_at?: string | null;
  entity_anchor?: string | null;
  body_snippet?: string | null;
  what_line?: string | null;
  so_what_line?: string | null;
  when_line?: string | null;
}

export interface CommoditySnapshot {
  symbol: string;
  name: string;
  price_usd: number;
  change_pct: number;
}

export interface MarketIndexSnapshot {
  symbol: string;
  name: string;
  value: number;
  change_pct: number;
  currency: string;
}

export interface ExchangeRateSnapshot {
  target_currency: string;
  rate: number;
  change_pct?: number;
}

export interface MarketSnapshot {
  commodities: CommoditySnapshot[];
  indices: MarketIndexSnapshot[];
  exchange_rates: ExchangeRateSnapshot[];
}

export interface TradePartner {
  country_code: string;
  trade_volume_usd: number;
  dependency_pct: number;
  export_usd?: number | null;
  import_usd?: number | null;
  trade_balance?: string | null;  // "surplus" | "deficit"
}

export interface TradeExposure {
  top_partners: TradePartner[];
  total_trade_volume: number;
}

export interface TravelAlert {
  country_code: string;
  level: number;
  title?: string;
  source: string;
}

export interface ImpactSummary {
  score: number;
  level: string;
  summary: string;
  economy?: string | null;
  trade?: string | null;
  travel?: string | null;
  top_issues: ImpactSummaryTopIssue[];
  affected_sectors_count: number;
  critical_issues_count: number;
  total_active_issues: number;
  data_sources: string[];
  generated_at: string;
  cached: boolean;
  market_snapshot?: MarketSnapshot | null;
  trade_exposure?: TradeExposure | null;
  travel_advisories?: TravelAlert[];
  risk_radar?: RiskRadarOut | null;
  impact_flow?: ImpactFlowOut | null;
}

export interface RiskRadarAxis {
  axis: string;
  value: number;
  prev_value: number;
  label_ko: string;
  label_en: string;
}

export interface RiskRadarOut {
  axes: RiskRadarAxis[];
  overall_trend: string;
}

export interface ImpactFlowNode {
  id: string;
  label: string;
  color: string;
  category: string;
}

export interface ImpactFlowLink {
  source: string;
  target: string;
  value: number;
}

export interface ImpactFlowOut {
  nodes: ImpactFlowNode[];
  links: ImpactFlowLink[];
}

export function useImpactSummary(homeCountry?: string, lang?: string, enabled = true) {
  return useQuery({
    queryKey: ["impact", "summary", homeCountry ?? "db", lang ?? "ko"],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (homeCountry !== undefined) params.home_country = homeCountry;
      if (lang) params.lang = lang;
      return apiFetch<ImpactSummary>("/impact/summary", params);
    },
    enabled,
    staleTime: 30 * 60 * 1000,
    placeholderData: keepPreviousData,
    retry: (count, error) => {
      const status = (error as any)?.status;
      // 401은 auth 복원 지연일 수 있으므로 2회까지 재시도
      if (status === 401 && count < 2) return true;
      // 일시적 서버 에러 (429 rate limit, 500, 503) 1회 재시도
      if ([429, 500, 503].includes(status) && count < 1) return true;
      return false;
    },
    retryDelay: 1500,
  });
}

/** 국가 선택기 열릴 때 호출 — 선택된 국가만 prefetch (대역폭 최적화) */
export function usePrefetchImpactSummary() {
  const qc = useQueryClient();
  return (countries: string[], lang: string) => {
    // 최대 3개국만 prefetch (현재 국가 + 인접 2개) — 25개 동시 요청 방지
    const subset = countries.slice(0, 3);
    for (const cc of subset) {
      const key = ["impact", "summary", cc || "db", lang];
      if (qc.getQueryData(key)) continue;
      qc.prefetchQuery({
        queryKey: key,
        queryFn: () => {
          const params: Record<string, string> = {};
          if (cc) params.home_country = cc;
          params.lang = lang;
          return apiFetch<ImpactSummary>("/impact/summary", params);
        },
        staleTime: 30 * 60 * 1000,
      });
    }
  };
}

// Per-cluster impact brief (legacy, Pro)
export interface ImpactBrief {
  cluster_id: string;
  title: string;
  title_ko?: string | null;
  economy: string;
  trade: string;
  travel: string;
  summary: string;
  score: number;
  data_sources: string[];
  generated_at: string;
  cached: boolean;
}

export function useImpactBrief(clusterId?: string, homeCountry?: string, lang?: string) {
  return useQuery({
    queryKey: ["impact", "brief", clusterId, homeCountry ?? "db", lang ?? "ko"],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (homeCountry) params.home_country = homeCountry;
      if (lang) params.lang = lang;
      return apiFetch<ImpactBrief>(`/impact/brief/${clusterId}`, params);
    },
    enabled: !!clusterId,
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
}

export interface SectorExposure {
  sector: string;
  exposure_pct: number;
  trade_dependency: number;
  risk_level: string;
  description: string;
}

export interface SectorAnalysis {
  home_country: string;
  affected_country: string;
  sectors: SectorExposure[];
  overall_risk: string;
  generated_at: string;
  cached: boolean;
}

export function useSectorAnalysis(clusterId?: string, homeCountry?: string, lang?: string) {
  return useQuery({
    queryKey: ["impact", "sector", clusterId, homeCountry ?? "db", lang ?? "ko"],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (homeCountry) params.home_country = homeCountry;
      if (lang) params.lang = lang;
      return apiFetch<SectorAnalysis>(`/impact/sector/${clusterId}`, params);
    },
    enabled: !!clusterId,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

export function useSectorOverview(homeCountry?: string, lang?: string, enabled = true) {
  return useQuery({
    queryKey: ["impact", "sector-overview", homeCountry ?? "db", lang ?? "ko"],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (homeCountry) params.home_country = homeCountry;
      if (lang) params.lang = lang;
      return apiFetch<SectorAnalysis>("/impact/sector-overview", params);
    },
    enabled,
    staleTime: 30 * 60 * 1000,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export interface WeeklyReportIssue {
  cluster_id: string;
  title: string;
  kscore: number;
  impact_score: number;
  country_codes: string[];
  topic: string;
}

export interface WeeklyReport {
  week_start: string;
  week_end: string;
  home_country: string;
  top_issues: WeeklyReportIssue[];
  tension_summary: { current: number; previous: number; delta: number; trend: string };
  total_events: number;
  highlight: string;
  generated_at: string;
}

export function useWeeklyReport(enabled = true) {
  return useQuery({
    queryKey: ["impact", "weekly-report"],
    queryFn: () => apiFetch<WeeklyReport>("/impact/weekly-report"),
    enabled,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

export interface Recommendations {
  recommended_countries: string[];
  recommended_topics: string[];
  based_on: string;
}

export function useRecommendations() {
  return useQuery({
    queryKey: ["impact", "recommendations"],
    queryFn: () => apiFetch<Recommendations>("/impact/recommendations"),
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
}

export function useTrackBehavior() {
  return useMutation({
    mutationFn: (data: { event_name: string; props: Record<string, any> }) =>
      apiFetch("/impact/track", undefined, {
        method: "POST",
        body: JSON.stringify(data),
      }),
  });
}

// --- Trade Flow (Sankey) ---
export interface TradeFlowNode {
  id: string;
  label: string;
}

export interface TradeFlowLink {
  source: string;
  target: string;
  value: number;
}

export interface TradeFlow {
  nodes: TradeFlowNode[];
  links: TradeFlowLink[];
  home_country: string;
  generated_at: string;
  cached: boolean;
}

export function useTradeFlow(enabled = true) {
  return useQuery({
    queryKey: ["impact", "trade-flow"],
    queryFn: () => apiFetch<TradeFlow>("/impact/trade-flow"),
    enabled,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

// --- Weekly PDF ---
export interface WeeklyPdf {
  url: string | null;
  week: string;
  available: boolean;
}

export function useWeeklyPdf(enabled = true) {
  return useQuery({
    queryKey: ["impact", "weekly-pdf"],
    queryFn: () => apiFetch<WeeklyPdf>("/impact/weekly-pdf"),
    enabled,
    staleTime: 60 * 60 * 1000,
    retry: false,
  });
}

// --- Intelligence Signals ---

export interface SignalSummary {
  firms_hotspot: number;
  ioda_outage: number;
  cf_anomaly: number;
  gps_jam: number;
  total: number;
  affected_countries: number;
  last_updated: string | null;
}

export interface SignalGeoJSON {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: {
      id: string;
      signal_type: string;
      intensity: number;
      raw_value: number | null;
      confidence: number;
      country_code: string | null;
      observed_at: string | null;
      metadata: Record<string, unknown>;
    };
  }>;
}

export function useFirmsSignals(enabled: boolean) {
  return useQuery({
    queryKey: ["signals", "firms"],
    queryFn: () => apiFetch<SignalGeoJSON>("/signals/firms"),
    enabled,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: false,
  });
}

export function useOutageSignals(enabled: boolean) {
  return useQuery({
    queryKey: ["signals", "outage"],
    queryFn: () => apiFetch<SignalGeoJSON>("/signals/outage"),
    enabled,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: false,
  });
}

export function useGpsJamSignals(enabled: boolean) {
  return useQuery({
    queryKey: ["signals", "gps-jam"],
    queryFn: () => apiFetch<SignalGeoJSON>("/signals/gps-jam"),
    enabled,
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
    retry: false,
  });
}

export function useSignalSummary() {
  return useQuery({
    queryKey: ["signals", "summary"],
    queryFn: () => apiFetch<SignalSummary>("/signals/summary"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useMatchedSignals(clusterId: string | null | undefined) {
  return useQuery({
    queryKey: ["signals", "matched", clusterId],
    queryFn: () => apiFetch<SignalGeoJSON>(`/signals/matched/${clusterId}`),
    enabled: !!clusterId,
    staleTime: 5 * 60 * 1000,
  });
}

// ── 이슈 상세 — 교차검증 시그널 + 역사적 맥락 ──

export interface ClusterSignalMatch {
  signal_type: string;
  intensity: number;
  raw_value: number | null;
  distance_km: number | null;
  time_delta_h: number | null;
  country_code: string | null;
  observed_at: string | null;
  metadata: Record<string, unknown> | null;
}

export interface HistoricalContext {
  total_events: number;
  period_start: string | null;
  period_end: string | null;
  top_actors: string[];
  recent_fatalities: number;
  yearly_trend: Record<string, unknown>[];
}

export function useClusterSignals(clusterId: string | null | undefined) {
  return useQuery({
    queryKey: ["issues", clusterId, "signals"],
    queryFn: () => apiFetch<ClusterSignalMatch[]>(`/issues/${clusterId}/signals`),
    enabled: !!clusterId,
    staleTime: 5 * 60 * 1000,
  });
}

export function useClusterContext(clusterId: string | null | undefined) {
  return useQuery({
    queryKey: ["issues", clusterId, "context"],
    queryFn: () => apiFetch<HistoricalContext>(`/issues/${clusterId}/context`),
    enabled: !!clusterId,
    staleTime: 10 * 60 * 1000,
  });
}

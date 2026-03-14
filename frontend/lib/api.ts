import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  const devUid = typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
  if (devUid) return { "X-Dev-UID": devUid };
  try {
    const { getIdToken } = await import("./auth");
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
  options?: RequestInit
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
    refetchInterval: 5 * 60 * 1000,  // Celery beat=5min과 동기화
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
    refetchInterval: 5 * 60 * 1000,  // Celery beat=5min과 동기화
  });
}

// --- 이슈 클러스터 훅 ---
export function useClusters(params?: Record<string, string>) {
  return useQuery({
    queryKey: ["issues", params],
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

// --- 긴장도 훅 ---
export function useTensionMine(countries?: string[] | null) {
  const param = countries && countries.length > 0 ? countries.join(",") : undefined;
  return useQuery({
    queryKey: ["tension", "mine", param],
    queryFn: () => apiFetch("/tension/mine", param ? { countries: param } : undefined),
    enabled: countries !== null,
    staleTime: 2 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
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
}

export function useTensionAll() {
  return useQuery({
    queryKey: ["tension", "all"],
    queryFn: () => apiFetch<TensionAllItem[]>("/tension/all"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
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

export function getTensionLevelLabel(level: number): string {
  const labels: Record<number, string> = {
    0: "안정",
    1: "주의",
    2: "경계",
    3: "심각",
    4: "극심",
  };
  return labels[level] ?? "알 수 없음";
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
}

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<MeData>("/me"),
    retry: false,
    staleTime: 5 * 60 * 1000,
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
  impact_score: number;
  country_codes: string[];
  topic: string;
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
}

export function useImpactSummary(enabled = true) {
  return useQuery({
    queryKey: ["impact", "summary"],
    queryFn: () => apiFetch<ImpactSummary>("/impact/summary"),
    enabled,
    staleTime: 30 * 60 * 1000,
    retry: false,
  });
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

export function useImpactBrief(clusterId?: string) {
  return useQuery({
    queryKey: ["impact", "brief", clusterId],
    queryFn: () => apiFetch<ImpactBrief>(`/impact/brief/${clusterId}`),
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

export function useSectorAnalysis(clusterId?: string) {
  return useQuery({
    queryKey: ["impact", "sector", clusterId],
    queryFn: () => apiFetch<SectorAnalysis>(`/impact/sector/${clusterId}`),
    enabled: !!clusterId,
    staleTime: 60 * 60 * 1000,
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

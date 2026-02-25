import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeaders(): Record<string, string> {
  const devUid = typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
  if (devUid) return { "X-Dev-UID": devUid };
  const token = typeof window !== "undefined" ? localStorage.getItem("firebase_token") : null;
  if (token) return { Authorization: `Bearer ${token}` };
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
  const res = await fetch(url.toString(), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
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
    refetchInterval: 15 * 60 * 1000,
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
  });
}

// --- 이슈 클러스터 훅 ---
export function useClusters(params?: Record<string, string>) {
  return useQuery({
    queryKey: ["issues", params],
    queryFn: () => apiFetch("/issues", params),
    staleTime: 2 * 60 * 1000,
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
    staleTime: 15 * 60 * 1000,
    refetchInterval: 15 * 60 * 1000,
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
    staleTime: 15 * 60 * 1000,
  });
}

export function getTensionLevelColor(level: number): string {
  const colors: Record<number, string> = {
    0: "#22c55e",
    1: "#eab308",
    2: "#f97316",
    3: "#ef4444",
  };
  return colors[level] ?? "#6b7280";
}

export function getTensionLevelLabel(level: number): string {
  const labels: Record<number, string> = {
    0: "안정",
    1: "주의",
    2: "경계",
    3: "위기",
  };
  return labels[level] ?? "알 수 없음";
}

// --- 사용자 훅 ---
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch("/me"),
    retry: false,
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me", "areas"] }),
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
  type: string;       // "verified" | "spike"
  cluster_id: string | null;
  title: string;
  body: string;
  is_read: boolean;
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

// --- 타입 ---
export interface UserArea {
  id: number;
  area_type: string;
  country_code: string;
  label: string;
  notify_verified: boolean;
  notify_fast: boolean;
}

export interface UserPreferences {
  language: string;
  min_severity: number;
  min_kscore: number;
  topics: string[];
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  timezone: string;
}

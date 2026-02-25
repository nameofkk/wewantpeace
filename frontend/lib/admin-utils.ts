"use client";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function adminFetch<T>(
  path: string,
  opts?: { method?: string; body?: unknown }
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("firebase_token") : null;
  const devUid =
    typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (devUid) headers["X-Dev-UID"] = devUid;
  else if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts?.method ?? "GET",
    headers,
    ...(opts?.body ? { body: JSON.stringify(opts.body) } : {}),
  });
  if (!res.ok) throw new Error(`Admin API ${res.status}`);
  return res.json();
}

export async function adminFetchWithToken<T>(
  path: string,
  token: string,
  opts?: { method?: string; body?: unknown }
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    ...(opts?.body ? { body: JSON.stringify(opts.body) } : {}),
  });
  if (!res.ok) throw new Error(`Admin API ${res.status}`);
  return res.json();
}

/**
 * Event tracking - fire-and-forget to backend.
 * Future: Amplitude/GA4 integration.
 */

import { API_BASE } from "./api";

function getAuthHeaders(): Record<string, string> {
  const devUid = typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
  if (devUid) return { "X-Dev-UID": devUid };
  const token = typeof window !== "undefined" ? localStorage.getItem("firebase_token") : null;
  if (token) return { Authorization: `Bearer ${token}` };
  return {};
}

export async function trackEvent(
  name: string,
  props?: Record<string, any>
): Promise<void> {
  try {
    const headers = getAuthHeaders();
    if (!headers.Authorization && !headers["X-Dev-UID"]) return;

    fetch(`${API_BASE}/me/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify({ name, props: props || {} }),
    }).catch(() => {}); // fire-and-forget
  } catch {
    // silent fail
  }
}

export async function trackPaywallEvent(
  trigger: string,
  action: "shown" | "dismissed" | "clicked_upgrade",
  extra?: { source?: string; plan?: string; session_id?: string }
): Promise<void> {
  try {
    const headers = getAuthHeaders();

    fetch(`${API_BASE}/me/paywall-event`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify({
        trigger,
        action,
        source: extra?.source,
        plan: extra?.plan,
        session_id: extra?.session_id,
      }),
    }).catch(() => {});
  } catch {
    // silent fail
  }
}

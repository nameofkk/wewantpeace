/**
 * Event tracking - fire-and-forget to backend.
 * Supports both authenticated and anonymous users via session_id.
 * Future: Amplitude/GA4 integration.
 */

import { API_BASE } from "./api";

function getSessionId(): string {
  if (typeof window === "undefined") return "";
  let sid = localStorage.getItem("wwp_session_id");
  if (!sid) {
    sid = crypto.randomUUID();
    localStorage.setItem("wwp_session_id", sid);
  }
  return sid;
}

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

export async function trackEvent(
  name: string,
  props?: Record<string, any>
): Promise<void> {
  try {
    const headers = await getAuthHeaders();
    const sessionId = getSessionId();

    fetch(`${API_BASE}/me/events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: JSON.stringify({
        name,
        props: props || {},
        session_id: sessionId,
        platform: "web",
      }),
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
    const headers = await getAuthHeaders();

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

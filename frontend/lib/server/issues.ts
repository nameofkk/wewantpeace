/**
 * Server-only fetch functions for issues.
 * Used by server components for SSR/ISR.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface IssueServer {
  id: string;
  cluster_key: string;
  topic: string;
  title: string;
  title_ko?: string | null;
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
  events: Array<{
    id: string;
    title: string;
    title_ko?: string | null;
    body: string;
    topic: string;
    severity: number;
    confidence: number;
    source_tier: string | null;
    source_name: string | null;
    source_url: string | null;
    event_time: string;
    country_code: string | null;
    entity_anchor: string | null;
  }>;
}

export async function fetchIssueServer(id: string): Promise<IssueServer | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${API_BASE}/issues/${id}`, {
      next: { revalidate: 120 },
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export interface TensionCountry {
  country_code: string;
  country_name: string;
  tension_level: number;
  score: number;
  event_count_24h: number;
}

export async function fetchCountryTension(code: string): Promise<TensionCountry | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${API_BASE}/tension/country/${code}`, {
      next: { revalidate: 120 },
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

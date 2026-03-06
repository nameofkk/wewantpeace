import { Metadata } from "next";
import WeeklyReportClient from "./client";

export const revalidate = 1800;

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const metadata: Metadata = {
  title: "주간 리포트 | WeWantPeace Weekly Report",
  description: "WeWantPeace 주간 TOP 이슈와 긴장도 순위를 확인하세요. Check the weekly top issues and tension rankings.",
  openGraph: {
    title: "WeWantPeace 주간 리포트",
    description: "이번 주 TOP 10 이슈와 국가별 긴장도 순위",
    type: "website",
    url: "https://www.wewantpeace.live/reports/weekly",
    siteName: "WeWantPeace",
  },
};

interface WeeklySummary {
  period: { start: string; end: string };
  top_issues: {
    id: string;
    title: string;
    title_ko: string | null;
    severity: number;
    kscore: number;
    event_count: number;
    country_code: string | null;
    topic: string;
  }[];
  top_tension: {
    country_code: string;
    raw_score: number;
    tension_level: number;
  }[];
  stats: {
    total_events: number;
    new_clusters: number;
    crisis_countries: number;
  };
  prev_stats?: {
    total_events: number;
    new_clusters: number;
  };
}

async function fetchWeeklySummary(): Promise<WeeklySummary | null> {
  try {
    const res = await fetch(`${API_BASE}/public/weekly-summary`, {
      next: { revalidate: 1800 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function WeeklyReportPage() {
  const data = await fetchWeeklySummary();
  return <WeeklyReportClient data={data} />;
}

import { MetadataRoute } from "next";

// 2026-11-09: ISR(revalidate=120)로 두었더니 빌드 때 API 를 못 불러 만든 빈 결과(정적 18개)가 계속 나갔다
// (서치 콘솔: 이슈 페이지 전부 "Google에 알려지지 않은 URL"). 요청마다 만들고, API 응답은 10분 메모리 캐시.
export const dynamic = "force-dynamic";

let _issuesCache: { at: number; data: Issue[] } | null = null;
const ISSUES_TTL_MS = 10 * 60 * 1000;

const BASE_URL = "https://www.wewantpeace.live";

interface Issue {
  id: string;
  slug?: string;
  severity: number;
  topic?: string;
  country_code?: string;
  updated_at?: string;
  last_event_at?: string;
}

async function fetchIssues(): Promise<Issue[]> {
  if (_issuesCache && Date.now() - _issuesCache.at < ISSUES_TTL_MS) return _issuesCache.data;
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/issues?limit=2000`, { cache: "no-store" });
    if (!res.ok) {
      console.error(`sitemap: /issues ${res.status}`);
      return _issuesCache?.data ?? [];
    }
    const data = await res.json();
    const list: Issue[] = Array.isArray(data) ? data : (data.items ?? data.results ?? []);
    if (list.length) _issuesCache = { at: Date.now(), data: list };
    return list;
  } catch (e) {
    console.error("sitemap: /issues 실패", e);
    return _issuesCache?.data ?? [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();
  const corePaths = [
    { path: "/", freq: "always" as const, pri: 1.0 },
    { path: "/home", freq: "always" as const, pri: 0.9 },
    { path: "/feed", freq: "always" as const, pri: 0.9 },
    { path: "/map", freq: "always" as const, pri: 0.9 },
    { path: "/tension", freq: "daily" as const, pri: 0.8 },
    { path: "/search", freq: "daily" as const, pri: 0.6 },
    { path: "/upgrade", freq: "weekly" as const, pri: 0.5 },
    { path: "/terms", freq: "monthly" as const, pri: 0.3 },
    { path: "/privacy", freq: "monthly" as const, pri: 0.3 },
  ];

  const staticPages: MetadataRoute.Sitemap = corePaths.flatMap(({ path, freq, pri }) => [
    {
      url: `${BASE_URL}${path}`,
      lastModified: now,
      changeFrequency: freq,
      priority: pri,
    },
    {
      url: `${BASE_URL}${path}${path === "/" ? "?lang=en" : "?lang=en"}`,
      lastModified: now,
      changeFrequency: freq,
      priority: pri * 0.9,
    },
  ]);

  const issues = await fetchIssues();

  // 이슈가 실제로 존재하는 국가만 country 페이지 포함
  const countriesWithIssues = new Set<string>();
  for (const issue of issues) {
    const cc = issue.country_code?.toUpperCase();
    if (cc) countriesWithIssues.add(cc);
  }

  const countryPages: MetadataRoute.Sitemap = Array.from(countriesWithIssues).map((code) => ({
    url: `${BASE_URL}/issues/country/${code.toLowerCase()}`,
    lastModified: now,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  // severity 20 이상, 분류된 이슈만 포함 (미분류 일반 기사는 "크롤링됨 - 색인 안 됨"만 늘린다)
  const issuePages: MetadataRoute.Sitemap = issues
    .filter((issue) => issue.severity >= 20 && issue.topic !== "unknown")
    .map((issue) => {
      const modRaw = issue.updated_at || issue.last_event_at;
      // 일부 매체가 시간대를 틀리게 줘 미래 시각이 들어온다 — 사이트맵 lastmod 는 지금 이후일 수 없다
      const mod = modRaw ? new Date(Math.min(new Date(modRaw).getTime(), now.getTime())) : undefined;
      const priority = issue.severity >= 70 ? 0.9 : issue.severity >= 50 ? 0.8 : 0.7;
      return {
        url: `${BASE_URL}/issues/${issue.slug ?? issue.id}`,
        lastModified: mod,
        changeFrequency: (issue.severity >= 60 ? "hourly" : "daily") as "hourly" | "daily",
        priority,
      };
    });

  return [...staticPages, ...countryPages, ...issuePages];
}

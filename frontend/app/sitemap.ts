import { MetadataRoute } from "next";

export const revalidate = 120;

const BASE_URL = "https://www.wewantpeace.live";

interface Issue {
  id: string;
  slug?: string;
  severity: number;
  country_code?: string;
  updated_at?: string;
  last_event_at?: string;
}

async function fetchIssues(): Promise<Issue[]> {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/issues?limit=2000`, {
      next: { revalidate: 120 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : (data.items ?? data.results ?? []);
  } catch {
    return [];
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

  // severity 20 이상 이슈만 포함
  const issuePages: MetadataRoute.Sitemap = issues
    .filter((issue) => issue.severity >= 20)
    .map((issue) => {
      const mod = issue.updated_at || issue.last_event_at;
      const priority = issue.severity >= 70 ? 0.9 : issue.severity >= 50 ? 0.8 : 0.7;
      return {
        url: `${BASE_URL}/issues/${issue.slug ?? issue.id}`,
        lastModified: mod ? new Date(mod) : undefined,
        changeFrequency: (issue.severity >= 60 ? "hourly" : "daily") as "hourly" | "daily",
        priority,
      };
    });

  return [...staticPages, ...countryPages, ...issuePages];
}

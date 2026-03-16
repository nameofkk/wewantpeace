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
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: `${BASE_URL}/`,
      lastModified: now,
      changeFrequency: "always",
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/home`,
      lastModified: now,
      changeFrequency: "always",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/feed`,
      lastModified: now,
      changeFrequency: "always",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/map`,
      lastModified: now,
      changeFrequency: "always",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/tension`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/search`,
      lastModified: now,
      changeFrequency: "daily",
      priority: 0.6,
    },
    {
      url: `${BASE_URL}/upgrade`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.5,
    },
    {
      url: `${BASE_URL}/terms`,
      changeFrequency: "monthly",
      priority: 0.3,
    },
    {
      url: `${BASE_URL}/privacy`,
      changeFrequency: "monthly",
      priority: 0.3,
    },
  ];

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

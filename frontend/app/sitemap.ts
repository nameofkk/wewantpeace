import { MetadataRoute } from "next";

export const revalidate = 120;

const BASE_URL = "https://www.wewantpeace.live";

const COUNTRY_CODES: string[] = [
  "AF", "AL", "DZ", "AD", "AO", "AG", "AR", "AM", "AU", "AT",
  "AZ", "BS", "BH", "BD", "BB", "BY", "BE", "BZ", "BJ", "BT",
  "BO", "BA", "BW", "BR", "BN", "BG", "BF", "BI", "CV", "KH",
  "CM", "CA", "CF", "TD", "CL", "CN", "CO", "KM", "CG", "CD",
  "CR", "HR", "CU", "CY", "CZ", "DK", "DJ", "DM", "DO", "EC",
  "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FJ", "FI", "FR",
  "GA", "GM", "GE", "DE", "GH", "GR", "GD", "GT", "GN", "GW",
  "GY", "HT", "HN", "HU", "IS", "IN", "ID", "IR", "IQ", "IE",
  "IL", "IT", "JM", "JP", "JO", "KZ", "KE", "KI", "KP", "KR",
  "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT",
  "LU", "MG", "MW", "MY", "MV", "ML", "MT", "MH", "MR", "MU",
  "MX", "FM", "MD", "MC", "MN", "ME", "MA", "MZ", "MM", "NA",
  "NR", "NP", "NL", "NZ", "NI", "NE", "NG", "MK", "NO", "OM",
  "PK", "PW", "PA", "PG", "PY", "PE", "PH", "PL", "PT", "QA",
  "RO", "RU", "RW", "KN", "LC", "VC", "WS", "SM", "ST", "SA",
  "SN", "RS", "SC", "SL", "SG", "SK", "SI", "SB", "SO", "ZA",
  "SS", "ES", "LK", "SD", "SR", "SE", "CH", "SY", "TW", "TJ",
  "TZ", "TH", "TL", "TG", "TO", "TT", "TN", "TR", "TM", "TV",
  "UG", "UA", "AE", "GB", "US", "UY", "UZ", "VU", "VE", "VN",
  "YE", "ZM", "ZW",
];

interface Issue {
  id: string;
  slug?: string;
  severity: number;
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

  const countryPages: MetadataRoute.Sitemap = COUNTRY_CODES.map((code) => ({
    url: `${BASE_URL}/issues/country/${code.toLowerCase()}`,
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  const issues = await fetchIssues();
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

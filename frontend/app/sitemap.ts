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
}

async function fetchIssues(): Promise<Issue[]> {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  try {
    const res = await fetch(`${apiUrl}/issues?limit=500`, {
      next: { revalidate: 120 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    // API may return { items: [...] } or directly an array
    return Array.isArray(data) ? data : (data.items ?? data.results ?? []);
  } catch {
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: `${BASE_URL}/`,
      changeFrequency: "always",
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/map`,
      changeFrequency: "always",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/tension`,
      changeFrequency: "daily",
      priority: 0.8,
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
    .filter((issue) => issue.severity >= 30)
    .map((issue) => ({
      url: `${BASE_URL}/issues/${issue.slug ?? issue.id}`,
      lastModified: issue.updated_at ? new Date(issue.updated_at) : undefined,
      changeFrequency: "hourly" as const,
      priority: 0.85,
    }));

  return [...staticPages, ...countryPages, ...issuePages];
}

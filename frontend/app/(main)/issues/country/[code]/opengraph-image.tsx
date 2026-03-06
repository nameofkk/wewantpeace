import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "WeWantPeace Country Tension";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const COUNTRY_NAMES: Record<string, { ko: string; en: string }> = {
  UA: { ko: "우크라이나", en: "Ukraine" },
  RU: { ko: "러시아", en: "Russia" },
  CN: { ko: "중국", en: "China" },
  US: { ko: "미국", en: "United States" },
  KR: { ko: "대한민국", en: "South Korea" },
  KP: { ko: "북한", en: "North Korea" },
  JP: { ko: "일본", en: "Japan" },
  TW: { ko: "대만", en: "Taiwan" },
  IL: { ko: "이스라엘", en: "Israel" },
  PS: { ko: "팔레스타인", en: "Palestine" },
  IR: { ko: "이란", en: "Iran" },
  SY: { ko: "시리아", en: "Syria" },
  MM: { ko: "미얀마", en: "Myanmar" },
  AF: { ko: "아프가니스탄", en: "Afghanistan" },
  SD: { ko: "수단", en: "Sudan" },
  YE: { ko: "예멘", en: "Yemen" },
  ET: { ko: "에티오피아", en: "Ethiopia" },
  SO: { ko: "소말리아", en: "Somalia" },
  LB: { ko: "레바논", en: "Lebanon" },
  IQ: { ko: "이라크", en: "Iraq" },
};

const LEVEL_LABELS: Record<number, { ko: string; en: string }> = {
  0: { ko: "안정", en: "Stable" },
  1: { ko: "주의", en: "Caution" },
  2: { ko: "경계", en: "Warning" },
  3: { ko: "심각", en: "Serious" },
  4: { ko: "극심", en: "Critical" },
};

const LEVEL_BG: Record<number, string> = {
  0: "#166534",
  1: "#92400e",
  2: "#c2410c",
  3: "#991b1b",
  4: "#7f1d1d",
};

interface TensionData {
  country_code: string;
  raw_score: number;
  tension_level: number;
  top5_clusters: { title_ko?: string; title: string }[];
}

export default async function OGImage({ params }: { params: { code: string } }) {
  const code = params.code.toUpperCase();

  let tension: TensionData | null = null;
  try {
    const res = await fetch(`${API_BASE}/tension/country/${code}`, { next: { revalidate: 300 } });
    if (res.ok) tension = await res.json();
  } catch {}

  if (!tension) {
    return new ImageResponse(
      (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: "100%", height: "100%", background: "#0f172a", color: "#fff", fontSize: 48 }}>
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  const country = COUNTRY_NAMES[code];
  const countryName = country ? `${country.ko} (${country.en})` : code;
  const level = tension.tension_level;
  const levelLabel = LEVEL_LABELS[level] || LEVEL_LABELS[0];
  const bgColor = LEVEL_BG[level] || LEVEL_BG[0];
  const topIssue = tension.top5_clusters?.[0];
  const topIssueTitle = topIssue ? (topIssue.title_ko || topIssue.title) : "";

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          width: "100%",
          height: "100%",
          background: bgColor,
          padding: "60px",
          fontFamily: "sans-serif",
        }}
      >
        {/* Top bar */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", color: "rgba(255,255,255,0.7)", fontSize: 24 }}>
            WeWantPeace
          </div>
          <div style={{ display: "flex", background: "rgba(255,255,255,0.15)", borderRadius: "8px", padding: "6px 16px", color: "#fff", fontSize: 20 }}>
            {code}
          </div>
        </div>

        {/* Country name + score */}
        <div style={{ display: "flex", flexDirection: "column", gap: "20px", flex: 1, justifyContent: "center" }}>
          <div style={{ color: "#fff", fontSize: 52, fontWeight: 700, lineHeight: 1.2 }}>
            {countryName}
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "16px" }}>
            <div style={{ color: "#fff", fontSize: 72, fontWeight: 800 }}>
              {tension.raw_score.toFixed(1)}
            </div>
            <div style={{ display: "flex", background: "rgba(255,255,255,0.2)", borderRadius: "12px", padding: "8px 20px", color: "#fff", fontSize: 28, fontWeight: 600 }}>
              {levelLabel.ko} / {levelLabel.en}
            </div>
          </div>
          {topIssueTitle && (
            <div style={{ color: "rgba(255,255,255,0.8)", fontSize: 24, lineHeight: 1.3, maxHeight: "64px", overflow: "hidden" }}>
              TOP: {topIssueTitle.length > 80 ? topIssueTitle.slice(0, 77) + "..." : topIssueTitle}
            </div>
          )}
        </div>

        {/* Bottom */}
        <div style={{ display: "flex", color: "rgba(255,255,255,0.6)", fontSize: 20 }}>
          Tension Index · wewantpeace.live
        </div>
      </div>
    ),
    { ...size }
  );
}

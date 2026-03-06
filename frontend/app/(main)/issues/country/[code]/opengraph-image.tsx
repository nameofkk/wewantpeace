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

const LEVEL_BADGE = [
  { level: 4, bg: "#DC2626", label: "Critical" },
  { level: 3, bg: "#D97706", label: "Serious" },
  { level: 2, bg: "#CA8A04", label: "Elevated" },
  { level: 1, bg: "#2563EB", label: "Moderate" },
  { level: 0, bg: "#16A34A", label: "Low" },
];

function getBadge(level: number) {
  return LEVEL_BADGE.find((b) => b.level === level) || LEVEL_BADGE[LEVEL_BADGE.length - 1];
}

function condenseTitle(raw: string, maxLen = 35): string {
  let t = raw
    .replace(
      /[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu,
      ""
    )
    .replace(/[⚡️🔴🟠🟡🟢⚠️🚨📰💥🔥❗️‼️]/g, "")
    .trim();
  t = t
    .replace(/^(중동 라이브|MIDDLE EAST LIVE|요약|Recap|속보|BREAKING|URGENT)\s*[:：\-–—]\s*/i, "")
    .replace(/^(좋은 아침입니다|Good morning).*$/i, "")
    .trim();
  const colonIdx = t.indexOf(": ");
  if (colonIdx > 0 && colonIdx < 15) t = t.slice(colonIdx + 2).trim();
  t = t
    .replace(/했다고\s+.{1,10}(밝혔|전했|보도했|발표했|알렸)습니다\.?$/, "")
    .replace(/[이가을를은는]\s*(것으로\s+)?(밝혀졌|전해졌|알려졌|보도됐|확인됐)습니다\.?$/, "")
    .replace(/고\s+(있|밝혔|전했)습니다\.?$/, "")
    .replace(/습니다\.?$/, "")
    .replace(/했다$/, "")
    .replace(/\.$/, "")
    .trim();
  if (!t) return raw.slice(0, maxLen);
  if (t.length <= maxLen) return t;
  const slice = t.slice(0, maxLen);
  const lastBreak = Math.max(
    slice.lastIndexOf(", "),
    slice.lastIndexOf(" "),
    slice.lastIndexOf("·"),
    slice.lastIndexOf(" – "),
  );
  if (lastBreak > maxLen * 0.6) return slice.slice(0, lastBreak).trim();
  return slice.trim();
}

interface TensionData {
  country_code: string;
  raw_score: number;
  tension_level: number;
  top5_clusters: { title_ko?: string; title: string }[];
}

export default async function OGImage({ params }: { params: { code: string } }) {
  const code = params.code.toUpperCase();

  let logoSrc: string | null = null;
  try {
    const logoRes = await fetch(
      new URL("../../../../../public/logo-eye.png", import.meta.url)
    );
    const logoBuf = await logoRes.arrayBuffer();
    logoSrc = `data:image/png;base64,${Buffer.from(logoBuf).toString("base64")}`;
  } catch {}

  let tension: TensionData | null = null;
  try {
    const res = await fetch(`${API_BASE}/tension/country/${code}`, {
      next: { revalidate: 300 },
    });
    if (res.ok) tension = await res.json();
  } catch {}

  if (!tension) {
    return new ImageResponse(
      (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: "100%",
            height: "100%",
            background: "#0B1120",
            color: "#94A3B8",
            fontSize: 32,
            fontFamily: "sans-serif",
          }}
        >
          {logoSrc ? (
            <img src={logoSrc} width={64} height={28} style={{ marginRight: "16px" }} />
          ) : null}
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  const country = COUNTRY_NAMES[code];
  const countryKo = country ? country.ko : code;
  const countryEn = country ? country.en : code;
  const badge = getBadge(tension.tension_level);
  const topIssue = tension.top5_clusters?.[0];
  const topIssueRaw = topIssue ? (topIssue.title_ko || topIssue.title) : "";
  const displayTopIssue = condenseTitle(topIssueRaw, 40);

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          width: "100%",
          height: "100%",
          background: "linear-gradient(180deg, #0B1120 0%, #162036 100%)",
          padding: "48px",
          fontFamily: "sans-serif",
        }}
      >
        {/* Top row: logo + level badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {logoSrc ? (
              <img
                src={logoSrc}
                width={64}
                height={28}
                style={{ width: "64px", height: "28px" }}
              />
            ) : null}
            <span
              style={{
                color: "#94A3B8",
                fontSize: 18,
                fontWeight: 500,
              }}
            >
              WeWantPeace
            </span>
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: badge.bg,
              color: badge.bg === "#CA8A04" ? "#1A1A2E" : "#FFFFFF",
              padding: "6px 16px",
              borderRadius: "20px",
              fontSize: 14,
              fontWeight: 700,
              letterSpacing: "0.5px",
            }}
          >
            {badge.label}
          </div>
        </div>

        {/* Country name + score */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            flex: 1,
            justifyContent: "center",
            gap: "8px",
          }}
        >
          <div
            style={{
              color: "#F8FAFC",
              fontSize: 56,
              fontWeight: 700,
              lineHeight: 1.1,
              letterSpacing: "-0.5px",
            }}
          >
            {countryKo}
          </div>
          <div
            style={{
              color: "#64748B",
              fontSize: 24,
              fontWeight: 400,
            }}
          >
            {countryEn}
          </div>

          {/* Score */}
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              gap: "12px",
              marginTop: "12px",
            }}
          >
            <span
              style={{
                color: "#F8FAFC",
                fontSize: 56,
                fontWeight: 800,
                letterSpacing: "-1px",
              }}
            >
              {tension.raw_score.toFixed(1)}
            </span>
            <span
              style={{
                color: "#64748B",
                fontSize: 20,
                fontWeight: 500,
              }}
            >
              Tension Index
            </span>
          </div>

          {/* Top issue */}
          {displayTopIssue ? (
            <div
              style={{
                display: "flex",
                marginTop: "8px",
                color: "#94A3B8",
                fontSize: 18,
                lineHeight: 1.4,
              }}
            >
              {displayTopIssue}
            </div>
          ) : null}
        </div>

        {/* Bottom row: country code badge + url */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              background: "#334155",
              color: "#E2E8F0",
              padding: "5px 14px",
              borderRadius: "14px",
              fontSize: 14,
              fontWeight: 500,
            }}
          >
            {code}
          </div>
          <span style={{ color: "#64748B", fontSize: 14 }}>
            wewantpeace.live
          </span>
        </div>
      </div>
    ),
    { ...size }
  );
}

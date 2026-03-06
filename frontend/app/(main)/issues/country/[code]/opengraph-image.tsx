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

const LEVEL_CONFIG = [
  { level: 4, gradStart: "#450a0a", barColor: "#ef4444", label: "극심", labelEn: "Critical" },
  { level: 3, gradStart: "#7f1d1d", barColor: "#f97316", label: "심각", labelEn: "Serious" },
  { level: 2, gradStart: "#78350f", barColor: "#f59e0b", label: "경계", labelEn: "Warning" },
  { level: 1, gradStart: "#1e3a5f", barColor: "#3b82f6", label: "주의", labelEn: "Caution" },
  { level: 0, gradStart: "#1e293b", barColor: "#10b981", label: "안정", labelEn: "Stable" },
];

function getLevelConfig(level: number) {
  return LEVEL_CONFIG.find((c) => c.level === level) || LEVEL_CONFIG[LEVEL_CONFIG.length - 1];
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
            background: "#0f172a",
            color: "#fff",
            fontSize: 48,
          }}
        >
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  const country = COUNTRY_NAMES[code];
  const countryKo = country ? country.ko : code;
  const countryEn = country ? country.en : code;
  const config = getLevelConfig(tension.tension_level);
  const topIssue = tension.top5_clusters?.[0];
  const topIssueTitle = topIssue
    ? topIssue.title_ko || topIssue.title
    : "";
  const displayTopIssue =
    topIssueTitle.length > 80
      ? topIssueTitle.slice(0, 77) + "..."
      : topIssueTitle;

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          width: "100%",
          height: "100%",
          background: `linear-gradient(135deg, ${config.gradStart} 0%, #0f172a 100%)`,
          fontFamily: "sans-serif",
        }}
      >
        {/* Left tension bar */}
        <div
          style={{
            display: "flex",
            width: "8px",
            height: "100%",
            background: config.barColor,
          }}
        />

        {/* Main content */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            flex: 1,
            padding: "40px 48px",
          }}
        >
          {/* Header: Logo + LIVE */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div
              style={{ display: "flex", alignItems: "center", gap: "12px" }}
            >
              {logoSrc ? (
                <img
                  src={logoSrc}
                  width={73}
                  height={32}
                  style={{ width: "73px", height: "32px" }}
                />
              ) : null}
              <span
                style={{
                  color: "rgba(255,255,255,0.8)",
                  fontSize: 22,
                  fontWeight: 600,
                }}
              >
                WeWantPeace
              </span>
            </div>
            <div
              style={{ display: "flex", alignItems: "center", gap: "8px" }}
            >
              <div
                style={{
                  display: "flex",
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  background: "#ef4444",
                }}
              />
              <span
                style={{
                  color: "#ef4444",
                  fontSize: 18,
                  fontWeight: 700,
                  letterSpacing: "1px",
                }}
              >
                LIVE
              </span>
            </div>
          </div>

          {/* Divider */}
          <div
            style={{
              display: "flex",
              width: "100%",
              height: "1px",
              background: "rgba(255,255,255,0.1)",
              marginTop: "16px",
            }}
          />

          {/* Country code badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              marginTop: "24px",
            }}
          >
            <div
              style={{
                display: "flex",
                background: "rgba(255,255,255,0.12)",
                borderRadius: "8px",
                padding: "4px 12px",
              }}
            >
              <span
                style={{
                  color: "#fff",
                  fontSize: 20,
                  fontWeight: 700,
                }}
              >
                {code}
              </span>
            </div>
            <span
              style={{ color: "rgba(255,255,255,0.5)", fontSize: 20 }}
            >
              Tension Index
            </span>
          </div>

          {/* Country name */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "4px",
              marginTop: "12px",
            }}
          >
            <div
              style={{
                color: "#fff",
                fontSize: 52,
                fontWeight: 700,
                lineHeight: 1.2,
              }}
            >
              {countryKo}
            </div>
            <div
              style={{
                color: "rgba(255,255,255,0.5)",
                fontSize: 28,
                fontWeight: 400,
              }}
            >
              {countryEn}
            </div>
          </div>

          {/* Score + Level badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
              marginTop: "16px",
            }}
          >
            <div
              style={{
                color: "#fff",
                fontSize: 64,
                fontWeight: 800,
              }}
            >
              {tension.raw_score.toFixed(1)}
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: config.barColor,
                borderRadius: "10px",
                padding: "8px 18px",
              }}
            >
              <span
                style={{
                  color: "#fff",
                  fontSize: 24,
                  fontWeight: 700,
                }}
              >
                {config.label}
              </span>
            </div>
          </div>

          {/* Top issue */}
          {displayTopIssue ? (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                marginTop: "12px",
                color: "rgba(255,255,255,0.6)",
                fontSize: 22,
                lineHeight: 1.3,
              }}
            >
              <span style={{ fontWeight: 600 }}>TOP</span>
              <span style={{ color: "rgba(255,255,255,0.3)" }}>|</span>
              <span>{displayTopIssue}</span>
            </div>
          ) : null}

          {/* Footer */}
          <div
            style={{
              display: "flex",
              marginTop: "auto",
              paddingTop: "20px",
              color: "rgba(255,255,255,0.4)",
              fontSize: 18,
            }}
          >
            wewantpeace.live · 실시간 세계정세 모니터링
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}

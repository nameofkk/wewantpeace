import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "WeWantPeace Issue";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TOPIC_KO: Record<string, string> = {
  conflict: "무장 충돌",
  terror: "폭력·테러",
  coup: "정변·쿠데타",
  sanctions: "경제 제재",
  cyber: "사이버 공격",
  protest: "시위·집회",
  diplomacy: "외교",
  maritime: "해상 분쟁",
  disaster: "재난·재해",
  health: "감염병·보건",
  unknown: "이슈",
};

/* severity → 작은 pill 뱃지 색상만 (배경은 항상 동일) */
const SEVERITY_BADGE = [
  { min: 80, bg: "#DC2626", label: "Critical" },
  { min: 60, bg: "#D97706", label: "Serious" },
  { min: 40, bg: "#CA8A04", label: "Elevated" },
  { min: 20, bg: "#2563EB", label: "Moderate" },
  { min: 0, bg: "#16A34A", label: "Low" },
];

function getBadge(severity: number) {
  return SEVERITY_BADGE.find((b) => severity >= b.min) || SEVERITY_BADGE[SEVERITY_BADGE.length - 1];
}

export default async function OGImage({ params }: { params: { id: string } }) {
  let logoSrc: string | null = null;
  try {
    const logoRes = await fetch(
      new URL("../../../../public/logo-eye.png", import.meta.url)
    );
    const logoBuf = await logoRes.arrayBuffer();
    logoSrc = `data:image/png;base64,${Buffer.from(logoBuf).toString("base64")}`;
  } catch {}

  let issue: {
    title_ko?: string;
    title: string;
    severity: number;
    topic: string;
    event_count: number;
    country_code?: string;
    kscore?: number;
    independent_sources?: number;
  } | null = null;

  try {
    const res = await fetch(`${API_BASE}/issues/${params.id}`, {
      next: { revalidate: 120 },
    });
    if (res.ok) issue = await res.json();
  } catch {}

  if (!issue) {
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

  const title = issue.title_ko || issue.title;
  const displayTitle = title.length > 90 ? title.slice(0, 87) + "..." : title;
  const titleSize = title.length > 50 ? 40 : 48;
  const badge = getBadge(issue.severity);
  const topicKo = TOPIC_KO[issue.topic] || TOPIC_KO.unknown;
  const countryCode = issue.country_code || "";

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
        {/* Top row: logo + severity badge */}
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

        {/* Headline */}
        <div
          style={{
            display: "flex",
            flex: 1,
            alignItems: "center",
            color: "#F8FAFC",
            fontSize: titleSize,
            fontWeight: 700,
            lineHeight: 1.25,
            letterSpacing: "-0.5px",
            maxWidth: "95%",
          }}
        >
          {displayTitle}
        </div>

        {/* Bottom row: badges + url */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {countryCode ? (
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
                {countryCode}
              </div>
            ) : null}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: "#1E293B",
                color: "#94A3B8",
                padding: "5px 14px",
                borderRadius: "14px",
                fontSize: 14,
                fontWeight: 500,
                border: "1px solid #334155",
              }}
            >
              {topicKo}
            </div>
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

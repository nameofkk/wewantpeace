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

const SEVERITY_CONFIG = [
  { min: 80, gradStart: "#450a0a", barColor: "#ef4444", label: "극심" },
  { min: 60, gradStart: "#7f1d1d", barColor: "#f97316", label: "심각" },
  { min: 40, gradStart: "#78350f", barColor: "#f59e0b", label: "경계" },
  { min: 20, gradStart: "#1e3a5f", barColor: "#3b82f6", label: "주의" },
  { min: 0, gradStart: "#1e293b", barColor: "#10b981", label: "안정" },
];

function getSeverityConfig(severity: number) {
  return SEVERITY_CONFIG.find((c) => severity >= c.min) || SEVERITY_CONFIG[SEVERITY_CONFIG.length - 1];
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

  const title = issue.title_ko || issue.title;
  const displayTitle =
    title.length > 100 ? title.slice(0, 97) + "..." : title;
  const titleSize = title.length > 60 ? 36 : 48;
  const config = getSeverityConfig(issue.severity);
  const topicKo = TOPIC_KO[issue.topic] || TOPIC_KO.unknown;
  const kscore = issue.kscore ?? issue.severity / 10;
  const sources = issue.independent_sources ?? issue.event_count;

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
        {/* Left severity bar */}
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

          {/* Country + Topic */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginTop: "24px",
            }}
          >
            {issue.country_code ? (
              <span
                style={{
                  color: "rgba(255,255,255,0.7)",
                  fontSize: 22,
                  fontWeight: 600,
                }}
              >
                {issue.country_code}
              </span>
            ) : null}
            {issue.country_code ? (
              <span
                style={{ color: "rgba(255,255,255,0.3)", fontSize: 22 }}
              >
                ·
              </span>
            ) : null}
            <span
              style={{ color: "rgba(255,255,255,0.7)", fontSize: 22 }}
            >
              {topicKo}
            </span>
          </div>

          {/* Title */}
          <div
            style={{
              display: "flex",
              flex: 1,
              alignItems: "center",
              color: "#fff",
              fontSize: titleSize,
              fontWeight: 700,
              lineHeight: 1.3,
              maxHeight: "200px",
              overflow: "hidden",
              marginTop: "8px",
            }}
          >
            {displayTitle}
          </div>

          {/* Badges */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              marginTop: "16px",
            }}
          >
            {/* Severity badge */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: config.barColor,
                borderRadius: "8px",
                padding: "6px 14px",
              }}
            >
              <span
                style={{ color: "#fff", fontSize: 18, fontWeight: 700 }}
              >
                {config.label}
              </span>
            </div>

            {/* KScore badge */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                background: "rgba(255,255,255,0.12)",
                borderRadius: "8px",
                padding: "6px 14px",
              }}
            >
              <span
                style={{
                  color: "rgba(255,255,255,0.6)",
                  fontSize: 18,
                }}
              >
                K
              </span>
              <span
                style={{ color: "#fff", fontSize: 18, fontWeight: 700 }}
              >
                {typeof kscore === "number" ? kscore.toFixed(1) : kscore}
              </span>
            </div>

            {/* Sources badge */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: "rgba(255,255,255,0.12)",
                borderRadius: "8px",
                padding: "6px 14px",
              }}
            >
              <span
                style={{ color: "#fff", fontSize: 18, fontWeight: 600 }}
              >
                {sources}개 출처
              </span>
            </div>
          </div>

          {/* Footer */}
          <div
            style={{
              display: "flex",
              marginTop: "20px",
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

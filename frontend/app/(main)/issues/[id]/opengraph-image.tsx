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

const SEVERITY_BADGE = [
  { min: 80, bg: "#DC2626", label: "Critical" },
  { min: 60, bg: "#D97706", label: "Serious" },
  { min: 40, bg: "#CA8A04", label: "Elevated" },
  { min: 20, bg: "#2563EB", label: "Moderate" },
  { min: 0, bg: "#16A34A", label: "Low" },
];

function getBadge(severity: number) {
  return (
    SEVERITY_BADGE.find((b) => severity >= b.min) ||
    SEVERITY_BADGE[SEVERITY_BADGE.length - 1]
  );
}

/**
 * OG용 타이틀 압축:
 * 1. 이모지 제거
 * 2. 노이즈 접두사 제거
 * 3. 콜론/대시 뒤 핵심 추출
 * 4. 불필요한 후위절 제거
 * 5. maxLen 이내로 자연스럽게 잘라냄
 */
function condenseTitle(raw: string, maxLen = 40): string {
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
  if (colonIdx > 0 && colonIdx < 15) {
    t = t.slice(colonIdx + 2).trim();
  }

  t = t
    .replace(/했다고\s+.{1,10}(밝혔|전했|보도했|발표했|알렸)습니다\.?$/, "")
    .replace(/[이가을를은는]\s*(것으로\s+)?(밝혀졌|전해졌|알려졌|보도됐|확인됐)습니다\.?$/, "")
    .replace(/고\s+(밝혔|전했)습니다\.?$/, "")
    .trim();

  t = t.replace(/\.$/, "").trim();

  if (!t) return raw.slice(0, maxLen);

  if (t.length <= maxLen) return t;

  const slice = t.slice(0, maxLen);
  const lastBreak = Math.max(
    slice.lastIndexOf(", "),
    slice.lastIndexOf(" "),
    slice.lastIndexOf("·"),
    slice.lastIndexOf(" – "),
  );
  if (lastBreak > maxLen * 0.6) {
    return slice.slice(0, lastBreak).trim() + "…";
  }
  return slice.trim() + "…";
}

export default async function OGImage({
  params,
}: {
  params: { id: string };
}) {
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
    image_url?: string;
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
            color: "#E2E8F0",
            fontSize: 40,
            fontWeight: 800,
            fontFamily: "sans-serif",
          }}
        >
          {logoSrc ? (
            <img
              src={logoSrc}
              width={120}
              height={52}
              style={{ marginRight: "20px" }}
            />
          ) : null}
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  const rawTitle = issue.title_ko || issue.title;
  const headline = condenseTitle(rawTitle, 40);
  const titleSize = headline.length <= 18 ? 64 : headline.length <= 28 ? 56 : 48;
  const badge = getBadge(issue.severity);
  const topicKo = TOPIC_KO[issue.topic] || TOPIC_KO.unknown;
  const countryCode = issue.country_code || "";

  const hasBackground = !!issue.image_url;

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          width: "100%",
          height: "100%",
          position: "relative",
          fontFamily: "sans-serif",
        }}
      >
        {/* 배경 이미지 */}
        {hasBackground ? (
          <img
            src={issue.image_url!}
            width={1200}
            height={630}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: 1200,
              height: 630,
              objectFit: "cover",
              filter: "brightness(0.35)",
            }}
          />
        ) : null}

        {/* 콘텐츠 레이어 */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "100%",
            height: "100%",
            padding: "52px 60px",
            position: "relative",
            background: hasBackground
              ? "linear-gradient(180deg, rgba(11,17,32,0.3) 0%, rgba(11,17,32,0.85) 50%, rgba(11,17,32,0.95) 100%)"
              : "linear-gradient(180deg, #0B1120 0%, #162036 100%)",
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
            <div
              style={{ display: "flex", alignItems: "center", gap: "14px" }}
            >
              {logoSrc ? (
                <img
                  src={logoSrc}
                  width={120}
                  height={52}
                  style={{ width: "120px", height: "52px" }}
                />
              ) : null}
              <span style={{ color: "#CBD5E1", fontSize: 26, fontWeight: 800, letterSpacing: "-0.3px" }}>
                WeWantPeace
              </span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                background: badge.bg,
                color: badge.bg === "#CA8A04" ? "#1A1A2E" : "#FFFFFF",
                padding: "10px 24px",
                borderRadius: "24px",
                fontSize: 20,
                fontWeight: 800,
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
              color: "#FFFFFF",
              fontSize: titleSize,
              fontWeight: 900,
              lineHeight: 1.35,
              letterSpacing: "-0.5px",
              wordBreak: "keep-all",
              overflowWrap: "break-word",
              textShadow: "0 2px 12px rgba(0,0,0,0.7)",
            }}
          >
            {headline}
          </div>

          {/* Bottom row: badges + url */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div
              style={{ display: "flex", alignItems: "center", gap: "10px" }}
            >
              {countryCode ? (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    background: hasBackground ? "rgba(51,65,85,0.85)" : "#334155",
                    color: "#F1F5F9",
                    padding: "8px 18px",
                    borderRadius: "16px",
                    fontSize: 18,
                    fontWeight: 700,
                  }}
                >
                  {countryCode}
                </div>
              ) : null}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: hasBackground ? "rgba(30,41,59,0.85)" : "#1E293B",
                  color: "#CBD5E1",
                  padding: "8px 18px",
                  borderRadius: "16px",
                  fontSize: 18,
                  fontWeight: 600,
                  border: "1px solid #475569",
                }}
              >
                {topicKo}
              </div>
            </div>
            <span style={{ color: "#94A3B8", fontSize: 18, fontWeight: 600 }}>
              wewantpeace.live
            </span>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}

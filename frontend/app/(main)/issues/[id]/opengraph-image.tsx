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
 * 2. 노이즈 접두사 제거 (중동 라이브:, 요약, Recap 등)
 * 3. 콜론/대시 뒤 핵심 추출
 * 4. 불필요한 후위절 제거 (~ 밝혔습니다, ~발표했습니다 등)
 * 5. 35자 이내로 자연스럽게 잘라냄
 */
function condenseTitle(raw: string, maxLen = 35): string {
  // 이모지/특수문자 제거
  let t = raw
    .replace(
      /[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu,
      ""
    )
    .replace(/[⚡️🔴🟠🟡🟢⚠️🚨📰💥🔥❗️‼️]/g, "")
    .trim();

  // 노이즈 접두사 제거
  t = t
    .replace(/^(중동 라이브|MIDDLE EAST LIVE|요약|Recap|속보|BREAKING|URGENT)\s*[:：\-–—]\s*/i, "")
    .replace(/^(좋은 아침입니다|Good morning).*$/i, "")
    .trim();

  // 콜론 뒤 핵심 추출 (앞부분이 지역/카테고리인 경우)
  const colonIdx = t.indexOf(": ");
  if (colonIdx > 0 && colonIdx < 15) {
    t = t.slice(colonIdx + 2).trim();
  }

  // 한국어 장황한 어미 축약
  t = t
    .replace(/했다고\s+.{1,10}(밝혔|전했|보도했|발표했|알렸)습니다\.?$/, "")
    .replace(/[이가을를은는]\s*(것으로\s+)?(밝혀졌|전해졌|알려졌|보도됐|확인됐)습니다\.?$/, "")
    .replace(/고\s+(있|밝혔|전했)습니다\.?$/, "")
    .replace(/습니다\.?$/, "")
    .replace(/했다$/, "")
    .trim();

  // 마침표 제거
  t = t.replace(/\.$/, "").trim();

  if (!t) return raw.slice(0, maxLen);

  // 길이 제한: 자연스러운 끊김점에서 자르기
  if (t.length <= maxLen) return t;

  // 쉼표, 세미콜론, 공백 등에서 자르기
  const slice = t.slice(0, maxLen);
  const lastBreak = Math.max(
    slice.lastIndexOf(", "),
    slice.lastIndexOf(" "),
    slice.lastIndexOf("·"),
    slice.lastIndexOf(" – "),
  );
  if (lastBreak > maxLen * 0.6) {
    return slice.slice(0, lastBreak).trim();
  }
  return slice.trim();
}

/** 외부 이미지를 fetch하여 base64 data URI로 변환. 실패 시 null. */
async function fetchImageAsBase64(url: string): Promise<string | null> {
  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) return null;
    const contentLength = res.headers.get("content-length");
    if (contentLength && parseInt(contentLength) > 2 * 1024 * 1024) return null;
    const buf = await res.arrayBuffer();
    if (buf.byteLength > 2 * 1024 * 1024) return null;
    const contentType = res.headers.get("content-type") || "image/jpeg";
    return `data:${contentType};base64,${Buffer.from(buf).toString("base64")}`;
  } catch {
    return null;
  }
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
            color: "#94A3B8",
            fontSize: 32,
            fontFamily: "sans-serif",
          }}
        >
          {logoSrc ? (
            <img
              src={logoSrc}
              width={64}
              height={28}
              style={{ marginRight: "16px" }}
            />
          ) : null}
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  // 배경 이미지 fetch
  let bgImageSrc: string | null = null;
  if (issue.image_url) {
    bgImageSrc = await fetchImageAsBase64(issue.image_url);
  }

  const rawTitle = issue.title_ko || issue.title;
  const headline = condenseTitle(rawTitle, 35);
  const titleSize = headline.length <= 20 ? 60 : headline.length <= 30 ? 52 : 44;
  const badge = getBadge(issue.severity);
  const topicKo = TOPIC_KO[issue.topic] || TOPIC_KO.unknown;
  const countryCode = issue.country_code || "";

  const hasBackground = !!bgImageSrc;

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
        {/* 배경 이미지 (있을 때) */}
        {hasBackground ? (
          <img
            src={bgImageSrc!}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              filter: "brightness(0.45)",
            }}
          />
        ) : null}

        {/* 하단 그라데이션 오버레이 (이미지 있을 때) / 기존 배경 (없을 때) */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "100%",
            height: "100%",
            padding: "48px 56px",
            position: "relative",
            background: hasBackground
              ? "linear-gradient(180deg, rgba(11,17,32,0.2) 0%, rgba(11,17,32,0.85) 60%, rgba(11,17,32,0.95) 100%)"
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
              style={{ display: "flex", alignItems: "center", gap: "12px" }}
            >
              {logoSrc ? (
                <img
                  src={logoSrc}
                  width={64}
                  height={28}
                  style={{ width: "64px", height: "28px" }}
                />
              ) : null}
              <span style={{ color: "#94A3B8", fontSize: 18, fontWeight: 500 }}>
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
              lineHeight: 1.3,
              letterSpacing: "-0.5px",
              wordBreak: "keep-all",
              overflowWrap: "break-word",
              textShadow: hasBackground ? "0 2px 8px rgba(0,0,0,0.6)" : "none",
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
              style={{ display: "flex", alignItems: "center", gap: "8px" }}
            >
              {countryCode ? (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    background: hasBackground ? "rgba(51,65,85,0.8)" : "#334155",
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
                  background: hasBackground ? "rgba(30,41,59,0.8)" : "#1E293B",
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
      </div>
    ),
    { ...size }
  );
}

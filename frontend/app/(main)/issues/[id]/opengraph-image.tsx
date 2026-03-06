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

const COUNTRY_NAMES: Record<string, string> = {
  UA: "우크라이나", RU: "러시아", CN: "중국", US: "미국",
  KR: "대한민국", KP: "북한", JP: "일본", TW: "대만",
  IL: "이스라엘", PS: "팔레스타인", IR: "이란", SY: "시리아",
  MM: "미얀마", AF: "아프가니스탄", SD: "수단", YE: "예멘",
  ET: "에티오피아", SO: "소말리아", LB: "레바논", IQ: "이라크",
};

const SEVERITY_CONFIG = [
  { min: 80, bg: "#DC2626", label: "Critical", barColor: "#EF4444" },
  { min: 60, bg: "#D97706", label: "Serious", barColor: "#F59E0B" },
  { min: 40, bg: "#CA8A04", label: "Elevated", barColor: "#EAB308" },
  { min: 20, bg: "#2563EB", label: "Moderate", barColor: "#3B82F6" },
  { min: 0, bg: "#16A34A", label: "Low", barColor: "#22C55E" },
];

function getConfig(severity: number) {
  return SEVERITY_CONFIG.find((c) => severity >= c.min) || SEVERITY_CONFIG[SEVERITY_CONFIG.length - 1];
}

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
  if (colonIdx > 0 && colonIdx < 15) t = t.slice(colonIdx + 2).trim();
  t = t
    .replace(/했다고\s+.{1,10}(밝혔|전했|보도했|발표했|알렸)습니다\.?$/, "")
    .replace(/[이가을를은는]\s*(것으로\s+)?(밝혀졌|전해졌|알려졌|보도됐|확인됐)습니다\.?$/, "")
    .replace(/고\s+(밝혔|전했)습니다\.?$/, "")
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
  if (lastBreak > maxLen * 0.6) return slice.slice(0, lastBreak).trim() + "…";
  return slice.trim() + "…";
}

interface KScorePoint {
  time: string;
  kscore: number;
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
  } | null = null;

  try {
    const res = await fetch(`${API_BASE}/issues/${params.id}`, {
      next: { revalidate: 120 },
    });
    if (res.ok) issue = await res.json();
  } catch {}

  let kscoreHistory: KScorePoint[] = [];
  try {
    const res = await fetch(`${API_BASE}/issues/${params.id}/kscore-history?days=7`, {
      next: { revalidate: 300 },
    });
    if (res.ok) kscoreHistory = await res.json();
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
            background: "#0F172A",
            color: "#E2E8F0",
            fontSize: 40,
            fontWeight: 800,
            fontFamily: "sans-serif",
          }}
        >
          {logoSrc ? (
            <img src={logoSrc} width={120} height={52} alt="" style={{ marginRight: "20px" }} />
          ) : null}
          WeWantPeace
        </div>
      ),
      { ...size }
    );
  }

  const rawTitle = issue.title_ko || issue.title;
  const headline = condenseTitle(rawTitle, 45);
  const titleSize = headline.length <= 18 ? 52 : headline.length <= 30 ? 44 : 38;
  const config = getConfig(issue.severity);
  const topicKo = TOPIC_KO[issue.topic] || TOPIC_KO.unknown;
  const countryName = issue.country_code ? (COUNTRY_NAMES[issue.country_code] || issue.country_code) : "";
  const kscore = issue.kscore ?? 0;

  // KScore 그래프
  const graphWidth = 380;
  const graphHeight = 100;
  let svgPath = "";
  let svgAreaPath = "";
  const graphPoints = kscoreHistory.length >= 2 ? kscoreHistory : [];
  if (graphPoints.length >= 2) {
    const maxK = Math.max(...graphPoints.map((p) => p.kscore), 1);
    const step = graphWidth / (graphPoints.length - 1);
    const pts = graphPoints.map((p, i) => ({
      x: Math.round(i * step),
      y: Math.round(graphHeight - (p.kscore / maxK) * (graphHeight - 8)),
    }));
    svgPath = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
    svgAreaPath = `${svgPath} L${pts[pts.length - 1].x},${graphHeight} L${pts[0].x},${graphHeight} Z`;
  }

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          width: "100%",
          height: "100%",
          fontFamily: "sans-serif",
          background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)",
          position: "relative",
        }}
      >
        {/* 배경 그리드 패턴 */}
        <div
          style={{
            display: "flex",
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            opacity: 0.04,
            backgroundImage: "linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />

        {/* 상단 악센트 라인 */}
        <div
          style={{
            display: "flex",
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "4px",
            background: `linear-gradient(90deg, transparent 0%, ${config.barColor} 30%, ${config.barColor} 70%, transparent 100%)`,
          }}
        />

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            width: "100%",
            height: "100%",
            padding: "44px 56px 40px",
            position: "relative",
          }}
        >
          {/* ── 상단: 로고 + 뱃지들 ── */}
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
                  width={100}
                  height={43}
                  alt=""
                  style={{ width: "100px", height: "43px" }}
                />
              ) : null}
              <span style={{ color: "#94A3B8", fontSize: 22, fontWeight: 700, letterSpacing: "-0.3px" }}>
                WeWantPeace
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ color: "#64748B", fontSize: 16, fontWeight: 600 }}>
                실시간 세계정세 모니터링
              </span>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: config.bg,
                  color: config.bg === "#CA8A04" ? "#1A1A2E" : "#FFFFFF",
                  padding: "8px 20px",
                  borderRadius: "20px",
                  fontSize: 16,
                  fontWeight: 800,
                }}
              >
                {config.label}
              </div>
            </div>
          </div>

          {/* ── 중앙: 제목 + 지표 + 그래프 ── */}
          <div
            style={{
              display: "flex",
              flex: 1,
              gap: "40px",
              marginTop: "24px",
              alignItems: "center",
            }}
          >
            {/* 왼쪽: 제목 + 메타 */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                flex: 1,
                gap: "12px",
              }}
            >
              {/* 메타 뱃지 */}
              <div style={{ display: "flex", gap: "8px" }}>
                {countryName && (
                  <span
                    style={{
                      background: "#1E293B",
                      color: "#CBD5E1",
                      padding: "6px 14px",
                      borderRadius: "14px",
                      fontSize: 15,
                      fontWeight: 600,
                      border: "1px solid #334155",
                    }}
                  >
                    {countryName}
                  </span>
                )}
                <span
                  style={{
                    background: "#1E293B",
                    color: "#CBD5E1",
                    padding: "6px 14px",
                    borderRadius: "14px",
                    fontSize: 15,
                    fontWeight: 600,
                    border: "1px solid #334155",
                  }}
                >
                  {topicKo}
                </span>
              </div>

              {/* 헤드라인 */}
              <div
                style={{
                  color: "#FFFFFF",
                  fontSize: titleSize,
                  fontWeight: 900,
                  lineHeight: 1.3,
                  letterSpacing: "-0.5px",
                  wordBreak: "keep-all",
                  overflowWrap: "break-word",
                }}
              >
                {headline}
              </div>

              {/* 지표 행 */}
              <div style={{ display: "flex", alignItems: "center", gap: "24px", marginTop: "8px" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{ color: config.barColor, fontSize: 36, fontWeight: 900, lineHeight: 1 }}>
                    {issue.severity}
                  </span>
                  <span style={{ color: "#64748B", fontSize: 13, fontWeight: 600 }}>
                    위기지수
                  </span>
                </div>
                <div style={{ display: "flex", width: "1px", height: "36px", background: "#334155" }} />
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{ color: "#E2E8F0", fontSize: 36, fontWeight: 900, lineHeight: 1 }}>
                    K{kscore.toFixed(1)}
                  </span>
                  <span style={{ color: "#64748B", fontSize: 13, fontWeight: 600 }}>
                    KScore
                  </span>
                </div>
                <div style={{ display: "flex", width: "1px", height: "36px", background: "#334155" }} />
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{ color: "#E2E8F0", fontSize: 36, fontWeight: 900, lineHeight: 1 }}>
                    {issue.event_count}
                  </span>
                  <span style={{ color: "#64748B", fontSize: 13, fontWeight: 600 }}>
                    보도 건수
                  </span>
                </div>
              </div>
            </div>

            {/* 오른쪽: KScore 그래프 */}
            {graphPoints.length >= 2 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  width: "400px",
                  gap: "8px",
                }}
              >
                <span style={{ color: "#64748B", fontSize: 14, fontWeight: 600 }}>
                  KScore 7일 추이
                </span>
                <div
                  style={{
                    display: "flex",
                    position: "relative",
                    width: `${graphWidth}px`,
                    height: `${graphHeight}px`,
                    background: "rgba(15,23,42,0.6)",
                    borderRadius: "12px",
                    border: "1px solid #1E293B",
                  }}
                >
                  <svg
                    width={graphWidth}
                    height={graphHeight}
                    viewBox={`0 0 ${graphWidth} ${graphHeight}`}
                    style={{ position: "absolute", top: 0, left: 0 }}
                  >
                    <defs>
                      <linearGradient id="kGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={config.barColor} stopOpacity="0.3" />
                        <stop offset="100%" stopColor={config.barColor} stopOpacity="0.02" />
                      </linearGradient>
                    </defs>
                    <path d={svgAreaPath} fill="url(#kGrad)" />
                    <path d={svgPath} fill="none" stroke={config.barColor} strokeWidth="3" />
                    {(() => {
                      const maxK = Math.max(...graphPoints.map((p) => p.kscore), 1);
                      const lastPt = graphPoints[graphPoints.length - 1];
                      const lx = graphWidth;
                      const ly = graphHeight - (lastPt.kscore / maxK) * (graphHeight - 8);
                      return <circle cx={lx - 1} cy={ly} r="5" fill={config.barColor} />;
                    })()}
                  </svg>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", width: `${graphWidth}px` }}>
                  <span style={{ color: "#475569", fontSize: 12 }}>
                    {new Date(graphPoints[0].time).toLocaleDateString("ko-KR", { month: "short", day: "numeric" })}
                  </span>
                  <span style={{ color: "#475569", fontSize: 12 }}>
                    {new Date(graphPoints[graphPoints.length - 1].time).toLocaleDateString("ko-KR", { month: "short", day: "numeric" })}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* ── 하단: 브랜드 ── */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              marginTop: "auto",
            }}
          >
            <span style={{ color: "#64748B", fontSize: 16, fontWeight: 600 }}>
              wewantpeace.live
            </span>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}

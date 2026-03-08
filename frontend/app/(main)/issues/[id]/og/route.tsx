import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

export const runtime = "edge";

const size = { width: 1200, height: 630 };
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── 커스텀 폰트 (모듈 레벨, 첫 요청 시 1회 fetch) ──
const playfairFont = fetch(
  "https://fonts.gstatic.com/s/playfairdisplay/v37/nuFRD-vYSZviVYUb_rj3ij__anPXDTnCjmHKM4nYO7KN_qiTbtbK-F2rA0s.ttf"
).then((r) => r.arrayBuffer()).catch((): null => null);

const notoSansKrFont = fetch(
  "https://fonts.gstatic.com/s/notosanskr/v36/PbyxFmXiEBPT4ITbgNA5Cgms3VYcOA-vvnIzzuoyeLTq8H4hfeE.ttf"
).then((r) => r.arrayBuffer()).catch((): null => null);

const TOPIC: Record<string, { ko: string; en: string }> = {
  conflict: { ko: "무장 충돌", en: "Armed Conflict" },
  terror: { ko: "폭력·테러", en: "Violence & Terror" },
  coup: { ko: "정변·쿠데타", en: "Coup & Upheaval" },
  sanctions: { ko: "경제 제재", en: "Sanctions" },
  cyber: { ko: "사이버 공격", en: "Cyber Attack" },
  protest: { ko: "시위·집회", en: "Protest" },
  diplomacy: { ko: "외교", en: "Diplomacy" },
  maritime: { ko: "해상 분쟁", en: "Maritime Dispute" },
  disaster: { ko: "재난·재해", en: "Disaster" },
  health: { ko: "감염병·보건", en: "Health Crisis" },
  unknown: { ko: "이슈", en: "Issue" },
};

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

function cleanTitle(raw: string): string {
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
  return t || raw;
}

interface KScorePoint {
  time: string;
  kscore: number;
}

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  // 폰트 로드
  const [playfairData, notoSansKrData] = await Promise.all([playfairFont, notoSansKrFont]);
  const ogFonts: { name: string; data: ArrayBuffer; weight: 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900; style: "normal" }[] = [];
  if (playfairData) ogFonts.push({ name: "Playfair Display", data: playfairData, weight: 900 as const, style: "normal" });
  if (notoSansKrData) ogFonts.push({ name: "Noto Sans KR", data: notoSansKrData, weight: 700 as const, style: "normal" });

  const lang = req.nextUrl.searchParams.get("lang") === "en" ? "en" : "ko";

  let logoSrc: string | null = null;
  try {
    const logoRes = await fetch(
      new URL("../../../../../public/logo-eye.png", import.meta.url)
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
    image_url?: string;
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
      { ...size, fonts: ogFonts }
    );
  }

  const rawTitle = lang === "en" ? (issue.title || issue.title_ko || "") : (issue.title_ko || issue.title || "");
  const headline = cleanTitle(rawTitle);
  const titleSize = headline.length <= 18 ? 56 : headline.length <= 30 ? 46 : headline.length <= 50 ? 38 : 32;
  const config = getConfig(issue.severity);
  const topicLabel = (TOPIC[issue.topic] || TOPIC.unknown)[lang];
  const cn = issue.country_code ? COUNTRY_NAMES[issue.country_code] : null;
  const countryName = cn ? cn[lang] : (issue.country_code || "");
  const kscore = issue.kscore ?? 0;

  // Satori는 외부 URL을 직접 fetch할 수 없으므로 Base64로 변환
  let bgImageSrc: string | null = null;
  if (issue.image_url) {
    try {
      const imgRes = await fetch(issue.image_url, { signal: AbortSignal.timeout(3000) });
      if (imgRes.ok) {
        const ct = imgRes.headers.get("content-type") || "image/jpeg";
        const buf = await imgRes.arrayBuffer();
        bgImageSrc = `data:${ct};base64,${Buffer.from(buf).toString("base64")}`;
      }
    } catch {}
  }
  const hasBackground = !!bgImageSrc;

  // KScore 그래프
  const graphWidth = 420;
  const graphHeight = 120;
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
          fontFamily: "'Noto Sans KR', sans-serif",
          background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)",
          position: "relative",
        }}
      >
        {/* 배경 이미지 (Base64) */}
        {hasBackground ? (
          <img
            src={bgImageSrc!}
            width={1200}
            height={630}
            alt=""
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: 1200,
              height: 630,
              objectFit: "cover",
              filter: "brightness(0.5) saturate(0.8)",
            }}
          />
        ) : null}

        {/* 배경 패턴 */}
        {!hasBackground && (
          <div
            style={{
              display: "flex",
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              background: "linear-gradient(135deg, rgba(30,41,59,0.5) 0%, transparent 50%, rgba(30,41,59,0.5) 100%)",
            }}
          />
        )}

        {/* 상단 악센트 라인 */}
        <div
          style={{
            display: "flex",
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "6px",
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
            background: hasBackground
              ? "linear-gradient(180deg, rgba(15,23,42,0.4) 0%, rgba(15,23,42,0.75) 40%, rgba(15,23,42,0.9) 100%)"
              : "transparent",
          }}
        >
          {/* 상단: 로고 + 뱃지들 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
              {logoSrc ? (
                <img
                  src={logoSrc}
                  width={140}
                  height={60}
                  alt=""
                  style={{ width: "140px", height: "60px" }}
                />
              ) : null}
              <span style={{ color: "#94A3B8", fontSize: 28, fontWeight: 800, letterSpacing: "-0.3px" }}>
                WeWantPeace
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{ color: "#94A3B8", fontSize: 20, fontWeight: 700 }}>
                {lang === "en" ? "Real-time Global Conflict Monitor" : "실시간 글로벌 분쟁 모니터링"}
              </span>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  background: config.bg,
                  color: config.bg === "#CA8A04" ? "#1A1A2E" : "#FFFFFF",
                  padding: "10px 26px",
                  borderRadius: "24px",
                  fontSize: 20,
                  fontWeight: 800,
                }}
              >
                {config.label}
              </div>
            </div>
          </div>

          {/* 중앙: 제목 + 지표 + 그래프 */}
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
              <div style={{ display: "flex", gap: "10px" }}>
                {countryName && (
                  <span
                    style={{
                      background: "#1E293B",
                      color: "#E2E8F0",
                      padding: "8px 18px",
                      borderRadius: "16px",
                      fontSize: 18,
                      fontWeight: 700,
                      border: "1px solid #334155",
                    }}
                  >
                    {countryName}
                  </span>
                )}
                <span
                  style={{
                    background: "#1E293B",
                    color: "#E2E8F0",
                    padding: "8px 18px",
                    borderRadius: "16px",
                    fontSize: 18,
                    fontWeight: 700,
                    border: "1px solid #334155",
                  }}
                >
                  {topicLabel}
                </span>
              </div>

              {/* 헤드라인 */}
              <div
                style={{
                  display: "flex",
                  color: "#FFFFFF",
                  fontSize: titleSize,
                  fontWeight: 900,
                  fontFamily: "'Playfair Display', 'Noto Sans KR', serif",
                  lineHeight: 1.35,
                  letterSpacing: "-0.5px",
                  wordBreak: "keep-all",
                  overflowWrap: "break-word",
                  maxHeight: `${Math.round(titleSize * 1.35 * 3)}px`,
                  overflow: "hidden",
                }}
              >
                {headline}
              </div>

              {/* 지표 행 */}
              <div style={{ display: "flex", alignItems: "center", gap: "28px", marginTop: "12px" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{ color: config.barColor, fontSize: 44, fontWeight: 900, lineHeight: 1 }}>
                    {issue.severity}
                  </span>
                  <span style={{ color: "#94A3B8", fontSize: 16, fontWeight: 700 }}>
                    {lang === "en" ? "Severity" : "위기지수"}
                  </span>
                </div>
                <div style={{ display: "flex", width: "2px", height: "44px", background: "#334155" }} />
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{ color: "#E2E8F0", fontSize: 44, fontWeight: 900, lineHeight: 1 }}>
                    K{kscore.toFixed(1)}
                  </span>
                  <span style={{ color: "#94A3B8", fontSize: 16, fontWeight: 700 }}>
                    KScore
                  </span>
                </div>
                <div style={{ display: "flex", width: "2px", height: "44px", background: "#334155" }} />
                <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                  <span style={{ color: "#E2E8F0", fontSize: 44, fontWeight: 900, lineHeight: 1 }}>
                    {issue.event_count}
                  </span>
                  <span style={{ color: "#94A3B8", fontSize: 16, fontWeight: 700 }}>
                    {lang === "en" ? "Sources" : "보도 건수"}
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
                  width: "440px",
                  gap: "8px",
                }}
              >
                <span style={{ color: "#94A3B8", fontSize: 18, fontWeight: 700 }}>
                  {lang === "en" ? "KScore 7-Day Trend" : "KScore 7일 추이"}
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
                    <path d={svgPath} fill="none" stroke={config.barColor} strokeWidth="4" />
                    {(() => {
                      const maxK = Math.max(...graphPoints.map((p) => p.kscore), 1);
                      const lastPt = graphPoints[graphPoints.length - 1];
                      const lx = graphWidth;
                      const ly = graphHeight - (lastPt.kscore / maxK) * (graphHeight - 8);
                      return <circle cx={lx - 1} cy={ly} r="7" fill={config.barColor} />;
                    })()}
                  </svg>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", width: `${graphWidth}px` }}>
                  <span style={{ color: "#64748B", fontSize: 15, fontWeight: 600 }}>
                    {new Date(graphPoints[0].time).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR", { month: "short", day: "numeric" })}
                  </span>
                  <span style={{ color: "#64748B", fontSize: 15, fontWeight: 600 }}>
                    {new Date(graphPoints[graphPoints.length - 1].time).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR", { month: "short", day: "numeric" })}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* 하단: 브랜드 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "flex-end",
              marginTop: "auto",
            }}
          >
            <span style={{ color: "#94A3B8", fontSize: 20, fontWeight: 700 }}>
              wewantpeace.live
            </span>
          </div>
        </div>
      </div>
    ),
    { ...size, fonts: ogFonts }
  );
}

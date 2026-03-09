import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

export const runtime = "edge";

const size = { width: 1200, height: 630 };
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── 커스텀 폰트 (모듈 레벨, 첫 요청 시 1회 fetch) ──
// 영문 헤드라인: Noto Serif KR Black (900)
const notoSerifKrFont = fetch(
  "https://fonts.gstatic.com/s/notoserifkr/v31/3JnoSDn90Gmq2mr3blnHaTZXbOtLJDvui3JOnchPf852.ttf"
).then((r) => r.arrayBuffer()).catch((): null => null);

// 한국어 헤드라인: Gothic A1 Black (900)
const gothicA1Font = fetch(
  "https://fonts.gstatic.com/s/gothica1/v18/CSR44z5ZnPydRjlCCwlC6OAKSA.ttf"
).then((r) => r.arrayBuffer()).catch((): null => null);

// 본문: Inter Semi-Bold (600)
const interFont = fetch(
  "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf"
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

function cleanTitle(raw: string, lang: string = "ko"): string {
  let t = raw
    .replace(
      /[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu,
      ""
    )
    .replace(/[⚡️🔴🟠🟡🟢⚠️🚨📰💥🔥❗️‼️]/g, "")
    .trim();
  // 접두사 제거
  t = t
    .replace(/^(중동 라이브|MIDDLE EAST LIVE|요약|Recap|속보|BREAKING|URGENT)\s*[:：\-–—]\s*/i, "")
    .replace(/^(좋은 아침입니다|Good morning).*$/i, "")
    .trim();
  const colonIdx = t.indexOf(": ");
  if (colonIdx > 0 && colonIdx < 15) t = t.slice(colonIdx + 2).trim();
  // 한국어 서술형 어미 → 명사형 종결 (뉴스 스타일)
  t = t
    .replace(/했다고\s+.{1,10}(밝혔|전했|보도했|발표했|알렸)습니다\.?$/, "")
    .replace(/[이가을를은는]\s*(것으로\s+)?(밝혀졌|전해졌|알려졌|보도됐|확인됐)습니다\.?$/, "")
    .replace(/고\s+(밝혔|전했)습니다\.?$/, "")
    .replace(/(하고\s+있|하려고\s+노력하|하려\s+하|시도하|노력하)(고 있다|다)\.?$/, "")
    .replace(/(에\s+나서|을\s+촉구하|를\s+요구하|에\s+돌입하)(고 있다|다|였다)\.?$/, "")
    .replace(/(습니다|합니다|됩니다|입니다|했다|됐다|였다|이다)\.?$/, "")
    .replace(/[.…]+$/, "")
    .trim();
  // 자연스러운 지점에서 자르기 (영어는 글자 폭이 좁아 더 긴 임계값 사용)
  const maxLen = lang === "en" ? 55 : 40;
  const hardMax = lang === "en" ? 58 : 45;
  const hardCut = lang === "en" ? 52 : 42;
  if (t.length > maxLen) {
    const cutPoints = [",", "…", "·", " - ", "–"];
    for (const sep of cutPoints) {
      const idx = t.lastIndexOf(sep, maxLen);
      if (idx >= 15) { t = t.slice(0, idx).trim(); break; }
    }
    if (t.length > hardMax) {
      if (lang === "en") {
        const lastSpace = t.lastIndexOf(" ", hardCut);
        t = lastSpace > 15 ? t.slice(0, lastSpace) + "…" : t.slice(0, hardCut) + "…";
      } else {
        t = t.slice(0, hardCut) + "…";
      }
    }
  }
  return t || raw;
}

/**
 * 헤드라인을 자연스러운 지점에서 2줄로 분할.
 * 규칙:
 *   1. 18자 이하면 1줄 유지
 *   2. 구분자(, · … – — ;) 중 중앙에 가장 가까운 지점에서 줄바꿈
 *   3. 첫 줄 최소 8자, 둘째 줄 최소 4자
 *   4. 구분자가 없으면 1줄 유지 (CSS 자동 줄바꿈에 맡김)
 */
function splitHeadline(text: string, lang: string = "ko"): string[] {
  const singleLineMax = lang === "en" ? 28 : 18;
  if (text.length <= singleLineMax) return [text];

  const seps = [", ", "…", "· ", " - ", "– ", "— ", "; "];
  const target = Math.floor(text.length * 0.55); // 첫 줄을 약간 길게
  let bestAt = -1;
  let bestDist = Infinity;

  for (const sep of seps) {
    let from = 0;
    while (true) {
      const idx = text.indexOf(sep, from);
      if (idx === -1) break;
      const after = idx + sep.length;
      if (after >= 8 && after <= text.length - 4) {
        const d = Math.abs(after - target);
        if (d < bestDist) { bestDist = d; bestAt = after; }
      }
      from = idx + 1;
    }
  }

  if (bestAt > 0) {
    const line1 = text.slice(0, bestAt).trim().replace(/[,;·]$/, "").trim();
    const line2 = text.slice(bestAt).trim();
    return [line1, line2];
  }

  // 영어: 구분자 없으면 단어 경계에서 분할
  if (lang === "en" && text.length > singleLineMax) {
    const target = Math.floor(text.length * 0.55);
    const spaceIdx = text.lastIndexOf(" ", target);
    if (spaceIdx >= 8 && spaceIdx <= text.length - 4) {
      return [text.slice(0, spaceIdx), text.slice(spaceIdx + 1)];
    }
  }

  return [text];
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
  const [notoSerifKrData, gothicA1Data, interData] = await Promise.all([notoSerifKrFont, gothicA1Font, interFont]);
  const ogFonts: { name: string; data: ArrayBuffer; weight: 100 | 200 | 300 | 400 | 500 | 600 | 700 | 800 | 900; style: "normal" }[] = [];
  if (notoSerifKrData) ogFonts.push({ name: "Noto Serif KR", data: notoSerifKrData, weight: 900 as const, style: "normal" });
  if (gothicA1Data) ogFonts.push({ name: "Gothic A1", data: gothicA1Data, weight: 900 as const, style: "normal" });
  if (interData) ogFonts.push({ name: "Inter", data: interData, weight: 600 as const, style: "normal" });

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
    const res = await fetch(`${API_BASE}/trending/kscore-history/${params.id}?days=7`, {
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
  const headline = cleanTitle(rawTitle, lang);
  const headlineLines = splitHeadline(headline, lang);
  const titleSize = lang === "en"
    ? (headline.length <= 15 ? 72 : headline.length <= 25 ? 60 : headline.length <= 38 ? 48 : headline.length <= 52 ? 40 : 34)
    : (headline.length <= 10 ? 72 : headline.length <= 18 ? 60 : headline.length <= 28 ? 48 : headline.length <= 40 ? 40 : 34);
  const config = getConfig(issue.severity);
  const topicLabel = (TOPIC[issue.topic] || TOPIC.unknown)[lang];
  const cn = issue.country_code ? COUNTRY_NAMES[issue.country_code] : null;
  const countryName = cn ? cn[lang] : (issue.country_code || "");
  const kscore = issue.kscore ?? 0;
  const displayFont = lang === "en" ? "'Noto Serif KR', serif" : "'Gothic A1', sans-serif";

  // Satori는 외부 URL을 직접 fetch할 수 없으므로 Base64로 변환
  // Satori가 지원하는 포맷: JPEG, PNG, GIF (WebP 미지원 → 크래시)
  // Edge Runtime 메모리 한계로 대용량 이미지도 스킵
  const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif"];
  const MAX_IMAGE_BYTES = 800_000; // 800KB
  let bgImageSrc: string | null = null;
  if (issue.image_url) {
    try {
      const imgRes = await fetch(issue.image_url, { signal: AbortSignal.timeout(3000) });
      if (imgRes.ok) {
        const ct = imgRes.headers.get("content-type") || "";
        const cl = parseInt(imgRes.headers.get("content-length") || "0", 10);
        if (ALLOWED_IMAGE_TYPES.some((t) => ct.startsWith(t)) && (cl === 0 || cl <= MAX_IMAGE_BYTES)) {
          const buf = await imgRes.arrayBuffer();
          if (buf.byteLength <= MAX_IMAGE_BYTES) {
            bgImageSrc = `data:${ct};base64,${Buffer.from(buf).toString("base64")}`;
          }
        }
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
          fontFamily: "'Inter', sans-serif",
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
              filter: "brightness(0.65) saturate(0.8)",
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
            padding: "44px 56px 40px 40px",
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
              <span style={{ color: "#94A3B8", fontSize: 28, fontWeight: 600, letterSpacing: "-0.3px" }}>
                WeWantPeace
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{ color: "#94A3B8", fontSize: 20, fontWeight: 600 }}>
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
              marginTop: "36px",
              alignItems: "center",
            }}
          >
            {/* 왼쪽: 제목 + 메타 */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                flex: 1,
                gap: "20px",
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
                  flexDirection: "column",
                  color: "#FFFFFF",
                  fontSize: titleSize,
                  fontWeight: 900,
                  fontFamily: displayFont,
                  lineHeight: 1.35,
                  letterSpacing: "-0.5px",
                  wordBreak: "keep-all",
                  overflowWrap: "break-word",
                  maxHeight: `${Math.round(titleSize * 1.35 * 3)}px`,
                  overflow: "hidden",
                }}
              >
                {headlineLines.map((line, i) => (
                  <span key={i} style={{ display: "block" }}>{line}</span>
                ))}
              </div>

              {/* 지표 행 */}
              <div style={{ display: "flex", alignItems: "center", gap: "28px", marginTop: "24px" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "2px" }}>
                  <span style={{ color: config.barColor, fontSize: 44, fontWeight: 900, fontFamily: displayFont, lineHeight: 1 }}>
                    {issue.severity}
                  </span>
                  <span style={{ color: "#94A3B8", fontSize: 16, fontWeight: 600 }}>
                    {lang === "en" ? "Severity" : "위기지수"}
                  </span>
                </div>
                <div style={{ display: "flex", width: "2px", height: "44px", background: "#334155" }} />
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "2px" }}>
                  <span style={{ color: "#E2E8F0", fontSize: 44, fontWeight: 900, fontFamily: displayFont, lineHeight: 1 }}>
                    K{kscore.toFixed(1)}
                  </span>
                  <span style={{ color: "#94A3B8", fontSize: 16, fontWeight: 600 }}>
                    KScore
                  </span>
                </div>
                <div style={{ display: "flex", width: "2px", height: "44px", background: "#334155" }} />
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "2px" }}>
                  <span style={{ color: "#E2E8F0", fontSize: 44, fontWeight: 900, fontFamily: displayFont, lineHeight: 1 }}>
                    {issue.event_count}
                  </span>
                  <span style={{ color: "#94A3B8", fontSize: 16, fontWeight: 600 }}>
                    {lang === "en" ? "Sources" : "보도 건수"}
                  </span>
                </div>
              </div>
            </div>

            {/* 오른쪽: KScore 그래프 (한국어만) */}
            {lang === "ko" && graphPoints.length >= 2 && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  width: "440px",
                  gap: "8px",
                }}
              >
                <span style={{ color: "#94A3B8", fontSize: 18, fontWeight: 600 }}>
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
                    {new Date(graphPoints[0].time).toLocaleDateString("ko-KR", { month: "short", day: "numeric" })}
                  </span>
                  <span style={{ color: "#64748B", fontSize: 15, fontWeight: 600 }}>
                    {new Date(graphPoints[graphPoints.length - 1].time).toLocaleDateString("ko-KR", { month: "short", day: "numeric" })}
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
            <span style={{ color: "#94A3B8", fontSize: 20, fontWeight: 600 }}>
              wewantpeace.live
            </span>
          </div>
        </div>
      </div>
    ),
    { ...size, fonts: ogFonts }
  );
}

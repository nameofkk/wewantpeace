import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const runtime = "nodejs";

const size = { width: 1200, height: 630 };
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── 커스텀 폰트 (filesystem에서 직접 읽기 — self-fetch 데드락 방지) ──
const FONT_DIR = join(process.cwd(), "public", "fonts");

const notoSerifKrFont = readFile(join(FONT_DIR, "NotoSerifKR-Black-latin.ttf"))
  .then((buf) => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer)
  .catch((): null => null);

const gothicA1Font = readFile(join(FONT_DIR, "GothicA1-Black-subset.ttf"))
  .then((buf) => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer)
  .catch((): null => null);

const interFont = readFile(join(FONT_DIR, "Inter-SemiBold.ttf"))
  .then((buf) => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer)
  .catch((): null => null);

// ── 토픽 레이블 ──
const TOPIC: Record<string, { ko: string; en: string }> = {
  conflict:  { ko: "무장 충돌",   en: "Armed Conflict" },
  terror:    { ko: "폭력·테러",   en: "Violence & Terror" },
  coup:      { ko: "정변·쿠데타", en: "Coup & Upheaval" },
  sanctions: { ko: "경제 제재",   en: "Sanctions" },
  cyber:     { ko: "사이버 공격", en: "Cyber Attack" },
  protest:   { ko: "시위·집회",   en: "Protest" },
  diplomacy: { ko: "외교",        en: "Diplomacy" },
  maritime:  { ko: "해상 분쟁",   en: "Maritime Dispute" },
  disaster:  { ko: "재난·재해",   en: "Disaster" },
  health:    { ko: "감염병·보건", en: "Health Crisis" },
  unknown:   { ko: "이슈",        en: "Issue" },
};

const COUNTRY_NAMES: Record<string, { ko: string; en: string }> = {
  UA: { ko: "우크라이나",    en: "Ukraine" },
  RU: { ko: "러시아",        en: "Russia" },
  CN: { ko: "중국",          en: "China" },
  US: { ko: "미국",          en: "United States" },
  KR: { ko: "대한민국",      en: "South Korea" },
  KP: { ko: "북한",          en: "North Korea" },
  JP: { ko: "일본",          en: "Japan" },
  TW: { ko: "대만",          en: "Taiwan" },
  IL: { ko: "이스라엘",      en: "Israel" },
  PS: { ko: "팔레스타인",    en: "Palestine" },
  IR: { ko: "이란",          en: "Iran" },
  SY: { ko: "시리아",        en: "Syria" },
  MM: { ko: "미얀마",        en: "Myanmar" },
  AF: { ko: "아프가니스탄",  en: "Afghanistan" },
  SD: { ko: "수단",          en: "Sudan" },
  YE: { ko: "예멘",          en: "Yemen" },
  ET: { ko: "에티오피아",    en: "Ethiopia" },
  SO: { ko: "소말리아",      en: "Somalia" },
  LB: { ko: "레바논",        en: "Lebanon" },
  IQ: { ko: "이라크",        en: "Iraq" },
  PK: { ko: "파키스탄",      en: "Pakistan" },
  ML: { ko: "말리",          en: "Mali" },
  DE: { ko: "독일",          en: "Germany" },
};

const SEVERITY_CONFIG = [
  { min: 80, color: "#EF4444", bg: "#DC2626", label: "Critical",  labelKo: "위험" },
  { min: 60, color: "#F59E0B", bg: "#D97706", label: "Serious",   labelKo: "심각" },
  { min: 40, color: "#EAB308", bg: "#CA8A04", label: "Elevated",  labelKo: "경계" },
  { min: 20, color: "#3B82F6", bg: "#2563EB", label: "Moderate",  labelKo: "주의" },
  { min:  0, color: "#22C55E", bg: "#16A34A", label: "Low",       labelKo: "안정" },
];

function getConfig(severity: number) {
  return SEVERITY_CONFIG.find((c) => severity >= c.min) ?? SEVERITY_CONFIG[SEVERITY_CONFIG.length - 1];
}

// ── 레이아웃 상수 ──
// 풀블리드 (이미지 있음): 좌62 + 우60 = 가용폭 1078px
const IMAGE_CONTENT_W = 1078;
// 에디토리얼 폴백 (이미지 없음): 좌80 + 우76 = 가용폭 1044px
const EDITORIAL_CONTENT_W = 1044;

/**
 * 텍스트 한 줄을 주어진 가용폭에 맞는 폰트 크기 자동 계산
 *
 * 실측 기반 문자당 폭 비율:
 *   Gothic A1 Black (KO):       fontSize × 0.95
 *   Noto Serif KR Black (EN):   fontSize × 0.58
 *
 * maxPx / minPx 로 클램핑
 */
function fitFontSize(
  text: string,
  lang: string,
  contentW: number,
  maxPx: number,
  minPx: number,
): number {
  if (!text || text.length === 0) return maxPx;
  const charRatio = lang === "en" ? 0.58 : 0.95;
  const fit = Math.floor(contentW / (text.length * charRatio));
  return Math.max(minPx, Math.min(maxPx, fit));
}

function cleanTitle(raw: string, lang: string = "ko"): string {
  let t = raw
    .replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{FE00}-\u{FE0F}\u{200D}\u{20E3}\u{E0020}-\u{E007F}]/gu, "")
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
    .replace(/(하고\s+있|하려고\s+노력하|하려\s+하|시도하|노력하)(고 있다|다)\.?$/, "")
    .replace(/(에\s+나서|을\s+촉구하|를\s+요구하|에\s+돌입하)(고 있다|다|였다)\.?$/, "")
    .replace(/(습니다|합니다|됩니다|입니다|했다|됐다|였다|이다)\.?$/, "")
    .replace(/[.…]+$/, "")
    .trim();
  const maxLen  = lang === "en" ? 52 : 36;
  const hardCut = lang === "en" ? 50 : 38;
  if (t.length > maxLen) {
    const cutPoints = [",", "…", "·", " - ", "–"];
    for (const sep of cutPoints) {
      const idx = t.lastIndexOf(sep, maxLen);
      if (idx >= 12) { t = t.slice(0, idx).trim(); break; }
    }
    if (t.length > maxLen + 4) {
      if (lang === "en") {
        const sp = t.lastIndexOf(" ", hardCut);
        t = sp > 12 ? t.slice(0, sp) + "…" : t.slice(0, hardCut) + "…";
      } else {
        t = t.slice(0, hardCut) + "…";
      }
    }
  }
  return t || raw;
}

/**
 * 헤드라인을 최대 2줄로 분할.
 *
 * singleLineMax: 이 글자 수 이하면 분할 없이 단일 줄 유지
 *   KO: max 88px에서 1078px에 들어가는 글자 수 = floor(1078/(88×0.95)) = 12
 *   EN: max 88px에서 1078px에 들어가는 글자 수 = floor(1078/(88×0.58)) = 21
 */
function splitHeadline(text: string, lang: string = "ko"): string[] {
  const singleLineMax = lang === "en" ? 21 : 12;
  if (text.length <= singleLineMax) return [text];

  const seps = [", ", "…", "· ", " - ", "– ", "— ", "; "];
  const target = Math.floor(text.length * 0.52);
  let bestAt = -1;
  let bestDist = Infinity;

  for (const sep of seps) {
    let from = 0;
    while (true) {
      const idx = text.indexOf(sep, from);
      if (idx === -1) break;
      const after = idx + sep.length;
      if (after >= 6 && after <= text.length - 3) {
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

  // 구분자 없으면 공백 기준으로 midpoint에 가장 가까운 지점 분할 (KO·EN 모두)
  let bestSpace = -1;
  let bestSpaceDist = Infinity;
  for (let i = 4; i < text.length - 3; i++) {
    if (text[i] === " ") {
      const d = Math.abs(i - target);
      if (d < bestSpaceDist) { bestSpaceDist = d; bestSpace = i; }
    }
  }
  if (bestSpace > 0) {
    return [text.slice(0, bestSpace), text.slice(bestSpace + 1)];
  }

  return [text];
}

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const [notoSerifKrData, gothicA1Data, interData] = await Promise.all([
    notoSerifKrFont, gothicA1Font, interFont,
  ]);
  const ogFonts: { name: string; data: ArrayBuffer; weight: 100|200|300|400|500|600|700|800|900; style: "normal" }[] = [];
  if (notoSerifKrData) ogFonts.push({ name: "Noto Serif KR", data: notoSerifKrData, weight: 900, style: "normal" });
  if (gothicA1Data)    ogFonts.push({ name: "Gothic A1",     data: gothicA1Data,    weight: 900, style: "normal" });
  if (interData)       ogFonts.push({ name: "Inter",          data: interData,        weight: 600, style: "normal" });

  const lang = req.nextUrl.searchParams.get("lang") === "en" ? "en" : "ko";

  // ── 이슈 데이터 fetch ──
  let issue: {
    title_ko?: string; title: string; severity: number;
    topic: string; event_count: number; country_code?: string;
    image_url?: string;
  } | null = null;

  try {
    const res = await fetch(`${API_BASE}/issues/${params.id}`, {
      next: { revalidate: 120 },
      signal: AbortSignal.timeout(10000),
    });
    if (res.ok) issue = await res.json();
    else console.error(`[OG] issue ${params.id} → ${res.status}`);
  } catch (e) {
    console.error(`[OG] fetch error:`, e instanceof Error ? e.message : e);
  }

  // ── 데이터 없으면 브랜드 플레이스홀더 ──
  if (!issue) {
    return new ImageResponse(
      (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center",
          width: "100%", height: "100%", background: "#0d0d0d" }}>
          <span style={{ color: "rgba(255,255,255,0.4)", fontSize: 32, fontWeight: 600,
            fontFamily: "'Inter', sans-serif", letterSpacing: "4px" }}>
            WEWANTPEACE
          </span>
        </div>
      ),
      { ...size, fonts: ogFonts }
    );
  }

  // ── 공통 변수 ──
  const rawTitle    = lang === "en" ? (issue.title || issue.title_ko || "") : (issue.title_ko || issue.title || "");
  const headline    = cleanTitle(rawTitle, lang);
  const lines       = splitHeadline(headline, lang);
  const config      = getConfig(issue.severity);
  const topicLabel  = (TOPIC[issue.topic] || TOPIC.unknown)[lang];
  const cn          = issue.country_code ? COUNTRY_NAMES[issue.country_code] : null;
  const countryName = cn ? cn[lang] : (issue.country_code ?? "");
  const displayFont = lang === "en" ? "'Noto Serif KR', serif" : "'Gothic A1', sans-serif";
  const uiFont      = "'Inter', sans-serif";
  const metaLine    = [countryName, topicLabel].filter(Boolean).join("  ·  ");
  const reportsText = lang === "en" ? `${issue.event_count} Reports` : `보도 ${issue.event_count}건`;
  const sevLevelText = lang === "en" ? config.label.toUpperCase() : config.labelKo;

  // ── 배경 이미지 fetch (풀블리드용: 1200×630) ──
  const MAX_IMAGE_BYTES = 800_000;
  let bgImageSrc: string | null = null;
  if (issue.image_url) {
    try {
      // q=75 먼저 시도, 800KB 초과 시 q=55로 재시도
      for (const q of [75, 55]) {
        const fetchUrl = `https://wsrv.nl/?url=${encodeURIComponent(issue.image_url)}&output=jpg&q=${q}&w=1200&h=630&fit=cover`;
        const imgRes = await fetch(fetchUrl, { signal: AbortSignal.timeout(5000) });
        if (!imgRes.ok) break;
        const buf = await imgRes.arrayBuffer();
        if (buf.byteLength <= MAX_IMAGE_BYTES) {
          bgImageSrc = `data:image/jpeg;base64,${Buffer.from(buf).toString("base64")}`;
          break;
        }
      }
    } catch {}
  }

  // ══════════════════════════════════════════════════════════
  // LAYOUT A: 이미지 있음 — 풀블리드 + 그라디언트 오버레이
  // ══════════════════════════════════════════════════════════
  if (bgImageSrc) {
    // 각 줄 글자수에 맞게 폰트 크기 자동 계산
    // line1 (흰색 컨텍스트): max 88px, min 50px
    // line2 (severity 컬러 핵심): max 100px, min 56px — 항상 line1보다 크게
    const line1Size = fitFontSize(lines[0], lang, IMAGE_CONTENT_W, 88, 50);
    const line2Size = lines[1]
      ? fitFontSize(lines[1], lang, IMAGE_CONTENT_W, 100, 56)
      : line1Size;

    return new ImageResponse(
      (
        <div style={{ display: "flex", width: "100%", height: "100%", position: "relative", fontFamily: uiFont }}>

          {/* ── 풀블리드 사진 ── */}
          <img
            src={bgImageSrc}
            style={{
              position: "absolute", top: 0, left: 0,
              width: "100%", height: "100%",
              objectFit: "cover",
            }}
            alt=""
          />

          {/* ── 상단 그라디언트 (브랜드 배지 가독성) ── */}
          <div style={{
            display: "flex",
            position: "absolute", top: 0, left: 0, right: 0, height: 260,
            background: "linear-gradient(to bottom, rgba(0,0,0,0.82) 0%, rgba(0,0,0,0.2) 65%, transparent 100%)",
          }} />

          {/* ── 하단 그라디언트 (텍스트 가독성) ── */}
          <div style={{
            display: "flex",
            position: "absolute", bottom: 0, left: 0, right: 0, height: 500,
            background: "linear-gradient(to top, rgba(0,0,0,0.97) 0%, rgba(0,0,0,0.91) 30%, rgba(0,0,0,0.65) 55%, transparent 100%)",
          }} />

          {/* ── 좌측 severity 컬러 스트라이프 ── */}
          <div style={{
            display: "flex",
            position: "absolute", top: 0, left: 0, width: 6, height: 630,
            background: config.color,
          }} />

          {/* ── 상단 행: 브랜드 · severity 배지 ── */}
          <div style={{
            display: "flex",
            position: "absolute", top: 0, left: 0, right: 0,
            padding: "36px 54px",
            justifyContent: "space-between", alignItems: "center",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                display: "flex", width: 10, height: 10,
                borderRadius: 5, background: config.color,
              }} />
              <span style={{
                color: "rgba(255,255,255,0.62)", fontSize: 14,
                fontWeight: 700, letterSpacing: "3.5px",
              }}>
                WEWANTPEACE
              </span>
            </div>
            <div style={{
              display: "flex",
              background: config.bg, color: "#fff",
              fontSize: 12, fontWeight: 700, letterSpacing: "3px",
              padding: "8px 22px", borderRadius: 2,
            }}>
              {sevLevelText}
            </div>
          </div>

          {/* ── 하단 텍스트 블록 ── */}
          <div style={{
            display: "flex", flexDirection: "column",
            position: "absolute", bottom: 0, left: 0, right: 0,
            padding: `0 60px 44px 62px`,
          }}>
            {/* 메타 라인 */}
            {metaLine ? (
              <span style={{
                color: "rgba(255,255,255,0.4)", fontSize: 22,
                fontWeight: 600, letterSpacing: "2px", marginBottom: 14,
              }}>
                {metaLine}
              </span>
            ) : null}

            {/* 헤드라인 줄 1 — 흰색 */}
            <span style={{
              fontFamily: displayFont, fontWeight: 900,
              fontSize: line1Size, lineHeight: 1.06,
              color: "#fff",
              letterSpacing: lang === "en" ? "-1px" : "-1.5px",
            }}>
              {lines[0]}
            </span>

            {/* 헤드라인 줄 2 — severity 컬러 강조 */}
            {lines[1] ? (
              <span style={{
                fontFamily: displayFont, fontWeight: 900,
                fontSize: line2Size, lineHeight: 1.06,
                color: config.color,
                letterSpacing: lang === "en" ? "-1.5px" : "-2px",
              }}>
                {lines[1]}
              </span>
            ) : null}

            {/* 보도 건수 + 도메인 */}
            <div style={{ display: "flex", alignItems: "center", gap: 18, marginTop: 20 }}>
              <span style={{ color: "rgba(255,255,255,0.35)", fontSize: 19, fontWeight: 600 }}>
                {reportsText}
              </span>
              <span style={{ color: "rgba(255,255,255,0.14)", fontSize: 18 }}>|</span>
              <span style={{ color: "rgba(255,255,255,0.22)", fontSize: 18 }}>
                wewantpeace.live
              </span>
            </div>
          </div>
        </div>
      ),
      {
        ...size,
        fonts: ogFonts,
        headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=120" },
      }
    );
  }

  // ══════════════════════════════════════════════════════════
  // LAYOUT B: 이미지 없음 — 크림 에디토리얼 폴백
  // ══════════════════════════════════════════════════════════

  // 에디토리얼도 동일하게 글자수 기반 폰트 크기 계산
  const editLine1Size = fitFontSize(lines[0], lang, EDITORIAL_CONTENT_W, 92, 52);
  const editLine2Size = lines[1]
    ? fitFontSize(lines[1], lang, EDITORIAL_CONTENT_W, 104, 58)
    : editLine1Size;

  return new ImageResponse(
    (
      <div style={{
        display: "flex", width: "100%", height: "100%",
        background: "#f5f0e6", fontFamily: uiFont, position: "relative",
      }}>
        {/* 좌측 Severity 스트라이프 */}
        <div style={{
          display: "flex", position: "absolute",
          left: 0, top: 0, width: 7, height: 630,
          background: config.bg,
        }} />

        {/* 워터마크 숫자 — 우하단 */}
        <div style={{
          display: "flex", position: "absolute",
          right: -10, bottom: -50,
          fontFamily: displayFont, fontWeight: 900,
          fontSize: 400, lineHeight: 1,
          color: "rgba(0,0,0,0.038)",
          letterSpacing: "-20px",
        }}>
          {issue.severity}
        </div>

        {/* 콘텐츠 레이어 */}
        <div style={{
          display: "flex", flexDirection: "column",
          height: "100%", padding: "48px 76px 44px 80px",
          position: "relative",
        }}>
          {/* 상단 메타 */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              display: "flex", alignItems: "center",
              background: config.bg, color: "#fff",
              fontSize: 11, fontWeight: 700, letterSpacing: "3px",
              padding: "7px 18px", borderRadius: 2,
            }}>
              {lang === "en" ? config.label.toUpperCase() : config.labelKo}
            </div>
            {countryName ? (
              <>
                <span style={{ color: "rgba(0,0,0,0.2)", fontSize: 18 }}>·</span>
                <span style={{ color: "rgba(0,0,0,0.45)", fontSize: 15, fontWeight: 600 }}>
                  {countryName}
                </span>
              </>
            ) : null}
            <span style={{ color: "rgba(0,0,0,0.2)", fontSize: 18 }}>·</span>
            <span style={{ color: "rgba(0,0,0,0.45)", fontSize: 15, fontWeight: 600 }}>
              {topicLabel}
            </span>
            <span style={{ color: "rgba(0,0,0,0.2)", fontSize: 18 }}>·</span>
            <span style={{ color: "rgba(0,0,0,0.45)", fontSize: 15, fontWeight: 600 }}>
              {reportsText}
            </span>
          </div>

          {/* 헤드라인 존 (상·하 룰 사이) */}
          <div style={{
            display: "flex", flexDirection: "column",
            flex: 1, justifyContent: "center",
          }}>
            <div style={{ display: "flex", height: 2, background: "rgba(0,0,0,0.1)", marginBottom: 28 }} />

            <div style={{ display: "flex", flexDirection: "column" }}>
              <span style={{
                fontFamily: displayFont, fontWeight: 900,
                fontSize: editLine1Size, lineHeight: 1.07,
                color: "#0d0d0d",
                letterSpacing: lang === "en" ? "-1.5px" : "-2px",
              }}>
                {lines[0]}
              </span>
              {lines[1] ? (
                <span style={{
                  fontFamily: displayFont, fontWeight: 900,
                  fontSize: editLine2Size, lineHeight: 1.07,
                  color: "rgba(0,0,0,0.36)",
                  letterSpacing: lang === "en" ? "-1.5px" : "-2px",
                }}>
                  {lines[1]}
                </span>
              ) : null}
            </div>

            <div style={{ display: "flex", height: 2, background: "rgba(0,0,0,0.1)", marginTop: 28 }} />
          </div>

          {/* 하단 행 */}
          <div style={{
            display: "flex", alignItems: "center",
            justifyContent: "space-between",
          }}>
            <div style={{
              display: "flex", alignItems: "center",
              fontSize: 12, fontWeight: 700, letterSpacing: "2px",
              color: "rgba(0,0,0,0.34)",
              border: "1.5px solid rgba(0,0,0,0.14)",
              padding: "7px 16px", borderRadius: 2,
            }}>
              {topicLabel.toUpperCase()}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                <span style={{
                  fontFamily: displayFont, fontWeight: 900,
                  fontSize: 66, lineHeight: 1, letterSpacing: "-2px",
                  color: config.bg,
                }}>
                  {issue.severity}
                </span>
                <span style={{
                  fontSize: 11, fontWeight: 600, letterSpacing: "2px",
                  color: "rgba(0,0,0,0.28)", paddingBottom: 9,
                }}>
                  {lang === "en" ? "SEVERITY" : "위기지수"}
                </span>
              </div>
              <span style={{ fontSize: 13, fontWeight: 600, color: "rgba(0,0,0,0.22)", letterSpacing: "0.5px" }}>
                wewantpeace.live
              </span>
            </div>
          </div>
        </div>
      </div>
    ),
    {
      ...size,
      fonts: ogFonts,
      headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=120" },
    }
  );
}

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
 * 헤드라인을 2줄로 분할.
 * 좁아진 콘텐츠 패널(~548px)에 맞춰 임계값 조정.
 */
function splitHeadline(text: string, lang: string = "ko"): string[] {
  // 분할이 필요없을 정도로 짧으면 단일 줄
  const singleLineMax = lang === "en" ? 22 : 11;
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

  // 영어: 구분자 없으면 단어 경계
  if (lang === "en") {
    const sp = text.lastIndexOf(" ", target);
    if (sp >= 6 && sp <= text.length - 3) {
      return [text.slice(0, sp), text.slice(sp + 1)];
    }
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
  const rawTitle   = lang === "en" ? (issue.title || issue.title_ko || "") : (issue.title_ko || issue.title || "");
  const headline   = cleanTitle(rawTitle, lang);
  const lines      = splitHeadline(headline, lang);
  const config     = getConfig(issue.severity);
  const topicLabel = (TOPIC[issue.topic] || TOPIC.unknown)[lang];
  const cn         = issue.country_code ? COUNTRY_NAMES[issue.country_code] : null;
  const countryName = cn ? cn[lang] : (issue.country_code ?? "");
  const displayFont = lang === "en" ? "'Noto Serif KR', serif" : "'Gothic A1', sans-serif";
  const uiFont      = "'Inter', sans-serif";

  // 콘텐츠 패널 너비: 650px, 패딩 좌48+우52 = 내용 너비 ~550px
  // Gothic A1 Black 기준 KO 1자 ≈ 0.95em, EN 1자 ≈ 0.55em
  const titleSize = lang === "en"
    ? (headline.length <= 12 ? 54 : headline.length <= 20 ? 46 : headline.length <= 30 ? 40 : 34)
    : (headline.length <= 8  ? 56 : headline.length <= 13 ? 48 : headline.length <= 19 ? 42 : 36);

  // ── 배경 이미지 (Base64) — wsrv.nl로 JPEG 변환 + 사이즈 최적화 ──
  const MAX_IMAGE_BYTES = 800_000;
  let bgImageSrc: string | null = null;
  if (issue.image_url) {
    try {
      const fetchUrl = `https://wsrv.nl/?url=${encodeURIComponent(issue.image_url)}&output=jpg&q=82&w=560&h=630&fit=cover`;
      const imgRes = await fetch(fetchUrl, { signal: AbortSignal.timeout(5000) });
      if (imgRes.ok) {
        const buf = await imgRes.arrayBuffer();
        if (buf.byteLength <= MAX_IMAGE_BYTES) {
          bgImageSrc = `data:image/jpeg;base64,${Buffer.from(buf).toString("base64")}`;
        }
      }
    } catch {}
  }

  const metaLine = [countryName, topicLabel].filter(Boolean).join("  ·  ");
  const reportsText = lang === "en" ? `${issue.event_count} Reports` : `보도 ${issue.event_count}건`;
  const sevLabelText = lang === "en" ? "SEVERITY" : "위기지수";
  const sevLevelText = lang === "en" ? config.label.toUpperCase() : config.labelKo;

  // ══════════════════════════════════════════════════════════
  // LAYOUT A: 이미지 있음 — 하드 스플릿 (콘텐츠 좌 / 사진 우)
  // ══════════════════════════════════════════════════════════
  if (bgImageSrc) {
    return new ImageResponse(
      (
        <div style={{ display: "flex", width: "100%", height: "100%", fontFamily: uiFont }}>

          {/* ── 좌: 콘텐츠 패널 (650px) ── */}
          <div style={{
            display: "flex", flexDirection: "column",
            width: 650, height: 630,
            background: "#0d0d0d",
            position: "relative",
            flexShrink: 0,
          }}>
            {/* Severity 상단 3px 엣지 */}
            <div style={{
              display: "flex", position: "absolute", top: 0, left: 0,
              width: 650, height: 3, background: config.color,
            }} />

            {/* 내부 레이아웃 */}
            <div style={{
              display: "flex", flexDirection: "column",
              height: "100%", padding: "46px 52px 44px 48px",
            }}>
              {/* 상단: 브랜드 · Severity 레이블 */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <div style={{
                    display: "flex", width: 8, height: 8,
                    borderRadius: 4, background: config.color,
                  }} />
                  <span style={{
                    color: "rgba(255,255,255,0.28)", fontSize: 12,
                    fontWeight: 600, letterSpacing: "2.5px",
                  }}>
                    WEWANTPEACE
                  </span>
                </div>
                <span style={{
                  color: config.color, fontSize: 11,
                  fontWeight: 600, letterSpacing: "3px",
                }}>
                  {sevLevelText}
                </span>
              </div>

              {/* 중앙: 메타 + 헤드라인 */}
              <div style={{
                display: "flex", flexDirection: "column",
                flex: 1, justifyContent: "center", gap: 16,
              }}>
                {metaLine ? (
                  <span style={{
                    color: "rgba(255,255,255,0.25)", fontSize: 12,
                    fontWeight: 600, letterSpacing: "2px",
                  }}>
                    {metaLine}
                  </span>
                ) : null}

                <div style={{
                  display: "flex", flexDirection: "column",
                  fontFamily: displayFont, fontWeight: 900,
                  fontSize: titleSize, lineHeight: 1.18,
                  letterSpacing: lang === "en" ? "-0.5px" : "-1px",
                }}>
                  <span style={{ color: "#fff" }}>{lines[0]}</span>
                  {lines[1] ? (
                    <span style={{ color: "rgba(255,255,255,0.52)" }}>{lines[1]}</span>
                  ) : null}
                </div>
              </div>

              {/* 하단: 구분선 + 지표 */}
              <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
                <div style={{ display: "flex", height: 1, background: "rgba(255,255,255,0.09)" }} />
                <div style={{
                  display: "flex", alignItems: "flex-end",
                  justifyContent: "space-between",
                }}>
                  {/* 위기지수 숫자 */}
                  <div style={{ display: "flex", alignItems: "baseline", gap: 9 }}>
                    <span style={{
                      fontFamily: displayFont, fontWeight: 900,
                      fontSize: 82, lineHeight: 1, letterSpacing: "-3px",
                      color: config.color,
                    }}>
                      {issue.severity}
                    </span>
                    <span style={{
                      fontSize: 11, fontWeight: 600, letterSpacing: "2.5px",
                      color: "rgba(255,255,255,0.22)",
                      paddingBottom: 12,
                    }}>
                      {sevLabelText}
                    </span>
                  </div>

                  {/* 보도 건수 + 도메인 */}
                  <div style={{
                    display: "flex", flexDirection: "column",
                    alignItems: "flex-end", gap: 5, paddingBottom: 5,
                  }}>
                    <span style={{ fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.38)" }}>
                      {reportsText}
                    </span>
                    <span style={{ fontSize: 12, color: "rgba(255,255,255,0.17)" }}>
                      wewantpeace.live
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ── 수직 구분선 (1px) ── */}
          <div style={{
            display: "flex", width: 1, height: 630,
            background: "rgba(255,255,255,0.08)", flexShrink: 0,
          }} />

          {/* ── 우: 뉴스 사진 (549px) — 거의 원본 밝기 ── */}
          <div style={{ display: "flex", flex: 1, height: 630, overflow: "hidden" }}>
            <img
              src={bgImageSrc}
              width={549}
              height={630}
              style={{ objectFit: "cover", filter: "brightness(0.9) saturate(0.92)" }}
              alt=""
            />
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

  // 에디토리얼 폴백 헤드라인은 더 넓은 공간(1132px) 사용 → 폰트 크게
  const editorialTitleSize = lang === "en"
    ? (headline.length <= 18 ? 66 : headline.length <= 28 ? 58 : headline.length <= 38 ? 50 : 42)
    : (headline.length <= 10 ? 72 : headline.length <= 16 ? 64 : headline.length <= 24 ? 56 : 46);

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
          color: "rgba(0,0,0,0.048)",
          letterSpacing: "-20px",
        }}>
          {issue.severity}
        </div>

        {/* 콘텐츠 레이어 */}
        <div style={{
          display: "flex", flexDirection: "column",
          height: "100%", padding: "48px 68px 44px 72px",
          position: "relative",
        }}>
          {/* 상단 메타 */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            {/* Severity 필 */}
            <div style={{
              display: "flex", alignItems: "center",
              background: config.bg, color: "#fff",
              fontSize: 10, fontWeight: 600, letterSpacing: "3px",
              padding: "5px 14px", borderRadius: 1,
            }}>
              {config.label.toUpperCase()}
            </div>
            {countryName ? (
              <>
                <span style={{ color: "rgba(0,0,0,0.2)", fontSize: 15 }}>·</span>
                <span style={{ color: "rgba(0,0,0,0.38)", fontSize: 13, fontWeight: 600 }}>
                  {countryName}
                </span>
              </>
            ) : null}
            <span style={{ color: "rgba(0,0,0,0.2)", fontSize: 15 }}>·</span>
            <span style={{ color: "rgba(0,0,0,0.38)", fontSize: 13, fontWeight: 600 }}>
              {topicLabel}
            </span>
            <span style={{ color: "rgba(0,0,0,0.2)", fontSize: 15 }}>·</span>
            <span style={{ color: "rgba(0,0,0,0.38)", fontSize: 13, fontWeight: 600 }}>
              {reportsText}
            </span>
          </div>

          {/* 헤드라인 존 (상·하 룰 사이) */}
          <div style={{
            display: "flex", flexDirection: "column",
            flex: 1, justifyContent: "center",
          }}>
            {/* 상단 룰 */}
            <div style={{ display: "flex", height: 1.5, background: "rgba(0,0,0,0.11)", marginBottom: 28 }} />

            <div style={{
              display: "flex", flexDirection: "column",
              fontFamily: displayFont, fontWeight: 900,
              fontSize: editorialTitleSize, lineHeight: 1.08,
              letterSpacing: lang === "en" ? "-1.5px" : "-2px",
              wordBreak: "keep-all",
            }}>
              <span style={{ color: "#0d0d0d" }}>{lines[0]}</span>
              {lines[1] ? (
                <span style={{ color: "rgba(0,0,0,0.42)" }}>{lines[1]}</span>
              ) : null}
            </div>

            {/* 하단 룰 */}
            <div style={{ display: "flex", height: 1.5, background: "rgba(0,0,0,0.11)", marginTop: 28 }} />
          </div>

          {/* 하단 행 */}
          <div style={{
            display: "flex", alignItems: "center",
            justifyContent: "space-between",
          }}>
            {/* 토픽 칩 */}
            <div style={{
              display: "flex", alignItems: "center",
              fontSize: 11, fontWeight: 600, letterSpacing: "2px",
              color: "rgba(0,0,0,0.35)",
              border: "1px solid rgba(0,0,0,0.12)",
              padding: "5px 13px", borderRadius: 1,
            }}>
              {topicLabel.toUpperCase()}
            </div>

            {/* 위기지수 + 도메인 */}
            <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 7 }}>
                <span style={{
                  fontFamily: displayFont, fontWeight: 900,
                  fontSize: 60, lineHeight: 1, letterSpacing: "-2px",
                  color: config.bg,
                }}>
                  {issue.severity}
                </span>
                <span style={{
                  fontSize: 10, fontWeight: 600, letterSpacing: "2px",
                  color: "rgba(0,0,0,0.28)", paddingBottom: 9,
                }}>
                  {sevLabelText}
                </span>
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: "rgba(0,0,0,0.22)", letterSpacing: "0.5px" }}>
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

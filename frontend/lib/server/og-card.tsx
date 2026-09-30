/**
 * 링크 미리보기(OG) 카드 — 1200×630, 영어.
 *
 * 2026-09-30 리디자인. 스레드 카드뉴스 표지(worker/social/brief_card.py, 사장님 합격)와 같은 결:
 * 기사 사진 전면 + 아래로 어두워지는 막 + 나라·날짜 칩 + "N sources" 칩 + 굵은 흰 헤드라인(나라 이름 노랑).
 * 예전 카드는 기본이 한국어(?lang=en 이 있어야 영어)였고, 스레드 링크에 lang 이 없어
 * 영어 사용자가 한국어 미리보기를 봤다. 이제 미리보기는 항상 영어.
 */
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const OG_SIZE = { width: 1200, height: 630 };
export const ACCENT = "#FFD23F";
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const FONT_DIR = join(process.cwd(), "public", "fonts");

function load(name: string): Promise<ArrayBuffer | null> {
  return readFile(join(FONT_DIR, name))
    .then((buf) => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer)
    .catch((): null => null);
}

// 사진이 없을 때 배경 — 사이트 공통 미리보기와 같은 점 세계지도 (public/og-fallback-bg.jpg)
const fallbackBg = readFile(join(process.cwd(), "public", "og-fallback-bg.jpg"))
  .then((buf) => `data:image/jpeg;base64,${buf.toString("base64")}`)
  .catch((): null => null);

export async function fallbackPhoto(): Promise<{ src: string; credit: string } | null> {
  const src = await fallbackBg;
  return src ? { src, credit: "" } : null;
}

// 모듈 로드 시 한 번 읽는다 (self-fetch 데드락 방지로 파일에서 직접)
const fontFiles = Promise.all([
  load("Inter-Black.ttf"), load("Inter-ExtraBold.ttf"), load("Inter-SemiBold.ttf"),
]);

type Weight = 600 | 800 | 900;
export async function ogFonts() {
  const [black, extra, semi] = await fontFiles;
  const out: { name: string; data: ArrayBuffer; weight: Weight; style: "normal" }[] = [];
  if (black) out.push({ name: "Inter", data: black, weight: 900, style: "normal" });
  if (extra) out.push({ name: "Inter", data: extra, weight: 800, style: "normal" });
  if (semi) out.push({ name: "Inter", data: semi, weight: 600, style: "normal" });
  return out;
}

export const COUNTRY_EN: Record<string, string> = {
  UA: "Ukraine", RU: "Russia", CN: "China", US: "United States", KR: "South Korea", KP: "North Korea",
  JP: "Japan", TW: "Taiwan", IL: "Israel", PS: "Palestine", IR: "Iran", SY: "Syria", MM: "Myanmar",
  AF: "Afghanistan", SD: "Sudan", YE: "Yemen", ET: "Ethiopia", SO: "Somalia", LB: "Lebanon", IQ: "Iraq",
  PK: "Pakistan", ML: "Mali", DE: "Germany", IN: "India", TR: "Turkey", SA: "Saudi Arabia", EG: "Egypt",
  LY: "Libya", VE: "Venezuela", HT: "Haiti", GB: "United Kingdom", FR: "France", AE: "UAE", QA: "Qatar",
  NG: "Nigeria", CD: "DR Congo", MX: "Mexico", BR: "Brazil", CU: "Cuba", AZ: "Azerbaijan", AM: "Armenia",
  GE: "Georgia", BY: "Belarus", PL: "Poland", SS: "South Sudan", BF: "Burkina Faso", NE: "Niger",
};

export function countryName(cc?: string | null): string {
  if (!cc) return "";
  const up = cc.toUpperCase();
  if (COUNTRY_EN[up]) return COUNTRY_EN[up];
  try {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(up) || up;
  } catch {
    return up;
  }
}

/** "Palestine Conflict" 같은 자동 템플릿 제목 — 미리보기 헤드라인으로 쓰지 않는다 */
export function isTemplateTitle(t?: string | null): boolean {
  const s = (t || "").trim();
  return s.split(/\s+/).length <= 3;
}

export function cleanHeadline(raw: string, max = 96): string {
  let s = (raw || "").replace(/\s+/g, " ").replace(/^(BREAKING|UPDATE|WATCH|LIVE)\s*[:\-–]\s*/i, "").trim();
  s = s.replace(/[.\s]+$/, "");
  if (s.length <= max) return s;
  const cut = s.slice(0, max);
  return cut.slice(0, cut.lastIndexOf(" ")).replace(/[,;:]$/, "") + "…";
}

type Ev = { image_url?: string | null; source_tier?: string | null; source_name?: string | null; title?: string | null };

// 기사 사진이 아닌 매체 로고·기본 공유 이미지 (배포 직후 실측: TASS 가 모든 기사에 로고 PNG 를 붙인다)
const JUNK_IMG = /logo|placeholder|default[-_]?(image|share|og)|share[-_]?(image|img|default)|icon|avatar|sprite|whatsapp|blank|no[-_]?image/i;

const STOP = new Set(["with", "from", "after", "over", "into", "that", "this", "their", "have", "were", "said",
  "says", "amid", "against", "about", "more", "than", "they", "what", "when", "will", "been"]);
function words(t?: string | null): Set<string> {
  return new Set((t || "").toLowerCase().match(/[\p{L}]{4,}/gu)?.filter((w) => !STOP.has(w)) ?? []);
}

/** 기사 사진 후보 — 헤드라인과 제목이 겹치는 기사 사진부터, 같으면 믿을 만한 출처(A/B)부터.
 *  한 이슈에 다른 사건 기사가 섞여 있어(팔레스타인 이슈에 이란 미사일 사진) 출처 등급만으로 고르면 엉뚱한 사진이 나왔다.
 *  미검증(D) 채널 사진과 로고 이미지는 쓰지 않는다. */
export function photoCandidates(events: Ev[], fallback?: string | null, headline?: string): { url: string; credit: string }[] {
  const rank: Record<string, number> = { A: 0, B: 1, C: 2 };
  const hw = words(headline);
  const overlap = (e: Ev) => {
    let n = 0;
    words(e.title).forEach((w) => { if (hw.has(w)) n += 1; });
    return n;
  };
  // 같은 사진이 서로 다른 기사 3건 이상에 붙어 있으면 매체 피드의 공용 이미지다
  // (Middle East Eye 피드가 이란 미사일 사진 한 장을 여러 기사에 붙여, 팔레스타인 정착민 기사 미리보기에 나왔다)
  const titlesByImg = new Map<string, Set<string>>();
  events.forEach((e) => {
    if (!e.image_url) return;
    const set = titlesByImg.get(e.image_url) ?? new Set<string>();
    set.add((e.title || "").slice(0, 60));
    titlesByImg.set(e.image_url, set);
  });
  const shared = (u: string) => (titlesByImg.get(u)?.size ?? 0) >= 3;
  const seen = new Set<string>();
  const out: { url: string; credit: string }[] = [];
  [...events]
    .filter((e) => e.image_url && (e.source_tier || "D") !== "D" && !JUNK_IMG.test(e.image_url) && !shared(e.image_url))
    // 같은 사건(겹치는 단어 2개 이상)인지 먼저, 그 안에서는 출처 등급 먼저.
    // 겹침 수만으로 고르면 제목이 똑같은 B등급 기사의 잘못 붙은 피드 사진(MEE: 정착민 기사에 이란 광고판)이 뽑혔다.
    .sort((a, b) => {
      const bucket = (e: Ev) => (overlap(e) >= 2 ? 0 : overlap(e) === 1 ? 1 : 2);
      return (bucket(a) - bucket(b))
        || ((rank[a.source_tier || ""] ?? 3) - (rank[b.source_tier || ""] ?? 3))
        || (overlap(b) - overlap(a));
    })
    .forEach((e) => {
      const u = e.image_url as string;
      if (u.startsWith("http") && !seen.has(u)) {
        seen.add(u);
        out.push({ url: u, credit: e.source_name || "" });
      }
    });
  if (fallback && fallback.startsWith("http") && !seen.has(fallback) && !JUNK_IMG.test(fallback)) {
    out.push({ url: fallback, credit: "" });
  }
  return out;
}

export function sourceCount(events: Ev[]): number {
  return new Set(events.filter((e) => (e.source_tier || "D") !== "D" && e.source_name).map((e) => e.source_name)).size;
}

/** 사진을 받아 data URL 로. satori 는 jpeg/png 만 안정적이라 그 외 형식·실패·작은 이미지는 건너뛴다 */
export async function loadPhoto(cands: { url: string; credit: string }[]): Promise<{ src: string; credit: string } | null> {
  for (const c of cands.slice(0, 5)) {
    try {
      const res = await fetch(c.url, {
        signal: AbortSignal.timeout(6000),
        headers: {
          "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
          Accept: "image/jpeg,image/png,image/*;q=0.8",
        },
      });
      const type = (res.headers.get("content-type") || "").split(";")[0];
      if (!res.ok || !/^image\/(jpeg|jpg|png)$/.test(type)) continue;
      const buf = Buffer.from(await res.arrayBuffer());
      if (buf.length < 12000 || buf.length > 6_000_000) continue;
      return { src: `data:${type};base64,${buf.toString("base64")}`, credit: c.credit };
    } catch {
      /* 다음 후보 */
    }
  }
  return null;
}

function headlinePx(t: string): number {
  if (t.length <= 42) return 76;
  if (t.length <= 64) return 64;
  return 54;
}

/** 헤드라인을 단어 단위로 쪼개 강조어(나라 이름 등)만 노랑으로 — satori 는 인라인 서식을 단어 span 으로 처리 */
function Headline({ text, highlight }: { text: string; highlight?: string }) {
  const words = text.split(" ");
  const hl = (highlight || "").toLowerCase().split(" ").filter(Boolean);
  let start = -1;
  if (hl.length) {
    for (let i = 0; i <= words.length - hl.length; i++) {
      const slice = words.slice(i, i + hl.length).map((w) => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, ""));
      if (slice.join(" ") === hl.map((w) => w.replace(/[^\p{L}\p{N}]/gu, "")).join(" ")) {
        start = i;
        break;
      }
    }
  }
  const px = headlinePx(text);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", fontSize: px, fontWeight: 900, lineHeight: 1.04,
      letterSpacing: "-0.025em", color: "#fff", maxWidth: 1080 }}>
      {words.map((w, i) => (
        <span key={i} style={{ marginRight: px * 0.24,
          color: start >= 0 && i >= start && i < start + hl.length ? ACCENT : "#fff" }}>{w}</span>
      ))}
    </div>
  );
}

export function CoverCard(props: {
  headline: string;
  highlight?: string;
  dek?: string;
  chips: { text: string; kind: "cc" | "src" }[];
  photo?: { src: string; credit: string } | null;
}) {
  const { headline, highlight, dek, chips, photo } = props;
  return (
    <div style={{ display: "flex", position: "relative", width: "100%", height: "100%", background: "#0c0d10",
      fontFamily: "Inter" }}>
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={photo.src} alt="" width={1200} height={630}
          style={{ position: "absolute", top: 0, left: 0, width: 1200, height: 630, objectFit: "cover" }} />
      ) : (
        <div style={{ position: "absolute", top: 0, left: 0, width: 1200, height: 630, display: "flex",
          backgroundImage: "radial-gradient(circle at 30% 20%, #2a2f38 0%, #101216 70%)" }} />
      )}
      <div style={{ position: "absolute", top: 0, left: 0, width: 1200, height: 630, display: "flex",
        backgroundImage: "linear-gradient(to bottom, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.05) 25%, rgba(0,0,0,0.25) 42%, rgba(0,0,0,0.85) 70%, rgba(0,0,0,0.94) 100%)" }} />
      {/* 머리글 */}
      <div style={{ position: "absolute", top: 40, left: 60, right: 60, display: "flex",
        justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 22, fontWeight: 900, letterSpacing: "0.08em", color: "#fff" }}>WEWANTPEACE</span>
        <span style={{ fontSize: 20, fontWeight: 600, color: "rgba(255,255,255,0.8)" }}>wewantpeace.live</span>
      </div>
      {/* 본문 */}
      <div style={{ position: "absolute", left: 60, right: 60, bottom: 66, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", marginBottom: 18 }}>
          {chips.filter((c) => c.text).map((c, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", marginRight: 12, padding: "7px 14px",
              borderRadius: 6, fontSize: 19, fontWeight: 800, letterSpacing: "0.06em", textTransform: "uppercase",
              background: c.kind === "src" ? "#fff" : "rgba(0,0,0,0.55)",
              color: c.kind === "src" ? "#111" : "#fff",
              border: c.kind === "src" ? "2px solid #fff" : "2px solid rgba(255,255,255,0.35)" }}>
              {c.kind === "cc" ? (
                <div style={{ width: 10, height: 10, borderRadius: 5, background: "#FF3B30", marginRight: 9 }} />
              ) : null}
              {c.text}
            </div>
          ))}
        </div>
        <Headline text={headline} highlight={highlight} />
        {dek ? (
          <div style={{ display: "flex", marginTop: 14, fontSize: 26, fontWeight: 600, lineHeight: 1.3,
            color: "rgba(255,255,255,0.88)" }}>{dek}</div>
        ) : null}
      </div>
      {photo?.credit ? (
        <div style={{ position: "absolute", left: 60, bottom: 26, display: "flex", fontSize: 15, fontWeight: 600,
          color: "rgba(255,255,255,0.6)" }}>{`Photo: ${photo.credit}`}</div>
      ) : null}
    </div>
  );
}

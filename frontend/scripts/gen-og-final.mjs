/**
 * 3개 폰트 × 2개 템플릿(Country/Issue) × 2개 언어 = 12개 OG 이미지
 * 실제 프로덕션 데이터 + 배경이미지 + 그래프 포함
 */
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { writeFileSync, mkdirSync } from "fs";

const W = 1200, H = 630;

const FONTS_META = {
  notoserif: {
    name: "Noto Serif KR",
    url: "https://fonts.gstatic.com/s/notoserifkr/v31/3JnoSDn90Gmq2mr3blnHaTZXbOtLJDvui3JOnchPf852.ttf",
    weight: 900,
    label: "Noto Serif KR Black",
  },
  hahmlet: {
    name: "Hahmlet",
    url: "https://fonts.gstatic.com/s/hahmlet/v21/BngXUXpCQ3nKpIo0TfPyfCdXfaeU4RjjP9jo.ttf",
    weight: 900,
    label: "Hahmlet Black",
  },
  gothica1: {
    name: "Gothic A1",
    url: "https://fonts.gstatic.com/s/gothica1/v18/CSR44z5ZnPydRjlCCwlC6OAKSA.ttf",
    weight: 900,
    label: "Gothic A1 Black",
  },
};

const INTER_URL = "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf";
const API = "https://api.wewantpeace.live";

async function fetchFont(url) { return (await fetch(url)).arrayBuffer(); }
async function fetchJson(url) { const r = await fetch(url); return r.ok ? r.json() : null; }
async function fetchImageBase64(url) {
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!r.ok) return null;
    const ct = r.headers.get("content-type") || "image/jpeg";
    const buf = await r.arrayBuffer();
    return `data:${ct};base64,${Buffer.from(buf).toString("base64")}`;
  } catch { return null; }
}

function buildSvgPath(points, width, height, key) {
  if (points.length < 2) return { path: "", area: "" };
  const max = Math.max(...points.map(p => p[key]), 1);
  const step = width / (points.length - 1);
  const pts = points.map((p, i) => ({
    x: Math.round(i * step),
    y: Math.round(height - (p[key] / max) * (height - 8)),
  }));
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const area = `${path} L${pts[pts.length - 1].x},${height} L${pts[0].x},${height} Z`;
  return { path, area, lastX: pts[pts.length - 1].x, lastY: pts[pts.length - 1].y };
}

// ── Country OG ──
function countryOG(fontName, lang, tension, history, bgSrc) {
  const isEn = lang === "en";
  const headline = isEn ? "Ukraine" : "우크라이나";
  const sub = isEn ? "우크라이나" : "Ukraine";
  const tagline = isEn ? "Real-time Global Conflict Monitor" : "실시간 글로벌 분쟁 모니터링";
  const levelLabel = isEn ? "Critical" : "위험";
  const trendLabel = isEn ? "7-Day Trend" : "7일 추이";
  const issuesLabel = isEn ? "Top Issues" : "주요 이슈";
  const score = tension.raw_score.toFixed(1);
  const barColor = "#EF4444";

  const topIssues = tension.top5_clusters.slice(0, 2).map((c, i) => {
    const t = isEn ? (c.title || c.title_ko || "") : (c.title_ko || c.title || "");
    return `${i+1}. ${t.length > 32 ? t.slice(0,32) + "…" : t}`;
  });

  // Downsample history to ~30 points
  const step = Math.max(1, Math.floor(history.length / 30));
  const sampled = history.filter((_, i) => i % step === 0 || i === history.length - 1);
  const gW = 420, gH = 110;
  const { path, area, lastX, lastY } = buildSvgPath(sampled, gW, gH, "raw_score");

  const dateStart = sampled.length > 0 ? new Date(sampled[0].time).toLocaleDateString(isEn ? "en-US" : "ko-KR", { month: "short", day: "numeric" }) : "";
  const dateEnd = sampled.length > 0 ? new Date(sampled[sampled.length-1].time).toLocaleDateString(isEn ? "en-US" : "ko-KR", { month: "short", day: "numeric" }) : "";

  const children = [];

  // BG image
  if (bgSrc) {
    children.push({ type: "img", props: { src: bgSrc, width: W, height: H, alt: "", style: { position: "absolute", top: 0, left: 0, width: W, height: H, objectFit: "cover", filter: "brightness(0.45) saturate(0.8)" } } });
  }

  // Accent line
  children.push({ type: "div", props: { style: { display: "flex", position: "absolute", top: 0, left: 0, width: "100%", height: "6px", background: `linear-gradient(90deg, transparent 0%, ${barColor} 30%, ${barColor} 70%, transparent 100%)` } } });

  // Main content
  children.push({ type: "div", props: { style: {
    display: "flex", flexDirection: "column", width: "100%", height: "100%", padding: "44px 56px 40px", position: "relative",
    background: bgSrc ? "linear-gradient(180deg, rgba(15,23,42,0.4) 0%, rgba(15,23,42,0.75) 40%, rgba(15,23,42,0.9) 100%)" : "transparent",
  }, children: [
    // Top bar
    { type: "div", props: { style: { display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
      { type: "span", props: { style: { color: "#94A3B8", fontSize: 28, fontWeight: 400 }, children: "WeWantPeace" } },
      { type: "div", props: { style: { display: "flex", alignItems: "center", gap: "12px" }, children: [
        { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 400 }, children: tagline } },
        { type: "div", props: { style: { display: "flex", background: "#DC2626", color: "#FFF", padding: "10px 26px", borderRadius: "24px", fontSize: 20, fontWeight: 400 }, children: levelLabel } },
      ] } },
    ] } },
    // Middle
    { type: "div", props: { style: { display: "flex", flex: 1, alignItems: "center", gap: "48px", marginTop: "20px" }, children: [
      // Left: headline + score
      { type: "div", props: { style: { display: "flex", flexDirection: "column", flex: 1, gap: "4px" }, children: [
        { type: "div", props: { style: { display: "flex", alignItems: "baseline", gap: "16px" }, children: [
          { type: "span", props: { style: { color: "#FFFFFF", fontSize: 72, fontWeight: 900, fontFamily: `'${fontName}', serif`, lineHeight: 1.1, letterSpacing: "-1px" }, children: headline } },
          { type: "span", props: { style: { color: "#94A3B8", fontSize: 28, fontWeight: 400 }, children: sub } },
        ] } },
        { type: "div", props: { style: { display: "flex", alignItems: "baseline", gap: "12px", marginTop: "16px" }, children: [
          { type: "span", props: { style: { color: barColor, fontSize: 88, fontWeight: 900, fontFamily: `'${fontName}', serif`, letterSpacing: "-3px", lineHeight: 1 }, children: score } },
          { type: "span", props: { style: { color: "#94A3B8", fontSize: 24, fontWeight: 400 }, children: "/ 100" } },
        ] } },
        { type: "span", props: { style: { color: "#94A3B8", fontSize: 22, fontWeight: 400, marginTop: "2px" }, children: "Tension Index" } },
        // Gauge
        { type: "div", props: { style: { display: "flex", width: "100%", maxWidth: "360px", height: "16px", background: "#1E293B", borderRadius: "6px", marginTop: "16px", overflow: "hidden", border: "1px solid #334155" }, children: [
          { type: "div", props: { style: { display: "flex", width: `${Math.min(parseFloat(score), 100)}%`, height: "100%", background: `linear-gradient(90deg, ${barColor}88, ${barColor})`, borderRadius: "6px" } } },
        ] } },
      ] } },
      // Right: graph + issues
      { type: "div", props: { style: { display: "flex", flexDirection: "column", width: "440px", gap: "8px" }, children: [
        { type: "span", props: { style: { color: "#94A3B8", fontSize: 18, fontWeight: 400 }, children: trendLabel } },
        // SVG graph
        ...(path ? [
          { type: "div", props: { style: { display: "flex", position: "relative", width: `${gW}px`, height: `${gH}px`, background: "rgba(15,23,42,0.6)", borderRadius: "12px", border: "1px solid #1E293B" }, children: [
            { type: "svg", props: { width: gW, height: gH, viewBox: `0 0 ${gW} ${gH}`, style: { position: "absolute", top: 0, left: 0 }, children: [
              { type: "defs", props: { children: [
                { type: "linearGradient", props: { id: "aG", x1: "0", y1: "0", x2: "0", y2: "1", children: [
                  { type: "stop", props: { offset: "0%", stopColor: barColor, stopOpacity: "0.3" } },
                  { type: "stop", props: { offset: "100%", stopColor: barColor, stopOpacity: "0.02" } },
                ] } },
              ] } },
              { type: "path", props: { d: area, fill: "url(#aG)" } },
              { type: "path", props: { d: path, fill: "none", stroke: barColor, strokeWidth: "3" } },
              { type: "circle", props: { cx: lastX, cy: lastY, r: "6", fill: barColor } },
            ] } },
          ] } },
          { type: "div", props: { style: { display: "flex", justifyContent: "space-between", width: `${gW}px` }, children: [
            { type: "span", props: { style: { color: "#64748B", fontSize: 14, fontWeight: 400 }, children: dateStart } },
            { type: "span", props: { style: { color: "#64748B", fontSize: 14, fontWeight: 400 }, children: dateEnd } },
          ] } },
        ] : []),
        { type: "span", props: { style: { color: "#64748B", fontSize: 16, fontWeight: 400, marginTop: "4px" }, children: issuesLabel } },
        ...topIssues.map(t => ({ type: "span", props: { style: { color: "#CBD5E1", fontSize: 17, fontWeight: 400 }, children: t } })),
      ] } },
    ] } },
    // Bottom
    { type: "div", props: { style: { display: "flex", justifyContent: "flex-end", marginTop: "auto" }, children: [
      { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 400 }, children: "wewantpeace.live" } },
    ] } },
  ] } });

  return { type: "div", props: { style: { display: "flex", width: "100%", height: "100%", fontFamily: "'Inter', sans-serif", background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)", position: "relative" }, children } };
}

// ── Issue OG ──
function issueOG(fontName, lang, issue, bgSrc) {
  const isEn = lang === "en";
  const rawTitle = isEn ? (issue.title || issue.title_ko) : (issue.title_ko || issue.title);
  const headline = rawTitle.replace(/[\u{1F000}-\u{1FFFF}]/gu, "").trim();
  const country = isEn ? "Israel" : "이스라엘";
  const topic = isEn ? "Armed Conflict" : "무장 충돌";
  const tagline = isEn ? "Real-time Global Conflict Monitor" : "실시간 글로벌 분쟁 모니터링";
  const sevLabel = isEn ? "Severity" : "위기지수";
  const srcLabel = isEn ? "Sources" : "보도 건수";
  const barColor = "#EF4444";
  const titleSize = headline.length <= 20 ? 52 : headline.length <= 35 ? 44 : 36;

  const children = [];
  if (bgSrc) {
    children.push({ type: "img", props: { src: bgSrc, width: W, height: H, alt: "", style: { position: "absolute", top: 0, left: 0, width: W, height: H, objectFit: "cover", filter: "brightness(0.45) saturate(0.8)" } } });
  }
  children.push({ type: "div", props: { style: { display: "flex", position: "absolute", top: 0, left: 0, width: "100%", height: "6px", background: `linear-gradient(90deg, transparent 0%, ${barColor} 30%, ${barColor} 70%, transparent 100%)` } } });

  children.push({ type: "div", props: { style: {
    display: "flex", flexDirection: "column", width: "100%", height: "100%", padding: "44px 56px 40px", position: "relative",
    background: bgSrc ? "linear-gradient(180deg, rgba(15,23,42,0.4) 0%, rgba(15,23,42,0.75) 40%, rgba(15,23,42,0.9) 100%)" : "transparent",
  }, children: [
    // Top
    { type: "div", props: { style: { display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
      { type: "span", props: { style: { color: "#94A3B8", fontSize: 28, fontWeight: 400 }, children: "WeWantPeace" } },
      { type: "div", props: { style: { display: "flex", alignItems: "center", gap: "12px" }, children: [
        { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 400 }, children: tagline } },
        { type: "div", props: { style: { display: "flex", background: "#DC2626", color: "#FFF", padding: "10px 26px", borderRadius: "24px", fontSize: 20, fontWeight: 400 }, children: "Critical" } },
      ] } },
    ] } },
    // Middle
    { type: "div", props: { style: { display: "flex", flex: 1, marginTop: "24px", alignItems: "center" }, children: [
      { type: "div", props: { style: { display: "flex", flexDirection: "column", flex: 1, gap: "12px" }, children: [
        // Badges
        { type: "div", props: { style: { display: "flex", gap: "10px" }, children: [
          { type: "span", props: { style: { background: "rgba(30,41,59,0.8)", color: "#E2E8F0", padding: "8px 18px", borderRadius: "16px", fontSize: 18, fontWeight: 400, border: "1px solid #334155" }, children: country } },
          { type: "span", props: { style: { background: "rgba(30,41,59,0.8)", color: "#E2E8F0", padding: "8px 18px", borderRadius: "16px", fontSize: 18, fontWeight: 400, border: "1px solid #334155" }, children: topic } },
        ] } },
        // Headline
        { type: "div", props: { style: { display: "flex", color: "#FFFFFF", fontSize: titleSize, fontWeight: 900, fontFamily: `'${fontName}', serif`, lineHeight: 1.35, letterSpacing: "-0.5px", wordBreak: "keep-all", overflowWrap: "break-word", maxWidth: "700px" }, children: headline } },
        // Metrics
        { type: "div", props: { style: { display: "flex", alignItems: "center", gap: "28px", marginTop: "12px" }, children: [
          { type: "div", props: { style: { display: "flex", flexDirection: "column", gap: "2px" }, children: [
            { type: "span", props: { style: { color: barColor, fontSize: 44, fontWeight: 900, fontFamily: `'${fontName}', serif`, lineHeight: 1 }, children: String(issue.severity) } },
            { type: "span", props: { style: { color: "#94A3B8", fontSize: 16, fontWeight: 400 }, children: sevLabel } },
          ] } },
          { type: "div", props: { style: { display: "flex", width: "2px", height: "44px", background: "#334155" } } },
          { type: "div", props: { style: { display: "flex", flexDirection: "column", gap: "2px" }, children: [
            { type: "span", props: { style: { color: "#E2E8F0", fontSize: 44, fontWeight: 900, fontFamily: `'${fontName}', serif`, lineHeight: 1 }, children: `K${(issue.kscore||0).toFixed(1)}` } },
            { type: "span", props: { style: { color: "#94A3B8", fontSize: 16, fontWeight: 400 }, children: "KScore" } },
          ] } },
          { type: "div", props: { style: { display: "flex", width: "2px", height: "44px", background: "#334155" } } },
          { type: "div", props: { style: { display: "flex", flexDirection: "column", gap: "2px" }, children: [
            { type: "span", props: { style: { color: "#E2E8F0", fontSize: 44, fontWeight: 900, fontFamily: `'${fontName}', serif`, lineHeight: 1 }, children: String(issue.event_count) } },
            { type: "span", props: { style: { color: "#94A3B8", fontSize: 16, fontWeight: 400 }, children: srcLabel } },
          ] } },
        ] } },
      ] } },
    ] } },
    // Bottom
    { type: "div", props: { style: { display: "flex", justifyContent: "flex-end", marginTop: "auto" }, children: [
      { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 400 }, children: "wewantpeace.live" } },
    ] } },
  ] } });

  return { type: "div", props: { style: { display: "flex", width: "100%", height: "100%", fontFamily: "'Inter', sans-serif", background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)", position: "relative" }, children } };
}

async function main() {
  console.log("Fetching fonts...");
  const interData = await fetchFont(INTER_URL);
  const fontDataMap = {};
  for (const [k, f] of Object.entries(FONTS_META)) {
    console.log(`  ${f.label}...`);
    fontDataMap[k] = await fetchFont(f.url);
  }

  console.log("Fetching real data...");
  const [issue, tension, historyRaw] = await Promise.all([
    fetchJson(`${API}/issues/c6171f25-4f4d-4da9-a0c6-c904730ba5d4`),
    fetchJson(`${API}/tension/country/UA`),
    fetchJson(`${API}/tension/country/UA/history?range=7d`),
  ]);

  // Fetch background images
  console.log("Fetching background images...");
  const issueBg = issue?.image_url ? await fetchImageBase64(issue.image_url) : null;
  const countryBgUrl = tension?.top5_clusters?.find(c => c.image_url)?.image_url;
  const countryBg = countryBgUrl ? await fetchImageBase64(countryBgUrl) : null;
  console.log(`  Issue bg: ${issueBg ? "OK" : "none"}, Country bg: ${countryBg ? "OK" : "none"}`);

  const history = historyRaw || [];

  mkdirSync("/tmp/og-final", { recursive: true });

  for (const [fKey, fMeta] of Object.entries(FONTS_META)) {
    const fonts = [
      { name: fMeta.name, data: fontDataMap[fKey], weight: fMeta.weight, style: "normal" },
      { name: "Inter", data: interData, weight: 600, style: "normal" },
    ];

    for (const lang of ["ko", "en"]) {
      // Country OG
      const cJsx = countryOG(fMeta.name, lang, tension, history, countryBg);
      console.log(`Rendering ${fKey}_country_${lang}...`);
      let svg = await satori(cJsx, { width: W, height: H, fonts });
      let png = new Resvg(svg, { fitTo: { mode: "width", value: W } }).render().asPng();
      writeFileSync(`/tmp/og-final/${fKey}_country_${lang}.png`, png);

      // Issue OG
      const iJsx = issueOG(fMeta.name, lang, issue, issueBg);
      console.log(`Rendering ${fKey}_issue_${lang}...`);
      svg = await satori(iJsx, { width: W, height: H, fonts });
      png = new Resvg(svg, { fitTo: { mode: "width", value: W } }).render().asPng();
      writeFileSync(`/tmp/og-final/${fKey}_issue_${lang}.png`, png);
    }
  }
  console.log("Done! 12 images generated.");
}

main().catch(console.error);

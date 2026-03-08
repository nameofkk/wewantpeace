/**
 * Black Han Sans 폰트로 OG 이미지 4개 생성
 * - Country OG (ko/en) — 우크라이나 Tension Index
 * - Issue OG (ko/en) — 이란 전쟁 이슈 상세
 */
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";
import { writeFileSync, mkdirSync } from "fs";

const W = 1200, H = 630;

const BLACK_HAN_URL = "https://fonts.gstatic.com/s/blackhansans/v17/ea8Aad44WunzF9a-dL6toA8r8nqVIXSkH-Hc.ttf";
const INTER_URL = "https://fonts.gstatic.com/s/inter/v20/UcCO3FwrK3iLTeHuS_nVMrMxCp50SjIw2boKoduKmMEVuGKYMZg.ttf";

async function fetchFont(url) {
  return (await fetch(url)).arrayBuffer();
}

// ── Country OG (Tension Index) ──
function countryOG(lang) {
  const isEn = lang === "en";
  const headline = isEn ? "Ukraine" : "우크라이나";
  const sub = isEn ? "우크라이나" : "Ukraine";
  const tagline = isEn ? "Real-time Global Conflict Monitor" : "실시간 글로벌 분쟁 모니터링";
  const levelLabel = isEn ? "Critical" : "위험";
  const trendLabel = isEn ? "7-Day Trend" : "7일 추이";
  const issuesLabel = isEn ? "Top Issues" : "주요 이슈";
  const issues = isEn
    ? ["1. Russia-Ukraine frontline escalation", "2. Zaporizhzhia nuclear plant tensions"]
    : ["1. 러시아-우크라이나 전선 교착 격화", "2. 자포리자 원전 긴장 고조"];

  return {
    type: "div",
    props: {
      style: { display: "flex", width: "100%", height: "100%", fontFamily: "'Inter', sans-serif", background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)", position: "relative" },
      children: [
        // 상단 악센트
        { type: "div", props: { style: { display: "flex", position: "absolute", top: 0, left: 0, width: "100%", height: "6px", background: "linear-gradient(90deg, transparent 0%, #EF4444 30%, #EF4444 70%, transparent 100%)" } } },
        // 메인
        { type: "div", props: { style: { display: "flex", flexDirection: "column", width: "100%", height: "100%", padding: "44px 56px 40px", position: "relative" }, children: [
          // 상단
          { type: "div", props: { style: { display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
            { type: "span", props: { style: { color: "#94A3B8", fontSize: 28, fontWeight: 600, letterSpacing: "-0.3px" }, children: "WeWantPeace" } },
            { type: "div", props: { style: { display: "flex", alignItems: "center", gap: "12px" }, children: [
              { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 600 }, children: tagline } },
              { type: "div", props: { style: { display: "flex", background: "#DC2626", color: "#FFF", padding: "10px 26px", borderRadius: "24px", fontSize: 20, fontWeight: 600 }, children: levelLabel } },
            ] } },
          ] } },
          // 국가명 + 점수
          { type: "div", props: { style: { display: "flex", flex: 1, alignItems: "center", gap: "48px", marginTop: "20px" }, children: [
            { type: "div", props: { style: { display: "flex", flexDirection: "column", flex: 1, gap: "4px" }, children: [
              // 헤드라인
              { type: "div", props: { style: { display: "flex", alignItems: "baseline", gap: "16px" }, children: [
                { type: "span", props: { style: { color: "#FFFFFF", fontSize: 72, fontWeight: 400, fontFamily: "'Black Han Sans', sans-serif", lineHeight: 1.1, letterSpacing: "-1px" }, children: headline } },
                { type: "span", props: { style: { color: "#94A3B8", fontSize: 28, fontWeight: 600 }, children: sub } },
              ] } },
              // 점수
              { type: "div", props: { style: { display: "flex", alignItems: "baseline", gap: "12px", marginTop: "16px" }, children: [
                { type: "span", props: { style: { color: "#EF4444", fontSize: 88, fontWeight: 400, fontFamily: "'Black Han Sans', sans-serif", letterSpacing: "-3px", lineHeight: 1 }, children: "72.4" } },
                { type: "span", props: { style: { color: "#94A3B8", fontSize: 24, fontWeight: 600 }, children: "/ 100" } },
              ] } },
              { type: "span", props: { style: { color: "#94A3B8", fontSize: 22, fontWeight: 600, marginTop: "2px" }, children: "Tension Index" } },
              // 게이지
              { type: "div", props: { style: { display: "flex", width: "100%", maxWidth: "360px", height: "16px", background: "#1E293B", borderRadius: "6px", marginTop: "16px", overflow: "hidden", border: "1px solid #334155" }, children: [
                { type: "div", props: { style: { display: "flex", width: "72.4%", height: "100%", background: "linear-gradient(90deg, #EF444488, #EF4444)", borderRadius: "6px" } } },
              ] } },
            ] } },
            // 오른쪽: 7일 추이 placeholder + 이슈
            { type: "div", props: { style: { display: "flex", flexDirection: "column", width: "440px", gap: "12px" }, children: [
              { type: "span", props: { style: { color: "#94A3B8", fontSize: 18, fontWeight: 600 }, children: trendLabel } },
              { type: "div", props: { style: { display: "flex", width: "420px", height: "100px", background: "rgba(15,23,42,0.6)", borderRadius: "12px", border: "1px solid #1E293B", alignItems: "center", justifyContent: "center" }, children: [
                { type: "span", props: { style: { color: "#334155", fontSize: 16 }, children: "▅▆▇█▇▅▆▇" } },
              ] } },
              { type: "span", props: { style: { color: "#64748B", fontSize: 16, fontWeight: 600, marginTop: "4px" }, children: issuesLabel } },
              ...issues.map(t => ({ type: "span", props: { style: { color: "#CBD5E1", fontSize: 18, fontWeight: 600 }, children: t } })),
            ] } },
          ] } },
          // 하단
          { type: "div", props: { style: { display: "flex", justifyContent: "flex-end", marginTop: "auto" }, children: [
            { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 600 }, children: "wewantpeace.live" } },
          ] } },
        ] } },
      ],
    },
  };
}

// ── Issue OG (이슈 상세) ──
function issueOG(lang) {
  const isEn = lang === "en";
  const headline = isEn
    ? "Global Protests Mark One Week of Iran War"
    : "이란 전쟁 일주일을 맞아 전 세계 시위";
  const country = isEn ? "Israel" : "이스라엘";
  const topic = isEn ? "Armed Conflict" : "무장 충돌";
  const tagline = isEn ? "Real-time Global Conflict Monitor" : "실시간 글로벌 분쟁 모니터링";
  const sevLabel = isEn ? "Severity" : "위기지수";
  const srcLabel = isEn ? "Sources" : "보도 건수";
  const trendLabel = isEn ? "KScore 7-Day Trend" : "KScore 7일 추이";
  const titleSize = headline.length <= 20 ? 56 : headline.length <= 35 ? 46 : 38;

  return {
    type: "div",
    props: {
      style: { display: "flex", width: "100%", height: "100%", fontFamily: "'Inter', sans-serif", background: "linear-gradient(135deg, #0F172A 0%, #1E293B 50%, #0F172A 100%)", position: "relative" },
      children: [
        { type: "div", props: { style: { display: "flex", position: "absolute", top: 0, left: 0, width: "100%", height: "6px", background: "linear-gradient(90deg, transparent 0%, #EF4444 30%, #EF4444 70%, transparent 100%)" } } },
        { type: "div", props: { style: { display: "flex", flexDirection: "column", width: "100%", height: "100%", padding: "44px 56px 40px", position: "relative" }, children: [
          // 상단
          { type: "div", props: { style: { display: "flex", alignItems: "center", justifyContent: "space-between" }, children: [
            { type: "span", props: { style: { color: "#94A3B8", fontSize: 28, fontWeight: 600 }, children: "WeWantPeace" } },
            { type: "div", props: { style: { display: "flex", alignItems: "center", gap: "12px" }, children: [
              { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 600 }, children: tagline } },
              { type: "div", props: { style: { display: "flex", background: "#DC2626", color: "#FFF", padding: "10px 26px", borderRadius: "24px", fontSize: 20, fontWeight: 600 }, children: "Critical" } },
            ] } },
          ] } },
          // 중앙
          { type: "div", props: { style: { display: "flex", flex: 1, gap: "40px", marginTop: "24px", alignItems: "center" }, children: [
            { type: "div", props: { style: { display: "flex", flexDirection: "column", flex: 1, gap: "12px" }, children: [
              // 뱃지
              { type: "div", props: { style: { display: "flex", gap: "10px" }, children: [
                { type: "span", props: { style: { background: "#1E293B", color: "#E2E8F0", padding: "8px 18px", borderRadius: "16px", fontSize: 18, fontWeight: 600, border: "1px solid #334155" }, children: country } },
                { type: "span", props: { style: { background: "#1E293B", color: "#E2E8F0", padding: "8px 18px", borderRadius: "16px", fontSize: 18, fontWeight: 600, border: "1px solid #334155" }, children: topic } },
              ] } },
              // 헤드라인
              { type: "div", props: { style: { display: "flex", color: "#FFFFFF", fontSize: titleSize, fontWeight: 400, fontFamily: "'Black Han Sans', sans-serif", lineHeight: 1.35, letterSpacing: "-0.5px", wordBreak: "keep-all", overflowWrap: "break-word" }, children: headline } },
              // 지표
              { type: "div", props: { style: { display: "flex", alignItems: "center", gap: "28px", marginTop: "12px" }, children: [
                { type: "div", props: { style: { display: "flex", flexDirection: "column", gap: "2px" }, children: [
                  { type: "span", props: { style: { color: "#EF4444", fontSize: 44, fontWeight: 400, fontFamily: "'Black Han Sans', sans-serif", lineHeight: 1 }, children: "90" } },
                  { type: "span", props: { style: { color: "#94A3B8", fontSize: 16, fontWeight: 600 }, children: sevLabel } },
                ] } },
                { type: "div", props: { style: { display: "flex", width: "2px", height: "44px", background: "#334155" } } },
                { type: "div", props: { style: { display: "flex", flexDirection: "column", gap: "2px" }, children: [
                  { type: "span", props: { style: { color: "#E2E8F0", fontSize: 44, fontWeight: 400, fontFamily: "'Black Han Sans', sans-serif", lineHeight: 1 }, children: "K5.3" } },
                  { type: "span", props: { style: { color: "#94A3B8", fontSize: 16, fontWeight: 600 }, children: "KScore" } },
                ] } },
                { type: "div", props: { style: { display: "flex", width: "2px", height: "44px", background: "#334155" } } },
                { type: "div", props: { style: { display: "flex", flexDirection: "column", gap: "2px" }, children: [
                  { type: "span", props: { style: { color: "#E2E8F0", fontSize: 44, fontWeight: 400, fontFamily: "'Black Han Sans', sans-serif", lineHeight: 1 }, children: "47" } },
                  { type: "span", props: { style: { color: "#94A3B8", fontSize: 16, fontWeight: 600 }, children: srcLabel } },
                ] } },
              ] } },
            ] } },
            // 그래프 placeholder
            { type: "div", props: { style: { display: "flex", flexDirection: "column", width: "440px", gap: "8px" }, children: [
              { type: "span", props: { style: { color: "#94A3B8", fontSize: 18, fontWeight: 600 }, children: trendLabel } },
              { type: "div", props: { style: { display: "flex", width: "420px", height: "120px", background: "rgba(15,23,42,0.6)", borderRadius: "12px", border: "1px solid #1E293B", alignItems: "center", justifyContent: "center" }, children: [
                { type: "span", props: { style: { color: "#334155", fontSize: 16 }, children: "▃▅▆▇█▇▅▃▅▇" } },
              ] } },
            ] } },
          ] } },
          // 하단
          { type: "div", props: { style: { display: "flex", justifyContent: "flex-end", marginTop: "auto" }, children: [
            { type: "span", props: { style: { color: "#94A3B8", fontSize: 20, fontWeight: 600 }, children: "wewantpeace.live" } },
          ] } },
        ] } },
      ],
    },
  };
}

async function main() {
  console.log("Fetching fonts...");
  const [bhsData, interData] = await Promise.all([
    fetchFont(BLACK_HAN_URL),
    fetchFont(INTER_URL),
  ]);

  const fonts = [
    { name: "Black Han Sans", data: bhsData, weight: 400, style: "normal" },
    { name: "Inter", data: interData, weight: 600, style: "normal" },
  ];

  mkdirSync("/tmp/og-blackhan", { recursive: true });

  const variants = [
    { name: "country_ko", jsx: countryOG("ko") },
    { name: "country_en", jsx: countryOG("en") },
    { name: "issue_ko", jsx: issueOG("ko") },
    { name: "issue_en", jsx: issueOG("en") },
  ];

  for (const v of variants) {
    console.log(`Rendering ${v.name}...`);
    const svg = await satori(v.jsx, { width: W, height: H, fonts });
    const resvg = new Resvg(svg, { fitTo: { mode: "width", value: W } });
    const png = resvg.render().asPng();
    writeFileSync(`/tmp/og-blackhan/${v.name}.png`, png);
    console.log(`  ✓ ${v.name}.png`);
  }
  console.log("Done!");
}

main().catch(console.error);

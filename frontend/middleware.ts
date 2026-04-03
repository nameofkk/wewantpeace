import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * 검색 봇 UA 감지 → 깔끔한 HTML 직접 반환 (root `/` 전용).
 *
 * Next.js SSR은 <head> 안에 <script> 태그를 <title>/<meta> 앞에 삽입하기 때문에
 * NAVER 등 일부 크롤러가 <title>/<meta description>/OG 태그를 파싱하지 못함.
 * 봇에게는 script 없는 깨끗한 HTML을 직접 반환하여 메타태그를 확실히 전달.
 *
 * NAVER/Daum 봇 → 한국어, 그 외 봇 → 영어.
 * 일반 유저: 온보딩 미완료 시 /onboarding으로 rewrite.
 */

const KOREAN_BOT_RE = /Yeti|NaverBot|Daumoa/i;

const GLOBAL_BOT_RE =
  /Googlebot|bingbot|Slurp|DuckDuckBot|Baiduspider|Twitterbot|facebookexternalhit|kakaotalk-scrap|line-poker|Discordbot|Applebot|PetalBot|Bytespider|ChatGPT-User|OAI-SearchBot|PerplexityBot|CopilotBot/i;

const SITE = "https://www.wewantpeace.live";

const META_KO = {
  lang: "ko",
  title: "실시간 전쟁 지도 · 분쟁 뉴스 트래커 | WeWantPeace",
  desc: "전쟁·분쟁이 내 삶에 미치는 영향을 실시간 추적. 195개국 긴장도 지수, AI 분석, 분쟁 지도",
  ogTitle: "실시간 전쟁 지도 · 분쟁 뉴스 트래커 | WeWantPeace",
  ogDesc: "전쟁·분쟁이 내 삶에 미치는 영향을 실시간 추적. 195개국 긴장도 지수, AI 분석, 분쟁 지도",
  h1: "실시간 전쟁 지도 · 분쟁 뉴스 트래커",
  body: `<p>전 세계 전쟁·분쟁이 내 삶에 미치는 영향을 실시간으로 추적하세요.</p>
<ul>
<li>긴장도 지수: 195개국 실시간 점수(0~100), 15분마다 갱신</li>
<li>위험지수: AI 기반 맞춤형 영향 분석</li>
<li>리스크 레이더: 군사·에너지·무역·식량·금융 5축 위험 평가</li>
<li>시장 스냅샷: 원유·금·가스 가격 및 환율과 분쟁 연계 분석</li>
<li>글로벌 분쟁 지도: 히트맵 + 실시간 마커, 195개국</li>
<li>스마트 알림: 관심 국가 기반 위험지수 푸시 알림</li>
</ul>`,
  nav: `<a href="${SITE}/home">대시보드</a> <a href="${SITE}/tension">긴장도 지수</a> <a href="${SITE}/feed">분쟁 피드</a> <a href="${SITE}/map">글로벌 지도</a>`,
};

const META_EN = {
  lang: "en",
  title: "Live War Map &amp; Conflict Tracker | WeWantPeace",
  desc: "Track wars &amp; conflicts in real time across 195 countries. Live map, Tension Index, AI analysis &amp; alerts",
  ogTitle: "Live War Map &amp; Conflict Tracker | WeWantPeace",
  ogDesc: "Track wars &amp; conflicts in real time across 195 countries. Live map, Tension Index, AI analysis &amp; alerts",
  h1: "Live War Map &amp; Conflict Tracker",
  body: `<p>Track how war and conflict impact your daily life in real time.</p>
<ul>
<li>Tension Index: Real-time country-level scores (0-100), updated every 15 minutes</li>
<li>Risk Level: AI-powered impact analysis personalized to your country</li>
<li>Risk Radar: Military, Energy, Trade, Food, Finance - 5-axis risk assessment</li>
<li>Market Snapshot: Oil, gold, gas prices and exchange rates linked to conflicts</li>
<li>Global Conflict Map: Heatmap + real-time markers across 195 countries</li>
<li>Smart Alerts: Risk-level-based push notifications for your countries of interest</li>
</ul>`,
  nav: `<a href="${SITE}/home">Dashboard</a> <a href="${SITE}/tension">Tension Index</a> <a href="${SITE}/feed">Conflict Feed</a> <a href="${SITE}/map">Global Map</a>`,
};

function botHtml(m: typeof META_KO) {
  return `<!DOCTYPE html>
<html lang="${m.lang}">
<head>
<meta charset="utf-8">
<title>${m.title}</title>
<meta name="description" content="${m.desc}">
<meta name="robots" content="index, follow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="${SITE}">
<link rel="alternate" hreflang="ko" href="${SITE}">
<link rel="alternate" hreflang="en" href="${SITE}">
<link rel="alternate" hreflang="x-default" href="${SITE}">
<meta property="og:type" content="website">
<meta property="og:title" content="${m.ogTitle}">
<meta property="og:description" content="${m.ogDesc}">
<meta property="og:image" content="${SITE}/og-image.png?v=4">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="${SITE}">
<meta property="og:site_name" content="WeWantPeace">
<meta property="og:locale" content="${m.lang === "ko" ? "ko_KR" : "en_US"}">
<meta property="og:locale:alternate" content="${m.lang === "ko" ? "en_US" : "ko_KR"}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="${m.ogTitle}">
<meta name="twitter:description" content="${m.ogDesc}">
<meta name="twitter:image" content="${SITE}/og-image-twitter.png?v=4">
<meta name="google-site-verification" content="LJQ8sx_1VitFQTLo9e3oNys3rRVZdpIWAHuSYZtzrOo">
<meta name="naver-site-verification" content="ce8b1e250ea44cedcdd2e4383a4d35d1f9252031">
</head>
<body>
<h1>${m.h1}</h1>
${m.body}
<nav>${m.nav}</nav>
</body>
</html>`;
}

export function middleware(request: NextRequest) {
  const ua = request.headers.get("user-agent") || "";

  if (KOREAN_BOT_RE.test(ua)) {
    return new NextResponse(botHtml(META_KO), {
      status: 200,
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "public, max-age=3600, s-maxage=86400",
      },
    });
  }

  if (GLOBAL_BOT_RE.test(ua)) {
    return new NextResponse(botHtml(META_EN), {
      status: 200,
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "public, max-age=3600, s-maxage=86400",
      },
    });
  }

  if (request.cookies.get("onboarding_done")) return;
  return NextResponse.rewrite(new URL("/onboarding", request.url));
}

export const config = {
  matcher: "/",
};

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * 검색 봇 UA 감지 → 깔끔한 HTML 직접 반환 (root `/` 전용).
 *
 * Next.js SSR은 <head> 안에 <script> 태그를 <title>/<meta> 앞에 삽입하기 때문에
 * NAVER 등 일부 크롤러가 <title>/<meta description>/OG 태그를 파싱하지 못함.
 * 봇에게는 script 없는 깨끗한 HTML을 직접 반환하여 메타태그를 확실히 전달.
 *
 * 일반 유저: 온보딩 미완료 시 /onboarding으로 rewrite.
 */
const SEARCH_BOT_RE =
  /Yeti|Googlebot|bingbot|Slurp|DuckDuckBot|Baiduspider|Twitterbot|facebookexternalhit|kakaotalk-scrap|line-poker|Discordbot|Applebot|PetalBot|Bytespider|ChatGPT-User|OAI-SearchBot|PerplexityBot|CopilotBot|NaverBot/i;

const SITE = "https://www.wewantpeace.live";

function botHtml() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>WeWantPeace: Real-time Conflict Tracker</title>
<meta name="description" content="Track how war affects you in real time. Tension Index &amp; alerts for 195 countries">
<meta name="robots" content="index, follow">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="${SITE}">
<link rel="alternate" hreflang="ko" href="${SITE}">
<link rel="alternate" hreflang="en" href="${SITE}">
<link rel="alternate" hreflang="x-default" href="${SITE}">
<meta property="og:type" content="website">
<meta property="og:title" content="WeWantPeace: Real-time Conflict Tracker">
<meta property="og:description" content="Track how war affects you in real time. Tension Index &amp; alerts for 195 countries">
<meta property="og:image" content="${SITE}/og-image.png?v=4">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="${SITE}">
<meta property="og:site_name" content="WeWantPeace">
<meta property="og:locale" content="ko_KR">
<meta property="og:locale:alternate" content="en_US">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="WeWantPeace: Real-time Conflict Tracker">
<meta name="twitter:description" content="Track how war affects you in real time. Tension Index &amp; alerts for 195 countries">
<meta name="twitter:image" content="${SITE}/og-image-twitter.png?v=4">
<meta name="google-site-verification" content="LJQ8sx_1VitFQTLo9e3oNys3rRVZdpIWAHuSYZtzrOo">
<meta name="naver-site-verification" content="ce8b1e250ea44cedcdd2e4383a4d35d1f9252031">
</head>
<body>
<h1>WeWantPeace: Real-time Conflict Tracker</h1>
<p>Track how war and conflict impact your daily life in real time.</p>
<ul>
<li>Tension Index: Real-time country-level scores (0-100), updated every 15 minutes</li>
<li>KScore: AI-powered impact analysis personalized to your country</li>
<li>Risk Radar: Military, Energy, Trade, Food, Finance - 5-axis risk assessment</li>
<li>Market Snapshot: Oil, gold, gas prices and exchange rates linked to conflicts</li>
<li>Global Conflict Map: Heatmap + real-time markers across 195 countries</li>
<li>Smart Alerts: KScore-based push notifications for your countries of interest</li>
</ul>
<nav>
<a href="${SITE}/home">Dashboard</a>
<a href="${SITE}/tension">Tension Index</a>
<a href="${SITE}/feed">Conflict Feed</a>
<a href="${SITE}/map">Global Map</a>
</nav>
</body>
</html>`;
}

export function middleware(request: NextRequest) {
  const ua = request.headers.get("user-agent") || "";

  if (SEARCH_BOT_RE.test(ua)) {
    return new NextResponse(botHtml(), {
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

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * 온보딩 미완료 사용자가 `/` 접속 시 `/onboarding` 페이지를 SSR로 제공.
 * rewrite 사용 → URL은 `/`로 유지, OG 메타태그 정상 동작.
 *
 * 검색 봇은 리라이트 건너뜀:
 *   x-middleware-rewrite: /onboarding 헤더 + robots.txt Disallow: /onboarding 조합 시
 *   NAVER 등의 봇이 콘텐츠(메타태그 포함)를 처리하지 않는 문제 방지.
 */
const SEARCH_BOT_RE =
  /Yeti|Googlebot|bingbot|Slurp|DuckDuckBot|Baiduspider|Twitterbot|facebookexternalhit|kakaotalk-scrap|line-poker|Discordbot|Applebot|PetalBot|Bytespider|ChatGPT-User|OAI-SearchBot|PerplexityBot|CopilotBot/i;

export function middleware(request: NextRequest) {
  const ua = request.headers.get("user-agent") || "";
  if (SEARCH_BOT_RE.test(ua)) return NextResponse.next();
  if (request.cookies.get("onboarding_done")) return;
  return NextResponse.rewrite(new URL("/onboarding", request.url));
}

export const config = {
  matcher: "/",
};

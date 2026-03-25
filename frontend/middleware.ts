import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * 온보딩 미완료 사용자가 `/` 접속 시 `/onboarding` 페이지를 SSR로 제공.
 * rewrite 사용 → URL은 `/`로 유지, OG 메타태그 정상 동작.
 * 이전: 클라이언트 JS 로드 후 router.replace() → LCP 6초+
 * 이후: 서버에서 즉시 onboarding HTML 응답 → LCP 1-2초
 */
export function middleware(request: NextRequest) {
  if (request.cookies.get("onboarding_done")) return;
  return NextResponse.rewrite(new URL("/onboarding", request.url));
}

export const config = {
  matcher: "/",
};

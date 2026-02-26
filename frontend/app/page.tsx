"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * 루트 페이지: 클라이언트 사이드 리다이렉트.
 * 서버 사이드 redirect()를 사용하면 HTTP 307이 반환되어
 * 소셜 미디어 크롤러(카카오톡, Facebook 등)가 OG 메타태그를 읽지 못함.
 * layout.tsx의 metadata가 200으로 제공되어야 OG 미리보기가 정상 동작함.
 */
export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    router.replace(done ? "/home" : "/onboarding");
  }, [router]);

  return null;
}

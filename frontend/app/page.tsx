"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * 루트 페이지: 클라이언트 사이드 리다이렉트.
 * 서버 사이드 redirect()를 사용하면 HTTP 307이 반환되어
 * 소셜 미디어 크롤러(카카오톡, Facebook 등)가 OG 메타태그를 읽지 못함.
 * layout.tsx의 metadata가 200으로 제공되어야 OG 미리보기가 정상 동작함.
 *
 * SEO: 검색봇이 body 콘텐츠를 읽을 수 있도록 숨겨진 콘텐츠 포함.
 */
export default function RootPage() {
  const router = useRouter();

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    router.replace(done ? "/home" : "/onboarding");
  }, [router]);

  return (
    <div className="sr-only" aria-hidden="true">
      <h1>WeWantPeace — 실시간 전쟁·분쟁 모니터링</h1>
      <p>
        전쟁·분쟁이 내 삶에 미치는 영향을 실시간으로 추적하세요.
        195개국 긴장도 지수, 맞춤 알림, 글로벌 분쟁 지도를 제공합니다.
      </p>
      <p>
        Track how war and conflict impact your daily life in real time.
        Tension Index across 195 countries, personalized alerts, and global conflict map.
      </p>
      <ul>
        <li>긴장도 지수: 국가별 0~100 실시간 업데이트</li>
        <li>KScore: AI 기반 영향도 분석</li>
        <li>리스크 레이더: 군사·에너지·무역·식량·금융</li>
        <li>시장 스냅샷: 유가·금값·환율 실시간 연동</li>
        <li>글로벌 분쟁 지도: 히트맵 + 실시간 마커</li>
        <li>실시간 알림: KScore 기반 맞춤 푸시</li>
      </ul>
    </div>
  );
}

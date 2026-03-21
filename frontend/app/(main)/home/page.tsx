import type { Metadata } from "next";
import { Suspense } from "react";
import HomeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "홈 — 나의 글로벌 리스크 대시보드",
  description:
    "분쟁이 나에게 미치는 영향을 실시간으로 확인하세요. 개인화 영향도, 긴장도 지수, 시장 동향, 핵심 이슈 요약. Your personalized global risk dashboard — see how world conflicts affect you in real time with KScore impact analysis.",
  alternates: {
    canonical: `${SITE_URL}/home`,
    languages: {
      ko: `${SITE_URL}/home`,
      en: `${SITE_URL}/home?lang=en`,
      "x-default": `${SITE_URL}/home`,
    },
  },
  openGraph: {
    title: "나의 글로벌 리스크 대시보드 | WeWantPeace",
    description: "Your personalized global risk dashboard — see how world conflicts affect you in real time.",
    type: "website",
    url: `${SITE_URL}/home`,
    siteName: "WeWantPeace",
  },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <HomeClient />
    </Suspense>
  );
}

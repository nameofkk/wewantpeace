import type { Metadata } from "next";
import { Suspense } from "react";
import FeedClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "실시간 이슈 피드",
  description:
    "글로벌 분쟁·안보 이슈를 실시간으로 확인하세요. KScore 기반 정렬, 토픽별 필터링, 심각도 표시. Live feed of global conflict and security events | AI-classified, severity-scored, and updated every 3 minutes from 200+ sources.",
  alternates: {
    canonical: `${SITE_URL}/feed`,
    languages: {
      ko: `${SITE_URL}/feed`,
      en: `${SITE_URL}/feed?lang=en`,
      "x-default": `${SITE_URL}/feed`,
    },
  },
  openGraph: {
    title: "Real-time Conflict Feed | WeWantPeace",
    description: "Live feed of global conflict events | AI-classified from 200+ sources, updated every 3 minutes.",
    type: "website",
    url: `${SITE_URL}/feed`,
    siteName: "WeWantPeace",
  },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <FeedClient />
    </Suspense>
  );
}

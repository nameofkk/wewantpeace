import type { Metadata } from "next";
import { Suspense } from "react";
import UpgradeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Pro 플랜 업그레이드",
  description:
    "WeWantPeace Pro로 업그레이드하여 인터랙티브 이슈 지도, 5개 관심국가, KScore 필터, 30일 히스토리 등 프리미엄 기능을 이용하세요.",
  alternates: {
    canonical: `${SITE_URL}/upgrade`,
    languages: {
      ko: `${SITE_URL}/upgrade`,
      en: `${SITE_URL}/upgrade?lang=en`,
      "x-default": `${SITE_URL}/upgrade`,
    },
  },
  openGraph: {
    title: "Pro 플랜 업그레이드 | WeWantPeace",
    description: "프리미엄 기능으로 글로벌 리스크를 더 깊이 분석하세요.",
    type: "website",
    url: `${SITE_URL}/upgrade`,
    siteName: "WeWantPeace",
  },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <UpgradeClient />
    </Suspense>
  );
}

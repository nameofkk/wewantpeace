import type { Metadata } from "next";
import MapClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "실시간 글로벌 이슈 지도",
  description:
    "195개국 분쟁·안보 이슈를 실시간 인터랙티브 지도에서 확인하세요. 긴장도, 심각도, KScore 기반 필터링 지원. Interactive world conflict map | visualize active crises, wars, and security threats across 195 countries in real time.",
  alternates: {
    canonical: `${SITE_URL}/map`,
    languages: {
      ko: `${SITE_URL}/map`,
      en: `${SITE_URL}/map?lang=en`,
      "x-default": `${SITE_URL}/map`,
    },
  },
  openGraph: {
    title: "Interactive World Conflict Map | WeWantPeace",
    description:
      "Visualize active crises, wars, and security threats across 195 countries in real time.",
    type: "website",
    url: `${SITE_URL}/map`,
    siteName: "WeWantPeace",
  },
};

export default function Page() {
  return <MapClient />;
}

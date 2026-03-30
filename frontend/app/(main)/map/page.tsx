import type { Metadata } from "next";
import MapClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Interactive Global Issue Map",
  description:
    "Interactive world conflict map. Visualize active crises, wars, and security threats across 195 countries in real time. | 195개국 분쟁·안보 이슈를 실시간 인터랙티브 지도에서 확인하세요.",
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

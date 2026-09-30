import type { Metadata } from "next";
import MapClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Interactive Global Conflict Map",
  description:
    "Visualize active crises, wars, and security threats across 195 countries in real time. Heatmap, markers & satellite signals.",
  alternates: {
    canonical: `${SITE_URL}/map`,
    languages: {
      ko: `${SITE_URL}/map`,
      en: `${SITE_URL}/map?lang=en`,
      "x-default": `${SITE_URL}/map`,
    },
  },
  openGraph: {
    title: "Interactive Global Conflict Map | WeWantPeace",
    description:
      "Visualize active crises, wars, and security threats across 195 countries in real time.",
    type: "website",
    url: `${SITE_URL}/map`,
    siteName: "WeWantPeace",
    locale: "en_US",
    // openGraph 를 페이지에서 새로 적으면 루트의 이미지가 통째로 사라진다 — 여기서도 넣는다
    images: [{ url: `${SITE_URL}/og-image.png?v=5`, width: 1200, height: 630 }],
  },
  twitter: { card: "summary_large_image", images: [`${SITE_URL}/og-image.png?v=5`] },
};

export default function Page() {
  return <MapClient />;
}

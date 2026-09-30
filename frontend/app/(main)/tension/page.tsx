import type { Metadata } from "next";
import TensionClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Country Tension Index (0–100)",
  description:
    "Real-time Tension Index across 195 countries. Updated every 15 minutes — combining event severity, activity volume, and spillover analysis.",
  alternates: {
    canonical: `${SITE_URL}/tension`,
    languages: {
      ko: `${SITE_URL}/tension`,
      en: `${SITE_URL}/tension?lang=en`,
      "x-default": `${SITE_URL}/tension`,
    },
  },
  openGraph: {
    title: "Country Tension Index (0–100) | WeWantPeace",
    description: "Real-time tension scores for 195 countries. Updated every 15 minutes based on conflict events, activity, and spillover.",
    type: "website",
    url: `${SITE_URL}/tension`,
    siteName: "WeWantPeace",
    locale: "en_US",
    // openGraph 를 페이지에서 새로 적으면 루트의 이미지가 통째로 사라진다 — 여기서도 넣는다
    images: [{ url: `${SITE_URL}/og-image.png?v=5`, width: 1200, height: 630 }],
  },
  twitter: { card: "summary_large_image", images: [`${SITE_URL}/og-image.png?v=5`] },
};

export default function Page() {
  return <TensionClient />;
}

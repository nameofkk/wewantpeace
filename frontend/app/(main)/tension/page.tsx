import type { Metadata } from "next";
import TensionClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Country Tension Index",
  description:
    "Country-level Tension Index (0-100) updated every 5 minutes. Combining event severity, activity volume, and spillover from neighboring countries. | 195개국 실시간 긴장도 지수.",
  alternates: {
    canonical: `${SITE_URL}/tension`,
    languages: {
      ko: `${SITE_URL}/tension`,
      en: `${SITE_URL}/tension?lang=en`,
      "x-default": `${SITE_URL}/tension`,
    },
  },
  openGraph: {
    title: "Country Tension Index (0-100) | WeWantPeace",
    description: "Real-time tension scores for 195 countries | updated every 5 minutes based on conflict events, activity, and spillover.",
    type: "website",
    url: `${SITE_URL}/tension`,
    siteName: "WeWantPeace",
  },
};

export default function Page() {
  return <TensionClient />;
}

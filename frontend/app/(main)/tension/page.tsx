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
  },
};

export default function Page() {
  return <TensionClient />;
}

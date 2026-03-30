import type { Metadata } from "next";
import { Suspense } from "react";
import UpgradeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Upgrade to Pro",
  description:
    "Upgrade to WeWantPeace Pro for interactive issue maps, 5 watchlist countries, KScore filters, 30-day history, and more premium features.",
  alternates: {
    canonical: `${SITE_URL}/upgrade`,
    languages: {
      ko: `${SITE_URL}/upgrade`,
      en: `${SITE_URL}/upgrade?lang=en`,
      "x-default": `${SITE_URL}/upgrade`,
    },
  },
  openGraph: {
    title: "Upgrade to Pro | WeWantPeace",
    description: "Go deeper with premium global risk analysis features.",
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

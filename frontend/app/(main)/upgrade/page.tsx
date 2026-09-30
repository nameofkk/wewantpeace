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
    locale: "en_US",
    // openGraph 를 페이지에서 새로 적으면 루트의 이미지가 통째로 사라진다 — 여기서도 넣는다
    images: [{ url: `${SITE_URL}/og-image.png?v=5`, width: 1200, height: 630 }],
  },
  twitter: { card: "summary_large_image", images: [`${SITE_URL}/og-image.png?v=5`] },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <UpgradeClient />
    </Suspense>
  );
}

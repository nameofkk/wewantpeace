import type { Metadata } from "next";
import { Suspense } from "react";
import HomeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "My Global Risk Dashboard",
  description:
    "Your personalized global risk dashboard. See how conflicts affect you in real time — economy, trade, energy & travel risk analysis with KScore.",
  alternates: {
    canonical: `${SITE_URL}/home`,
    languages: {
      ko: `${SITE_URL}/home`,
      en: `${SITE_URL}/home?lang=en`,
      "x-default": `${SITE_URL}/home`,
    },
  },
  openGraph: {
    title: "My Global Risk Dashboard | WeWantPeace",
    description: "Your personalized global risk dashboard. See how conflicts affect you in real time with KScore.",
    type: "website",
    url: `${SITE_URL}/home`,
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
      <HomeClient />
    </Suspense>
  );
}

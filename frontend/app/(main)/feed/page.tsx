import type { Metadata } from "next";
import { Suspense } from "react";
import FeedClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Real-time Conflict Feed",
  description:
    "Live feed of global conflict and security events. AI-classified, severity-scored, updated every 3 minutes from 500+ sources.",
  alternates: {
    canonical: `${SITE_URL}/feed`,
    languages: {
      ko: `${SITE_URL}/feed`,
      en: `${SITE_URL}/feed?lang=en`,
      "x-default": `${SITE_URL}/feed`,
    },
  },
  openGraph: {
    title: "Real-time Conflict Feed | WeWantPeace",
    description: "Live feed of global conflict events. AI-classified from 500+ sources, updated every 3 minutes.",
    type: "website",
    url: `${SITE_URL}/feed`,
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
      <FeedClient />
    </Suspense>
  );
}

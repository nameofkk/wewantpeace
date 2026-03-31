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
  },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <FeedClient />
    </Suspense>
  );
}

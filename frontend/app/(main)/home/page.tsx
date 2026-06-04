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
  },
};

export default function Page() {
  return (
    <Suspense fallback={null}>
      <HomeClient />
    </Suspense>
  );
}

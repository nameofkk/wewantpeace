import type { Metadata } from "next";
import { Suspense } from "react";
import HomeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Your Daily Conflict Weather",
  description:
    "Track how conflicts affect your daily costs — gas, groceries, flights. Your personalized conflict weather across 195 countries.",
  alternates: {
    canonical: `${SITE_URL}/home`,
    languages: {
      ko: `${SITE_URL}/home`,
      en: `${SITE_URL}/home?lang=en`,
      "x-default": `${SITE_URL}/home`,
    },
  },
  openGraph: {
    title: "Your Daily Conflict Weather | WeWantPeace",
    description: "Track how conflicts affect your daily costs — gas, groceries, flights. Real-time analysis across 195 countries.",
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

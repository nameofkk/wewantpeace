import type { Metadata } from "next";
import MapClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Interactive Global Conflict Map",
  description:
    "Visualize active crises, wars, and security threats across 195 countries in real time. Heatmap, markers & satellite signals.",
  alternates: {
    canonical: `${SITE_URL}/map`,
    languages: {
      ko: `${SITE_URL}/map`,
      en: `${SITE_URL}/map?lang=en`,
      "x-default": `${SITE_URL}/map`,
    },
  },
  openGraph: {
    title: "Interactive Global Conflict Map | WeWantPeace",
    description:
      "Visualize active crises, wars, and security threats across 195 countries in real time.",
    type: "website",
    url: `${SITE_URL}/map`,
    siteName: "WeWantPeace",
  },
};

export default function Page() {
  return <MapClient />;
}

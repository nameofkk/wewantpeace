import type { Metadata } from "next";
import { Suspense } from "react";
import HomeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: "Home | My Global Risk Dashboard",
  description:
    "Your personalized global risk dashboard. See how world conflicts affect you in real time with KScore impact analysis. | 분쟁이 나에게 미치는 영향을 실시간으로 확인하세요.",
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
    description: "Your personalized global risk dashboard. See how world conflicts affect you in real time.",
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

import type { Metadata } from "next";
import MapClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

interface Props {
  searchParams: { [key: string]: string | string[] | undefined };
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const isEn = searchParams.lang === "en";
  const canonical = `${SITE_URL}/map`;

  return {
    title: isEn ? "Real-time Global Issue Map" : "실시간 글로벌 이슈 지도",
    description: isEn
      ? "Interactive map showing global conflicts and security threats across 195 countries in real time."
      : "195개국 분쟁·안보 이슈를 실시간 인터랙티브 지도에서 확인하세요. 긴장도, 심각도, KScore 기반 필터링 지원.",
    alternates: {
      canonical,
      languages: { ko: canonical, en: `${canonical}?lang=en`, "x-default": canonical },
    },
    openGraph: {
      title: isEn ? "Real-time Global Issue Map | WeWantPeace" : "실시간 글로벌 이슈 지도 | WeWantPeace",
      description: isEn
        ? "Interactive map showing global conflicts and security threats across 195 countries."
        : "195개국 분쟁·안보 이슈를 실시간 인터랙티브 지도에서 확인하세요.",
      type: "website",
      url: canonical,
      siteName: "WeWantPeace",
    },
  };
}

export default function Page() {
  return <MapClient />;
}

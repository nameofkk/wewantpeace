import type { Metadata } from "next";
import TensionClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

interface Props {
  searchParams: { [key: string]: string | string[] | undefined };
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const isEn = searchParams.lang === "en";
  const canonical = `${SITE_URL}/tension`;

  return {
    title: isEn ? "Country Tension Index" : "국가별 긴장도 지수",
    description: isEn
      ? "Real-time tension index (0-100) for 195 countries. Based on event severity, activity volume, and spillover effects."
      : "195개국의 실시간 긴장도 지수(0-100)를 확인하세요. 이벤트 심각도, 활동량, 인접국 파급효과 기반 종합 평가.",
    alternates: {
      canonical,
      languages: { ko: canonical, en: `${canonical}?lang=en`, "x-default": canonical },
    },
    openGraph: {
      title: isEn ? "Country Tension Index | WeWantPeace" : "국가별 긴장도 지수 | WeWantPeace",
      description: isEn
        ? "Real-time tension index (0-100) for 195 countries."
        : "195개국의 실시간 긴장도 지수(0-100)를 확인하세요.",
      type: "website",
      url: canonical,
      siteName: "WeWantPeace",
    },
  };
}

export default function Page() {
  return <TensionClient />;
}

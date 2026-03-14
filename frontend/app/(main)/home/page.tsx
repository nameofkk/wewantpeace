import type { Metadata } from "next";
import HomeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

interface Props {
  searchParams: { [key: string]: string | string[] | undefined };
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const isEn = searchParams.lang === "en";
  const canonical = `${SITE_URL}/home`;

  return {
    title: isEn ? "My Global Risk Dashboard" : "홈 — 나의 글로벌 리스크 대시보드",
    description: isEn
      ? "See how global conflicts impact you in real time. Personalized impact score, tension index, market trends, and top issues."
      : "분쟁이 나에게 미치는 영향을 실시간으로 확인하세요. 개인화 영향도, 긴장도 지수, 시장 동향, 핵심 이슈 요약.",
    alternates: {
      canonical,
      languages: { ko: canonical, en: `${canonical}?lang=en`, "x-default": canonical },
    },
    openGraph: {
      title: isEn ? "My Global Risk Dashboard | WeWantPeace" : "나의 글로벌 리스크 대시보드 | WeWantPeace",
      description: isEn
        ? "See how global conflicts impact you in real time."
        : "분쟁이 나에게 미치는 영향을 실시간으로 확인하세요.",
      type: "website",
      url: canonical,
      siteName: "WeWantPeace",
    },
  };
}

export default function Page() {
  return <HomeClient />;
}

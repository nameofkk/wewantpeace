import type { Metadata } from "next";
import FeedClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

interface Props {
  searchParams: { [key: string]: string | string[] | undefined };
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const isEn = searchParams.lang === "en";
  const canonical = `${SITE_URL}/feed`;

  return {
    title: isEn ? "Real-time Issue Feed" : "실시간 이슈 피드",
    description: isEn
      ? "Live feed of global conflict and security issues. Sorted by KScore with topic filters and severity indicators."
      : "글로벌 분쟁·안보 이슈를 실시간으로 확인하세요. KScore 기반 정렬, 토픽별 필터링, 심각도 표시.",
    alternates: {
      canonical,
      languages: { ko: canonical, en: `${canonical}?lang=en`, "x-default": canonical },
    },
    openGraph: {
      title: isEn ? "Real-time Issue Feed | WeWantPeace" : "실시간 이슈 피드 | WeWantPeace",
      description: isEn
        ? "Live feed of global conflict and security issues."
        : "글로벌 분쟁·안보 이슈를 실시간으로 확인하세요.",
      type: "website",
      url: canonical,
      siteName: "WeWantPeace",
    },
  };
}

export default function Page() {
  return <FeedClient />;
}

import type { Metadata } from "next";
import UpgradeClient from "./client";

const SITE_URL = "https://www.wewantpeace.live";

interface Props {
  searchParams: { [key: string]: string | string[] | undefined };
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const isEn = searchParams.lang === "en";
  const canonical = `${SITE_URL}/upgrade`;

  return {
    title: isEn ? "Upgrade to Pro" : "Pro 플랜 업그레이드",
    description: isEn
      ? "Upgrade to WeWantPeace Pro for interactive issue maps, 5 watched countries, KScore filters, 30-day history, and more."
      : "WeWantPeace Pro로 업그레이드하여 인터랙티브 이슈 지도, 5개 관심국가, KScore 필터, 30일 히스토리 등 프리미엄 기능을 이용하세요.",
    alternates: {
      canonical,
      languages: { ko: canonical, en: `${canonical}?lang=en`, "x-default": canonical },
    },
    openGraph: {
      title: isEn ? "Upgrade to Pro | WeWantPeace" : "Pro 플랜 업그레이드 | WeWantPeace",
      description: isEn
        ? "Premium features for deeper global risk analysis."
        : "프리미엄 기능으로 글로벌 리스크를 더 깊이 분석하세요.",
      type: "website",
      url: canonical,
      siteName: "WeWantPeace",
    },
  };
}

export default function Page() {
  return <UpgradeClient />;
}

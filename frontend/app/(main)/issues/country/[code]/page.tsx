import { Metadata } from "next";
import Client from "./client";

export const revalidate = 120;
export const dynamicParams = true;

interface Props {
  params: { code: string };
}

// Country name lookup for metadata
const COUNTRY_NAMES: Record<string, { ko: string; en: string }> = {
  UA: { ko: "우크라이나", en: "Ukraine" },
  RU: { ko: "러시아", en: "Russia" },
  CN: { ko: "중국", en: "China" },
  US: { ko: "미국", en: "United States" },
  KR: { ko: "대한민국", en: "South Korea" },
  KP: { ko: "북한", en: "North Korea" },
  JP: { ko: "일본", en: "Japan" },
  TW: { ko: "대만", en: "Taiwan" },
  IL: { ko: "이스라엘", en: "Israel" },
  PS: { ko: "팔레스타인", en: "Palestine" },
  IR: { ko: "이란", en: "Iran" },
  SY: { ko: "시리아", en: "Syria" },
  MM: { ko: "미얀마", en: "Myanmar" },
  AF: { ko: "아프가니스탄", en: "Afghanistan" },
  SD: { ko: "수단", en: "Sudan" },
  YE: { ko: "예멘", en: "Yemen" },
  ET: { ko: "에티오피아", en: "Ethiopia" },
  SO: { ko: "소말리아", en: "Somalia" },
  LB: { ko: "레바논", en: "Lebanon" },
  IQ: { ko: "이라크", en: "Iraq" },
};

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const code = params.code.toUpperCase();
  const country = COUNTRY_NAMES[code];
  const nameKo = country?.ko || code;
  const nameEn = country?.en || code;

  const title = `${nameKo} (${nameEn}) 이슈 | WeWantPeace`;
  const description = `${nameKo} 관련 분쟁·갈등 이슈를 실시간으로 추적합니다. Track ${nameEn} conflict issues in real time.`;

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "website",
      url: `https://www.wewantpeace.live/issues/country/${code.toLowerCase()}`,
      siteName: "WeWantPeace",
    },
  };
}

export default function Page({ params }: Props) {
  // JSON-LD Place schema
  const code = params.code.toUpperCase();
  const country = COUNTRY_NAMES[code];

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Place",
    name: country ? `${country.ko} (${country.en})` : code,
    url: `https://www.wewantpeace.live/issues/country/${code.toLowerCase()}`,
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <Client />
    </>
  );
}

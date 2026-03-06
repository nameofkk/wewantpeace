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

  const title = `${nameKo} 긴장도`;
  const siteDesc = "WeWantPeace | 실시간 세계정세 모니터링";

  const ogImage = `https://www.wewantpeace.live/issues/country/${code.toLowerCase()}/og`;

  return {
    title,
    description: siteDesc,
    openGraph: {
      title: `${title} | WeWantPeace`,
      description: siteDesc,
      type: "website",
      url: `https://www.wewantpeace.live/issues/country/${code.toLowerCase()}`,
      siteName: "WeWantPeace",
      images: [{ url: ogImage }],
    },
    twitter: {
      card: "summary",
      title: `${title} | WeWantPeace`,
      description: siteDesc,
      images: [{ url: ogImage }],
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

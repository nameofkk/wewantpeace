import { Metadata } from "next";
import Client from "./client";

export const revalidate = 120;
export const dynamicParams = true;

interface Props {
  params: { code: string };
  searchParams: { [key: string]: string | string[] | undefined };
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

// 링크 미리보기·검색 메타데이터는 영어가 기본 (2026-09-30). 한국어는 ?lang=ko.
export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const code = params.code.toUpperCase();
  const isKo = searchParams.lang === "ko";
  const country = COUNTRY_NAMES[code];
  const nameKo = country?.ko || code;
  let nameEn = country?.en || code;
  if (!country) {
    try {
      nameEn = new Intl.DisplayNames(["en"], { type: "region" }).of(code) || code;
    } catch {
      /* 코드 그대로 */
    }
  }

  const titleEn = `${nameEn}: live conflict tracker and weekly brief`;
  const descEn = `What is happening in ${nameEn} right now, checked against multiple independent sources. Free weekly email brief.`;
  const title = isKo ? `${nameKo} 긴장도` : titleEn;
  const desc = isKo ? "195개국 분쟁·안보 실시간 모니터링 플랫폼" : descEn;
  const canonicalUrl = `https://www.wewantpeace.live/issues/country/${code.toLowerCase()}`;
  const ogImage = `${canonicalUrl}/og`;

  return {
    title,
    description: desc,
    alternates: {
      canonical: canonicalUrl,
      languages: { en: canonicalUrl, ko: `${canonicalUrl}?lang=ko`, "x-default": canonicalUrl },
    },
    openGraph: {
      title: `${titleEn} | WeWantPeace`,
      description: descEn,
      type: "website",
      url: canonicalUrl,
      siteName: "WeWantPeace",
      locale: "en_US",
      images: [{ url: ogImage, width: 1200, height: 630, type: "image/png" }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${titleEn} | WeWantPeace`,
      description: descEn,
      images: [{ url: ogImage, width: 1200, height: 630 }],
    },
  };
}

export default function Page({ params }: Props) {
  // JSON-LD Place schema
  const code = params.code.toUpperCase();
  const country = COUNTRY_NAMES[code];

  const countryUrl = `https://www.wewantpeace.live/issues/country/${code.toLowerCase()}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebPage",
        name: country ? `${country.ko} (${country.en}) | Tension Index` : `${code} Tension Index`,
        url: countryUrl,
        description: country
          ? `Real-time tension index and conflict analysis for ${country.en} (${country.ko}). Live monitoring of security events, KScore impact scoring, and historical trend data.`
          : `Real-time conflict monitoring for ${code}.`,
        inLanguage: ["ko", "en"],
        about: {
          "@type": "Place",
          name: country?.en || code,
        },
        isPartOf: {
          "@id": "https://www.wewantpeace.live/#website",
        },
        publisher: {
          "@id": "https://www.wewantpeace.live/#organization",
        },
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: "https://www.wewantpeace.live" },
          { "@type": "ListItem", position: 2, name: "Tension Index", item: "https://www.wewantpeace.live/tension" },
          { "@type": "ListItem", position: 3, name: country?.en || code, item: countryUrl },
        ],
      },
    ],
  };

  return (
    <>
      {/* SAFE: JSON-LD 구조화 데이터. JSON.stringify로 직렬화되어 XSS 불가 */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <Client />
    </>
  );
}

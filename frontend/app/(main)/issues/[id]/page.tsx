import { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchIssueServer } from "@/lib/server/issues";
import IssueDetailClient from "./client";

export const revalidate = 120;
export const dynamicParams = true;

interface Props {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
}

const SITE_URL = "https://www.wewantpeace.live";
const SITE_DESC = "195개국 분쟁·안보 실시간 모니터링 플랫폼";

export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const issue = await fetchIssueServer(params.id);
  const lang = searchParams.lang === "en" ? "en" : "ko";
  const isEn = lang === "en";

  if (!issue) {
    return {
      title: "WeWantPeace",
      description: isEn ? "Real-time monitoring of conflicts across 195 countries" : SITE_DESC,
      openGraph: {
        title: "WeWantPeace",
        description: isEn ? "Real-time monitoring of conflicts across 195 countries" : SITE_DESC,
        type: "website",
        url: SITE_URL,
        siteName: "WeWantPeace",
        images: [{ url: `${SITE_URL}/og-image.png?v=4` }],
      },
      twitter: {
        card: "summary_large_image",
        title: "WeWantPeace",
        description: isEn ? "Real-time monitoring of conflicts across 195 countries" : SITE_DESC,
        images: [{ url: `${SITE_URL}/og-image-twitter.png?v=4` }],
      },
    };
  }

  const title = isEn ? (issue.title || issue.title_ko || "Issue") : (issue.title_ko || issue.title || "이슈");
  // 카카오톡: og:title이 길면 description이 완전히 숨겨짐
  // 영어 글자는 좁아서 35자까지 허용, 한국어는 25자
  const maxOgTitle = isEn ? 35 : 25;
  let ogTitle: string = title;
  if (title.length > maxOgTitle) {
    const cut = title.lastIndexOf(" ", maxOgTitle);
    ogTitle = (cut > 8 ? title.slice(0, cut) : title.slice(0, maxOgTitle)) + "…";
  }

  const langSuffix = isEn ? "?lang=en" : "";
  const ogImage = `${SITE_URL}/issues/${issue.id}/og${langSuffix}`;
  const pageUrl = `${SITE_URL}/issues/${issue.id}${langSuffix}`;
  const severity = issue.severity ?? 0;
  const eventCount = issue.event_count ?? 0;
  const weatherEmoji = severity >= 80 ? "🌪️" : severity >= 60 ? "⛈️" : severity >= 40 ? "🌥️" : severity >= 20 ? "⛅" : "☀️";
  const soWhat = isEn
    ? (issue.so_what_consumer || issue.so_what_line || `${eventCount} reports`)
    : (issue.so_what_consumer || issue.so_what_line || `${eventCount}건 보도`);
  const walletPart = issue.wallet_line ? ` · 💰 ${issue.wallet_line}` : "";
  const desc = isEn
    ? `${weatherEmoji} ${soWhat}${walletPart} — WeWantPeace`
    : `${weatherEmoji} ${soWhat}${walletPart} — WeWantPeace`;

  const canonicalUrl = `${SITE_URL}/issues/${issue.id}`;

  return {
    title,
    description: desc,
    alternates: {
      canonical: canonicalUrl,
      languages: {
        ko: canonicalUrl,
        en: `${canonicalUrl}?lang=en`,
        "x-default": canonicalUrl,
      },
    },
    openGraph: {
      title: ogTitle,
      description: desc,
      type: "website",
      url: canonicalUrl,
      siteName: "WeWantPeace",
      images: [{ url: ogImage, width: 1200, height: 630, type: "image/png" }],
    },
    twitter: {
      card: "summary_large_image",
      title: ogTitle,
      description: desc,
      images: [{ url: ogImage, width: 1200, height: 630 }],
    },
  };
}

export default async function Page({ params }: Props) {
  const issue = await fetchIssueServer(params.id);
  if (!issue) notFound();

  // JSON-LD NewsArticle + BreadcrumbList
  const pageUrl = `https://www.wewantpeace.live/issues/${issue.id}`;
  const jsonLd = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "NewsArticle",
        headline: issue.title_ko || issue.title,
        alternativeHeadline: issue.title || issue.title_ko,
        datePublished: issue.first_event_at,
        dateModified: issue.last_event_at,
        description: `Severity ${issue.severity}/100 crisis. ${issue.event_count} verified source reports. Real-time conflict monitoring by WeWantPeace.`,
        url: pageUrl,
        mainEntityOfPage: pageUrl,
        inLanguage: ["ko", "en"],
        about: {
          "@type": "Thing",
          name: issue.topic || "Global Conflict",
        },
        ...(issue.country_code && {
          spatialCoverage: {
            "@type": "Place",
            name: issue.country_code,
          },
        }),
        publisher: {
          "@type": "Organization",
          "@id": "https://www.wewantpeace.live/#organization",
          name: "WeWantPeace",
          url: "https://www.wewantpeace.live",
          logo: {
            "@type": "ImageObject",
            url: "https://www.wewantpeace.live/logo-eye.png",
          },
        },
        image: `${pageUrl}/og`,
        isAccessibleForFree: true,
      },
      {
        "@type": "BreadcrumbList",
        itemListElement: [
          { "@type": "ListItem", position: 1, name: "Home", item: "https://www.wewantpeace.live" },
          { "@type": "ListItem", position: 2, name: "Issues", item: "https://www.wewantpeace.live/feed" },
          { "@type": "ListItem", position: 3, name: issue.title_ko || issue.title, item: pageUrl },
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
      <IssueDetailClient initialData={issue} />
    </>
  );
}

import { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchIssueServer } from "@/lib/server/issues";
import IssueDetailClient from "./client";

export const revalidate = 3600;
export const dynamicParams = true;

interface Props {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
}

const SITE_URL = "https://www.wewantpeace.live";
const SITE_DESC = "195개국 분쟁·안보 실시간 모니터링 플랫폼";

// 링크 미리보기·검색 메타데이터는 영어가 기본 (2026-09-30).
// 예전엔 ?lang=en 이 없으면 한국어였고, 스레드 답글 링크(?ref=threads)에 lang 이 없어
// 해외 사용자(실방문의 90%)가 한국어 제목·이미지를 봤다. 한국어는 ?lang=ko.
export async function generateMetadata({ params, searchParams }: Props): Promise<Metadata> {
  const issue = await fetchIssueServer(params.id);
  const isKo = searchParams.lang === "ko";

  if (!issue) {
    const d = isKo ? SITE_DESC : "Real-time monitoring of conflicts across 195 countries";
    return {
      title: "WeWantPeace",
      description: d,
      openGraph: {
        title: "WeWantPeace", description: d, type: "website", url: SITE_URL, siteName: "WeWantPeace",
        locale: "en_US", images: [{ url: `${SITE_URL}/og-image.png?v=5`, width: 1200, height: 630 }],
      },
      twitter: { card: "summary_large_image", title: "WeWantPeace", description: d,
        images: [{ url: `${SITE_URL}/og-image.png?v=5` }] },
    };
  }

  const titleEn = issue.title || issue.title_ko || "Conflict update";
  const title = isKo ? (issue.title_ko || titleEn) : titleEn;
  const ogImage = `${SITE_URL}/issues/${issue.id}/og`;
  const canonicalUrl = `${SITE_URL}/issues/${issue.id}`;
  const sources = new Set(
    (issue.events || []).filter((e) => (e.source_tier || "D") !== "D" && e.source_name).map((e) => e.source_name),
  ).size;
  const eventCount = issue.event_count ?? 0;
  const descEn = `${sources > 0 ? `${sources} independent sources · ` : ""}${eventCount} reports · Live conflict tracking by WeWantPeace`;
  const desc = isKo ? `독립 출처 ${sources}곳 · 보도 ${eventCount}건 · 실시간 세계 분쟁 모니터링` : descEn;

  return {
    title,
    description: desc,
    alternates: {
      canonical: canonicalUrl,
      languages: { en: canonicalUrl, ko: `${canonicalUrl}?lang=ko`, "x-default": canonicalUrl },
    },
    openGraph: {
      // 미리보기는 공유되는 곳(스레드 등)이 영어권이라 항상 영어
      title: titleEn,
      description: descEn,
      type: "article",
      url: canonicalUrl,
      siteName: "WeWantPeace",
      locale: "en_US",
      images: [{ url: ogImage, width: 1200, height: 630, type: "image/png" }],
    },
    twitter: {
      card: "summary_large_image",
      title: titleEn,
      description: descEn,
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
        headline: issue.title || issue.title_ko,
        alternativeHeadline: issue.title_ko || issue.title,
        datePublished: issue.first_event_at,
        dateModified: issue.last_event_at,
        description: `${issue.event_count} reports. Real-time conflict monitoring by WeWantPeace.`,
        url: pageUrl,
        mainEntityOfPage: pageUrl,
        inLanguage: ["en", "ko"],
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
          { "@type": "ListItem", position: 3, name: issue.title || issue.title_ko, item: pageUrl },
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

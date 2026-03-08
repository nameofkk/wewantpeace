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
  // 25자 이내로 강제 절단하여 description 영역 확보
  let ogTitle: string = title;
  if (title.length > 25) {
    const cut = title.lastIndexOf(" ", 25);
    ogTitle = (cut > 8 ? title.slice(0, cut) : title.slice(0, 25)) + "…";
  }

  const langSuffix = isEn ? "?lang=en" : "";
  const ogImage = `${SITE_URL}/issues/${issue.id}/og${langSuffix}`;
  const pageUrl = `${SITE_URL}/issues/${issue.id}${langSuffix}`;
  // 이슈별 구체적 description (generic 대신)
  const severity = issue.severity ?? 0;
  const eventCount = issue.event_count ?? 0;
  const desc = isEn
    ? `Severity ${severity} | ${eventCount} reports — Real-time conflict monitoring`
    : `위기지수 ${severity} | ${eventCount}건 보도 — 실시간 분쟁 모니터링`;

  return {
    title,
    description: desc,
    openGraph: {
      title: ogTitle,
      description: desc,
      type: "website",
      url: pageUrl,
      siteName: "WeWantPeace",
      images: [{ url: ogImage }],
    },
    twitter: {
      card: "summary_large_image",
      title: ogTitle,
      description: desc,
      images: [{ url: ogImage }],
    },
  };
}

export default async function Page({ params }: Props) {
  const issue = await fetchIssueServer(params.id);
  if (!issue) notFound();

  // JSON-LD NewsArticle
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    headline: issue.title_ko || issue.title,
    datePublished: issue.first_event_at,
    dateModified: issue.last_event_at,
    description: `Severity ${issue.severity}, ${issue.event_count} source reports`,
    url: `https://www.wewantpeace.live/issues/${issue.id}`,
    publisher: {
      "@type": "Organization",
      name: "WeWantPeace",
      url: "https://www.wewantpeace.live",
    },
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <IssueDetailClient initialData={issue} />
    </>
  );
}

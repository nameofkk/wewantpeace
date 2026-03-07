import { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchIssueServer } from "@/lib/server/issues";
import IssueDetailClient from "./client";

export const revalidate = 120;
export const dynamicParams = true;

interface Props {
  params: { id: string };
}

const SITE_URL = "https://www.wewantpeace.live";
const SITE_DESC = "195개국 분쟁·안보 실시간 모니터링 플랫폼";

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const issue = await fetchIssueServer(params.id);
  if (!issue) {
    return {
      title: "WeWantPeace",
      description: SITE_DESC,
      openGraph: {
        title: "WeWantPeace | 실시간 글로벌 분쟁 모니터링",
        description: SITE_DESC,
        type: "website",
        url: SITE_URL,
        siteName: "WeWantPeace",
        images: [{ url: `${SITE_URL}/og-image.png?v=3` }],
      },
      twitter: {
        card: "summary_large_image",
        title: "WeWantPeace | 실시간 글로벌 분쟁 모니터링",
        description: SITE_DESC,
        images: [{ url: `${SITE_URL}/og-image-twitter.png?v=3` }],
      },
    };
  }

  const title = issue.title_ko || issue.title;
  // 카카오톡: og:title이 길면 description 영역을 밀어내서 숨김
  // 띄어쓰기 기준으로 자연스럽게 자름
  let ogTitle = title;
  if (title.length > 40) {
    const cut = title.lastIndexOf(" ", 40);
    ogTitle = (cut > 10 ? title.slice(0, cut) : title.slice(0, 40)) + "…";
  }

  const ogImage = `${SITE_URL}/issues/${issue.id}/og`;

  return {
    title,
    description: SITE_DESC,
    openGraph: {
      title: ogTitle,
      description: SITE_DESC,
      type: "website",
      url: `${SITE_URL}/issues/${issue.id}`,
      siteName: "WeWantPeace",
      images: [{ url: ogImage }],
    },
    twitter: {
      card: "summary_large_image",
      title: ogTitle,
      description: SITE_DESC,
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

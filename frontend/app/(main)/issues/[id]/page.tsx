import { Metadata } from "next";
import { notFound } from "next/navigation";
import { fetchIssueServer } from "@/lib/server/issues";
import IssueDetailClient from "./client";

export const revalidate = 120;
export const dynamicParams = true;

interface Props {
  params: { id: string };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const issue = await fetchIssueServer(params.id);
  if (!issue) {
    return { title: "Issue Not Found" };
  }

  const title = issue.title_ko || issue.title;
  const description = `${title} — 위기지수 ${issue.severity}, 보도 ${issue.event_count}건 | WeWantPeace 실시간 세계정세 모니터링`;

  return {
    title,
    description,
    openGraph: {
      title: `${title} | WeWantPeace`,
      description,
      type: "article",
      url: `https://www.wewantpeace.live/issues/${issue.id}`,
      siteName: "WeWantPeace",
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} | WeWantPeace`,
      description,
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

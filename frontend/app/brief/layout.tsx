import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Weekly country brief",
  description:
    "One calm email a week about the countries you follow: what happened, why it matters and what to watch, with the number of independent sources behind each point.",
  alternates: { canonical: "https://www.wewantpeace.live/brief" },
  // 루트 openGraph(사이트 제목)를 물려받지 않도록 이 페이지 것을 따로 적는다
  openGraph: {
    title: "Weekly country brief | WeWantPeace",
    description: "One calm email a week about the countries you follow, checked against multiple independent sources.",
    type: "website",
    url: "https://www.wewantpeace.live/brief",
    siteName: "WeWantPeace",
    locale: "en_US",
    images: [{ url: "https://www.wewantpeace.live/og-image.png?v=5", width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Weekly country brief | WeWantPeace",
    images: ["https://www.wewantpeace.live/og-image.png?v=5"],
  },
};

export default function BriefLayout({ children }: { children: React.ReactNode }) {
  return children;
}

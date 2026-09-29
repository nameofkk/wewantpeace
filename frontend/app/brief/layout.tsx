import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Weekly country brief",
  description:
    "One calm email a week about the countries you follow: what happened, why it matters and what to watch, with the number of independent sources behind each point.",
  alternates: { canonical: "https://www.wewantpeace.live/brief" },
};

export default function BriefLayout({ children }: { children: React.ReactNode }) {
  return children;
}

import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";
import {
  API_BASE, CoverCard, OG_SIZE, cleanHeadline, countryName, isTemplateTitle, loadPhoto, ogFonts,
  photoCandidates, sourceCount, fallbackPhoto,
} from "@/lib/server/og-card";

export const runtime = "nodejs";

// 이슈 링크 미리보기 — 항상 영어 (2026-09-30 리디자인, lib/server/og-card.tsx 참고)
export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const fonts = await ogFonts();

  type Issue = {
    title: string; title_ko?: string | null; country_code?: string | null; image_url?: string | null;
    last_event_at?: string; events?: { title: string; image_url?: string | null; source_tier?: string | null;
      source_name?: string | null }[];
  };
  let issue: Issue | null = null;
  try {
    const res = await fetch(`${API_BASE}/issues/${params.id}`, {
      next: { revalidate: 600 },
      signal: AbortSignal.timeout(10000),
    });
    if (res.ok) issue = await res.json();
    else console.error(`[OG] issue ${params.id} → ${res.status}`);
  } catch (e) {
    console.error("[OG] fetch error:", e instanceof Error ? e.message : e);
  }

  if (!issue) {
    return new ImageResponse(
      <CoverCard headline="Conflict news, checked against multiple sources" chips={[{ text: "Live tracking", kind: "cc" }]} />,
      { ...OG_SIZE, fonts },
    );
  }

  const events = issue.events || [];
  const country = countryName(issue.country_code);
  // 자동 템플릿 제목("Palestine Conflict")이면 가장 믿을 만한 출처 기사 제목으로 대신한다
  const rank: Record<string, number> = { A: 0, B: 1, C: 2 };
  const bestEvent = [...events]
    .filter((e) => (e.source_tier || "D") !== "D" && e.title)
    .sort((a, b) => (rank[a.source_tier || ""] ?? 3) - (rank[b.source_tier || ""] ?? 3))[0];
  const rawTitle = isTemplateTitle(issue.title) && bestEvent ? bestEvent.title : issue.title;
  const headline = cleanHeadline(rawTitle || issue.title_ko || "Conflict update");
  const n = sourceCount(events);
  const date = issue.last_event_at
    ? new Date(issue.last_event_at).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" })
    : "";
  const photo = await loadPhoto(photoCandidates(events, issue.image_url));

  return new ImageResponse(
    <CoverCard
      headline={headline}
      highlight={country && headline.toLowerCase().includes(country.toLowerCase()) ? country : undefined}
      chips={[
        { text: [country, date].filter(Boolean).join(" · "), kind: "cc" },
        { text: n > 0 ? `${n} source${n === 1 ? "" : "s"}` : "", kind: "src" },
      ]}
      photo={photo ?? (await fallbackPhoto())}
    />,
    {
      ...OG_SIZE,
      fonts,
      headers: { "Cache-Control": "public, max-age=600, s-maxage=3600, stale-while-revalidate=86400" },
    },
  );
}

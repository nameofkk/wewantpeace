import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";
import {
  API_BASE, CoverCard, OG_SIZE, cleanHeadline, countryName, isTemplateTitle, loadPhoto, ogFonts,
  photoCandidates, fallbackPhoto,
} from "@/lib/server/og-card";

export const runtime = "nodejs";

// 나라 페이지 링크 미리보기 — 항상 영어 (2026-09-30 리디자인).
// 예전 카드는 긴장도 숫자(대부분 99~100에 붙어 있었다)와 7일 선 그래프, 템플릿 제목 두 줄이었다.
// 이제 "이 나라에서 지금 가장 큰 이슈" 헤드라인 + 기사 사진 + 활성 이슈 수.
export async function GET(_req: NextRequest, { params }: { params: { code: string } }) {
  const fonts = await ogFonts();
  const cc = (params.code || "").toUpperCase();
  const country = countryName(cc);

  type Cluster = { id: string; title: string; image_url?: string | null };
  let clusters: Cluster[] = [];
  try {
    const res = await fetch(`${API_BASE}/issues?country_code=${cc}&limit=30&sort_by=kscore`, {
      next: { revalidate: 900 },
      signal: AbortSignal.timeout(10000),
    });
    if (res.ok) clusters = await res.json();
  } catch (e) {
    console.error("[OG] country fetch error:", e instanceof Error ? e.message : e);
  }

  const top = clusters.find((c) => !isTemplateTitle(c.title));
  let photo: { src: string; credit: string } | null = null;
  if (top) {
    try {
      const res = await fetch(`${API_BASE}/issues/${top.id}`, {
        next: { revalidate: 900 },
        signal: AbortSignal.timeout(10000),
      });
      if (res.ok) {
        const detail = await res.json();
        photo = await loadPhoto(photoCandidates(detail.events || [], top.image_url, top.title));
      }
    } catch {
      /* 사진 없이 */
    }
  }

  const headline = top ? cleanHeadline(top.title, 90) : `${country}: what is happening and why it matters`;
  const n = clusters.length;

  return new ImageResponse(
    <CoverCard
      headline={headline}
      highlight={headline.toLowerCase().includes(country.toLowerCase()) ? country : undefined}
      dek={`Follow ${country} with a free weekly brief`}
      chips={[
        { text: `${country} · last 48 hours`, kind: "cc" },
        // 목록을 30개까지만 받으므로 30 이면 상한이지 실제 개수가 아니다
        { text: n >= 30 ? "30+ active issues" : n > 0 ? `${n} active issue${n === 1 ? "" : "s"}` : "", kind: "src" },
      ]}
      photo={photo ?? (await fallbackPhoto())}
    />,
    {
      ...OG_SIZE,
      fonts,
      headers: { "Cache-Control": "public, max-age=900, s-maxage=3600, stale-while-revalidate=86400" },
    },
  );
}

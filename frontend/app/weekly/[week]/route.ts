import type { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 주간 브리핑 웹판 — 메일의 "브라우저로 보기"·다른 언어판 링크 (worker/weekly/render.py web_url).
// 백엔드가 메일과 같은 HTML 을 그려 주고, 여기서는 사이트 주소로 그대로 내보낸다.
export async function GET(req: NextRequest, { params }: { params: { week: string } }) {
  const week = params.week;
  if (!/^(\d{4}-W\d{2}|latest)$/.test(week)) {
    return new Response("Not found", { status: 404 });
  }
  const lang = req.nextUrl.searchParams.get("lang") === "ko" ? "ko" : "en";
  const res = await fetch(`${API_BASE}/newsletter/weekly/${week}?lang=${lang}`, { cache: "no-store" });
  if (!res.ok) {
    return new Response(lang === "ko" ? "이 호를 찾을 수 없어요." : "This issue was not found.", {
      status: res.status === 404 ? 404 : 502,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
  return new Response(await res.text(), {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "public, max-age=600" },
  });
}

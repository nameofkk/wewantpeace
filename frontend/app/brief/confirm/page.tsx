"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";

// 확인 메일 링크 도착지 — 누르는 순간 구독이 활성화된다.
export default function BriefConfirmPage() {
  const [state, setState] = useState<"loading" | "ok" | "bad">("loading");
  const [info, setInfo] = useState<{ email?: string; countries?: string[] }>({});
  const [ko, setKo] = useState(false);

  useEffect(() => {
    setKo((navigator.language || "").startsWith("ko"));
    const token = new URLSearchParams(window.location.search).get("token") || "";
    if (!token) return setState("bad");
    fetch(`${API_BASE}/briefs/confirm?token=${encodeURIComponent(token)}`)
      .then(async (r) => {
        if (!r.ok) throw new Error();
        setInfo(await r.json());
        setState("ok");
      })
      .catch(() => setState("bad"));
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-xl px-4 py-16">
        <Link href="/" className="text-sm font-semibold tracking-tight">WeWantPeace</Link>
        <div className="mt-10 rounded-xl border border-border bg-card p-6">
          {state === "loading" && <p className="text-sm text-muted-foreground">…</p>}
          {state === "ok" && (
            <>
              <h1 className="text-lg font-semibold mb-2">{ko ? "구독이 확인되었습니다" : "You're subscribed"}</h1>
              <p className="text-sm text-muted-foreground">
                {ko
                  ? `${info.countries?.join(", ")} 주간 브리프를 ${info.email} 로 보내 드립니다.`
                  : `The weekly brief on ${info.countries?.join(", ")} will go to ${info.email}.`}
              </p>
            </>
          )}
          {state === "bad" && (
            <>
              <h1 className="text-lg font-semibold mb-2">{ko ? "링크가 올바르지 않습니다" : "This link doesn't work"}</h1>
              <p className="text-sm text-muted-foreground">
                {ko ? "다시 신청해 주세요." : "Please subscribe again."}{" "}
                <Link href="/brief" className="underline underline-offset-2">/brief</Link>
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

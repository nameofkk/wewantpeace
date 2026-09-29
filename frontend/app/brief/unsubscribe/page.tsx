"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { API_BASE } from "@/lib/api";

// 브리프 메일 하단 수신거부 링크 도착지. 메일 클라이언트의 링크 미리 열기로 해지되지 않도록
// 화면에서 버튼을 눌러야 해지한다.
export default function BriefUnsubscribePage() {
  const [token, setToken] = useState("");
  const [info, setInfo] = useState<{ email?: string; status?: string } | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "done" | "bad">("loading");
  const [ko, setKo] = useState(false);

  useEffect(() => {
    setKo((navigator.language || "").startsWith("ko"));
    const t = new URLSearchParams(window.location.search).get("token") || "";
    setToken(t);
    if (!t) return setState("bad");
    fetch(`${API_BASE}/briefs/unsubscribe?token=${encodeURIComponent(t)}`)
      .then(async (r) => {
        if (!r.ok) throw new Error();
        const d = await r.json();
        setInfo(d);
        setState(d.status === "unsubscribed" ? "done" : "ready");
      })
      .catch(() => setState("bad"));
  }, []);

  async function unsubscribe() {
    const r = await fetch(`${API_BASE}/briefs/unsubscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    setState(r.ok ? "done" : "bad");
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto max-w-xl px-4 py-16">
        <Link href="/" className="text-sm font-semibold tracking-tight">WeWantPeace</Link>
        <div className="mt-10 rounded-xl border border-border bg-card p-6">
          {state === "loading" && <p className="text-sm text-muted-foreground">…</p>}
          {state === "ready" && (
            <>
              <h1 className="text-lg font-semibold mb-2">{ko ? "수신거부" : "Unsubscribe"}</h1>
              <p className="text-sm text-muted-foreground mb-4">
                {ko ? `${info?.email} 로 가는 주간 브리프를 멈춥니다.` : `Stop the weekly brief to ${info?.email}.`}
              </p>
              <button
                type="button"
                onClick={unsubscribe}
                className="rounded-lg bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground hover:bg-primary/90"
              >
                {ko ? "수신거부" : "Unsubscribe"}
              </button>
            </>
          )}
          {state === "done" && (
            <h1 className="text-lg font-semibold">{ko ? "수신거부되었습니다. 더 이상 보내지 않습니다." : "You're unsubscribed. No more emails."}</h1>
          )}
          {state === "bad" && (
            <h1 className="text-lg font-semibold">{ko ? "링크가 올바르지 않습니다" : "This link doesn't work"}</h1>
          )}
        </div>
      </div>
    </div>
  );
}

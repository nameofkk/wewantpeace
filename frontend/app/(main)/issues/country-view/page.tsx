"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import dynamic from "next/dynamic";

// 동적 import — country/[code]/client.tsx는 토스 빌드 시 비활성화되므로
// 직접 API에서 fetch하는 간단한 국가 이슈 목록 구현
const CountryIssuesInner = dynamic(() => import("./inner"), { ssr: false });

export default function CountryViewPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col min-h-screen animate-pulse">
        <div className="sticky top-0 z-20 flex items-center gap-3 px-4 py-3 border-b border-border bg-background">
          <div className="h-5 w-5 rounded bg-muted" />
          <div className="h-5 w-32 rounded bg-muted" />
        </div>
        <div className="flex-1 p-4 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 rounded-xl border border-border bg-card" />
          ))}
        </div>
      </div>
    }>
      <CountryIssuesInner />
    </Suspense>
  );
}

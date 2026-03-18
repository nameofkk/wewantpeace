"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import IssueDetailClient from "../[id]/client";

function IssueViewInner() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";

  if (!id) {
    return (
      <div className="flex items-center justify-center min-h-screen text-muted-foreground">
        이슈를 찾을 수 없습니다.
      </div>
    );
  }

  // initialData 없이 전달 → client.tsx가 useClusterDetail(id)로 API에서 fetch
  return <IssueDetailClient initialData={{ id } as any} />;
}

export default function IssueViewPage() {
  return (
    <Suspense fallback={
      <div className="flex flex-col min-h-screen animate-pulse">
        <div className="sticky top-0 z-20 flex items-center gap-3 px-4 py-3 border-b border-border bg-background">
          <div className="h-5 w-5 rounded bg-muted" />
          <div className="h-5 w-40 rounded bg-muted" />
        </div>
        <div className="flex-1 p-4 space-y-4">
          <div className="h-6 w-3/4 rounded bg-muted" />
          <div className="rounded-xl border border-border bg-card p-4 space-y-3">
            <div className="h-4 w-24 rounded bg-muted" />
            <div className="h-2 w-full rounded-full bg-muted" />
          </div>
        </div>
      </div>
    }>
      <IssueViewInner />
    </Suspense>
  );
}

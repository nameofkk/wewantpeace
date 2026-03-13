"use client";

export function DashboardSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {/* Risk Summary skeleton */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-3 mb-3">
          <div className="h-10 w-10 rounded-lg bg-secondary" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-32 rounded bg-secondary" />
            <div className="h-5 w-20 rounded bg-secondary" />
          </div>
        </div>
        <div className="h-2 rounded-full bg-secondary" />
      </div>

      {/* Watchlist skeleton */}
      <div className="flex gap-2 overflow-hidden">
        {[0, 1, 2].map((i) => (
          <div key={i} className="shrink-0 w-32 h-24 rounded-lg border border-border bg-card p-3">
            <div className="h-3 w-16 rounded bg-secondary mb-2" />
            <div className="h-6 w-12 rounded bg-secondary mb-1" />
            <div className="h-2 w-10 rounded bg-secondary" />
          </div>
        ))}
      </div>

      {/* Top Issues skeleton */}
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <div key={i} className="h-16 rounded-lg border border-border bg-card animate-pulse" style={{ animationDelay: `${i * 80}ms` }} />
        ))}
      </div>
    </div>
  );
}

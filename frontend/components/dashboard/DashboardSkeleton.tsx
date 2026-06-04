"use client";

function ShimmerBlock({ className }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded bg-secondary ${className || ""}`}>
      <div className="absolute inset-0 -translate-x-full animate-[shimmer_1.5s_infinite] bg-gradient-to-r from-transparent via-white/5 to-transparent" />
    </div>
  );
}

export function DashboardSkeleton() {
  return (
    <div className="space-y-5">
      {/* Notice ticker skeleton */}
      <ShimmerBlock className="h-8 rounded-lg" />

      {/* Risk Summary skeleton */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-3 mb-3">
          <ShimmerBlock className="h-12 w-12 rounded-xl" />
          <div className="flex-1 space-y-2">
            <ShimmerBlock className="h-4 w-32 rounded" />
            <ShimmerBlock className="h-5 w-20 rounded" />
          </div>
          <div className="space-y-1 text-right">
            <ShimmerBlock className="h-7 w-12 rounded" />
            <ShimmerBlock className="h-3 w-8 rounded ml-auto" />
          </div>
        </div>
        <ShimmerBlock className="h-2.5 rounded-full" />
      </div>

      {/* Watchlist skeleton */}
      <div>
        <ShimmerBlock className="h-3 w-24 rounded mb-2" />
        <div className="flex gap-2 overflow-hidden">
          {[0, 1, 2].map((i) => (
            <div key={i} className="shrink-0 w-[140px] rounded-xl border border-border bg-card p-3">
              <ShimmerBlock className="h-4 w-20 rounded mb-2" />
              <ShimmerBlock className="h-6 w-14 rounded mb-1" />
              <ShimmerBlock className="h-3 w-12 rounded" />
            </div>
          ))}
        </div>
      </div>

      {/* Top Issues skeleton */}
      <div>
        <ShimmerBlock className="h-3 w-20 rounded mb-2" />
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-[68px] rounded-xl border border-border bg-card overflow-hidden"
              style={{ animationDelay: `${i * 80}ms` }}
            >
              <ShimmerBlock className="h-full w-full !rounded-xl" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

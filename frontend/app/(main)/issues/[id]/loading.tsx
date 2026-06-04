export default function IssueDetailLoading() {
  return (
    <div className="flex flex-col min-h-screen animate-pulse">
      {/* 헤더 바 */}
      <div className="sticky top-0 z-20 flex items-center gap-3 px-4 py-3 border-b border-border bg-background">
        <div className="h-5 w-5 rounded bg-muted" />
        <div className="h-5 w-40 rounded bg-muted" />
      </div>

      <div className="flex-1 p-4 space-y-4">
        {/* 제목 + 배지 */}
        <div className="space-y-2">
          <div className="h-6 w-3/4 rounded bg-muted" />
          <div className="flex gap-2">
            <div className="h-5 w-16 rounded-full bg-muted" />
            <div className="h-5 w-20 rounded-full bg-muted" />
          </div>
        </div>

        {/* KScore 카드 */}
        <div className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="h-4 w-24 rounded bg-muted" />
            <div className="h-8 w-12 rounded bg-muted" />
          </div>
          <div className="h-2 w-full rounded-full bg-muted" />
        </div>

        {/* 지도 영역 */}
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="h-48 bg-muted" />
        </div>

        {/* 이벤트 타임라인 */}
        <div className="space-y-3">
          <div className="h-4 w-32 rounded bg-muted" />
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex gap-3">
              <div className="h-7 w-7 rounded-lg bg-muted shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-full rounded bg-muted" />
                <div className="h-3 w-2/3 rounded bg-muted" />
                <div className="h-3 w-24 rounded bg-muted" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

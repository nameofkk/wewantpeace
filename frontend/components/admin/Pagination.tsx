import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  prevLabel?: string;
  nextLabel?: string;
  pageLabel?: string;
}

export function Pagination({ page, totalPages, onPageChange, prevLabel = "Prev", nextLabel = "Next", pageLabel }: PaginationProps) {
  if (totalPages <= 1) return null;

  const pages: (number | "...")[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pages.push(i);
  } else {
    pages.push(1);
    if (page > 3) pages.push("...");
    for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
      pages.push(i);
    }
    if (page < totalPages - 2) pages.push("...");
    pages.push(totalPages);
  }

  return (
    <div className="flex items-center justify-center gap-1.5 mt-4">
      <button
        onClick={() => onPageChange(Math.max(1, page - 1))}
        disabled={page === 1}
        className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-secondary transition-colors"
      >
        {prevLabel}
      </button>
      {pages.map((p, i) =>
        p === "..." ? (
          <span key={`ellipsis-${i}`} className="px-1 text-sm text-muted-foreground">...</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={cn(
              "rounded-lg px-2.5 py-1.5 text-sm tabular-nums transition-colors",
              p === page
                ? "bg-primary/10 text-primary font-medium border border-primary/30"
                : "border border-border text-muted-foreground hover:bg-secondary"
            )}
          >
            {p}
          </button>
        )
      )}
      <button
        onClick={() => onPageChange(Math.min(totalPages, page + 1))}
        disabled={page >= totalPages}
        className="rounded-lg border border-border px-3 py-1.5 text-sm disabled:opacity-50 hover:bg-secondary transition-colors"
      >
        {nextLabel}
      </button>
    </div>
  );
}

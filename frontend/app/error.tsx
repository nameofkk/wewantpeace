"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // 에러 로깅 (Sentry 등)
    console.error("Global error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center">
      <AlertTriangle className="h-12 w-12 text-red-400 mb-4" />
      <h2 className="text-lg font-bold mb-2">문제가 발생했습니다</h2>
      <p className="text-sm text-muted-foreground mb-6 max-w-xs">
        일시적인 오류입니다. 잠시 후 다시 시도해 주세요.
        {error.digest && (
          <span className="block mt-1 text-[10px] font-mono text-muted-foreground/60">
            오류 코드: {error.digest}
          </span>
        )}
      </p>
      <button
        onClick={reset}
        className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <RefreshCw className="h-4 w-4" />
        다시 시도
      </button>
    </div>
  );
}

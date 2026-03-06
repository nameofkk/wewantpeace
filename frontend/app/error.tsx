"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const lang = useAppStore((s) => s.lang);

  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center">
      <AlertTriangle className="h-12 w-12 text-red-400 mb-4" />
      <h2 className="text-lg font-bold mb-2">{t(lang, "error_title")}</h2>
      <p className="text-sm text-muted-foreground mb-6 max-w-xs">
        {t(lang, "error_message")}
        {error.digest && (
          <span className="block mt-1 text-[10px] font-mono text-muted-foreground/60">
            {t(lang, "error_code")}: {error.digest}
          </span>
        )}
      </p>
      <button
        onClick={reset}
        className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <RefreshCw className="h-4 w-4" />
        {t(lang, "error_retry")}
      </button>
    </div>
  );
}

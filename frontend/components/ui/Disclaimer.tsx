"use client";

import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { Info } from "lucide-react";

export function Disclaimer() {
  const lang = useAppStore((s) => s.lang);

  return (
    <div className="rounded-lg bg-muted/30 border border-border/40 px-3 py-2.5 mt-4">
      <div className="flex items-start gap-2">
        <Info className="h-3.5 w-3.5 text-muted-foreground shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-[10px] text-muted-foreground leading-relaxed">
            {t(lang, "dash_disclaimer")}
          </p>
          <p className="text-[9px] text-muted-foreground/60">
            {t(lang, "dash_ai_estimate")}
          </p>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

interface SourceBadgeProps {
  tier: "A" | "B" | "C" | "D" | string;
  className?: string;
  showDesc?: boolean;
}

const TIER_CONFIG = {
  A: { label: "A", color: "text-blue-400 border-blue-400/40 bg-blue-400/10", descKey: "source_tier_A_desc" as const },
  B: { label: "B", color: "text-green-400 border-green-400/40 bg-green-400/10", descKey: "source_tier_B_desc" as const },
  C: { label: "C", color: "text-yellow-400 border-yellow-400/40 bg-yellow-400/10", descKey: "source_tier_C_desc" as const },
  D: { label: "D", color: "text-gray-400 border-gray-400/40 bg-gray-400/10", descKey: "source_tier_D_desc" as const },
};

export function SourceBadge({ tier, className = "", showDesc = false }: SourceBadgeProps) {
  const lang = useAppStore((s) => s.lang);
  const config = TIER_CONFIG[tier as keyof typeof TIER_CONFIG] ?? TIER_CONFIG.D;
  const desc = t(lang, config.descKey);

  return (
    <span className={showDesc ? "inline-flex flex-col items-center gap-0.5" : "inline-flex"}>
      <span
        className={`inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 text-[10px] font-bold leading-none ${config.color} ${className}`}
        title={`Tier ${tier}: ${desc}`}
      >
        {tier}
      </span>
      {showDesc && (
        <span className="text-[9px] text-muted-foreground leading-none whitespace-nowrap">
          {desc}
        </span>
      )}
    </span>
  );
}

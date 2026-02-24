"use client";

interface SourceBadgeProps {
  tier: "A" | "B" | "C" | "D" | string;
  className?: string;
}

const TIER_CONFIG = {
  A: { label: "A", color: "text-blue-400 border-blue-400/40 bg-blue-400/10", desc: "공식·주요언론" },
  B: { label: "B", color: "text-green-400 border-green-400/40 bg-green-400/10", desc: "신뢰도 높음" },
  C: { label: "C", color: "text-yellow-400 border-yellow-400/40 bg-yellow-400/10", desc: "중립" },
  D: { label: "D", color: "text-gray-400 border-gray-400/40 bg-gray-400/10", desc: "미검증" },
};

export function SourceBadge({ tier, className = "" }: SourceBadgeProps) {
  const config = TIER_CONFIG[tier as keyof typeof TIER_CONFIG] ?? TIER_CONFIG.D;
  return (
    <span
      className={`inline-flex items-center gap-0.5 rounded border px-1.5 py-0.5 text-[10px] font-bold leading-none ${config.color} ${className}`}
      title={`Tier ${tier}: ${config.desc}`}
    >
      {tier}
    </span>
  );
}

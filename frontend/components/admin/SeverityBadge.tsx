import { cn } from "@/lib/utils";

const SEVERITY_COLORS: Record<number, string> = {
  0: "bg-secondary text-muted-foreground",
  1: "bg-green-500/20 text-green-400",
  2: "bg-yellow-500/20 text-yellow-400",
  3: "bg-orange-500/20 text-orange-400",
  4: "bg-red-500/20 text-red-400",
  5: "bg-red-600/30 text-red-300",
};

interface SeverityBadgeProps {
  severity: number;
  className?: string;
}

export function SeverityBadge({ severity, className }: SeverityBadgeProps) {
  return (
    <span className={cn(
      "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold tabular-nums",
      SEVERITY_COLORS[severity] ?? SEVERITY_COLORS[0],
      className,
    )}>
      {severity}
    </span>
  );
}

export { SEVERITY_COLORS };

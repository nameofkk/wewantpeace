import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string | number;
  subText?: string;
  icon: LucideIcon;
  iconColor?: string;
  iconBg?: string;
}

export function StatCard({ label, value, subText, icon: Icon, iconColor = "text-primary", iconBg = "bg-primary/10" }: StatCardProps) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
        <div className={cn("rounded-lg p-1", iconBg)}>
          <Icon className={cn("h-3.5 w-3.5", iconColor)} />
        </div>
        {label}
      </div>
      <p className="text-lg font-bold tabular-nums">{typeof value === "number" ? value.toLocaleString() : value}</p>
      {subText && <p className="text-[10px] text-muted-foreground mt-0.5">{subText}</p>}
    </div>
  );
}

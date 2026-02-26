"use client";

interface KScoreBarProps {
  kscore: number;   // 0 ~ 5 (이론적 최대값)
  showLabel?: boolean;
  className?: string;
}

const KSCORE_MAX = 5.0;  // 바 100% 기준값

function kscoreColor(k: number): string {
  if (k >= 3.0) return "from-red-500 to-red-400";
  if (k >= 2.0) return "from-orange-500 to-orange-400";
  if (k >= 1.0) return "from-yellow-500 to-yellow-400";
  return "from-green-500 to-green-400";
}

function kscoreLabel(k: number): string {
  if (k >= 3.0) return "매우 높음";
  if (k >= 2.0) return "높음";
  if (k >= 1.0) return "보통";
  return "낮음";
}

export function KScoreBar({ kscore, showLabel = true, className = "" }: KScoreBarProps) {
  const pct = Math.min(100, Math.round((kscore / KSCORE_MAX) * 100));
  const gradient = kscoreColor(kscore);
  const label = kscoreLabel(kscore);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showLabel && (
        <span className="text-[10px] text-muted-foreground w-10 shrink-0">KScore</span>
      )}
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${gradient} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-medium text-right w-16 shrink-0 text-muted-foreground">
        {kscore.toFixed(2)} <span className="text-foreground">{label}</span>
      </span>
    </div>
  );
}

"use client";

interface ConfidenceBarProps {
  confidence: number; // 0.0 ~ 1.0
  showLabel?: boolean;
  className?: string;
}

function confidenceColor(c: number): string {
  if (c >= 0.8) return "from-green-500 to-green-400";
  if (c >= 0.6) return "from-yellow-500 to-yellow-400";
  if (c >= 0.4) return "from-orange-500 to-orange-400";
  return "from-red-500 to-red-400";
}

function confidenceLabel(c: number): string {
  if (c >= 0.8) return "높음";
  if (c >= 0.6) return "보통";
  if (c >= 0.4) return "낮음";
  return "불확실";
}

export function ConfidenceBar({ confidence, showLabel = true, className = "" }: ConfidenceBarProps) {
  const pct = Math.round(confidence * 100);
  const gradient = confidenceColor(confidence);
  const label = confidenceLabel(confidence);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {showLabel && (
        <span className="text-[10px] text-muted-foreground w-10 shrink-0">신뢰도</span>
      )}
      <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full bg-gradient-to-r ${gradient} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] font-medium text-right w-16 shrink-0 text-muted-foreground">
        {pct}% <span className="text-foreground">{label}</span>
      </span>
    </div>
  );
}

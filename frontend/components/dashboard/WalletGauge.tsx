"use client";

import { cn } from "@/lib/utils";
import { t } from "@/lib/i18n";

interface CommodityInfo {
  price: number;
  change_pct: number;
  symbol: string;
}

interface WalletGaugeProps {
  energy: number;
  food: number;
  finance: number;
  travel: number;
  lang: "ko" | "en";
  commoditySnapshot?: Record<string, CommodityInfo> | null;
}

const CATEGORIES = [
  { key: "energy", emoji: "⛽", labelKo: "에너지", labelEn: "Energy", snapKey: "oil" },
  { key: "food", emoji: "🌾", labelKo: "식품", labelEn: "Groceries", snapKey: "wheat" },
  { key: "finance", emoji: "📈", labelKo: "금융", labelEn: "Finance", snapKey: "gold" },
  { key: "travel", emoji: "✈️", labelKo: "여행", labelEn: "Travel", snapKey: null },
] as const;

function dotColor(dots: number): string {
  if (dots >= 5) return "#991B1B";
  if (dots >= 4) return "#EF4444";
  if (dots >= 3) return "#F97316";
  if (dots >= 2) return "#EAB308";
  return "#22C55E";
}

function changePctText(pct: number): string {
  if (pct > 0) return `+${pct.toFixed(1)}%`;
  if (pct < 0) return `${pct.toFixed(1)}%`;
  return "0.0%";
}

export function WalletGauge({ energy, food, finance, travel, lang, commoditySnapshot }: WalletGaugeProps) {
  const values = { energy, food, finance, travel };

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-1.5 mb-3">
        <span className="text-xs font-bold text-foreground">
          {lang === "ko" ? "내 지갑 영향" : "How It Hits Your Wallet"}
        </span>
      </div>
      <div className="space-y-2.5">
        {CATEGORIES.map((cat) => {
          const dots = values[cat.key as keyof typeof values];
          const color = dotColor(dots);
          const snap = cat.snapKey && commoditySnapshot?.[cat.snapKey];

          return (
            <div key={cat.key} className="flex items-center gap-2">
              <span className="text-sm shrink-0 w-5 text-center">{cat.emoji}</span>
              <span className="text-[10px] font-medium text-foreground w-10 shrink-0">
                {lang === "ko" ? cat.labelKo : cat.labelEn}
              </span>

              {/* Price + Change */}
              <div className="flex-1 min-w-0 flex items-center gap-1.5">
                {snap ? (
                  <>
                    <span className="text-[10px] font-bold tabular-nums text-foreground">
                      ${snap.price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </span>
                    <span
                      className={cn(
                        "text-[9px] font-medium tabular-nums",
                        snap.change_pct > 0 ? "text-red-500" : snap.change_pct < 0 ? "text-blue-500" : "text-muted-foreground"
                      )}
                    >
                      {changePctText(snap.change_pct)}
                    </span>
                  </>
                ) : (
                  <span className="text-[9px] text-muted-foreground/50">—</span>
                )}
              </div>

              {/* Dot Gauge */}
              <div className="flex items-center gap-0.5 shrink-0">
                {Array.from({ length: 5 }, (_, i) => (
                  <span
                    key={i}
                    className={cn(
                      "inline-block h-2 w-2 rounded-full",
                      i >= dots && "bg-muted"
                    )}
                    style={i < dots ? { backgroundColor: color } : undefined}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
      {/* Disclaimer */}
      <p className="text-[8px] text-muted-foreground/40 mt-2.5 leading-tight">
        {lang === "ko"
          ? "본 정보는 참고용이며 투자 자문이 아닙니다."
          : "For informational purposes only. Not financial advice."}
      </p>
    </div>
  );
}

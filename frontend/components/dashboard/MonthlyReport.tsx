"use client";

import { cn } from "@/lib/utils";

interface MonthlyReportProps {
  energy: number;    // 0-5
  food: number;
  finance: number;
  travel: number;
  streakDays: number;
  month: string;     // "4월" or "April"
  lang: "ko" | "en";
  onShare?: () => void;
}

const CATEGORIES = [
  { key: "energy", emoji: "⛽", labelKo: "에너지", labelEn: "Energy" },
  { key: "food", emoji: "🌾", labelKo: "식품", labelEn: "Groceries" },
  { key: "finance", emoji: "📈", labelKo: "금융", labelEn: "Finance" },
  { key: "travel", emoji: "✈️", labelKo: "여행", labelEn: "Travel" },
] as const;

function impactLabel(dots: number, lang: "ko" | "en"): string {
  if (dots >= 5) return lang === "ko" ? "영향 매우 큼" : "Very High";
  if (dots >= 4) return lang === "ko" ? "영향 큼" : "High";
  if (dots >= 3) return lang === "ko" ? "영향 중간" : "Moderate";
  if (dots >= 2) return lang === "ko" ? "영향 낮음" : "Low";
  return lang === "ko" ? "영향 없음" : "None";
}

function barColor(dots: number): string {
  if (dots >= 5) return "#991B1B";
  if (dots >= 4) return "#EF4444";
  if (dots >= 3) return "#F97316";
  if (dots >= 2) return "#EAB308";
  return "#22C55E";
}

export function MonthlyReport({ energy, food, finance, travel, streakDays, month, lang, onShare }: MonthlyReportProps) {
  const values = { energy, food, finance, travel };

  const shareText = lang === "ko"
    ? `🌍 ${month} 분쟁 영향 리포트\n⛽ 에너지: ${impactLabel(energy, "ko")}\n🌾 식품: ${impactLabel(food, "ko")}\n📈 금융: ${impactLabel(finance, "ko")}\n✈️ 여행: ${impactLabel(travel, "ko")}\n🔥 ${streakDays}일 연속 확인\n\n👉 나도 확인하기: https://wewantpeace.org`
    : `🌍 ${month} Conflict Impact Report\n⛽ Energy: ${impactLabel(energy, "en")}\n🌾 Groceries: ${impactLabel(food, "en")}\n📈 Finance: ${impactLabel(finance, "en")}\n✈️ Travel: ${impactLabel(travel, "en")}\n🔥 ${streakDays}-day streak\n\n👉 Check yours: https://wewantpeace.org`;

  const handleShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({ text: shareText });
      } catch { /* cancelled */ }
    } else {
      await navigator.clipboard.writeText(shareText);
      onShare?.();
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-1.5 mb-3">
        <span className="text-xs">🌍</span>
        <span className="text-xs font-bold text-foreground">
          {lang === "ko" ? `${month} 분쟁 영향 리포트` : `${month} Conflict Impact Report`}
        </span>
      </div>

      <div className="space-y-2">
        {CATEGORIES.map((cat) => {
          const dots = values[cat.key as keyof typeof values];
          const color = barColor(dots);
          const pct = (dots / 5) * 100;
          return (
            <div key={cat.key} className="flex items-center gap-2">
              <span className="text-sm shrink-0 w-5 text-center">{cat.emoji}</span>
              <span className="text-[10px] font-medium text-foreground w-10 shrink-0">
                {lang === "ko" ? cat.labelKo : cat.labelEn}
              </span>
              <div className="flex-1 h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{ width: `${pct}%`, backgroundColor: color }}
                />
              </div>
              <span className="text-[9px] text-muted-foreground w-16 text-right shrink-0">
                {impactLabel(dots, lang)}
              </span>
            </div>
          );
        })}
      </div>

      {streakDays > 0 && (
        <p className="text-[10px] text-foreground/70 mt-2">
          🔥 {streakDays}{lang === "ko" ? "일 연속 확인" : "-day streak"}
        </p>
      )}

      <button
        onClick={handleShare}
        className="w-full mt-3 rounded-lg py-2 text-xs font-bold bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
      >
        {lang === "ko" ? "공유하기" : "Share"}
      </button>
    </div>
  );
}

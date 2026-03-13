"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { cn } from "@/lib/utils";
import { getFlag, getCountryName } from "@/lib/countries";
import { useAppStore } from "@/lib/store";
import { useTensionMine, type TensionAllItem } from "@/lib/api";
import { t } from "@/lib/i18n";
import { MapPin, Plus } from "lucide-react";

function tensionColor(score: number) {
  if (score >= 80) return { border: "border-l-red-900", text: "text-red-700 dark:text-red-300", bg: "bg-red-900/10" };
  if (score >= 60) return { border: "border-l-red-500", text: "text-red-600 dark:text-red-400", bg: "bg-red-500/10" };
  if (score >= 40) return { border: "border-l-orange-500", text: "text-orange-600 dark:text-orange-300", bg: "bg-orange-500/10" };
  if (score >= 20) return { border: "border-l-amber-500", text: "text-amber-600 dark:text-amber-300", bg: "bg-amber-500/10" };
  return { border: "border-l-emerald-500", text: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10" };
}

function tensionLabel(score: number, lang: "ko" | "en") {
  if (score >= 80) return lang === "ko" ? "극심" : "Extreme";
  if (score >= 60) return lang === "ko" ? "심각" : "Severe";
  if (score >= 40) return lang === "ko" ? "경계" : "Alert";
  if (score >= 20) return lang === "ko" ? "주의" : "Caution";
  return lang === "ko" ? "안정" : "Stable";
}

export function WatchlistQuickStatus() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const myCountries = useAppStore((s) => s.myCountries);

  const { data: tensionData } = useTensionMine(myCountries.length > 0 ? myCountries : null);
  const tensions = (tensionData as TensionAllItem[] | undefined) ?? [];

  // 빈 상태
  if (myCountries.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-card/50 p-5 text-center fade-in-up">
        <MapPin className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm font-medium mb-1">{t(lang, "dash_watchlist_empty")}</p>
        <Link
          href="/settings?section=countries"
          className="inline-flex items-center gap-1 mt-2 rounded-full bg-primary px-3 py-1.5 text-xs font-bold text-primary-foreground"
        >
          <Plus className="h-3 w-3" />
          {t(lang, "dash_watchlist_add")}
        </Link>
      </div>
    );
  }

  // 국가별 텐션 매핑
  const tensionMap = new Map(tensions.map((t: any) => [t.country_code, t]));

  return (
    <div className="fade-in-up">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
          {t(lang, "dash_watchlist")}
        </h3>
        <Link
          href="/settings?section=countries"
          className="text-[10px] text-primary hover:underline"
        >
          {lang === "ko" ? "편집" : "Edit"}
        </Link>
      </div>

      <div className="flex gap-2 overflow-x-auto scrollbar-hide pb-1">
        {myCountries.map((code) => {
          const data = tensionMap.get(code) as TensionAllItem | undefined;
          const score = data?.raw_score ?? 0;
          const color = tensionColor(score);
          return (
            <div
              key={code}
              onClick={() => router.push(`/tension?country=${code}`)}
              className={cn(
                "shrink-0 w-32 rounded-lg border border-border bg-card p-3 cursor-pointer",
                "hover:bg-card/80 transition-all border-l-4",
                color.border,
              )}
            >
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className="text-base">{getFlag(code)}</span>
                <span className="text-[11px] font-medium truncate">
                  {getCountryName(code, lang)}
                </span>
              </div>
              <div className="flex items-baseline gap-1">
                <span className={cn("text-lg font-bold tabular-nums", color.text)}>
                  {score}
                </span>
                <span className="text-[9px] text-muted-foreground">/100</span>
              </div>
              <span className={cn("text-[10px] font-medium", color.text)}>
                {tensionLabel(score, lang)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

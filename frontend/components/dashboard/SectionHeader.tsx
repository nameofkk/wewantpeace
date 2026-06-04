"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t, type TranslationKey } from "@/lib/i18n";
import { Info, X } from "lucide-react";

interface SectionHeaderProps {
  icon: React.ReactNode;
  titleKey: TranslationKey;
  subtitleKey?: TranslationKey;
  descKey?: TranslationKey;
  badge?: { label: string; color: string };
  right?: React.ReactNode;
}

export function SectionHeader({
  icon,
  titleKey,
  subtitleKey,
  descKey,
  badge,
  right,
}: SectionHeaderProps) {
  const lang = useAppStore((s) => s.lang);
  const [showInfo, setShowInfo] = useState(false);

  return (
    <div className="mb-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            {t(lang, titleKey)}
          </h3>
          {badge && (
            <span
              className={cn(
                "text-[9px] px-1.5 py-0.5 rounded-full font-bold",
                badge.color
              )}
            >
              {badge.label}
            </span>
          )}
          {descKey && (
            <button
              onClick={() => setShowInfo(!showInfo)}
              className="p-0.5 rounded-full hover:bg-muted/50 transition-colors"
              aria-label={t(lang, "dash_section_info")}
            >
              <Info className="h-3 w-3 text-muted-foreground/50" />
            </button>
          )}
        </div>
        {right}
      </div>
      {subtitleKey && (
        <p className="text-[10px] text-muted-foreground/70 mt-0.5 ml-6">
          {t(lang, subtitleKey)}
        </p>
      )}
      {showInfo && descKey && (
        <div className="mt-2 ml-1 rounded-lg bg-muted/30 border border-border/40 px-3 py-2 flex items-start gap-2 fade-in-up">
          <Info className="h-3.5 w-3.5 text-blue-400 shrink-0 mt-0.5" />
          <p className="text-[10px] text-muted-foreground leading-relaxed flex-1">
            {t(lang, descKey)}
          </p>
          <button
            onClick={() => setShowInfo(false)}
            className="p-0.5 rounded-full hover:bg-muted/50 shrink-0"
          >
            <X className="h-3 w-3 text-muted-foreground" />
          </button>
        </div>
      )}
    </div>
  );
}

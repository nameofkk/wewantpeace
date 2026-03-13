"use client";

import Link from "next/link";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { useMe } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Lock, Sparkles, TrendingUp } from "lucide-react";

export function ProTeaser() {
  const lang = useAppStore((s) => s.lang);
  const { data: me } = useMe();
  const meObj = me as { plan?: string } | undefined;
  const plan = meObj?.plan ?? "free";

  // Pro+ 유저: Phase 3 Coming Soon
  if (plan === "pro_plus") {
    return (
      <div className="rounded-xl border border-border bg-card/50 p-4 fade-in-up">
        <div className="flex items-center gap-2 mb-2">
          <Sparkles className="h-4 w-4 text-purple-400" />
          <span className="text-xs font-bold text-purple-400">{t(lang, "dash_sector_impact")}</span>
        </div>
        <p className="text-[11px] text-muted-foreground">{t(lang, "dash_coming_soon")}</p>
      </div>
    );
  }

  // Pro 유저: Impact Brief Coming Soon + Sector Impact teaser
  if (plan === "pro") {
    return (
      <div className="space-y-2 fade-in-up">
        <div className="rounded-xl border border-border bg-card/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="h-4 w-4 text-blue-400" />
            <span className="text-xs font-bold text-blue-400">{t(lang, "dash_impact_brief")}</span>
          </div>
          <p className="text-[11px] text-muted-foreground">{t(lang, "dash_coming_soon")}</p>
        </div>
        <div className="rounded-xl border border-border bg-card/50 p-4">
          <div className="flex items-center gap-2 mb-2">
            <Lock className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs font-bold text-muted-foreground">{t(lang, "dash_sector_impact")}</span>
          </div>
          <p className="text-[11px] text-muted-foreground mb-2">{t(lang, "dash_coming_soon")}</p>
          <Link
            href="/upgrade"
            className="inline-flex items-center gap-1 rounded-full px-3 py-1.5 text-[10px] font-bold text-white"
            style={{ background: "linear-gradient(to right, #7c3aed, #6366f1)" }}
          >
            {t(lang, "dash_unlock_pro_plus")}
          </Link>
        </div>
      </div>
    );
  }

  // Free 유저: 모두 잠금
  return (
    <div className="rounded-xl border border-border bg-card/50 p-4 fade-in-up">
      <div className="flex items-center gap-2 mb-3">
        <Lock className="h-4 w-4 text-muted-foreground" />
        <span className="text-xs font-bold text-muted-foreground">
          {lang === "ko" ? "Pro 전용 기능" : "Pro Features"}
        </span>
      </div>

      <div className="space-y-2">
        {/* Impact Brief teaser */}
        <div className="rounded-lg bg-muted/30 p-3 blur-[1px] select-none pointer-events-none">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-3.5 w-3.5 text-blue-400/50" />
            <span className="text-[11px] font-medium text-foreground/50">{t(lang, "dash_impact_brief")}</span>
          </div>
          <div className="mt-1.5 h-2 w-3/4 rounded bg-muted" />
          <div className="mt-1 h-2 w-1/2 rounded bg-muted" />
        </div>

        {/* Sector Impact teaser */}
        <div className="rounded-lg bg-muted/30 p-3 blur-[1px] select-none pointer-events-none">
          <div className="flex items-center gap-2">
            <Sparkles className="h-3.5 w-3.5 text-purple-400/50" />
            <span className="text-[11px] font-medium text-foreground/50">{t(lang, "dash_sector_impact")}</span>
          </div>
          <div className="mt-1.5 h-2 w-2/3 rounded bg-muted" />
          <div className="mt-1 h-2 w-1/3 rounded bg-muted" />
        </div>
      </div>

      <Link
        href="/upgrade"
        className="flex items-center justify-center gap-1.5 mt-3 rounded-full py-2 text-xs font-bold text-white w-full"
        style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
      >
        {t(lang, "dash_unlock_pro")}
      </Link>
    </div>
  );
}

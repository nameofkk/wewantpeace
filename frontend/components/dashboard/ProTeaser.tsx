"use client";

import Link from "next/link";
import { useAppStore } from "@/lib/store";
import { useMe } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Lock, Sparkles, TrendingUp } from "lucide-react";

const DEMO_BRIEF = {
  ko: {
    title: "글로벌 안보 영향도",
    score: 67,
    summary: "우크라이나·팔레스타인 분쟁 장기화로 글로벌 에너지·방산 시장에 영향...",
    sectors: [
      { name: "에너지", impact: 72 },
      { name: "방위산업", impact: 58 },
      { name: "무역", impact: 45 },
    ],
  },
  en: {
    title: "Global Security Impact",
    score: 67,
    summary: "Prolonged conflicts in Ukraine and Palestine affecting global energy and defense markets...",
    sectors: [
      { name: "Energy", impact: 72 },
      { name: "Defense", impact: 58 },
      { name: "Trade", impact: 45 },
    ],
  },
};

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

  // Free 유저: 데모 Impact Brief 표시
  const demo = DEMO_BRIEF[lang === "ko" ? "ko" : "en"];
  const circumference = 2 * Math.PI * 36;
  const strokeOffset = circumference - (demo.score / 100) * circumference;

  return (
    <div className="rounded-xl border border-border bg-card/50 p-4 fade-in-up relative overflow-hidden">
      {/* Demo banner */}
      <div className="flex items-center gap-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-1.5 mb-3">
        <span className="text-[10px] font-medium text-amber-400">
          {t(lang, "demo_banner_impact")}
        </span>
      </div>

      {/* Blurred demo content */}
      <div className="relative">
        <div className="select-none pointer-events-none opacity-40" style={{ filter: "blur(2px)" }}>
          {/* Title */}
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="h-4 w-4 text-blue-400" />
            <span className="text-xs font-bold text-blue-400">{demo.title}</span>
          </div>

          {/* Score gauge circle */}
          <div className="flex items-center gap-4 mb-3">
            <div className="relative w-20 h-20 shrink-0">
              <svg className="w-20 h-20 -rotate-90" viewBox="0 0 80 80">
                <circle cx="40" cy="40" r="36" fill="none" stroke="currentColor" strokeWidth="6" className="text-muted/30" />
                <circle
                  cx="40" cy="40" r="36" fill="none" strokeWidth="6"
                  stroke="#3b82f6"
                  strokeLinecap="round"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeOffset}
                />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-lg font-bold tabular-nums">
                {demo.score}
              </span>
            </div>
            <p className="text-[11px] text-foreground/70 leading-relaxed">{demo.summary}</p>
          </div>

          {/* Sector impact bars */}
          <div className="space-y-2">
            {demo.sectors.map((s) => (
              <div key={s.name} className="flex items-center gap-2">
                <span className="text-[10px] w-14 text-muted-foreground shrink-0">{s.name}</span>
                <div className="flex-1 h-2 rounded-full bg-muted/30 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500"
                    style={{ width: `${s.impact}%` }}
                  />
                </div>
                <span className="text-[10px] font-bold tabular-nums w-6 text-right">{s.impact}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Gradient overlay */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-card/90 pointer-events-none" />
      </div>

      {/* CTA button */}
      <Link
        href="/upgrade?source=demo_impact"
        className="flex items-center justify-center gap-1.5 mt-3 rounded-full py-2 text-xs font-bold text-white w-full relative z-10"
        style={{ background: "linear-gradient(to right, #2563eb, #6366f1)" }}
      >
        {t(lang, "demo_cta_pro")}
      </Link>
    </div>
  );
}

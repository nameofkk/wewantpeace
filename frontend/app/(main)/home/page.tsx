"use client";

import React, { Suspense } from "react";
import { useAppStore } from "@/lib/store";
import { useMe } from "@/lib/api";
import { t } from "@/lib/i18n";
import { LogoIcon } from "@/components/ui/logo-icon";
import { RiskSummaryHeader } from "@/components/dashboard/RiskSummaryHeader";
import { WatchlistQuickStatus } from "@/components/dashboard/WatchlistQuickStatus";
import { TopIssuesAffectingMe } from "@/components/dashboard/TopIssuesAffectingMe";
import { ProTeaser } from "@/components/dashboard/ProTeaser";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { Disclaimer } from "@/components/ui/Disclaimer";

export default function HomePage() {
  return (
    <Suspense fallback={<div className="p-4"><DashboardSkeleton /></div>}>
      <DashboardContent />
    </Suspense>
  );
}

function DashboardContent() {
  const lang = useAppStore((s) => s.lang);
  const { data: me, isLoading } = useMe();
  const meObj = me as { plan?: string } | undefined;
  const userPlan = meObj?.plan ?? "free";

  if (isLoading) {
    return (
      <div className="p-4">
        <DashboardSkeleton />
      </div>
    );
  }

  return (
    <div className="flex flex-col" style={{ height: "calc(100dvh - 60px)" }}>
      {/* Header */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 pt-4 pb-3">
        <div className="flex items-center justify-between mb-1">
          <div>
            <h1 className="text-sm font-bold">{t(lang, "dash_title")}</h1>
            <p className="text-[10px] text-muted-foreground mt-0.5">
              {t(lang, "dash_subtitle")}
            </p>
          </div>
          <LogoIcon height={24} hideText />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
        {/* 1. Risk Summary */}
        <RiskSummaryHeader />

        {/* 2. Watchlist Quick Status */}
        <WatchlistQuickStatus />

        {/* 3. Top Issues Affecting Me */}
        <TopIssuesAffectingMe />

        {/* 4. Pro Feature Teaser */}
        <ProTeaser />

        {/* 5. Disclaimer */}
        <Disclaimer />
      </div>
    </div>
  );
}

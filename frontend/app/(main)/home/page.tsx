"use client";

import React, { Suspense, useState, useMemo, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { useMe, useTrackBehavior } from "@/lib/api";
import { t } from "@/lib/i18n";
import { LogoIcon } from "@/components/ui/logo-icon";
import { RiskSummaryHeader } from "@/components/dashboard/RiskSummaryHeader";
import { WatchlistQuickStatus } from "@/components/dashboard/WatchlistQuickStatus";
import { TopIssuesAffectingMe } from "@/components/dashboard/TopIssuesAffectingMe";
import { ImpactBriefCard } from "@/components/dashboard/ImpactBriefCard";
import { SectorImpactCard } from "@/components/dashboard/SectorImpactCard";
import { TradeFlowSankey } from "@/components/dashboard/TradeFlowSankey";
import { WeeklyReportCard } from "@/components/dashboard/WeeklyReportCard";
import { DashboardSkeleton } from "@/components/dashboard/DashboardSkeleton";
import { NoticeTicker } from "@/components/dashboard/NoticeTicker";
import { Disclaimer } from "@/components/ui/Disclaimer";
import AppTour from "@/components/ui/AppTour";
import TourHelpButton from "@/components/ui/TourHelpButton";
import type { Step } from "react-joyride";

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
  const [tourRun, setTourRun] = useState(false);

  // Phase 5: 대시보드 방문 이벤트 트래킹
  const trackBehavior = useTrackBehavior();
  useEffect(() => {
    trackBehavior.mutate({ event_name: "dashboard_view", props: { plan: userPlan } });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const dashTourSteps: Step[] = useMemo(() => [
    {
      target: "[data-tour='dash-page']",
      content: t(lang, "tour_dash_page_role"),
      placement: "center" as const,
      disableBeacon: true,
    },
    {
      target: "[data-tour='dash-risk']",
      content: t(lang, "tour_dash_risk"),
    },
    {
      target: "[data-tour='dash-watchlist']",
      content: t(lang, "tour_dash_watchlist"),
    },
    {
      target: "[data-tour='dash-top-issues']",
      content: t(lang, "tour_dash_top_issues"),
    },
  ], [lang]);

  if (isLoading) {
    return (
      <div className="p-4">
        <DashboardSkeleton />
      </div>
    );
  }

  return (
    <div className="flex flex-col" data-tour="dash-page" style={{ height: "calc(100dvh - 60px)" }}>
      <AppTour tourId="dashboard" steps={dashTourSteps} run={tourRun} onComplete={() => setTourRun(false)} />
      <TourHelpButton tourId="dashboard" onStartTour={() => setTourRun(true)} />

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

      {/* Notice Ticker */}
      <NoticeTicker />

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-6">
        {/* 1. Risk Summary */}
        <div data-tour="dash-risk">
          <RiskSummaryHeader />
        </div>

        {/* 2. Watchlist Quick Status */}
        <div data-tour="dash-watchlist">
          <WatchlistQuickStatus />
        </div>

        {/* 3. Top Issues Affecting Me */}
        <div data-tour="dash-top-issues">
          <TopIssuesAffectingMe />
        </div>

        {/* 4. Impact Brief (Phase 2 - 모든 플랜) */}
        <ImpactBriefCard />

        {/* 5. Sector Impact Analysis (Phase 3 - Pro+) */}
        <SectorImpactCard />

        {/* 6. Trade Flow Sankey (Phase 6 - Pro+) */}
        <TradeFlowSankey />

        {/* 7. Weekly Report (Phase 4 - Pro+) */}
        <WeeklyReportCard />

        {/* 8. Disclaimer */}
        <Disclaimer />
      </div>
    </div>
  );
}

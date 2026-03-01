"use client";

import { BottomNav } from "@/components/ui/bottom-nav";
import { NewEventBanner } from "@/components/ui/new-event-banner";
import { PWAInstallPrompt } from "@/components/ui/pwa-install-prompt";
import { SmartAppBanner } from "@/components/ui/smart-app-banner";
import { useMe, useClusters } from "@/lib/api";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  // 레이아웃 마운트 시 공통 데이터 프리페치 (하위 페이지에서 캐시 히트)
  useMe();
  useClusters({ limit: "2000" });

  return (
    <>
      <NewEventBanner />
      <main className="pb-[60px]">{children}</main>
      <BottomNav />
      <PWAInstallPrompt />
      <SmartAppBanner />
    </>
  );
}

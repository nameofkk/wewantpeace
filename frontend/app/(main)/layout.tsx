"use client";

import { useEffect } from "react";
import { BottomNav } from "@/components/ui/bottom-nav";
import { NewEventBanner } from "@/components/ui/new-event-banner";
import { PWAInstallPrompt } from "@/components/ui/pwa-install-prompt";
import { SmartAppBanner } from "@/components/ui/smart-app-banner";
import { useMe, useMyAreas } from "@/lib/api";
import { useAppStore } from "@/lib/store";

/** DB에 저장된 관심국가를 localStorage(Zustand)에 동기화 — DB가 항상 진실의 원천 */
function CountrySync() {
  const { data: areas } = useMyAreas();
  const setMyCountries = useAppStore((s) => s.setMyCountries);

  useEffect(() => {
    if (!areas) return; // 로딩 중
    // DB 기준으로 localStorage를 항상 덮어씀 (중복 제거)
    const dbCodes = [...new Set(areas.map((a) => a.country_code))];
    setMyCountries(dbCodes);
  }, [areas, setMyCountries]);

  return null;
}

export default function MainLayout({ children }: { children: React.ReactNode }) {
  // 레이아웃 마운트 시 사용자 정보 프리페치 (하위 페이지에서 캐시 히트)
  useMe();

  return (
    <>
      <CountrySync />
      <NewEventBanner />
      <main className="pb-[60px]">{children}</main>
      <BottomNav />
      <PWAInstallPrompt />
      <SmartAppBanner />
    </>
  );
}

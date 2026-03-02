"use client";

import { useEffect } from "react";
import { BottomNav } from "@/components/ui/bottom-nav";
import { NewEventBanner } from "@/components/ui/new-event-banner";
import { PWAInstallPrompt } from "@/components/ui/pwa-install-prompt";
import { SmartAppBanner } from "@/components/ui/smart-app-banner";
import { useMe, useMyAreas } from "@/lib/api";
import { useAppStore } from "@/lib/store";

/** DB에 저장된 관심국가를 localStorage(Zustand)에 동기화 */
function CountrySync() {
  const { data: areas } = useMyAreas();
  const myCountries = useAppStore((s) => s.myCountries);
  const setMyCountries = useAppStore((s) => s.setMyCountries);

  useEffect(() => {
    if (!areas || areas.length === 0) return;
    // DB에 관심국가가 있는데 localStorage가 비어있으면 DB에서 복원 (중복 제거)
    const dbCodes = [...new Set(areas.map((a) => a.country_code))];
    if (myCountries.length === 0 && dbCodes.length > 0) {
      setMyCountries(dbCodes);
    }
  }, [areas, myCountries.length, setMyCountries]);

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

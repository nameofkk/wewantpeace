"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { BottomNav } from "@/components/ui/bottom-nav";
import { NewEventBanner } from "@/components/ui/new-event-banner";
import { PWAInstallPrompt } from "@/components/ui/pwa-install-prompt";
import { SmartAppBanner } from "@/components/ui/smart-app-banner";
import { useMe, useMyAreas } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { useAuth } from "@/lib/auth";

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

/** 로그인됐는데 등록 미완료(닉네임/약관동의 없음)인 유저를 등록 페이지로 리다이렉트 */
function RegistrationGuard() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { data: me, isLoading: meLoading } = useMe();

  useEffect(() => {
    if (authLoading || meLoading) return;
    if (!user) return; // 비로그인 유저는 게스트로 이용 가능
    if (!me) return;
    // 닉네임 또는 약관동의가 없으면 등록 폼으로 리다이렉트
    if (!me.nickname || !me.agreed_terms_at) {
      router.replace("/login");
    }
  }, [authLoading, meLoading, user, me, router]);

  return null;
}

export default function MainLayout({ children }: { children: React.ReactNode }) {
  // 레이아웃 마운트 시 사용자 정보 프리페치 (하위 페이지에서 캐시 히트)
  useMe();

  return (
    <>
      <CountrySync />
      <RegistrationGuard />
      <NewEventBanner />
      <main className="pb-[60px]">{children}</main>
      <BottomNav />
      <PWAInstallPrompt />
      <SmartAppBanner />
    </>
  );
}

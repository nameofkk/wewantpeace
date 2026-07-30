"use client";

import { useEffect, useCallback } from "react";
import { useRouter, usePathname } from "next/navigation";
import { BottomNav } from "@/components/ui/bottom-nav";
import { isTossMiniApp } from "@/lib/platform";
import { NewEventBanner } from "@/components/ui/new-event-banner";
import { PWAInstallPrompt } from "@/components/ui/pwa-install-prompt";
import { SmartAppBanner } from "@/components/ui/smart-app-banner";
import WelcomeModal from "@/components/ui/WelcomeModal";
import { OnboardingBanner } from "@/components/ui/OnboardingBanner";
import { useMe, useMyAreas } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { useAuth } from "@/lib/auth";
import { updateLastActive, checkAndResetSession } from "@/lib/session";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

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

/** 서버 plan을 localStorage(Zustand)에 동기화 — DB가 항상 진실의 원천
 *
 * userPlan은 store에 persist되는데, 서버값과 맞추는 코드가 /feed와 /settings 두 곳에만
 * 있었다. 그래서 어드민에서 플랜을 올려도 그 두 페이지를 방문하기 전까지는
 * localStorage에 남은 옛 값("free")이 계속 쓰였다.
 * PaywallModal·UpgradeNudgeBanner·이슈상세가 store의 userPlan을 읽으므로
 * Pro+ 계정이 Free로 보였다. CountrySync와 같은 방식으로 레이아웃에서 한 번만 맞춘다.
 */
function PlanSync() {
  const { data: me } = useMe();
  const setUserPlan = useAppStore((s) => s.setUserPlan);
  const userPlan = useAppStore((s) => s.userPlan);

  useEffect(() => {
    const serverPlan = (me as { plan?: string } | undefined)?.plan;
    if (serverPlan && serverPlan !== userPlan) {
      setUserPlan(serverPlan as "free" | "pro" | "pro_plus");
    }
  }, [me, userPlan, setUserPlan]);

  return null;
}

/** 로그인됐는데 등록 미완료(닉네임/약관동의 없음)인 유저를 등록 페이지로 리다이렉트 */
function RegistrationGuard() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const { data: me, isLoading: meLoading } = useMe();

  useEffect(() => {
    if (authLoading || meLoading) return;
    if (!user) return; // 비로그인 유저는 게스트로 이용 가능
    if (!me) return;
    // 닉네임 또는 약관동의가 없으면 등록 폼으로 리다이렉트
    if (!me.nickname || !me.agreed_terms_at) {
      // 현재 페이지를 returnUrl로 보존
      if (pathname && pathname !== "/home") {
        sessionStorage.setItem("wwp_return_url", pathname);
      }
      router.replace("/login?tab=google-register");
    }
  }, [authLoading, meLoading, user, me, router, pathname]);

  return null;
}

/** 세션 추적: 30분 비활성 → 새 세션 (PRD 6.5) */
function SessionTracker() {
  const handleVisibilityChange = useCallback(() => {
    if (document.visibilityState === "visible") {
      checkAndResetSession();
    }
  }, []);

  useEffect(() => {
    // 사용자 활동 시 마지막 활동 시간 갱신
    const onActivity = () => updateLastActive();
    document.addEventListener("visibilitychange", handleVisibilityChange);
    document.addEventListener("click", onActivity, { passive: true });
    document.addEventListener("scroll", onActivity, { passive: true });
    document.addEventListener("keydown", onActivity, { passive: true });

    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      document.removeEventListener("click", onActivity);
      document.removeEventListener("scroll", onActivity);
      document.removeEventListener("keydown", onActivity);
    };
  }, [handleVisibilityChange]);

  return null;
}

export default function MainLayout({ children }: { children: React.ReactNode }) {
  // 레이아웃 마운트 시 사용자 정보 프리페치 (하위 페이지에서 캐시 히트)
  useMe();

  return (
    <>
      <CountrySync />
      <PlanSync />
      <RegistrationGuard />
      <SessionTracker />
      <NewEventBanner />
      <WelcomeModal />
      <main className={isTossMiniApp() ? "pb-[84px]" : "pb-[80px]"}>
        <ErrorBoundary>{children}</ErrorBoundary>
      </main>
      <BottomNav />
      <OnboardingBanner />
      <PWAInstallPrompt />
      <SmartAppBanner />
    </>
  );
}

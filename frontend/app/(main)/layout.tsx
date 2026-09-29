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
import { useMe, useMyAreas, usePatchPreferences } from "@/lib/api";
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

/** 브라우저 언어·시간대를 서버 설정에 한 번 맞춘다.
 *
 * 서버 기본값이 ko / Asia/Seoul 이라, 가입자 291명 전원이 한국어·서울 시간으로
 * 저장돼 있었다(2026-09 실측 — 실제 방문자는 90%가 해외). 알림 시간·이메일 언어가
 * 전부 한국 기준으로 나가고, 가입자가 어디 사람인지도 알 수 없었다.
 * 사용자마다 한 번만 보내고, 이후 변경은 설정 화면이 맡는다.
 */
function PrefsSync() {
  const { user } = useAuth();
  const { data: me } = useMe();
  const lang = useAppStore((s) => s.lang);
  const patchPrefs = usePatchPreferences();
  const userId = (me as { id?: string } | undefined)?.id;

  useEffect(() => {
    if (!user || !userId) return;
    const key = `prefs_synced_v1:${userId}`;
    try {
      if (localStorage.getItem(key)) return;
    } catch {
      return;
    }
    let timezone = "";
    try {
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch {}
    patchPrefs.mutate(
      { language: lang, ...(timezone ? { timezone } : {}) },
      {
        onSuccess: () => {
          try { localStorage.setItem(key, "1"); } catch {}
        },
        // 서버 tz 목록에 없는 이름이면 400 — 언어만이라도 저장하고 다시 시도하지 않는다
        onError: () => {
          patchPrefs.mutate({ language: lang });
          try { localStorage.setItem(key, "1"); } catch {}
        },
      },
    );
    // patchPrefs 객체는 렌더마다 새로 만들어져 의존성에 넣으면 되쓰기 고리가 된다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, userId, lang]);

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
      <PrefsSync />
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

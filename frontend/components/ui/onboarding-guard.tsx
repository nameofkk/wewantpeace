"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth, getFirebaseAuth } from "@/lib/auth";
import { SplashScreen } from "./splash-screen";

/** 공유 링크로 접근 가능한 경로들 */
const SHAREABLE_PATHS = ["/issues/", "/feed", "/map", "/tension"];

function isShareablePage(pathname: string): boolean {
  return SHAREABLE_PATHS.some((p) => pathname.startsWith(p));
}

/**
 * 온보딩 완료 여부를 localStorage로 체크하여
 * 미완료 시 /onboarding으로 리다이렉트.
 * 단, 공유 페이지로 진입한 경우 리다이렉트를 스킵하고 콘텐츠를 먼저 보여줌.
 * 스플래시 화면을 오버레이로 표시하여 children은 항상 렌더링 (데이터 prefetch 가능).
 */
export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { loading: authLoading } = useAuth();
  const [checked, setChecked] = useState(false);
  const [splashVisible, setSplashVisible] = useState(true);
  const mountTime = useRef(Date.now());

  // SSR 온보딩: 콘텐츠가 이미 HTML에 있으므로 React 스플래시 즉시 비활성화 (auth 대기 불필요)
  useEffect(() => {
    const p = window.location.pathname;
    if (p === "/" || p === "/onboarding") {
      setSplashVisible(false);
    }
  }, []);

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    const pathname = window.location.pathname;
    // middleware rewrite: `/`에서 onboarding 콘텐츠를 SSR로 제공하므로 `/`도 온보딩 페이지로 인식
    const isOnboardingPage = pathname === "/onboarding" || pathname === "/";
    const isAdminPage = pathname.startsWith("/admin");

    // onboarding_done → 쿠키 동기화 (middleware SSR 최적화용)
    if (done) {
      document.cookie = "onboarding_done=true; path=/; max-age=31536000; SameSite=Lax";
    }

    // 로그인 상태면 온보딩 자동 완료 처리 (이중 리다이렉트 방지)
    const auth = getFirebaseAuth();
    const isLoggedIn =
      !!localStorage.getItem("dev_uid") || !!auth?.currentUser;
    if (!done && isLoggedIn) {
      localStorage.setItem("onboarding_done", "true");
      document.cookie = "onboarding_done=true; path=/; max-age=31536000; SameSite=Lax";
      setChecked(true);
      return;
    }

    // 공유 페이지: 온보딩 미완료여도 리다이렉트 스킵, 플래그만 세팅
    if (!done && isShareablePage(pathname) && !isOnboardingPage) {
      sessionStorage.setItem("wwp_share_entry", "true");
      sessionStorage.setItem("wwp_return_url", pathname + window.location.search);
      setChecked(true);
      return;
    }

    if (!done && !isOnboardingPage && !isAdminPage) {
      router.replace("/onboarding");
    }
    setChecked(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 마운트 시 1회만 실행

  // 온보딩 체크 + auth 로딩 완료 시 스플래시 해제
  useEffect(() => {
    if (!checked || authLoading) return;

    const pathname = window.location.pathname;
    const isOnboardingSSR = pathname === "/" || pathname === "/onboarding";
    const elapsed = Date.now() - mountTime.current;
    // SSR 온보딩: 콘텐츠가 이미 HTML에 있으므로 스플래시 즉시 해제
    const minTime = isOnboardingSSR ? 0 : 800;
    const remaining = Math.max(0, minTime - elapsed);

    const timer = setTimeout(() => setSplashVisible(false), remaining);
    return () => clearTimeout(timer);
  }, [checked, authLoading]);

  // 안전 타임아웃: auth 로딩이 3초 이상 걸리면 강제 해제
  useEffect(() => {
    const timer = setTimeout(() => setSplashVisible(false), 3000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <>
      <SplashScreen visible={splashVisible} />
      {children}
    </>
  );
}

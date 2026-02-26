"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { SplashScreen } from "./splash-screen";

/**
 * 온보딩 완료 여부를 localStorage로 체크하여
 * 미완료 시 /onboarding으로 리다이렉트.
 * 스플래시 화면을 오버레이로 표시하여 children은 항상 렌더링 (데이터 prefetch 가능).
 */
export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { loading: authLoading } = useAuth();
  const [checked, setChecked] = useState(false);
  const [splashVisible, setSplashVisible] = useState(true);
  const mountTime = useRef(Date.now());

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    const isOnboardingPage = window.location.pathname === "/onboarding";
    const isAdminPage = window.location.pathname.startsWith("/admin");

    // 로그인 상태면 온보딩 자동 완료 처리 (이중 리다이렉트 방지)
    const isLoggedIn =
      !!localStorage.getItem("dev_uid") || !!localStorage.getItem("firebase_token");
    if (!done && isLoggedIn) {
      localStorage.setItem("onboarding_done", "true");
      setChecked(true);
      return;
    }

    if (!done && !isOnboardingPage && !isAdminPage) {
      router.replace("/onboarding");
    }
    setChecked(true);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 마운트 시 1회만 실행

  // 온보딩 체크 + auth 로딩 완료 시 최소 800ms 보장 후 스플래시 해제
  useEffect(() => {
    if (!checked || authLoading) return;

    const elapsed = Date.now() - mountTime.current;
    const remaining = Math.max(0, 800 - elapsed);

    const timer = setTimeout(() => setSplashVisible(false), remaining);
    return () => clearTimeout(timer);
  }, [checked, authLoading]);

  return (
    <>
      <SplashScreen visible={splashVisible} />
      {children}
    </>
  );
}

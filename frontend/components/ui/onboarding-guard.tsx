"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * 온보딩 완료 여부를 localStorage로 체크하여
 * 미완료 시 /onboarding으로 리다이렉트.
 * 마운트 시 1회만 체크 — pathname 의존성 제거로 네비게이션 시 BottomNav 사라짐 버그 수정.
 */
export function OnboardingGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

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
    } else {
      setChecked(true);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 마운트 시 1회만 실행

  if (!checked) return null;
  return <>{children}</>;
}

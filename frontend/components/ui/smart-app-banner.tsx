"use client";

import { useState, useEffect } from "react";
import { Smartphone, X, ExternalLink } from "lucide-react";
import { isInAppBrowser, isStandalone } from "@/lib/browser-detect";
import { isNativeApp, isMobileBrowser, isAndroidBrowser, isIOSBrowser } from "@/lib/platform-detect";
import { isTossMiniApp } from "@/lib/platform";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const DISMISS_KEY = "smart_app_banner_dismissed";
const DISMISS_HOURS = 24 * 14; // 2주
const VISITS_KEY = "smart_app_banner_visits";
const MIN_VISITS = 2; // 첫 방문에는 내용부터 보여 준다

const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.wewantpeace.app";
const PLAY_STORE_MARKET = "market://details?id=com.wewantpeace.app";
// TODO: Replace with actual App Store ID after iOS app launch
const APP_STORE_ID = ""; // Empty = don't show App Store banner
const APP_STORE_URL = APP_STORE_ID ? `https://apps.apple.com/app/wewantpeace/id${APP_STORE_ID}` : "";

/** Android에서 Play Store 앱으로 직접 열기, 실패 시 웹 폴백 */
function openPlayStore() {
  if (isAndroidBrowser()) {
    // market:// 스킴으로 Play Store 앱 직접 실행 시도
    const start = Date.now();
    window.location.href = PLAY_STORE_MARKET;
    // 500ms 안에 앱이 안 열리면 웹으로 폴백
    setTimeout(() => {
      if (Date.now() - start < 1500) {
        window.open(PLAY_STORE_URL, "_blank");
      }
    }, 500);
  } else {
    window.open(PLAY_STORE_URL, "_blank");
  }
}

/**
 * 앱 설치 유도 배너.
 *
 * 표시 조건:
 *  - 웹 브라우저(PC/모바일)에서만 표시
 *  - TWA / iOS 네이티브 / PWA standalone에서는 숨김
 *  - 인앱브라우저: "외부 브라우저에서 열기" 안내
 *  - 모바일: 해당 OS 스토어 링크
 *  - PC: 양쪽 스토어 링크
 *  - 닫기 시 72시간 무시
 */
export function SmartAppBanner() {
  const [visible, setVisible] = useState(false);
  const [inApp, setInApp] = useState(false);
  const lang = useAppStore((s) => s.lang);

  useEffect(() => {
    // 네이티브 앱(TWA/iOS), standalone, 토스 미니앱이면 표시 안 함
    if (isNativeApp() || isStandalone() || isTossMiniApp()) return;
    // 온보딩 미완료 유저에게는 표시 안 함 (OnboardingBanner 우선)
    if (!localStorage.getItem("onboarding_done")) return;

    // iOS 전용 브라우저인데 App Store ID가 없으면 배너 표시 안 함
    if (isIOSBrowser() && !APP_STORE_ID) return;
    // PC에서는 설치할 앱이 없으니 표시 안 함 (Play 스토어 웹 링크만 떴었다)
    if (!isMobileBrowser()) return;

    // 첫 방문자에게는 띄우지 않는다 — 들어오자마자 화면 아래를 가렸다
    let visits = parseInt(localStorage.getItem(VISITS_KEY) || "0", 10);
    if (!sessionStorage.getItem(VISITS_KEY)) {
      sessionStorage.setItem(VISITS_KEY, "1");
      visits += 1;
      localStorage.setItem(VISITS_KEY, String(visits));
    }
    if (visits < MIN_VISITS) return;

    // 72시간 내 닫은 적 있으면 무시
    const dismissed = localStorage.getItem(DISMISS_KEY);
    if (dismissed) {
      const dismissedAt = parseInt(dismissed, 10);
      if (Date.now() - dismissedAt < DISMISS_HOURS * 60 * 60 * 1000) return;
      localStorage.removeItem(DISMISS_KEY);
    }

    setInApp(isInAppBrowser());

    // 1초 대기 후 표시 (PWAInstallPrompt에 우선권 양보)
    const timer = setTimeout(() => setVisible(true), 1000);
    return () => clearTimeout(timer);
  }, []);

  function handleDismiss() {
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  }

  function handleOpenExternal() {
    // 인앱브라우저에서 외부 브라우저로 열기
    const url = window.location.href;
    // intent:// 스킴으로 Android Chrome 열기 시도
    if (isAndroidBrowser()) {
      window.location.href = `intent://${url.replace(/^https?:\/\//, "")}#Intent;scheme=https;package=com.android.chrome;end`;
      return;
    }
    window.open(url, "_system");
  }

  function handleStoreClick() {
    if (isAndroidBrowser()) {
      openPlayStore();
    } else if (isIOSBrowser() && APP_STORE_URL) {
      window.open(APP_STORE_URL, "_blank");
    } else {
      // PC: 웹 Play Store
      window.open(PLAY_STORE_URL, "_blank");
    }
    handleDismiss();
  }

  if (!visible) return null;

  // 인앱브라우저: "외부 브라우저에서 열기" 안내
  if (inApp) {
    return (
      <div className={cn(
        "fixed left-4 right-4 z-50 rounded-xl border border-border bg-card shadow-xl p-4 flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300",
        isTossMiniApp() ? "bottom-[calc(80px+env(safe-area-inset-bottom,0px))]" : "bottom-[72px]"
      )}>
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/20">
          <ExternalLink className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">
            {lang === "en" ? "Open in browser" : "외부 브라우저에서 열기"}
          </p>
          <p className="text-[10px] text-muted-foreground whitespace-nowrap">
            {lang === "en"
              ? "Open in Chrome/Safari to install the app"
              : "Chrome/Safari에서 열면 앱을 설치할 수 있어요"}
          </p>
        </div>
        <button
          onClick={handleOpenExternal}
          className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          {lang === "en" ? "Open" : "열기"}
        </button>
        <button
          onClick={handleDismiss}
          className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          aria-label={lang === "ko" ? "닫기" : "Close"}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    );
  }

  // 모바일/PC 브라우저: 스토어 다운로드 유도
  const storeLabel = lang === "en" ? "Install" : "설치";

  // 한 줄짜리 바 — 예전 카드형은 피드 아래쪽 두 줄을 통째로 가렸다
  return (
    <div className={cn(
      "fixed left-4 right-4 z-50 rounded-xl border border-border bg-card shadow-lg px-3 py-2 flex items-center gap-2.5 animate-in slide-in-from-bottom-4 duration-300",
      isTossMiniApp() ? "bottom-[calc(80px+env(safe-area-inset-bottom,0px))]" : "bottom-[72px]"
    )}>
      <Smartphone className="h-4 w-4 text-primary shrink-0" />
      <p className="flex-1 min-w-0 text-xs font-medium truncate">
        {lang === "en" ? "Get alerts in the app" : "앱에서 알림 받기"}
      </p>
      <button
        onClick={handleStoreClick}
        className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        {storeLabel}
      </button>
      <button
        onClick={handleDismiss}
        className="shrink-0 rounded-lg p-1 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        aria-label={lang === "ko" ? "닫기" : "Close"}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

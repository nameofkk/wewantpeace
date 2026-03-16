"use client";

import { useState, useEffect } from "react";
import { Smartphone, X, ExternalLink } from "lucide-react";
import { isInAppBrowser, isStandalone } from "@/lib/browser-detect";
import { isNativeApp, isMobileBrowser, isAndroidBrowser, isIOSBrowser } from "@/lib/platform-detect";
import { isTossMiniApp } from "@/lib/platform";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

const DISMISS_KEY = "smart_app_banner_dismissed";
const DISMISS_HOURS = 72; // 3일

const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.wewantpeace.app";
const APP_STORE_URL = "https://apps.apple.com/app/wewantpeace/id0000000000"; // TODO: 실제 ID로 교체

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
      window.open(PLAY_STORE_URL, "_blank");
    } else if (isIOSBrowser()) {
      window.open(APP_STORE_URL, "_blank");
    } else {
      // PC: Play Store 우선
      window.open(PLAY_STORE_URL, "_blank");
    }
    handleDismiss();
  }

  if (!visible) return null;

  // 인앱브라우저: "외부 브라우저에서 열기" 안내
  if (inApp) {
    return (
      <div className="fixed bottom-[72px] left-4 right-4 z-50 rounded-xl border border-border bg-card shadow-xl p-4 flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/20">
          <ExternalLink className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">
            {lang === "en" ? "Open in browser" : "외부 브라우저에서 열기"}
          </p>
          <p className="text-[11px] text-muted-foreground truncate">
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
  const isMobile = isMobileBrowser();
  const storeLabel = isAndroidBrowser()
    ? t(lang, "store_download_android")
    : isIOSBrowser()
      ? t(lang, "store_download_ios")
      : lang === "en"
        ? "Get the app"
        : "앱 다운로드";

  return (
    <div className="fixed bottom-[72px] left-4 right-4 z-50 rounded-xl border border-border bg-card shadow-xl p-4 animate-in slide-in-from-bottom-4 duration-300">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/20">
          <Smartphone className="h-5 w-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold">
            {lang === "en" ? "Get WeWantPeace app" : "WeWantPeace 앱 설치"}
          </p>
          <p className="text-[11px] text-muted-foreground truncate">
            {lang === "en"
              ? "Get real-time alerts and a better experience"
              : "실시간 알림과 더 나은 경험을 받아보세요"}
          </p>
        </div>
        <button
          onClick={handleDismiss}
          className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          aria-label={lang === "ko" ? "닫기" : "Close"}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* 스토어 버튼 */}
      <div className="flex gap-2 mt-3">
        {(!isMobile || isAndroidBrowser()) && (
          <button
            onClick={() => { window.open(PLAY_STORE_URL, "_blank"); handleDismiss(); }}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current"><path d="M3.609 1.814L13.792 12 3.61 22.186a.996.996 0 01-.61-.92V2.734a1 1 0 01.609-.92zm10.89 10.893l2.302 2.302-10.937 6.333 8.635-8.635zm3.199-3.199l2.807 1.626a1 1 0 010 1.732l-2.807 1.626L15.206 12l2.492-2.492zM5.864 3.458L16.8 9.79l-2.302 2.302-8.635-8.635z"/></svg>
            {t(lang, "store_download_android")}
          </button>
        )}
        {(!isMobile || isIOSBrowser()) && (
          <button
            onClick={() => { window.open(APP_STORE_URL, "_blank"); handleDismiss(); }}
            className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-secondary px-3 py-2 text-xs font-semibold text-secondary-foreground hover:bg-secondary/80 transition-colors"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
            {t(lang, "store_download_ios")}
          </button>
        )}
      </div>
    </div>
  );
}

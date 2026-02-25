"use client";

import { useState, useEffect } from "react";
import { Download, X, ExternalLink } from "lucide-react";
import { isInAppBrowser, isStandalone } from "@/lib/browser-detect";

const DISMISS_KEY = "smart_app_banner_dismissed";
const DISMISS_HOURS = 24;

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

/**
 * 앱 설치 유도 배너.
 * - beforeinstallprompt 이벤트가 발생하면 PWAInstallPrompt가 우선 → 숨김
 * - 인앱브라우저: "외부 브라우저에서 열기" 안내
 * - 일반 브라우저(PWA 미지원): "홈 화면에 추가" 안내
 * - standalone(이미 앱): 표시 안 함
 * - 닫기 시 24시간 무시
 */
export function SmartAppBanner() {
  const [visible, setVisible] = useState(false);
  const [hasPwaPrompt, setHasPwaPrompt] = useState(false);
  const [inApp, setInApp] = useState(false);

  useEffect(() => {
    // standalone이면 표시 안 함
    if (isStandalone()) return;

    // 24시간 내 닫은 적 있으면 무시
    const dismissed = localStorage.getItem(DISMISS_KEY);
    if (dismissed) {
      const dismissedAt = parseInt(dismissed, 10);
      if (Date.now() - dismissedAt < DISMISS_HOURS * 60 * 60 * 1000) return;
    }

    setInApp(isInAppBrowser());

    // beforeinstallprompt 대기 — 발생하면 PWAInstallPrompt에 양보
    const handler = () => setHasPwaPrompt(true);
    window.addEventListener("beforeinstallprompt", handler);

    // 500ms 후 표시 (PWA 프롬프트 발생 여부 확인 시간)
    const timer = setTimeout(() => setVisible(true), 500);

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
      clearTimeout(timer);
    };
  }, []);

  function handleDismiss() {
    setVisible(false);
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
  }

  function handleOpenExternal() {
    const url = window.location.href;
    window.open(url, "_system");
  }

  // PWA 프롬프트가 발생하면 PWAInstallPrompt에 양보
  if (!visible || hasPwaPrompt) return null;

  return (
    <div className="fixed bottom-[72px] left-4 right-4 z-50 rounded-xl border border-border bg-card shadow-xl p-4 flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/20">
        {inApp ? (
          <ExternalLink className="h-5 w-5 text-primary" />
        ) : (
          <Download className="h-5 w-5 text-primary" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        {inApp ? (
          <>
            <p className="text-sm font-semibold">외부 브라우저에서 열기</p>
            <p className="text-[11px] text-muted-foreground truncate">
              앱 설치 시 실시간 알림을 받을 수 있습니다
            </p>
          </>
        ) : (
          <>
            <p className="text-sm font-semibold">홈 화면에 추가</p>
            <p className="text-[11px] text-muted-foreground truncate">
              앱 설치 시 실시간 알림을 받을 수 있습니다
            </p>
          </>
        )}
      </div>

      {inApp ? (
        <button
          onClick={handleOpenExternal}
          className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          열기
        </button>
      ) : (
        <button
          onClick={handleDismiss}
          className="shrink-0 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          확인
        </button>
      )}

      <button
        onClick={handleDismiss}
        className="shrink-0 rounded-lg p-1.5 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
        aria-label="닫기"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

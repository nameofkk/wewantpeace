"use client";

import React, { useState, useEffect } from "react";
import { Bell, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { t } from "@/lib/i18n";
import { isPushSupported, getStoredFCMToken, requestAndGetFCMToken } from "@/lib/fcm";
import { useRegisterPushToken } from "@/lib/api";

const DISMISS_KEY = "push_prompt_dismissed";

interface PushPromptBannerProps {
  lang: "ko" | "en";
  isLoggedIn: boolean;
}

export function PushPromptBanner({ lang, isLoggedIn }: PushPromptBannerProps) {
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const registerToken = useRegisterPushToken();

  useEffect(() => {
    if (!isLoggedIn) return;
    if (typeof window === "undefined") return;
    // 이미 토큰이 있거나 iOS이거나 지원 안 하면 안 보여줌
    if (getStoredFCMToken()) return;
    if (!isPushSupported()) return;
    // 이미 dismiss 했으면 안 보여줌
    const dismissed = localStorage.getItem(DISMISS_KEY);
    if (dismissed) return;
    // Notification.permission이 이미 granted면 자동 등록 시도
    if (typeof Notification !== "undefined" && Notification.permission === "granted") {
      handleEnable();
      return;
    }
    // denied면 안 보여줌
    if (typeof Notification !== "undefined" && Notification.permission === "denied") return;
    setVisible(true);
  }, [isLoggedIn]);

  async function handleEnable() {
    setLoading(true);
    try {
      const token = await requestAndGetFCMToken();
      if (token) {
        await registerToken.mutateAsync({ fcm_token: token, platform: "web" });
      }
    } catch {
      // 실패해도 배너 닫기
    }
    setVisible(false);
    setLoading(false);
  }

  function handleDismiss() {
    localStorage.setItem(DISMISS_KEY, "1");
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className={cn(
      "relative mx-4 mt-2 mb-1 rounded-lg border border-blue-200 dark:border-blue-800",
      "bg-blue-50/80 dark:bg-blue-950/40 p-3",
    )}>
      <button
        onClick={handleDismiss}
        className="absolute top-2 right-2 p-1 rounded-full hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
        aria-label="Close"
      >
        <X className="w-3.5 h-3.5 text-blue-400" />
      </button>
      <div className="flex items-start gap-3 pr-6">
        <div className="flex-shrink-0 mt-0.5">
          <Bell className="w-5 h-5 text-blue-500" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
            {t(lang, "push_prompt_title")}
          </p>
          <p className="text-xs text-blue-700 dark:text-blue-300 mt-0.5">
            {t(lang, "push_prompt_desc")}
          </p>
          <button
            onClick={handleEnable}
            disabled={loading}
            className={cn(
              "mt-2 px-3 py-1.5 text-xs font-medium rounded-md transition-colors",
              "bg-blue-600 hover:bg-blue-700 text-white",
              "disabled:opacity-50 disabled:cursor-not-allowed",
            )}
          >
            {loading
              ? (lang === "ko" ? "설정 중..." : "Setting up...")
              : t(lang, "push_prompt_enable")}
          </button>
        </div>
      </div>
    </div>
  );
}

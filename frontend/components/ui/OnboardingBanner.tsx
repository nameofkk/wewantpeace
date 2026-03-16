"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, X } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { LogoIcon } from "@/components/ui/logo-icon";

/**
 * 공유 링크로 진입한 온보딩 미완료 유저에게 표시하는 하단 CTA 배너.
 *
 * 표시 조건:
 *  - onboarding_done === null (미완료)
 *  - sessionStorage.wwp_share_entry === "true"
 *
 * 동작:
 *  - "설정하기" → /onboarding (returnUrl은 이미 sessionStorage에 저장됨)
 *  - X 닫기 → onboarding_done=true (자유 이용, 홈에서 WelcomeModal 표시)
 */
export function OnboardingBanner() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    const shareEntry = sessionStorage.getItem("wwp_share_entry");
    if (!done && shareEntry === "true") {
      // 약간의 딜레이로 콘텐츠가 먼저 보이도록
      const timer = setTimeout(() => setVisible(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  if (!visible) return null;

  function handleSetup() {
    router.push("/onboarding");
  }

  function handleDismiss() {
    localStorage.setItem("onboarding_done", "true");
    // wwp_welcome_seen은 세팅하지 않음 → 홈에서 WelcomeModal 표시
    sessionStorage.removeItem("wwp_share_entry");
    setVisible(false);
  }

  return (
    <div
      className="fixed bottom-[72px] left-4 right-4 z-50 rounded-xl border border-blue-500/30 shadow-xl p-3.5 flex items-center gap-3 animate-in slide-in-from-bottom-4 duration-300"
      style={{
        background:
          "linear-gradient(135deg, rgba(15,23,42,0.97) 0%, rgba(30,41,59,0.97) 100%)",
      }}
    >
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-500/15">
        <LogoIcon height={20} hideText />
      </div>
      <p className="flex-1 text-[12px] font-medium text-slate-200 leading-snug min-w-0">
        {t(lang, "onboarding_banner_text" as any)}
      </p>
      <button
        onClick={handleSetup}
        className="shrink-0 flex items-center gap-1 rounded-lg px-3 py-1.5 text-[11px] font-bold text-white transition-colors"
        style={{
          background: "linear-gradient(135deg, #3b82f6 0%, #06b6d4 100%)",
        }}
      >
        {t(lang, "onboarding_banner_cta" as any)}
        <ArrowRight className="h-3 w-3" />
      </button>
      <button
        onClick={handleDismiss}
        className="shrink-0 rounded-lg p-1 text-slate-400 hover:text-slate-200 hover:bg-white/10 transition-colors"
        aria-label={lang === "ko" ? "닫기" : "Close"}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

"use client";

import { useEffect, useState } from "react";
import { X, Shield, Check, Zap, Lock, RotateCcw } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { detectPlatform, type AppPlatform } from "@/lib/platform-detect";
import { isTossMiniApp } from "@/lib/platform";
import { shouldShowPaywall, recordPaywallShown } from "@/lib/paywall-cap";
import { trackPaywallEvent } from "@/lib/analytics";
import { getSessionId } from "@/lib/session";
import { useRouter } from "next/navigation";

interface PaywallModalProps {
  trigger: "map_locked" | "verified_locked" | "kscore_threshold_locked" | "watch_country_limit_locked";
  isOpen: boolean;
  onClose: () => void;
}

const TRIGGER_TITLES: Record<string, { ko: string; en: string }> = {
  map_locked: {
    ko: "실시간 이슈 지도",
    en: "Real-time Issue Map",
  },
  verified_locked: {
    ko: "신뢰 알림",
    en: "Verified Alerts",
  },
  kscore_threshold_locked: {
    ko: "KScore 필터 조정",
    en: "KScore Filter",
  },
  watch_country_limit_locked: {
    ko: "더 많은 관심 국가",
    en: "More Countries",
  },
};

const TRIGGER_DESCRIPTIONS: Record<string, { ko: string; en: string }> = {
  map_locked: {
    ko: "Pro 플랜에서 실시간 글로벌 이슈 지도를 확인하세요",
    en: "Access the real-time global issue map with Pro",
  },
  verified_locked: {
    ko: "공신력 있는 소스로 확인된 이슈 알림을 받아보세요",
    en: "Get alerts for issues verified by trusted sources",
  },
  kscore_threshold_locked: {
    ko: "KScore 임계치를 조절하여 맞춤 알림을 받으세요",
    en: "Customize your KScore threshold for tailored alerts",
  },
  watch_country_limit_locked: {
    ko: "Pro에서 5개 국가까지, Pro+에서 무제한으로 추적하세요",
    en: "Track up to 5 countries with Pro, unlimited with Pro+",
  },
};

export function PaywallModal({ trigger, isOpen, onClose }: PaywallModalProps) {
  const router = useRouter();
  const { lang } = useAppStore();
  const [platform, setPlatform] = useState<AppPlatform>("web");
  const [closing, setClosing] = useState(false);

  useEffect(() => {
    setPlatform(detectPlatform());
  }, []);

  // 페이월 표시 시 이벤트 트래킹
  useEffect(() => {
    if (isOpen) {
      recordPaywallShown(trigger);
      const sessionId = getSessionId();
      trackPaywallEvent(trigger, "shown", { source: trigger, session_id: sessionId });
    }
  }, [isOpen, trigger]);

  if (!isOpen) return null;

  const isWeb = platform === "web" && !isTossMiniApp();
  const isIOS = platform === "ios-native" || platform === "ios-app";
  const title = TRIGGER_TITLES[trigger]?.[lang] || "";
  const description = TRIGGER_DESCRIPTIONS[trigger]?.[lang] || "";

  const handleClose = () => {
    setClosing(true);
    trackPaywallEvent(trigger, "dismissed", { source: trigger, session_id: getSessionId() });
    setTimeout(() => {
      setClosing(false);
      onClose();
    }, 200);
  };

  const handleUpgrade = () => {
    trackPaywallEvent(trigger, "clicked_upgrade", {
      source: trigger,
      plan: "pro",
      session_id: getSessionId(),
    });
    router.push(`/upgrade?source=${trigger}`);
    onClose();
  };

  const handleRestore = async () => {
    // iOS 구매 복원 → 설정 페이지로 이동
    router.push("/settings");
    onClose();
  };

  const proFeatures = [
    t(lang, "paywall_pro_feature_map"),
    t(lang, "paywall_pro_feature_countries"),
    t(lang, "paywall_pro_feature_kscore"),
    t(lang, "paywall_pro_feature_quiet"),
  ];

  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex items-end sm:items-center justify-center",
        closing ? "animate-out fade-out" : "animate-in fade-in"
      )}
    >
      {/* 오버레이 */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={handleClose}
      />

      {/* 모달 */}
      <div
        className={cn(
          "relative w-full max-w-md mx-4 sm:mx-auto rounded-t-3xl sm:rounded-3xl bg-card border border-border/60 overflow-hidden",
          closing
            ? "animate-out slide-out-to-bottom"
            : "animate-in slide-in-from-bottom"
        )}
        style={{
          animation: closing
            ? "slideDown 0.2s ease forwards"
            : "slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1) forwards",
        }}
      >
        <style>{`
          @keyframes slideUp {
            from { opacity: 0; transform: translateY(100%); }
            to { opacity: 1; transform: translateY(0); }
          }
          @keyframes slideDown {
            from { opacity: 1; transform: translateY(0); }
            to { opacity: 0; transform: translateY(100%); }
          }
        `}</style>

        {/* 닫기 버튼 */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 z-10 rounded-full p-1.5 bg-muted/50 hover:bg-muted transition-colors"
        >
          <X className="h-4 w-4" />
        </button>

        {/* 헤더 */}
        <div className="pt-8 pb-4 px-6 text-center">
          <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-cyan-400 mb-4 shadow-lg shadow-blue-500/20">
            <Lock className="h-6 w-6 text-white" />
          </div>
          <h3 className="text-xl font-black tracking-tight">{title}</h3>
          <p className="mt-2 text-sm text-muted-foreground">{description}</p>
        </div>

        {/* Pro 기능 목록 */}
        <div className="px-6 pb-4">
          <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-4">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="h-4 w-4 text-blue-400" />
              <span className="text-sm font-bold text-blue-400">Pro</span>
              <span className="ml-auto text-xs text-muted-foreground">
                {lang === "ko" ? "7일 무료 체험" : "7-day free trial"}
              </span>
            </div>
            <div className="space-y-2.5">
              {proFeatures.map((feature, i) => (
                <div key={i} className="flex items-center gap-2.5">
                  <div className="h-5 w-5 rounded-full bg-blue-500/15 flex items-center justify-center shrink-0">
                    <Check className="h-3 w-3 text-blue-400" />
                  </div>
                  <span className="text-xs text-foreground/80">{feature}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* CTA 버튼 */}
        <div className="px-6 pb-4 space-y-3">
          {isWeb ? (
            <div className="w-full rounded-xl py-3.5 text-sm font-bold text-center bg-gradient-to-r from-blue-500/20 to-cyan-500/20 text-blue-400 border border-blue-500/20">
              {lang === "ko" ? "앱에서 구독하세요" : "Subscribe in App"}
            </div>
          ) : (
            <button
              onClick={handleUpgrade}
              className="w-full rounded-xl py-3.5 text-sm font-bold bg-gradient-to-r from-blue-500 to-cyan-500 text-white hover:shadow-lg hover:shadow-blue-500/25 transition-all active:scale-[0.98]"
            >
              <Zap className="inline h-4 w-4 mr-1.5 -mt-0.5" />
              {lang === "ko" ? "Pro 무료 체험 시작" : "Start Pro Free Trial"}
            </button>
          )}

          <button
            onClick={handleClose}
            className="w-full rounded-xl py-2.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {lang === "ko" ? "나중에" : "Maybe Later"}
          </button>
        </div>

        {/* iOS Restore + 푸터 (PRD 6.6: 페이월 하단 고정) */}
        <div className="px-6 pb-6 pt-2 border-t border-border/30 text-center space-y-1">
          {isIOS && (
            <button
              onClick={handleRestore}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 mx-auto"
            >
              <RotateCcw className="h-3 w-3" />
              {lang === "ko" ? "구매 복원" : "Restore Purchases"}
            </button>
          )}
          <p className="text-[10px] text-muted-foreground/60">
            {lang === "ko"
              ? "Pro+ 플랜은 무료 체험이 제공되지 않습니다"
              : "Pro+ plan does not include a free trial"}
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * 페이월 표시 조건 체크 (frequency cap 포함)
 */
export function usePaywall(trigger: PaywallModalProps["trigger"]) {
  const [isOpen, setIsOpen] = useState(false);
  const userPlan = useAppStore((s) => s.userPlan);

  const show = () => {
    if (userPlan !== "free") return; // Pro 이상은 표시 안 함
    if (!shouldShowPaywall(trigger)) return; // frequency cap
    setIsOpen(true);
  };

  const close = () => setIsOpen(false);

  return { isOpen, show, close };
}

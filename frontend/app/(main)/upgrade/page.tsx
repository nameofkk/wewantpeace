"use client";

import { useState, useEffect } from "react";
import { Check, X, Zap, Shield, Star, Crown, ArrowLeft, Download, Smartphone, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { detectPlatform, isMobileBrowser, isAndroidBrowser, isIOSBrowser, type AppPlatform } from "@/lib/platform-detect";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_BASE, useMe } from "@/lib/api";

interface Feature {
  labelKo: string;
  labelEn: string;
  free: boolean | string;
  pro: boolean | string;
  proplus: boolean | string;
}

const FEATURES: Feature[] = [
  {
    labelKo: "관심 국가",         labelEn: "Monitored countries",
    free: "2개",                  pro: "5개",                     proplus: "무제한",
  },
  {
    labelKo: "글로벌 트렌딩",      labelEn: "Global trending",
    free: true,                   pro: true,                      proplus: true,
  },
  {
    labelKo: "실시간 이슈 지도",    labelEn: "Real-time issue map",
    free: false,                  pro: true,                      proplus: true,
  },
  {
    labelKo: "공식 확인 이슈 알림", labelEn: "Verified issue alerts",
    free: true,                   pro: true,                      proplus: true,
  },
  {
    labelKo: "속보 알림 (미확인 포함)", labelEn: "Fast alerts (breaking news)",
    free: false,                  pro: true,                      proplus: true,
  },
  {
    labelKo: "KScore 필터 조정",   labelEn: "KScore threshold filter",
    free: "고정 (3.0)",           pro: "3.0 ~ 10.0",              proplus: "1.5 ~ 10.0",
  },
  {
    labelKo: "토픽 필터",          labelEn: "Topic filter",
    free: false,                  pro: true,                      proplus: true,
  },
  {
    labelKo: "방해금지 시간",       labelEn: "Quiet hours",
    free: false,                  pro: true,                      proplus: true,
  },
  {
    labelKo: "긴장도 히스토리",     labelEn: "Tension history",
    free: "7일",                  pro: "30일",                    proplus: "90일",
  },
  {
    labelKo: "KScore 히스토리",    labelEn: "KScore history",
    free: "7일",                  pro: "30일",                    proplus: "90일",
  },
  {
    labelKo: "커뮤니티",           labelEn: "Community",
    free: "읽기/쓰기",             pro: "읽기/쓰기",               proplus: "읽기/쓰기",
  },
];

const GOOGLE_PRODUCT_IDS: Record<string, string> = {
  pro: "com.wewantpeace.pro_monthly",
  pro_plus: "com.wewantpeace.proplus_monthly",
};

const APPLE_PRODUCT_IDS: Record<string, string> = {
  pro: "com.wewantpeace.pro.monthly",
  pro_plus: "com.wewantpeace.proplus.monthly",
};

// 스토어 링크 (등록 후 실제 URL로 교체)
const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.wewantpeace.app";
const APP_STORE_URL = "https://apps.apple.com/app/wewantpeace/id0000000000"; // TODO: 실제 ID

function FeatureValue({
  val, planId, lang,
}: { val: boolean | string; planId: string; lang: Lang }) {
  if (val === true) {
    const color = planId === "pro_plus" ? "text-purple-400" : planId === "pro" ? "text-blue-400" : "text-green-500";
    return <Check className={cn("h-4 w-4 mx-auto", color)} />;
  }
  if (val === false) return <X className="h-4 w-4 mx-auto text-muted-foreground/30" />;
  return (
    <span className={cn(
      "text-[11px] font-medium",
      planId === "pro_plus" ? "text-purple-400" : planId === "pro" ? "text-blue-400" : "text-muted-foreground"
    )}>
      {val}
    </span>
  );
}

/** 웹에서 "앱에서 구독하세요" 안내 UI */
function AppInstallPrompt({ lang }: { lang: Lang }) {
  const isAndroid = isAndroidBrowser();
  const isIOS = isIOSBrowser();

  return (
    <div className="rounded-2xl border-2 border-primary/30 bg-card p-6 text-center space-y-4">
      <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 mx-auto">
        <Smartphone className="h-7 w-7 text-primary" />
      </div>

      <div>
        <h3 className="text-lg font-bold">
          {t(lang, "store_subscribe_in_app")}
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          {lang === "ko"
            ? "WeWantPeace 앱을 설치하고 Pro/Pro+ 플랜을 구독하세요"
            : "Install the WeWantPeace app and subscribe to Pro/Pro+"}
        </p>
      </div>

      <div className="flex flex-col gap-3">
        {(!isIOS) && (
          <a
            href={PLAY_STORE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-green-600 to-green-500 py-3 text-sm font-bold text-white hover:opacity-90 transition-opacity"
          >
            <Download className="h-4 w-4" />
            {t(lang, "store_download_android")}
          </a>
        )}
        {(!isAndroid) && (
          <a
            href={APP_STORE_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 py-3 text-sm font-bold text-white hover:opacity-90 transition-opacity"
          >
            <Download className="h-4 w-4" />
            {t(lang, "store_download_ios")}
          </a>
        )}
      </div>

      <div className="pt-2 border-t border-border">
        <p className="text-xs text-muted-foreground">
          {t(lang, "store_already_subscribed")}
        </p>
        <p className="text-xs text-muted-foreground mt-0.5">
          {t(lang, "store_login_to_sync")}
        </p>
      </div>
    </div>
  );
}

export default function UpgradePage() {
  const router = useRouter();
  const { user } = useAuth();
  const { lang } = useAppStore();
  const { data: me } = useMe();
  const currentPlan = (me as { plan?: string })?.plan ?? "free";
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<"pro" | "pro_plus">("pro");
  const [platform, setPlatform] = useState<AppPlatform>("web");
  const [cancelSuccess, setCancelSuccess] = useState<string | null>(null);

  useEffect(() => {
    setPlatform(detectPlatform());
  }, []);

  // 현재 플랜에 따라 기본 선택 변경
  useEffect(() => {
    if (currentPlan === "pro") setSelected("pro_plus");
  }, [currentPlan]);

  async function handleSubscribe(planId: string) {
    if (planId === "free") return;
    if (!user) { window.location.href = "/login"; return; }

    setLoading(planId);
    setError(null);

    try {
      if (platform === "android-twa") {
        await handleAndroidPurchase(planId);
      } else if (platform === "ios-app") {
        await handleIOSPurchase(planId);
      }
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || t(lang, "upgrade_payment_error"));
    } finally {
      setLoading(null);
    }
  }

  async function handleDowngrade() {
    if (!user) return;
    if (!confirm(t(lang, "upgrade_downgrade_confirm"))) return;
    setLoading("downgrade");
    setError(null);
    setCancelSuccess(null);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/subscriptions/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ reason: "plan_downgrade" }),
      });
      const data = await res.json();
      if (data.status === "store_cancel_required") {
        // 스토어 구독 → 스토어로 안내
        if (data.manage_url) window.open(data.manage_url, "_blank");
        setCancelSuccess(t(lang, "upgrade_downgrade_store"));
      } else if (data.status === "cancelled") {
        setCancelSuccess(data.message || t(lang, "upgrade_cancel_success"));
      } else if (!res.ok) {
        setError(data.detail || t(lang, "upgrade_payment_error"));
      }
    } catch {
      setError(t(lang, "upgrade_payment_error"));
    } finally {
      setLoading(null);
    }
  }

  async function handleAndroidPurchase(planId: string) {
    const { purchaseSubscription } = await import("@/lib/play-billing");
    const productId = GOOGLE_PRODUCT_IDS[planId];
    if (!productId) throw new Error("Invalid plan");

    const purchaseToken = await purchaseSubscription(productId);
    if (!purchaseToken) return;

    const token = await user!.getIdToken();
    const res = await fetch(`${API_BASE}/subscriptions/store/google/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ purchase_token: purchaseToken, product_id: productId }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || t(lang, "upgrade_payment_failed"));
    }

    window.location.href = "/settings";
  }

  async function handleIOSPurchase(planId: string) {
    const { purchaseViaStoreKit } = await import("@/lib/ios-storekit");
    const productId = APPLE_PRODUCT_IDS[planId];
    if (!productId) throw new Error("Invalid plan");

    const result = await purchaseViaStoreKit(productId);
    if (!result) return;

    const token = await user!.getIdToken();
    const res = await fetch(`${API_BASE}/subscriptions/store/apple/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ transaction_id: result.transactionId, product_id: productId }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || t(lang, "upgrade_payment_failed"));
    }

    window.location.href = "/settings";
  }

  const isWeb = platform === "web";

  return (
    <div className="min-h-screen bg-background">
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0); }
          50%      { transform: translateY(-4px); }
        }
        @keyframes borderGlow {
          0%, 100% { opacity: 0.6; }
          50%      { opacity: 1; }
        }
        @keyframes scaleIn {
          from { opacity: 0; transform: scale(0.92); }
          to   { opacity: 1; transform: scale(1); }
        }
        .card-enter { animation: scaleIn 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.1) both; }
        .card-enter-1 { animation-delay: 0.08s; }
        .card-enter-2 { animation-delay: 0.18s; }
        .card-enter-3 { animation-delay: 0.28s; }
        .shimmer-text {
          background: linear-gradient(90deg, currentColor 40%, rgba(255,255,255,0.8) 50%, currentColor 60%);
          background-size: 200% 100%;
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          animation: shimmer 3s ease-in-out infinite;
        }
        .shimmer-border {
          position: relative;
          overflow: hidden;
        }
        .shimmer-border::before {
          content: '';
          position: absolute;
          inset: -2px;
          border-radius: inherit;
          padding: 2px;
          background: linear-gradient(135deg, transparent 30%, rgba(255,255,255,0.15) 50%, transparent 70%);
          background-size: 300% 300%;
          animation: shimmer 4s ease infinite;
          -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
          -webkit-mask-composite: xor;
          mask-composite: exclude;
          pointer-events: none;
        }
        .glow-blue {
          box-shadow: 0 0 20px rgba(59,130,246,0.15), 0 0 60px rgba(59,130,246,0.05);
        }
        .glow-purple {
          box-shadow: 0 0 20px rgba(168,85,247,0.15), 0 0 60px rgba(168,85,247,0.05);
        }
        .glass-card {
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
        }
        .gradient-border-pro {
          border-image: linear-gradient(135deg, #3b82f6, #06b6d4, #3b82f6) 1;
        }
        .btn-shine {
          position: relative;
          overflow: hidden;
        }
        .btn-shine::after {
          content: '';
          position: absolute;
          top: -50%;
          left: -60%;
          width: 40%;
          height: 200%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
          transform: skewX(-15deg);
          animation: btnShine 3s ease-in-out infinite;
        }
        @keyframes btnShine {
          0% { left: -60%; }
          20% { left: 120%; }
          100% { left: 120%; }
        }
        .badge-float {
          animation: float 2.5s ease-in-out infinite;
        }
      `}</style>

      {/* 헤더 */}
      <div className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-background/90 backdrop-blur-sm px-4 py-3">
        <Link href="/settings" className="rounded-full p-1.5 hover:bg-muted transition-colors">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-sm font-bold">{t(lang, "upgrade_title")}</h1>
      </div>

      <div className="mx-auto max-w-lg px-4 py-8">

        {/* 타이틀 */}
        <div className="text-center mb-10" style={{ animation: "fadeSlideUp 0.4s ease both" }}>
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-4 py-1.5 mb-4">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            <span className="text-xs font-semibold text-primary">
              {lang === "ko" ? "더 강력한 분석 도구" : "More powerful analytics"}
            </span>
          </div>
          <h2 className="text-2xl font-black tracking-tight">
            {lang === "ko" ? "당신에게 맞는 플랜" : "Choose Your Plan"}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">{t(lang, "upgrade_subtitle")}</p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive text-center">
            {error}
          </div>
        )}

        {cancelSuccess && (
          <div className="mb-6 rounded-lg bg-green-500/10 border border-green-500/20 px-4 py-3 text-sm text-green-400 text-center">
            {cancelSuccess}
          </div>
        )}

        {/* 웹 브라우저: 앱 설치 유도 */}
        {isWeb && (
          <div className="mb-8" style={{ animation: "fadeSlideUp 0.35s ease both" }}>
            <AppInstallPrompt lang={lang} />
          </div>
        )}

        {/* ── 플랜 카드 ── */}
        <div className="space-y-5">

          {/* Free 카드 — 심플하게 */}
          <div className="card-enter card-enter-1 rounded-2xl border border-border/60 bg-card/50 p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-xl bg-muted/80 flex items-center justify-center">
                  <span className="text-lg">🌐</span>
                </div>
                <div>
                  <p className="text-base font-bold text-muted-foreground">Free</p>
                  <p className="text-[11px] text-muted-foreground/70">
                    {lang === "ko" ? "핵심 기능 무료" : "Core features, free"}
                  </p>
                </div>
              </div>
              <p className="text-lg font-bold text-muted-foreground">
                {lang === "ko" ? "무료" : "Free"}
              </p>
            </div>
            {currentPlan === "free" ? (
              <div className="mt-3 w-full rounded-xl py-2 text-xs font-semibold text-center bg-secondary/50 text-muted-foreground">
                {t(lang, "upgrade_current_plan")}
              </div>
            ) : (
              <button
                onClick={handleDowngrade}
                disabled={loading === "downgrade"}
                className="mt-3 w-full rounded-xl py-2 text-xs font-medium text-center text-red-400/80 border border-red-500/20 hover:bg-red-500/10 transition-colors disabled:opacity-50"
              >
                {loading === "downgrade" ? t(lang, "upgrade_processing") : t(lang, "upgrade_downgrade_free")}
              </button>
            )}
          </div>

          {/* Pro 카드 — 블루 글로시 */}
          <div
            className={cn(
              "card-enter card-enter-2 relative rounded-2xl p-[2px] cursor-pointer transition-all duration-300",
              selected === "pro"
                ? "glow-blue bg-gradient-to-br from-blue-500 via-cyan-400 to-blue-600"
                : "bg-border/40 hover:bg-gradient-to-br hover:from-blue-500/50 hover:via-cyan-400/50 hover:to-blue-600/50"
            )}
            onClick={() => setSelected("pro")}
          >
            {/* 인기 배지 */}
            <div className="absolute -top-3.5 left-0 right-0 flex justify-center z-10 badge-float">
              <div className="flex items-center gap-1 rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 px-4 py-1 shadow-lg shadow-blue-500/25">
                <Zap className="h-3 w-3 text-white" />
                <span className="text-[11px] font-bold text-white">
                  {lang === "ko" ? "인기" : "Popular"}
                </span>
              </div>
            </div>

            <div className={cn(
              "rounded-[14px] bg-card p-5 shimmer-border glass-card transition-all duration-300",
              selected === "pro" && "bg-gradient-to-br from-blue-950/40 via-card to-cyan-950/20"
            )}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
                    <Shield className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <p className="text-lg font-black">Pro</p>
                    <p className="text-[11px] text-muted-foreground">
                      {lang === "ko" ? "전문 분석가를 위한 도구" : "Tools for serious analysts"}
                    </p>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="flex items-baseline gap-0.5">
                    <span className="text-xs text-blue-400 font-medium">₩</span>
                    <span className={cn(
                      "text-2xl font-black text-blue-400",
                      selected === "pro" && "shimmer-text"
                    )}>4,900</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">{lang === "ko" ? "/월" : "/mo"}</p>
                </div>
              </div>

              {/* 핵심 기능 */}
              <div className="mt-4 space-y-2.5">
                {[
                  lang === "ko" ? "실시간 글로벌 이슈 지도" : "Real-time global issue map",
                  lang === "ko" ? "관심 국가 5개 + 속보 알림" : "5 countries + Breaking alerts",
                  lang === "ko" ? "KScore 필터 + 30일 히스토리" : "KScore filter + 30-day history",
                ].map((text, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="h-5 w-5 rounded-full bg-blue-500/15 flex items-center justify-center shrink-0">
                      <Check className="h-3 w-3 text-blue-400" />
                    </div>
                    <span className="text-xs text-foreground/80">{text}</span>
                  </div>
                ))}
              </div>

              {/* 구독 버튼 */}
              {currentPlan === "pro" ? (
                <div className="mt-5 w-full rounded-xl py-3 text-xs font-semibold text-center bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {t(lang, "upgrade_current_plan")}
                </div>
              ) : currentPlan === "pro_plus" ? (
                <button
                  onClick={(e) => { e.stopPropagation(); handleDowngrade(); }}
                  disabled={loading === "downgrade"}
                  className="mt-5 w-full rounded-xl py-3 text-xs font-medium text-center text-orange-400/80 border border-orange-500/20 hover:bg-orange-500/10 transition-colors disabled:opacity-50"
                >
                  {loading === "downgrade" ? t(lang, "upgrade_processing") : t(lang, "upgrade_downgrade_pro")}
                </button>
              ) : !isWeb ? (
                <button
                  onClick={(e) => { e.stopPropagation(); handleSubscribe("pro"); }}
                  disabled={loading === "pro"}
                  className={cn(
                    "btn-shine mt-5 w-full rounded-xl py-3 text-sm font-bold transition-all duration-200",
                    "bg-gradient-to-r from-blue-500 to-cyan-500 text-white",
                    "hover:shadow-lg hover:shadow-blue-500/25 hover:-translate-y-0.5",
                    "active:scale-[0.98] active:shadow-none",
                    "disabled:opacity-50"
                  )}
                >
                  {loading === "pro" ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      {t(lang, "upgrade_processing")}
                    </span>
                  ) : t(lang, "upgrade_subscribe")}
                </button>
              ) : (
                <div className="mt-5 w-full rounded-xl py-3 text-sm font-semibold text-center bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {t(lang, "store_subscribe_in_app")}
                </div>
              )}
            </div>
          </div>

          {/* Pro+ 카드 — 퍼플 프리미엄 */}
          <div
            className={cn(
              "card-enter card-enter-3 relative rounded-2xl p-[2px] cursor-pointer transition-all duration-300",
              selected === "pro_plus"
                ? "glow-purple bg-gradient-to-br from-purple-500 via-pink-500 to-purple-600"
                : "bg-border/40 hover:bg-gradient-to-br hover:from-purple-500/50 hover:via-pink-500/50 hover:to-purple-600/50"
            )}
            onClick={() => setSelected("pro_plus")}
          >
            {/* 최고 배지 */}
            <div className="absolute -top-3.5 left-0 right-0 flex justify-center z-10 badge-float">
              <div className="flex items-center gap-1 rounded-full bg-gradient-to-r from-purple-500 to-pink-500 px-4 py-1 shadow-lg shadow-purple-500/25">
                <Crown className="h-3 w-3 text-white" />
                <span className="text-[11px] font-bold text-white">
                  {lang === "ko" ? "최고" : "Best"}
                </span>
              </div>
            </div>

            <div className={cn(
              "rounded-[14px] bg-card p-5 shimmer-border glass-card transition-all duration-300",
              selected === "pro_plus" && "bg-gradient-to-br from-purple-950/40 via-card to-pink-950/20"
            )}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-purple-500/20">
                    <Star className="h-5 w-5 text-white" />
                  </div>
                  <div>
                    <p className="text-lg font-black">Pro+</p>
                    <p className="text-[11px] text-muted-foreground">
                      {lang === "ko" ? "전체 기능 잠금 해제" : "Unlock everything"}
                    </p>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="flex items-baseline gap-0.5">
                    <span className="text-xs text-purple-400 font-medium">₩</span>
                    <span className={cn(
                      "text-2xl font-black text-purple-400",
                      selected === "pro_plus" && "shimmer-text"
                    )}>9,900</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">{lang === "ko" ? "/월" : "/mo"}</p>
                </div>
              </div>

              {/* 핵심 기능 */}
              <div className="mt-4 space-y-2.5">
                {[
                  lang === "ko" ? "Pro 모든 기능 포함" : "Everything in Pro",
                  lang === "ko" ? "무제한 국가 + KScore 1.5~10.0" : "Unlimited countries + KScore 1.5~10.0",
                  lang === "ko" ? "90일 전체 히스토리" : "Full 90-day history",
                ].map((text, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="h-5 w-5 rounded-full bg-purple-500/15 flex items-center justify-center shrink-0">
                      <Check className="h-3 w-3 text-purple-400" />
                    </div>
                    <span className="text-xs text-foreground/80">{text}</span>
                  </div>
                ))}
              </div>

              {/* 구독 버튼 */}
              {currentPlan === "pro_plus" ? (
                <div className="mt-5 w-full rounded-xl py-3 text-xs font-semibold text-center bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {t(lang, "upgrade_current_plan")}
                </div>
              ) : !isWeb ? (
                <button
                  onClick={(e) => { e.stopPropagation(); handleSubscribe("pro_plus"); }}
                  disabled={loading === "pro_plus"}
                  className={cn(
                    "btn-shine mt-5 w-full rounded-xl py-3 text-sm font-bold transition-all duration-200",
                    "bg-gradient-to-r from-purple-500 to-pink-500 text-white",
                    "hover:shadow-lg hover:shadow-purple-500/25 hover:-translate-y-0.5",
                    "active:scale-[0.98] active:shadow-none",
                    "disabled:opacity-50"
                  )}
                >
                  {loading === "pro_plus" ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      {t(lang, "upgrade_processing")}
                    </span>
                  ) : currentPlan === "pro"
                    ? (lang === "ko" ? "Pro+로 업그레이드" : "Upgrade to Pro+")
                    : t(lang, "upgrade_subscribe")}
                </button>
              ) : (
                <div className="mt-5 w-full rounded-xl py-3 text-sm font-semibold text-center bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {t(lang, "store_subscribe_in_app")}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ── 상세 비교 표 ── */}
        <div className="mt-12" style={{ animation: "fadeSlideUp 0.5s ease 0.4s both" }}>
          <h3 className="text-xs font-bold mb-4 text-center text-muted-foreground uppercase tracking-widest">
            {lang === "ko" ? "플랜 상세 비교" : "Detailed Comparison"}
          </h3>
          <div className="rounded-2xl border border-border overflow-hidden">
            {/* 헤더 */}
            <div className="grid grid-cols-4 bg-muted/30 text-[11px] font-bold">
              <div className="p-3 text-muted-foreground">{lang === "ko" ? "기능" : "Feature"}</div>
              <div className="p-3 text-center text-muted-foreground">Free</div>
              <div className="p-3 text-center text-blue-400">Pro</div>
              <div className="p-3 text-center text-purple-400">Pro+</div>
            </div>
            {/* 행 */}
            {FEATURES.map((f, i) => (
              <div key={f.labelKo} className={cn(
                "grid grid-cols-4 items-center text-[11px] border-t border-border/50",
                i % 2 === 0 ? "bg-background" : "bg-muted/10"
              )}>
                <div className="p-3 text-muted-foreground font-medium">
                  {lang === "ko" ? f.labelKo : f.labelEn}
                </div>
                <div className="p-3 text-center">
                  <FeatureValue val={f.free} planId="free" lang={lang} />
                </div>
                <div className="p-3 text-center">
                  <FeatureValue val={f.pro} planId="pro" lang={lang} />
                </div>
                <div className="p-3 text-center">
                  <FeatureValue val={f.proplus} planId="pro_plus" lang={lang} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 푸터 */}
        <div className="mt-8 text-center text-[11px] text-muted-foreground space-y-1 pb-4">
          <p style={{ wordBreak: "keep-all", lineHeight: "1.7" }}>
            {lang === "ko"
              ? "구독 취소 시 현재 결제 기간 만료까지 서비스 이용 가능"
              : "Cancel anytime · Service continues until current billing period ends"}
          </p>
          <p>
            <a href="/terms" className="hover:underline">{t(lang, "terms_title")}</a>
            {" · "}
            <a href="/privacy" className="hover:underline">{t(lang, "privacy_title")}</a>
          </p>
        </div>
      </div>
    </div>
  );
}

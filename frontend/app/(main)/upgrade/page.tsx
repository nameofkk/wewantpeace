"use client";

import { useState, useEffect, useMemo, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Check, X, Zap, Shield, Star, Crown, ArrowLeft, Sparkles, ExternalLink, Tag } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { detectPlatform, type AppPlatform } from "@/lib/platform-detect";
import { isTossMiniApp } from "@/lib/platform";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { API_BASE, useMe, createDodoCheckout } from "@/lib/api";
import { DodoPayments } from "dodopayments-checkout";
import AppTour from "@/components/ui/AppTour";
import TourHelpButton from "@/components/ui/TourHelpButton";
import type { Step } from "react-joyride";

interface Feature {
  labelKo: string;
  labelEn: string;
  free: boolean | { ko: string; en: string };
  pro: boolean | { ko: string; en: string };
  proplus: boolean | { ko: string; en: string };
}

const FEATURES: Feature[] = [
  {
    labelKo: "관심 국가",              labelEn: "Monitored countries",
    free: { ko: "2개", en: "2" },      pro: { ko: "5개", en: "5" },      proplus: { ko: "무제한", en: "Unlimited" },
  },
  {
    labelKo: "기준국가",                labelEn: "Home country",
    free: { ko: "BASIC 고정", en: "BASIC only" }, pro: true,              proplus: true,
  },
  {
    labelKo: "실시간 이슈 지도",       labelEn: "Real-time issue map",
    free: false,                       pro: true,                       proplus: true,
  },
  {
    labelKo: "글로벌 트렌딩",          labelEn: "Global trending",
    free: true,                        pro: true,                       proplus: true,
  },
  {
    labelKo: "속보 알림",               labelEn: "Fast alerts",
    free: true,                        pro: true,                       proplus: true,
  },
  {
    labelKo: "신뢰 알림",              labelEn: "Verified alerts",
    free: false,                       pro: true,                       proplus: true,
  },
  {
    labelKo: "일일 알림 상한",         labelEn: "Daily alert limit",
    free: { ko: "5건", en: "5" },      pro: { ko: "20건", en: "20" },    proplus: { ko: "100건", en: "100" },
  },
  {
    labelKo: "긴급 상한 무시",         labelEn: "Critical bypass",
    free: false,                       pro: true,                       proplus: true,
  },
  {
    labelKo: "KScore 필터",             labelEn: "KScore filter",
    free: { ko: "3.0 고정", en: "3.0 fixed" }, pro: { ko: "3.0~10.0", en: "3.0~10.0" }, proplus: { ko: "1.5~10.0", en: "1.5~10.0" },
  },
  {
    labelKo: "토픽 필터",              labelEn: "Topic filter",
    free: false,                       pro: true,                       proplus: true,
  },
  {
    labelKo: "방해금지 시간",          labelEn: "Quiet hours",
    free: false,                       pro: true,                       proplus: true,
  },
  {
    labelKo: "긴장도 히스토리",        labelEn: "Tension history",
    free: { ko: "7일", en: "7d" },     pro: { ko: "30일", en: "30d" },   proplus: { ko: "90일", en: "90d" },
  },
  {
    labelKo: "KScore 히스토리",        labelEn: "KScore history",
    free: { ko: "7일", en: "7d" },     pro: { ko: "30일", en: "30d" },   proplus: { ko: "90일", en: "90d" },
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

function FeatureValue({
  val, planId, lang,
}: { val: boolean | string | { ko: string; en: string }; planId: string; lang: Lang }) {
  if (val === true) {
    const color = planId === "pro_plus" ? "text-purple-400" : planId === "pro" ? "text-blue-400" : "text-green-500";
    return <Check className={cn("h-4 w-4 mx-auto", color)} />;
  }
  if (val === false) return <X className="h-4 w-4 mx-auto text-muted-foreground/30" />;
  const text = typeof val === "object" ? (lang === "ko" ? val.ko : val.en) : val;
  return (
    <span className={cn(
      "text-[10px] font-medium whitespace-nowrap",
      planId === "pro_plus" ? "text-purple-400" : planId === "pro" ? "text-blue-400" : "text-muted-foreground"
    )}>
      {text}
    </span>
  );
}


export default function UpgradePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <UpgradeContent />
    </Suspense>
  );
}

function UpgradeContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const source = searchParams.get("source");
  const { user } = useAuth();
  const { lang } = useAppStore();
  const { data: me } = useMe();
  const currentPlan = (me as { plan?: string })?.plan ?? "free";
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [trialUsed, setTrialUsed] = useState(false);
  const [isCurrentlyTrial, setIsCurrentlyTrial] = useState(false);
  const [trialEnd, setTrialEnd] = useState<string | null>(null);
  const [trialSuccess, setTrialSuccess] = useState(false);
  const [promoOpen, setPromoOpen] = useState(false);
  const [promoCode, setPromoCode] = useState("");
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoSuccess, setPromoSuccess] = useState(false);

  // trial 사용 이력 확인: /subscriptions/my 에서 status가 trial인 이력이 있으면 사용됨
  useEffect(() => {
    (async () => {
      try {
        const devUid = typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (devUid) {
          headers["X-Dev-UID"] = devUid;
        } else {
          const { getIdToken } = await import("@/lib/auth");
          const token = await getIdToken();
          if (token) headers["Authorization"] = `Bearer ${token}`;
        }
        const res = await fetch(`${API_BASE}/subscriptions/my`, { headers });
        if (res.ok) {
          const data = await res.json();
          // trial_end가 있으면 trial 사용 이력 있음
          if (data.trial_end) {
            setTrialUsed(true);
          }
          if (data.status === "trial") {
            setIsCurrentlyTrial(true);
            setTrialUsed(true);
            if (data.trial_end) setTrialEnd(data.trial_end);
          }
        }
      } catch { /* ignore */ }
    })();
  }, []);
  // ── 가이드 투어 ──────────────────────────────────────────
  const [tourRun, setTourRun] = useState(false);
  const tourSteps: Step[] = useMemo(() => [
    {
      target: "[data-tour='upgrade-page']",
      content: t(lang, "tour_upgrade_page_role"),
      placement: "center" as const,
      disableBeacon: true,
    },
    {
      target: "[data-tour='upgrade-comparison']",
      content: t(lang, "tour_upgrade_comparison"),
    },
  ], [lang]);

  const [selected, setSelected] = useState<"pro" | "pro_plus">("pro");
  const [platform, setPlatform] = useState<AppPlatform>("web");
  const [cancelSuccess, setCancelSuccess] = useState<string | null>(null);

  useEffect(() => {
    setPlatform(detectPlatform());
    // DodoPayments Overlay SDK 초기화
    DodoPayments.Initialize({
      mode: "live",
      displayType: "overlay",
      onEvent: (event: { event_type: string }) => {
        if (event.event_type === "checkout.closed") {
          setLoading(null);
        }
      },
    });
  }, []);

  // 현재 플랜에 따라 기본 선택 변경
  useEffect(() => {
    if (currentPlan === "pro") setSelected("pro_plus");
  }, [currentPlan]);

  async function handleSubscribe(planId: string) {
    if (planId === "free") return;
    if (!user) { window.location.href = "/login?returnUrl=/upgrade"; return; }

    setLoading(planId);
    setError(null);

    try {
      if (isWeb) {
        await handleDodoCheckout(planId);
      } else if (platform === "android-native" || platform === "android-twa") {
        await handleAndroidPurchase(planId);
      } else if (platform === "ios-native" || platform === "ios-app") {
        await handleIOSPurchase(planId);
      }
    } catch (e: unknown) {
      const err = e as { message?: string; body?: { detail?: { code?: string; message?: string } | string } };
      const code = typeof err.body?.detail === "object" ? err.body?.detail?.code : "";
      if (code === "ALREADY_SUBSCRIBED") {
        setError(lang === "ko" ? "이미 활성 구독이 있습니다. 설정에서 현재 구독을 확인해주세요." : "You already have an active subscription. Please check your current plan in Settings.");
      } else {
        setError(err.message || t(lang, "upgrade_payment_error"));
      }
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

  async function handleStartTrial() {
    if (!user) { window.location.href = "/login?returnUrl=/upgrade"; return; }
    setLoading("trial");
    setError(null);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/subscriptions/start-trial`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || t(lang, "trial_already_used"));
        return;
      }
      setTrialSuccess(true);
      router.push(`/upgrade/success?plan=pro&trial=true`);
    } catch {
      setError(t(lang, "upgrade_payment_error"));
    } finally {
      setLoading(null);
    }
  }

  async function handleRedeemPromo() {
    if (!user) { window.location.href = "/login?returnUrl=/upgrade"; return; }
    if (!promoCode.trim()) return;
    setPromoLoading(true);
    setError(null);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/subscriptions/redeem-promo`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ code: promoCode.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        const code = data?.detail?.code || data?.detail || "";
        if (code === "INVALID_PROMO_CODE") {
          setError(t(lang, "promo_invalid"));
        } else if (code === "PROMO_ALREADY_USED") {
          setError(t(lang, "promo_already_used"));
        } else if (code === "ALREADY_PAID_PLAN") {
          setError(t(lang, "promo_already_paid"));
        } else {
          setError(t(lang, "promo_invalid"));
        }
        return;
      }
      setPromoSuccess(true);
      setTimeout(() => { window.location.reload(); }, 1500);
    } catch {
      setError(t(lang, "upgrade_payment_error"));
    } finally {
      setPromoLoading(false);
    }
  }

  async function handleAndroidPurchase(planId: string) {
    const { purchaseSubscription } = await import("@/lib/play-billing");
    const { isReactNative } = await import("@/lib/platform-detect");
    const productId = GOOGLE_PRODUCT_IDS[planId];
    if (!productId) throw new Error("Invalid plan");

    const authToken = await user!.getIdToken();

    // React Native: 브릿지를 통해 결제 (네이티브가 검증까지 처리)
    if (isReactNative()) {
      const result = await purchaseSubscription(productId, authToken);
      if (!result) return; // 취소
      router.push(`/upgrade/success?plan=${planId}`);
      return;
    }

    // TWA: Digital Goods API
    const purchaseToken = await purchaseSubscription(productId);
    if (!purchaseToken) return;

    const res = await fetch(`${API_BASE}/subscriptions/store/google/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ purchase_token: purchaseToken, product_id: productId, source: source || undefined }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || t(lang, "upgrade_payment_failed"));
    }

    router.push(`/upgrade/success?plan=${planId}`);
  }

  async function handleIOSPurchase(planId: string) {
    const { isReactNative } = await import("@/lib/platform-detect");
    const productId = APPLE_PRODUCT_IDS[planId];
    if (!productId) throw new Error("Invalid plan");

    // React Native iOS: 브릿지를 통해 결제 (네이티브가 검증까지 처리)
    if (isReactNative()) {
      const { purchaseSubscription } = await import("@/lib/play-billing");
      const authToken = await user!.getIdToken();
      const result = await purchaseSubscription(productId, authToken);
      if (!result) return;
      router.push(`/upgrade/success?plan=${planId}`);
      return;
    }

    // WKWebView StoreKit 브릿지
    const { purchaseViaStoreKit } = await import("@/lib/ios-storekit");
    const result = await purchaseViaStoreKit(productId);
    if (!result) return;

    const token = await user!.getIdToken();
    const res = await fetch(`${API_BASE}/subscriptions/store/apple/verify`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ transaction_id: result.transactionId, product_id: productId, source: source || undefined }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || t(lang, "upgrade_payment_failed"));
    }

    router.push(`/upgrade/success?plan=${planId}`);
  }

  async function handleDodoCheckout(planId: string) {
    const { checkout_url } = await createDodoCheckout(planId);
    if (checkout_url) {
      await DodoPayments.Checkout.open({ checkoutUrl: checkout_url });
    }
  }

  const isWeb = platform === "web" && !isTossMiniApp();

  return (
    <div className="min-h-screen bg-background" data-tour="upgrade-page">
      <AppTour tourId="upgrade" steps={tourSteps} run={tourRun} onComplete={() => setTourRun(false)} />
      <TourHelpButton tourId="upgrade" onStartTour={() => setTourRun(true)} />
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

        {/* source 안내 배너 */}
        {source && (
          <div className="mb-4 flex items-center gap-2 rounded-xl bg-primary/5 border border-primary/20 px-4 py-2.5 text-xs text-primary" style={{ animation: "fadeSlideUp 0.3s ease both" }}>
            <ExternalLink className="h-3.5 w-3.5 shrink-0" />
            <span>{t(lang, "upgrade_source_from", { source: t(lang, `source_${source}` as any) || source })}</span>
          </div>
        )}

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

        {trialSuccess && (
          <div className="mb-6 rounded-lg bg-blue-500/10 border border-blue-500/20 px-4 py-3 text-sm text-blue-400 text-center">
            {t(lang, "trial_success")}
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
                    <span className="text-xs text-blue-400 font-medium">$</span>
                    <span className={cn(
                      "text-2xl font-black text-blue-400",
                      selected === "pro" && "shimmer-text"
                    )}>3.90</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">{lang === "ko" ? "/월 · 세금 별도" : "/mo · excl. tax"}</p>
                </div>
              </div>

              {/* 핵심 기능 */}
              <div className="mt-4 space-y-2.5">
                {[
                  lang === "ko" ? "실시간 글로벌 이슈 지도" : "Real-time global issue map",
                  lang === "ko" ? "관심 국가 5개 · 신뢰 알림" : "5 countries · Verified alerts",
                  lang === "ko" ? "내 국가 변경 · 토픽 필터" : "Home country · Topic filter",
                  lang === "ko" ? "KScore 필터 · 30일 히스토리" : "KScore filter · 30-day history",
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
              {currentPlan === "pro" && isCurrentlyTrial ? (
                <div className="mt-5 space-y-2">
                  <div className="w-full rounded-xl py-2.5 text-xs font-semibold text-center bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    {t(lang, "settings_plan_status_trial")}
                    {trialEnd && (() => {
                      const d = Math.max(0, Math.ceil((new Date(trialEnd).getTime() - Date.now()) / 86400000));
                      return <span className="ml-1.5 text-[10px] opacity-80">({t(lang, "trial_remaining_days", { n: d })})</span>;
                    })()}
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleSubscribe("pro"); }}
                    disabled={loading === "pro"}
                    className={cn(
                      "btn-shine w-full rounded-xl py-3 text-sm font-bold transition-all duration-200",
                      "bg-gradient-to-r from-blue-500 to-cyan-500 text-white",
                      "hover:shadow-lg hover:shadow-blue-500/25 hover:-translate-y-0.5",
                      "active:scale-[0.98] active:shadow-none",
                      "disabled:opacity-50"
                    )}
                  >
                    {loading === "pro" ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                        {isWeb ? t(lang, "web_subscribe_loading") : t(lang, "upgrade_processing")}
                      </span>
                    ) : isWeb ? t(lang, "web_subscribe_button") : t(lang, "upgrade_subscribe")}
                  </button>
                </div>
              ) : currentPlan === "pro" && !isCurrentlyTrial ? (
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
                <div className="mt-5 space-y-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleSubscribe("pro"); }}
                    disabled={loading === "pro"}
                    className={cn(
                      "btn-shine w-full rounded-xl py-3 text-sm font-bold transition-all duration-200",
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
                  {currentPlan === "free" && !trialUsed && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleStartTrial(); }}
                      disabled={loading === "trial"}
                      className="w-full rounded-xl py-2.5 text-xs font-semibold text-center text-blue-400 border border-blue-500/30 hover:bg-blue-500/10 transition-colors disabled:opacity-50"
                    >
                      {loading === "trial" ? t(lang, "upgrade_processing") : t(lang, "trial_start_button")}
                    </button>
                  )}
                </div>
              ) : (
                <div className="mt-5 space-y-2">
                  <button
                    onClick={(e) => { e.stopPropagation(); handleSubscribe("pro"); }}
                    disabled={loading === "pro"}
                    className={cn(
                      "btn-shine w-full rounded-xl py-3 text-sm font-bold transition-all duration-200",
                      "bg-gradient-to-r from-blue-500 to-cyan-500 text-white",
                      "hover:shadow-lg hover:shadow-blue-500/25 hover:-translate-y-0.5",
                      "active:scale-[0.98] active:shadow-none",
                      "disabled:opacity-50"
                    )}
                  >
                    {loading === "pro" ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
                        {t(lang, "web_subscribe_loading")}
                      </span>
                    ) : t(lang, "web_subscribe_button")}
                  </button>
                  {currentPlan === "free" && !trialUsed && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleStartTrial(); }}
                      disabled={loading === "trial"}
                      className="w-full rounded-xl py-2.5 text-xs font-semibold text-center text-blue-400 border border-blue-500/30 hover:bg-blue-500/10 transition-colors disabled:opacity-50"
                    >
                      {loading === "trial" ? t(lang, "upgrade_processing") : t(lang, "trial_start_button")}
                    </button>
                  )}
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
                    <span className="text-xs text-purple-400 font-medium">$</span>
                    <span className={cn(
                      "text-2xl font-black text-purple-400",
                      selected === "pro_plus" && "shimmer-text"
                    )}>6.90</span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">{lang === "ko" ? "/월 · 세금 별도" : "/mo · excl. tax"}</p>
                </div>
              </div>

              {/* 핵심 기능 */}
              <div className="mt-4 space-y-2.5">
                {[
                  lang === "ko" ? "Pro 모든 기능 포함" : "Everything in Pro",
                  lang === "ko" ? "무제한 국가 · 일일 알림 100건" : "Unlimited countries · 100 daily alerts",
                  lang === "ko" ? "KScore 1.5~10.0 · 90일 히스토리" : "KScore 1.5~10.0 · 90-day history",
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
                      {t(lang, "web_subscribe_loading")}
                    </span>
                  ) : currentPlan === "pro"
                    ? (lang === "ko" ? "Pro+로 업그레이드" : "Upgrade to Pro+")
                    : t(lang, "web_subscribe_button")}
                </button>
              )}
            </div>
          </div>
        </div>

        {/* ── 상세 비교 표 ── */}
        <div className="mt-12" data-tour="upgrade-comparison" style={{ animation: "fadeSlideUp 0.5s ease 0.4s both" }}>
          <h3 className="text-xs font-bold mb-4 text-center text-muted-foreground uppercase tracking-widest">
            {lang === "ko" ? "플랜 상세 비교" : "Detailed Comparison"}
          </h3>
          <div className="rounded-2xl border border-border overflow-hidden">
            {/* 헤더 */}
            <div className="grid grid-cols-[2fr_1fr_1fr_1fr] bg-muted/30 text-[11px] font-bold">
              <div className="p-3 text-muted-foreground">{lang === "ko" ? "기능" : "Feature"}</div>
              <div className={cn("p-3 text-center", currentPlan === "free" && "bg-green-500/5")}>
                <span className="text-muted-foreground">🌐 Free</span>
              </div>
              <div className={cn("p-3 text-center", currentPlan === "pro" && "bg-blue-500/5")}>
                <span className="text-blue-400">🛡️ Pro</span>
              </div>
              <div className={cn("p-3 text-center", currentPlan === "pro_plus" && "bg-purple-500/5")}>
                <span className="text-purple-400">⭐ Pro+</span>
              </div>
            </div>
            {/* 행 */}
            {FEATURES.map((f, i) => {
              const hasValue = (v: boolean | string | { ko: string; en: string }) => typeof v === "object" || (typeof v === "string");
              return (
                <div key={f.labelKo} className={cn(
                  "grid grid-cols-[2fr_1fr_1fr_1fr] items-center text-[11px] border-t border-border/50 transition-colors hover:bg-muted/20",
                  i % 2 === 0 ? "bg-background" : "bg-muted/10"
                )}>
                  <div className="p-3 text-muted-foreground font-medium" style={{ wordBreak: "keep-all" }}>
                    {lang === "ko" ? f.labelKo : f.labelEn}
                  </div>
                  <div className={cn("p-3 text-center", currentPlan === "free" && "bg-green-500/5", hasValue(f.free) && "font-bold")} style={{ wordBreak: "keep-all" }}>
                    <FeatureValue val={f.free} planId="free" lang={lang} />
                  </div>
                  <div className={cn("p-3 text-center", currentPlan === "pro" && "bg-blue-500/5", hasValue(f.pro) && "font-bold")} style={{ wordBreak: "keep-all" }}>
                    <FeatureValue val={f.pro} planId="pro" lang={lang} />
                  </div>
                  <div className={cn("p-3 text-center", currentPlan === "pro_plus" && "bg-purple-500/5", hasValue(f.proplus) && "font-bold")} style={{ wordBreak: "keep-all" }}>
                    <FeatureValue val={f.proplus} planId="pro_plus" lang={lang} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── 프로모 코드 ── */}
        {currentPlan === "free" && (
          <div className="mt-8 text-center" style={{ animation: "fadeSlideUp 0.5s ease 0.5s both" }}>
            {promoSuccess ? (
              <div className="rounded-xl bg-green-500/10 border border-green-500/20 px-4 py-3 text-sm text-green-400 font-semibold">
                {t(lang, "promo_success")}
              </div>
            ) : !promoOpen ? (
              <button
                onClick={() => setPromoOpen(true)}
                className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary transition-colors"
              >
                <Tag className="h-3 w-3" />
                {t(lang, "promo_have_code")}
              </button>
            ) : (
              <div className="flex items-center gap-2 max-w-xs mx-auto">
                <input
                  type="text"
                  value={promoCode}
                  onChange={(e) => setPromoCode(e.target.value.toUpperCase())}
                  onKeyDown={(e) => e.key === "Enter" && handleRedeemPromo()}
                  placeholder={t(lang, "promo_input_placeholder")}
                  className="flex-1 rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-primary/30"
                  autoFocus
                />
                <button
                  onClick={handleRedeemPromo}
                  disabled={promoLoading || !promoCode.trim()}
                  className="rounded-xl bg-primary px-4 py-2 text-sm font-bold text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {promoLoading ? (
                    <span className="h-4 w-4 rounded-full border-2 border-primary-foreground border-t-transparent animate-spin inline-block" />
                  ) : t(lang, "promo_redeem")}
                </button>
              </div>
            )}
          </div>
        )}

        {/* 푸터 */}
        <div className="mt-8 text-center text-[11px] text-muted-foreground space-y-1 pb-4">
          <p style={{ wordBreak: "keep-all", lineHeight: "1.7" }}>
            {lang === "ko"
              ? "구독 취소 시 현재 결제 기간 만료까지 서비스 이용 가능"
              : "Cancel anytime · Service continues until current billing period ends"}
          </p>
          <p>
            <Link href="/terms" className="hover:underline">{t(lang, "terms_title")}</Link>
            {" · "}
            <Link href="/privacy" className="hover:underline">{t(lang, "privacy_title")}</Link>
          </p>
        </div>
      </div>
    </div>
  );
}

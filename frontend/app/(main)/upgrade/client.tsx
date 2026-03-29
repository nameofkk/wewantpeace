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
// DodoPayments SDK: Toss WebView에서 window.fetch 간섭 방지를 위해 dynamic import 사용
// import { DodoPayments } from "dodopayments-checkout";  // ← 삭제됨
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
    labelKo: "실시간 이슈 지도",       labelEn: "Real-time issue map",
    free: true,                        pro: true,                        proplus: true,
  },
  {
    labelKo: "글로벌 트렌딩",          labelEn: "Global trending",
    free: true,                        pro: true,                        proplus: true,
  },
  {
    labelKo: "영향 흐름도",            labelEn: "Impact flow",
    free: true,                        pro: true,                        proplus: true,
  },
  {
    labelKo: "종합 영향도",            labelEn: "Overall impact",
    free: true,                        pro: true,                        proplus: true,
  },
  {
    labelKo: "속보 알림",              labelEn: "Fast alerts",
    free: { ko: "5건", en: "5" },      pro: { ko: "20건", en: "20" },    proplus: { ko: "100건", en: "100" },
  },
  {
    labelKo: "관심 국가",              labelEn: "Monitored countries",
    free: { ko: "2개", en: "2" },      pro: { ko: "5개", en: "5" },      proplus: { ko: "무제한", en: "Unlimited" },
  },
  {
    labelKo: "기준국가",               labelEn: "Home country",
    free: { ko: "글로벌", en: "Global" }, pro: { ko: "개인화", en: "Custom" }, proplus: { ko: "개인화", en: "Custom" },
  },
  {
    labelKo: "KScore 필터",            labelEn: "KScore filter",
    free: { ko: "4.0 고정", en: "4.0 fixed" }, pro: { ko: "3.0~10.0", en: "3.0~10.0" }, proplus: { ko: "1.5~10.0", en: "1.5~10.0" },
  },
  {
    labelKo: "긴장도 히스토리",        labelEn: "Tension history",
    free: { ko: "7일", en: "7d" },     pro: { ko: "30일", en: "30d" },   proplus: { ko: "90일", en: "90d" },
  },
  {
    labelKo: "KScore 히스토리",        labelEn: "KScore history",
    free: { ko: "7일", en: "7d" },     pro: { ko: "30일", en: "30d" },   proplus: { ko: "90일", en: "90d" },
  },
  {
    labelKo: "신뢰 알림",              labelEn: "Verified alerts",
    free: false,                       pro: true,                        proplus: true,
  },
  {
    labelKo: "토픽 필터",              labelEn: "Topic filter",
    free: false,                       pro: true,                        proplus: true,
  },
  {
    labelKo: "방해금지 시간",          labelEn: "Quiet hours",
    free: false,                       pro: true,                        proplus: true,
  },
  {
    labelKo: "Intel 레이어",                   labelEn: "Intel layers",
    free: { ko: "데모", en: "Demo" },  pro: true,                        proplus: true,
  },
  {
    labelKo: "교차검증 시그널",        labelEn: "Cross-verification",
    free: { ko: "데모", en: "Demo" },  pro: true,                        proplus: true,
  },
  {
    labelKo: "AI 영향 분석",           labelEn: "AI impact analysis",
    free: { ko: "데모", en: "Demo" },  pro: true,                        proplus: true,
  },
  {
    labelKo: "홈 산업별 리스크 개요",  labelEn: "Sector risk overview",
    free: { ko: "데모", en: "Demo" },  pro: true,                        proplus: true,
  },
  {
    labelKo: "이슈별 산업 리스크",     labelEn: "Per-issue sector risk",
    free: { ko: "데모", en: "Demo" },  pro: { ko: "데모", en: "Demo" },  proplus: true,
  },
  {
    labelKo: "주간 리포트",            labelEn: "Weekly report",
    free: { ko: "준비중", en: "Soon" }, pro: { ko: "준비중", en: "Soon" }, proplus: { ko: "준비중", en: "Soon" },
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

type BillingCycle = "monthly" | "annual" | "lifetime";

const PRICING = {
  pro:      { monthly: 6.99, annual: 62.99, annualPerMonth: 5.25, lifetime: 149.99 },
  pro_plus: { monthly: 9.99, annual: 89.99, annualPerMonth: 7.50, lifetime: 199.99 },
} as const;

const ANNUAL_DISCOUNT = 25; // %
const ANNUAL_MONTHS_FREE = 3;

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
  const redirectError = searchParams.get("error");
  const { user, loading: authLoading } = useAuth();
  const { lang } = useAppStore();
  const { data: me } = useMe();
  const currentPlan = (me as { plan?: string })?.plan ?? "free";
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(redirectError);
  const [trialUsed, setTrialUsed] = useState(false);
  const [isCurrentlyTrial, setIsCurrentlyTrial] = useState(false);
  const [trialEnd, setTrialEnd] = useState<string | null>(null);
  const [trialSuccess, setTrialSuccess] = useState(false);
  const [promoOpen, setPromoOpen] = useState(false);
  const [promoCode, setPromoCode] = useState("");
  const [promoLoading, setPromoLoading] = useState(false);
  const [promoSuccess, setPromoSuccess] = useState(false);
  const [currentBillingInterval, setCurrentBillingInterval] = useState<string>("monthly");

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
          if (data.billing_interval) {
            setCurrentBillingInterval(data.billing_interval);
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
  const [billingCycle, setBillingCycle] = useState<BillingCycle>("annual");
  const [platform, setPlatform] = useState<AppPlatform>("web");
  const [cancelSuccess, setCancelSuccess] = useState<string | null>(null);

  useEffect(() => {
    setPlatform(detectPlatform());
    // 토스 WebView: DodoPayments SDK 로드 자체를 하지 않음 (fetch 간섭 방지)
    if (!isTossMiniApp()) {
      import("dodopayments-checkout").then(({ DodoPayments }) => {
        DodoPayments.Initialize({
          mode: "live",
          displayType: "overlay",
          onEvent: (event: { event_type: string }) => {
            if (event.event_type === "checkout.closed") {
              setLoading(null);
            }
          },
        });
      }).catch((err) => {
        console.error("[Upgrade] DodoPayments SDK load failed:", err);
      });
    }
  }, []);

  // 현재 플랜에 따라 기본 선택 변경
  useEffect(() => {
    if (currentPlan === "pro") setSelected("pro_plus");
  }, [currentPlan]);

  async function handleSubscribe(planId: string) {
    if (planId === "free") return;
    if (authLoading) return;
    if (!user) { window.location.href = "/login?returnUrl=/upgrade"; return; }

    // 라이프타임 구독자가 월간/연간으로 전환 시도 → 차단
    if (currentPlan === planId && currentBillingInterval === "lifetime" && billingCycle !== "lifetime") {
      setError(lang === "ko"
        ? "이미 평생 이용권을 보유하고 있습니다. 월간/연간 전환이 필요하지 않습니다."
        : "You already have a lifetime plan. No need to switch to monthly/annual.");
      return;
    }

    // 같은 플랜인데 결제 주기만 바꾸는 경우 확인
    if (currentPlan === planId && billingCycle !== currentBillingInterval && !isCurrentlyTrial) {
      const cycleLabel = billingCycle === "annual"
        ? (lang === "ko" ? "연간" : "Annual")
        : billingCycle === "lifetime"
          ? (lang === "ko" ? "평생" : "Lifetime")
          : (lang === "ko" ? "월간" : "Monthly");
      const confirmed = confirm(
        lang === "ko"
          ? `현재 구독을 ${cycleLabel} 결제로 전환하시겠습니까? 기존 구독은 즉시 취소되고 새 결제가 진행됩니다.`
          : `Switch to ${cycleLabel} billing? Your current subscription will be cancelled and a new payment will be processed.`
      );
      if (!confirmed) return;
    }

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
      const err = e as { message?: string; status?: number; body?: { detail?: string } };
      console.error("[Upgrade] error:", err);
      const detail = typeof err.body?.detail === "string" ? err.body.detail : "";
      if (err.status === 409 && detail) {
        setError(detail);
      } else {
        setError(detail || err.message || t(lang, "upgrade_payment_error"));
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
        // detail은 string으로 통일 (서버에서 한국어 메시지 전달)
        const detail = typeof data?.detail === "string" ? data.detail : "";
        if (res.status === 400) {
          setError(detail || t(lang, "promo_invalid"));
        } else if (res.status === 409) {
          setError(detail || t(lang, "promo_already_used"));
        } else {
          setError(detail || t(lang, "promo_invalid"));
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
    const { purchaseSubscription, isDigitalGoodsAvailable } = await import("@/lib/play-billing");
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

    // TWA: Digital Goods API 시도 → 실패 시 DodoPayments 웹 결제로 자동 폴백
    if (isDigitalGoodsAvailable()) {
      try {
        const purchaseToken = await purchaseSubscription(productId);
        if (!purchaseToken) return; // 사용자 취소

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
        return;
      } catch (dgErr) {
        // Digital Goods API 사용 불가 (Android 13+ DelegationService 버그 등)
        // → DodoPayments 웹 결제로 자동 전환
        console.warn("[Upgrade] Play Billing 불가, 웹 결제 전환:", dgErr);
      }
    }

    // Digital Goods API 미지원 또는 실패 → DodoPayments 웹 결제
    await handleDodoCheckout(planId);
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
    // 토스 WebView든 일반 웹이든 20초 안에 끝나지 않으면 강제 에러
    const masterTimeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error(lang === "ko" ? "결제 처리 시간 초과. 잠시 후 다시 시도해주세요." : "Payment timeout. Please try again.")), 20000),
    );

    const doCheckout = async () => {
      if (isTossMiniApp()) {
        // Toss WebView: application/json fetch는 CORS preflight가 필요 → 차단됨
        // application/x-www-form-urlencoded은 "Simple Request"라 preflight 없음!
        if (!user) throw new Error(lang === "ko" ? "로그인이 필요합니다." : "Login required.");
        const token = await user.getIdToken();
        const params = new URLSearchParams();
        params.set("plan", planId);
        params.set("token", token);
        params.set("billing_interval", billingCycle);

        const ctrl = new AbortController();
        const tid = setTimeout(() => ctrl.abort(), 15000);

        let res: Response;
        try {
          res = await fetch(`${API_BASE}/payments/dodo/create-checkout-simple`, {
            method: "POST",
            body: params, // Content-Type: application/x-www-form-urlencoded 자동 설정
            signal: ctrl.signal,
          });
        } catch (e) {
          clearTimeout(tid);
          if ((e as Error).name === "AbortError") {
            throw new Error(lang === "ko" ? "결제 서버 응답 시간 초과 (15초). 잠시 후 다시 시도해주세요." : "Payment server timeout. Please try again.");
          }
          throw new Error(lang === "ko" ? `결제 서버에 연결할 수 없습니다. (${(e as Error).message})` : `Cannot reach payment server. (${(e as Error).message})`);
        }
        clearTimeout(tid);

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw Object.assign(
            new Error(typeof data.detail === "string" ? data.detail : data.detail?.message || "결제 생성 실패"),
            { status: res.status, body: data },
          );
        }

        const { checkout_url } = await res.json();
        if (!checkout_url) throw new Error(lang === "ko" ? "결제 URL을 생성하지 못했습니다." : "Failed to create checkout URL.");
        // Toss WebView: window.open으로 인앱 브라우저에서 열기 (location.href는 WebView 자체를 이동시켜 행 걸림)
        window.open(checkout_url, "_blank");
        return;
      }

      // 일반 웹: fetch + DodoPayments overlay
      const { checkout_url } = await createDodoCheckout(planId, billingCycle);
      if (!checkout_url) throw new Error("결제 URL을 생성하지 못했습니다.");
      const { DodoPayments } = await import("dodopayments-checkout");
      await DodoPayments.Checkout.open({ checkoutUrl: checkout_url });
    };

    await Promise.race([doCheckout(), masterTimeout]);
  }

  const isWeb = platform === "web";  // 토스 WebView도 웹 결제(DodoPayments) 사용

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
        <div className="text-center mb-6" style={{ animation: "fadeSlideUp 0.4s ease both" }}>
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

        {/* 결제 주기 토글 — Claude/ChatGPT 스타일 */}
        <div className="flex justify-center mb-8" style={{ animation: "fadeSlideUp 0.45s ease both" }}>
          <div className="inline-flex rounded-xl bg-muted/50 border border-border p-1 gap-0.5">
            {(["monthly", "annual", "lifetime"] as BillingCycle[]).map((cycle) => (
              <button
                key={cycle}
                onClick={() => setBillingCycle(cycle)}
                className={cn(
                  "relative rounded-lg px-3.5 py-2 text-xs font-semibold transition-all duration-200",
                  billingCycle === cycle
                    ? "bg-card text-foreground shadow-sm border border-border/50"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {cycle === "monthly" ? (lang === "ko" ? "월간" : "Monthly") :
                 cycle === "annual" ? (
                   <span className="flex items-center gap-1.5">
                     {lang === "ko" ? "연간" : "Annual"}
                     <span className="rounded-full bg-green-500/15 text-green-500 text-[9px] font-bold px-1.5 py-0.5 whitespace-nowrap">
                       -{ANNUAL_DISCOUNT}%
                     </span>
                   </span>
                 ) :
                 (lang === "ko" ? "평생" : "Lifetime")}
              </button>
            ))}
          </div>
        </div>

        {/* 체험판 중 결제 유도 배너 */}
        {isCurrentlyTrial && trialEnd && (() => {
          const daysLeft = Math.max(0, Math.ceil((new Date(trialEnd).getTime() - Date.now()) / 86400000));
          return (
            <div className="mb-6 rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 to-orange-500/10 p-4" style={{ animation: "fadeSlideUp 0.45s ease both" }}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-amber-400">
                  {lang === "ko" ? "무료 체험 중" : "Free Trial Active"}
                </span>
                <span className="text-xs font-semibold text-amber-400">
                  {t(lang, "trial_remaining_days", { n: daysLeft })}
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-amber-500/20 overflow-hidden mb-3">
                <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all"
                     style={{ width: `${Math.max(5, ((7 - daysLeft) / 7) * 100)}%` }} />
              </div>
              <p className="text-[11px] text-foreground/70 mb-2">
                {lang === "ko"
                  ? "체험 종료 후 Free 플랜으로 전환됩니다. 지금 구독하면 중단 없이 계속 이용하세요."
                  : "After trial ends, you'll switch to Free. Subscribe now for uninterrupted access."}
              </p>
              {billingCycle === "annual" && (
                <p className="text-[11px] font-semibold text-green-500">
                  {lang === "ko" ? "💡 연간 구독 시 3개월 무료!" : "💡 Get 3 months free with annual!"}
                </p>
              )}
            </div>
          );
        })()}

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
                  {billingCycle === "annual" && (
                    <p className="text-[10px] text-muted-foreground/50 line-through mb-0.5">${PRICING.pro.monthly.toFixed(2)}/mo</p>
                  )}
                  <div className="flex items-baseline gap-0.5">
                    <span className="text-xs text-blue-400 font-medium">$</span>
                    <span className={cn(
                      "text-2xl font-black text-blue-400",
                      selected === "pro" && "shimmer-text"
                    )}>
                      {billingCycle === "monthly" ? PRICING.pro.monthly.toFixed(2)
                       : billingCycle === "annual" ? PRICING.pro.annualPerMonth.toFixed(2)
                       : PRICING.pro.lifetime.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    {billingCycle === "monthly" ? (lang === "ko" ? "/월" : "/mo")
                     : billingCycle === "annual" ? (lang === "ko" ? `/월 · $${PRICING.pro.annual}/년` : `/mo · $${PRICING.pro.annual}/yr`)
                     : (lang === "ko" ? "일회성 결제" : "one-time")}
                  </p>
                </div>
              </div>

              {/* 핵심 기능 */}
              <div className="mt-4 space-y-2.5">
                {[
                  lang === "ko" ? "관심 국가 5개 · 신뢰 알림 · 토픽 필터" : "5 countries · Verified alerts · Topic filter",
                  lang === "ko" ? "AI 영향 분석 · 산업별 리스크 개요" : "AI impact analysis · Sector risk overview",
                  lang === "ko" ? "Intel 레이어 (위성·GPS·교역)" : "Intel layers (FIRMS·GPS·Trade)",
                  lang === "ko" ? "KScore 3.0~ · 30일 히스토리" : "KScore 3.0+ · 30-day history",
                ].map((text, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="h-5 w-5 rounded-full bg-blue-500/15 flex items-center justify-center shrink-0">
                      <Check className="h-3 w-3 text-blue-400" />
                    </div>
                    <span className="text-xs text-foreground/80">{text}</span>
                  </div>
                ))}
              </div>

              {/* 절약 배지 */}
              {billingCycle === "annual" && (
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-3 py-2">
                  <Tag className="h-3 w-3 text-green-500 shrink-0" />
                  <span className="text-[11px] text-green-500 font-medium whitespace-nowrap">
                    {lang === "ko" ? `${ANNUAL_MONTHS_FREE}개월 무료 · 연 $${(PRICING.pro.monthly * 12 - PRICING.pro.annual).toFixed(2)} 절약` : `${ANNUAL_MONTHS_FREE} months free · Save $${(PRICING.pro.monthly * 12 - PRICING.pro.annual).toFixed(2)}/yr`}
                  </span>
                </div>
              )}
              {billingCycle === "lifetime" && (
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2">
                  <Sparkles className="h-3 w-3 text-amber-500 shrink-0" />
                  <span className="text-[11px] text-amber-500 font-medium whitespace-nowrap">
                    {lang === "ko" ? "한 번 결제, 평생 이용" : "Pay once, use forever"}
                  </span>
                </div>
              )}

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
              ) : currentPlan === "pro" && !isCurrentlyTrial && billingCycle === currentBillingInterval ? (
                <div className="mt-5 w-full rounded-xl py-3 text-xs font-semibold text-center bg-blue-500/10 text-blue-400 border border-blue-500/20">
                  {t(lang, "upgrade_current_plan")}
                </div>
              ) : currentPlan === "pro" && !isCurrentlyTrial && billingCycle !== currentBillingInterval ? (
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
                      {isWeb ? t(lang, "web_subscribe_loading") : t(lang, "upgrade_processing")}
                    </span>
                  ) : lang === "ko"
                    ? `${billingCycle === "annual" ? "연간" : billingCycle === "lifetime" ? "평생" : "월간"}으로 전환`
                    : `Switch to ${billingCycle === "annual" ? "Annual" : billingCycle === "lifetime" ? "Lifetime" : "Monthly"}`}
                </button>
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
                  {billingCycle === "annual" && (
                    <p className="text-[10px] text-muted-foreground/50 line-through mb-0.5">${PRICING.pro_plus.monthly.toFixed(2)}/mo</p>
                  )}
                  <div className="flex items-baseline gap-0.5">
                    <span className="text-xs text-purple-400 font-medium">$</span>
                    <span className={cn(
                      "text-2xl font-black text-purple-400",
                      selected === "pro_plus" && "shimmer-text"
                    )}>
                      {billingCycle === "monthly" ? PRICING.pro_plus.monthly.toFixed(2)
                       : billingCycle === "annual" ? PRICING.pro_plus.annualPerMonth.toFixed(2)
                       : PRICING.pro_plus.lifetime.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    {billingCycle === "monthly" ? (lang === "ko" ? "/월" : "/mo")
                     : billingCycle === "annual" ? (lang === "ko" ? `/월 · $${PRICING.pro_plus.annual}/년` : `/mo · $${PRICING.pro_plus.annual}/yr`)
                     : (lang === "ko" ? "일회성 결제" : "one-time")}
                  </p>
                </div>
              </div>

              {/* 핵심 기능 */}
              <div className="mt-4 space-y-2.5">
                {[
                  lang === "ko" ? "Pro 모든 기능 포함" : "Everything in Pro",
                  lang === "ko" ? "무제한 국가 · 일일 100건 · KScore 1.5~" : "Unlimited countries · 100/day · KScore 1.5+",
                  lang === "ko" ? "이슈별 산업 리스크 · 주간 리포트" : "Per-issue sector risk · Weekly report",
                  lang === "ko" ? "90일 히스토리" : "90-day history",
                ].map((text, i) => (
                  <div key={i} className="flex items-center gap-2.5">
                    <div className="h-5 w-5 rounded-full bg-purple-500/15 flex items-center justify-center shrink-0">
                      <Check className="h-3 w-3 text-purple-400" />
                    </div>
                    <span className="text-xs text-foreground/80">{text}</span>
                  </div>
                ))}
              </div>

              {/* Pro+ 절약 배지 */}
              {billingCycle === "annual" && (
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-3 py-2">
                  <Tag className="h-3 w-3 text-green-500 shrink-0" />
                  <span className="text-[11px] text-green-500 font-medium whitespace-nowrap">
                    {lang === "ko" ? `${ANNUAL_MONTHS_FREE}개월 무료 · 연 $${(PRICING.pro_plus.monthly * 12 - PRICING.pro_plus.annual).toFixed(2)} 절약` : `${ANNUAL_MONTHS_FREE} months free · Save $${(PRICING.pro_plus.monthly * 12 - PRICING.pro_plus.annual).toFixed(2)}/yr`}
                  </span>
                </div>
              )}
              {billingCycle === "lifetime" && (
                <div className="mt-3 flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2">
                  <Sparkles className="h-3 w-3 text-amber-500 shrink-0" />
                  <span className="text-[11px] text-amber-500 font-medium whitespace-nowrap">
                    {lang === "ko" ? "한 번 결제, 평생 이용" : "Pay once, use forever"}
                  </span>
                </div>
              )}

              {/* 구독 버튼 */}
              {currentPlan === "pro_plus" && billingCycle === currentBillingInterval ? (
                <div className="mt-5 w-full rounded-xl py-3 text-xs font-semibold text-center bg-purple-500/10 text-purple-400 border border-purple-500/20">
                  {t(lang, "upgrade_current_plan")}
                </div>
              ) : currentPlan === "pro_plus" && billingCycle !== currentBillingInterval ? (
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
                      {isWeb ? t(lang, "web_subscribe_loading") : t(lang, "upgrade_processing")}
                    </span>
                  ) : lang === "ko"
                    ? `${billingCycle === "annual" ? "연간" : billingCycle === "lifetime" ? "평생" : "월간"}으로 전환`
                    : `Switch to ${billingCycle === "annual" ? "Annual" : billingCycle === "lifetime" ? "Lifetime" : "Monthly"}`}
                </button>
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
          <div className="rounded-2xl border border-border overflow-hidden overflow-x-auto">
            <div className="min-w-[420px]">
            {/* 헤더 */}
            <div className="grid grid-cols-[2fr_1fr_1fr_1fr] bg-muted/30 text-[11px] font-bold">
              <div className="p-3 text-muted-foreground">{lang === "ko" ? "기능" : "Feature"}</div>
              <div className={cn("p-3 text-center", currentPlan === "free" && "bg-green-500/5")}>
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold bg-muted text-muted-foreground">Free</span>
              </div>
              <div className={cn("p-3 text-center", currentPlan === "pro" && "bg-blue-500/5")}>
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold bg-gradient-to-r from-blue-500 to-cyan-400 text-white shadow-sm">Pro</span>
              </div>
              <div className={cn("p-3 text-center", currentPlan === "pro_plus" && "bg-purple-500/5")}>
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-sm">Pro+</span>
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
              ? "구독 취소 시 현재 결제 기간 만료까지 서비스 이용 가능 · 세금 별도"
              : "Cancel anytime · Service continues until current billing period ends · Excl. tax"}
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

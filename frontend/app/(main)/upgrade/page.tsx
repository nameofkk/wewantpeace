"use client";

import { useState } from "react";
import { Check, X, Zap, Shield, Star, ArrowLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import Link from "next/link";

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
    free: "고정 (1.0)",           pro: "1.0 ~ 4.0",               proplus: "0.5 ~ 4.0",
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

const PLANS = [
  {
    id: "free",     name: "Free",  icon: null,
    priceKRW: 0,
    gradient: "",
    border: "border-border",
    badge: null,
    taglineKo: "핵심 기능 무료",
    taglineEn: "Core features, free",
  },
  {
    id: "pro",      name: "Pro",   icon: Shield,
    priceKRW: 4900,
    gradient: "from-blue-600 to-primary",
    border: "border-primary",
    badge: { ko: "인기", en: "Popular" },
    taglineKo: "전문 분석가를 위한 도구",
    taglineEn: "Tools for serious analysts",
  },
  {
    id: "pro_plus", name: "Pro+",  icon: Star,
    priceKRW: 9900,
    gradient: "from-purple-600 to-pink-500",
    border: "border-purple-500",
    badge: { ko: "최고", en: "Best" },
    taglineKo: "API + 전체 기능",
    taglineEn: "Full features + API",
  },
] as const;

function FeatureValue({
  val, planId, lang,
}: { val: boolean | string; planId: string; lang: string }) {
  if (val === true) {
    const color = planId === "pro_plus" ? "text-purple-400" : planId === "pro" ? "text-primary" : "text-green-500";
    return <Check className={cn("h-4 w-4 mx-auto", color)} />;
  }
  if (val === false) return <X className="h-4 w-4 mx-auto text-muted-foreground/30" />;
  return (
    <span className={cn(
      "text-[11px] font-medium",
      planId === "pro_plus" ? "text-purple-400" : planId === "pro" ? "text-primary" : "text-muted-foreground"
    )}>
      {val}
    </span>
  );
}

export default function UpgradePage() {
  const { user } = useAuth();
  const lang = useAppStore((s) => s.lang);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<"pro" | "pro_plus">("pro");

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  async function handleSubscribe(planId: string) {
    if (planId === "free") return;
    if (!user) { window.location.href = "/login"; return; }
    setLoading(planId);
    setError(null);
    try {
      const token = await user.getIdToken();
      const res = await fetch(`${API_BASE}/subscriptions/toss/ready?plan=${planId}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(t(lang, "upgrade_payment_failed"));
      const data = await res.json();
      const { loadTossPayments } = await import("@tosspayments/payment-sdk");
      const tossKey = process.env.NEXT_PUBLIC_TOSS_CLIENT_KEY;
      if (!tossKey) {
        throw new Error(lang === "ko" ? "결제 시스템이 준비 중입니다. 잠시 후 다시 시도해주세요." : "Payment system is not configured. Please try again later.");
      }
      const toss = await loadTossPayments(tossKey);
      await toss.requestBillingAuth("카드", {
        customerKey: data.customer_key,
        successUrl: `${window.location.origin}/upgrade/success?plan=${planId}`,
        failUrl: `${window.location.origin}/upgrade/fail`,
      });
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || t(lang, "upgrade_payment_error"));
    } finally {
      setLoading(null);
    }
  }

  function formatPrice(krw: number): string {
    if (krw === 0) return lang === "ko" ? "무료" : "Free";
    const formatted = krw.toLocaleString("ko-KR");
    if (lang === "ko") return `₩${formatted}/월`;
    return `₩${formatted}/mo`;
  }

  return (
    <div className="min-h-screen bg-background">
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(20px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes glowPulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.3); }
          50%       { box-shadow: 0 0 0 8px rgba(59,130,246,0); }
        }
        @keyframes glowPulsePurple {
          0%, 100% { box-shadow: 0 0 0 0 rgba(168,85,247,0.3); }
          50%       { box-shadow: 0 0 0 8px rgba(168,85,247,0); }
        }
        .plan-card { animation: fadeSlideUp 0.4s ease both; }
        .plan-card:nth-child(1) { animation-delay: 0.05s; }
        .plan-card:nth-child(2) { animation-delay: 0.15s; }
        .plan-card:nth-child(3) { animation-delay: 0.25s; }
        .glow-pro     { animation: glowPulse 2.5s ease-in-out infinite; }
        .glow-proplus { animation: glowPulsePurple 2.5s ease-in-out infinite; }
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
        <div className="text-center mb-8" style={{ animation: "fadeSlideUp 0.3s ease both" }}>
          <h2 className="text-2xl font-bold">
            {lang === "ko" ? "당신에게 맞는 플랜" : "Choose Your Plan"}
          </h2>
          <p className="mt-1.5 text-sm text-muted-foreground">{t(lang, "upgrade_subtitle")}</p>
        </div>

        {error && (
          <div className="mb-6 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive text-center">
            {error}
          </div>
        )}

        {/* ── 플랜 카드 3개 ── */}
        <div className="space-y-4">
          {PLANS.map((plan) => {
            const isPro = plan.id === "pro";
            const isProPlus = plan.id === "pro_plus";
            const isHighlighted = highlighted === plan.id;
            const Icon = plan.icon;

            return (
              <div
                key={plan.id}
                className={cn(
                  "plan-card relative rounded-2xl border-2 bg-card p-5 cursor-pointer transition-all duration-200",
                  plan.border,
                  isPro && isHighlighted && "glow-pro",
                  isProPlus && isHighlighted && "glow-proplus",
                  !isHighlighted && "opacity-90 scale-[0.99]",
                  isHighlighted && "scale-[1.01]"
                )}
                onClick={() => { if (isPro) setHighlighted("pro"); if (isProPlus) setHighlighted("pro_plus"); }}
              >
                {/* 배지 */}
                {plan.badge && (
                  <span className={cn(
                    "absolute -top-3 left-1/2 -translate-x-1/2 rounded-full px-3 py-1 text-[11px] font-bold text-white",
                    isPro ? "bg-primary" : "bg-purple-500"
                  )}>
                    {lang === "ko" ? plan.badge.ko : plan.badge.en}
                  </span>
                )}

                <div className="flex items-start justify-between gap-3">
                  {/* 플랜 이름 + 설명 */}
                  <div className="flex items-center gap-2.5">
                    {Icon && (
                      <div className={cn(
                        "h-9 w-9 rounded-xl flex items-center justify-center text-white bg-gradient-to-br",
                        plan.gradient
                      )}>
                        <Icon className="h-4.5 w-4.5 h-[18px] w-[18px]" />
                      </div>
                    )}
                    {!Icon && (
                      <div className="h-9 w-9 rounded-xl bg-muted flex items-center justify-center">
                        <span className="text-base">🌐</span>
                      </div>
                    )}
                    <div>
                      <p className="text-base font-bold">{plan.name}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {lang === "ko" ? plan.taglineKo : plan.taglineEn}
                      </p>
                    </div>
                  </div>

                  {/* 가격 */}
                  <div className="text-right shrink-0">
                    <p className={cn(
                      "text-xl font-black",
                      isPro ? "text-primary" : isProPlus ? "text-purple-400" : "text-muted-foreground"
                    )}>
                      {plan.priceKRW === 0 ? (lang === "ko" ? "무료" : "Free") : `₩${plan.priceKRW.toLocaleString("ko-KR")}`}
                    </p>
                    {plan.priceKRW > 0 && (
                      <p className="text-[10px] text-muted-foreground">{lang === "ko" ? "/월" : "/mo"}</p>
                    )}
                  </div>
                </div>

                {/* 핵심 기능 요약 (프리 제외) */}
                {plan.id !== "free" && (
                  <div className={cn(
                    "mt-4 rounded-xl px-3 py-2.5 text-[11px] space-y-1",
                    isPro ? "bg-primary/8 border border-primary/20" : "bg-purple-500/8 border border-purple-500/20"
                  )}>
                    {plan.id === "pro" && (
                      <>
                        <p className="flex items-center gap-1.5"><Zap className="h-3 w-3 text-primary" />{lang === "ko" ? "🗺️ 실시간 글로벌 이슈 지도 잠금 해제" : "🗺️ Real-time global issue map"}</p>
                        <p className="flex items-center gap-1.5"><Zap className="h-3 w-3 text-primary" />{lang === "ko" ? "관심 국가 최대 5개 · 속보 알림" : "Up to 5 countries · Fast alerts"}</p>
                        <p className="flex items-center gap-1.5"><Zap className="h-3 w-3 text-primary" />{lang === "ko" ? "KScore 필터 · KScore/긴장도 30일 히스토리" : "KScore filter · 30-day KScore & tension history"}</p>
                      </>
                    )}
                    {plan.id === "pro_plus" && (
                      <>
                        <p className="flex items-center gap-1.5"><Star className="h-3 w-3 text-purple-400" />{lang === "ko" ? "Pro 모든 기능 포함 (지도 포함)" : "Everything in Pro (map included)"}</p>
                        <p className="flex items-center gap-1.5"><Star className="h-3 w-3 text-purple-400" />{lang === "ko" ? "무제한 국가 + KScore 0.5 ~ 4.0" : "Unlimited countries + KScore 0.5~4.0"}</p>
                        <p className="flex items-center gap-1.5"><Star className="h-3 w-3 text-purple-400" />{lang === "ko" ? "KScore/긴장도 90일 전체 히스토리" : "Full 90-day KScore & tension history"}</p>
                      </>
                    )}
                  </div>
                )}

                {/* 구독 버튼 */}
                <button
                  onClick={(e) => { e.stopPropagation(); handleSubscribe(plan.id); }}
                  disabled={plan.id === "free" || loading === plan.id}
                  className={cn(
                    "mt-4 w-full rounded-xl py-2.5 text-sm font-bold transition-all duration-150",
                    plan.id === "free"
                      ? "bg-secondary text-muted-foreground cursor-default"
                      : isPro
                        ? "bg-gradient-to-r from-blue-600 to-primary text-white hover:opacity-90 active:scale-[0.98]"
                        : "bg-gradient-to-r from-purple-600 to-pink-500 text-white hover:opacity-90 active:scale-[0.98]",
                    "disabled:opacity-50"
                  )}
                >
                  {loading === plan.id ? (
                    <span className="flex items-center justify-center gap-2">
                      <span className="h-3.5 w-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                      {t(lang, "upgrade_processing")}
                    </span>
                  ) : plan.id === "free"
                    ? t(lang, "upgrade_current_plan")
                    : t(lang, "upgrade_subscribe")}
                </button>
              </div>
            );
          })}
        </div>

        {/* ── 상세 비교 표 ── */}
        <div className="mt-10" style={{ animation: "fadeSlideUp 0.5s ease 0.3s both" }}>
          <h3 className="text-sm font-bold mb-4 text-center text-muted-foreground uppercase tracking-wider">
            {lang === "ko" ? "플랜 상세 비교" : "Detailed Comparison"}
          </h3>
          <div className="rounded-2xl border border-border overflow-hidden">
            {/* 헤더 */}
            <div className="grid grid-cols-4 bg-muted/30 text-[11px] font-bold">
              <div className="p-3 text-muted-foreground">{lang === "ko" ? "기능" : "Feature"}</div>
              <div className="p-3 text-center text-muted-foreground">Free</div>
              <div className="p-3 text-center text-primary">Pro</div>
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
        <div className="mt-8 text-center text-[11px] text-muted-foreground space-y-1">
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

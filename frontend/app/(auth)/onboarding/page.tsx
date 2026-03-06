"use client";

import { useRouter } from "next/navigation";
import Image from "next/image";
import { useState, useEffect, useMemo, useCallback } from "react";
import {
  Rss,
  Brain,
  Bell,
  BellOff,
  Lock,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  Search,
  Check,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { ALL_COUNTRIES, getCountryName, getFlag } from "@/lib/countries";
import { useMe } from "@/lib/api";
import { signInWithGoogle, signInWithApple, getIdToken } from "@/lib/auth";
import { trackEvent } from "@/lib/analytics";

type Step = 0 | 1 | 2;

// 주요 국기 (히어로 하단)
const HERO_FLAGS = ["UA", "IL", "TW", "MM", "SD"];

// 지역별 그룹핑
function groupByRegion(lang: string) {
  const groups: Record<string, typeof ALL_COUNTRIES> = {};
  for (const c of ALL_COUNTRIES) {
    const region = c.region;
    if (!groups[region]) groups[region] = [];
    groups[region].push(c);
  }
  return groups;
}

// Google SVG 아이콘
function GoogleIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
    </svg>
  );
}

// Apple SVG 아이콘
function AppleIcon() {
  return (
    <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
      <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z" />
    </svg>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const { lang, setMyCountries } = useAppStore();
  const { refetch: refetchMe } = useMe();

  const [step, setStep] = useState<Step>(0);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [pushStatus, setPushStatus] = useState<"default" | "granted" | "denied">("default");
  const [search, setSearch] = useState("");
  const [proBannerHighlight, setProBannerHighlight] = useState(false);
  const [loginLoading, setLoginLoading] = useState<"google" | "apple" | null>(null);
  const [isApple, setIsApple] = useState(false);

  // 이미 온보딩 완료면 /home
  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    if (done === "true") {
      router.replace("/home");
    }
  }, [router]);

  // Notification 권한 상태 확인
  useEffect(() => {
    if (typeof Notification !== "undefined") {
      setPushStatus(Notification.permission as "default" | "granted" | "denied");
    }
  }, []);

  // Apple 디바이스 감지
  useEffect(() => {
    const ua = navigator.userAgent;
    setIsApple(/iPad|iPhone|iPod|Macintosh/.test(ua));
  }, []);

  // 국가 검색 필터
  const regionGroups = useMemo(() => groupByRegion(lang), [lang]);
  const filteredGroups = useMemo(() => {
    if (!search.trim()) return regionGroups;
    const q = search.toLowerCase();
    const result: Record<string, typeof ALL_COUNTRIES> = {};
    for (const [region, countries] of Object.entries(regionGroups)) {
      const filtered = countries.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          getCountryName(c.code, "en").toLowerCase().includes(q) ||
          c.code.toLowerCase().includes(q)
      );
      if (filtered.length > 0) result[region] = filtered;
    }
    return result;
  }, [regionGroups, search, lang]);

  // --- 이벤트 트래킹 ---
  const trackSkip = useCallback(
    (reason: "close" | "back" | "later" | "error") => {
      trackEvent("onboarding_skip", { step, reason });
    },
    [step]
  );

  // --- 스텝 전환 ---
  function handleNext() {
    if (step === 0) {
      trackEvent("onboarding_hero_start");
      setStep(1);
    } else if (step === 1) {
      setMyCountries(selectedCountries);
      trackEvent("onboarding_countries_done", { count: selectedCountries.length });
      setStep(2);
    }
  }

  function handleBack() {
    if (step > 0) {
      setStep((s) => (s - 1) as Step);
    }
  }

  function handleSkip() {
    trackSkip("later");
    localStorage.setItem("onboarding_done", "true");
    router.push("/home");
  }

  function finishOnboarding() {
    localStorage.setItem("onboarding_done", "true");
    router.push("/home");
  }

  // --- 국가 선택/해제 ---
  function toggleCountry(code: string) {
    if (selectedCountries.includes(code)) {
      setSelectedCountries((prev) => prev.filter((c) => c !== code));
      trackEvent("watch_country_remove", { code, count_after: selectedCountries.length - 1 });
    } else {
      if (selectedCountries.length >= 2) {
        // 3번째 탭 시 배너 하이라이트
        setProBannerHighlight(true);
        return;
      }
      setSelectedCountries((prev) => [...prev, code]);
      trackEvent("watch_country_add", { code, count_after: selectedCountries.length + 1 });
    }
  }

  // --- 알림 권한 요청 ---
  async function requestPush() {
    trackEvent("push_permission_request");
    try {
      const result = await Notification.requestPermission();
      setPushStatus(result as "granted" | "denied");
      trackEvent("push_permission_result", { result });
    } catch {
      setPushStatus("denied");
      trackEvent("push_permission_result", { result: "error" });
    }
  }

  // --- 로그인 처리 ---
  async function handleOAuthLogin(provider: "google" | "apple") {
    setLoginLoading(provider);
    try {
      const user = provider === "google"
        ? await signInWithGoogle()
        : await signInWithApple();

      const token = await user.getIdToken();
      localStorage.setItem("firebase_token", token);

      // /me 호출하여 닉네임+약관 확인
      const meResult = await refetchMe();
      const me = meResult.data as { nickname: string | null; agreed_terms_at: string | null } | undefined;

      if (me?.nickname && me?.agreed_terms_at) {
        trackEvent("onboarding_login_complete", { provider });
        finishOnboarding();
      } else {
        // 닉네임/약관 미등록 → 등록 폼
        trackEvent("onboarding_login_need_register", { provider });
        localStorage.setItem("onboarding_done", "true");
        router.push("/login?tab=google-register");
      }
    } catch (err: any) {
      // redirect 에러는 정상 (React Native WebView)
      if (err?.message === "redirect") return;
      // 그 외 에러 → 무시, 홈으로
      trackEvent("onboarding_login_error", { provider, error: String(err) });
      finishOnboarding();
    } finally {
      setLoginLoading(null);
    }
  }

  // --- Next 버튼 활성화 ---
  const canNext = step === 0 || (step === 1 && selectedCountries.length >= 2);

  return (
    <div className="relative flex flex-col h-[100dvh] bg-background overflow-hidden">
      {/* 배경 그라디언트 */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% 0%, rgba(59,130,246,0.10) 0%, transparent 60%)",
        }}
      />

      {/* 헤더 */}
      <div className="relative z-10 flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          {step > 0 && (
            <button
              onClick={handleBack}
              className="p-1.5 rounded-lg hover:bg-muted/50 transition-colors"
            >
              <ChevronLeft className="h-5 w-5 text-muted-foreground" />
            </button>
          )}
          {step > 0 && (
            <span className="text-xs text-muted-foreground font-medium">
              {step}/2
            </span>
          )}
        </div>
        <button
          onClick={handleSkip}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1"
        >
          {t(lang, "ob_skip")}
        </button>
      </div>

      {/* 프로그레스 바 (Step 1, 2만) */}
      {step > 0 && (
        <div className="relative z-10 mx-4 h-1 rounded-full bg-muted/30 overflow-hidden">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
            style={{ width: `${(step / 2) * 100}%` }}
          />
        </div>
      )}

      {/* 메인 콘텐츠 */}
      <div className="relative z-10 flex-1 flex flex-col items-center overflow-hidden px-4 pt-4">
        <div className="w-full max-w-md flex-1 flex flex-col">

          {/* === Step 0: 히어로 === */}
          {step === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center animate-fadeIn">
              {/* 로고 + 타이틀 */}
              <div className="text-center mb-8">
                <div className="flex justify-center mb-4">
                  <Image
                    src="/logo-eye.png"
                    alt="WeWantPeace"
                    width={80}
                    height={35}
                    className="object-contain"
                    priority
                  />
                </div>
                <h1 className="text-lg font-bold text-foreground/80 mb-1">WeWantPeace</h1>
                <h2 className="text-xl font-bold whitespace-pre-line leading-snug">
                  {t(lang, "ob_hero_title")}
                </h2>
              </div>

              {/* Trust Signals */}
              <div className="w-full space-y-3 mb-8">
                {[
                  { icon: Rss, key: "ob_hero_signal_1" as const },
                  { icon: Brain, key: "ob_hero_signal_2" as const },
                  { icon: Bell, key: "ob_hero_signal_3" as const },
                ].map(({ icon: Icon, key }) => (
                  <div
                    key={key}
                    className="flex items-center gap-3 rounded-xl border border-border/30 bg-card/30 px-4 py-3"
                  >
                    <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Icon className="h-4.5 w-4.5 text-primary" />
                    </div>
                    <span className="text-sm font-medium text-foreground/80">
                      {t(lang, key)}
                    </span>
                  </div>
                ))}
              </div>

              {/* 모니터링 현황 + 국기 */}
              <div className="text-center">
                <p className="text-xs text-muted-foreground mb-2">
                  {t(lang, "ob_hero_monitoring")}
                </p>
                <div className="flex justify-center gap-1.5">
                  {HERO_FLAGS.map((code) => (
                    <span key={code} className="text-xl">{getFlag(code)}</span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* === Step 1: 국가 선택 + 알림 === */}
          {step === 1 && (
            <div className="flex-1 flex flex-col min-h-0 animate-fadeIn">
              {/* 국가 선택 헤더 */}
              <div className="text-center mb-3">
                <h2 className="text-xl font-bold mb-1">{t(lang, "ob_step_countries")}</h2>
                <p className="text-sm text-muted-foreground">{t(lang, "ob_countries_desc")}</p>
              </div>

              {/* 선택 카운트 + 검색 */}
              <div className="flex items-center gap-2 mb-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <input
                    type="text"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder={lang === "ko" ? "국가 검색..." : "Search country..."}
                    className="w-full pl-9 pr-3 py-2 text-sm rounded-xl border border-border/40 bg-card/40 focus:border-primary/50 focus:outline-none transition-colors"
                  />
                </div>
                <span
                  className={`text-xs font-semibold px-2.5 py-1.5 rounded-lg whitespace-nowrap ${
                    selectedCountries.length >= 2
                      ? "bg-primary/10 text-primary"
                      : "bg-muted/30 text-muted-foreground"
                  }`}
                >
                  {t(lang, "ob_select_n_countries", { n: selectedCountries.length })}
                </span>
              </div>

              {/* Pro 인라인 배너 (항상 표시) */}
              <div
                className={`mb-2 flex items-center gap-2 rounded-xl border px-3 py-2 transition-all duration-300 ${
                  proBannerHighlight
                    ? "border-amber-500/50 bg-amber-500/15 animate-pulse"
                    : "border-border/20 bg-muted/10"
                }`}
              >
                <Lock className={`h-3.5 w-3.5 flex-shrink-0 ${proBannerHighlight ? "text-amber-400" : "text-muted-foreground/60"}`} />
                <span className={`text-xs font-medium ${proBannerHighlight ? "text-amber-300" : "text-muted-foreground/60"}`}>
                  {t(lang, "ob_countries_plan_info")}
                </span>
              </div>

              {/* 최소 2개 안내 */}
              {selectedCountries.length < 2 && selectedCountries.length > 0 && (
                <p className="text-xs text-muted-foreground mb-2 text-center">
                  {t(lang, "ob_countries_min")}
                </p>
              )}

              {/* 국가 목록 (스크롤) */}
              <div className="flex-1 overflow-y-auto -mx-1 px-1 pb-2 space-y-4 scrollbar-thin">
                {Object.entries(filteredGroups).map(([region, countries]) => (
                  <div key={region}>
                    <div className="text-[11px] font-semibold text-muted-foreground/60 uppercase tracking-wider mb-1.5 px-1">
                      {lang === "en"
                        ? (
                            {
                              "유럽": "Europe",
                              "중동": "Middle East",
                              "동아시아": "East Asia",
                              "동남아": "Southeast Asia",
                              "남아시아": "South Asia",
                              "중앙아시아": "Central Asia",
                              "아프리카": "Africa",
                              "남미": "South America",
                              "중미": "Central America",
                              "북미": "North America",
                              "오세아니아": "Oceania",
                            } as Record<string, string>
                          )[region] ?? region
                        : region}
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {countries.map((c) => {
                        const selected = selectedCountries.includes(c.code);
                        return (
                          <button
                            key={c.code}
                            onClick={() => toggleCountry(c.code)}
                            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-all active:scale-95 ${
                              selected
                                ? "bg-primary/15 border border-primary/50 text-foreground"
                                : "bg-card/40 border border-border/30 text-muted-foreground hover:border-border"
                            }`}
                          >
                            <span>{getFlag(c.code)}</span>
                            <span>{getCountryName(c.code, lang)}</span>
                            {selected && <CheckCircle2 className="h-3 w-3 text-primary" />}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              {/* 알림 섹션 (구분선 후) */}
              <div className="border-t border-border/30 pt-3 mt-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bell className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold">
                      {lang === "ko" ? "알림" : "Notifications"}
                    </span>
                  </div>
                  {pushStatus === "default" && (
                    <button
                      onClick={() => {
                        trackEvent("push_pre_permission_view");
                        requestPush();
                      }}
                      className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 transition-colors active:scale-95"
                    >
                      <Bell className="h-3.5 w-3.5" />
                      {t(lang, "ob_alerts_allow")}
                    </button>
                  )}
                  {pushStatus === "granted" && (
                    <div className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {t(lang, "ob_alerts_granted")}
                    </div>
                  )}
                  {pushStatus === "denied" && (
                    <div className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-red-400 bg-red-500/10 border border-red-500/30">
                      <BellOff className="h-3.5 w-3.5" />
                      {t(lang, "ob_alerts_denied")}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* === Step 2: 로그인 유도 === */}
          {step === 2 && (
            <div className="flex-1 flex flex-col items-center justify-center animate-fadeIn">
              {/* 잠금 아이콘 */}
              <div className="mx-auto mb-6 w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
                <Lock className="h-8 w-8 text-primary" />
              </div>

              {/* 메인 카피 */}
              <h2 className="text-xl font-bold text-center whitespace-pre-line leading-snug mb-6">
                {t(lang, "ob_login_title")}
              </h2>

              {/* 혜택 리스트 */}
              <div className="w-full space-y-3 mb-8">
                {[
                  { key: "ob_login_sync" as const },
                  { key: "ob_login_community" as const },
                  { key: "ob_login_pro" as const },
                ].map(({ key }) => (
                  <div key={key} className="flex items-center gap-3">
                    <div className="w-6 h-6 rounded-full bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                    </div>
                    <span className="text-sm text-foreground/80">{t(lang, key)}</span>
                  </div>
                ))}
              </div>

              {/* OAuth 버튼들 */}
              <div className="w-full space-y-3">
                {/* Google */}
                <button
                  onClick={() => handleOAuthLogin("google")}
                  disabled={loginLoading !== null}
                  className="w-full flex items-center justify-center gap-3 rounded-xl border border-border bg-background py-3 text-sm font-medium hover:bg-secondary transition-colors disabled:opacity-50"
                >
                  {loginLoading === "google" ? (
                    <div className="h-5 w-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <GoogleIcon />
                  )}
                  {t(lang, "ob_login_google")}
                </button>

                {/* Apple (iOS/Mac만) */}
                {isApple && (
                  <button
                    onClick={() => handleOAuthLogin("apple")}
                    disabled={loginLoading !== null}
                    className="w-full flex items-center justify-center gap-3 rounded-xl border border-border bg-foreground text-background py-3 text-sm font-medium hover:opacity-90 transition-colors disabled:opacity-50"
                  >
                    {loginLoading === "apple" ? (
                      <div className="h-5 w-5 border-2 border-background border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <AppleIcon />
                    )}
                    {t(lang, "ob_login_apple")}
                  </button>
                )}
              </div>

              {/* 나중에 할게요 */}
              <div className="mt-6 text-center">
                <button
                  onClick={() => {
                    trackEvent("onboarding_login_skip");
                    finishOnboarding();
                  }}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
                >
                  {t(lang, "ob_login_later")}
                </button>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  ({t(lang, "ob_login_later_sub")})
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 하단 버튼 (Step 0, 1만) */}
      {step < 2 && (
        <div className="relative z-10 px-4 pb-6 pt-3">
          <div className="w-full max-w-md mx-auto">
            <button
              onClick={handleNext}
              disabled={!canNext}
              className={`w-full flex items-center justify-center gap-2 rounded-2xl py-3.5 text-[15px] font-bold transition-all active:scale-95 ${
                canNext
                  ? "text-primary-foreground shadow-lg"
                  : "bg-muted/30 text-muted-foreground cursor-not-allowed"
              }`}
              style={
                canNext
                  ? {
                      background:
                        "linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary)/0.85) 100%)",
                      boxShadow: "0 4px 20px rgba(99,102,241,0.3)",
                    }
                  : undefined
              }
            >
              {step === 0 ? t(lang, "ob_hero_cta") : t(lang, "ob_next")}
              <ChevronRight className="h-4.5 w-4.5" />
            </button>
          </div>
        </div>
      )}

      <style jsx global>{`
        @keyframes fadeIn {
          from {
            opacity: 0;
            transform: translateY(8px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .animate-fadeIn {
          animation: fadeIn 0.35s ease-out both;
        }
        .scrollbar-thin::-webkit-scrollbar {
          width: 4px;
        }
        .scrollbar-thin::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 2px;
        }
        .scrollbar-thin::-webkit-scrollbar-track {
          background: transparent;
        }
      `}</style>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import Image from "next/image";
import { useState, useEffect, useMemo, useCallback } from "react";
import {
  Rss,
  Satellite,
  Bell,
  BellOff,
  Lock,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  Search,
  Check,
  Activity,
  Shield,
  Globe,
  BarChart3,
  TrendingUp,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { ALL_COUNTRIES, getCountryName, getFlag } from "@/lib/countries";
import { useMe, API_BASE } from "@/lib/api";
import { signInWithGoogle, signInWithApple, signInWithToss, getIdToken } from "@/lib/auth";
import { isTossMiniApp } from "@/lib/platform";
import { isGoogleOAuthBlocked, openInExternalBrowser } from "@/lib/browser-detect";
import { trackEvent } from "@/lib/analytics";

type Step = 0 | 1 | 2;

// 수집처 목록 (마퀴 스크롤)
const DATA_SOURCES = [
  "Reuters", "Associated Press", "ACLED", "GDELT", "NASA FIRMS",
  "UCDP", "OCHA ReliefWeb", "IODA", "Al Jazeera", "BBC",
];

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

const REGION_EN: Record<string, string> = {
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
};

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

// 실시간 스캔 카운터 (히어로)
function useScanCounter() {
  const [count, setCount] = useState(1247);
  useEffect(() => {
    const interval = setInterval(() => {
      setCount((c) => c + Math.floor(Math.random() * 3) + 1);
    }, 2000 + Math.random() * 1500);
    return () => clearInterval(interval);
  }, []);
  return count;
}

export default function OnboardingPage() {
  const router = useRouter();
  const { lang, setMyCountries, setHomeCountry } = useAppStore();
  const { refetch: refetchMe } = useMe();

  const [step, setStep] = useState<Step>(0);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [homeCountryLocal, setHomeCountryLocal] = useState("KR");
  const [pushStatus, setPushStatus] = useState<"default" | "granted" | "denied">("default");
  const [search, setSearch] = useState("");
  const [proBannerHighlight, setProBannerHighlight] = useState(false);
  const [loginLoading, setLoginLoading] = useState<"google" | "apple" | "toss" | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [expandedRegions, setExpandedRegions] = useState<Set<string>>(new Set());
  const [marketingConsent, setMarketingConsent] = useState(false);

  const scanCount = useScanCounter();

  // 이미 온보딩 완료면 원래 페이지로 복원 (deep link 지원)
  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    if (done === "true") {
      const returnUrl = sessionStorage.getItem("wwp_return_url");
      sessionStorage.removeItem("wwp_return_url");
      router.replace(returnUrl || "/home");
    }
  }, [router]);

  // Notification 권한 상태 확인
  useEffect(() => {
    if (typeof Notification !== "undefined") {
      setPushStatus(Notification.permission as "default" | "granted" | "denied");
    }
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

  // 검색 중이면 모든 지역 펼침
  const isSearching = search.trim().length > 0;

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
      if (selectedCountries.length < 2) {
        setCountryWarning(true);
        setTimeout(() => setCountryWarning(false), 3000);
        return;
      }
      setHomeCountry(homeCountryLocal);
      setMyCountries(selectedCountries);
      trackEvent("onboarding_countries_done", { count: selectedCountries.length, home: homeCountryLocal });
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
    localStorage.setItem("wwp_welcome_seen", String(Date.now()));
    const returnUrl = sessionStorage.getItem("wwp_return_url");
    sessionStorage.removeItem("wwp_return_url");
    router.push(returnUrl || "/home?tour=1");
  }

  async function finishOnboarding() {
    trackEvent("onboarding_complete", { countries: selectedCountries.length, home: homeCountryLocal });
    try {
      const token = await getIdToken();
      if (token) {
        // 기준국가 동기화
        await fetch(`${API_BASE}/me/preferences`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ home_country: homeCountryLocal }),
        });
        // 마케팅 수신 동의 시 PATCH /me
        if (marketingConsent) {
          await fetch(`${API_BASE}/me`, {
            method: "PATCH",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ marketing_agreed_at: new Date().toISOString() }),
          });
        }
      }
    } catch {
      // 실패해도 온보딩은 계속 진행
    }
    localStorage.setItem("onboarding_done", "true");
    localStorage.setItem("wwp_welcome_seen", String(Date.now()));
    const returnUrl = sessionStorage.getItem("wwp_return_url");
    sessionStorage.removeItem("wwp_return_url");
    router.push(returnUrl || "/home?tour=1");
  }

  // --- 국가 선택/해제 ---
  function toggleCountry(code: string) {
    if (selectedCountries.includes(code)) {
      setSelectedCountries((prev) => prev.filter((c) => c !== code));
      trackEvent("watch_country_remove", { code, count_after: selectedCountries.length - 1 });
    } else {
      if (selectedCountries.length >= 2) {
        setProBannerHighlight(true);
        return;
      }
      setSelectedCountries((prev) => [...prev, code]);
      trackEvent("watch_country_add", { code, count_after: selectedCountries.length + 1 });
    }
  }

  // --- 지역 접기/펴기 ---
  function toggleRegion(region: string) {
    setExpandedRegions((prev) => {
      const next = new Set(prev);
      if (next.has(region)) next.delete(region);
      else next.add(region);
      return next;
    });
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

  // --- 인앱브라우저 감지 ---
  const [inAppBlocked, setInAppBlocked] = useState(false);

  // --- 로그인 처리 ---
  async function handleOAuthLogin(provider: "google" | "apple") {
    if (isGoogleOAuthBlocked()) {
      setInAppBlocked(true);
      setLoginError(
        lang === "en"
          ? "Google/Apple login is not supported in this browser. Please open in Chrome or Safari."
          : "이 브라우저에서는 Google/Apple 로그인이 지원되지 않습니다.\nChrome 또는 Safari에서 열어주세요."
      );
      return;
    }
    setLoginLoading(provider);
    setLoginError(null);
    try {
      const user = provider === "google"
        ? await signInWithGoogle()
        : await signInWithApple();

      const meResult = await refetchMe();
      const me = meResult.data as { nickname: string | null; agreed_terms_at: string | null } | undefined;

      if (me?.nickname && me?.agreed_terms_at) {
        trackEvent("auth_success", { provider, source: "onboarding" });
        trackEvent("onboarding_login_complete", { provider });
        finishOnboarding();
      } else {
        trackEvent("auth_success", { provider, source: "onboarding" });
        trackEvent("onboarding_login_need_register", { provider });
        localStorage.setItem("onboarding_done", "true");
        router.push("/login?tab=google-register");
      }
    } catch (err: any) {
      if (err?.message === "redirect") return;
      trackEvent("onboarding_login_error", { provider, error: String(err) });
      setLoginError(lang === "en" ? "Login failed. Please try again." : "로그인에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setLoginLoading(null);
    }
  }

  // --- Toss 로그인 처리 ---
  async function handleTossLogin() {
    setLoginLoading("toss");
    setLoginError(null);
    try {
      const { user, isNewUser } = await signInWithToss();
      if (!user) throw new Error("Toss login failed");

      if (!isNewUser) {
        const meResult = await refetchMe();
        const me = meResult.data as { nickname: string | null; agreed_terms_at: string | null } | undefined;
        if (me?.nickname && me?.agreed_terms_at) {
          trackEvent("auth_success", { provider: "toss", source: "onboarding" });
          trackEvent("onboarding_login_complete", { provider: "toss" });
          finishOnboarding();
          return;
        }
      }
      trackEvent("auth_success", { provider: "toss", source: "onboarding" });
      trackEvent("onboarding_login_need_register", { provider: "toss" });
      localStorage.setItem("onboarding_done", "true");
      router.push("/login?tab=google-register");
    } catch (err: any) {
      trackEvent("onboarding_login_error", { provider: "toss", error: String(err) });
      setLoginError(lang === "en" ? "Login failed. Please try again." : "로그인에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setLoginLoading(null);
    }
  }

  // --- 관심 국가 미선택 경고 ---
  const [countryWarning, setCountryWarning] = useState(false);

  // --- Next 버튼 활성화 (항상 활성) ---
  const canNext = step === 0 || step === 1;

  return (
    <div className="relative flex flex-col h-[100dvh] bg-background overflow-hidden">
      {/* 배경: dotted 세계지도 + 이슈 핑 애니메이션 */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* 지도 SVG */}
        <div
          className="absolute inset-0 opacity-60"
          style={{
            backgroundImage: "url(/dotted-world-map.svg)",
            backgroundSize: "140% auto",
            backgroundPosition: "center 40%",
            backgroundRepeat: "no-repeat",
          }}
        />
        {/* 이슈 발생 핑 애니메이션 */}
        <span className="ob-ping" style={{ top: "28%", left: "52%" }} />
        <span className="ob-ping ob-ping--2" style={{ top: "35%", left: "72%" }} />
        <span className="ob-ping ob-ping--3" style={{ top: "42%", left: "58%" }} />
        <span className="ob-ping ob-ping--4" style={{ top: "55%", left: "45%" }} />
        <span className="ob-ping ob-ping--5" style={{ top: "30%", left: "30%" }} />
        <span className="ob-ping ob-ping--6" style={{ top: "48%", left: "80%" }} />
        {/* 어두운 오버레이 */}
        <div
          className="absolute inset-0"
          style={{
            background: "radial-gradient(ellipse 80% 60% at 50% 40%, rgba(15,23,42,0.5) 0%, rgba(15,23,42,0.85) 70%, rgba(15,23,42,0.95) 100%)",
          }}
        />
      </div>

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
      <div className="relative z-10 flex-1 flex flex-col items-center px-4 pt-4 min-h-0">
        <div className="w-full max-w-md flex-1 flex flex-col min-h-0">

          {/* === Step 0: 히어로 === */}
          {step === 0 && (
            <div className="flex-1 overflow-y-auto animate-fadeIn">
            <div className="flex flex-col items-center min-h-full justify-center py-2">
              {/* 로고 + 레이더 */}
              <div className="relative flex items-center justify-center mb-6">
                {/* 레이더 파동 */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="ob-radar ob-radar--1" />
                  <span className="ob-radar ob-radar--2" />
                  <span className="ob-radar ob-radar--3" />
                </div>
                <div className="relative z-10">
                  <Image
                    src="/logo-eye.png"
                    alt="WeWantPeace"
                    width={100}
                    height={44}
                    className="object-contain"
                    priority
                  />
                </div>
              </div>

              <h1 className="text-lg font-bold tracking-tight mb-1">WeWantPeace</h1>
              <h2 className="text-xl font-bold whitespace-pre-line leading-snug text-center mb-6">
                {t(lang, "ob_hero_title")}
              </h2>

              {/* 실시간 스캔 인디케이터 */}
              <div className="flex items-center gap-2 mb-6 px-4 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                <span className="ob-live-dot" />
                <span className="text-xs font-semibold text-emerald-400">
                  {lang === "ko" ? "실시간 스캔 중" : "Live scanning"}
                </span>
                <span className="text-xs font-mono text-emerald-400/70 tabular-nums">
                  {scanCount.toLocaleString()}
                </span>
                <span className="text-xs text-emerald-400/50">
                  {lang === "ko" ? "건" : "events"}
                </span>
              </div>

              {/* Trust Signals */}
              <div className="w-full space-y-2.5 mb-6">
                {[
                  { icon: Rss, key: "ob_hero_signal_1" as const, delay: "0s" },
                  { icon: BarChart3, key: "ob_hero_signal_2" as const, delay: "0.1s" },
                  { icon: TrendingUp, key: "ob_hero_impact" as const, delay: "0.2s" },
                  { icon: Satellite, key: "ob_hero_signal_3_v2" as const, delay: "0.3s" },
                  { icon: Bell, key: "ob_hero_signal_4" as const, delay: "0.4s" },
                ].map(({ icon: Icon, key, delay }) => (
                  <div
                    key={key}
                    className="flex items-center gap-3 rounded-xl border border-border/30 bg-card/30 px-4 py-3 ob-slide-in"
                    style={{ animationDelay: delay }}
                  >
                    <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <span className="text-sm font-medium text-foreground/80">
                      {t(lang, key)}
                    </span>
                  </div>
                ))}
              </div>

              {/* 하단 신뢰 지표 */}
              <div className="w-full flex items-center justify-between px-2 mb-2">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5 text-muted-foreground/60">
                    <Globe className="h-3.5 w-3.5" />
                    <span className="text-[11px] font-medium">
                      {t(lang, "ob_hero_monitoring")}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1.5 text-muted-foreground/60">
                  <Shield className="h-3.5 w-3.5" />
                  <span className="text-[11px] font-medium">
                    {lang === "ko" ? "SSL 암호화" : "SSL Encrypted"}
                  </span>
                </div>
              </div>

              {/* 수집처 마퀴 */}
              <div className="w-full overflow-hidden relative">
                <div className="pointer-events-none absolute inset-y-0 left-0 w-8 z-10 bg-gradient-to-r from-background to-transparent" />
                <div className="pointer-events-none absolute inset-y-0 right-0 w-8 z-10 bg-gradient-to-l from-background to-transparent" />
                <div className="ob-marquee flex gap-6 whitespace-nowrap">
                  {[...DATA_SOURCES, ...DATA_SOURCES].map((src, i) => (
                    <span key={`${src}-${i}`} className="text-[11px] font-medium text-muted-foreground/50 flex items-center gap-1.5">
                      <span className="h-1 w-1 rounded-full bg-primary/30" />
                      {src}
                    </span>
                  ))}
                </div>
              </div>
            </div>
            </div>
          )}

          {/* === Step 1: 국가 선택 + 알림 === */}
          {step === 1 && (
            <div className="flex-1 flex flex-col min-h-0 animate-fadeIn">
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

              {/* Pro 인라인 배너 */}
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

              {/* 국가 목록 (아코디언) */}
              <div className="flex-1 overflow-y-auto -mx-1 px-1 pb-2 space-y-1 scrollbar-thin">
                {Object.entries(filteredGroups).map(([region, countries]) => {
                  const isOpen = isSearching || expandedRegions.has(region);
                  const selectedInRegion = countries.filter((c) =>
                    selectedCountries.includes(c.code)
                  ).length;
                  const regionLabel = lang === "en" ? (REGION_EN[region] ?? region) : region;

                  return (
                    <div key={region} className="rounded-xl border border-border/20 overflow-hidden">
                      {/* 지역 헤더 (탭하여 펼치기/접기) */}
                      <button
                        onClick={() => toggleRegion(region)}
                        className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-muted/20 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-muted-foreground/80">
                            {regionLabel}
                          </span>
                          <span className="text-[10px] text-muted-foreground/50">
                            {countries.length}
                          </span>
                          {selectedInRegion > 0 && (
                            <span className="text-[10px] font-bold text-primary bg-primary/10 px-1.5 py-0.5 rounded-full">
                              {selectedInRegion}
                            </span>
                          )}
                        </div>
                        <ChevronDown
                          className={`h-3.5 w-3.5 text-muted-foreground/50 transition-transform duration-200 ${
                            isOpen ? "rotate-180" : ""
                          }`}
                        />
                      </button>

                      {/* 국가 칩들 */}
                      {isOpen && (
                        <div className="flex flex-wrap gap-1.5 px-3 pb-3 animate-fadeIn">
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
                      )}
                    </div>
                  );
                })}
              </div>

              {/* 알림 섹션 */}
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

              {/* 마케팅 수신 동의 */}
              <div className="border-t border-border/30 pt-3 mt-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Rss className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold">
                      {t(lang, "marketing_consent_label")}
                    </span>
                  </div>
                  <button
                    onClick={() => setMarketingConsent(!marketingConsent)}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition-colors active:scale-95 ${
                      marketingConsent
                        ? "text-emerald-400 bg-emerald-500/10 border border-emerald-500/30"
                        : "bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20"
                    }`}
                  >
                    {marketingConsent ? (
                      <><CheckCircle2 className="h-3.5 w-3.5" />{lang === "ko" ? "동의함" : "Agreed"}</>
                    ) : (
                      <>{lang === "ko" ? "동의하기" : "Agree"}</>
                    )}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* === Step 2: 로그인 유도 === */}
          {step === 2 && (
            <div className="flex-1 overflow-y-auto animate-fadeIn">
            <div className="flex flex-col items-center min-h-full justify-center py-2">
              <div className="mx-auto mb-6 w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
                <Lock className="h-8 w-8 text-primary" />
              </div>

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

              {/* 로그인 에러 메시지 */}
              {loginError && (
                <div className="w-full rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-sm text-red-400 text-center whitespace-pre-line">
                  {loginError}
                </div>
              )}

              {/* 인앱브라우저 외부 열기 버튼 */}
              {inAppBlocked && (
                <button
                  onClick={openInExternalBrowser}
                  className="w-full flex items-center justify-center gap-2 rounded-xl border border-primary/50 bg-primary/10 py-3 text-sm font-bold text-primary hover:bg-primary/20 transition-colors"
                >
                  <Globe className="h-4 w-4" />
                  {lang === "en" ? "Open in browser" : "브라우저에서 열기"}
                </button>
              )}

              {/* OAuth 버튼들 */}
              <div className="w-full space-y-3">
                {isTossMiniApp() ? (
                  /* Toss 미니앱: Toss 로그인만 */
                  <button
                    onClick={handleTossLogin}
                    disabled={loginLoading !== null}
                    className="w-full flex items-center justify-center gap-3 rounded-xl py-3 text-sm font-bold text-white transition-colors disabled:opacity-50"
                    style={{ backgroundColor: "#0064FF" }}
                  >
                    {loginLoading === "toss" ? (
                      <div className="h-5 w-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1.5 14.5v-9l7 4.5-7 4.5z" fill="white"/>
                      </svg>
                    )}
                    {t(lang, "login_toss")}
                  </button>
                ) : (
                  /* 일반: Google + Apple */
                  <>
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
                  </>
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
            </div>
          )}
        </div>
      </div>

      {/* 관심 국가 미선택 경고 */}
      {countryWarning && (
        <div className="relative z-10 mx-4 mb-1 animate-fadeIn">
          <div className="w-full max-w-md mx-auto text-center py-2 px-3 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-300 text-xs font-semibold">
            {lang === "ko" ? "최소 2개 이상 관심 국가를 선택해주세요" : "Please select at least 2 countries"}
          </div>
        </div>
      )}

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
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.35s ease-out both;
        }

        /* 레이더 파동 */
        @keyframes ob-radar-pulse {
          0% { transform: scale(0.3); opacity: 0.6; }
          100% { transform: scale(2.5); opacity: 0; }
        }
        .ob-radar {
          position: absolute;
          width: 80px;
          height: 80px;
          border-radius: 50%;
          border: 1.5px solid rgba(99,102,241,0.3);
          animation: ob-radar-pulse 3s ease-out infinite;
        }
        .ob-radar--2 { animation-delay: 1s; }
        .ob-radar--3 { animation-delay: 2s; }

        /* 라이브 닷 */
        @keyframes ob-live-blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
        .ob-live-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #10B981;
          animation: ob-live-blink 1.5s ease-in-out infinite;
          flex-shrink: 0;
        }

        /* 슬라이드 인 */
        @keyframes ob-slide-in {
          from { opacity: 0; transform: translateX(-12px); }
          to { opacity: 1; transform: translateX(0); }
        }
        .ob-slide-in {
          animation: ob-slide-in 0.4s ease-out both;
        }

        /* 수집처 마퀴 */
        @keyframes ob-marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .ob-marquee {
          animation: ob-marquee 25s linear infinite;
        }

        /* 이슈 발생 핑 */
        @keyframes ob-issue-ping {
          0% { transform: scale(0); opacity: 0.9; }
          50% { transform: scale(1); opacity: 0.6; }
          100% { transform: scale(2.5); opacity: 0; }
        }
        .ob-ping {
          position: absolute;
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: rgba(239, 68, 68, 0.7);
          box-shadow: 0 0 6px 2px rgba(239, 68, 68, 0.4);
          animation: ob-issue-ping 3s ease-out infinite;
        }
        .ob-ping::after {
          content: "";
          position: absolute;
          inset: -2px;
          border-radius: 50%;
          border: 1px solid rgba(239, 68, 68, 0.5);
          animation: ob-issue-ping 3s ease-out infinite;
          animation-delay: 0.3s;
        }
        .ob-ping--2 { animation-delay: 0.8s; background: rgba(249, 115, 22, 0.7); box-shadow: 0 0 6px 2px rgba(249, 115, 22, 0.4); }
        .ob-ping--2::after { border-color: rgba(249, 115, 22, 0.5); animation-delay: 1.1s; }
        .ob-ping--3 { animation-delay: 1.6s; }
        .ob-ping--3::after { animation-delay: 1.9s; }
        .ob-ping--4 { animation-delay: 2.2s; background: rgba(249, 115, 22, 0.7); box-shadow: 0 0 6px 2px rgba(249, 115, 22, 0.4); }
        .ob-ping--4::after { border-color: rgba(249, 115, 22, 0.5); animation-delay: 2.5s; }
        .ob-ping--5 { animation-delay: 0.4s; background: rgba(234, 179, 8, 0.6); box-shadow: 0 0 6px 2px rgba(234, 179, 8, 0.3); }
        .ob-ping--5::after { border-color: rgba(234, 179, 8, 0.4); animation-delay: 0.7s; }
        .ob-ping--6 { animation-delay: 1.2s; }
        .ob-ping--6::after { animation-delay: 1.5s; }

        .scrollbar-thin::-webkit-scrollbar { width: 4px; }
        .scrollbar-thin::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.1);
          border-radius: 2px;
        }
        .scrollbar-thin::-webkit-scrollbar-track { background: transparent; }
      `}</style>
    </div>
  );
}

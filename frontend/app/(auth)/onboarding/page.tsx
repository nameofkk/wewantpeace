"use client";

import { useRouter } from "next/navigation";
import Image from "next/image";
import { useState, useEffect, useMemo, useCallback } from "react";
import {
  Plane,
  TrendingUp,
  Briefcase,
  Globe,
  Bell,
  BellOff,
  Shield,
  Lock,
  Clock,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
  X,
  Search,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { ALL_COUNTRIES, getCountryName, getFlag } from "@/lib/countries";
import { useMe, usePatchPreferences, useTensionMine } from "@/lib/api";
import { trackEvent } from "@/lib/analytics";

type Intent = "travel" | "invest" | "expat" | "general";
type Step = 1 | 2 | 3 | 4 | 5;

const INTENTS: { key: Intent; icon: typeof Plane; color: string }[] = [
  { key: "travel", icon: Plane, color: "text-sky-400" },
  { key: "invest", icon: TrendingUp, color: "text-emerald-400" },
  { key: "expat", icon: Briefcase, color: "text-amber-400" },
  { key: "general", icon: Globe, color: "text-violet-400" },
];

const INTENT_I18N: Record<Intent, string> = {
  travel: "ob_intent_travel",
  invest: "ob_intent_invest",
  expat: "ob_intent_expat",
  general: "ob_intent_general",
};

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

// 긴장도 등급 라벨
function tensionGrade(level: number, lang: string): string {
  const ko = ["안정", "주의", "경계", "심각", "극심"];
  const en = ["Stable", "Caution", "Alert", "Severe", "Extreme"];
  return lang === "ko" ? ko[level] ?? "—" : en[level] ?? "—";
}

function tensionColor(level: number): string {
  const colors = ["text-emerald-400", "text-yellow-400", "text-orange-400", "text-red-400", "text-red-600"];
  return colors[level] ?? "text-muted-foreground";
}

export default function OnboardingPage() {
  const router = useRouter();
  const { lang, addMyCountry, removeMyCountry, myCountries, setMyCountries, userPlan } = useAppStore();
  const { data: me } = useMe();
  const patchPrefs = usePatchPreferences();

  const [step, setStep] = useState<Step>(1);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [selectedCountries, setSelectedCountries] = useState<string[]>([]);
  const [pushStatus, setPushStatus] = useState<"default" | "granted" | "denied">("default");
  const [showProTeaser, setShowProTeaser] = useState(false);
  const [search, setSearch] = useState("");

  // 이미 온보딩 완료 + 비로그인이면 기존 스플래시로 리다이렉트
  useEffect(() => {
    const done = localStorage.getItem("onboarding_done");
    if (done === "true") {
      router.replace("/home");
    }
  }, [router]);

  // 이전 Notification 권한 상태 확인
  useEffect(() => {
    if (typeof Notification !== "undefined") {
      setPushStatus(Notification.permission as "default" | "granted" | "denied");
    }
  }, []);

  // Step5 Summary: 선택한 국가의 긴장도 조회
  const { data: tensionData } = useTensionMine(
    step === 5 && selectedCountries.length > 0 ? selectedCountries : null
  );
  const tensions = tensionData as { country_code: string; raw_score: number; tension_level: number }[] | undefined;

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

  // --- 이벤트 트래킹 헬퍼 ---
  const trackSkip = useCallback(
    (reason: "close" | "back" | "later" | "error") => {
      trackEvent("onboarding_skip", { step, reason });
    },
    [step]
  );

  // --- 스텝 전환 ---
  function handleNext() {
    if (step === 1 && intent) {
      trackEvent("onboarding_intent_select", { intent });
      // API에 intent 저장
      patchPrefs.mutate({ topics: [intent] } as any);
      setStep(2);
    } else if (step === 2) {
      // 선택한 국가를 store에 반영
      setMyCountries(selectedCountries);
      setStep(3);
    } else if (step === 3) {
      setStep(4);
    } else if (step === 4) {
      setStep(5);
    }
  }

  function handleBack() {
    if (step > 1) {
      setStep((s) => (s - 1) as Step);
    }
  }

  function handleSkip() {
    trackSkip("later");
    localStorage.setItem("onboarding_done", "true");
    router.push("/home");
  }

  function handleComplete() {
    trackEvent("onboarding_complete", {
      intent: intent ?? "none",
      count: selectedCountries.length,
      push_status: pushStatus,
    });
    localStorage.setItem("onboarding_done", "true");
    router.push("/home");
  }

  // --- 국가 선택/해제 ---
  function toggleCountry(code: string) {
    if (selectedCountries.includes(code)) {
      setSelectedCountries((prev) => prev.filter((c) => c !== code));
      trackEvent("watch_country_remove", { code, count_after: selectedCountries.length - 1 });
    } else {
      // 3번째 국가 탭 시 인라인 티저
      if (selectedCountries.length >= 2) {
        setShowProTeaser(true);
        setTimeout(() => setShowProTeaser(false), 3000);
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

  // --- Next 버튼 활성화 ---
  const canNext =
    (step === 1 && intent !== null) ||
    (step === 2 && selectedCountries.length >= 2) ||
    step === 3 ||
    step === 4;

  // --- 프로그레스 바 ---
  const progress = (step / 5) * 100;

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

      {/* 헤더: 프로그레스 + 건너뛰기 */}
      <div className="relative z-10 flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          {step > 1 && (
            <button
              onClick={handleBack}
              className="p-1.5 rounded-lg hover:bg-muted/50 transition-colors"
            >
              <ChevronLeft className="h-5 w-5 text-muted-foreground" />
            </button>
          )}
          <span className="text-xs text-muted-foreground font-medium">{step}/5</span>
        </div>
        <button
          onClick={handleSkip}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1"
        >
          {t(lang, "ob_skip")}
        </button>
      </div>

      {/* 프로그레스 바 */}
      <div className="relative z-10 mx-4 h-1 rounded-full bg-muted/30 overflow-hidden">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* 메인 콘텐츠 */}
      <div className="relative z-10 flex-1 flex flex-col items-center overflow-hidden px-4 pt-4">
        <div className="w-full max-w-md flex-1 flex flex-col">
          {/* === Step 1: Intent === */}
          {step === 1 && (
            <div className="flex-1 flex flex-col animate-fadeIn">
              <div className="text-center mb-6">
                <div className="flex justify-center mb-3">
                  <Image
                    src="/logo-eye.png"
                    alt="WeWantPeace"
                    width={80}
                    height={35}
                    className="object-contain"
                    priority
                  />
                </div>
                <h2 className="text-xl font-bold mb-1">{t(lang, "ob_step_intent")}</h2>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {INTENTS.map(({ key, icon: Icon, color }) => (
                  <button
                    key={key}
                    onClick={() => setIntent(key)}
                    className={`flex flex-col items-center gap-2.5 rounded-2xl border-2 p-5 transition-all active:scale-95 ${
                      intent === key
                        ? "border-primary bg-primary/10 shadow-lg shadow-primary/10"
                        : "border-border/40 bg-card/40 hover:border-border"
                    }`}
                  >
                    <Icon
                      className={`h-8 w-8 ${intent === key ? color : "text-muted-foreground"}`}
                    />
                    <span
                      className={`text-sm font-semibold ${
                        intent === key ? "text-foreground" : "text-muted-foreground"
                      }`}
                    >
                      {t(lang, INTENT_I18N[key] as any)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* === Step 2: Countries === */}
          {step === 2 && (
            <div className="flex-1 flex flex-col min-h-0 animate-fadeIn">
              <div className="text-center mb-3">
                <h2 className="text-xl font-bold mb-1">{t(lang, "ob_step_countries")}</h2>
                <p className="text-sm text-muted-foreground">{t(lang, "ob_countries_desc")}</p>
              </div>

              {/* 선택 카운트 + 검색 */}
              <div className="flex items-center gap-2 mb-3">
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

              {/* Pro 인라인 티저 */}
              {showProTeaser && (
                <div className="mb-2 flex items-center gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 animate-fadeIn">
                  <Sparkles className="h-4 w-4 text-amber-400 flex-shrink-0" />
                  <span className="text-xs text-amber-300 font-medium">
                    {t(lang, "ob_countries_pro_teaser")}
                  </span>
                  <span className="ml-auto text-[10px] font-bold text-amber-400 bg-amber-500/20 px-1.5 py-0.5 rounded">
                    PRO
                  </span>
                </div>
              )}

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
            </div>
          )}

          {/* === Step 3: Alerts === */}
          {step === 3 && (
            <div className="flex-1 flex flex-col animate-fadeIn">
              <div className="text-center mb-6">
                <div className="mx-auto mb-4 w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <Bell className="h-8 w-8 text-primary" />
                </div>
                <h2 className="text-xl font-bold mb-1">{t(lang, "ob_step_alerts")}</h2>
                <p className="text-sm text-muted-foreground">{t(lang, "ob_alerts_desc")}</p>
              </div>

              <div className="space-y-3">
                {/* Verified 알림 (항상 ON) */}
                <div className="flex items-center gap-3 rounded-2xl border border-border/40 bg-card/40 p-4">
                  <Shield className="h-5 w-5 text-emerald-400 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="text-sm font-semibold">{t(lang, "ob_alerts_verified")}</div>
                  </div>
                  <div className="w-10 h-6 rounded-full bg-emerald-500/80 flex items-center justify-end px-0.5">
                    <div className="w-5 h-5 rounded-full bg-white shadow-sm" />
                  </div>
                </div>

                {/* Fast 알림 (잠금 티저) */}
                <div className="relative flex items-center gap-3 rounded-2xl border border-border/20 bg-card/20 p-4 opacity-60">
                  <AlertTriangle className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-muted-foreground">
                      {t(lang, "ob_alerts_fast_locked")}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Lock className="h-3.5 w-3.5 text-amber-400" />
                    <span className="text-[10px] font-bold text-amber-400 bg-amber-500/20 px-1.5 py-0.5 rounded">
                      PRO
                    </span>
                  </div>
                </div>

                {/* 알림 권한 요청 버튼 */}
                <div className="mt-4">
                  {pushStatus === "default" && (
                    <button
                      onClick={() => {
                        trackEvent("push_pre_permission_view");
                        requestPush();
                      }}
                      className="w-full flex items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-bold bg-primary/10 border border-primary/30 text-primary hover:bg-primary/20 transition-colors active:scale-95"
                    >
                      <Bell className="h-4.5 w-4.5" />
                      {t(lang, "ob_alerts_allow")}
                    </button>
                  )}
                  {pushStatus === "granted" && (
                    <div className="flex items-center justify-center gap-2 rounded-2xl py-3 text-sm font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/30">
                      <CheckCircle2 className="h-4.5 w-4.5" />
                      {t(lang, "ob_alerts_granted")}
                    </div>
                  )}
                  {pushStatus === "denied" && (
                    <div className="flex items-center justify-center gap-2 rounded-2xl py-3 text-sm font-semibold text-red-400 bg-red-500/10 border border-red-500/30">
                      <BellOff className="h-4.5 w-4.5" />
                      {t(lang, "ob_alerts_denied")}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* === Step 4: DND === */}
          {step === 4 && (
            <div className="flex-1 flex flex-col animate-fadeIn">
              <div className="text-center mb-6">
                <div className="mx-auto mb-4 w-16 h-16 rounded-2xl bg-muted/20 flex items-center justify-center">
                  <Clock className="h-8 w-8 text-muted-foreground" />
                </div>
                <h2 className="text-xl font-bold mb-1">{t(lang, "ob_step_dnd")}</h2>
                <p className="text-sm text-muted-foreground">{t(lang, "ob_dnd_desc")}</p>
              </div>

              {/* DND 미리보기 (잠금) */}
              <div className="relative rounded-2xl border border-border/20 bg-card/20 p-6 overflow-hidden">
                {/* 잠금 오버레이 */}
                <div className="absolute inset-0 bg-background/60 backdrop-blur-[2px] z-10 flex flex-col items-center justify-center gap-2">
                  <div className="flex items-center gap-1.5">
                    <Lock className="h-4 w-4 text-amber-400" />
                    <span className="text-xs font-bold text-amber-400 bg-amber-500/20 px-2 py-0.5 rounded">
                      PRO
                    </span>
                  </div>
                  <span className="text-sm font-semibold text-muted-foreground">
                    {t(lang, "ob_dnd_pro_only")}
                  </span>
                </div>

                {/* 시계 미리보기 UI */}
                <div className="flex flex-col items-center gap-4 opacity-50">
                  <div className="relative w-32 h-32 rounded-full border-4 border-border/30 flex items-center justify-center">
                    <div className="text-center">
                      <div className="text-lg font-bold">{t(lang, "ob_dnd_preview")}</div>
                    </div>
                    {/* 시각적 호 표시 */}
                    <svg
                      className="absolute inset-0 w-full h-full -rotate-90"
                      viewBox="0 0 100 100"
                    >
                      <circle
                        cx="50"
                        cy="50"
                        r="46"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="4"
                        strokeDasharray="216.77 72.26"
                        className="text-primary/30"
                      />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* === Step 5: Summary === */}
          {step === 5 && (
            <div className="flex-1 flex flex-col animate-fadeIn">
              <div className="text-center mb-6">
                <div className="mx-auto mb-4 w-16 h-16 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
                  <CheckCircle2 className="h-8 w-8 text-emerald-400" />
                </div>
                <h2 className="text-xl font-bold mb-1">{t(lang, "ob_step_summary")}</h2>
                <p className="text-sm text-muted-foreground">{t(lang, "ob_summary_desc")}</p>
              </div>

              {/* 선택 국가별 긴장도 카드 */}
              <div className="space-y-3">
                {selectedCountries.map((code) => {
                  const td = tensions?.find((t) => t.country_code === code);
                  return (
                    <div
                      key={code}
                      className="flex items-center gap-3 rounded-2xl border border-border/40 bg-card/40 p-4"
                    >
                      <span className="text-2xl">{getFlag(code)}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-semibold truncate">
                          {getCountryName(code, lang)}
                        </div>
                        {td ? (
                          <div className={`text-xs font-medium ${tensionColor(td.tension_level)}`}>
                            {t(lang, "ob_summary_tension", {
                              score: td.raw_score.toFixed(0),
                              grade: tensionGrade(td.tension_level, lang),
                            })}
                          </div>
                        ) : (
                          <div className="text-xs text-muted-foreground">
                            {t(lang, "ob_summary_fallback")}
                          </div>
                        )}
                      </div>
                      {td && (
                        <div
                          className={`text-lg font-bold tabular-nums ${tensionColor(td.tension_level)}`}
                        >
                          {td.raw_score.toFixed(0)}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* 선택 요약 */}
              <div className="mt-4 flex flex-wrap gap-2 justify-center">
                {intent && (
                  <span className="text-xs bg-primary/10 text-primary px-2.5 py-1 rounded-full font-medium">
                    {t(lang, INTENT_I18N[intent] as any)}
                  </span>
                )}
                <span className="text-xs bg-muted/30 text-muted-foreground px-2.5 py-1 rounded-full font-medium">
                  {t(lang, "ob_select_n_countries", { n: selectedCountries.length })}
                </span>
                <span className="text-xs bg-muted/30 text-muted-foreground px-2.5 py-1 rounded-full font-medium">
                  {pushStatus === "granted"
                    ? lang === "ko"
                      ? "알림 ON"
                      : "Alerts ON"
                    : lang === "ko"
                      ? "알림 OFF"
                      : "Alerts OFF"}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 하단 버튼 */}
      <div className="relative z-10 px-4 pb-6 pt-3">
        <div className="w-full max-w-md mx-auto">
          {step < 5 ? (
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
              {t(lang, "ob_next")}
              <ChevronRight className="h-4.5 w-4.5" />
            </button>
          ) : (
            <button
              onClick={handleComplete}
              className="w-full flex items-center justify-center gap-2 rounded-2xl py-3.5 text-[15px] font-bold transition-all active:scale-95 text-primary-foreground shadow-lg"
              style={{
                background:
                  "linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary)/0.85) 100%)",
                boxShadow: "0 4px 20px rgba(99,102,241,0.3)",
              }}
            >
              {t(lang, "ob_start")}
              <ChevronRight className="h-4.5 w-4.5" />
            </button>
          )}
        </div>
      </div>

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

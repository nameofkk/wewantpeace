"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { Check, Bell, ArrowRight, Loader2, ChevronRight } from "lucide-react";
import { useAddArea, useRegisterPushToken } from "@/lib/api";
import { requestAndGetFCMToken } from "@/lib/fcm";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

/* ── 인트로 슬라이드 콘텐츠 ── */
const INTRO_SLIDES = [
  {
    emoji: "🌍",
    gradient: "from-blue-500/20 via-blue-600/10 to-transparent",
    dotColor: "bg-blue-400",
    accentColor: "text-blue-400",
    title_ko: "세계 갈등을\n실시간으로",
    title_en: "Track Global Conflicts\nin Real Time",
    desc_ko: "AI가 전 세계 뉴스를 분석해\n중요한 분쟁 이슈만 전달합니다",
    desc_en: "AI analyzes global news to deliver\nonly critical conflict updates to you",
  },
  {
    emoji: "📊",
    gradient: "from-orange-500/20 via-orange-600/10 to-transparent",
    dotColor: "bg-orange-400",
    accentColor: "text-orange-400",
    title_ko: "K-Score로 보는\n국가별 긴장도",
    title_en: "Country Tension\nvia K-Score",
    desc_ko: "0~100 점수로 긴장 수준을\n한눈에 파악하고 30일 추이도 확인하세요",
    desc_en: "Understand tension levels at a glance\nwith 0–100 scores and 30-day trends",
  },
  {
    emoji: "🔔",
    gradient: "from-green-500/20 via-green-600/10 to-transparent",
    dotColor: "bg-green-400",
    accentColor: "text-green-400",
    title_ko: "검증된 소식만\n오보 없이",
    title_en: "Verified Alerts\nNo False Alarms",
    desc_ko: "공식 소스로 확인된 이슈만 알림.\n속보도 커뮤니티에서 함께 분석합니다",
    desc_en: "Only officially verified issues.\nAnalyze breaking news together in community",
  },
];

/* ── 분쟁 지역 목록 ── */
const COUNTRIES = [
  { code: "UA", flag: "🇺🇦", name: "우크라이나", nameEn: "Ukraine", desc: "러-우 전쟁", descEn: "Russia-Ukraine War" },
  { code: "PS", flag: "🇵🇸", name: "팔레스타인", nameEn: "Palestine", desc: "가자 분쟁", descEn: "Gaza Conflict" },
  { code: "IL", flag: "🇮🇱", name: "이스라엘", nameEn: "Israel", desc: "중동 긴장", descEn: "Middle East Tension" },
  { code: "TW", flag: "🇹🇼", name: "대만", nameEn: "Taiwan", desc: "양안 관계", descEn: "Cross-Strait Relations" },
  { code: "KR", flag: "🇰🇷", name: "한국", nameEn: "South Korea", desc: "한반도 정세", descEn: "Korean Peninsula" },
  { code: "SY", flag: "🇸🇾", name: "시리아", nameEn: "Syria", desc: "내전 재발", descEn: "Civil War" },
  { code: "YE", flag: "🇾🇪", name: "예멘", nameEn: "Yemen", desc: "후티 분쟁", descEn: "Houthi Conflict" },
  { code: "MM", flag: "🇲🇲", name: "미얀마", nameEn: "Myanmar", desc: "군사 쿠데타", descEn: "Military Coup" },
  { code: "SD", flag: "🇸🇩", name: "수단", nameEn: "Sudan", desc: "내전", descEn: "Civil War" },
  { code: "KP", flag: "🇰🇵", name: "북한", nameEn: "North Korea", desc: "핵·미사일", descEn: "Nuclear & Missiles" },
  { code: "IR", flag: "🇮🇷", name: "이란", nameEn: "Iran", desc: "핵 협상·긴장", descEn: "Nuclear Negotiations" },
  { code: "RU", flag: "🇷🇺", name: "러시아", nameEn: "Russia", desc: "글로벌 갈등", descEn: "Global Conflict" },
];

const FREE_LIMIT = 2;

type Step = "intro" | "select" | "notify" | "done";

/* ── 인트로 슬라이드 컴포넌트 ── */
function IntroSlide({
  slide,
  lang,
  visible,
}: {
  slide: typeof INTRO_SLIDES[number];
  lang: "ko" | "en";
  visible: boolean;
}) {
  return (
    <div
      className={`absolute inset-0 flex flex-col items-center justify-center px-8 text-center transition-all duration-500 ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4 pointer-events-none"
      }`}
    >
      {/* 배경 그라디언트 */}
      <div className={`absolute inset-0 bg-gradient-to-b ${slide.gradient} pointer-events-none`} />

      {/* 이모지 아이콘 */}
      <div
        className="relative z-10 mb-8 flex items-center justify-center"
        style={{ animation: visible ? "floatBob 3s ease-in-out infinite" : "none" }}
      >
        <div className="text-[80px] leading-none select-none drop-shadow-lg">
          {slide.emoji}
        </div>
        {/* 광원 효과 */}
        <div
          className="absolute inset-0 rounded-full blur-3xl opacity-30"
          style={{ background: "radial-gradient(circle, white 0%, transparent 70%)" }}
        />
      </div>

      {/* 제목 */}
      <h1
        className="relative z-10 text-3xl font-black leading-tight tracking-tight whitespace-pre-line mb-4"
        style={{ animation: visible ? "fadeSlideUp 0.6s ease-out 0.1s both" : "none" }}
      >
        {lang === "en" ? slide.title_en : slide.title_ko}
      </h1>

      {/* 설명 */}
      <p
        className="relative z-10 text-sm text-muted-foreground leading-relaxed whitespace-pre-line"
        style={{ animation: visible ? "fadeSlideUp 0.6s ease-out 0.2s both" : "none" }}
      >
        {lang === "en" ? slide.desc_en : slide.desc_ko}
      </p>
    </div>
  );
}

export default function OnboardingPage() {
  const router = useRouter();
  const { addMyCountry, lang } = useAppStore();
  const [step, setStep] = useState<Step>("intro");
  const [introIdx, setIntroIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  const addArea = useAddArea();
  const registerToken = useRegisterPushToken();

  useEffect(() => {
    setMounted(true);
  }, []);

  function nextIntroSlide() {
    if (introIdx < INTRO_SLIDES.length - 1) {
      setIntroIdx((i) => i + 1);
    } else {
      setStep("select");
    }
  }

  function toggleCountry(code: string) {
    setSelected((prev) => {
      if (prev.includes(code)) return prev.filter((c) => c !== code);
      if (prev.length >= FREE_LIMIT) return prev;
      return [...prev, code];
    });
  }

  async function handleNotifyStep(enableNotif: boolean) {
    setLoading(true);
    setError(null);
    try {
      for (const code of selected) addMyCountry(code);

      try {
        if (!localStorage.getItem("dev_uid")) {
          localStorage.setItem("dev_uid", `user-${crypto.randomUUID()}`);
        }
        for (const code of selected) {
          const country = COUNTRIES.find((c) => c.code === code)!;
          await addArea.mutateAsync({
            area_type: "country",
            country_code: code,
            label: country.name,
            notify_verified: true,
            notify_fast: false,
          });
        }
      } catch { /* 백엔드 없어도 로컬 저장으로 동작 */ }

      if (enableNotif) {
        try {
          const token = await requestAndGetFCMToken();
          if (token) await registerToken.mutateAsync({ fcm_token: token, platform: "web" });
        } catch { /* 알림 권한 없어도 진행 */ }
      }

      localStorage.setItem("onboarding_done", "true");
      setStep("done");
      setTimeout(() => router.push("/home"), 1800);
    } catch {
      setError(t(lang, "onboarding_error"));
    } finally {
      setLoading(false);
    }
  }

  if (!mounted) return null;

  /* ── 완료 화면 ── */
  if (step === "done") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-6 px-8 bg-background">
        <div
          className="h-20 w-20 rounded-full flex items-center justify-center"
          style={{
            background: "radial-gradient(circle, rgba(34,197,94,0.3) 0%, rgba(34,197,94,0.05) 70%)",
            animation: "scaleIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both",
            border: "1px solid rgba(34,197,94,0.4)",
          }}
        >
          <Check className="h-10 w-10 text-green-400" style={{ animation: "scaleIn 0.3s ease-out 0.2s both" }} />
        </div>
        <div className="text-center" style={{ animation: "fadeSlideUp 0.5s ease-out 0.3s both" }}>
          <h2 className="text-2xl font-black mb-2">{t(lang, "onboarding_done_title")}</h2>
          <p className="text-sm text-muted-foreground">{t(lang, "onboarding_done_desc")}</p>
        </div>
      </div>
    );
  }

  /* ── 인트로 슬라이드 ── */
  if (step === "intro") {
    const slide = INTRO_SLIDES[introIdx];
    return (
      <div className="flex flex-col min-h-screen bg-background overflow-hidden">
        {/* 로고 */}
        <div
          className="flex items-center gap-2 px-6 pt-12 pb-0"
          style={{ animation: "fadeSlideDown 0.5s ease-out both" }}
        >
          <div className="relative h-6 w-14">
            <Image src="/logo-eye.png" alt="WeWantPeace" fill className="object-contain" />
          </div>
          <span className="text-sm font-semibold tracking-wide">WeWantPeace</span>
        </div>

        {/* 슬라이드 영역 */}
        <div className="relative flex-1">
          {INTRO_SLIDES.map((s, i) => (
            <IntroSlide key={i} slide={s} lang={lang} visible={i === introIdx} />
          ))}
        </div>

        {/* 하단 영역 */}
        <div className="px-6 pb-12 space-y-6" style={{ animation: "fadeSlideUp 0.5s ease-out 0.3s both" }}>
          {/* Dot indicator */}
          <div className="flex justify-center gap-2">
            {INTRO_SLIDES.map((s, i) => (
              <button
                key={i}
                onClick={() => setIntroIdx(i)}
                className={`rounded-full transition-all duration-300 ${
                  i === introIdx
                    ? `w-6 h-2 ${s.dotColor}`
                    : "w-2 h-2 bg-muted"
                }`}
              />
            ))}
          </div>

          {/* 다음 버튼 */}
          <button
            onClick={nextIntroSlide}
            className="w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all active:scale-95"
            style={{
              background: "linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary)/0.8) 100%)",
              color: "hsl(var(--primary-foreground))",
              boxShadow: "0 4px 24px rgba(255,255,255,0.1)",
            }}
          >
            {introIdx < INTRO_SLIDES.length - 1 ? (
              <>
                {lang === "ko" ? "다음" : "Next"}
                <ChevronRight className="h-5 w-5" />
              </>
            ) : (
              <>
                {lang === "ko" ? "시작하기" : "Get Started"}
                <ArrowRight className="h-5 w-5" />
              </>
            )}
          </button>

          {/* 건너뛰기 */}
          <div className="text-center">
            <button
              onClick={() => setStep("select")}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {lang === "ko" ? "건너뛰기" : "Skip intro"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  /* ── 지역 선택 ── */
  if (step === "select") {
    return (
      <div className="flex flex-col min-h-screen bg-background">
        {/* 헤더 */}
        <div className="px-6 pt-10 pb-4" style={{ animation: "fadeSlideDown 0.4s ease-out both" }}>
          <div className="flex items-center gap-2 mb-4">
            <div className="relative h-5 w-12">
              <Image src="/logo-eye.png" alt="WeWantPeace" fill className="object-contain" />
            </div>
          </div>

          {/* 스텝 표시 */}
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[10px] font-semibold text-primary/70 uppercase tracking-wider">
              {lang === "ko" ? "관심 지역 선택" : "Select Regions"}
            </span>
            <div className="flex-1 h-px bg-border" />
            <span className="text-[10px] text-muted-foreground">1 / 2</span>
          </div>

          <h1 className="text-2xl font-black leading-tight">{t(lang, "onboarding_select_title")}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t(lang, "onboarding_select_desc")}
            <span className="text-primary font-medium"> {t(lang, "onboarding_select_limit", { n: FREE_LIMIT })}</span>
          </p>
        </div>

        {/* 국가 그리드 */}
        <div className="flex-1 px-4 overflow-y-auto">
          <div className="grid grid-cols-3 gap-2 pb-4">
            {COUNTRIES.map((c, i) => {
              const isSelected = selected.includes(c.code);
              const isDisabled = !isSelected && selected.length >= FREE_LIMIT;
              const displayName = lang === "en" ? c.nameEn : c.name;
              const displayDesc = lang === "en" ? c.descEn : c.desc;
              return (
                <button
                  key={c.code}
                  onClick={() => toggleCountry(c.code)}
                  disabled={isDisabled}
                  style={{
                    animation: `fadeSlideUp 0.4s ease-out ${i * 0.04}s both`,
                    transform: isSelected ? "scale(1.03)" : "scale(1)",
                    transition: "transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), border-color 0.2s, background 0.2s",
                  }}
                  className={`
                    relative rounded-xl border p-3 text-left
                    ${isSelected
                      ? "border-primary bg-primary/10 shadow-[0_0_12px_rgba(255,255,255,0.08)]"
                      : isDisabled
                      ? "border-border bg-card/50 opacity-35"
                      : "border-border bg-card hover:border-primary/40 hover:bg-primary/5 active:scale-95"
                    }
                  `}
                >
                  {isSelected && (
                    <div
                      className="absolute top-1.5 right-1.5 h-4 w-4 rounded-full bg-primary flex items-center justify-center"
                      style={{ animation: "scaleIn 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) both" }}
                    >
                      <Check className="h-2.5 w-2.5 text-primary-foreground" />
                    </div>
                  )}
                  <span className="text-2xl leading-none">{c.flag}</span>
                  <p className="text-xs font-bold mt-1.5 truncate">{displayName}</p>
                  <p className="text-[10px] text-muted-foreground truncate mt-0.5">{displayDesc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* 하단 버튼 */}
        <div
          className="px-4 py-4 border-t border-border bg-background/95 backdrop-blur-sm"
          style={{ animation: "fadeSlideUp 0.4s ease-out 0.2s both" }}
        >
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-muted-foreground">
              {t(lang, "onboarding_selected_count", { n: selected.length, max: FREE_LIMIT })}
            </span>
            <div className="flex gap-1.5">
              {Array.from({ length: FREE_LIMIT }).map((_, i) => (
                <div
                  key={i}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    i < selected.length ? "w-6 bg-primary" : "w-2 bg-muted"
                  }`}
                />
              ))}
            </div>
          </div>
          <button
            onClick={() => setStep("notify")}
            disabled={selected.length === 0}
            className={`
              w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all
              ${selected.length > 0
                ? "bg-primary text-primary-foreground active:scale-95"
                : "bg-muted text-muted-foreground cursor-not-allowed"
              }
            `}
            style={selected.length > 0 ? { boxShadow: "0 4px 20px rgba(255,255,255,0.1)" } : {}}
          >
            {t(lang, "onboarding_next")}
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  /* ── 알림 설정 ── */
  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* 헤더 */}
      <div className="px-6 pt-10 pb-4" style={{ animation: "fadeSlideDown 0.4s ease-out both" }}>
        <div className="flex items-center gap-2 mb-4">
          <div className="relative h-5 w-12">
            <Image src="/logo-eye.png" alt="WeWantPeace" fill className="object-contain" />
          </div>
        </div>
        <div className="flex items-center gap-2 mb-3">
          <span className="text-[10px] font-semibold text-primary/70 uppercase tracking-wider">
            {lang === "ko" ? "알림 설정" : "Notifications"}
          </span>
          <div className="flex-1 h-px bg-border" />
          <span className="text-[10px] text-muted-foreground">2 / 2</span>
        </div>
        <h1 className="text-2xl font-black leading-tight">{t(lang, "onboarding_notify_title")}</h1>
        <p className="text-sm text-muted-foreground mt-1">{t(lang, "onboarding_notify_desc")}</p>
      </div>

      <div className="flex-1 px-4 space-y-3 overflow-y-auto">
        {/* 선택된 지역 요약 */}
        <div
          className="rounded-2xl border border-primary/20 bg-primary/5 p-4"
          style={{ animation: "fadeSlideUp 0.4s ease-out 0.05s both" }}
        >
          <p className="text-xs text-muted-foreground mb-2.5 font-medium">{t(lang, "onboarding_selected_label")}</p>
          <div className="flex flex-wrap gap-2">
            {selected.map((code) => {
              const c = COUNTRIES.find((x) => x.code === code)!;
              return (
                <div
                  key={code}
                  className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1"
                >
                  <span className="text-base leading-none">{c.flag}</span>
                  <span className="text-xs font-semibold">{lang === "en" ? c.nameEn : c.name}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 알림 종류 설명 */}
        <div
          className="rounded-2xl border border-border bg-card p-4 space-y-4"
          style={{ animation: "fadeSlideUp 0.4s ease-out 0.1s both" }}
        >
          {/* Verified */}
          <div className="flex items-start gap-3">
            <div className="h-9 w-9 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center justify-center shrink-0">
              <Bell className="h-4 w-4 text-green-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <p className="text-sm font-bold">{t(lang, "onboarding_verified_label")}</p>
                <span className="text-[9px] font-bold rounded-full bg-green-500/15 text-green-400 px-1.5 py-0.5">FREE</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{t(lang, "onboarding_verified_desc")}</p>
            </div>
          </div>

          <div className="h-px bg-border" />

          {/* Fast (Pro) */}
          <div className="flex items-start gap-3 opacity-50">
            <div className="h-9 w-9 rounded-xl bg-yellow-500/10 border border-yellow-500/20 flex items-center justify-center shrink-0">
              <Bell className="h-4 w-4 text-yellow-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <p className="text-sm font-bold">{t(lang, "onboarding_fast_label")}</p>
                <span className="text-[9px] font-bold rounded-full bg-yellow-500/15 text-yellow-400 px-1.5 py-0.5">PRO</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">{t(lang, "onboarding_fast_desc")}</p>
            </div>
          </div>
        </div>

        {error && (
          <div
            className="rounded-xl border border-red-500/30 bg-red-500/10 p-3"
            style={{ animation: "fadeSlideUp 0.3s ease-out both" }}
          >
            <p className="text-xs text-red-400">{error}</p>
          </div>
        )}
      </div>

      {/* 하단 버튼 */}
      <div
        className="px-4 py-4 border-t border-border bg-background/95 backdrop-blur-sm space-y-2.5 mt-4"
        style={{ animation: "fadeSlideUp 0.4s ease-out 0.2s both" }}
      >
        <button
          onClick={() => handleNotifyStep(true)}
          disabled={loading}
          className="w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all active:scale-95 disabled:opacity-60"
          style={{
            background: "linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary)/0.8) 100%)",
            color: "hsl(var(--primary-foreground))",
            boxShadow: "0 4px 20px rgba(255,255,255,0.1)",
          }}
        >
          {loading ? (
            <Loader2 className="h-5 w-5 animate-spin" />
          ) : (
            <>
              <Bell className="h-4 w-4" />
              {t(lang, "onboarding_allow_notify")}
            </>
          )}
        </button>
        <button
          onClick={() => handleNotifyStep(false)}
          disabled={loading}
          className="w-full py-3 rounded-2xl border border-border text-sm text-muted-foreground hover:text-foreground hover:border-primary/30 transition-colors"
        >
          {t(lang, "onboarding_skip_notify")}
        </button>
      </div>

      {/* 글로벌 CSS 애니메이션 */}
      <style jsx global>{`
        @keyframes floatBob {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-12px); }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes fadeSlideDown {
          from { opacity: 0; transform: translateY(-12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes scaleIn {
          from { opacity: 0; transform: scale(0.4); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}

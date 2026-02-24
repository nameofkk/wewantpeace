"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Globe, Check, Bell, ArrowRight, Loader2 } from "lucide-react";
import { useAddArea, useRegisterPushToken } from "@/lib/api";
import { requestAndGetFCMToken } from "@/lib/fcm";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";

// 주요 분쟁/긴장 지역 목록
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

export default function OnboardingPage() {
  const router = useRouter();
  const { addMyCountry, lang } = useAppStore();
  const [selected, setSelected] = useState<string[]>([]);
  const [step, setStep] = useState<"select" | "notify" | "done">("select");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const addArea = useAddArea();
  const registerToken = useRegisterPushToken();

  function toggleCountry(code: string) {
    setSelected((prev) => {
      if (prev.includes(code)) return prev.filter((c) => c !== code);
      if (prev.length >= FREE_LIMIT) return prev;
      return [...prev, code];
    });
  }

  async function handleSelectNext() {
    if (selected.length === 0) return;
    setStep("notify");
  }

  async function handleNotifyStep(enableNotif: boolean) {
    setLoading(true);
    setError(null);
    try {
      for (const code of selected) {
        addMyCountry(code);
      }

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
      } catch {
        // 백엔드 없을 때도 로컬 저장으로 정상 동작
      }

      if (enableNotif) {
        try {
          const token = await requestAndGetFCMToken();
          if (token) {
            await registerToken.mutateAsync({ fcm_token: token, platform: "web" });
          }
        } catch {
          // 알림 권한 없어도 진행
        }
      }

      localStorage.setItem("onboarding_done", "true");
      setStep("done");
      setTimeout(() => router.push("/home"), 1500);
    } catch {
      setError(t(lang, "onboarding_error"));
    } finally {
      setLoading(false);
    }
  }

  if (step === "done") {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4 px-6">
        <div className="h-16 w-16 rounded-full bg-green-500/20 flex items-center justify-center">
          <Check className="h-8 w-8 text-green-400" />
        </div>
        <h2 className="text-xl font-bold">{t(lang, "onboarding_done_title")}</h2>
        <p className="text-sm text-muted-foreground text-center">
          {t(lang, "onboarding_done_desc")}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      {/* 헤더 */}
      <div className="px-6 pt-12 pb-6">
        <div className="flex items-center gap-2 mb-2">
          <Globe className="h-6 w-6 text-primary" />
          <span className="text-sm font-medium text-primary">WeWantPeace</span>
        </div>

        {step === "select" && (
          <>
            <h1 className="text-2xl font-bold mt-4">{t(lang, "onboarding_select_title")}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {t(lang, "onboarding_select_desc")}
              <span className="text-primary font-medium"> {t(lang, "onboarding_select_limit", { n: FREE_LIMIT })}</span>
            </p>
          </>
        )}

        {step === "notify" && (
          <>
            <h1 className="text-2xl font-bold mt-4">{t(lang, "onboarding_notify_title")}</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {t(lang, "onboarding_notify_desc")}
            </p>
          </>
        )}
      </div>

      {/* 국가 선택 그리드 */}
      {step === "select" && (
        <>
          <div className="flex-1 px-4 overflow-y-auto">
            <div className="grid grid-cols-3 gap-2 pb-4">
              {COUNTRIES.map((c) => {
                const isSelected = selected.includes(c.code);
                const isDisabled = !isSelected && selected.length >= FREE_LIMIT;
                const displayName = lang === "en" ? c.nameEn : c.name;
                const displayDesc = lang === "en" ? c.descEn : c.desc;
                return (
                  <button
                    key={c.code}
                    onClick={() => toggleCountry(c.code)}
                    disabled={isDisabled}
                    className={`
                      relative rounded-xl border p-3 text-left transition-all
                      ${isSelected
                        ? "border-primary bg-primary/10"
                        : isDisabled
                        ? "border-border bg-card/50 opacity-40"
                        : "border-border bg-card hover:border-primary/50"
                      }
                    `}
                  >
                    {isSelected && (
                      <div className="absolute top-1.5 right-1.5 h-4 w-4 rounded-full bg-primary flex items-center justify-center">
                        <Check className="h-2.5 w-2.5 text-white" />
                      </div>
                    )}
                    <span className="text-2xl">{c.flag}</span>
                    <p className="text-xs font-semibold mt-1 truncate">{displayName}</p>
                    <p className="text-[10px] text-muted-foreground truncate">{displayDesc}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 선택 카운터 + 다음 버튼 */}
          <div className="px-4 py-4 border-t border-border bg-background">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm text-muted-foreground">
                {t(lang, "onboarding_selected_count", { n: selected.length, max: FREE_LIMIT })}
              </span>
              <div className="flex gap-1">
                {[0, 1].map((i) => (
                  <div
                    key={i}
                    className={`h-1.5 w-6 rounded-full transition-all ${
                      i < selected.length ? "bg-primary" : "bg-muted"
                    }`}
                  />
                ))}
              </div>
            </div>
            <button
              onClick={handleSelectNext}
              disabled={selected.length === 0}
              className={`
                w-full py-3 rounded-xl font-semibold flex items-center justify-center gap-2 transition-all
                ${selected.length > 0
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
                }
              `}
            >
              {t(lang, "onboarding_next")}
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </>
      )}

      {/* 알림 설정 단계 */}
      {step === "notify" && (
        <div className="flex-1 px-6 flex flex-col justify-between pb-8">
          <div className="mt-4 space-y-4">
            {/* 선택한 국가 요약 */}
            <div className="rounded-xl border border-border bg-card p-4">
              <p className="text-xs text-muted-foreground mb-2">{t(lang, "onboarding_selected_label")}</p>
              <div className="flex gap-2">
                {selected.map((code) => {
                  const c = COUNTRIES.find((x) => x.code === code)!;
                  const displayName = lang === "en" ? c.nameEn : c.name;
                  return (
                    <div key={code} className="flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1">
                      <span>{c.flag}</span>
                      <span className="text-xs font-medium">{displayName}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 알림 설명 */}
            <div className="rounded-xl border border-border bg-card p-4 space-y-3">
              <div className="flex items-start gap-3">
                <Bell className="h-5 w-5 text-primary mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold">{t(lang, "onboarding_verified_label")}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {t(lang, "onboarding_verified_desc")}
                  </p>
                </div>
              </div>
              <div className="flex items-start gap-3 opacity-50">
                <Bell className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-semibold">{t(lang, "onboarding_fast_label")}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {t(lang, "onboarding_fast_desc")}
                  </p>
                </div>
              </div>
            </div>

            {error && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3">
                <p className="text-xs text-red-400">{error}</p>
              </div>
            )}
          </div>

          <div className="space-y-3 mt-6">
            <button
              onClick={() => handleNotifyStep(true)}
              disabled={loading}
              className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-semibold flex items-center justify-center gap-2"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
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
              className="w-full py-3 rounded-xl border border-border text-sm text-muted-foreground"
            >
              {t(lang, "onboarding_skip_notify")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

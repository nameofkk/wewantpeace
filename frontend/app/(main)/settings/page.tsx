"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { MapPin, Plus, X, Search, ChevronUp, ChevronDown, Check, LogOut, LogIn, User, Loader2, Trash2, Sun, Moon, Mail, MessageCircleQuestion, Send, CheckCircle, BookOpen, Lock, Gift, Code } from "lucide-react";
import { cn, usePageTitle } from "@/lib/utils";
import { useAppStore, FREE_COUNTRY_LIMIT, PRO_COUNTRY_LIMIT, type Theme } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useMe, usePatchProfile, usePatchPreferences, useMyPreferences, useMyAreas, useAddArea, useDeleteArea, usePatchArea, useRegisterPushToken, useDeletePushToken, API_BASE } from "@/lib/api";
import { requestAndGetFCMToken, getStoredFCMToken, clearStoredFCMToken, isPushSupported } from "@/lib/fcm";
import { ALL_COUNTRIES, getCountryName, getRegionName, getFlag } from "@/lib/countries";
import { SUPPORTED_HOME_COUNTRIES } from "@/lib/impact-factors";
import { CONTACT_EMAIL } from "@/lib/legal-data";
import { useAuth, signOut } from "@/lib/auth";
import { LogoIcon } from "@/components/ui/logo-icon";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { PaywallModal, usePaywall } from "@/components/ui/PaywallModal";
import AppTour from "@/components/ui/AppTour";
import TourHelpButton from "@/components/ui/TourHelpButton";
import { isTossMiniApp } from "@/lib/platform";
import type { Step } from "react-joyride";

// ── 국가 선택 패널 ─────────────────────────────────────────────────────────
function CountryPickerPanel({
  selected, onAdd, onClose, canAdd, plan, lang,
}: {
  selected: string[];
  onAdd: (code: string) => void;
  onClose: () => void;
  canAdd: boolean;
  plan: string;
  lang: Lang;
}) {
  const [search, setSearch] = useState("");

  const filtered = search.trim()
    ? ALL_COUNTRIES.filter(
        (c) =>
          c.name.includes(search) ||
          c.code.toLowerCase().includes(search.toLowerCase()) ||
          getCountryName(c.code, lang).toLowerCase().includes(search.toLowerCase())
      )
    : ALL_COUNTRIES;

  const regions = Array.from(new Set(filtered.map((c) => c.region)));

  return (
    <div className="border-t border-border bg-background/98 p-4 space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="text"
          placeholder={t(lang, "settings_search_country")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          autoFocus
          className="w-full rounded-lg border border-border bg-secondary pl-9 pr-3 py-2 text-sm focus:outline-none focus:border-primary"
        />
      </div>

      {!canAdd && (
        <p className="text-[11px] text-amber-400 text-center">
          {plan === "free"
            ? t(lang, "settings_free_limit", { n: FREE_COUNTRY_LIMIT })
            : t(lang, "settings_pro_limit", { n: PRO_COUNTRY_LIMIT })}
        </p>
      )}

      <div className="max-h-64 overflow-y-auto space-y-3 pr-1">
        {regions.map((region) => {
          const list = filtered.filter((c) => c.region === region);
          return (
            <div key={region}>
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">
                {getRegionName(region, lang)}
              </p>
              <div className="grid grid-cols-2 gap-1.5">
                {list.map((country) => {
                  const isSelected = selected.includes(country.code);
                  return (
                    <button
                      key={country.code}
                      onClick={() => { if (!isSelected) onAdd(country.code); }}
                      disabled={isSelected || (!canAdd && !isSelected)}
                      className={cn(
                        "flex items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors",
                        isSelected
                          ? "bg-primary/15 border border-primary/40 text-primary cursor-default"
                          : canAdd
                          ? "bg-secondary hover:bg-secondary/80 border border-transparent"
                          : "bg-secondary/40 border border-transparent opacity-40 cursor-not-allowed"
                      )}
                    >
                      <span className="text-base leading-none">{country.flag}</span>
                      <span className="flex-1 text-xs truncate">{getCountryName(country.code, lang)}</span>
                      {isSelected && <span className="text-[10px] text-primary font-bold">✓</span>}
                    </button>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <button
        onClick={onClose}
        className="w-full py-2 rounded-lg border border-border text-sm text-muted-foreground hover:bg-muted/30"
      >
        {t(lang, "settings_close")}
      </button>
    </div>
  );
}

// ── 메인 설정 페이지 ──────────────────────────────────────────────────────
export default function SettingsPage() {
  const router = useRouter();
  const { user: firebaseUser, loading: authLoading } = useAuth();
  const { myCountries, addMyCountry, removeMyCountry, userPlan, lang, setLang, setUserPlan, theme, homeCountry, setHomeCountry, reset } = useAppStore();
  usePageTitle(lang, "tab_settings");
  const { data: me } = useMe();

  // 서버 plan → store 동기화 (Pro/Pro+ 관심국가 제한 반영)
  useEffect(() => {
    const serverPlan = (me as { plan?: string })?.plan;
    if (serverPlan && serverPlan !== userPlan) {
      setUserPlan(serverPlan as "free" | "pro" | "pro_plus");
    }
  }, [me, userPlan, setUserPlan]);
  const { data: prefs } = useMyPreferences();
  const { data: areas } = useMyAreas();
  const patchPrefs = usePatchPreferences();
  const patchProfile = usePatchProfile();
  const addArea = useAddArea();
  const deleteArea = useDeleteArea();
  const patchArea = usePatchArea();
  const registerToken = useRegisterPushToken();
  const deleteToken = useDeletePushToken();

  // country_code → 대표 area (첫 번째) 매핑 + 중복 ID 목록
  const areasMap = Object.fromEntries((areas ?? []).map((a) => [a.country_code, a]));
  const areasDupMap: Record<string, number[]> = {};
  for (const a of areas ?? []) {
    (areasDupMap[a.country_code] ??= []).push(a.id);
  }

  const [showPicker, setShowPicker] = useState(false);
  const [showHomeCountryPicker, setShowHomeCountryPicker] = useState(false);
  const [notifStatus, setNotifStatus] = useState<"idle" | "loading" | "done" | "denied" | "unsupported">("idle");
  const [openInfo, setOpenInfo] = useState<string | null>(null); // "verified-KR" | "fast-KR" 형태

  // 알림 설정 로컬 상태
  const [kscoreValue, setKscoreValue] = useState(4.0);
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [quietEnabled, setQuietEnabled] = useState(false);
  const [quietStart, setQuietStart] = useState("23:00");
  const [quietEnd, setQuietEnd] = useState("07:00");
  // 토스트 알림
  const [toast, setToast] = useState<{ msg: string; type: "success" | "info" } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showToast = (msg: string, type: "success" | "info" = "success") => {
    setToast({ msg, type });
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  };
  // notifSaving/notifSaved 제거 — 자동 저장

  // debounce refs — 빠른 연속 토글 시 마지막 값만 서버에 전송
  const topicDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestTopicsRef = useRef<string[]>(selectedTopics);
  const quietDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const latestQuietRef = useRef<{ start: string; end: string }>({ start: quietStart, end: quietEnd });

  // 프로필 편집
  const [showProfileEdit, setShowProfileEdit] = useState(false);
  const [editNickname, setEditNickname] = useState("");
  const [editBio, setEditBio] = useState("");
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSuccess, setProfileSuccess] = useState(false);

  // 회원 탈퇴
  const [deleteStep, setDeleteStep] = useState(0); // 0: idle, 1: confirm dialog
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteInput, setDeleteInput] = useState("");

  // ── PaywallModal 훅 ──────────────────────────────────────────
  const verifiedPaywall = usePaywall("verified_locked");
  const kscorePaywall = usePaywall("kscore_threshold_locked");
  const watchCountryPaywall = usePaywall("watch_country_limit_locked");

  // 피드백 모달
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  // ── 가이드 투어 ──────────────────────────────────────────
  const [tourRun, setTourRun] = useState(false);
  const tourSteps: Step[] = useMemo(() => [
    {
      target: "[data-tour='settings-page']",
      content: t(lang, "tour_settings_page_role"),
      placement: "center" as const,
      disableBeacon: true,
    },
    {
      target: "[data-tour='settings-home-country']",
      content: t(lang, "tour_settings_home_country"),
      placement: "bottom" as const,
    },
    {
      target: "[data-tour='settings-watched']",
      content: t(lang, "tour_settings_watched"),
      placement: "bottom" as const,
    },
    {
      target: "[data-tour='settings-notifications']",
      content: t(lang, "tour_settings_notifications"),
      placement: "bottom" as const,
    },
    {
      target: "[data-tour='settings-kscore-slider']",
      content: t(lang, "tour_settings_kscore_slider"),
      placement: "bottom" as const,
    },
    {
      target: "[data-tour='settings-marketing-email']",
      content: t(lang, "tour_settings_intel_alerts"),
      placement: "bottom" as const,
    },
    {
      target: "[data-tour='settings-plan']",
      content: t(lang, "tour_settings_plan"),
      placement: "bottom" as const,
    },
  ], [lang]);

  async function handleSubmitFeedback() {
    if (!firebaseUser || !feedbackMsg.trim()) return;
    setFeedbackSending(true);
    setFeedbackError(null);
    try {
      const token = await firebaseUser.getIdToken();
      const res = await fetch(`${API_BASE}/auth/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ message: feedbackMsg.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || t(lang, "feedback_error"));
      }
      setFeedbackSent(true);
      setFeedbackMsg("");
    } catch (e: unknown) {
      const err = e as { message?: string };
      setFeedbackError(err.message || t(lang, "feedback_error"));
    } finally {
      setFeedbackSending(false);
    }
  }

  // 구독 정보 조회
  const [subInfo, setSubInfo] = useState<{
    platform: string;
    started_at?: string;
    expires_at?: string;
    next_billing_at?: string;
    auto_renewing?: boolean;
    status?: string;
    trial_end?: string;
  }>({ platform: "web" });
  const subPlatform = subInfo.platform;
  useEffect(() => {
    if (!firebaseUser) return;
    firebaseUser.getIdToken().then((token) => {
      fetch(`${API_BASE}/subscriptions/my`, {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((r) => r.json())
        .then((d) => {
          if (d.plan !== "free") {
            setSubInfo({
              platform: d.platform || "web",
              started_at: d.started_at,
              expires_at: d.expires_at,
              next_billing_at: d.next_billing_at,
              auto_renewing: d.auto_renewing,
              status: d.status,
              trial_end: d.trial_end,
            });
          }
        })
        .catch(() => {});
    });
  }, [firebaseUser, API_BASE]);

  async function handleSignOut() {
    await signOut();
    reset();
    router.push("/login");
  }

  async function handleDeleteAccount() {
    if (!firebaseUser) return;
    setDeleteLoading(true);
    try {
      const token = await firebaseUser.getIdToken();
      const res = await fetch(`${API_BASE}/auth/account`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok && res.status !== 204) {
        throw new Error("Failed");
      }
      // Firebase Auth에서도 사용자 삭제 (동일 이메일 재가입 가능하도록)
      try {
        await firebaseUser.delete();
      } catch {
        // reauthentication 필요 등 실패 시 signOut만 진행
      }
      await signOut();
      localStorage.clear();
      alert(t(lang, "settings_delete_success"));
      router.push("/login");
    } catch {
      alert(lang === "en" ? "Failed to delete account." : "탈퇴 처리에 실패했습니다.");
    } finally {
      setDeleteLoading(false);
      setDeleteStep(0);
    }
  }

  function openProfileEdit() {
    const meData = me as { nickname?: string; bio?: string } | undefined;
    setEditNickname(meData?.nickname || firebaseUser?.displayName || "");
    setEditBio(meData?.bio || "");
    setProfileError(null);
    setProfileSuccess(false);
    setShowProfileEdit(true);
  }

  async function handleProfileSave() {
    if (!firebaseUser) return;
    setProfileSaving(true);
    setProfileError(null);
    try {
      const token = await firebaseUser.getIdToken();
      const res = await fetch(`${API_BASE}/auth/profile`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ nickname: editNickname.trim(), bio: editBio.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = err.detail;
        throw new Error(
          Array.isArray(detail) ? detail.map((d: { msg: string }) => d.msg).join(", ")
          : typeof detail === "string" ? detail : (lang === "ko" ? "저장에 실패했습니다." : "Failed to save.")
        );
      }
      setProfileSuccess(true);
      setShowProfileEdit(false);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setProfileError(err.message || (lang === "ko" ? "저장에 실패했습니다." : "Failed to save."));
    } finally {
      setProfileSaving(false);
    }
  }

  // prefs 로드 시 알림 상태 동기화
  useEffect(() => {
    if (prefs) {
      setKscoreValue(prefs.min_kscore ?? 4.0);
      setSelectedTopics(prefs.topics ?? []);
      const hasQuiet = !!(prefs.quiet_hours_start && prefs.quiet_hours_end);
      setQuietEnabled(hasQuiet);
      setQuietStart(prefs.quiet_hours_start || "23:00");
      setQuietEnd(prefs.quiet_hours_end || "07:00");
    }
  }, [prefs]);

  // ?section=countries 파라미터로 진입 시 picker 자동 오픈
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("section") === "countries") {
      setShowPicker(true);
    }
  }, []);

  const plan = (me as { plan?: string })?.plan ?? userPlan ?? "free";
  const canAdd = plan === "pro_plus"
    ? true
    : plan === "pro"
    ? myCountries.length < PRO_COUNTRY_LIMIT
    : myCountries.length < FREE_COUNTRY_LIMIT;

  const TOPICS = ["conflict", "terror", "coup", "sanctions", "cyber", "protest", "diplomacy", "maritime", "disaster", "health"];
  const TOPIC_LABELS: Record<string, { ko: string; en: string }> = {
    conflict: { ko: "분쟁", en: "Conflict" },
    terror: { ko: "테러", en: "Terror" },
    coup: { ko: "쿠데타", en: "Coup" },
    sanctions: { ko: "제재", en: "Sanctions" },
    cyber: { ko: "사이버", en: "Cyber" },
    protest: { ko: "시위", en: "Protest" },
    diplomacy: { ko: "외교", en: "Diplomacy" },
    maritime: { ko: "해양", en: "Maritime" },
    disaster: { ko: "재난·재해", en: "Disaster" },
    health: { ko: "감염병·보건", en: "Health" },
  };

  async function saveNotifPatch(patch: Parameters<typeof patchPrefs.mutate>[0]) {
    try {
      await patchPrefs.mutateAsync(patch);
    } catch {}
  }

  function handleSaveKscore() {
    saveNotifPatch({ min_kscore: kscoreValue });
  }

  function handleToggleTopic(topic: string) {
    const next = selectedTopics.includes(topic)
      ? selectedTopics.filter((t) => t !== topic)
      : [...selectedTopics, topic];
    setSelectedTopics(next);
    latestTopicsRef.current = next;

    if (topicDebounceRef.current) clearTimeout(topicDebounceRef.current);
    topicDebounceRef.current = setTimeout(() => {
      saveNotifPatch({ topics: latestTopicsRef.current });
    }, 300);
  }

  function handleSetAllTopics(topics: string[]) {
    setSelectedTopics(topics);
    latestTopicsRef.current = topics;

    if (topicDebounceRef.current) clearTimeout(topicDebounceRef.current);
    topicDebounceRef.current = setTimeout(() => {
      saveNotifPatch({ topics: latestTopicsRef.current });
    }, 300);
  }

  function handleSaveQuietHours(start: string, end: string) {
    latestQuietRef.current = { start, end };

    if (quietDebounceRef.current) clearTimeout(quietDebounceRef.current);
    quietDebounceRef.current = setTimeout(() => {
      saveNotifPatch({
        quiet_hours_start: latestQuietRef.current.start,
        quiet_hours_end: latestQuietRef.current.end,
      });
    }, 300);
  }

  // 국가 코드 → 이름+플래그
  const countryMap = Object.fromEntries(ALL_COUNTRIES.map((c) => [c.code, c]));

  function handleAdd(code: string) {
    const ok = addMyCountry(code, plan);
    if (!ok) {
      // Free 유저 제한 초과 시 PaywallModal
      if (plan === "free") {
        watchCountryPaywall.show();
      }
      return;
    }
    // 백엔드에도 저장
    addArea.mutate({ area_type: "country", country_code: code });
    const newCount = myCountries.length + 1;
    if ((plan === "free" && newCount >= FREE_COUNTRY_LIMIT) ||
        (plan === "pro" && newCount >= PRO_COUNTRY_LIMIT)) {
      setShowPicker(false);
    }
  }

  async function handleTogglePush() {
    // 비로그인 유저가 토글 시 로그인 유도
    if (!firebaseUser) {
      router.push("/login?returnUrl=/settings");
      return;
    }
    if (hasFCMToken) {
      // 즉시 UI 반영 → 비동기 처리
      setNotifStatus("idle");
      const token = getStoredFCMToken();
      clearStoredFCMToken();
      if (token && firebaseUser) {
        try { await deleteToken.mutateAsync({ fcm_token: token }); } catch {}
      }
    } else {
      // React Native 환경에서는 isPushSupported가 false를 반환하므로 별도 처리
      const isRN = typeof window !== "undefined" && !!(window.__REACT_NATIVE__ || window.ReactNativeWebView);
      if (!isRN && !isPushSupported()) { setNotifStatus("unsupported"); return; }
      // 즉시 UI 반영
      setNotifStatus("done");
      try {
        const token = await requestAndGetFCMToken();
        if (!token) {
          if (isRN) {
            setNotifStatus("idle");
          } else {
            const perm = typeof window !== "undefined" && "Notification" in window
              ? Notification.permission : "default";
            setNotifStatus(perm === "denied" ? "denied" : "idle");
          }
          return;
        }
        const pushPlatform = isRN
          ? (window.__NATIVE_PLATFORM__ === "ios" ? "ios" : "android")
          : "web";
        await registerToken.mutateAsync({ fcm_token: token, platform: pushPlatform });
      } catch {
        setNotifStatus("idle");
      }
    }
  }

  const hasFCMToken =
    notifStatus === "done" ||
    (typeof window !== "undefined" && !!getStoredFCMToken());

  return (
    <div className="flex flex-col" data-tour="settings-page">
      <AppTour tourId="settings" steps={tourSteps} run={tourRun} onComplete={() => setTourRun(false)} />
      <TourHelpButton tourId="settings" onStartTour={() => setTourRun(true)} />
      {/* 헤더 */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 mb-1">
          <div className="flex items-center min-w-0">
            <h1 className="text-sm font-bold whitespace-nowrap">{t(lang, "settings_title")}</h1>
          </div>
          <div className="flex justify-center">
            <LogoIcon height={26} hideText />
          </div>
          <div />
        </div>
        <p className="text-[11px] text-muted-foreground">{t(lang, "settings_subtitle")}</p>
      </div>

      <div className="px-4 py-4 space-y-6">

        {/* ── 로그인 상태 카드 ────────────────────────────────────── */}
        <section>
          <div className="rounded-xl border border-border bg-card p-4">
            {authLoading ? (
              <div className="flex items-center gap-3 animate-pulse">
                <div className="h-10 w-10 rounded-full bg-muted" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 w-32 bg-muted rounded" />
                  <div className="h-2 w-24 bg-muted rounded" />
                </div>
              </div>
            ) : firebaseUser ? (
              <div className="flex items-center gap-3">
                {firebaseUser.photoURL ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={firebaseUser.photoURL} alt={lang === "ko" ? "프로필" : "Profile"} className="h-10 w-10 rounded-full object-cover" />
                ) : (
                  <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                    <User className="h-5 w-5 text-primary" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">
                    {(me as { nickname?: string })?.nickname || firebaseUser.displayName || (lang === "ko" ? "사용자" : "User")}
                  </p>
                  <p className="text-[11px] text-muted-foreground truncate">{firebaseUser.email}</p>
                  <span className={cn(
                    "inline-block mt-0.5 rounded-full px-2 py-0.5 text-[10px] font-bold shadow-sm",
                    plan === "pro_plus" ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white" :
                    plan === "pro" ? "bg-gradient-to-r from-blue-500 to-cyan-400 text-white" :
                    "bg-muted text-muted-foreground"
                  )}>
                    {plan === "pro_plus" ? "Pro+" : plan === "pro" ? "Pro" : "Free"}
                  </span>
                </div>
                <button
                  onClick={handleSignOut}
                  className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:text-destructive hover:border-destructive/40 transition-colors"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  {t(lang, "settings_logout")}
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-muted flex items-center justify-center">
                  <User className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-muted-foreground">{t(lang, "settings_login_prompt")}</p>
                  <p className="text-[11px] text-muted-foreground">{t(lang, "settings_login_prompt_sub")}</p>
                </div>
                <button
                  onClick={() => router.push("/login")}
                  className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground"
                >
                  <LogIn className="h-3.5 w-3.5" />
                  {t(lang, "settings_login_btn")}
                </button>
              </div>
            )}
          </div>
        </section>

        {/* ── 관심지역 ─────────────────────────────────────────────── */}
        <section data-tour="settings-watched">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {t(lang, "settings_monitored")}
            </h2>
            {firebaseUser && (
              <span className="text-[10px] text-muted-foreground">
                {myCountries.length}/
                {plan === "free" ? FREE_COUNTRY_LIMIT : plan === "pro" ? PRO_COUNTRY_LIMIT : t(lang, "settings_unlimited")}
              </span>
            )}
          </div>


          <div className="rounded-xl border border-border bg-card overflow-hidden">
            {/* 비로그인 상태 */}
            {!firebaseUser ? (
              <div className="p-6 flex flex-col items-center gap-3 text-center">
                <MapPin className="h-8 w-8 text-muted-foreground/50" />
                <div>
                  <p className="text-sm font-medium">{t(lang, "settings_login_required_title")}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{t(lang, "settings_login_required_desc")}</p>
                </div>
                <button
                  onClick={() => router.push("/login")}
                  className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-xs font-medium text-primary-foreground"
                >
                  <LogIn className="h-3.5 w-3.5" />
                  {t(lang, "settings_login_btn")}
                </button>
              </div>
            ) : (
              <>
                {/* 선택된 국가 목록 */}
                {myCountries.length === 0 ? (
                  <div className="p-4 text-center text-sm text-muted-foreground">
                    {t(lang, "settings_add_country")}
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {myCountries.map((code) => {
                      const c = countryMap[code];
                      const area = areasMap[code];
                      const inactive = area && !area.is_active;
                      return (
                        <div key={code} className={cn("flex items-center gap-3 px-4 py-3", inactive && "opacity-40")}>
                          <span className="text-xl">{c?.flag ?? "🌐"}</span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-medium">{getCountryName(code, lang)}</p>
                            {inactive && (
                              <div className="mt-1 space-y-0.5">
                                <p className="text-[10px] text-amber-400">{t(lang, "settings_area_inactive")}</p>
                                <Link href="/upgrade" className="text-[10px] text-primary hover:underline">
                                  {t(lang, "settings_area_upgrade_hint")}
                                </Link>
                              </div>
                            )}
                            {area && !inactive ? (
                              <div className={cn("mt-2 space-y-1.5", !hasFCMToken && "opacity-40 pointer-events-none")}>
                                {!hasFCMToken && (
                                  <p className="text-[9px] text-muted-foreground">{t(lang, "settings_push_off_hint")}</p>
                                )}
                                {/* Fast 토글 — 모든 플랜에서 사용 가능 */}
                                <div>
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={() => {
                                        if (hasFCMToken) patchArea.mutate({ id: area.id, body: { notify_fast: !area.notify_fast } });
                                      }}
                                      disabled={!hasFCMToken}
                                      className={cn(
                                        "h-4 w-7 rounded-full relative flex-shrink-0 transition-colors",
                                        !hasFCMToken ? "bg-muted cursor-not-allowed"
                                          : area.notify_fast ? "bg-orange-500" : "bg-muted"
                                      )}
                                    >
                                      <div className={cn(
                                        "h-3 w-3 rounded-full bg-white absolute top-0.5 transition-transform",
                                        hasFCMToken && area.notify_fast ? "translate-x-3.5" : "translate-x-0.5"
                                      )} />
                                    </button>
                                    <span className={cn(
                                      "text-[11px]",
                                      !hasFCMToken ? "text-muted-foreground"
                                        : area.notify_fast ? "text-orange-400" : "text-muted-foreground"
                                    )}>
                                      {area.notify_fast
                                        ? (t(lang, "settings_fast_on"))
                                        : (t(lang, "settings_fast_off"))}
                                    </span>
                                    <button
                                      onClick={() => setOpenInfo(openInfo === `fast-${code}` ? null : `fast-${code}`)}
                                      className="ml-auto text-[11px] text-muted-foreground/60 hover:text-muted-foreground leading-none pointer-events-auto"
                                    >
                                      ⓘ
                                    </button>
                                  </div>
                                  {openInfo === `fast-${code}` && (
                                    <p className="mt-1 ml-9 text-[10px] text-muted-foreground bg-muted/40 rounded px-2 py-1">
                                      {t(lang, "settings_fast_info")}
                                    </p>
                                  )}
                                </div>

                                {/* Verified 토글 — Free 사용자 잠금 */}
                                <div>
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={() => {
                                        if (plan === "free") {
                                          verifiedPaywall.show();
                                          return;
                                        }
                                        if (hasFCMToken) patchArea.mutate({ id: area.id, body: { notify_verified: !area.notify_verified } });
                                      }}
                                      disabled={!hasFCMToken && plan !== "free"}
                                      className={cn(
                                        "h-4 w-7 rounded-full relative flex-shrink-0 transition-colors",
                                        plan === "free" ? "bg-muted opacity-60 cursor-pointer"
                                          : !hasFCMToken ? "bg-muted opacity-40 cursor-not-allowed"
                                          : area.notify_verified ? "bg-green-500" : "bg-muted"
                                      )}
                                    >
                                      <div className={cn(
                                        "h-3 w-3 rounded-full bg-white absolute top-0.5 transition-transform",
                                        area.notify_verified && plan !== "free" && hasFCMToken ? "translate-x-3.5" : "translate-x-0.5"
                                      )} />
                                    </button>
                                    <span className={cn(
                                      "text-[11px]",
                                      (plan === "free" || !hasFCMToken) ? "text-muted-foreground/40"
                                        : area.notify_verified ? "text-green-400" : "text-muted-foreground"
                                    )}>
                                      {plan === "free"
                                        ? (t(lang, "settings_verified_pro_only"))
                                        : area.notify_verified
                                        ? (t(lang, "settings_verified_on"))
                                        : (t(lang, "settings_verified_off"))}
                                    </span>
                                    <button
                                      onClick={() => setOpenInfo(openInfo === `verified-${code}` ? null : `verified-${code}`)}
                                      className="ml-auto text-[11px] text-muted-foreground/60 hover:text-muted-foreground leading-none pointer-events-auto"
                                    >
                                      ⓘ
                                    </button>
                                  </div>
                                  {openInfo === `verified-${code}` && (
                                    <p className="mt-1 ml-9 text-[10px] text-muted-foreground bg-muted/40 rounded px-2 py-1">
                                      {t(lang, "settings_verified_info")}
                                    </p>
                                  )}
                                </div>
                              </div>
                            ) : !area ? (
                              <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                                <Loader2 className="h-3 w-3 animate-spin" />
                                {t(lang, "settings_alert_loading")}
                              </div>
                            ) : null}
                          </div>
                          <button
                            onClick={() => {
                              removeMyCountry(code);
                              // 중복 레코드 모두 삭제
                              const ids = areasDupMap[code] ?? (area ? [area.id] : []);
                              ids.forEach((id) => deleteArea.mutate(id));
                            }}
                            className="rounded-full p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                          >
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* 추가 버튼 */}
                {canAdd ? (
                  <button
                    onClick={() => setShowPicker((v) => !v)}
                    className="flex items-center gap-3 px-4 py-3 w-full text-left hover:bg-muted/30 transition-colors border-t border-border"
                  >
                    <div className="h-7 w-7 rounded-full border-2 border-dashed border-muted-foreground/50 flex items-center justify-center">
                      {showPicker ? (
                        <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
                      ) : (
                        <Plus className="h-3.5 w-3.5 text-muted-foreground" />
                      )}
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {showPicker ? t(lang, "settings_collapse_picker") : t(lang, "settings_add_country")}
                    </span>
                    {plan === "free" && (
                      <span className="ml-auto text-[10px] text-muted-foreground">
                        {myCountries.length}/{FREE_COUNTRY_LIMIT}
                      </span>
                    )}
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      if (plan === "free") watchCountryPaywall.show();
                    }}
                    className="flex items-center gap-3 px-4 py-3 border-t border-border w-full text-left hover:bg-muted/30 transition-colors cursor-pointer"
                  >
                    <MapPin className="h-4 w-4 text-muted-foreground" />
                    <p className="text-[11px] text-muted-foreground">
                      {t(lang, "settings_upgrade_for_unlimited")}
                    </p>
                    {plan === "free" && <Lock className="h-3 w-3 text-muted-foreground ml-auto" />}
                  </button>
                )}

                {showPicker && (
                  <CountryPickerPanel
                    selected={myCountries}
                    onAdd={handleAdd}
                    onClose={() => setShowPicker(false)}
                    canAdd={canAdd}
                    plan={plan}
                    lang={lang}
                  />
                )}
              </>
            )}
          </div>
        </section>

        {/* ── 언어 설정 ─────────────────────────────────────────────── */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {t(lang, "settings_language")}
          </h2>
          <div className="rounded-xl border border-border bg-card p-1 flex gap-1">
            {(["ko", "en"] as const).map((l) => (
              <button
                key={l}
                onClick={() => { setLang(l); saveNotifPatch({ language: l }); }}
                className={cn(
                  "flex-1 py-2 rounded-lg text-sm font-medium transition-colors",
                  lang === l
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {l === "ko" ? "🇰🇷 한국어" : "🇺🇸 English"}
              </button>
            ))}
          </div>
        </section>

        {/* ── 테마 설정 (토스 미니앱에서는 라이트 모드 고정) ───────── */}
        {!isTossMiniApp() && (
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {t(lang, "settings_theme")}
          </h2>
          <div className="rounded-xl border border-border bg-card p-1 flex gap-1">
            {(["dark", "light"] as const).map((th) => (
              <button
                key={th}
                onClick={() => useAppStore.getState().setTheme(th)}
                className={cn(
                  "flex-1 py-2 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-1.5",
                  theme === th
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {th === "dark" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
                {th === "dark" ? t(lang, "settings_theme_dark") : t(lang, "settings_theme_light")}
              </button>
            ))}
          </div>
        </section>
        )}

        {/* ── 알림 설정 (토스 미니앱에서는 숨김) ────────────────────── */}
        {!isTossMiniApp() && <section data-tour="settings-notifications">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {t(lang, "settings_notifications")}
          </h2>
          <div className="rounded-xl border border-border bg-card divide-y divide-border">

            {/* 1. 푸시 알림 토글 */}
            <div className="p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">
                    {t(lang, "settings_push_title")}
                  </p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">
                    {hasFCMToken
                      ? t(lang, "settings_push_desc_enabled")
                      : notifStatus === "unsupported"
                      ? t(lang, "settings_push_desc_unsupported")
                      : notifStatus === "denied"
                      ? t(lang, "settings_push_desc_denied")
                      : t(lang, "settings_push_desc_default")
                    }
                  </p>
                </div>

                <button
                  onClick={handleTogglePush}
                  disabled={notifStatus === "denied" || notifStatus === "unsupported"}
                  className={cn(
                    "h-6 w-11 rounded-full relative flex-shrink-0 transition-colors",
                    (notifStatus === "denied" || notifStatus === "unsupported")
                      ? "bg-muted opacity-40 cursor-not-allowed"
                      : hasFCMToken ? "bg-green-500" : "bg-muted"
                  )}
                >
                  <div className={cn(
                    "h-5 w-5 rounded-full bg-white absolute top-0.5 transition-transform shadow-sm",
                    hasFCMToken ? "translate-x-[22px]" : "translate-x-0.5"
                  )} />
                </button>
              </div>
            </div>

            {/* 1.5. 기준 국가 (KScore 개인화) */}
            <div className="p-4 border-b border-border" data-tour="settings-home-country">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{t(lang, "settings_home_country")}</p>
                  <p className="text-[10px] text-muted-foreground">{t(lang, "settings_home_country_desc")}</p>
                </div>
                {plan === "free" ? (
                  <span className="text-sm text-muted-foreground">{t(lang, "settings_home_country_global")}</span>
                ) : (
                  <button
                    onClick={() => setShowHomeCountryPicker(true)}
                    className="flex items-center gap-1.5 text-sm bg-secondary border border-border rounded-md px-3 py-1.5 hover:bg-secondary/80 transition-colors"
                  >
                    <span>{homeCountry ? getFlag(homeCountry) : "🌐"}</span>
                    <span>{homeCountry ? getCountryName(homeCountry, lang) : (lang === "ko" ? "글로벌" : "Global")}</span>
                    <ChevronDown className="h-3 w-3 text-muted-foreground" />
                  </button>
                )}
              </div>
              {plan === "free" && (
                <p className="text-[9px] text-muted-foreground mt-1">{t(lang, "settings_home_country_pro_hint")}</p>
              )}
            </div>

            {/* 2. KScore 슬라이더 */}
            <div className={cn("p-4", !hasFCMToken && "opacity-50 pointer-events-none")} data-tour="settings-kscore-slider">
              <div className="flex items-center justify-between mb-1">
                <div>
                  <p className="text-sm font-medium">{t(lang, "notif_kscore_title")}</p>
                  <p className="text-[10px] text-muted-foreground">{t(lang, "notif_kscore_desc")}</p>
                </div>
                <span className="text-sm font-mono font-bold tabular-nums ml-3">
                  {kscoreValue.toFixed(1)}
                </span>
              </div>
              {!hasFCMToken ? (
                <p className="mt-2 text-[10px] text-muted-foreground">
                  {t(lang, "settings_push_off_hint")}
                </p>
              ) : plan === "free" ? (
                <div
                  className="mt-2 flex items-center gap-2 cursor-pointer group"
                  onClick={() => kscorePaywall.show()}
                >
                  <div className="flex-1 relative">
                    <div className="h-2 rounded-full bg-muted" />
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Lock className="h-3 w-3 text-muted-foreground group-hover:text-primary transition-colors" />
                    </div>
                  </div>
                  <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                    {t(lang, "notif_kscore_free_hint")}
                  </span>
                </div>
              ) : (
                <div className="mt-2 space-y-1">
                  <input
                    type="range"
                    min={plan === "pro_plus" ? 1.5 : plan === "pro" ? 3.0 : 4.0}
                    max={10.0}
                    step={0.5}
                    value={kscoreValue}
                    onChange={(e) => setKscoreValue(parseFloat(e.target.value))}
                    onMouseUp={handleSaveKscore}
                    onTouchEnd={handleSaveKscore}
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-[9px] text-muted-foreground">
                    <span>{plan === "pro_plus" ? "1.5" : plan === "pro" ? "3.0" : "4.0"} · {t(lang, "notif_kscore_low")}</span>
                    <span>10.0 · {t(lang, "notif_kscore_high")}</span>
                  </div>
                </div>
              )}
            </div>

            {/* 3. 토픽 필터 (Pro / Pro+) */}
            <div className={cn("p-4", (plan === "free" || !hasFCMToken) && "opacity-50 pointer-events-none")}>
              <div className="flex items-center justify-between mb-2">
                <div>
                  <p className="text-sm font-medium">{t(lang, "notif_topics_title")}</p>
                  <p className="text-[10px] text-muted-foreground">{t(lang, "notif_topics_desc")}</p>
                </div>
                {plan === "free" && (
                  <Link href="/upgrade" className="rounded-full bg-primary/10 border border-primary/30 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 transition-colors pointer-events-auto">
                    Pro →
                  </Link>
                )}
              </div>
              {!hasFCMToken ? (
                <p className="mt-1 text-[10px] text-muted-foreground">{t(lang, "settings_push_off_hint")}</p>
              ) : plan === "free" ? (
                <Link href="/upgrade" className="mt-2 flex items-center gap-1.5 text-[11px] text-primary/80 hover:text-primary pointer-events-auto">
                  <span>🔓</span>
                  <span>{t(lang, "settings_unlock_topics")}</span>
                </Link>
              ) : null}
              {plan !== "free" ? (
                <>
                  <div className="flex gap-3 mb-2">
                    <button
                      onClick={() => handleSetAllTopics(TOPICS)}
                      className="text-[10px] text-primary hover:underline"
                    >
                      {t(lang, "notif_topics_all")}
                    </button>
                    <span className="text-[10px] text-muted-foreground">·</span>
                    <button
                      onClick={() => handleSetAllTopics([])}
                      className="text-[10px] text-muted-foreground hover:underline"
                    >
                      {t(lang, "notif_topics_none")}
                    </button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5">
                    {TOPICS.map((topic) => (
                      <button
                        key={topic}
                        onClick={() => handleToggleTopic(topic)}
                        className={cn(
                          "rounded-lg border px-2 py-1.5 text-xs transition-colors",
                          selectedTopics.includes(topic)
                            ? "border-primary bg-primary/10 text-primary"
                            : "border-border text-muted-foreground hover:border-muted-foreground"
                        )}
                      >
                        {TOPIC_LABELS[topic]?.[lang === "ko" ? "ko" : "en"] ?? topic}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 mt-1">
                  {TOPICS.map((topic) => (
                    <span key={topic} className="rounded-lg border border-border px-2 py-1 text-[10px] text-muted-foreground text-center">
                      {TOPIC_LABELS[topic]?.[lang === "ko" ? "ko" : "en"] ?? topic}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* 4. 방해금지 시간 (Pro / Pro+) */}
            <div className={cn("p-4", (plan === "free" || !hasFCMToken) && "opacity-50 pointer-events-none")}>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{t(lang, "notif_quiet_title")}</p>
                  <p className="text-[10px] text-muted-foreground">{t(lang, "notif_quiet_desc")}</p>
                </div>
                {!hasFCMToken ? null : plan === "free" ? (
                  <Link href="/upgrade" className="rounded-full bg-primary/10 border border-primary/30 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 transition-colors pointer-events-auto">
                    Pro →
                  </Link>
                ) : (
                  <button
                    onClick={() => {
                      const next = !quietEnabled;
                      setQuietEnabled(next);
                      if (next) {
                        saveNotifPatch({ quiet_hours_start: quietStart || "23:00", quiet_hours_end: quietEnd || "07:00" });
                      } else {
                        saveNotifPatch({ quiet_hours_start: "", quiet_hours_end: "" });
                      }
                    }}
                    className={cn(
                      "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
                      quietEnabled ? "bg-primary" : "bg-secondary"
                    )}
                  >
                    <span className={cn(
                      "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform",
                      quietEnabled ? "translate-x-5" : "translate-x-0"
                    )} />
                  </button>
                )}
              </div>
              {!hasFCMToken ? (
                <p className="mt-2 text-[10px] text-muted-foreground">{t(lang, "settings_push_off_hint")}</p>
              ) : plan === "free" ? (
                <Link href="/upgrade" className="mt-2 flex items-center gap-1.5 text-[11px] text-primary/80 hover:text-primary pointer-events-auto">
                  <span>🔓</span>
                  <span>{t(lang, "settings_unlock_quiet")}</span>
                </Link>
              ) : null}
              {plan !== "free" && hasFCMToken && quietEnabled && (
                <div className="flex items-center gap-2 mt-3">
                  <div className="flex-1 flex items-center gap-1">
                    <span className="text-[10px] text-muted-foreground">{t(lang, "notif_quiet_from")}</span>
                    <input
                      type="time"
                      value={quietStart}
                      onChange={(e) => {
                        setQuietStart(e.target.value);
                        handleSaveQuietHours(e.target.value, quietEnd);
                      }}
                      className="flex-1 rounded-lg border border-border bg-background px-2 py-1.5 text-sm min-w-0"
                    />
                  </div>
                  <span className="text-muted-foreground">·</span>
                  <div className="flex-1 flex items-center gap-1">
                    <span className="text-[10px] text-muted-foreground">{t(lang, "notif_quiet_to")}</span>
                    <input
                      type="time"
                      value={quietEnd}
                      onChange={(e) => {
                        setQuietEnd(e.target.value);
                        handleSaveQuietHours(quietStart, e.target.value);
                      }}
                      className="flex-1 rounded-lg border border-border bg-background px-2 py-1.5 text-sm min-w-0"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* 5. 마케팅 수신 동의 */}
            <div className="p-4 border-t border-border" data-tour="settings-marketing-email">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{t(lang, "settings_marketing_toggle")}</p>
                  <p className="text-[10px] text-muted-foreground">{t(lang, "settings_marketing_desc")}</p>
                  {!me?.marketing_agreed_at && (
                    <p className="text-[10px] text-blue-400 mt-0.5">{t(lang, "marketing_newsletter_benefit")}</p>
                  )}
                </div>
                <button
                  disabled={patchProfile.isPending}
                  onClick={() => {
                    const turningOn = !me?.marketing_agreed_at;
                    const value = turningOn ? "now" : "";
                    patchProfile.mutate({ marketing_agreed_at: value }, {
                      onSuccess: () => {
                        if (turningOn) {
                          showToast(lang === "ko"
                            ? "마케팅 수신에 동의하였습니다"
                            : "Marketing consent agreed", "success");
                        } else {
                          showToast(lang === "ko"
                            ? "마케팅 수신을 거부하였습니다"
                            : "Marketing consent withdrawn", "info");
                        }
                      },
                    });
                  }}
                  className={cn(
                    "relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors",
                    me?.marketing_agreed_at ? "bg-primary" : "bg-secondary",
                    patchProfile.isPending && "opacity-50"
                  )}
                >
                  <span className={cn(
                    "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform",
                    me?.marketing_agreed_at ? "translate-x-5" : "translate-x-0"
                  )} />
                </button>
              </div>
            </div>

          </div>
        </section>}

        {/* ── 플랜 ──────────────────────────────────────────────────── */}
        <section data-tour="settings-plan">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {t(lang, "settings_plan")}
          </h2>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2">
              {plan === "pro_plus" ? (
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-sm">
                  Pro+
                </span>
              ) : plan === "pro" ? (
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold bg-gradient-to-r from-blue-500 to-cyan-400 text-white shadow-sm">
                  Pro
                </span>
              ) : (
                <span className="inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-bold bg-muted text-muted-foreground">
                  Free
                </span>
              )}
              {/* 체험판/유료 뱃지 */}
              {plan !== "free" && subInfo.status === "trial" && (
                <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
                  {t(lang, "trial_badge")}
                </span>
              )}
              {plan !== "free" && subInfo.status === "active" && (
                <span className="rounded-full bg-green-500/15 border border-green-500/30 px-2 py-0.5 text-[10px] font-semibold text-green-400">
                  {t(lang, "settings_plan_status_active")}
                </span>
              )}
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {plan === "pro_plus" ? t(lang, "settings_plan_proplus_desc") :
               plan === "pro" ? t(lang, "settings_plan_pro_desc") :
               t(lang, "settings_plan_free_desc", { n: FREE_COUNTRY_LIMIT })}
            </p>

            {/* 체험판 정보 */}
            {plan !== "free" && subInfo.status === "trial" && subInfo.trial_end && (
              <div className="mt-3 space-y-1.5 rounded-lg bg-amber-500/5 border border-amber-500/20 px-3 py-2.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">{t(lang, "trial_expires_label")}</span>
                  <span className="font-medium text-amber-400">
                    {new Date(subInfo.trial_end).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR")}
                  </span>
                </div>
                {(() => {
                  const daysLeft = Math.max(0, Math.ceil((new Date(subInfo.trial_end!).getTime() - Date.now()) / (1000 * 60 * 60 * 24)));
                  return (
                    <>
                      <p className="text-[10px] font-semibold text-amber-400">
                        {t(lang, "trial_remaining_days", { n: daysLeft })}
                      </p>
                      <div className="h-1.5 rounded-full bg-amber-500/20 overflow-hidden">
                        <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500"
                             style={{ width: `${Math.max(5, ((7 - daysLeft) / 7) * 100)}%` }} />
                      </div>
                    </>
                  );
                })()}
                <p className="text-[10px] text-muted-foreground">{t(lang, "trial_upgrade_prompt")}</p>
                <p className="text-[10px] text-green-500">
                  {lang === "ko" ? "연간 구독 시 $5.25/월 (25% 할인)" : "Annual: $5.25/mo (25% off)"}
                </p>
                <Link href="/upgrade" className="mt-1 block w-full rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 py-2 text-center text-xs font-bold text-white">
                  {lang === "ko" ? "지금 Pro 구독하기 · $6.99/월" : "Subscribe Pro · $6.99/mo"}
                </Link>
              </div>
            )}

            {/* 유료 구독 결제 정보 */}
            {plan !== "free" && subInfo.status !== "trial" && subInfo.started_at && (
              <div className="mt-3 space-y-1 rounded-lg bg-muted/30 px-3 py-2.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">{t(lang, "settings_plan_started")}</span>
                  <span className="font-medium">
                    {new Date(subInfo.started_at).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR")}
                  </span>
                </div>
                {subInfo.next_billing_at && (
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">{t(lang, "settings_plan_next_billing")}</span>
                    <span className="font-medium">
                      {new Date(subInfo.next_billing_at).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR")}
                    </span>
                  </div>
                )}
                {!subInfo.next_billing_at && subInfo.expires_at && (
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-muted-foreground">{t(lang, "settings_plan_expires")}</span>
                    <span className="font-medium">
                      {new Date(subInfo.expires_at).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR")}
                    </span>
                  </div>
                )}
                {subInfo.auto_renewing === false && (
                  <p className="text-[10px] text-amber-400 mt-1">{t(lang, "settings_plan_not_renewing")}</p>
                )}
              </div>
            )}

            {/* Free 플랜 잠긴 기능 목록 */}
            {plan === "free" && (
              <div className="mt-3 space-y-1.5">
                <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                  {t(lang, "settings_unlock_pro")}
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    { icon: "✅", ko: "신뢰 알림", en: "Verified alerts" },
                    { icon: "📊", ko: "KScore 조정", en: "KScore adjust" },
                    { icon: "🔕", ko: "방해금지 시간", en: "Quiet hours" },
                    { icon: "📍", ko: `관심 국가 ${PRO_COUNTRY_LIMIT}개`, en: `${PRO_COUNTRY_LIMIT} countries` },
                    { icon: "🛰️", ko: "인텔리전스 레이어", en: "Intel layers" },
                    { icon: "🔗", ko: "교차검증 상세", en: "Cross-verification" },
                  ].map((f) => (
                    <span key={f.ko} className="flex items-center gap-1 rounded-full bg-primary/8 border border-primary/20 px-2 py-0.5 text-[10px] text-primary/80">
                      <span>{f.icon}</span>
                      <span>{lang === "ko" ? f.ko : f.en}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* 플랜 변경/업그레이드 버튼 */}
            {plan === "free" && (
              <Link href="/upgrade" className="mt-3 block w-full rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 py-2.5 text-center text-sm font-bold text-white">
                {t(lang, "settings_upgrade_btn")}
              </Link>
            )}
            {plan !== "free" && (
              <Link href="/upgrade" className="mt-3 block w-full rounded-lg border border-border py-2.5 text-center text-sm font-medium text-foreground hover:bg-muted/30 transition-colors">
                {t(lang, "settings_plan_change")}
              </Link>
            )}

            {/* 스토어 구독 관리 링크 */}
            {plan !== "free" && subPlatform === "android" && (
              <a
                href="https://play.google.com/store/account/subscriptions"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-primary hover:underline"
              >
                <svg viewBox="0 0 24 24" className="h-3 w-3 fill-current shrink-0"><path d="M3.609 1.814L13.792 12 3.61 22.186a.996.996 0 01-.61-.92V2.734a1 1 0 01.609-.92zm10.89 10.893l2.302 2.302-10.937 6.333 8.635-8.635zm3.199-3.199l2.807 1.626a1 1 0 010 1.732l-2.807 1.626L15.206 12l2.492-2.492zM5.864 3.458L16.8 9.79l-2.302 2.302-8.635-8.635z"/></svg>
                {t(lang, "store_manage_google")}
              </a>
            )}
            {plan !== "free" && subPlatform === "ios" && (
              <a
                href="https://apps.apple.com/account/subscriptions"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-primary hover:underline"
              >
                <svg viewBox="0 0 24 24" className="h-3 w-3 fill-current shrink-0"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
                {t(lang, "store_manage_apple")}
              </a>
            )}
          </div>
        </section>

        {/* ── 친구 초대 ──────────────────────────────────────────────── */}
        {me && (
          <section>
            <a
              href="/settings/referral"
              className="flex items-center gap-3 rounded-xl border border-primary/30 bg-primary/5 p-4 hover:bg-primary/10 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                <Gift className="h-5 w-5 text-primary" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium">{t(lang, "referral_title")}</p>
                <p className="text-[11px] text-muted-foreground">{t(lang, "referral_subtitle")}</p>
              </div>
              <span className="text-primary text-xs">→</span>
            </a>
          </section>
        )}

        {/* ── 소셜 채널 ─────────────────────────────────────────────── */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {lang === "ko" ? "공식 채널" : "Official Channels"}
          </h2>
          <div className="rounded-xl border border-border bg-card divide-y divide-border">
            <a
              href="https://t.me/wewantpeace_live"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
            >
              <Send className="h-4 w-4 text-[#26A5E4] shrink-0" />
              <div className="flex-1">
                <p>Telegram</p>
                <p className="text-[11px] text-muted-foreground">
                  {lang === "ko" ? "실시간 속보 · 글로벌 분쟁 알림" : "Breaking news · Global conflict alerts"}
                </p>
              </div>
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </a>
            <a
              href="https://x.com/WeWantPeaceNews"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
            >
              <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
              <div className="flex-1">
                <p>X (Twitter)</p>
                <p className="text-[11px] text-muted-foreground">@WeWantPeaceNews</p>
              </div>
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </a>
            <a
              href="https://www.threads.com/@wewantpeace_news?igshid=NTc4MTIwNjQ2YQ=="
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
            >
              <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24" fill="currentColor"><path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.59 12c.025 3.086.718 5.496 2.057 7.164 1.432 1.784 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.284 3.272-.886 1.102-2.14 1.704-3.73 1.79-1.202.065-2.361-.218-3.259-.801-1.063-.689-1.685-1.74-1.752-2.96-.065-1.178.408-2.265 1.328-3.059.88-.76 2.099-1.198 3.43-1.234 1.158-.03 2.203.143 3.126.519.014-.467-.003-.93-.055-1.384-.266-2.33-1.58-3.507-3.905-3.507-1.258 0-2.328.423-3.088 1.11l-1.373-1.607C8.39 3.778 9.932 3.15 11.93 3.15c1.736 0 3.16.482 4.112 1.392 1.007.963 1.567 2.376 1.663 4.2.028.053.042.108.05.164.293.146.567.312.82.494 1.14.82 1.99 1.86 2.456 3.015.766 1.9.366 4.572-1.66 6.577C17.605 20.675 15.41 21.5 12.186 24zm-.09-8.71c-.94.025-1.735.249-2.296.646-.538.381-.795.876-.766 1.472.026.533.318 1.013.822 1.34.585.378 1.382.563 2.243.52 1.07-.058 1.89-.455 2.44-1.18.453-.596.739-1.391.86-2.369-.695-.309-1.489-.464-2.358-.464-.317 0-.634.012-.945.035z"/></svg>
              <div className="flex-1">
                <p>Threads</p>
                <p className="text-[11px] text-muted-foreground">@wewantpeace_news</p>
              </div>
              <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
            </a>
          </div>
        </section>

        {/* ── 고객센터 ──────────────────────────────────────────────── */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {t(lang, "settings_support")}
          </h2>
          <div className="rounded-xl border border-border bg-card divide-y divide-border">
            <a
              href="/settings/glossary"
              className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
            >
              <BookOpen className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1">
                <p>{t(lang, "settings_glossary")}</p>
                <p className="text-[11px] text-muted-foreground">{t(lang, "settings_glossary_sub")}</p>
              </div>
              <span className="text-muted-foreground text-xs">→</span>
            </a>
            <a
              href={`mailto:${CONTACT_EMAIL}`}
              className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
            >
              <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1">
                <p>{t(lang, "settings_support_email")}</p>
                <p className="text-[11px] text-muted-foreground">{CONTACT_EMAIL}</p>
              </div>
              <span className="text-muted-foreground text-xs">→</span>
            </a>
            {firebaseUser ? (
              <button
                onClick={() => { setShowFeedback(true); setFeedbackSent(false); setFeedbackError(null); }}
                className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50 w-full text-left"
              >
                <MessageCircleQuestion className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="flex-1">{t(lang, "settings_support_feedback")}</span>
                <span className="text-muted-foreground text-xs">→</span>
              </button>
            ) : (
              <a
                href={`mailto:${CONTACT_EMAIL}?subject=${lang === "ko" ? "WeWantPeace%20의견" : "WeWantPeace%20Feedback"}`}
                className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
              >
                <MessageCircleQuestion className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="flex-1">{t(lang, "settings_support_feedback")}</span>
                <span className="text-muted-foreground text-xs">→</span>
              </a>
            )}
            <a
              href="/api-docs"
              className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
            >
              <Code className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1">
                <p>{t(lang, "api_docs_developers")}</p>
                <p className="text-[11px] text-muted-foreground">{t(lang, "api_docs_developers_desc")}</p>
              </div>
              <span className="text-muted-foreground text-xs">→</span>
            </a>
          </div>
        </section>

        {/* ── 계정 ──────────────────────────────────────────────────── */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {t(lang, "settings_account")}
          </h2>
          <div className="rounded-xl border border-border bg-card divide-y divide-border">
            {showProfileEdit ? (
              <div className="p-4 space-y-3">
                <p className="text-sm font-semibold">{t(lang, "settings_profile_edit")}</p>
                {profileError && <p className="text-xs text-destructive">{profileError}</p>}
                <div>
                  <label className="text-[11px] text-muted-foreground">{t(lang, "settings_nickname")}</label>
                  <input
                    type="text"
                    value={editNickname}
                    onChange={(e) => setEditNickname(e.target.value)}
                    maxLength={20}
                    className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-muted-foreground">{t(lang, "settings_bio")}</label>
                  <textarea
                    value={editBio}
                    onChange={(e) => setEditBio(e.target.value)}
                    maxLength={200}
                    rows={3}
                    placeholder={t(lang, "settings_bio_placeholder")}
                    className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary resize-none"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleProfileSave}
                    disabled={profileSaving || !editNickname.trim()}
                    className="flex-1 rounded-lg bg-primary py-2 text-sm font-medium text-primary-foreground disabled:opacity-50 flex items-center justify-center gap-1"
                  >
                    {profileSaving && <span className="h-3 w-3 rounded-full border-2 border-white border-t-transparent animate-spin" />}
                    {t(lang, "settings_save")}
                  </button>
                  <button onClick={() => setShowProfileEdit(false)} className="flex-1 rounded-lg border border-border py-2 text-sm text-muted-foreground">
                    {t(lang, "settings_cancel")}
                  </button>
                </div>
              </div>
            ) : (
              <button onClick={openProfileEdit} className="flex items-center justify-between px-4 py-3 text-sm w-full text-left hover:bg-secondary/50">
                <span>{t(lang, "settings_profile_edit")}</span>
                <span className="text-muted-foreground text-xs">→</span>
              </button>
            )}
            <Link href="/community" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary/50">
              <div>
                <span>{t(lang, "settings_community")}</span>
                <p className="text-[10px] text-muted-foreground mt-0.5">{t(lang, "settings_community_desc")}</p>
              </div>
              <span className="text-muted-foreground text-xs">→</span>
            </Link>
            <Link href="/community/my" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary/50">
              <span>{t(lang, "settings_my_posts")}</span>
              <span className="text-muted-foreground text-xs">→</span>
            </Link>
            <Link href="/terms" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary/50">
              <span>{t(lang, "settings_terms")}</span>
              <span className="text-muted-foreground text-xs">→</span>
            </Link>
            <Link href="/privacy" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary/50">
              <span>{t(lang, "settings_privacy")}</span>
              <span className="text-muted-foreground text-xs">→</span>
            </Link>
          </div>
        </section>

        {/* ── 하단: 탈퇴 + 버전 ────────────────────────────────── */}
        <section className="pb-8">
          {firebaseUser && (
            <p
              className="text-center text-[10px] text-muted-foreground/30 mb-3 cursor-pointer hover:text-muted-foreground/50 transition-colors"
              onClick={() => setDeleteStep(1)}
            >
              {t(lang, "settings_delete_account")}
            </p>
          )}
          <p className="text-center text-[10px] text-muted-foreground/20 select-none">
            WeWantPeace v2.0
          </p>

          {/* ── PaywallModal들 ──────────────────────────────────────── */}
          <PaywallModal trigger="verified_locked" isOpen={verifiedPaywall.isOpen} onClose={verifiedPaywall.close} />
          <PaywallModal trigger="kscore_threshold_locked" isOpen={kscorePaywall.isOpen} onClose={kscorePaywall.close} />
          <PaywallModal trigger="watch_country_limit_locked" isOpen={watchCountryPaywall.isOpen} onClose={watchCountryPaywall.close} />

          {/* 피드백 모달 */}
          {showFeedback && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={() => setShowFeedback(false)}>
              <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
                {feedbackSent ? (
                  <>
                    <div className="flex flex-col items-center gap-3 py-4">
                      <CheckCircle className="h-10 w-10 text-green-500" />
                      <p className="text-sm font-semibold">{t(lang, "feedback_sent_title")}</p>
                      <p className="text-[12px] text-muted-foreground text-center">{t(lang, "feedback_sent_desc")}</p>
                    </div>
                    <button
                      onClick={() => setShowFeedback(false)}
                      className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground"
                    >
                      {t(lang, "settings_close")}
                    </button>
                  </>
                ) : (
                  <>
                    <p className="text-sm font-semibold">{t(lang, "feedback_title")}</p>
                    <p className="text-[12px] text-muted-foreground">{t(lang, "feedback_desc")}</p>
                    {feedbackError && <p className="text-xs text-destructive">{feedbackError}</p>}
                    <textarea
                      value={feedbackMsg}
                      onChange={(e) => setFeedbackMsg(e.target.value)}
                      maxLength={2000}
                      rows={5}
                      placeholder={t(lang, "feedback_placeholder")}
                      autoFocus
                      className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm outline-none focus:border-primary resize-none"
                    />
                    <p className="text-[10px] text-muted-foreground text-right">{feedbackMsg.length}/2000</p>
                    <div className="flex gap-2">
                      <button
                        onClick={handleSubmitFeedback}
                        disabled={feedbackSending || feedbackMsg.trim().length < 5}
                        className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 flex items-center justify-center gap-1.5"
                      >
                        {feedbackSending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                        {t(lang, "feedback_submit")}
                      </button>
                      <button
                        onClick={() => setShowFeedback(false)}
                        className="flex-1 rounded-lg border border-border py-2.5 text-sm text-muted-foreground"
                      >
                        {t(lang, "settings_cancel")}
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          {/* 탈퇴 확인 다이얼로그 */}
          {firebaseUser && deleteStep === 1 && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={() => { setDeleteStep(0); setDeleteInput(""); }}>
              <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
                <p className="text-sm font-semibold text-destructive">{t(lang, "settings_delete_account")}</p>
                <p className="text-[13px] text-muted-foreground whitespace-pre-line">{t(lang, "settings_delete_confirm")}</p>
                <div>
                  <label className="text-[11px] text-muted-foreground mb-1 block">
                    {lang === "en"
                      ? 'Type "delete" to confirm'
                      : '"탈퇴합니다"를 입력해주세요'}
                  </label>
                  <input
                    type="text"
                    value={deleteInput}
                    onChange={(e) => setDeleteInput(e.target.value)}
                    placeholder={lang === "en" ? "delete" : "탈퇴합니다"}
                    autoFocus
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-destructive"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleDeleteAccount}
                    disabled={deleteLoading || (lang === "en" ? deleteInput !== "delete" : deleteInput !== "탈퇴합니다")}
                    className="flex-1 rounded-lg bg-destructive py-2.5 text-sm font-medium text-destructive-foreground disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-1"
                  >
                    {deleteLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                    {t(lang, "settings_delete_account")}
                  </button>
                  <button
                    onClick={() => { setDeleteStep(0); setDeleteInput(""); }}
                    className="flex-1 rounded-lg border border-border py-2.5 text-sm text-muted-foreground"
                  >
                    {t(lang, "settings_cancel")}
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* 토스트 알림 */}
        {/* ═══════════════ 기준 국가 선택 바텀시트 ═══════════════ */}
        {showHomeCountryPicker && (
          <>
            <div className="fixed inset-0 z-50 bg-black/40" onClick={() => setShowHomeCountryPicker(false)} />
            <div className="fixed bottom-[60px] left-0 right-0 z-50 rounded-t-2xl border-t border-border bg-card shadow-2xl animate-in slide-in-from-bottom duration-200 max-w-lg mx-auto max-h-[60vh] flex flex-col">
              <div className="flex items-center justify-between px-5 py-3 border-b border-border shrink-0">
                <h3 className="text-sm font-bold">
                  {lang === "ko" ? "기준 국가 선택" : "Select Base Country"}
                </h3>
                <button
                  onClick={() => setShowHomeCountryPicker(false)}
                  className="p-1 rounded-full hover:bg-muted/50 transition-colors"
                >
                  <X className="h-4 w-4 text-muted-foreground" />
                </button>
              </div>
              <div className="overflow-y-auto flex-1 py-2 overscroll-contain">
                {/* 글로벌 옵션 */}
                <button
                  onClick={() => {
                    setHomeCountry("");
                    saveNotifPatch({ home_country: "" });
                    setShowHomeCountryPicker(false);
                  }}
                  className={cn(
                    "w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-muted/10 transition-colors",
                    !homeCountry && "bg-primary/5"
                  )}
                >
                  <span className="text-lg">🌐</span>
                  <span className="text-sm flex-1">{lang === "ko" ? "글로벌 (전체)" : "Global (All)"}</span>
                  <span className="text-[10px] text-muted-foreground">ALL</span>
                  {!homeCountry && <Check className="h-4 w-4 text-primary" />}
                </button>
                {/* 대륙별 그룹 */}
                {([
                  { label: lang === "ko" ? "동아시아" : "East Asia", codes: ["KR", "JP", "CN", "TW"] },
                  { label: lang === "ko" ? "동남아 · 오세아니아" : "SE Asia · Oceania", codes: ["TH", "VN", "SG", "ID", "PH", "AU"] },
                  { label: lang === "ko" ? "남아시아 · 중동" : "South Asia · Middle East", codes: ["IN", "SA", "AE", "IL", "EG", "TR"] },
                  { label: lang === "ko" ? "유럽" : "Europe", codes: ["DE", "GB", "FR", "PL", "RU"] },
                  { label: lang === "ko" ? "아메리카" : "Americas", codes: ["US", "CA", "MX", "BR"] },
                ] as { label: string; codes: string[] }[]).map((group) => {
                  const groupCountries = group.codes.filter((c) => SUPPORTED_HOME_COUNTRIES.includes(c));
                  if (!groupCountries.length) return null;
                  return (
                    <div key={group.label}>
                      <div className="px-5 pt-3 pb-1">
                        <span className="text-[10px] font-semibold text-muted-foreground/60 uppercase tracking-wider">{group.label}</span>
                      </div>
                      {groupCountries.map((cc) => (
                        <button
                          key={cc}
                          onClick={() => {
                            setHomeCountry(cc);
                            saveNotifPatch({ home_country: cc });
                            setShowHomeCountryPicker(false);
                          }}
                          className={cn(
                            "w-full flex items-center gap-3 px-5 py-2.5 text-left hover:bg-muted/10 transition-colors",
                            homeCountry === cc && "bg-primary/5"
                          )}
                        >
                          <span className="text-lg">{getFlag(cc)}</span>
                          <span className="text-sm flex-1">{getCountryName(cc, lang)}</span>
                          <span className="text-[10px] text-muted-foreground">{cc}</span>
                          {homeCountry === cc && <Check className="h-4 w-4 text-primary" />}
                        </button>
                      ))}
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {toast && (
          <div className="fixed bottom-20 inset-x-4 z-50 flex justify-center animate-in slide-in-from-bottom-4 fade-in duration-300">
            <div className={cn(
              "flex items-center gap-2.5 rounded-2xl px-5 py-3 shadow-2xl backdrop-blur-sm whitespace-nowrap",
              toast.type === "success"
                ? "bg-emerald-500/90 text-white"
                : "bg-zinc-700/90 text-zinc-100"
            )}>
              {toast.type === "success" ? (
                <CheckCircle className="h-4 w-4 shrink-0" />
              ) : (
                <Mail className="h-4 w-4 shrink-0 opacity-80" />
              )}
              <span className="text-[13px] font-medium">{toast.msg}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

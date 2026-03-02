"use client";

import { useState, useEffect } from "react";
import { MapPin, Shield, Plus, X, Search, ChevronUp, LogOut, LogIn, User, Loader2, Trash2, Sun, Moon, Mail, MessageCircleQuestion, Send, CheckCircle, BookOpen, Lock, Gift } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAppStore, FREE_COUNTRY_LIMIT, PRO_COUNTRY_LIMIT, type Theme } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { useMe, usePatchPreferences, useMyPreferences, useMyAreas, useAddArea, useDeleteArea, usePatchArea, useRegisterPushToken, useDeletePushToken, API_BASE } from "@/lib/api";
import { requestAndGetFCMToken, getStoredFCMToken, clearStoredFCMToken, isPushSupported } from "@/lib/fcm";
import { ALL_COUNTRIES, getCountryName, getRegionName } from "@/lib/countries";
import { useAuth, signOut } from "@/lib/auth";
import { LogoIcon } from "@/components/ui/logo-icon";
import { useRouter } from "next/navigation";
import { ExternalLink } from "lucide-react";
import { PaywallModal, usePaywall } from "@/components/ui/PaywallModal";

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
  const { myCountries, addMyCountry, removeMyCountry, userPlan, lang, setLang, setUserPlan, theme } = useAppStore();
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
  const [notifStatus, setNotifStatus] = useState<"idle" | "loading" | "done" | "denied" | "unsupported">("idle");
  const [openInfo, setOpenInfo] = useState<string | null>(null); // "verified-KR" | "fast-KR" 형태

  // 알림 설정 로컬 상태
  const [kscoreValue, setKscoreValue] = useState(3.0);
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [quietEnabled, setQuietEnabled] = useState(false);
  const [quietStart, setQuietStart] = useState("23:00");
  const [quietEnd, setQuietEnd] = useState("07:00");
  // notifSaving/notifSaved 제거 — 자동 저장

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
  const fastPaywall = usePaywall("fast_locked");
  const kscorePaywall = usePaywall("kscore_threshold_locked");
  const watchCountryPaywall = usePaywall("watch_country_limit_locked");

  // 피드백 모달
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState("");
  const [feedbackSending, setFeedbackSending] = useState(false);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

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
            });
          }
        })
        .catch(() => {});
    });
  }, [firebaseUser, API_BASE]);

  async function handleSignOut() {
    await signOut();
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
          : typeof detail === "string" ? detail : "저장에 실패했습니다."
        );
      }
      setProfileSuccess(true);
      setShowProfileEdit(false);
    } catch (e: unknown) {
      const err = e as { message?: string };
      setProfileError(err.message || "저장에 실패했습니다.");
    } finally {
      setProfileSaving(false);
    }
  }

  // prefs 로드 시 알림 상태 동기화
  useEffect(() => {
    if (prefs) {
      setKscoreValue(prefs.min_kscore ?? 3.0);
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
    saveNotifPatch({ topics: next });
  }

  function handleSetAllTopics(topics: string[]) {
    setSelectedTopics(topics);
    saveNotifPatch({ topics });
  }

  function handleSaveQuietHours(start: string, end: string) {
    saveNotifPatch({ quiet_hours_start: start, quiet_hours_end: end });
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
      const isRN = typeof window !== "undefined" && !!window.__REACT_NATIVE__;
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
    <div className="flex flex-col">
      {/* 헤더 */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <div className="grid grid-cols-3 items-center mb-1">
          <div className="flex items-center min-w-0 overflow-hidden">
            <h1 className="text-sm font-bold truncate">{t(lang, "settings_title")}</h1>
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
                  <img src={firebaseUser.photoURL} alt="프로필" className="h-10 w-10 rounded-full object-cover" />
                ) : (
                  <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center">
                    <User className="h-5 w-5 text-primary" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold truncate">
                    {(me as { nickname?: string })?.nickname || firebaseUser.displayName || "사용자"}
                  </p>
                  <p className="text-[11px] text-muted-foreground truncate">{firebaseUser.email}</p>
                  <span className="inline-block mt-0.5 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                    {plan.toUpperCase()}
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
        <section>
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
                                <a href="/upgrade" className="text-[10px] text-primary hover:underline">
                                  {t(lang, "settings_area_upgrade_hint")}
                                </a>
                              </div>
                            )}
                            {area && !inactive ? (
                              <div className={cn("mt-2 space-y-1.5", !hasFCMToken && "opacity-40 pointer-events-none")}>
                                {!hasFCMToken && (
                                  <p className="text-[9px] text-muted-foreground">{t(lang, "settings_push_off_hint")}</p>
                                )}
                                {/* Verified 토글 */}
                                <div>
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={() => patchArea.mutate({ id: area.id, body: { notify_verified: !area.notify_verified } })}
                                      disabled={!hasFCMToken}
                                      className={cn(
                                        "h-4 w-7 rounded-full relative flex-shrink-0 transition-colors",
                                        !hasFCMToken ? "bg-muted cursor-not-allowed"
                                          : area.notify_verified ? "bg-green-500" : "bg-muted"
                                      )}
                                    >
                                      <div className={cn(
                                        "h-3 w-3 rounded-full bg-white absolute top-0.5 transition-transform",
                                        hasFCMToken && area.notify_verified ? "translate-x-3.5" : "translate-x-0.5"
                                      )} />
                                    </button>
                                    <span className={cn("text-[11px]", hasFCMToken && area.notify_verified ? "text-green-400" : "text-muted-foreground")}>
                                      {area.notify_verified
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

                                {/* Fast 토글 */}
                                <div>
                                  <div className="flex items-center gap-2">
                                    <button
                                      onClick={() => {
                                        if (plan === "free") {
                                          fastPaywall.show();
                                          return;
                                        }
                                        if (hasFCMToken) patchArea.mutate({ id: area.id, body: { notify_fast: !area.notify_fast } });
                                      }}
                                      disabled={!hasFCMToken && plan !== "free"}
                                      className={cn(
                                        "h-4 w-7 rounded-full relative flex-shrink-0 transition-colors",
                                        plan === "free" ? "bg-muted opacity-60 cursor-pointer"
                                          : !hasFCMToken ? "bg-muted opacity-40 cursor-not-allowed"
                                          : area.notify_fast ? "bg-orange-500" : "bg-muted"
                                      )}
                                    >
                                      <div className={cn(
                                        "h-3 w-3 rounded-full bg-white absolute top-0.5 transition-transform",
                                        area.notify_fast && plan !== "free" && hasFCMToken ? "translate-x-3.5" : "translate-x-0.5"
                                      )} />
                                    </button>
                                    <span className={cn(
                                      "text-[11px]",
                                      (plan === "free" || !hasFCMToken) ? "text-muted-foreground/40"
                                        : area.notify_fast ? "text-orange-400" : "text-muted-foreground"
                                    )}>
                                      {plan === "free"
                                        ? (t(lang, "settings_fast_pro_only"))
                                        : area.notify_fast
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
                onClick={() => setLang(l)}
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

        {/* ── 테마 설정 ─────────────────────────────────────────────── */}
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

        {/* ── 알림 설정 ─────────────────────────────────────────────── */}
        <section>
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

            {/* 2. KScore 슬라이더 */}
            <div className={cn("p-4", !hasFCMToken && "opacity-50 pointer-events-none")}>
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
                    min={plan === "pro_plus" ? 1.5 : 3.0}
                    max={10.0}
                    step={0.5}
                    value={kscoreValue}
                    onChange={(e) => setKscoreValue(parseFloat(e.target.value))}
                    onMouseUp={handleSaveKscore}
                    onTouchEnd={handleSaveKscore}
                    className="w-full accent-primary"
                  />
                  <div className="flex justify-between text-[9px] text-muted-foreground">
                    <span>{plan === "pro_plus" ? "1.5" : "3.0"} · {t(lang, "notif_kscore_low")}</span>
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
                  <a href="/upgrade" className="rounded-full bg-primary/10 border border-primary/30 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 transition-colors pointer-events-auto">
                    Pro →
                  </a>
                )}
              </div>
              {!hasFCMToken ? (
                <p className="mt-1 text-[10px] text-muted-foreground">{t(lang, "settings_push_off_hint")}</p>
              ) : plan === "free" ? (
                <a href="/upgrade" className="mt-2 flex items-center gap-1.5 text-[11px] text-primary/80 hover:text-primary pointer-events-auto">
                  <span>🔓</span>
                  <span>{t(lang, "settings_unlock_topics")}</span>
                </a>
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
                  <a href="/upgrade" className="rounded-full bg-primary/10 border border-primary/30 px-2 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 transition-colors pointer-events-auto">
                    Pro →
                  </a>
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
                <a href="/upgrade" className="mt-2 flex items-center gap-1.5 text-[11px] text-primary/80 hover:text-primary pointer-events-auto">
                  <span>🔓</span>
                  <span>{t(lang, "settings_unlock_quiet")}</span>
                </a>
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
                  <span className="text-muted-foreground">—</span>
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

          </div>
        </section>

        {/* ── 플랜 ──────────────────────────────────────────────────── */}
        <section>
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
            {t(lang, "settings_plan")}
          </h2>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2">
              <Shield className={cn(
                "h-4 w-4",
                plan === "pro_plus" ? "text-purple-400" :
                plan === "pro" ? "text-yellow-400" :
                "text-muted-foreground"
              )} />
              <p className="text-sm font-medium">
                {plan === "pro_plus" ? t(lang, "settings_plan_proplus") :
                 plan === "pro" ? t(lang, "settings_plan_pro") :
                 t(lang, "settings_plan_free")}
              </p>
            </div>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {plan === "pro_plus" ? t(lang, "settings_plan_proplus_desc") :
               plan === "pro" ? t(lang, "settings_plan_pro_desc") :
               t(lang, "settings_plan_free_desc", { n: FREE_COUNTRY_LIMIT })}
            </p>

            {/* 결제 정보 (유료 플랜) */}
            {plan !== "free" && subInfo.started_at && (
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
                    { icon: "🗺️", ko: "실시간 이슈 지도", en: "Real-time map" },
                    { icon: "⚡", ko: "속보 알림", en: "Fast alerts" },
                    { icon: "📊", ko: "KScore 필터", en: "KScore filter" },
                    { icon: "🔕", ko: "방해금지 시간", en: "Quiet hours" },
                    { icon: "📍", ko: `관심지역 ${PRO_COUNTRY_LIMIT}개`, en: `${PRO_COUNTRY_LIMIT} regions` },
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
              <a href="/upgrade" className="mt-3 block w-full rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 py-2.5 text-center text-sm font-bold text-white">
                {t(lang, "settings_upgrade_btn")}
              </a>
            )}
            {plan !== "free" && (
              <a href="/upgrade" className="mt-3 block w-full rounded-lg border border-border py-2.5 text-center text-sm font-medium text-foreground hover:bg-muted/30 transition-colors">
                {t(lang, "settings_plan_change")}
              </a>
            )}

            {/* 스토어 구독 관리 링크 */}
            {plan !== "free" && subPlatform === "android" && (
              <a
                href="https://play.google.com/store/account/subscriptions"
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex items-center justify-center gap-1.5 text-[11px] text-primary hover:underline"
              >
                <ExternalLink className="h-3 w-3" />
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
                <ExternalLink className="h-3 w-3" />
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
              href="mailto:krshin7@naver.com"
              className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
            >
              <Mail className="h-4 w-4 text-muted-foreground shrink-0" />
              <div className="flex-1">
                <p>{t(lang, "settings_support_email")}</p>
                <p className="text-[11px] text-muted-foreground">krshin7@naver.com</p>
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
                href="mailto:krshin7@naver.com?subject=WeWantPeace%20의견"
                className="flex items-center gap-3 px-4 py-3 text-sm hover:bg-secondary/50"
              >
                <MessageCircleQuestion className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="flex-1">{t(lang, "settings_support_feedback")}</span>
                <span className="text-muted-foreground text-xs">→</span>
              </a>
            )}
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
            <a href="/community/my" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary/50">
              <span>{t(lang, "settings_my_posts")}</span>
              <span className="text-muted-foreground text-xs">→</span>
            </a>
            <a href="/terms" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary/50">
              <span>{t(lang, "settings_terms")}</span>
              <span className="text-muted-foreground text-xs">→</span>
            </a>
            <a href="/privacy" className="flex items-center justify-between px-4 py-3 text-sm hover:bg-secondary/50">
              <span>{t(lang, "settings_privacy")}</span>
              <span className="text-muted-foreground text-xs">→</span>
            </a>
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
          <PaywallModal trigger="fast_locked" isOpen={fastPaywall.isOpen} onClose={fastPaywall.close} />
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
      </div>
    </div>
  );
}

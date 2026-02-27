"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { Eye, EyeOff, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  signInWithGoogle,
  signInWithEmail,
  createEmailUser,
  getFirebaseAuth,
} from "@/lib/auth";
import { fetchSignInMethodsForEmail } from "firebase/auth";
import type { User as FirebaseUser } from "firebase/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";
import { isTossMiniApp } from "@/lib/platform";

type Tab = "login" | "register" | "google-register";

const CURRENT_YEAR = new Date().getFullYear();
const MIN_BIRTH_YEAR = CURRENT_YEAR - 100;
const MAX_BIRTH_YEAR = CURRENT_YEAR - 14;

export default function LoginPage() {
  const router = useRouter();
  const lang = useAppStore((s) => s.lang);
  const [tab, setTab] = useState<Tab>("login");

  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [showLoginPw, setShowLoginPw] = useState(false);

  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regPasswordConfirm, setRegPasswordConfirm] = useState("");
  const [nickname, setNickname] = useState("");
  const [nicknameAvailable, setNicknameAvailable] = useState<boolean | null>(null);
  const [nicknameChecking, setNicknameChecking] = useState(false);
  const [birthYear, setBirthYear] = useState("");
  const [agreedTerms, setAgreedTerms] = useState(false);
  const [agreedPrivacy, setAgreedPrivacy] = useState(false);
  const [agreedMarketing, setAgreedMarketing] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [googleUser, setGoogleUser] = useState<FirebaseUser | null>(null);

  // 실시간 검증 상태
  const [emailStatus, setEmailStatus] = useState<"idle" | "checking" | "available" | "taken">("idle");
  const [pwValid, setPwValid] = useState<boolean | null>(null);
  const [pwMatch, setPwMatch] = useState<boolean | null>(null);
  const [birthYearError, setBirthYearError] = useState<string | null>(null);

  // Debounce refs
  const nickDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);
  const emailDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 이메일 중복 확인 (debounced)
  const checkEmailExists = useCallback(async (email: string) => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setEmailStatus("idle");
      return;
    }
    setEmailStatus("checking");
    try {
      const auth = getFirebaseAuth();
      if (!auth) { setEmailStatus("idle"); return; }
      const methods = await fetchSignInMethodsForEmail(auth, email);
      setEmailStatus(methods.length > 0 ? "taken" : "available");
    } catch {
      setEmailStatus("idle");
    }
  }, []);

  function handleRegEmailChange(email: string) {
    setRegEmail(email);
    setEmailStatus("idle");
    if (emailDebounce.current) clearTimeout(emailDebounce.current);
    emailDebounce.current = setTimeout(() => checkEmailExists(email), 600);
  }

  // 비밀번호 실시간 검증
  function handleRegPasswordChange(pw: string) {
    setRegPassword(pw);
    setPwValid(pw.length >= 8);
    if (regPasswordConfirm) setPwMatch(pw === regPasswordConfirm);
  }

  function handleRegPasswordConfirmChange(pw: string) {
    setRegPasswordConfirm(pw);
    setPwMatch(pw.length > 0 ? regPassword === pw : null);
  }

  // 생년도 실시간 검증
  function handleBirthYearChange(val: string) {
    setBirthYear(val);
    const year = parseInt(val);
    if (!val || isNaN(year)) {
      setBirthYearError(null);
    } else if (year > MAX_BIRTH_YEAR) {
      setBirthYearError(t(lang, "login_error_underage"));
    } else if (year < MIN_BIRTH_YEAR) {
      setBirthYearError(lang === "en" ? "Invalid birth year." : "유효하지 않은 생년도입니다.");
    } else {
      setBirthYearError(null);
    }
  }

  // 닉네임 중복 확인 (debounced, 자동)
  async function checkNickname(name: string) {
    if (!name || name.length < 2) {
      setNicknameAvailable(null);
      return;
    }
    setNicknameChecking(true);
    try {
      const res = await fetch(`${API_BASE}/auth/check-nickname?nickname=${encodeURIComponent(name)}`);
      const data = await res.json();
      setNicknameAvailable(data.available);
    } catch {
      setNicknameAvailable(null);
    } finally {
      setNicknameChecking(false);
    }
  }

  function handleNicknameChange(name: string) {
    setNickname(name);
    setNicknameAvailable(null);
    if (nickDebounce.current) clearTimeout(nickDebounce.current);
    if (name.length >= 2) {
      nickDebounce.current = setTimeout(() => checkNickname(name), 500);
    }
  }

  // cleanup debounce on unmount
  useEffect(() => {
    return () => {
      if (nickDebounce.current) clearTimeout(nickDebounce.current);
      if (emailDebounce.current) clearTimeout(emailDebounce.current);
    };
  }, []);

  async function handleGoogleLogin() {
    setLoading(true);
    setError(null);
    try {
      const user = await signInWithGoogle();
      const token = await user.getIdToken();
      const meRes = await fetch(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (meRes.ok) {
        localStorage.setItem("onboarding_done", "true");
        router.push("/home");
      } else {
        setGoogleUser(user);
        setTab("google-register");
      }
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || "Google login failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!agreedTerms || !agreedPrivacy) {
      setError(lang === "en" ? "You must agree to the required terms." : "필수 약관에 동의해야 합니다.");
      return;
    }
    const year = parseInt(birthYear);
    if (isNaN(year) || year < MIN_BIRTH_YEAR || year > MAX_BIRTH_YEAR) {
      setError(lang === "en"
        ? `Birth year must be between ${MIN_BIRTH_YEAR} and ${MAX_BIRTH_YEAR} (age 14+).`
        : `생년도는 ${MIN_BIRTH_YEAR}~${MAX_BIRTH_YEAR} 사이여야 합니다. (만 14세 이상)`);
      return;
    }
    if (nicknameAvailable === false) {
      setError(t(lang, "login_nickname_taken"));
      return;
    }
    if (!googleUser) {
      setError(lang === "en" ? "Google login info missing. Please try again." : "구글 로그인 정보가 없습니다. 다시 시도해주세요.");
      return;
    }
    setLoading(true);
    try {
      const token = await googleUser.getIdToken();
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          firebase_token: token,
          nickname,
          birth_year: year,
          agreed_terms: agreedTerms,
          agreed_privacy: agreedPrivacy,
          marketing_agreed: agreedMarketing,
          display_name: googleUser.displayName || undefined,
          email: googleUser.email || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        const detail = err.detail;
        const msg = Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join(", ")
          : (typeof detail === "string" ? detail : (lang === "en" ? "Registration failed." : "가입에 실패했습니다."));
        throw new Error(msg);
      }
      localStorage.setItem("onboarding_done", "true");
      router.push("/home");
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || (lang === "en" ? "Registration failed." : "가입에 실패했습니다."));
    } finally {
      setLoading(false);
    }
  }

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const user = await signInWithEmail(loginEmail, loginPassword);
      const token = await user.getIdToken();
      const meRes = await fetch(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (meRes.ok) {
        localStorage.setItem("onboarding_done", "true");
        router.push("/home");
      } else {
        setError(lang === "en"
          ? "Could not verify account. Please sign up."
          : "계정 정보를 확인할 수 없습니다. 회원가입이 필요합니다.");
        setTab("register");
      }
    } catch (e: unknown) {
      const err = e as { code?: string; message?: string };
      const code = err.code || "";
      if (code === "auth/user-not-found" || code === "auth/wrong-password") {
        setError(lang === "en"
          ? "Incorrect email or password."
          : "이메일 또는 비밀번호가 올바르지 않습니다.");
      } else {
        setError(err.message || (lang === "en" ? "Login failed." : "로그인에 실패했습니다."));
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (regPassword !== regPasswordConfirm) {
      setError(lang === "en" ? "Passwords do not match." : "비밀번호가 일치하지 않습니다.");
      return;
    }
    if (!agreedTerms || !agreedPrivacy) {
      setError(lang === "en" ? "You must agree to the required terms." : "필수 약관에 동의해야 합니다.");
      return;
    }
    const year = parseInt(birthYear);
    if (isNaN(year) || year < MIN_BIRTH_YEAR || year > MAX_BIRTH_YEAR) {
      setError(lang === "en"
        ? `Birth year must be between ${MIN_BIRTH_YEAR} and ${MAX_BIRTH_YEAR} (age 14+).`
        : `생년도는 ${MIN_BIRTH_YEAR}~${MAX_BIRTH_YEAR} 사이여야 합니다. (만 14세 이상)`);
      return;
    }
    if (nicknameAvailable === false) {
      setError(t(lang, "login_nickname_taken"));
      return;
    }

    setLoading(true);
    try {
      const fbUser = await createEmailUser(regEmail, regPassword);
      const token = await fbUser.getIdToken();

      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          firebase_token: token,
          nickname,
          birth_year: year,
          agreed_terms: agreedTerms,
          agreed_privacy: agreedPrivacy,
          marketing_agreed: agreedMarketing,
          email: regEmail,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        const detail = err.detail;
        const msg = Array.isArray(detail)
          ? detail.map((d: { msg: string }) => d.msg).join(", ")
          : (typeof detail === "string" ? detail : (lang === "en" ? "Registration failed." : "회원가입에 실패했습니다."));
        throw new Error(msg);
      }

      localStorage.setItem("onboarding_done", "true");
      router.push("/home");
    } catch (e: unknown) {
      const err = e as { code?: string; message?: string };
      if (err.code === "auth/operation-not-allowed") {
        setError(t(lang, "login_error_not_allowed"));
      } else if (err.code === "auth/email-already-in-use") {
        setError(t(lang, "login_error_email_in_use"));
        setEmailStatus("taken");
      } else {
        setError(err.message || (lang === "en" ? "Registration failed." : "회원가입에 실패했습니다."));
      }
    } finally {
      setLoading(false);
    }
  }

  // 이메일 회원가입 버튼 비활성화 조건
  const registerDisabled = loading
    || nicknameAvailable === false
    || emailStatus === "taken"
    || pwValid === false
    || pwMatch === false
    || !!birthYearError;

  const termsItems = [
    { key: "terms" as const, label: t(lang, "login_terms_label"), required: true, href: "/terms" as string | null, value: agreedTerms, setter: setAgreedTerms },
    { key: "privacy" as const, label: t(lang, "login_privacy_label"), required: true, href: "/privacy" as string | null, value: agreedPrivacy, setter: setAgreedPrivacy },
    { key: "marketing" as const, label: t(lang, "login_marketing_label"), required: false, href: null as string | null, value: agreedMarketing, setter: setAgreedMarketing },
  ];

  return (
    <div className="rounded-2xl border border-border bg-card shadow-xl p-8">
      {/* 로고 */}
      <div className="flex items-center gap-2 justify-center mb-6">
        <div className="relative h-7 w-16">
          <Image src="/logo-eye.png" alt="WeWantPeace" fill className="object-contain" priority />
        </div>
        <span className="text-lg font-bold tracking-tight">WeWantPeace</span>
      </div>

      {/* 구글 신규 가입 헤더 */}
      {tab === "google-register" && (
        <div className="mb-6 text-center">
          <h2 className="text-base font-bold">{t(lang, "login_google_register_title")}</h2>
          <p className="text-xs text-muted-foreground mt-1">{t(lang, "login_google_register_desc")}</p>
        </div>
      )}

      {/* 탭 */}
      {tab !== "google-register" && (
        <div className="flex rounded-lg bg-secondary p-1 mb-6">
          {(["login", "register"] as const).map((tabKey) => (
            <button
              key={tabKey}
              onClick={() => { setTab(tabKey); setError(null); }}
              className={cn(
                "flex-1 py-2 text-sm font-medium rounded-md transition-colors",
                tab === tabKey ? "bg-background text-foreground shadow" : "text-muted-foreground"
              )}
            >
              {tabKey === "login" ? t(lang, "login_tab_login") : t(lang, "login_tab_register")}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="mb-4 rounded-lg bg-destructive/10 border border-destructive/20 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {tab === "login" ? (
        <div className="space-y-4">
          {!isTossMiniApp() && (
            <>
              <button
                onClick={handleGoogleLogin}
                disabled={loading}
                className="w-full flex items-center justify-center gap-3 rounded-lg border border-border bg-background py-3 text-sm font-medium hover:bg-secondary transition-colors disabled:opacity-50"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                {t(lang, "login_google")}
              </button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
                <div className="relative flex justify-center text-xs text-muted-foreground"><span className="bg-card px-2">{t(lang, "login_or_email")}</span></div>
              </div>
            </>
          )}

          <form onSubmit={handleEmailLogin} className="space-y-3">
            <input
              type="email" value={loginEmail} onChange={(e) => setLoginEmail(e.target.value)}
              placeholder={t(lang, "login_email_placeholder")} required
              className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
            />
            <div className="relative">
              <input
                type={showLoginPw ? "text" : "password"}
                value={loginPassword} onChange={(e) => setLoginPassword(e.target.value)}
                placeholder={t(lang, "login_password_placeholder")} required
                className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary pr-10"
              />
              <button type="button" onClick={() => setShowLoginPw(!showLoginPw)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                {showLoginPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
            <button type="submit" disabled={loading}
              className="w-full rounded-lg bg-primary py-3 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center gap-2">
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {t(lang, "login_submit")}
            </button>
          </form>
        </div>
      ) : tab === "google-register" ? (
        <form onSubmit={handleGoogleRegister} className="space-y-3">
          <div className="rounded-lg bg-secondary/50 border border-border px-4 py-3 flex items-center gap-2 text-sm">
            <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            <span className="text-muted-foreground">{t(lang, "login_google_account")}</span>
            <span className="font-medium truncate">{googleUser?.email}</span>
          </div>

          <div>
            <div className="relative">
              <input
                type="text" value={nickname}
                onChange={(e) => handleNicknameChange(e.target.value)}
                placeholder={t(lang, "login_nickname_placeholder")} required
                className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
              />
              {nicknameChecking && (
                <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>
            {nicknameAvailable === true && <p className="mt-1 text-xs text-green-500">{t(lang, "login_nickname_available")}</p>}
            {nicknameAvailable === false && <p className="mt-1 text-xs text-destructive">{t(lang, "login_nickname_taken")}</p>}
          </div>

          <div>
            <input
              type="number" value={birthYear} onChange={(e) => handleBirthYearChange(e.target.value)}
              placeholder={t(lang, "login_birth_year_placeholder")}
              min={MIN_BIRTH_YEAR} max={MAX_BIRTH_YEAR} required
              className={cn("w-full rounded-lg border bg-background px-4 py-3 text-sm outline-none focus:border-primary",
                birthYearError ? "border-destructive" : "border-border"
              )}
            />
            {birthYearError && <p className="mt-1 text-xs text-destructive">{birthYearError}</p>}
          </div>

          <div className="rounded-lg border border-border p-4 space-y-3">
            <p className="text-xs font-medium text-muted-foreground">{t(lang, "login_terms_section")}</p>
            {termsItems.map((item) => (
              <div key={item.key} className="flex items-center gap-3">
                <button type="button" onClick={() => item.setter(!item.value)} className="shrink-0">
                  {item.value ? <CheckCircle2 className="h-5 w-5 text-primary" /> : <Circle className="h-5 w-5 text-muted-foreground/40" />}
                </button>
                <span className="text-sm flex-1">
                  {item.required && <span className="text-primary font-medium">{t(lang, "login_terms_required")} </span>}
                  {!item.required && <span className="text-muted-foreground">{t(lang, "login_terms_optional")} </span>}
                  {item.href ? (
                    <Link href={item.href} className="hover:underline" target="_blank">{item.label}</Link>
                  ) : item.label}
                </span>
              </div>
            ))}
          </div>

          <button type="submit" disabled={loading || nicknameAvailable === false}
            className="w-full rounded-lg bg-primary py-3 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center gap-2">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {t(lang, "login_google_complete")}
          </button>

          <p className="text-center text-xs text-muted-foreground">
            {t(lang, "login_back_link_text")}{" "}
            <button type="button" onClick={() => { setTab("login"); setGoogleUser(null); setError(null); }} className="text-primary hover:underline">{t(lang, "login_back_to_login")}</button>
          </p>
        </form>
      ) : (
        <form onSubmit={handleRegister} className="space-y-3">
          {/* 이메일 */}
          <div>
            <input
              type="email" value={regEmail} onChange={(e) => handleRegEmailChange(e.target.value)}
              placeholder={t(lang, "login_email_placeholder")} required
              className={cn("w-full rounded-lg border bg-background px-4 py-3 text-sm outline-none focus:border-primary",
                emailStatus === "taken" ? "border-destructive" : "border-border"
              )}
            />
            {emailStatus === "checking" && <p className="mt-1 text-xs text-muted-foreground flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" />{lang === "en" ? "Checking..." : "확인 중..."}</p>}
            {emailStatus === "taken" && <p className="mt-1 text-xs text-destructive">{t(lang, "login_error_email_in_use")}</p>}
          </div>

          {/* 비밀번호 */}
          <div>
            <input
              type="password" value={regPassword} onChange={(e) => handleRegPasswordChange(e.target.value)}
              placeholder={t(lang, "login_password_min")} minLength={8} required
              className={cn("w-full rounded-lg border bg-background px-4 py-3 text-sm outline-none focus:border-primary",
                regPassword && !pwValid ? "border-destructive" : "border-border"
              )}
            />
            {regPassword && pwValid === false && <p className="mt-1 text-xs text-destructive">{t(lang, "login_error_pw_short")}</p>}
            {regPassword && pwValid === true && <p className="mt-1 text-xs text-green-500">{t(lang, "login_pw_ok")}</p>}
          </div>

          {/* 비밀번호 확인 */}
          <div>
            <input
              type="password" value={regPasswordConfirm} onChange={(e) => handleRegPasswordConfirmChange(e.target.value)}
              placeholder={t(lang, "login_password_confirm")} required
              className={cn("w-full rounded-lg border bg-background px-4 py-3 text-sm outline-none focus:border-primary",
                regPasswordConfirm && pwMatch === false ? "border-destructive" : "border-border"
              )}
            />
            {regPasswordConfirm && pwMatch === false && <p className="mt-1 text-xs text-destructive">{t(lang, "login_error_pw_mismatch")}</p>}
            {regPasswordConfirm && pwMatch === true && <p className="mt-1 text-xs text-green-500">{t(lang, "login_pw_match")}</p>}
          </div>

          {/* 닉네임 (자동 중복확인) */}
          <div>
            <div className="relative">
              <input
                type="text" value={nickname}
                onChange={(e) => handleNicknameChange(e.target.value)}
                placeholder={t(lang, "login_nickname_placeholder")} required
                className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
              />
              {nicknameChecking && (
                <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>
            {nicknameAvailable === true && <p className="mt-1 text-xs text-green-500">{t(lang, "login_nickname_available")}</p>}
            {nicknameAvailable === false && <p className="mt-1 text-xs text-destructive">{t(lang, "login_nickname_taken")}</p>}
          </div>

          {/* 생년도 */}
          <div>
            <input
              type="number" value={birthYear} onChange={(e) => handleBirthYearChange(e.target.value)}
              placeholder={t(lang, "login_birth_year_placeholder")}
              min={MIN_BIRTH_YEAR} max={MAX_BIRTH_YEAR} required
              className={cn("w-full rounded-lg border bg-background px-4 py-3 text-sm outline-none focus:border-primary",
                birthYearError ? "border-destructive" : "border-border"
              )}
            />
            {birthYearError && <p className="mt-1 text-xs text-destructive">{birthYearError}</p>}
          </div>

          <div className="rounded-lg border border-border p-4 space-y-3">
            <p className="text-xs font-medium text-muted-foreground">{t(lang, "login_terms_section")}</p>
            {termsItems.map((item) => (
              <div key={item.key} className="flex items-center gap-3">
                <button type="button" onClick={() => item.setter(!item.value)} className="shrink-0">
                  {item.value ? <CheckCircle2 className="h-5 w-5 text-primary" /> : <Circle className="h-5 w-5 text-muted-foreground/40" />}
                </button>
                <span className="text-sm flex-1">
                  {item.required && <span className="text-primary font-medium">{t(lang, "login_terms_required")} </span>}
                  {!item.required && <span className="text-muted-foreground">{t(lang, "login_terms_optional")} </span>}
                  {item.href ? (
                    <Link href={item.href} className="hover:underline" target="_blank">{item.label}</Link>
                  ) : item.label}
                </span>
              </div>
            ))}
          </div>

          <button type="submit" disabled={registerDisabled}
            className="w-full rounded-lg bg-primary py-3 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center gap-2">
            {loading && <Loader2 className="h-4 w-4 animate-spin" />}
            {t(lang, "login_register_submit")}
          </button>

          <p className="text-center text-xs text-muted-foreground">
            {t(lang, "login_already_have")}{" "}
            <button type="button" onClick={() => setTab("login")} className="text-primary hover:underline">{t(lang, "login_login_link")}</button>
          </p>
        </form>
      )}
    </div>
  );
}

"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import Image from "next/image";
import { Eye, EyeOff, CheckCircle2, Circle, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  signInWithGoogle,
  signInWithApple,
  signInWithEmail,
  signInWithToss,
  createEmailUser,
  sendPasswordResetEmail,
  getFirebaseAuth,
  checkGoogleRedirectResult,
  useAuth,
} from "@/lib/auth";
import { fetchSignInMethodsForEmail } from "firebase/auth";
import type { User as FirebaseUser } from "firebase/auth";
import { useAppStore } from "@/lib/store";
import { t } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";
import { isTossMiniApp } from "@/lib/platform";
import { detectPlatform } from "@/lib/platform-detect";
import { isGoogleOAuthBlocked, openInExternalBrowser } from "@/lib/browser-detect";
import { trackEvent } from "@/lib/analytics";
import { TERMS_KO, TERMS_EN, PRIVACY_KO, PRIVACY_EN } from "@/lib/legal-data";

type Tab = "login" | "register" | "google-register";

const CURRENT_YEAR = new Date().getFullYear();
const MIN_BIRTH_YEAR = CURRENT_YEAR - 100;
const MAX_BIRTH_YEAR = CURRENT_YEAR - 14;

function getReturnUrl(): string {
  if (typeof window === "undefined") return "/home";
  const params = new URLSearchParams(window.location.search);
  return params.get("returnUrl") || sessionStorage.getItem("wwp_return_url") || "/home";
}

export default function LoginPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
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

  const [showResetPw, setShowResetPw] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [resetSent, setResetSent] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  const [showFindEmail, setShowFindEmail] = useState(false);
  const [findNickname, setFindNickname] = useState("");
  const [findBirthYear, setFindBirthYear] = useState("");
  const [findResult, setFindResult] = useState<string | null>(null);
  const [findLoading, setFindLoading] = useState(false);
  const [findError, setFindError] = useState<string | null>(null);

  const [googleUser, setGoogleUser] = useState<FirebaseUser | null>(null);
  const [checkingRedirect, setCheckingRedirect] = useState(true);
  const [termsModal, setTermsModal] = useState<"terms" | "privacy" | null>(null);
  const [inAppBlocked, setInAppBlocked] = useState(false);
  const [urlCopied, setUrlCopied] = useState(false);

  // iOS 플랫폼 감지 (Apple 로그인 버튼 표시용)
  const platform = detectPlatform();
  const isIOS = platform === "ios-native" || platform === "ios-app";

  // Firebase auth 상태 구독 (RegistrationGuard 리다이렉트 대응)
  const { user: firebaseUser, loading: firebaseLoading } = useAuth();

  // URL ?tab=google-register로 진입 시: Firebase auth 복원을 기다린 후 등록 폼 표시
  // 기존 버그: useEffect([])로 마운트 시 1회만 체크 → Firebase 복원 전이면 놓침
  // 수정: firebaseLoading/firebaseUser를 deps에 넣어 auth 상태 변화에 반응
  useEffect(() => {
    const urlTab = new URLSearchParams(window.location.search).get("tab");
    if (urlTab !== "google-register") return;
    if (firebaseLoading) return; // Firebase 아직 복원 중 → 대기
    if (firebaseUser) {
      setGoogleUser(firebaseUser);
      setTab("google-register");
    }
    // Firebase 복원 완료 후 유저가 없으면 → 일반 로그인 폼으로 폴백
    setCheckingRedirect(false);
  }, [firebaseLoading, firebaseUser]);

  // React Native WebView: Google 리다이렉트 로그인 결과 확인
  useEffect(() => {
    // 안전장치: 5초 내에 완료되지 않으면 강제로 로딩 해제 (Whale 등 일부 브라우저 hang 방지)
    const safetyTimeout = setTimeout(() => setCheckingRedirect(false), 5000);
    checkGoogleRedirectResult().then(async (user) => {
      if (!user) { clearTimeout(safetyTimeout); setCheckingRedirect(false); return; }
      try {
        const token = await user.getIdToken();
        const meRes = await fetch(`${API_BASE}/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (meRes.ok) {
          const meData = await meRes.json();
          // 닉네임/약관동의가 없으면 등록 폼으로
          if (!meData.nickname || !meData.agreed_terms_at) {
            setGoogleUser(user);
            setTab("google-register");
            clearTimeout(safetyTimeout);
            setCheckingRedirect(false);
            return;
          }
          trackEvent("auth_success", { provider: "google", source: "redirect" });
          localStorage.setItem("onboarding_done", "true");
          localStorage.setItem("wwp_welcome_seen", String(Date.now()));
          clearTimeout(safetyTimeout);
          router.push(getReturnUrl());
          return; // 이동 중 — 로딩 유지
        } else {
          setGoogleUser(user);
          setTab("google-register");
        }
      } catch {
        // 무시 — 리다이렉트 결과 없음
      }
      clearTimeout(safetyTimeout);
      setCheckingRedirect(false);
    }).catch(() => { clearTimeout(safetyTimeout); setCheckingRedirect(false); });
    return () => clearTimeout(safetyTimeout);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  async function handleTossLogin() {
    setLoading(true);
    setError(null);
    try {
      const { user, isNewUser } = await signInWithToss();
      if (!user) throw new Error(lang === "ko" ? "토스 로그인 실패" : "Toss login failed");

      if (isNewUser) {
        setGoogleUser(user);
        setTab("google-register");
      } else {
        // 기존 유저 — 약관동의 완료 여부 확인
        const token = await user.getIdToken();
        const meRes = await fetch(`${API_BASE}/me`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (meRes.ok) {
          const meData = await meRes.json();
          if (!meData.nickname || !meData.agreed_terms_at) {
            setGoogleUser(user);
            setTab("google-register");
            return;
          }
        }
        trackEvent("auth_success", { provider: "toss", source: "login" });
        localStorage.setItem("onboarding_done", "true");
        localStorage.setItem("wwp_welcome_seen", String(Date.now()));
        router.push(getReturnUrl());
      }
    } catch (e: unknown) {
      const err = e as { message?: string };
      const msg = err.message || "";
      if (msg.includes("Load failed") || msg.includes("network")) {
        setError(lang === "ko"
          ? "네트워크 연결 오류입니다. 인터넷 연결을 확인하고 다시 시도해주세요."
          : "Network error. Please check your connection and try again.");
      } else if (msg.includes("시간 초과") || msg.includes("timeout") || msg.includes("AbortError")) {
        setError(lang === "ko"
          ? "서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
          : "Server timeout. Please try again later.");
      } else {
        setError(msg || (lang === "ko" ? "토스 로그인에 실패했습니다." : "Toss login failed."));
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleLogin() {
    if (isGoogleOAuthBlocked()) {
      setInAppBlocked(true);
      setError(
        lang === "en"
          ? "Google login is not supported in this browser. Please open in Chrome or Safari."
          : "이 브라우저에서는 Google 로그인이 지원되지 않습니다.\nChrome 또는 Safari에서 열어주세요."
      );
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const user = await signInWithGoogle();
      // signInWithRedirect (React Native)는 여기에 도달하지 않음 → catch로 이동
      const token = await user.getIdToken();
      const meRes = await fetch(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (meRes.ok) {
        const meData = await meRes.json();
        // 닉네임/약관동의가 없으면 등록 폼으로
        if (!meData.nickname || !meData.agreed_terms_at) {
          setGoogleUser(user);
          setTab("google-register");
          return;
        }
        trackEvent("auth_success", { provider: "google", source: "login" });
        localStorage.setItem("onboarding_done", "true");
        localStorage.setItem("wwp_welcome_seen", String(Date.now()));
        router.push(getReturnUrl());
      } else {
        setGoogleUser(user);
        setTab("google-register");
      }
    } catch (e: unknown) {
      const err = e as { code?: string; message?: string; customData?: { email?: string } };
      // signInWithRedirect 후 페이지가 리다이렉트되므로 "redirect" 에러는 무시
      if (err.message === "redirect") return;
      if (err.code === "auth/account-exists-with-different-credential") {
        const email = err.customData?.email;
        if (email) {
          try {
            const auth = getFirebaseAuth();
            if (auth) {
              const methods = await fetchSignInMethodsForEmail(auth, email);
              const provider = methods[0] === "google.com" ? "Google" : methods[0] === "apple.com" ? "Apple" : methods[0] || "unknown";
              setError(t(lang, "login_provider_conflict", { provider }));
            } else {
              setError(err.message || "Google login failed.");
            }
          } catch {
            setError(err.message || "Google login failed.");
          }
        } else {
          setError(err.message || "Google login failed.");
        }
      } else {
        setError(err.message || "Google login failed.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleAppleLogin() {
    if (isGoogleOAuthBlocked()) {
      setInAppBlocked(true);
      setError(
        lang === "en"
          ? "Apple login is not supported in this browser. Please open in Chrome or Safari."
          : "이 브라우저에서는 Apple 로그인이 지원되지 않습니다.\nChrome 또는 Safari에서 열어주세요."
      );
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const user = await signInWithApple();
      // signInWithRedirect (React Native)는 여기에 도달하지 않음 → catch로 이동
      const token = await user.getIdToken();
      const meRes = await fetch(`${API_BASE}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (meRes.ok) {
        const meData = await meRes.json();
        // 닉네임/약관동의가 없으면 등록 폼으로
        if (!meData.nickname || !meData.agreed_terms_at) {
          setGoogleUser(user);
          setTab("google-register");
          return;
        }
        trackEvent("auth_success", { provider: "apple", source: "login" });
        localStorage.setItem("onboarding_done", "true");
        localStorage.setItem("wwp_welcome_seen", String(Date.now()));
        router.push(getReturnUrl());
      } else {
        setGoogleUser(user);
        setTab("google-register");
      }
    } catch (e: unknown) {
      const err = e as { code?: string; message?: string; customData?: { email?: string } };
      // signInWithRedirect 후 페이지가 리다이렉트되므로 "redirect" 에러는 무시
      if (err.message === "redirect") return;
      if (err.code === "auth/account-exists-with-different-credential") {
        const email = err.customData?.email;
        if (email) {
          try {
            const auth = getFirebaseAuth();
            if (auth) {
              const methods = await fetchSignInMethodsForEmail(auth, email);
              const provider = methods[0] === "google.com" ? "Google" : methods[0] === "apple.com" ? "Apple" : methods[0] || "unknown";
              setError(t(lang, "login_provider_conflict", { provider }));
            } else {
              setError(err.message || "Apple login failed.");
            }
          } catch {
            setError(err.message || "Apple login failed.");
          }
        } else {
          setError(err.message || "Apple login failed.");
        }
      } else {
        setError(err.message || "Apple login failed.");
      }
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
      const registerBody = {
        firebase_token: token,
        nickname,
        birth_year: year,
        agreed_terms: agreedTerms,
        agreed_privacy: agreedPrivacy,
        marketing_agreed: agreedMarketing,
        display_name: googleUser.displayName || undefined,
        email: googleUser.email || undefined,
      };
      // 필수 필드 누락 사전 검증
      const missing: string[] = [];
      if (!registerBody.firebase_token) missing.push("firebase_token");
      if (!registerBody.nickname) missing.push("nickname");
      if (registerBody.birth_year == null || isNaN(registerBody.birth_year)) missing.push("birth_year");
      if (registerBody.agreed_terms == null) missing.push("agreed_terms");
      if (registerBody.agreed_privacy == null) missing.push("agreed_privacy");
      if (missing.length > 0) {
        console.error("[register] missing fields:", missing, registerBody);
      }
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(registerBody),
      });
      if (!res.ok) {
        const err = await res.json();
        const detail = err.detail;
        const msg = Array.isArray(detail)
          ? detail.map((d: { msg: string; loc?: (string | number)[] }) => {
              const field = d.loc ? d.loc.filter(l => l !== "body").join(".") : "";
              return field ? `${field}: ${d.msg}` : d.msg;
            }).join(", ")
          : (typeof detail === "string" ? detail : (lang === "en" ? "Registration failed." : "가입에 실패했습니다."));
        throw new Error(msg);
      }
      const registeredUser = await res.json();
      trackEvent("auth_success", { provider: "google", source: "register" });
      // 등록 응답을 즉시 캐시에 반영 — RegistrationGuard가 stale 데이터로 리다이렉트하는 것 방지
      queryClient.setQueryData(["me"], registeredUser);
      localStorage.setItem("onboarding_done", "true");
      localStorage.setItem("wwp_welcome_seen", String(Date.now()));
      router.push(getReturnUrl());
    } catch (e: unknown) {
      const err = e as { message?: string };
      setError(err.message || (lang === "en" ? "Registration failed." : "가입에 실패했습니다."));
    } finally {
      setLoading(false);
    }
  }

  async function handleFindEmail(e: React.FormEvent) {
    e.preventDefault();
    setFindError(null);
    setFindResult(null);
    setFindLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/auth/find-email?nickname=${encodeURIComponent(findNickname)}&birth_year=${findBirthYear}`
      );
      const data = await res.json();
      if (data.found) {
        setFindResult(data.email);
      } else {
        setFindError(t(lang, "login_find_email_not_found"));
      }
    } catch {
      setFindError(lang === "en" ? "Request failed. Try again." : "요청에 실패했습니다. 다시 시도해주세요.");
    } finally {
      setFindLoading(false);
    }
  }

  async function handlePasswordReset(e: React.FormEvent) {
    e.preventDefault();
    setResetError(null);
    setResetLoading(true);
    try {
      await sendPasswordResetEmail(resetEmail);
      setResetSent(true);
    } catch (err: unknown) {
      const error = err as { code?: string };
      if (error.code === "auth/user-not-found") {
        setResetError(lang === "en" ? "No account found with this email." : "해당 이메일로 등록된 계정이 없습니다.");
      } else {
        setResetError(lang === "en" ? "Failed to send reset email. Try again." : "재설정 이메일 전송에 실패했습니다. 다시 시도해주세요.");
      }
    } finally {
      setResetLoading(false);
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
        const meData = await meRes.json();
        // 닉네임/약관동의가 없으면 등록 폼으로
        if (!meData.nickname || !meData.agreed_terms_at) {
          setGoogleUser(user);
          setTab("google-register");
          return;
        }
        trackEvent("auth_success", { provider: "email", source: "login" });
        localStorage.setItem("onboarding_done", "true");
        localStorage.setItem("wwp_welcome_seen", String(Date.now()));
        router.push(getReturnUrl());
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

      const registeredEmailUser = await res.json();
      trackEvent("auth_success", { provider: "email", source: "register" });
      queryClient.setQueryData(["me"], registeredEmailUser);
      localStorage.setItem("onboarding_done", "true");
      localStorage.setItem("wwp_welcome_seen", String(Date.now()));
      router.push(getReturnUrl());
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
    { key: "terms" as const, label: t(lang, "login_terms_label"), required: true, modal: "terms" as "terms" | "privacy" | null, value: agreedTerms, setter: setAgreedTerms },
    { key: "privacy" as const, label: t(lang, "login_privacy_label"), required: true, modal: "privacy" as "terms" | "privacy" | null, value: agreedPrivacy, setter: setAgreedPrivacy },
    { key: "marketing" as const, label: t(lang, "login_marketing_label"), required: false, modal: null as "terms" | "privacy" | null, value: agreedMarketing, setter: setAgreedMarketing },
  ];

  if (checkingRedirect) {
    return (
      <div className="rounded-2xl border border-border bg-card shadow-xl p-5 sm:p-8 flex flex-col items-center justify-center min-h-[250px]">
        <div className="relative h-7 w-16 mb-4">
          <Image src="/logo-eye.png" alt="WeWantPeace" fill className="object-contain" priority />
        </div>
        <Loader2 className="h-6 w-6 animate-spin text-primary mb-3" />
        <p className="text-sm text-muted-foreground">
          {lang === "en" ? "Signing in..." : "로그인 중..."}
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-border bg-card shadow-xl p-5 sm:p-8">
      {/* 로고 */}
      <div className="flex items-center gap-2 justify-center" style={{ marginBottom: "var(--space-lg)" }}>
        <div className="relative h-7 w-16">
          <Image src="/logo-eye.png" alt="WeWantPeace" fill className="object-contain" priority />
        </div>
        <span className="text-lg font-bold tracking-tight">WeWantPeace</span>
      </div>

      {/* 구글 신규 가입 헤더 */}
      {tab === "google-register" && (
        <div className="text-center" style={{ marginBottom: "var(--space-lg)" }}>
          <h2 className="text-base font-bold">{t(lang, "login_google_register_title")}</h2>
          <p className="text-xs text-muted-foreground mt-1">{t(lang, "login_google_register_desc")}</p>
        </div>
      )}

      {/* 탭 (Toss 미니앱에서는 숨김 — Toss 로그인만 제공) */}
      {tab !== "google-register" && !isTossMiniApp() && (
        <div className="flex rounded-lg bg-secondary p-1" style={{ marginBottom: "var(--space-lg)" }}>
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
        <div className="mb-3 rounded-lg bg-destructive/10 border border-destructive/20 px-3 py-2 sm:mb-4 sm:px-4 sm:py-3 text-sm text-destructive whitespace-pre-line">
          {error}
        </div>
      )}

      {/* 인앱브라우저 URL 복사 버튼 */}
      {inAppBlocked && (
        <button
          onClick={async () => {
            await openInExternalBrowser();
            setUrlCopied(true);
          }}
          className={`w-full mb-4 flex items-center justify-center gap-2 rounded-lg border py-3 text-sm font-bold transition-colors ${
            urlCopied
              ? "border-emerald-500/50 bg-emerald-500/10 text-emerald-400"
              : "border-primary/50 bg-primary/10 text-primary hover:bg-primary/20"
          }`}
        >
          {urlCopied
            ? (lang === "en" ? "URL copied! Paste in your browser" : "URL 복사 완료! 브라우저에 붙여넣기 해주세요")
            : (lang === "en" ? "Copy URL to open in browser" : "URL 복사하기 (브라우저에서 열기)")}
        </button>
      )}

      {tab === "login" ? (
        <div className="space-y-4">
          {isTossMiniApp() ? (
            <>
              <button
                onClick={handleTossLogin}
                disabled={loading}
                className="w-full flex items-center justify-center gap-2.5 rounded-lg py-3 font-bold text-white transition-colors disabled:opacity-50"
                style={{ backgroundColor: "#0064FF" }}
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <span className="text-[15px] font-black tracking-tight" style={{ fontFamily: "'SF Pro', system-ui, sans-serif" }}>toss</span>
                )}
                <span className="text-sm">{t(lang, "login_toss")}</span>
              </button>

            </>
          ) : (
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

              <button
                onClick={handleAppleLogin}
                disabled={loading}
                className="w-full flex items-center justify-center gap-3 rounded-lg border border-border bg-foreground text-background py-3 text-sm font-medium hover:opacity-90 transition-colors disabled:opacity-50"
              >
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.54 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/>
                </svg>
                {t(lang, "login_apple")}
              </button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-border" /></div>
                <div className="relative flex justify-center text-xs text-muted-foreground"><span className="bg-card px-2">{t(lang, "login_or_email")}</span></div>
              </div>
            </>
          )}

          {/* 이메일 로그인 (Toss 미니앱에서는 숨김) */}
          {!isTossMiniApp() && (
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
              <div className="flex justify-between">
                <button
                  type="button"
                  onClick={() => { setShowFindEmail(true); setFindNickname(""); setFindBirthYear(""); setFindResult(null); setFindError(null); }}
                  className="text-xs text-muted-foreground hover:text-primary transition-colors"
                >
                  {t(lang, "login_find_email")}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowResetPw(true); setResetEmail(loginEmail); setResetSent(false); setResetError(null); }}
                  className="text-xs text-muted-foreground hover:text-primary transition-colors"
                >
                  {t(lang, "login_forgot_password")}
                </button>
              </div>
              <button type="submit" disabled={loading}
                className="w-full rounded-lg bg-primary py-3 text-sm font-bold text-primary-foreground hover:bg-primary/90 disabled:opacity-50 flex items-center justify-center gap-2">
                {loading && <Loader2 className="h-4 w-4" />}
                {t(lang, "login_submit")}
              </button>
            </form>
          )}

          {/* 비밀번호 재설정 모달 */}
          {showResetPw && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={() => setShowResetPw(false)}>
              <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
                <p className="text-sm font-semibold">{t(lang, "login_reset_title")}</p>
                {resetSent ? (
                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground">{t(lang, "login_reset_sent")}</p>
                    <button
                      onClick={() => setShowResetPw(false)}
                      className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground"
                    >
                      {t(lang, "login_reset_close")}
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handlePasswordReset} className="space-y-3">
                    <p className="text-xs text-muted-foreground">{t(lang, "login_reset_desc")}</p>
                    {resetError && <p className="text-xs text-destructive">{resetError}</p>}
                    <input
                      type="email"
                      value={resetEmail}
                      onChange={(e) => setResetEmail(e.target.value)}
                      placeholder={t(lang, "login_email_placeholder")}
                      required
                      autoFocus
                      className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
                    />
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={resetLoading}
                        className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 flex items-center justify-center gap-1"
                      >
                        {resetLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                        {t(lang, "login_reset_submit")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowResetPw(false)}
                        className="flex-1 rounded-lg border border-border py-2.5 text-sm text-muted-foreground"
                      >
                        {t(lang, "login_reset_cancel")}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}

          {/* 아이디(이메일) 찾기 모달 */}
          {showFindEmail && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-6" onClick={() => setShowFindEmail(false)}>
              <div className="w-full max-w-sm rounded-2xl border border-border bg-card p-5 space-y-4" onClick={(e) => e.stopPropagation()}>
                <p className="text-sm font-semibold">{t(lang, "login_find_email_title")}</p>
                {findResult ? (
                  <div className="space-y-3">
                    <p className="text-xs text-muted-foreground">{t(lang, "login_find_email_result")}</p>
                    <p className="text-sm font-mono bg-secondary rounded-lg px-4 py-3">{findResult}</p>
                    <button
                      onClick={() => setShowFindEmail(false)}
                      className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground"
                    >
                      {t(lang, "login_reset_close")}
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleFindEmail} className="space-y-3">
                    <p className="text-xs text-muted-foreground">{t(lang, "login_find_email_desc")}</p>
                    {findError && <p className="text-xs text-destructive">{findError}</p>}
                    <input
                      type="text"
                      value={findNickname}
                      onChange={(e) => setFindNickname(e.target.value)}
                      placeholder={t(lang, "login_nickname_placeholder")}
                      required
                      autoFocus
                      className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
                    />
                    <input
                      type="number"
                      value={findBirthYear}
                      onChange={(e) => setFindBirthYear(e.target.value)}
                      placeholder={t(lang, "login_birth_year_placeholder")}
                      required
                      className="w-full rounded-lg border border-border bg-background px-4 py-3 text-sm outline-none focus:border-primary"
                    />
                    <div className="flex gap-2">
                      <button
                        type="submit"
                        disabled={findLoading}
                        className="flex-1 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground disabled:opacity-50 flex items-center justify-center gap-1"
                      >
                        {findLoading && <Loader2 className="h-3 w-3 animate-spin" />}
                        {t(lang, "login_find_email_submit")}
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowFindEmail(false)}
                        className="flex-1 rounded-lg border border-border py-2.5 text-sm text-muted-foreground"
                      >
                        {t(lang, "login_reset_cancel")}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}
        </div>
      ) : tab === "google-register" ? (
        <form onSubmit={handleGoogleRegister} className="space-y-3">
          <div className="rounded-lg bg-secondary/50 border border-border px-4 py-3 flex items-center gap-2 text-sm">
            {googleUser?.uid?.startsWith("toss:") ? (
              <>
                <span className="text-[15px] font-black tracking-tight shrink-0" style={{ fontFamily: "'SF Pro', system-ui, sans-serif", color: "#0064FF" }}>toss</span>
                <span className="text-muted-foreground">{lang === "ko" ? "토스 계정으로 로그인됨" : "Signed in with Toss"}</span>
              </>
            ) : (
              <>
                <svg className="h-4 w-4 shrink-0" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                <span className="text-muted-foreground">{t(lang, "login_google_account")}</span>
                <span className="font-medium truncate">{googleUser?.email}</span>
              </>
            )}
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
                  {item.modal ? (
                    <button type="button" onClick={() => setTermsModal(item.modal)} className="hover:underline text-left">{item.label}</button>
                  ) : item.label}
                </span>
              </div>
            ))}
            <p className="text-[10px] text-blue-400 ml-8">{t(lang, "marketing_newsletter_benefit")}</p>
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
                  {item.modal ? (
                    <button type="button" onClick={() => setTermsModal(item.modal)} className="hover:underline text-left">{item.label}</button>
                  ) : item.label}
                </span>
              </div>
            ))}
            <p className="text-[10px] text-blue-400 ml-8">{t(lang, "marketing_newsletter_benefit")}</p>
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

      {/* 약관/개인정보 모달 */}
      {termsModal && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
          onClick={() => setTermsModal(null)}
        >
          <div className="absolute inset-0 bg-black/60" />
          <div
            className="relative w-full max-w-lg max-h-[85dvh] bg-background rounded-t-2xl sm:rounded-2xl flex flex-col overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 헤더 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
              <h2 className="text-base font-bold">
                {termsModal === "terms"
                  ? t(lang, "login_terms_label")
                  : t(lang, "login_privacy_label")}
              </h2>
              <button
                onClick={() => setTermsModal(null)}
                className="p-1 rounded-lg hover:bg-muted/50 transition-colors"
              >
                <X className="h-5 w-5 text-muted-foreground" />
              </button>
            </div>
            {/* 본문 */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              {(termsModal === "terms"
                ? lang === "en" ? TERMS_EN : TERMS_KO
                : lang === "en" ? PRIVACY_EN : PRIVACY_KO
              ).map((section) => (
                <div key={section.title}>
                  <h3 className="text-sm font-bold text-primary mb-1.5">{section.title}</h3>
                  <p className="text-xs text-muted-foreground leading-relaxed whitespace-pre-line">
                    {section.content}
                  </p>
                </div>
              ))}
            </div>
            {/* 닫기 버튼 */}
            <div className="px-5 py-3 border-t border-border shrink-0">
              <button
                onClick={() => setTermsModal(null)}
                className="w-full rounded-lg bg-primary py-2.5 text-sm font-bold text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                {lang === "ko" ? "확인" : "Close"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

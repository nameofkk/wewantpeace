"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { X, Globe } from "lucide-react";
import { signInWithGoogle } from "@/lib/auth";
import { useAppStore } from "@/lib/store";

interface LoginModalProps {
  onClose: () => void;
  message?: string;
}

export function LoginModal({ onClose, message }: LoginModalProps) {
  const router = useRouter();
  const overlayRef = useRef<HTMLDivElement>(null);
  const lang = useAppStore((s) => s.lang);

  useEffect(() => {
    document.body.style.overflow = "hidden";
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handler);
    };
  }, [onClose]);

  async function handleGoogle() {
    // React Native WebView: signInWithRedirect 사용 → /login 페이지로 이동
    const isRN = typeof window !== "undefined" && !!(window.__REACT_NATIVE__ || window.ReactNativeWebView);
    if (isRN) {
      onClose();
      router.push("/login");
      return;
    }
    try {
      await signInWithGoogle();
      onClose();
    } catch (e: unknown) {
      // signInWithGoogle이 팝업 차단(브라우저 정책·광고 차단 확장 등)을 만나면
      // 내부적으로 signInWithRedirect로 넘어가며 "redirect" 에러를 던진다 —
      // 이 시점엔 이미 브라우저가 Google 인증 화면으로 이동 중이므로
      // 여기서 /login으로 또 이동시키면 진행 중인 리다이렉트와 경쟁한다.
      // 실제 로그인 상태는 useAuth()의 onIdTokenChanged가 복귀 후 전역으로 잡아준다.
      if ((e as { message?: string })?.message === "redirect") return;
      router.push("/login");
    }
  }

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
    >
      <div className="relative w-full max-w-sm mx-4 rounded-2xl border border-border bg-card p-6 shadow-xl">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2 justify-center mb-4">
          <Globe className="h-5 w-5 text-primary" />
          <span className="font-bold">WeWantPeace</span>
        </div>

        <p className="text-center text-sm text-muted-foreground mb-5">
          {message || (lang === "ko" ? "로그인이 필요한 기능입니다." : "Login is required to use this feature.")}
        </p>

        <button
          onClick={handleGoogle}
          className="w-full flex items-center justify-center gap-3 rounded-xl border border-border bg-background py-3 text-sm font-medium hover:bg-secondary transition-colors"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          {lang === "ko" ? "Google로 계속하기" : "Continue with Google"}
        </button>

        <button
          onClick={() => { onClose(); router.push("/login"); }}
          className="mt-3 w-full rounded-xl bg-primary py-3 text-sm font-bold text-primary-foreground hover:bg-primary/90"
        >
          {lang === "ko" ? "이메일로 로그인 / 회원가입" : "Log in / Sign up with Email"}
        </button>
      </div>
    </div>
  );
}

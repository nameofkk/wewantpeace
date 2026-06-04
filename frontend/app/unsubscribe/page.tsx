"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState, Suspense } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.wewantpeace.live";

type State = "loading" | "confirm" | "success" | "already" | "error";

const TEXT = {
  ko: {
    title: "뉴스레터 수신거부",
    loading: "확인 중...",
    confirm_heading: "수신거부 확인",
    confirm_desc: "아래 이메일의 마케팅 뉴스레터 수신을 거부합니다.",
    email_label: "이메일",
    btn_unsubscribe: "수신거부",
    btn_processing: "처리 중...",
    success_heading: "수신거부 완료",
    success_desc: "더 이상 마케팅 뉴스레터를 보내지 않습니다.",
    success_note: "설정에서 언제든 다시 수신 동의할 수 있습니다.",
    already_heading: "이미 수신거부됨",
    already_desc: "이 이메일은 이미 수신거부 처리되었습니다.",
    error_heading: "오류 발생",
    error_desc: "유효하지 않거나 만료된 링크입니다.",
    home: "홈으로",
  },
  en: {
    title: "Unsubscribe from Newsletter",
    loading: "Verifying...",
    confirm_heading: "Confirm Unsubscribe",
    confirm_desc: "You are unsubscribing from marketing newsletters for the following email.",
    email_label: "Email",
    btn_unsubscribe: "Unsubscribe",
    btn_processing: "Processing...",
    success_heading: "Unsubscribed",
    success_desc: "You will no longer receive marketing newsletters.",
    success_note: "You can re-subscribe anytime from your account settings.",
    already_heading: "Already Unsubscribed",
    already_desc: "This email has already been unsubscribed.",
    error_heading: "Error",
    error_desc: "Invalid or expired link.",
    home: "Home",
  },
} as const;

function detectLang(): "ko" | "en" {
  if (typeof window === "undefined") return "ko";
  // Check localStorage for saved preference
  try {
    const store = JSON.parse(localStorage.getItem("wwp-store") || "{}");
    if (store.state?.lang) return store.state.lang === "en" ? "en" : "ko";
  } catch {
    // ignore
  }
  // Check browser language
  const nav = navigator.language || "";
  return nav.startsWith("ko") ? "ko" : "en";
}

function UnsubscribeContent() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") || "";

  const [state, setState] = useState<State>("loading");
  const [maskedEmail, setMaskedEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lang, setLang] = useState<"ko" | "en">("ko");

  useEffect(() => {
    setLang(detectLang());
  }, []);

  useEffect(() => {
    if (!token) {
      setState("error");
      return;
    }

    fetch(`${API_BASE}/newsletter/unsubscribe?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (!res.ok) {
          setState("error");
          return;
        }
        const data = await res.json();
        setMaskedEmail(data.masked_email);
        if (data.already_unsubscribed) {
          setState("already");
        } else {
          setState("confirm");
        }
      })
      .catch(() => setState("error"));
  }, [token]);

  const handleUnsubscribe = async () => {
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/newsletter/unsubscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (!res.ok) {
        setState("error");
        return;
      }
      const data = await res.json();
      if (data.status === "already_unsubscribed") {
        setState("already");
      } else {
        setState("success");
      }
    } catch {
      setState("error");
    } finally {
      setSubmitting(false);
    }
  };

  const t = TEXT[lang];

  return (
    <div className="min-h-screen bg-background flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-md">
        {/* Loading */}
        {state === "loading" && (
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-primary" />
            <p className="mt-4 text-sm text-muted-foreground">{t.loading}</p>
          </div>
        )}

        {/* Confirm */}
        {state === "confirm" && (
          <div className="rounded-xl border border-border bg-card p-8">
            <div className="text-center mb-6">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-orange-500/10">
                <svg className="h-6 w-6 text-orange-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <h1 className="text-lg font-bold text-foreground">{t.confirm_heading}</h1>
              <p className="mt-2 text-sm text-muted-foreground">{t.confirm_desc}</p>
            </div>

            <div className="rounded-lg bg-muted/50 p-4 mb-6">
              <p className="text-xs text-muted-foreground mb-1">{t.email_label}</p>
              <p className="text-sm font-medium text-foreground">{maskedEmail}</p>
            </div>

            <button
              onClick={handleUnsubscribe}
              disabled={submitting}
              className="w-full bg-primary text-primary-foreground rounded-lg px-4 py-2.5 text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {submitting ? t.btn_processing : t.btn_unsubscribe}
            </button>
          </div>
        )}

        {/* Success */}
        {state === "success" && (
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-green-500/10">
              <svg className="h-6 w-6 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-lg font-bold text-foreground">{t.success_heading}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{t.success_desc}</p>
            <p className="mt-4 text-xs text-muted-foreground">{t.success_note}</p>
            <a
              href="https://wewantpeace.live"
              className="mt-6 inline-block text-sm text-primary hover:underline"
            >
              {t.home}
            </a>
          </div>
        )}

        {/* Already unsubscribed */}
        {state === "already" && (
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-blue-500/10">
              <svg className="h-6 w-6 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h1 className="text-lg font-bold text-foreground">{t.already_heading}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{t.already_desc}</p>
            {maskedEmail && (
              <p className="mt-2 text-xs text-muted-foreground">{maskedEmail}</p>
            )}
            <a
              href="https://wewantpeace.live"
              className="mt-6 inline-block text-sm text-primary hover:underline"
            >
              {t.home}
            </a>
          </div>
        )}

        {/* Error */}
        {state === "error" && (
          <div className="rounded-xl border border-border bg-card p-8 text-center">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10">
              <svg className="h-6 w-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h1 className="text-lg font-bold text-foreground">{t.error_heading}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{t.error_desc}</p>
            <a
              href="https://wewantpeace.live"
              className="mt-6 inline-block text-sm text-primary hover:underline"
            >
              {t.home}
            </a>
          </div>
        )}

        {/* Footer */}
        <p className="mt-6 text-center text-xs text-muted-foreground">
          WeWantPeace
        </p>
      </div>
    </div>
  );
}

export default function UnsubscribePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-background flex items-center justify-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-2 border-muted-foreground border-t-primary" />
        </div>
      }
    >
      <UnsubscribeContent />
    </Suspense>
  );
}

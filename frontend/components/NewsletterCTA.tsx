"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useAppStore } from "@/lib/store";
import { useMe, usePatchProfile } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Mail, X, Eye, ArrowRight, CheckCircle } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://api.wewantpeace.live";
const DISMISSED_KEY = "wwp-newsletter-cta-dismissed";

export function NewsletterCTA() {
  const lang = useAppStore((s) => s.lang);
  const { data: me } = useMe();
  const patchProfile = usePatchProfile();

  const [dismissed, setDismissed] = useState(true);
  const [showPreview, setShowPreview] = useState(false);
  const [previewLang, setPreviewLang] = useState<"kr" | "us">("kr");
  const [subCount, setSubCount] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [previewHtml, setPreviewHtml] = useState("");

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(DISMISSED_KEY) === "true");
    } catch {
      setDismissed(false);
    }
  }, []);

  useEffect(() => {
    fetch(`${API}/newsletter/stats`)
      .then((r) => r.json())
      .then((d) => setSubCount(d.subscriber_count))
      .catch(() => {});
  }, []);

  // 미리보기 HTML fetch + CSS 주입 (max-width 제거 → 컨테이너 폭에 맞게)
  useEffect(() => {
    if (!showPreview) return;
    setPreviewHtml("");
    fetch(`${API}/newsletter/sample?lang=${previewLang}`)
      .then((r) => r.text())
      .then((raw) => {
        const inject = `<style>body{background:#fff!important}table[style*="max-width:600px"]{max-width:100%!important}.ma{max-width:100%!important}</style>`;
        setPreviewHtml(raw.replace("</head>", inject + "</head>"));
      })
      .catch(() => setPreviewHtml("<p style='padding:40px;text-align:center;color:#999'>로드 실패</p>"));
  }, [showPreview, previewLang]);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  }, []);

  const handleDismiss = useCallback(() => {
    setDismissed(true);
    try { localStorage.setItem(DISMISSED_KEY, "true"); } catch {}
  }, []);

  const isLoggedIn = !!me?.id;
  const isSubscribed = !!me?.marketing_agreed_at;

  const handleSubscribe = useCallback(() => {
    if (!isLoggedIn) return;
    const turningOn = !isSubscribed;
    patchProfile.mutate(
      { marketing_agreed_at: turningOn ? "now" : "" },
      {
        onSuccess: () => {
          showToast(
            turningOn
              ? lang === "ko" ? "구독 완료! 매주 월요일 브리핑을 보내드릴게요" : "Subscribed! Briefings every Monday"
              : lang === "ko" ? "구독이 해지되었습니다" : "Unsubscribed",
          );
        },
      },
    );
  }, [isLoggedIn, isSubscribed, lang, patchProfile, showToast]);

  if (dismissed) return null;

  const socialProof = subCount && subCount > 0
    ? lang === "ko"
      ? `${subCount.toLocaleString("ko-KR")}명이 읽는 중`
      : `${subCount.toLocaleString("en-US")} readers`
    : null;

  return (
    <>
      {/* ── 그래디언트 보더 카드 ── */}
      <div className="group relative rounded-xl p-[1px] bg-gradient-to-r from-blue-500/60 via-indigo-500/60 to-blue-400/60 transition-all duration-500 hover:from-blue-400 hover:via-indigo-400 hover:to-blue-300">
        {/* Glow */}
        <div className="absolute -inset-2 rounded-2xl bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-400 opacity-0 blur-xl transition-opacity duration-700 group-hover:opacity-[0.08]" />

        {/* 카드 본체 */}
        <div className="relative rounded-[11px] bg-card overflow-hidden">
          <button
            onClick={handleDismiss}
            className="absolute top-2.5 right-2.5 z-10 p-1 rounded-full hover:bg-muted/50 transition-colors"
            aria-label="Close"
          >
            <X className="h-3 w-3 text-muted-foreground/40" />
          </button>

          <div className="px-4 pt-4 pb-3.5">
            {/* 상태 뱃지 */}
            <div className="flex items-center gap-1.5 mb-2.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
              </span>
              <span className="text-[10px] font-medium text-emerald-400/80">
                {socialProof || (lang === "ko" ? "매주 월요일 발행" : "Published every Monday")}
              </span>
            </div>

            {/* 헤드라인 */}
            <h3 className="text-[13px] font-bold text-foreground leading-snug">
              {t(lang, "newsletter_title")}
            </h3>
            <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">
              {t(lang, "newsletter_desc")}
            </p>

            {/* 액션 버튼 — 항상 full-width 중앙정렬 */}
            <div className="mt-3.5 space-y-2">
              {isLoggedIn ? (
                isSubscribed ? (
                  /* 구독 중 — 중앙정렬된 상태 표시 */
                  <div className="h-9 rounded-lg bg-muted/20 flex items-center justify-center gap-1.5">
                    <CheckCircle className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-[11px] font-medium text-muted-foreground">
                      {lang === "ko" ? "구독 중 · 매주 월요일 발송" : "Subscribed · Every Monday"}
                    </span>
                  </div>
                ) : (
                  /* 미구독 — CTA 버튼 */
                  <button
                    onClick={handleSubscribe}
                    disabled={patchProfile.isPending}
                    className="relative w-full h-9 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-[11px] font-semibold overflow-hidden
                      hover:from-blue-500 hover:to-indigo-500 active:scale-[0.98] transition-all
                      before:absolute before:inset-0 before:rounded-[inherit]
                      before:bg-[linear-gradient(110deg,transparent_25%,rgba(255,255,255,0.15)_50%,transparent_75%)]
                      before:bg-[length:250%_100%] before:bg-[position:200%_0]
                      before:transition-[background-position] before:duration-[0ms]
                      hover:before:bg-[position:-100%_0] hover:before:duration-[1200ms]"
                  >
                    <span className="relative flex items-center justify-center gap-1">
                      {lang === "ko" ? "무료로 받아보기" : "Get it free"}
                      <ArrowRight className="h-3 w-3" />
                    </span>
                  </button>
                )
              ) : (
                /* 비로그인 */
                <Link href="/login" className="block">
                  <div className="relative h-9 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white flex items-center justify-center text-[11px] font-semibold overflow-hidden
                    hover:from-blue-500 hover:to-indigo-500 active:scale-[0.98] transition-all
                    before:absolute before:inset-0 before:rounded-[inherit]
                    before:bg-[linear-gradient(110deg,transparent_25%,rgba(255,255,255,0.15)_50%,transparent_75%)]
                    before:bg-[length:250%_100%] before:bg-[position:200%_0]
                    before:transition-[background-position] before:duration-[0ms]
                    hover:before:bg-[position:-100%_0] hover:before:duration-[1200ms]">
                    <span className="relative flex items-center gap-1">
                      {t(lang, "newsletter_login_subscribe")}
                      <ArrowRight className="h-3 w-3" />
                    </span>
                  </div>
                </Link>
              )}

              {/* 미리보기 버튼 — 항상 표시 */}
              <button
                onClick={() => { setPreviewLang(lang === "ko" ? "kr" : "us"); setShowPreview(true); }}
                className="w-full h-8 rounded-lg border border-border/60 text-[10px] font-medium text-muted-foreground hover:border-blue-500/30 hover:text-foreground transition-colors flex items-center justify-center gap-1.5"
              >
                <Eye className="h-3 w-3" />
                {lang === "ko" ? "지난 뉴스레터 미리보기" : "Preview past newsletter"}
              </button>
            </div>

            {/* 하단 */}
            {isLoggedIn && isSubscribed && (
              <button
                onClick={handleSubscribe}
                disabled={patchProfile.isPending}
                className="block mx-auto mt-2 text-[9px] text-muted-foreground/30 hover:text-muted-foreground/60 transition-colors"
              >
                {lang === "ko" ? "구독 해지" : "Unsubscribe"}
              </button>
            )}
            {!(isLoggedIn && isSubscribed) && (
              <p className="text-[9px] text-muted-foreground/30 text-center mt-2">
                {lang === "ko"
                  ? "무료 · 3분 분량 · 언제든 해지"
                  : "Free · 3 min read · Cancel anytime"}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* ── 토스트 ── */}
      {toast && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-[110] animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className="flex items-center gap-2 rounded-full bg-emerald-500 px-4 py-2.5 shadow-lg shadow-emerald-500/20">
            <CheckCircle className="h-3.5 w-3.5 text-white shrink-0" />
            <span className="text-white text-[11px] font-medium whitespace-nowrap">{toast}</span>
          </div>
        </div>
      )}

      {/* ── 미리보기 모달 ── */}
      {showPreview && (
        <div
          className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-end sm:items-center justify-center"
          onClick={() => setShowPreview(false)}
        >
          <div
            className="relative w-full sm:max-w-2xl max-h-[90vh] sm:max-h-[85vh] rounded-t-2xl sm:rounded-2xl bg-white shadow-2xl overflow-hidden flex flex-col animate-in fade-in slide-in-from-bottom-4 sm:zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 모달 헤더 */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 shrink-0">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-blue-500" />
                <span className="text-sm font-bold text-gray-900">
                  {lang === "ko" ? "뉴스레터 미리보기" : "Newsletter Preview"}
                </span>
              </div>
              {/* KR / EN 토글 */}
              <div className="flex items-center gap-1 bg-gray-100 rounded-md p-0.5">
                <button
                  onClick={() => setPreviewLang("kr")}
                  className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                    previewLang === "kr"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  KR
                </button>
                <button
                  onClick={() => setPreviewLang("us")}
                  className={`px-2.5 py-1 rounded text-[11px] font-medium transition-colors ${
                    previewLang === "us"
                      ? "bg-white text-gray-900 shadow-sm"
                      : "text-gray-500 hover:text-gray-700"
                  }`}
                >
                  EN
                </button>
              </div>
              <button
                onClick={() => setShowPreview(false)}
                className="p-1.5 rounded-full hover:bg-gray-100 transition-colors"
              >
                <X className="h-4 w-4 text-gray-400" />
              </button>
            </div>
            {/* 뉴스레터 HTML */}
            <div className="flex-1 overflow-auto bg-white">
              {previewHtml ? (
                <iframe
                  key={previewLang}
                  srcDoc={previewHtml}
                  className="w-full border-0"
                  style={{ minHeight: "75vh" }}
                  sandbox="allow-same-origin"
                  title="Newsletter Preview"
                />
              ) : (
                <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
                  {lang === "ko" ? "로딩 중..." : "Loading..."}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

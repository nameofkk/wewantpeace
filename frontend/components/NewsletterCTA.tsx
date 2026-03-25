"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useAppStore } from "@/lib/store";
import { useMe, usePatchProfile } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Mail, X, Eye, ArrowRight } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://api.wewantpeace.live";
const DISMISSED_KEY = "wwp-newsletter-cta-dismissed";

export function NewsletterCTA() {
  const lang = useAppStore((s) => s.lang);
  const { data: me } = useMe();
  const patchProfile = usePatchProfile();

  const [dismissed, setDismissed] = useState(true);
  const [showPreview, setShowPreview] = useState(false);
  const [latestId, setLatestId] = useState<number | null>(null);
  const [subCount, setSubCount] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(DISMISSED_KEY) === "true");
    } catch {
      setDismissed(false);
    }
  }, []);

  useEffect(() => {
    fetch(`${API}/newsletter/archive`)
      .then((r) => r.json())
      .then((d) => { if (Array.isArray(d) && d.length > 0) setLatestId(d[0].id); })
      .catch(() => {});
    fetch(`${API}/newsletter/stats`)
      .then((r) => r.json())
      .then((d) => setSubCount(d.subscriber_count))
      .catch(() => {});
  }, []);

  const handleDismiss = useCallback(() => {
    setDismissed(true);
    try { localStorage.setItem(DISMISSED_KEY, "true"); } catch {}
  }, []);

  const isLoggedIn = !!me?.id;
  const isSubscribed = !!me?.marketing_agreed_at;

  const handleSubscribe = () => {
    if (!isLoggedIn) return;
    const turningOn = !isSubscribed;
    patchProfile.mutate(
      { marketing_agreed_at: turningOn ? "now" : "" },
      {
        onSuccess: () => {
          const msg = turningOn
            ? lang === "ko" ? "구독 완료! 매주 월요일 브리핑을 보내드릴게요" : "Subscribed! You'll get briefings every Monday"
            : lang === "ko" ? "구독이 해지되었습니다" : "Unsubscribed";
          setToast(msg);
          setTimeout(() => setToast(null), 3000);
        },
      },
    );
  };

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
        {/* Glow (호버 시 은은하게 퍼짐) */}
        <div className="absolute -inset-2 rounded-2xl bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-400 opacity-0 blur-xl transition-opacity duration-700 group-hover:opacity-[0.08]" />

        {/* 카드 본체 */}
        <div className="relative rounded-[11px] bg-card overflow-hidden">
          {/* 닫기 */}
          <button
            onClick={handleDismiss}
            className="absolute top-2.5 right-2.5 z-10 p-1 rounded-full hover:bg-muted/50 transition-colors"
            aria-label="Close"
          >
            <X className="h-3 w-3 text-muted-foreground/40" />
          </button>

          <div className="px-4 pt-4 pb-3.5">
            {/* 상태 뱃지 + 소셜프루프 */}
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

            {/* 액션 영역 */}
            <div className="flex items-center gap-2 mt-3.5">
              {isLoggedIn ? (
                isSubscribed ? (
                  /* 구독 중 → 심플 상태 표시 */
                  <div className="flex items-center gap-2 flex-1">
                    <div className="flex-1 h-9 rounded-lg bg-muted/20 flex items-center justify-center gap-1.5">
                      <span className="text-[11px] font-medium text-muted-foreground">
                        {lang === "ko" ? "구독 중" : "Subscribed"}
                      </span>
                      <span className="text-emerald-400 text-[11px]">&#10003;</span>
                    </div>
                    <button
                      onClick={handleSubscribe}
                      disabled={patchProfile.isPending}
                      className="text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors shrink-0"
                    >
                      {lang === "ko" ? "해지" : "Cancel"}
                    </button>
                  </div>
                ) : (
                  /* 미구독 → CTA 버튼 (shine sweep 효과) */
                  <button
                    onClick={handleSubscribe}
                    disabled={patchProfile.isPending}
                    className="relative flex-1 h-9 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-[11px] font-semibold overflow-hidden
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
                <Link href="/login" className="flex-1">
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

              {/* 샘플 보기 */}
              {latestId !== null && (
                <button
                  onClick={() => setShowPreview(true)}
                  className="h-9 px-3 rounded-lg border border-border/60 text-[10px] font-medium text-muted-foreground hover:border-blue-500/30 hover:text-foreground transition-colors flex items-center gap-1 shrink-0"
                >
                  <Eye className="h-3 w-3" />
                  {lang === "ko" ? "샘플" : "Sample"}
                </button>
              )}
            </div>

            {/* 하단 */}
            <p className="text-[9px] text-muted-foreground/30 text-center mt-2.5">
              {lang === "ko"
                ? "무료 · 3분 분량 · 언제든 해지"
                : "Free · 3 min read · Cancel anytime"}
            </p>
          </div>
        </div>
      </div>

      {/* ── 토스트 ── */}
      {toast && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-[110] animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className="flex items-center gap-2 rounded-full bg-emerald-500 px-4 py-2 shadow-lg shadow-emerald-500/20">
            <span className="text-white text-[11px] font-medium">{toast}</span>
          </div>
        </div>
      )}

      {/* ── 미리보기 모달 ── */}
      {showPreview && latestId !== null && (
        <div
          className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowPreview(false)}
        >
          <div
            className="relative w-full max-w-lg max-h-[85vh] rounded-2xl bg-white shadow-2xl overflow-hidden flex flex-col animate-in fade-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 shrink-0">
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-blue-500" />
                <span className="text-sm font-bold text-gray-900">
                  {lang === "ko" ? "지난 뉴스레터 샘플" : "Newsletter Sample"}
                </span>
              </div>
              <button
                onClick={() => setShowPreview(false)}
                className="p-1.5 rounded-full hover:bg-gray-100 transition-colors"
              >
                <X className="h-4 w-4 text-gray-400" />
              </button>
            </div>
            <div className="flex-1 overflow-auto bg-gray-50">
              <iframe
                src={`${API}/newsletter/archive/${latestId}`}
                className="w-full border-0"
                style={{ minHeight: "70vh" }}
                title="Newsletter Preview"
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

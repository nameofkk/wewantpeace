"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useAppStore } from "@/lib/store";
import { useMe, usePatchProfile } from "@/lib/api";
import { t } from "@/lib/i18n";
import { Mail, X, Eye } from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "https://api.wewantpeace.live";
const DISMISSED_KEY = "wwp-newsletter-cta-dismissed";

export function NewsletterCTA() {
  const lang = useAppStore((s) => s.lang);
  const { data: me } = useMe();
  const patchProfile = usePatchProfile();

  const [dismissed, setDismissed] = useState(true);
  const [showPreview, setShowPreview] = useState(false);
  const [latestId, setLatestId] = useState<number | null>(null);

  useEffect(() => {
    try {
      setDismissed(localStorage.getItem(DISMISSED_KEY) === "true");
    } catch {
      setDismissed(false);
    }
  }, []);

  // 최신 뉴스레터 1개 ID만 가져옴
  useEffect(() => {
    fetch(`${API}/newsletter/archive`)
      .then((r) => r.json())
      .then((d) => { if (Array.isArray(d) && d.length > 0) setLatestId(d[0].id); })
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
    patchProfile.mutate({ marketing_agreed_at: isSubscribed ? "" : "now" });
  };

  if (dismissed) return null;

  return (
    <>
      <div className="relative rounded-xl border border-border bg-card overflow-hidden">
        {/* 닫기 */}
        <button
          onClick={handleDismiss}
          className="absolute top-2.5 right-2.5 z-10 p-1 rounded-full hover:bg-muted/50 transition-colors"
          aria-label="Close"
        >
          <X className="h-3 w-3 text-muted-foreground/40" />
        </button>

        <div className="px-4 pt-4 pb-3">
          {/* 타이틀 라인 */}
          <div className="flex items-center gap-2 mb-1.5">
            <div className="flex items-center justify-center h-6 w-6 rounded-md bg-blue-500/10">
              <Mail className="h-3 w-3 text-blue-500" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-bold text-foreground leading-tight">
                {t(lang, "newsletter_title")}
              </p>
              <p className="text-[9px] text-muted-foreground leading-tight">
                {t(lang, "newsletter_desc")}
              </p>
            </div>
          </div>

          {/* 액션 영역 */}
          <div className="flex items-center gap-2 mt-3">
            {isLoggedIn ? (
              <>
                <button
                  onClick={handleSubscribe}
                  disabled={patchProfile.isPending}
                  className={`flex-1 h-8 rounded-lg text-[11px] font-semibold transition-all ${
                    isSubscribed
                      ? "bg-muted/30 text-muted-foreground hover:bg-muted/50"
                      : "bg-blue-500 text-white hover:bg-blue-600 active:scale-[0.98]"
                  }`}
                >
                  {isSubscribed
                    ? lang === "ko" ? "구독 중" : "Subscribed"
                    : lang === "ko" ? "무료 구독" : "Subscribe Free"}
                </button>
                {latestId !== null && (
                  <button
                    onClick={() => setShowPreview(true)}
                    className="h-8 px-3 rounded-lg border border-border text-[11px] font-medium text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors flex items-center gap-1"
                  >
                    <Eye className="h-3 w-3" />
                    {lang === "ko" ? "샘플" : "Sample"}
                  </button>
                )}
              </>
            ) : (
              <>
                <Link href="/login" className="flex-1">
                  <div className="h-8 rounded-lg bg-blue-500 text-white flex items-center justify-center text-[11px] font-semibold hover:bg-blue-600 transition-colors active:scale-[0.98]">
                    {lang === "ko" ? "로그인하고 구독" : "Login to Subscribe"}
                  </div>
                </Link>
                {latestId !== null && (
                  <button
                    onClick={() => setShowPreview(true)}
                    className="h-8 px-3 rounded-lg border border-border text-[11px] font-medium text-muted-foreground hover:bg-muted/30 hover:text-foreground transition-colors flex items-center gap-1"
                  >
                    <Eye className="h-3 w-3" />
                    {lang === "ko" ? "샘플" : "Sample"}
                  </button>
                )}
              </>
            )}
          </div>

          {/* 하단 부가 정보 */}
          <p className="text-[9px] text-muted-foreground/40 text-center mt-2">
            {lang === "ko"
              ? "매주 월요일 발송 · 무료 · 언제든 해지"
              : "Every Monday · Free · Cancel anytime"}
          </p>
        </div>
      </div>

      {/* 미리보기 모달 */}
      {showPreview && latestId !== null && (
        <div
          className="fixed inset-0 z-[100] bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setShowPreview(false)}
        >
          <div
            className="relative w-full max-w-lg max-h-[85vh] rounded-2xl bg-white shadow-2xl overflow-hidden flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 모달 헤더 */}
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
            {/* 뉴스레터 HTML */}
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

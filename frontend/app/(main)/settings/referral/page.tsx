"use client";

import { useState, useEffect } from "react";
import { ArrowLeft, Copy, Check, Share2, Gift, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { t, type Lang } from "@/lib/i18n";
import { API_BASE } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { trackEvent } from "@/lib/analytics";

interface ReferralData {
  referral_code: string;
  referral_url: string;
  total_invited: number;
  total_activated: number;
  rewards: Array<{
    referee_name: string;
    reward_type: string;
    rewarded: boolean;
    activated: boolean;
    created_at: string | null;
  }>;
}

export default function ReferralPage() {
  const lang = useAppStore((s) => s.lang);
  const router = useRouter();
  const { user } = useAuth();
  const [data, setData] = useState<ReferralData | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!user) return;
    user.getIdToken().then(async (token) => {
      try {
        const res = await fetch(`${API_BASE}/me/referral`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setData(await res.json());
      } catch {}
      setLoading(false);
    });
  }, [user]);

  async function handleCopy() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.referral_code);
      setCopied(true);
      trackEvent("referral_copy", { code: data.referral_code });
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  }

  async function handleShare() {
    if (!data) return;
    trackEvent("referral_share", { code: data.referral_code });

    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share({
          title: "WeWantPeace",
          text: lang === "ko"
            ? "WeWantPeace에서 전 세계 분쟁 이슈를 실시간으로 추적하세요!"
            : "Track global conflict issues in real time with WeWantPeace!",
          url: data.referral_url,
        });
        return;
      } catch {}
    }

    try {
      await navigator.clipboard.writeText(data.referral_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center h-screen gap-3">
        <p className="text-sm text-muted-foreground">
          {lang === "ko" ? "로그인이 필요합니다" : "Login required"}
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <div className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur-sm px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => router.back()} className="rounded-lg p-1.5 hover:bg-secondary transition-colors">
            <ArrowLeft className="h-5 w-5" />
          </button>
          <h1 className="text-sm font-bold">{t(lang, "referral_title")}</h1>
        </div>
      </div>

      <div className="px-4 py-6 space-y-6 max-w-lg mx-auto w-full">
        {/* Hero */}
        <div className="text-center space-y-2">
          <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
            <Gift className="h-8 w-8 text-primary" />
          </div>
          <h2 className="text-lg font-bold">{t(lang, "referral_title")}</h2>
          <p className="text-sm text-muted-foreground">{t(lang, "referral_subtitle")}</p>
        </div>

        {data && (
          <>
            {/* Code card */}
            <div className="rounded-xl border border-border bg-card p-5 space-y-4">
              <p className="text-xs text-muted-foreground">{t(lang, "referral_my_code")}</p>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-secondary rounded-lg px-4 py-3 text-center">
                  <span className="text-2xl font-bold tracking-wider font-mono">{data.referral_code}</span>
                </div>
                <button
                  onClick={handleCopy}
                  className="rounded-lg border border-border p-3 hover:bg-secondary transition-colors"
                >
                  {copied ? <Check className="h-5 w-5 text-green-500" /> : <Copy className="h-5 w-5" />}
                </button>
              </div>

              <button
                onClick={handleShare}
                className="w-full flex items-center justify-center gap-2 rounded-lg bg-primary text-primary-foreground py-3 text-sm font-medium hover:bg-primary/90 transition-colors"
              >
                <Share2 className="h-4 w-4" />
                {t(lang, "referral_share")}
              </button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-xl border border-border bg-card p-4 text-center">
                <p className="text-2xl font-bold">{data.total_invited}</p>
                <p className="text-xs text-muted-foreground">
                  {t(lang, "referral_count", { n: data.total_invited })}
                </p>
              </div>
              <div className="rounded-xl border border-border bg-card p-4 text-center">
                <p className="text-2xl font-bold">{data.total_activated}</p>
                <p className="text-xs text-muted-foreground">
                  {lang === "ko" ? "보상 지급됨" : "Rewards given"}
                </p>
              </div>
            </div>

            {/* Rewards list */}
            {data.rewards.length > 0 && (
              <div className="rounded-xl border border-border bg-card overflow-hidden">
                <div className="px-4 py-3 border-b border-border">
                  <h3 className="text-xs font-semibold">
                    {lang === "ko" ? "초대 내역" : "Invite History"}
                  </h3>
                </div>
                <div className="divide-y divide-border">
                  {data.rewards.map((r, i) => (
                    <div key={i} className="flex items-center justify-between px-4 py-3">
                      <div>
                        <p className="text-sm font-medium">{r.referee_name}</p>
                        <p className="text-[10px] text-muted-foreground">
                          {r.created_at ? new Date(r.created_at).toLocaleDateString(lang === "en" ? "en-US" : "ko-KR") : ""}
                        </p>
                      </div>
                      <span className={`text-[10px] font-medium px-2 py-1 rounded-full ${
                        r.rewarded ? "bg-green-500/10 text-green-500" : "bg-yellow-500/10 text-yellow-500"
                      }`}>
                        {r.rewarded ? t(lang, "referral_reward_given") : t(lang, "referral_reward_pending")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import Image from "next/image";
import { LogIn, Globe } from "lucide-react";
import { useAppStore } from "@/lib/store";

const FEATURES = [
  {
    emoji: "🌍",
    ko: "전세계 갈등·분쟁 실시간 모니터링",
    en: "Real-time global conflict monitoring",
  },
  {
    emoji: "📊",
    ko: "K-Score 국가별 긴장도 지수",
    en: "K-Score country tension index",
  },
  {
    emoji: "🔔",
    ko: "검증된 뉴스만 알림 발송",
    en: "Alerts for verified news only",
  },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { lang } = useAppStore();

  function handleLogin() {
    localStorage.setItem("onboarding_done", "true");
    router.push("/login");
  }

  function handleGuest() {
    localStorage.setItem("onboarding_done", "true");
    router.push("/home");
  }

  return (
    <div className="relative flex flex-col min-h-screen bg-background overflow-hidden">
      {/* 배경 그라디언트 */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% 0%, rgba(99,102,241,0.15) 0%, transparent 70%)",
        }}
      />

      {/* 콘텐츠 — 세로 중앙 정렬 */}
      <div className="relative flex flex-1 flex-col items-center justify-center px-6 py-12 text-center">
        {/* 로고 */}
        <div
          className="mb-2 flex flex-col items-center gap-4"
          style={{ animation: "fadeSlideUp 0.6s ease-out both" }}
        >
          <div
            className="relative h-20 w-40"
            style={{ animation: "floatBob 4s ease-in-out infinite" }}
          >
            <Image
              src="/logo-eye.png"
              alt="WeWantPeace"
              fill
              className="object-contain"
              priority
            />
          </div>
          <h1 className="text-3xl font-black tracking-tight">WeWantPeace</h1>
        </div>

        {/* 서비스 설명 */}
        <p
          className="mb-8 max-w-xs text-sm leading-relaxed text-muted-foreground"
          style={{ animation: "fadeSlideUp 0.6s ease-out 0.1s both" }}
        >
          {lang === "ko" ? (
            <>전세계 분쟁·긴장 이슈를 실시간 분석해<br />검증된 중요 소식만 전달합니다</>
          ) : (
            <>Global conflicts analyzed in real time<br />Only verified critical updates delivered</>
          )}
        </p>

        {/* 특징 3가지 */}
        <div className="mb-10 w-full max-w-xs space-y-2.5">
          {FEATURES.map((item, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-xl border border-border/60 bg-card/60 px-4 py-3"
              style={{ animation: `fadeSlideUp 0.5s ease-out ${0.15 + i * 0.08}s both` }}
            >
              <span className="text-xl leading-none">{item.emoji}</span>
              <span className="text-left text-sm text-muted-foreground">
                {lang === "ko" ? item.ko : item.en}
              </span>
            </div>
          ))}
        </div>

        {/* 버튼 */}
        <div
          className="w-full max-w-xs space-y-3"
          style={{ animation: "fadeSlideUp 0.5s ease-out 0.4s both" }}
        >
          <button
            onClick={handleLogin}
            className="w-full flex items-center justify-center gap-2 rounded-2xl py-4 text-base font-bold transition-all active:scale-95"
            style={{
              background:
                "linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary)/0.85) 100%)",
              color: "hsl(var(--primary-foreground))",
              boxShadow: "0 4px 24px rgba(99,102,241,0.3)",
            }}
          >
            <LogIn className="h-5 w-5" />
            {lang === "ko" ? "로그인하기" : "Sign In"}
          </button>

          <button
            onClick={handleGuest}
            className="w-full flex items-center justify-center gap-2 rounded-2xl border border-border py-3.5 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground active:scale-95"
          >
            <Globe className="h-4 w-4" />
            {lang === "ko" ? "게스트로 시작" : "Continue as Guest"}
          </button>
        </div>
      </div>

      <style jsx global>{`
        @keyframes floatBob {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-10px); }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

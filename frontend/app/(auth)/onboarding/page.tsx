"use client";

import { useRouter } from "next/navigation";
import Image from "next/image";
import { useState, useEffect, useRef } from "react";
import {
  LogIn,
  Globe,
  Smartphone,
  Shield,
  Activity,
  Radio,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { isAndroidBrowser, isIOSBrowser, isMobileBrowser } from "@/lib/platform-detect";

const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.wewantpeace.app";
const APP_STORE_URL = "https://apps.apple.com/app/wewantpeace/id0000000000"; // TODO: 실제 ID

/** 실시간 스캔 로그 */
const SCAN_KO = [
  "분쟁 이벤트 3건 감지 — 중동",
  "긴장도 지수 업데이트 — 동유럽",
  "뉴스 수집 완료 — 85개 소스",
  "이슈 클러스터 생성 — 동아시아",
  "K-Score 재계산 — 47개국",
  "확인 완료: AP·Reuters 교차검증",
  "시위 이슈 감지 — 남미",
  "해양 분쟁 모니터링 — 남중국해",
];
const SCAN_EN = [
  "3 conflict events — Middle East",
  "Tension index updated — E. Europe",
  "News collected — 85 sources",
  "Issue cluster created — East Asia",
  "K-Score recalculated — 47 countries",
  "Verified: AP·Reuters cross-check",
  "Protest detected — South America",
  "Maritime dispute — South China Sea",
];

export default function OnboardingPage() {
  const router = useRouter();
  const { lang } = useAppStore();
  const [scanLines, setScanLines] = useState<string[]>([]);
  const scanIdx = useRef(0);
  const [counts, setCounts] = useState({ c: 0, s: 0, e: 0 });

  // 카운터 애니메이션
  useEffect(() => {
    const targets = { c: 50, s: 120, e: 1400 };
    const steps = 35;
    let step = 0;
    const timer = setInterval(() => {
      step++;
      const ease = 1 - Math.pow(1 - step / steps, 4);
      setCounts({
        c: Math.round(targets.c * ease),
        s: Math.round(targets.s * ease),
        e: Math.round(targets.e * ease),
      });
      if (step >= steps) clearInterval(timer);
    }, 50);
    return () => clearInterval(timer);
  }, []);

  // 스캔 로그
  useEffect(() => {
    const events = lang === "ko" ? SCAN_KO : SCAN_EN;
    const t1 = setTimeout(() => {
      setScanLines([events[0]]);
      scanIdx.current = 1;
    }, 600);
    const interval = setInterval(() => {
      const idx = scanIdx.current % events.length;
      setScanLines((prev) => [events[idx], ...prev].slice(0, 2));
      scanIdx.current++;
    }, 2200);
    return () => { clearTimeout(t1); clearInterval(interval); };
  }, [lang]);

  function handleLogin() {
    localStorage.setItem("onboarding_done", "true");
    router.push("/login");
  }
  function handleGuest() {
    localStorage.setItem("onboarding_done", "true");
    router.push("/home");
  }

  const isMobile = typeof navigator !== "undefined" && isMobileBrowser();
  const isAndroid = typeof navigator !== "undefined" && isAndroidBrowser();
  const isIOS = typeof navigator !== "undefined" && isIOSBrowser();

  return (
    <div className="relative flex flex-col h-[100dvh] bg-background overflow-hidden">
      {/* 배경 그라디언트 */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% 0%, rgba(59,130,246,0.12) 0%, transparent 60%)",
        }}
      />

      {/* 콘텐츠 — dvh 기준 한 화면 */}
      <div className="relative flex flex-1 flex-col items-center justify-center gap-4 px-5 py-6">
        {/* 상단: 로고 + LIVE + 설명 */}
        <div className="flex flex-col items-center text-center">
          {/* 로고 + 레이더 파동 */}
          <div
            className="relative mb-1 flex items-center justify-center"
            style={{ width: 120, height: 56, animation: "fadeSlideUp 0.5s ease-out both" }}
          >
            {/* 레이더 링 */}
            <div className="ob-radar-ring ob-radar-ring--1" />
            <div className="ob-radar-ring ob-radar-ring--2" />
            <div className="ob-radar-ring ob-radar-ring--3" />
            <Image
              src="/logo-eye.png"
              alt="WeWantPeace"
              width={120}
              height={52}
              className="relative z-10 object-contain"
              priority
            />
          </div>
          <h1 className="text-2xl font-black tracking-tight" style={{ animation: "fadeSlideUp 0.5s ease-out 0.05s both" }}>
            WeWantPeace
          </h1>
          {/* LIVE 배지 */}
          <div className="mt-1.5 flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5"
            style={{ animation: "fadeSlideUp 0.5s ease-out 0.1s both" }}>
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
            </span>
            <span className="text-[10px] font-semibold tracking-wide text-emerald-400">
              {lang === "ko" ? "실시간 모니터링 중" : "LIVE MONITORING"}
            </span>
          </div>
          {/* 서비스 설명 */}
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground max-w-[260px] whitespace-pre-line"
            style={{ animation: "fadeSlideUp 0.5s ease-out 0.15s both" }}>
            {lang === "ko"
              ? "전세계 분쟁·긴장 이슈를 실시간 수집·분석해\n검증된 중요 소식만 전달합니다"
              : "Real-time collection & analysis of global conflicts\nOnly verified alerts delivered"}
          </p>
        </div>

        {/* 중간: 스캔 피드 + 통계 */}
        <div className="w-full max-w-xs flex flex-col gap-2.5">
          {/* 스캔 피드 */}
          <div
            className="rounded-lg border border-border/40 bg-card/40 backdrop-blur-sm overflow-hidden"
            style={{ animation: "fadeSlideUp 0.4s ease-out 0.2s both" }}
          >
            <div className="flex items-center gap-1.5 border-b border-border/30 px-3 py-1.5">
              <Activity className="h-3 w-3 text-emerald-400 ob-pulse-icon" />
              <span className="text-[10px] font-medium text-muted-foreground tracking-wide">SCANNING</span>
            </div>
            <div className="px-3 py-2 space-y-1 min-h-[40px]">
              {scanLines.map((line, i) => (
                <div
                  key={`${line}-${i}`}
                  className="flex items-start gap-1.5"
                  style={{
                    animation: "scanLineIn 0.3s ease-out both",
                    opacity: i === 0 ? 1 : 0.4,
                  }}
                >
                  <Radio className="h-2.5 w-2.5 mt-[3px] flex-shrink-0 text-blue-400" />
                  <span className="text-[10px] leading-tight text-muted-foreground font-mono">{line}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 통계 카운터 */}
          <div
            className="grid grid-cols-3 gap-2"
            style={{ animation: "fadeSlideUp 0.4s ease-out 0.25s both" }}
          >
            {[
              { v: `${counts.c}+`, l: lang === "ko" ? "모니터링 국가" : "Countries" },
              { v: `${counts.s}+`, l: lang === "ko" ? "뉴스 소스" : "Sources" },
              { v: `${counts.e.toLocaleString()}+`, l: lang === "ko" ? "수집 이벤트" : "Events" },
            ].map((item) => (
              <div key={item.l} className="flex flex-col items-center rounded-lg border border-border/40 bg-card/30 py-2">
                <span className="text-lg font-black text-foreground tabular-nums">{item.v}</span>
                <span className="text-[9px] text-muted-foreground">{item.l}</span>
              </div>
            ))}
          </div>

          {/* 신뢰 배지 */}
          <div className="flex items-center justify-center gap-1.5 text-[10px] text-muted-foreground/60"
            style={{ animation: "fadeSlideUp 0.4s ease-out 0.3s both" }}>
            <Shield className="h-3 w-3" />
            <span>{lang === "ko" ? "AP · Reuters · 정부 공식 발표 기반 검증" : "Verified via AP · Reuters · official sources"}</span>
          </div>
        </div>

        {/* 하단: 버튼 + 앱 다운로드 */}
        <div className="w-full max-w-xs flex flex-col gap-2">
          {/* CTA 버튼 */}
          <div style={{ animation: "fadeSlideUp 0.4s ease-out 0.35s both" }}>
            <button
              onClick={handleLogin}
              className="w-full flex items-center justify-center gap-2 rounded-2xl py-3.5 text-[15px] font-bold transition-all active:scale-95"
              style={{
                background: "linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary)/0.85) 100%)",
                color: "hsl(var(--primary-foreground))",
                boxShadow: "0 4px 20px rgba(99,102,241,0.3)",
              }}
            >
              <LogIn className="h-4.5 w-4.5" />
              {lang === "ko" ? "로그인하기" : "Sign In"}
            </button>
          </div>

          <button
            onClick={handleGuest}
            className="w-full flex items-center justify-center gap-2 rounded-2xl border border-border py-3 text-sm font-medium text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground active:scale-95"
            style={{ animation: "fadeSlideUp 0.4s ease-out 0.4s both" }}
          >
            <Globe className="h-4 w-4" />
            {lang === "ko" ? "게스트로 둘러보기" : "Browse as Guest"}
          </button>

          {/* 앱 다운로드 */}
          <div style={{ animation: "fadeSlideUp 0.4s ease-out 0.45s both" }}>
            <div className="flex items-center gap-2 mb-1.5">
              <div className="flex-1 h-px bg-border/40" />
              <span className="text-[10px] text-muted-foreground/50 flex items-center gap-1">
                <Smartphone className="h-3 w-3" />
                {lang === "ko" ? "앱 다운로드" : "Download App"}
              </span>
              <div className="flex-1 h-px bg-border/40" />
            </div>
            <div className="flex gap-2">
              {(!isMobile || isAndroid) && (
                <a href={PLAY_STORE_URL} target="_blank" rel="noopener noreferrer"
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-border/40 bg-card/30 py-2 text-[11px] font-medium text-muted-foreground hover:border-primary/30 hover:text-foreground transition-colors">
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M3.609 1.814L13.792 12 3.61 22.186a.996.996 0 0 1-.61-.92V2.734a1 1 0 0 1 .609-.92zm10.89 10.893l2.302 2.302-10.937 6.333 8.635-8.635zm3.199-3.199l2.302 2.302a1 1 0 0 1 0 1.38l-2.302 2.302L15.137 12l2.561-2.492zM5.864 2.658L16.8 8.99l-2.302 2.302L5.864 2.658z"/>
                  </svg>
                  Google Play
                </a>
              )}
              {(!isMobile || isIOS) && (
                <a href={APP_STORE_URL} target="_blank" rel="noopener noreferrer"
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-border/40 bg-card/30 py-2 text-[11px] font-medium text-muted-foreground hover:border-primary/30 hover:text-foreground transition-colors">
                  <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                  </svg>
                  App Store
                </a>
              )}
            </div>
          </div>
        </div>
      </div>

      <style jsx global>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes scanLineIn {
          from { opacity: 0; transform: translateX(-6px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes radarPulse {
          0% { transform: translate(-50%,-50%) scale(0.5); opacity: 0.6; }
          100% { transform: translate(-50%,-50%) scale(2.2); opacity: 0; }
        }
        .ob-radar-ring {
          position: absolute;
          top: 50%; left: 50%;
          width: 80px; height: 80px;
          border-radius: 50%;
          border: 1px solid rgba(59,130,246,0.2);
          transform: translate(-50%,-50%) scale(0.5);
          animation: radarPulse 3.5s ease-out infinite;
          pointer-events: none;
        }
        .ob-radar-ring--2 { animation-delay: 1.2s; }
        .ob-radar-ring--3 { animation-delay: 2.4s; }
        .ob-pulse-icon {
          animation: iconPulse 2s ease-in-out infinite;
        }
        @keyframes iconPulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

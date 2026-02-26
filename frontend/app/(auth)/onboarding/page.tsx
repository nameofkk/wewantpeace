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
  MapPin,
  Bell,
  BarChart3,
  Radar,
} from "lucide-react";
import { useAppStore } from "@/lib/store";
import { isAndroidBrowser, isIOSBrowser, isMobileBrowser } from "@/lib/platform-detect";

const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.wewantpeace.app";
const APP_STORE_URL = "https://apps.apple.com/app/wewantpeace/id0000000000"; // TODO: 실제 ID

const FEATURES = [
  {
    icon: Radar,
    ko: "50개국+ 분쟁·긴장 실시간 모니터링",
    en: "Real-time monitoring of 50+ countries",
    subKo: "10가지 카테고리 · AI 자동 분류",
    subEn: "10 categories · AI-powered classification",
  },
  {
    icon: BarChart3,
    ko: "K-Score 긴장도 지수",
    en: "K-Score Tension Index",
    subKo: "국가별 위험도 정량 분석 · 30일 추이",
    subEn: "Quantified risk analysis · 30-day trends",
  },
  {
    icon: MapPin,
    ko: "글로벌 이슈 맵",
    en: "Global Issue Map",
    subKo: "실시간 이슈 분포 · 심각도별 시각화",
    subEn: "Live issue distribution · severity visualization",
  },
  {
    icon: Bell,
    ko: "검증된 뉴스 알림",
    en: "Verified News Alerts",
    subKo: "AP·Reuters 등 공신력 있는 소스 기반",
    subEn: "Based on AP, Reuters and trusted sources",
  },
];

/** 실시간 스캔 로그에 표시할 이벤트 목록 */
const SCAN_EVENTS_KO = [
  "분쟁 이벤트 3건 감지 — 중동",
  "긴장도 지수 업데이트 — 동유럽",
  "신규 뉴스 수집 완료 — 85개 소스",
  "이슈 클러스터 생성 — 동아시아",
  "K-Score 재계산 완료 — 47개국",
  "제재 관련 이슈 분류 — 유럽",
  "사이버 위협 탐지 — 북미",
  "확인 완료: AP, Reuters 교차검증",
  "시위 이슈 감지 — 남미",
  "해양 분쟁 모니터링 — 남중국해",
];
const SCAN_EVENTS_EN = [
  "3 conflict events detected — Middle East",
  "Tension index updated — Eastern Europe",
  "News collection complete — 85 sources",
  "Issue cluster created — East Asia",
  "K-Score recalculated — 47 countries",
  "Sanctions issue classified — Europe",
  "Cyber threat detected — North America",
  "Verified: AP, Reuters cross-checked",
  "Protest detected — South America",
  "Maritime dispute monitoring — South China Sea",
];

export default function OnboardingPage() {
  const router = useRouter();
  const { lang } = useAppStore();
  const [scanLines, setScanLines] = useState<string[]>([]);
  const scanIdx = useRef(0);
  const [countryCount, setCountryCount] = useState(0);
  const [sourceCount, setSourceCount] = useState(0);
  const [eventCount, setEventCount] = useState(0);

  // 카운터 애니메이션
  useEffect(() => {
    const targets = { country: 50, source: 120, event: 1400 };
    const duration = 2000;
    const steps = 40;
    const interval = duration / steps;
    let step = 0;
    const timer = setInterval(() => {
      step++;
      const progress = step / steps;
      // easeOutQuart
      const ease = 1 - Math.pow(1 - progress, 4);
      setCountryCount(Math.round(targets.country * ease));
      setSourceCount(Math.round(targets.source * ease));
      setEventCount(Math.round(targets.event * ease));
      if (step >= steps) clearInterval(timer);
    }, interval);
    return () => clearInterval(timer);
  }, []);

  // 스캔 로그 애니메이션
  useEffect(() => {
    const events = lang === "ko" ? SCAN_EVENTS_KO : SCAN_EVENTS_EN;
    // 초기 1개
    const t1 = setTimeout(() => {
      setScanLines([events[0]]);
      scanIdx.current = 1;
    }, 800);

    const interval = setInterval(() => {
      const idx = scanIdx.current % events.length;
      setScanLines((prev) => {
        const next = [events[idx], ...prev];
        return next.slice(0, 3);
      });
      scanIdx.current++;
    }, 2400);

    return () => {
      clearTimeout(t1);
      clearInterval(interval);
    };
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
    <div className="relative flex flex-col min-h-screen bg-background overflow-hidden">
      {/* 배경 그라디언트 */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% 0%, rgba(59,130,246,0.12) 0%, transparent 60%), radial-gradient(ellipse 60% 40% at 80% 80%, rgba(99,102,241,0.08) 0%, transparent 50%)",
        }}
      />

      {/* 레이더 펄스 배경 */}
      <div className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/3 w-[500px] h-[500px]">
        <div className="ob-radar-ring ob-radar-ring--1" />
        <div className="ob-radar-ring ob-radar-ring--2" />
        <div className="ob-radar-ring ob-radar-ring--3" />
      </div>

      {/* 콘텐츠 */}
      <div className="relative flex flex-1 flex-col items-center px-6 pt-14 pb-10 text-center">
        {/* 로고 + LIVE 배지 */}
        <div
          className="mb-1 flex flex-col items-center gap-3"
          style={{ animation: "fadeSlideUp 0.6s ease-out both" }}
        >
          <div className="relative h-20 w-[184px]" style={{ animation: "floatBob 4s ease-in-out infinite" }}>
            <Image src="/logo-eye.png" alt="WeWantPeace" fill className="object-contain" priority />
          </div>
          <h1 className="text-3xl font-black tracking-tight">WeWantPeace</h1>
          {/* LIVE 배지 */}
          <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            </span>
            <span className="text-[11px] font-semibold tracking-wide text-emerald-400">
              {lang === "ko" ? "실시간 모니터링 중" : "LIVE MONITORING"}
            </span>
          </div>
        </div>

        {/* 서비스 설명 */}
        <p
          className="mt-3 mb-5 max-w-xs text-sm leading-relaxed text-muted-foreground"
          style={{ animation: "fadeSlideUp 0.6s ease-out 0.1s both" }}
        >
          {lang === "ko" ? (
            <>전세계 분쟁·긴장 이슈를 AI가 실시간 수집·분석해<br />검증된 중요 소식만 전달합니다</>
          ) : (
            <>AI-powered real-time collection &amp; analysis<br />of global conflicts — only verified alerts</>
          )}
        </p>

        {/* 실시간 스캔 피드 */}
        <div
          className="mb-5 w-full max-w-xs rounded-xl border border-border/40 bg-card/40 backdrop-blur-sm overflow-hidden"
          style={{ animation: "fadeSlideUp 0.5s ease-out 0.15s both" }}
        >
          <div className="flex items-center gap-2 border-b border-border/30 px-3 py-2">
            <Activity className="h-3.5 w-3.5 text-emerald-400 ob-pulse-icon" />
            <span className="text-[11px] font-medium text-muted-foreground tracking-wide">
              {lang === "ko" ? "SCANNING" : "SCANNING"}
            </span>
          </div>
          <div className="px-3 py-2.5 space-y-1.5 min-h-[72px]">
            {scanLines.map((line, i) => (
              <div
                key={`${line}-${i}`}
                className="flex items-start gap-2 text-left"
                style={{
                  animation: "scanLineIn 0.4s ease-out both",
                  opacity: i === 0 ? 1 : 0.5 - i * 0.15,
                }}
              >
                <Radio className="h-3 w-3 mt-0.5 flex-shrink-0 text-blue-400" />
                <span className="text-[11px] leading-tight text-muted-foreground font-mono">{line}</span>
              </div>
            ))}
          </div>
        </div>

        {/* 통계 카운터 */}
        <div
          className="mb-6 grid grid-cols-3 gap-3 w-full max-w-xs"
          style={{ animation: "fadeSlideUp 0.5s ease-out 0.2s both" }}
        >
          <div className="flex flex-col items-center rounded-xl border border-border/40 bg-card/30 py-3">
            <span className="text-xl font-black text-foreground tabular-nums">{countryCount}+</span>
            <span className="text-[10px] text-muted-foreground mt-0.5">
              {lang === "ko" ? "모니터링 국가" : "Countries"}
            </span>
          </div>
          <div className="flex flex-col items-center rounded-xl border border-border/40 bg-card/30 py-3">
            <span className="text-xl font-black text-foreground tabular-nums">{sourceCount}+</span>
            <span className="text-[10px] text-muted-foreground mt-0.5">
              {lang === "ko" ? "뉴스 소스" : "Sources"}
            </span>
          </div>
          <div className="flex flex-col items-center rounded-xl border border-border/40 bg-card/30 py-3">
            <span className="text-xl font-black text-foreground tabular-nums">{eventCount.toLocaleString()}+</span>
            <span className="text-[10px] text-muted-foreground mt-0.5">
              {lang === "ko" ? "수집 이벤트" : "Events"}
            </span>
          </div>
        </div>

        {/* 특징 4가지 */}
        <div className="mb-7 w-full max-w-xs space-y-2">
          {FEATURES.map((item, i) => {
            const Icon = item.icon;
            return (
              <div
                key={i}
                className="flex items-start gap-3 rounded-xl border border-border/50 bg-card/50 px-4 py-3 text-left"
                style={{ animation: `fadeSlideUp 0.5s ease-out ${0.25 + i * 0.07}s both` }}
              >
                <div className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Icon className="h-4 w-4 text-primary" />
                </div>
                <div className="min-w-0">
                  <p className="text-[13px] font-semibold text-foreground leading-tight">
                    {lang === "ko" ? item.ko : item.en}
                  </p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {lang === "ko" ? item.subKo : item.subEn}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* 신뢰 배지 */}
        <div
          className="mb-6 flex items-center gap-2 text-[11px] text-muted-foreground/70"
          style={{ animation: "fadeSlideUp 0.5s ease-out 0.55s both" }}
        >
          <Shield className="h-3.5 w-3.5" />
          <span>
            {lang === "ko"
              ? "AP · Reuters · 정부 공식 발표 기반 검증"
              : "Verified via AP · Reuters · official sources"}
          </span>
        </div>

        {/* 버튼 */}
        <div
          className="w-full max-w-xs space-y-3"
          style={{ animation: "fadeSlideUp 0.5s ease-out 0.5s both" }}
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
            {lang === "ko" ? "게스트로 둘러보기" : "Browse as Guest"}
          </button>
        </div>

        {/* 앱 다운로드 섹션 */}
        <div
          className="mt-6 w-full max-w-xs"
          style={{ animation: "fadeSlideUp 0.5s ease-out 0.6s both" }}
        >
          <div className="flex items-center gap-2 mb-3">
            <div className="flex-1 h-px bg-border/50" />
            <span className="text-[11px] text-muted-foreground/60 flex items-center gap-1.5">
              <Smartphone className="h-3 w-3" />
              {lang === "ko" ? "앱 다운로드" : "Download App"}
            </span>
            <div className="flex-1 h-px bg-border/50" />
          </div>
          <div className="flex gap-2">
            {(!isMobile || isAndroid) && (
              <a
                href={PLAY_STORE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-border/50 bg-card/30 py-2.5 text-xs font-medium text-muted-foreground hover:border-primary/30 hover:text-foreground transition-colors"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3.609 1.814L13.792 12 3.61 22.186a.996.996 0 0 1-.61-.92V2.734a1 1 0 0 1 .609-.92zm10.89 10.893l2.302 2.302-10.937 6.333 8.635-8.635zm3.199-3.199l2.302 2.302a1 1 0 0 1 0 1.38l-2.302 2.302L15.137 12l2.561-2.492zM5.864 2.658L16.8 8.99l-2.302 2.302L5.864 2.658z"/>
                </svg>
                Google Play
              </a>
            )}
            {(!isMobile || isIOS) && (
              <a
                href={APP_STORE_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="flex-1 flex items-center justify-center gap-1.5 rounded-xl border border-border/50 bg-card/30 py-2.5 text-xs font-medium text-muted-foreground hover:border-primary/30 hover:text-foreground transition-colors"
              >
                <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                </svg>
                App Store
              </a>
            )}
          </div>
          <p className="mt-2 text-[10px] text-muted-foreground/50 text-center">
            {lang === "ko"
              ? "앱 설치 시 실시간 푸시 알림을 받을 수 있습니다"
              : "Install the app for real-time push notifications"}
          </p>
        </div>
      </div>

      <style jsx global>{`
        @keyframes floatBob {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-8px); }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes scanLineIn {
          from { opacity: 0; transform: translateX(-8px); }
          to { opacity: 1; transform: translateX(0); }
        }
        @keyframes radarPulse {
          0% { transform: scale(0.3); opacity: 0.5; }
          100% { transform: scale(1); opacity: 0; }
        }
        .ob-radar-ring {
          position: absolute;
          inset: 0;
          border-radius: 50%;
          border: 1px solid rgba(59, 130, 246, 0.15);
          animation: radarPulse 4s ease-out infinite;
        }
        .ob-radar-ring--2 { animation-delay: 1.3s; }
        .ob-radar-ring--3 { animation-delay: 2.6s; }
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

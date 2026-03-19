"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
interface SplashScreenProps {
  visible: boolean;
}

export function SplashScreen({ visible }: SplashScreenProps) {
  const [mounted, setMounted] = useState(true);

  useEffect(() => {
    if (!visible) {
      // fade-out 애니메이션 후 DOM에서 제거
      const timer = setTimeout(() => setMounted(false), 500);
      return () => clearTimeout(timer);
    }
  }, [visible]);

  // 안전장치: 10초 후에도 visible이면 강제로 fade-out (느린 네트워크 대응)
  useEffect(() => {
    const failsafe = setTimeout(() => {
      setMounted(false);
    }, 10000);
    return () => clearTimeout(failsafe);
  }, []);

  useEffect(() => {
    // React 스플래시가 마운트되면 인라인 HTML 스플래시 제거
    const el = document.getElementById("__splash");
    if (el) el.remove();
  }, []);

  if (!mounted) return null;

  return (
    <div
      className={`fixed inset-0 z-[9999] flex flex-col items-center justify-center overflow-hidden ${
        visible ? "" : "splash-fade-out"
      }`}
      style={{
        background: "linear-gradient(160deg, #0a0f1e 0%, #0f172a 35%, #121d36 65%, #0d1425 100%)",
      }}
    >
      {/* 배경: dotted 세계지도 */}
      <div
        className="absolute inset-0 opacity-50"
        style={{
          backgroundImage: "url(/dotted-world-map.svg)",
          backgroundSize: "140% auto",
          backgroundPosition: "center 40%",
          backgroundRepeat: "no-repeat",
        }}
      />
      {/* 이슈 핑 애니메이션 */}
      <span className="splash-ping" style={{ top: "25%", left: "55%" }} />
      <span className="splash-ping splash-ping--2" style={{ top: "38%", left: "72%" }} />
      <span className="splash-ping splash-ping--3" style={{ top: "45%", left: "48%" }} />
      <span className="splash-ping splash-ping--4" style={{ top: "32%", left: "30%" }} />
      <span className="splash-ping splash-ping--5" style={{ top: "55%", left: "60%" }} />
      {/* 글로우 오버레이 */}
      <div
        className="absolute inset-0"
        style={{
          background: "radial-gradient(ellipse 70% 60% at 50% 45%, rgba(10,15,30,0.4) 0%, rgba(10,15,30,0.85) 70%, rgba(10,15,30,0.95) 100%)",
        }}
      />
      {/* 수평 스캔 라인 */}
      <div
        className="absolute left-0 right-0 h-px splash-scan"
        style={{
          background:
            "linear-gradient(90deg, transparent 0%, rgba(59,130,246,0.4) 20%, rgba(59,130,246,0.6) 50%, rgba(59,130,246,0.4) 80%, transparent 100%)",
          boxShadow: "0 0 12px 2px rgba(59,130,246,0.15)",
        }}
      />

      {/* 로고 + 레이더 영역 */}
      <div className="relative flex items-center justify-center w-[184px] h-20">
        <>
          {/* 레이더 파동 3겹 */}
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[50px] h-[50px] rounded-full border border-blue-500/25 splash-radar" />
          <div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[50px] h-[50px] rounded-full border border-blue-500/20 opacity-0 splash-radar"
            style={{ animationDelay: "1s" }}
          />
          <div
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[50px] h-[50px] rounded-full border border-blue-500/15 opacity-0 splash-radar"
            style={{ animationDelay: "2s" }}
          />
        </>
        <Image
          src="/logo-eye.png"
          alt="WeWantPeace"
          width={184}
          height={80}
          className="relative z-[1] h-20 w-auto object-contain"
          style={{ filter: "drop-shadow(0 0 20px rgba(59,130,246,0.2))" }}
          priority
        />
      </div>

      {/* 타이틀 */}
      <p className="mt-4 text-[22px] font-black tracking-tight text-slate-100">
        WeWantPeace
      </p>

      {/* 서브타이틀 */}
      <p className="mt-1.5 text-xs font-medium tracking-widest uppercase text-slate-400/80">
        Real-time Global Conflict Monitor
      </p>

      {/* Disquiet 배지 */}
      <div className="mt-6 relative z-[1]">
        <iframe
          title="disquiet-badge"
          frameBorder={0}
          src="https://badge.disquiet.io/vote-badge?productUrlSlug=we-want-peace&mode=dark"
          style={{ width: 210, height: 54, border: "none" }}
        />
      </div>

      {/* 로딩 인디케이터 */}
      <div className="mt-4 flex items-center gap-2">
        <div className="flex gap-[3px]">
          <span className={"splash-dot h-1 w-1 rounded-full bg-blue-500/70"} />
          <span
            className={"splash-dot h-1 w-1 rounded-full bg-blue-500/70"}
            style={{ animationDelay: "200ms" }}
          />
          <span
            className={"splash-dot h-1 w-1 rounded-full bg-blue-500/70"}
            style={{ animationDelay: "400ms" }}
          />
        </div>
        <span className="text-[11px] font-medium tracking-wide text-slate-400/60">
          Connecting sources
        </span>
      </div>
    </div>
  );
}

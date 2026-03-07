import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { OnboardingGuard } from "@/components/ui/onboarding-guard";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: {
    default: "WeWantPeace",
    template: "%s | WeWantPeace",
  },
  description: "실시간 글로벌 분쟁 모니터링 · 40개국 긴장도 지수 · AI 이슈 분석 · 스파이크 알림 — WeWantPeace",
  manifest: "/manifest.json",
  metadataBase: new URL(SITE_URL),
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: SITE_URL,
    siteName: "WeWantPeace",
    title: "WeWantPeace — 실시간 글로벌 분쟁 모니터링",
    description: "40개국 긴장도 지수 · AI 이슈 분석 · 스파이크 알림 — 전 세계 분쟁 이슈를 실시간으로 추적합니다",
    images: [{ url: `${SITE_URL}/og-image.png`, width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "WeWantPeace — 실시간 글로벌 분쟁 모니터링",
    description: "40개국 긴장도 지수 · AI 이슈 분석 · 실시간 스파이크 알림",
    images: [{ url: `${SITE_URL}/og-image-twitter.png` }],
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "WeWantPeace",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
  formatDetection: {
    telephone: false,
  },
  robots: {
    index: true,
    follow: true,
  },
  verification: {
    google: "LJQ8sx_1VitFQTLo9e3oNys3rRVZdpIWAHuSYZtzrOo",
    other: {
      "naver-site-verification": ["ce8b1e250ea44cedcdd2e4383a4d35d1f9252031"],
    },
  },
};

export const viewport: Viewport = {
  themeColor: "#0f1729",
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className="dark" suppressHydrationWarning>
      <head>
        {/* 테마/언어 깜빡임 방지: localStorage → 브라우저 언어 감지 순으로 즉시 적용 */}
        <script dangerouslySetInnerHTML={{ __html: `
          try {
            var s = JSON.parse(localStorage.getItem('wwp-store') || '{}');
            var t = (s.state && s.state.theme) || 'dark';
            document.documentElement.className = t;
            var l = s.state && s.state.lang;
            if (!l) {
              l = (navigator.language || '').startsWith('ko') ? 'ko' : 'en';
              if (!s.state) s.state = {};
              s.state.lang = l;
              s.version = 4;
              localStorage.setItem('wwp-store', JSON.stringify(s));
            }
            document.documentElement.lang = l;
            document.documentElement.dataset.lang = l;
          } catch(e) {}
        ` }} />
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
      </head>
      <body className="min-h-screen bg-background antialiased">
        {/* 인라인 스플래시: JS 번들 로드 전 빈 화면 방지 (React 하이드레이션 후 제거됨) */}
        <div
          id="__splash"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "linear-gradient(160deg, #0a0f1e 0%, #0f172a 35%, #121d36 65%, #0d1425 100%)",
            overflow: "hidden",
          }}
        >
          {/* 배경 그리드 패턴 */}
          <div style={{ position: "absolute", inset: 0, opacity: 0.04, backgroundImage: "linear-gradient(rgba(59,130,246,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.5) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />

          {/* 배경 글로우 오브 */}
          <div style={{ position: "absolute", top: "30%", left: "50%", width: 300, height: 300, borderRadius: "50%", background: "radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)", transform: "translate(-50%, -50%)", animation: "splash-glow 4s ease-in-out infinite" }} />

          {/* 수평 스캔 라인 */}
          <div style={{ position: "absolute", left: 0, right: 0, height: 1, background: "linear-gradient(90deg, transparent 0%, rgba(59,130,246,0.4) 20%, rgba(59,130,246,0.6) 50%, rgba(59,130,246,0.4) 80%, transparent 100%)", animation: "splash-scan 3s ease-in-out infinite", boxShadow: "0 0 12px 2px rgba(59,130,246,0.15)" }} />

          {/* 로고 + 레이더 영역 */}
          <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center", width: 184, height: 80 }}>
            {/* 레이더 파동 3겹 */}
            <div style={{ position: "absolute", top: "50%", left: "50%", width: 50, height: 50, borderRadius: "50%", border: "1px solid rgba(59,130,246,0.25)", transform: "translate(-50%,-50%)", animation: "splash-radar 3s ease-out infinite" }} />
            <div style={{ position: "absolute", top: "50%", left: "50%", width: 50, height: 50, borderRadius: "50%", border: "1px solid rgba(59,130,246,0.2)", transform: "translate(-50%,-50%)", animation: "splash-radar 3s ease-out 1s infinite" }} />
            <div style={{ position: "absolute", top: "50%", left: "50%", width: 50, height: 50, borderRadius: "50%", border: "1px solid rgba(59,130,246,0.15)", transform: "translate(-50%,-50%)", animation: "splash-radar 3s ease-out 2s infinite" }} />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/logo-eye.png"
              alt=""
              width={184}
              height={80}
              style={{ position: "relative", zIndex: 1, height: 80, width: "auto", objectFit: "contain", filter: "drop-shadow(0 0 20px rgba(59,130,246,0.2))" }}
            />
          </div>

          {/* 타이틀 */}
          <p style={{ marginTop: 16, fontSize: 22, fontWeight: 900, letterSpacing: "-0.02em", color: "#f1f5f9" }}>
            WeWantPeace
          </p>

          {/* 서브타이틀 — 서비스 설명 */}
          <p style={{ marginTop: 6, fontSize: 12, fontWeight: 500, letterSpacing: "0.05em", color: "rgba(148,163,184,0.8)", textTransform: "uppercase" }}>
            Real-time Global Conflict Monitor
          </p>

          {/* 로딩 인디케이터 */}
          <div style={{ marginTop: 32, display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ display: "flex", gap: 3 }}>
              <span style={{ width: 4, height: 4, borderRadius: "50%", background: "rgba(59,130,246,0.7)", animation: "splash-dot 1.4s ease-in-out infinite" }} />
              <span style={{ width: 4, height: 4, borderRadius: "50%", background: "rgba(59,130,246,0.7)", animation: "splash-dot 1.4s ease-in-out 0.2s infinite" }} />
              <span style={{ width: 4, height: 4, borderRadius: "50%", background: "rgba(59,130,246,0.7)", animation: "splash-dot 1.4s ease-in-out 0.4s infinite" }} />
            </div>
            <span style={{ fontSize: 11, fontWeight: 500, color: "rgba(148,163,184,0.6)", letterSpacing: "0.02em" }}>
              Connecting sources
            </span>
          </div>

          <style dangerouslySetInnerHTML={{ __html: `
            @keyframes splash-radar {
              0% { transform: translate(-50%,-50%) scale(0.5); opacity: 0.6; }
              100% { transform: translate(-50%,-50%) scale(4); opacity: 0; }
            }
            @keyframes splash-scan {
              0% { top: 15%; opacity: 0; }
              10% { opacity: 1; }
              90% { opacity: 1; }
              100% { top: 85%; opacity: 0; }
            }
            @keyframes splash-glow {
              0%, 100% { opacity: 0.6; transform: translate(-50%, -50%) scale(1); }
              50% { opacity: 1; transform: translate(-50%, -50%) scale(1.15); }
            }
            @keyframes splash-dot {
              0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
              40% { opacity: 1; transform: scale(1.2); }
            }
          ` }} />
        </div>
        <Providers>
          <OnboardingGuard>
            {children}
          </OnboardingGuard>
        </Providers>
      </body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { OnboardingGuard } from "@/components/ui/onboarding-guard";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://www.wewantpeace.live";

export const metadata: Metadata = {
  title: {
    default: "WeWantPeace — 실시간 글로벌 분쟁 모니터링",
    template: "%s | WeWantPeace",
  },
  description: "분쟁이 나에게 미치는 영향, 실시간으로 — 195개국 분쟁·안보 모니터링 & 개인화 영향 분석. KScore로 나에게 미치는 위험도를 확인하세요.",
  keywords: [
    "분쟁 모니터링", "국제 안보", "긴장도 지수", "실시간 뉴스", "위기 분석",
    "전쟁 뉴스", "글로벌 리스크", "지정학", "안보 위협", "KScore",
    "conflict monitoring", "global security", "tension index", "real-time news",
    "geopolitical risk", "crisis analysis", "war news", "security alert",
    "WeWantPeace", "위원트피스",
  ],
  manifest: "/manifest.json",
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: SITE_URL,
    languages: {
      "ko": SITE_URL,
      "en": `${SITE_URL}/en`,
      "x-default": SITE_URL,
    },
  },
  openGraph: {
    type: "website",
    locale: "ko_KR",
    alternateLocale: "en_US",
    url: SITE_URL,
    siteName: "WeWantPeace",
    title: "WeWantPeace — 실시간 글로벌 분쟁 모니터링",
    description: "195개국 분쟁·안보 이슈를 실시간 모니터링. AI 기반 KScore로 나에게 미치는 영향을 분석합니다.",
    images: [{ url: `${SITE_URL}/og-image.png?v=4`, width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "WeWantPeace — 실시간 글로벌 분쟁 모니터링",
    description: "195개국 분쟁·안보 이슈를 실시간 모니터링. AI 기반 KScore로 나에게 미치는 영향을 분석합니다.",
    images: [{ url: `${SITE_URL}/og-image-twitter.png?v=4` }],
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
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
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
    <html lang="ko" className="" suppressHydrationWarning>
      <head>
        {/* SAFE: 테마/언어 깜빡임 방지 인라인 스크립트. 개발자 작성 리터럴만 사용, 사용자 입력 없음 */}
        {/* SAFE: 테마/언어 깜빡임 방지 인라인 스크립트. 개발자 작성 리터럴만 사용, 사용자 입력 없음 */}
        <script dangerouslySetInnerHTML={{ __html: `try {
              var s = JSON.parse(localStorage.getItem('wwp-store') || '{}');
              var t = (s.state && s.state.theme) || 'dark';
              document.documentElement.className = t;
              var l = s.state && s.state.lang;
              if (!l) {
                l = (navigator.language || '').startsWith('ko') ? 'ko' : 'en';
                if (!s.state) s.state = {};
                s.state.lang = l;
                s.version = 9;
                localStorage.setItem('wwp-store', JSON.stringify(s));
              }
              document.documentElement.lang = l;
              document.documentElement.dataset.lang = l;
            } catch(e) {}`
        }} />
        {/* SAFE: SEO JSON-LD 구조화 데이터. JSON.stringify로 직렬화되어 XSS 불가 */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@graph": [
                {
                  "@type": "Organization",
                  "@id": "https://www.wewantpeace.live/#organization",
                  "name": "WeWantPeace",
                  "url": "https://www.wewantpeace.live",
                  "logo": {
                    "@type": "ImageObject",
                    "url": "https://www.wewantpeace.live/logo-eye.png",
                    "width": 184,
                    "height": 80,
                  },
                  "description":
                    "Real-time global conflict and security monitoring platform covering 195 countries with AI-powered analysis.",
                  "sameAs": [
                    "https://x.com/wewantpeace_",
                    "https://www.threads.net/@wewantpeace.live",
                    "https://www.instagram.com/wewantpeace.live",
                  ],
                  "foundingDate": "2025",
                  "knowsAbout": [
                    "Global conflict monitoring",
                    "Geopolitical risk analysis",
                    "Security intelligence",
                    "Real-time news aggregation",
                  ],
                },
                {
                  "@type": "WebApplication",
                  "@id": "https://www.wewantpeace.live/#webapp",
                  "name": "WeWantPeace",
                  "url": "https://www.wewantpeace.live",
                  "applicationCategory": "NewsApplication",
                  "operatingSystem": "Web, Android (TWA)",
                  "browserRequirements": "Requires JavaScript. Requires HTML5.",
                  "description":
                    "Monitor how global conflicts affect you in real time. Personalized impact dashboard with AI-powered KScore scoring across 195 countries, Tension Index, real-time alerts, and interactive crisis maps.",
                  "offers": [
                    {
                      "@type": "Offer",
                      "name": "Free",
                      "price": "0",
                      "priceCurrency": "USD",
                      "description":
                        "Real-time trending issues, basic tension index, KScore alerts",
                    },
                    {
                      "@type": "Offer",
                      "name": "Pro",
                      "price": "4.99",
                      "priceCurrency": "USD",
                      "description":
                        "Interactive issue map, 5 watched countries, KScore filter, 30-day history",
                    },
                  ],
                  "featureList": [
                    "Real-time conflict monitoring across 195 countries",
                    "KScore (Key Impact Score) personalized to your country",
                    "Country-level Tension Index (0-100)",
                    "AI-powered KScore alerts with push notifications",
                    "Interactive global crisis map",
                    "Multi-source news aggregation (RSS, Telegram)",
                    "Bilingual interface (Korean/English)",
                  ],
                  "screenshot": "https://www.wewantpeace.live/og-image.png?v=4",
                  "publisher": {
                    "@id": "https://www.wewantpeace.live/#organization",
                  },
                },
                {
                  "@type": "FAQPage",
                  "@id": "https://www.wewantpeace.live/#faq",
                  "mainEntity": [
                    {
                      "@type": "Question",
                      "name": "What is WeWantPeace?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "WeWantPeace is a real-time global conflict and security monitoring platform that covers 195 countries. It aggregates news from hundreds of RSS feeds and Telegram channels, uses AI to classify and score events, and presents them through trending issue lists, interactive maps, and per-country tension dashboards.",
                      },
                    },
                    {
                      "@type": "Question",
                      "name": "What is KScore (Key Impact Score)?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "KScore is a 0-10 score that measures how much a global issue impacts your home country. It combines a base score (event velocity, severity, source spread, and credibility) with a country-specific impact factor that accounts for geographic proximity, security alliances, and economic ties. Scores above 8 indicate extreme impact; below 2 is stable.",
                      },
                    },
                    {
                      "@type": "Question",
                      "name": "How does the Tension Index work?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "The Tension Index is a 0-100 score assigned to each country, updated every 5 minutes. It is calculated from three components: EventScore (55% weight, based on severity and confidence of recent events), ActivityScore (35% weight, combining event volume and acceleration), and Spillover (10% weight, reflecting the highest severity from neighboring countries). Levels range from Stable (0-20) to Extreme (80-100).",
                      },
                    },
                    {
                      "@type": "Question",
                      "name": "What data sources does WeWantPeace use?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "WeWantPeace aggregates data from hundreds of international RSS news feeds and Telegram channels. Events are collected every 3-5 minutes, then processed through an AI pipeline using GPT-4o-mini for topic classification, severity scoring, country/coordinate extraction, and deduplication. Sources include major wire services, regional news outlets, and defense/security-focused channels.",
                      },
                    },
                    {
                      "@type": "Question",
                      "name": "Is WeWantPeace free to use?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Yes, WeWantPeace offers a free tier that includes real-time trending issues, basic tension index views, and KScore alert notifications. Pro and Pro+ plans unlock additional features like the interactive issue map, more watched countries, KScore filtering, quiet hours, and extended history (30 or 90 days).",
                      },
                    },
                    {
                      "@type": "Question",
                      "name": "How does the KScore alert system work?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "The KScore alert system monitors global conflict and security events in real-time. When an issue's KScore exceeds the user's configured threshold and severity reaches a minimum level, users receive push notifications (via Firebase Cloud Messaging) for issues related to their watched countries. Fast alerts are available for all plans, while verified alerts (confirmed by trusted sources) are available for Pro and Pro+ plans.",
                      },
                    },
                    {
                      "@type": "Question",
                      "name": "How often is the data updated?",
                      "acceptedAnswer": {
                        "@type": "Answer",
                        "text": "Data is collected continuously: RSS feeds are polled every 5 minutes and Telegram channels every 3 minutes. The KScore trending rankings are recalculated every 15 minutes, and the Tension Index is updated every 5 minutes. KScore-based alerts are processed in real-time as new events arrive.",
                      },
                    },
                  ],
                },
              ],
            }),
          }}
        />
        <link rel="icon" href="/favicon.ico" sizes="48x48" />
        <link rel="icon" href="/favicon-32x32.png" type="image/png" sizes="32x32" />
        <link rel="icon" href="/favicon-16x16.png" type="image/png" sizes="16x16" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180" />
        <meta name="msapplication-TileImage" content="/mstile-150x150.png" />
        <meta name="msapplication-TileColor" content="#0f1729" />
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
          <>
            {/* 배경 그리드 패턴 */}
            <div style={{ position: "absolute", inset: 0, opacity: 0.04, backgroundImage: "linear-gradient(rgba(59,130,246,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.5) 1px, transparent 1px)", backgroundSize: "40px 40px" }} />
            {/* 배경 글로우 오브 */}
            <div style={{ position: "absolute", top: "30%", left: "50%", width: 300, height: 300, borderRadius: "50%", background: "radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)", transform: "translate(-50%, -50%)", animation: "splash-glow 4s ease-in-out infinite" }} />
            {/* 수평 스캔 라인 */}
            <div style={{ position: "absolute", left: 0, right: 0, height: 1, background: "linear-gradient(90deg, transparent 0%, rgba(59,130,246,0.4) 20%, rgba(59,130,246,0.6) 50%, rgba(59,130,246,0.4) 80%, transparent 100%)", animation: "splash-scan 3s ease-in-out infinite", boxShadow: "0 0 12px 2px rgba(59,130,246,0.15)" }} />
          </>

          {/* 로고 + 레이더 영역 */}
          <div style={{ position: "relative", display: "flex", alignItems: "center", justifyContent: "center", width: 184, height: 80 }}>
            <>
              {/* 레이더 파동 3겹 */}
              <div style={{ position: "absolute", top: "50%", left: "50%", width: 50, height: 50, borderRadius: "50%", border: "1px solid rgba(59,130,246,0.25)", transform: "translate(-50%,-50%)", animation: "splash-radar 3s ease-out infinite" }} />
              <div style={{ position: "absolute", top: "50%", left: "50%", width: 50, height: 50, borderRadius: "50%", border: "1px solid rgba(59,130,246,0.2)", transform: "translate(-50%,-50%)", animation: "splash-radar 3s ease-out 1s infinite" }} />
              <div style={{ position: "absolute", top: "50%", left: "50%", width: 50, height: 50, borderRadius: "50%", border: "1px solid rgba(59,130,246,0.15)", transform: "translate(-50%,-50%)", animation: "splash-radar 3s ease-out 2s infinite" }} />
            </>
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
          <p style={{ marginTop: 16, fontSize: 22, fontWeight: 900, letterSpacing: "-0.02em", color: "#ffffff" }}>
            WeWantPeace
          </p>

          {/* 서브타이틀 — 서비스 설명 */}
          <p style={{ marginTop: 6, fontSize: 12, fontWeight: 500, letterSpacing: "0.05em", color: "rgba(255,255,255,0.8)", textTransform: "uppercase" }}>
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

          {/* SAFE: CSS @keyframes 리터럴. 사용자 입력 없음 */}
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
          ` }} />
          {/* SAFE: CSS @keyframes 리터럴. 사용자 입력 없음 */}
          <style dangerouslySetInnerHTML={{ __html: `
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

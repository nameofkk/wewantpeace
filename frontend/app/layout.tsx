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
  description: "실시간 세계정세 모니터링 · 긴장도 지수 · 이슈 알림",
  manifest: "/manifest.json",
  metadataBase: new URL(SITE_URL),
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: SITE_URL,
    siteName: "WeWantPeace",
    title: "WeWantPeace — 세계정세 모니터링",
    description: "긴장도 지수 · 이슈 알림 · 실시간 지도",
    // images는 app/opengraph-image.png 파일 기반 메타데이터가 자동 적용됨
  },
  twitter: {
    card: "summary_large_image",
    title: "WeWantPeace — 세계정세 모니터링",
    description: "긴장도 지수 · 이슈 알림 · 실시간 지도",
    // images는 app/twitter-image.png 파일 기반 메타데이터가 자동 적용됨
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "WeWantPeace",
  },
  formatDetection: {
    telephone: false,
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#1a1a2e",
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
    <html lang="ko" className="dark">
      <head>
        <link rel="icon" href="/favicon.ico" sizes="48x48" />
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
            background: "#1a1a2e",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo-eye.png"
            alt=""
            width={160}
            height={80}
            style={{ height: 80, width: 160, objectFit: "contain" }}
          />
          <p
            style={{
              marginTop: 12,
              fontSize: 20,
              fontWeight: 900,
              letterSpacing: "-0.025em",
              color: "hsl(210 40% 98%)",
            }}
          >
            WeWantPeace
          </p>
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

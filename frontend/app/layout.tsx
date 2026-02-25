import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { BottomNav } from "@/components/ui/bottom-nav";
import { OnboardingGuard } from "@/components/ui/onboarding-guard";
import { PWAInstallPrompt } from "@/components/ui/pwa-install-prompt";
import { NewEventBanner } from "@/components/ui/new-event-banner";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://wewantpeace.fly.dev";

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
    title: "WeWantPeace — 실시간 세계정세 모니터링",
    description: "긴장도 지수 · 이슈 알림 · 실시간 지도",
    images: [
      {
        url: "/icons/og-image.png",
        width: 1200,
        height: 630,
        alt: "WeWantPeace",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "WeWantPeace — 실시간 세계정세 모니터링",
    description: "긴장도 지수 · 이슈 알림 · 실시간 지도",
    images: ["/icons/og-image.png"],
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
        <Providers>
          <OnboardingGuard>
            <NewEventBanner />
            <main className="pb-[60px]">{children}</main>
            <BottomNav />
            <PWAInstallPrompt />
          </OnboardingGuard>
        </Providers>
      </body>
    </html>
  );
}

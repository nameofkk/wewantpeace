import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://www.wewantpeace.live";
const PLAY_STORE_URL = "https://play.google.com/store/apps/details?id=com.wewantpeace.app";
const APP_STORE_URL = ""; // iOS 앱 출시 시 추가

export const metadata: Metadata = {
  title: "위원트피스 설치하기",
  description: "분쟁이 나에게 미치는 영향, 실시간으로 — 195개국 분쟁·안보 모니터링 & 개인화 영향 분석",
  openGraph: {
    type: "website",
    locale: "ko_KR",
    url: `${SITE_URL}/app`,
    siteName: "WeWantPeace",
    title: "위원트피스 설치하기",
    description: "분쟁이 나에게 미치는 영향, 실시간으로 — 195개국 분쟁·안보 모니터링 & 개인화 영향 분석",
    images: [{ url: `${SITE_URL}/og-image.png?v=4`, width: 1200, height: 630 }],
  },
  twitter: {
    card: "summary_large_image",
    title: "위원트피스 설치하기",
    description: "분쟁이 나에게 미치는 영향, 실시간으로 — 195개국 분쟁·안보 모니터링 & 개인화 영향 분석",
    images: [{ url: `${SITE_URL}/og-image-twitter.png?v=4` }],
  },
};

export default async function AppDownloadPage() {
  // UA 기반 플랫폼 감지 → 자동 리다이렉트
  const headersList = await headers();
  const ua = headersList.get("user-agent") || "";
  const isAndroid = /Android/i.test(ua);
  const isIOS = /iPhone|iPad|iPod/i.test(ua);

  if (isAndroid && PLAY_STORE_URL) {
    redirect(PLAY_STORE_URL);
  }
  if (isIOS && APP_STORE_URL) {
    redirect(APP_STORE_URL);
  }

  // 데스크톱이거나 스토어 URL 미설정 시 → 웹 버전으로
  redirect("/home");
}

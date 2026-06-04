"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { setupForegroundListener, refreshTokenIfNeeded } from "@/lib/fcm";
import { isTossMiniApp } from "@/lib/platform";

function ThemeSync() {
  const theme = useAppStore((s) => s.theme);
  useEffect(() => {
    const html = document.documentElement;
    html.classList.toggle("dark", theme === "dark");
    html.classList.toggle("light", theme === "light");
  }, [theme]);
  return null;
}

function FCMForegroundInit() {
  useEffect(() => {
    // 토스 WebView에서는 Service Worker 미지원 → FCM 초기화 스킵
    if (isTossMiniApp()) return;
    setupForegroundListener();
    // 앱 로드 시 FCM 토큰 자동 갱신 (12시간 간격)
    refreshTokenIfNeeded();
  }, []);
  return null;
}

/** Native 앱에서 PUSH_NOTIFICATION_CLICK 메시지 수신 → 해당 이슈 페이지로 이동 */
function NativePushClickHandler() {
  const router = useRouter();
  useEffect(() => {
    if (typeof window === "undefined") return;
    const handler = (e: Event) => {
      const msg = (e as CustomEvent).detail;
      if (msg?.type === "PUSH_NOTIFICATION_CLICK" && msg.payload?.url) {
        router.push(msg.payload.url);
      }
    };
    window.addEventListener("nativeMessage", handler);
    return () => window.removeEventListener("nativeMessage", handler);
  }, [router]);
  return null;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 3 * 60 * 1000, // 3분 (체감 속도 개선: 캐시 재사용 빈도 증가)
            gcTime: 15 * 60 * 1000,   // 15분 (캐시 더 오래 유지)
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeSync />
      <FCMForegroundInit />
      <NativePushClickHandler />
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}

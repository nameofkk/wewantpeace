"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAppStore } from "@/lib/store";
import { setupForegroundListener, refreshTokenIfNeeded } from "@/lib/fcm";
import { isTossMiniApp } from "@/lib/platform";
import { useAuth } from "@/lib/auth";
import { trackEvent } from "@/lib/analytics";

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

/**
 * 앱 로드 부트스트랩 — 로그인 상태(토큰 존재)면 인증요청 1회를 무조건 쏜다.
 *
 * 왜 필요하냐면: DAU는 백엔드가 '오늘 첫 인증요청'에 daily_active 이벤트를 하루 1건
 * 적재하고(core/auth.py), 그 distinct 유저 수를 세는 구조거든(admin._dau_query).
 * 그런데 재방문 로그인 유저가 앱만 열고 아무 인증 API도 안 부르는 화면에 머물면
 * daily_active가 안 박혀서 오늘 DAU에서 통째로 빠져버린다(언더카운트).
 *
 * 그래서 로그인 유저면 앱 로드마다 /me/events(app_open) 1회를 보장한다.
 * 이 요청이 백엔드 get_optional_user → get_current_user를 거치면서 daily_active를 적재해준다.
 * app_open은 CORE_ACTION_EVENTS가 아니라서 활성화(activation) 지표는 오염시키지 않는다.
 */
function DailyActiveBootstrap() {
  const { user, loading } = useAuth();
  const firedFor = useRef<string | null>(null);

  useEffect(() => {
    if (loading) return; // auth 복원 끝날 때까지 대기 — 비로그인으로 오판해서 누락하는 것 방지
    // X-Dev-UID(개발)도 '토큰 존재'로 취급
    const devUid =
      typeof window !== "undefined" ? localStorage.getItem("dev_uid") : null;
    const uid = user?.uid ?? (devUid ? `dev:${devUid}` : null);
    if (!uid) return; // 비로그인 — DAU 대상 아님
    if (firedFor.current === uid) return; // 이 앱 로드에서 이미 보냄(중복 방지)
    firedFor.current = uid;

    // 인증된 요청 1회 → 백엔드가 오늘 daily_active를 적재 → 재방문 로그인 유저 DAU 누락 방지.
    // fire-and-forget(keepalive)이라 실패해도 앱 동작에는 영향 없다.
    trackEvent("app_open", { source: "bootstrap" });
  }, [user, loading]);

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

/**
 * 방문 비콘 — 브라우저 탭 세션마다 1회 `visit` 이벤트.
 *
 * 누가 어디서 오는지를 우리 DB 로 직접 알기 위해 넣었다. 2026-09 진단 때는 이걸 알려고
 * Railway HTTP 로그 13만 건을 내려받아 IP 를 나라로 바꾸고, 봇·데이터센터·JS 안 불러온
 * 수집기를 걸러내야 했다(실제 사람은 하루 14명, 90% 해외).
 * - 보내는 것: 들어온 사이트 도메인(주소 전체 아님), 첫 경로, ?ref= 값, 브라우저 언어, 시간대
 * - 보내지 않는 것: IP, 쿼리 전체, 들어온 페이지의 전체 주소
 * 자바스크립트를 실행하는 브라우저만 보내므로 봇 대부분이 자연히 빠진다.
 */
function VisitBeacon() {
  useEffect(() => {
    try {
      if (sessionStorage.getItem("wwp_visit_sent")) return;
      sessionStorage.setItem("wwp_visit_sent", "1");
    } catch {
      return;
    }
    let refHost = "";
    try {
      if (document.referrer) {
        const h = new URL(document.referrer).hostname;
        if (h && h !== window.location.hostname) refHost = h;
      }
    } catch {}
    let tz = "";
    try {
      tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch {}
    const params = new URLSearchParams(window.location.search);
    trackEvent("visit", {
      ref_host: refHost,
      ref: (params.get("ref") || params.get("utm_source") || "").slice(0, 32),
      path: window.location.pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27,}/gi, "{id}").slice(0, 80),
      lang: (navigator.language || "").slice(0, 16),
      tz: tz.slice(0, 48),
      mobile: /Mobi|Android|iPhone/i.test(navigator.userAgent),
    });
  }, []);
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
      <DailyActiveBootstrap />
      <VisitBeacon />
      <NativePushClickHandler />
      {children}
      {process.env.NODE_ENV === "development" && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  );
}

/**
 * 인앱브라우저 / standalone(PWA) 감지 유틸리티.
 */

/** 카카오톡, 네이버, LINE, Facebook, Instagram, Threads 등 인앱브라우저 감지 */
export function isInAppBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /KAKAOTALK|NAVER|LINE|FB_IAB|FBAV|Instagram|FBAN|Barcelona|Threads/i.test(ua);
}

/**
 * Google OAuth가 차단되는 인앱브라우저만 감지.
 * Meta 계열(Threads/Instagram/Facebook)은 자체 WebView를 사용하여 Google이 403 disallowed_useragent로 차단.
 * 카카오톡/네이버/LINE은 Chrome Custom Tabs를 사용하므로 Google OAuth 허용됨.
 */
export function isGoogleOAuthBlocked(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /FB_IAB|FBAV|Instagram|FBAN|Barcelona|Threads/i.test(ua);
}

/** 인앱브라우저에서 외부 브라우저로 현재 URL 열기 시도 */
export function openInExternalBrowser(): void {
  if (typeof window === "undefined") return;
  const url = window.location.href;
  const ua = navigator.userAgent || "";

  // Android: intent URL로 Chrome/기본 브라우저에서 열기
  if (/Android/i.test(ua)) {
    window.location.href = `intent://${window.location.host}${window.location.pathname}${window.location.search}${window.location.hash}#Intent;scheme=https;action=android.intent.action.VIEW;end`;
    return;
  }

  // iOS / fallback: clipboard 복사 + 새 창 시도
  if (navigator.clipboard) {
    navigator.clipboard.writeText(url).catch(() => {});
  }
  window.open(url, '_blank');
}

/** PWA standalone 모드(홈 화면에서 실행) 감지 */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as any).standalone === true
  );
}

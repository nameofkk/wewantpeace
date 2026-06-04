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

/**
 * 인앱브라우저에서 외부 브라우저로 현재 URL 열기 시도.
 * 클립보드에 URL 복사 후 성공 여부를 반환.
 * intent:// 등은 인앱브라우저마다 동작이 달라 신뢰할 수 없으므로 클립보드 복사 방식 사용.
 */
export async function openInExternalBrowser(): Promise<boolean> {
  if (typeof window === "undefined") return false;
  const url = window.location.href;
  try {
    await navigator.clipboard.writeText(url);
    return true;
  } catch {
    // clipboard API 미지원 시 fallback
    const ta = document.createElement("textarea");
    ta.value = url;
    ta.style.cssText = "position:fixed;left:-9999px";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    return true;
  }
}

/** PWA standalone 모드(홈 화면에서 실행) 감지 */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as any).standalone === true
  );
}

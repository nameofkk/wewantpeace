/**
 * 인앱브라우저 / standalone(PWA) 감지 유틸리티.
 */

/** 카카오톡, 네이버, LINE, Facebook, Instagram 등 인앱브라우저 감지 */
export function isInAppBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent || "";
  return /KAKAOTALK|NAVER|LINE|FB_IAB|Instagram|FBAN/i.test(ua);
}

/** PWA standalone 모드(홈 화면에서 실행) 감지 */
export function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as any).standalone === true
  );
}

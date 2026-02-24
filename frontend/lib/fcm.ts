/**
 * FCM (Firebase Cloud Messaging) 초기화 + 토큰 관리.
 * firebase JS SDK가 없어도 SW 등록까지는 동작 (토큰 획득 불가).
 */

const VAPID_KEY = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY || "";
const FCM_TOKEN_KEY = "fcm_token";

/** Service Worker 등록 */
export async function registerFCMServiceWorker(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return null;
  try {
    const reg = await navigator.serviceWorker.register("/firebase-messaging-sw.js", {
      scope: "/",
    });
    return reg;
  } catch (e) {
    console.warn("[FCM] SW 등록 실패:", e);
    return null;
  }
}

/** 알림 권한 요청 → FCM 토큰 획득 */
export async function requestAndGetFCMToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;

  // 알림 권한 요청
  if (Notification.permission === "default") {
    const perm = await Notification.requestPermission();
    if (perm !== "granted") return null;
  }
  if (Notification.permission !== "granted") return null;

  try {
    const { initializeApp, getApps } = await import("firebase/app");
    const { getMessaging, getToken } = await import("firebase/messaging");

    const firebaseConfig = {
      apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
      authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
      projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
      storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
      appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
    };

    const app = getApps().length ? getApps()[0] : initializeApp(firebaseConfig);
    const messaging = getMessaging(app);

    const sw = await registerFCMServiceWorker();
    const token = await getToken(messaging, {
      vapidKey: VAPID_KEY,
      serviceWorkerRegistration: sw || undefined,
    });

    if (token) {
      localStorage.setItem(FCM_TOKEN_KEY, token);
    }
    return token || null;
  } catch (e) {
    console.warn("[FCM] 토큰 획득 실패 (firebase SDK 없음):", e);
    return null;
  }
}

/** 저장된 FCM 토큰 반환 */
export function getStoredFCMToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(FCM_TOKEN_KEY);
}

/** 저장된 FCM 토큰 삭제 */
export function clearStoredFCMToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(FCM_TOKEN_KEY);
}

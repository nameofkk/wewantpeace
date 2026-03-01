/**
 * FCM (Firebase Cloud Messaging) 초기화 + 토큰 관리.
 * firebase JS SDK가 없어도 SW 등록까지는 동작 (토큰 획득 불가).
 */

const VAPID_KEY = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY || "";
const FCM_TOKEN_KEY = "fcm_token";

/** 푸시 알림을 지원하는 환경인지 확인 */
export function isPushSupported(): boolean {
  if (typeof window === "undefined") return false;
  if (!("Notification" in window)) return false;
  if (!("serviceWorker" in navigator)) return false;
  return true;
}

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

/** Promise에 타임아웃을 적용하는 헬퍼 */
function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} 타임아웃(${ms}ms)`)), ms);
    promise.then(
      (v) => { clearTimeout(timer); resolve(v); },
      (e) => { clearTimeout(timer); reject(e); },
    );
  });
}

/** 알림 권한 요청 → FCM 토큰 획득 */
export async function requestAndGetFCMToken(): Promise<string | null> {
  if (!isPushSupported()) return null;

  // 알림 권한 확인 + 요청
  try {
    if (Notification.permission === "default") {
      try {
        const perm = await withTimeout(
          Notification.requestPermission(),
          10_000,
          "Notification.requestPermission",
        );
        if (perm !== "granted") return null;
      } catch {
        // Edge: requestPermission이 타임아웃되어도 설정에서 허용했으면 granted일 수 있음
        if ((Notification.permission as string) !== "granted") return null;
      }
    }
    if (Notification.permission !== "granted") return null;
  } catch (e) {
    console.warn("[FCM] 알림 권한 요청 실패:", e);
    return null;
  }

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
    const token = await withTimeout(
      getToken(messaging, {
        vapidKey: VAPID_KEY,
        serviceWorkerRegistration: sw || undefined,
      }),
      15_000,
      "getToken",
    );

    if (token) {
      localStorage.setItem(FCM_TOKEN_KEY, token);
    }
    return token || null;
  } catch (e) {
    console.warn("[FCM] 토큰 획득 실패:", e);
    return null;
  }
}

/** 포그라운드 메시지 수신 리스너 등록 (탭이 활성 상태일 때) */
export async function setupForegroundListener(): Promise<void> {
  if (!isPushSupported()) return;
  if (Notification.permission !== "granted") return;

  try {
    const { initializeApp, getApps } = await import("firebase/app");
    const { getMessaging, onMessage } = await import("firebase/messaging");

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

    onMessage(messaging, (payload) => {
      const data = payload.data || {};
      const title = data.title || payload.notification?.title || "WeWantPeace";
      const body = data.body || payload.notification?.body || "";

      // Service Worker를 통해 시스템 알림 표시
      navigator.serviceWorker.ready.then((reg) => {
        reg.showNotification(title, {
          body,
          icon: "/icons/icon-192.png",
          badge: "/icons/icon-96.png",
          tag: data.cluster_id || "wwp-fg-notification",
          data: { url: data.cluster_id && data.cluster_id !== "test" ? `/issues/${data.cluster_id}` : "/" },
        });
      });
    });
  } catch (e) {
    console.warn("[FCM] 포그라운드 리스너 설정 실패:", e);
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

/**
 * FCM (Firebase Cloud Messaging) 초기화 + 토큰 관리.
 * firebase JS SDK가 없어도 SW 등록까지는 동작 (토큰 획득 불가).
 */

const VAPID_KEY = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY || "";
const FCM_TOKEN_KEY = "fcm_token";

/** iOS 기기인지 확인 */
export function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPhone|iPad|iPod/i.test(navigator.userAgent);
}

/** 푸시 알림을 지원하는 환경인지 확인 */
export function isPushSupported(): boolean {
  if (typeof window === "undefined") return false;
  if (isIOS()) return false;
  // 토스 WebView는 Service Worker 미지원
  if (process.env.NEXT_PUBLIC_IS_TOSS_MINIAPP === "true") return false;
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
  // React Native 환경: 네이티브 브릿지로 토큰 요청
  if (typeof window !== "undefined" && (window.__REACT_NATIVE__ || window.ReactNativeWebView)) {
    // __handleNativeMessage가 없으면 세팅 (결과 수신용)
    if (!window.__handleNativeMessage) {
      window.__handleNativeMessage = (msg: unknown) => {
        window.dispatchEvent(new CustomEvent("nativeMessage", { detail: msg }));
      };
    }

    return new Promise<string | null>((resolve) => {
      const handler = (e: Event) => {
        const msg = (e as CustomEvent).detail;
        if (msg?.type === "FCM_TOKEN") {
          window.removeEventListener("nativeMessage", handler);
          const token: string | null = msg.payload.token || null;
          if (token) localStorage.setItem(FCM_TOKEN_KEY, token);
          resolve(token);
        }
      };
      window.addEventListener("nativeMessage", handler);
      // 10초 타임아웃
      setTimeout(() => {
        window.removeEventListener("nativeMessage", handler);
        resolve(null);
      }, 10_000);

      if (window.__nativeBridge) {
        window.__nativeBridge.postToNative("GET_FCM_TOKEN", {});
      } else if (window.ReactNativeWebView) {
        window.ReactNativeWebView.postMessage(JSON.stringify({ type: "GET_FCM_TOKEN", payload: {} }));
      } else {
        window.removeEventListener("nativeMessage", handler);
        resolve(null);
      }
    });
  }

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
  // React Native 환경: 네이티브가 포그라운드 메시지를 처리하므로 skip
  if (typeof window !== "undefined" && (window.__REACT_NATIVE__ || window.ReactNativeWebView)) return;

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

const TOKEN_REFRESH_KEY = "fcm_token_refreshed_at";
const TOKEN_REFRESH_INTERVAL = 3 * 60 * 60 * 1000; // 3시간 (FCM 토큰 자동 교체 대응)

/**
 * 앱 로드 시 FCM 토큰을 자동 갱신하여 서버에 재등록.
 * - 이미 알림 허용된 경우에만 동작 (권한 팝업 안 띄움)
 * - 12시간 이내 갱신했으면 스킵
 * - 서버에 POST /me/push-tokens → 같은 토큰이면 last_used 갱신, 새 토큰이면 등록
 */
export async function refreshTokenIfNeeded(): Promise<void> {
  if (typeof window === "undefined") return;

  // 토스 미니앱: 푸시 미지원
  if (process.env.NEXT_PUBLIC_IS_TOSS_MINIAPP === "true") return;

  // 12시간 이내 갱신했으면 스킵
  const lastRefresh = localStorage.getItem(TOKEN_REFRESH_KEY);
  if (lastRefresh && Date.now() - Number(lastRefresh) < TOKEN_REFRESH_INTERVAL) return;

  // React Native: 네이티브 브릿지로 토큰 갱신
  if (window.__REACT_NATIVE__ || window.ReactNativeWebView) {
    try {
      const token = await requestAndGetFCMToken();
      if (token) {
        await _registerTokenToServer(token, "android");
        localStorage.setItem(TOKEN_REFRESH_KEY, String(Date.now()));
      }
    } catch (e) {
      console.warn("[FCM] 네이티브 토큰 갱신 실패:", e);
    }
    return;
  }

  // 웹: 이미 알림 허용된 경우에만 (권한 팝업 안 띄움)
  if (!isPushSupported()) return;
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;

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
      "getToken(refresh)",
    );

    if (token) {
      localStorage.setItem(FCM_TOKEN_KEY, token);
      await _registerTokenToServer(token, "web");
      localStorage.setItem(TOKEN_REFRESH_KEY, String(Date.now()));
      console.log("[FCM] 토큰 자동 갱신 완료");
    }
  } catch (e) {
    console.warn("[FCM] 토큰 자동 갱신 실패:", e);
  }
}

/** 서버에 토큰 등록/갱신 (apiFetch 의존 없이 직접 fetch) */
async function _registerTokenToServer(fcmToken: string, platform: string): Promise<void> {
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  let authHeaders: Record<string, string> = {};

  const devUid = localStorage.getItem("dev_uid");
  if (devUid) {
    authHeaders = { "X-Dev-UID": devUid };
  } else {
    try {
      const { waitForAuth, getIdToken } = await import("./auth");
      await waitForAuth();
      const idToken = await getIdToken();
      if (idToken) authHeaders = { Authorization: `Bearer ${idToken}` };
    } catch { /* 미인증 → 스킵 */ }
  }

  if (!authHeaders.Authorization && !authHeaders["X-Dev-UID"]) return;

  await fetch(`${API_BASE}/me/push-tokens`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders },
    body: JSON.stringify({ fcm_token: fcmToken, platform }),
  });
}

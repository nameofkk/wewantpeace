/**
 * Firebase Cloud Messaging Service Worker.
 * 백그라운드 푸시 알림 수신 처리.
 */
importScripts("https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js");

// 환경변수는 SW에서 접근 불가 → next.config.js에서 PUBLIC 변수 주입 또는 하드코딩
// 실제 배포 시에는 /api/fcm-config 엔드포인트로 동적 주입 가능
firebase.initializeApp({
  apiKey: self.__FIREBASE_API_KEY__ || "",
  authDomain: self.__FIREBASE_AUTH_DOMAIN__ || "",
  projectId: self.__FIREBASE_PROJECT_ID__ || "wewantpeace",
  storageBucket: self.__FIREBASE_STORAGE_BUCKET__ || "",
  messagingSenderId: self.__FIREBASE_MESSAGING_SENDER_ID__ || "",
  appId: self.__FIREBASE_APP_ID__ || "",
});

const messaging = firebase.messaging();

// 백그라운드 메시지 처리
messaging.onBackgroundMessage((payload) => {
  console.log("[FCM SW] 백그라운드 메시지:", payload);

  const { title, body, icon } = payload.notification || {};
  const data = payload.data || {};

  self.registration.showNotification(title || "WeWantPeace 알림", {
    body: body || "",
    icon: icon || "/icons/icon-192.png",
    badge: "/icons/icon-96.png",
    tag: data.cluster_id || "wwp-notification",
    data: { url: data.cluster_id ? `/issues/${data.cluster_id}` : "/" },
    actions: [
      { action: "view", title: "자세히 보기" },
      { action: "dismiss", title: "닫기" },
    ],
  });
});

// 알림 클릭 처리
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  if (event.action === "dismiss") return;

  const url = event.notification.data?.url || "/";
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        for (const client of clientList) {
          if (client.url.includes(self.location.origin) && "focus" in client) {
            client.navigate(url);
            return client.focus();
          }
        }
        return clients.openWindow(url);
      })
  );
});

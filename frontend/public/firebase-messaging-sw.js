/**
 * Firebase Cloud Messaging Service Worker.
 * 백그라운드 푸시 알림 수신 처리.
 */
importScripts("https://www.gstatic.com/firebasejs/10.7.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.7.0/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "AIzaSyBlJf58F_C9hkIry1eEV185-S1EQZmt2ps",
  authDomain: "auth.wewantpeace.live",
  projectId: "wewantpeace-14660",
  storageBucket: "wewantpeace-14660.firebasestorage.app",
  messagingSenderId: "736999139205",
  appId: "1:736999139205:web:50b36428d7a3fc25e806ec",
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const data = payload.data || {};
  const title = data.title || payload.notification?.title || "WeWantPeace 알림";
  const body = data.body || payload.notification?.body || "";

  self.registration.showNotification(title, {
    body,
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-96.png",
    tag: data.cluster_id || "wwp-notification",
    data: { url: data.cluster_id && data.cluster_id !== "test" ? `/issues/${data.cluster_id}` : "/" },
    actions: [
      { action: "view", title: "자세히 보기" },
      { action: "dismiss", title: "닫기" },
    ],
  });
});

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

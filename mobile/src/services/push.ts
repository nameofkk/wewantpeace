/**
 * 네이티브 푸시 알림 서비스.
 * - Android 알림 채널 생성 (HIGH / MAX importance)
 * - FCM 토큰 획득/갱신
 * - 포그라운드/백그라운드 메시지 수신
 * - 알림 클릭 → URL 반환
 */

import messaging from "@react-native-firebase/messaging";
import notifee, { AndroidImportance } from "@notifee/react-native";
import { Platform, PermissionsAndroid } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { CHANNEL_ALERTS, CHANNEL_CRITICAL, API_BASE } from "../utils/constants";

const FCM_TOKEN_KEY = "@wwp_fcm_token";

/**
 * Android 알림 채널 생성 (Notifee 사용)
 */
export async function createNotificationChannels(): Promise<void> {
  if (Platform.OS !== "android") return;

  await notifee.createChannel({
    id: CHANNEL_ALERTS,
    name: "WeWantPeace Alerts",
    importance: AndroidImportance.HIGH,
    vibration: true,
    badge: true,
  });

  await notifee.createChannel({
    id: CHANNEL_CRITICAL,
    name: "WeWantPeace Critical",
    importance: AndroidImportance.HIGH,
    vibration: true,
    badge: true,
  });
}

/**
 * 푸시 알림 권한 요청 + FCM 토큰 획득
 */
export async function requestPushPermissionAndGetToken(): Promise<string | null> {
  try {
    // Android 13+ POST_NOTIFICATIONS 권한 요청
    if (Platform.OS === "android" && Platform.Version >= 33) {
      const granted = await PermissionsAndroid.request(
        PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS,
      );
      if (granted !== PermissionsAndroid.RESULTS.GRANTED) {
        return null;
      }
    }

    // iOS 권한 요청
    if (Platform.OS === "ios") {
      const authStatus = await messaging().requestPermission();
      const enabled =
        authStatus === messaging.AuthorizationStatus.AUTHORIZED ||
        authStatus === messaging.AuthorizationStatus.PROVISIONAL;
      if (!enabled) return null;
    }

    const token = await messaging().getToken();
    if (token) {
      await AsyncStorage.setItem(FCM_TOKEN_KEY, token);
    }
    return token;
  } catch (e) {
    console.warn("[Push] 토큰 획득 실패:", e);
    return null;
  }
}

/**
 * 백엔드에 FCM 토큰 등록
 */
export async function registerTokenWithBackend(
  fcmToken: string,
  authToken: string,
): Promise<void> {
  const platform = Platform.OS; // "android" | "ios"
  try {
    await fetch(`${API_BASE}/me/push-tokens`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify({ fcm_token: fcmToken, platform }),
    });
  } catch (e) {
    console.warn("[Push] 토큰 등록 실패:", e);
  }
}

/**
 * 토큰 리프레시 리스너 등록
 */
export function setupTokenRefreshListener(
  onNewToken: (token: string) => void,
): () => void {
  return messaging().onTokenRefresh(async (token) => {
    await AsyncStorage.setItem(FCM_TOKEN_KEY, token);
    onNewToken(token);
  });
}

/**
 * 포그라운드 메시지 수신 리스너
 * 포그라운드에서는 notification 필드가 자동 표시되지 않으므로
 * Notifee를 사용해 로컬 알림으로 직접 표시.
 */
export function setupForegroundMessageHandler(
  onMessage: (data: Record<string, string>) => void,
): () => void {
  return messaging().onMessage(async (remoteMessage) => {
    const data = remoteMessage.data as Record<string, string> | undefined;
    const notification = remoteMessage.notification;

    // Notifee로 로컬 알림 표시 (heads-up)
    const title = data?.title || notification?.title || "WeWantPeace";
    const body = data?.body || notification?.body || "";
    const severity = parseInt(data?.severity || "0", 10);
    const channelId = severity >= 90 ? CHANNEL_CRITICAL : CHANNEL_ALERTS;

    try {
      await notifee.displayNotification({
        title,
        body,
        android: {
          channelId,
          smallIcon: "notification_icon",
          pressAction: { id: "default" },
        },
        data: data || {},
      });
    } catch (e) {
      console.warn("[Push] 포그라운드 알림 표시 실패:", e);
    }

    if (data) {
      onMessage(data);
    }
  });
}

/**
 * 백그라운드 메시지 핸들러 등록
 * (App.tsx 최상단 or index.js에서 호출)
 */
export function registerBackgroundHandler(): void {
  messaging().setBackgroundMessageHandler(async (_remoteMessage) => {
    // notification 필드가 있으면 시스템이 자동 표시.
    // data-only 메시지 처리가 필요하면 여기에 추가.
  });
}

/**
 * 알림 클릭 → URL 반환 (앱이 백그라운드에 있었을 때)
 */
export function setupNotificationOpenedHandler(
  onUrl: (url: string) => void,
): () => void {
  return messaging().onNotificationOpenedApp((remoteMessage) => {
    const clusterId = remoteMessage.data?.cluster_id;
    if (clusterId && clusterId !== "test") {
      onUrl(`/issues/${clusterId}`);
    }
  });
}

/**
 * 앱이 완전히 종료된 상태에서 알림으로 열렸을 때 URL 반환
 */
export async function getInitialNotificationUrl(): Promise<string | null> {
  const remoteMessage = await messaging().getInitialNotification();
  if (remoteMessage?.data?.cluster_id) {
    const clusterId = remoteMessage.data.cluster_id;
    if (clusterId !== "test") {
      return `/issues/${clusterId}`;
    }
  }
  return null;
}

/**
 * 저장된 FCM 토큰 반환
 */
export async function getStoredToken(): Promise<string | null> {
  return AsyncStorage.getItem(FCM_TOKEN_KEY);
}

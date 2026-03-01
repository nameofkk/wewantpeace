/**
 * 네이티브 푸시 알림 서비스.
 * - Android 알림 채널 생성 (HIGH / MAX importance)
 * - FCM 토큰 획득/갱신
 * - 포그라운드/백그라운드 메시지 수신
 * - 알림 클릭 → URL 반환
 */

import messaging from "@react-native-firebase/messaging";
import { Platform, PermissionsAndroid } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { CHANNEL_ALERTS, CHANNEL_CRITICAL, API_BASE } from "../utils/constants";

const FCM_TOKEN_KEY = "@wwp_fcm_token";

/**
 * Android 알림 채널 생성
 */
export async function createNotificationChannels(): Promise<void> {
  if (Platform.OS !== "android") return;

  // react-native-firebase v21+에서는 messaging().android가 없으므로
  // Notifee 없이 네이티브 채널은 expo prebuild의 AndroidManifest에서 설정하거나
  // 여기서는 Firebase messaging이 default channel을 사용하도록 둡니다.
  // 실제 채널 설정은 android/app/src/main/java 네이티브 코드 또는 expo config plugin에서 처리.
  // 아래는 firebase messaging의 default notification channel 설정.
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
  return messaging().onTokenRefresh((token) => {
    AsyncStorage.setItem(FCM_TOKEN_KEY, token);
    onNewToken(token);
  });
}

/**
 * 포그라운드 메시지 수신 리스너
 * 포그라운드에서는 notification 필드가 자동 표시되지 않으므로
 * 로컬 알림으로 직접 표시해야 함.
 * (여기서는 콜백으로 위임)
 */
export function setupForegroundMessageHandler(
  onMessage: (data: Record<string, string>) => void,
): () => void {
  return messaging().onMessage(async (remoteMessage) => {
    const data = remoteMessage.data as Record<string, string> | undefined;
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

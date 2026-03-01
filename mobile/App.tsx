import React, { useEffect, useState, useCallback, useRef } from "react";
import { SafeAreaView, StyleSheet, Platform, StatusBar, Linking } from "react-native";
import * as SplashScreen from "expo-splash-screen";
import AppWebView, {
  sendMessageToWeb,
  webViewRef,
} from "./src/components/AppWebView";
import {
  createNotificationChannels,
  requestPushPermissionAndGetToken,
  registerTokenWithBackend,
  setupTokenRefreshListener,
  setupForegroundMessageHandler,
  setupNotificationOpenedHandler,
  getInitialNotificationUrl,
  registerBackgroundHandler,
} from "./src/services/push";
import {
  initIAP,
  cleanupIAP,
  getProducts,
  purchaseProduct,
  setupPurchaseListeners,
  finishPurchase,
  verifyPurchaseWithBackend,
  ErrorCode,
} from "./src/services/iap";
import type { WebToNativeMessage } from "./src/services/bridge";

// 백그라운드 메시지 핸들러 (앱 외부)
try {
  registerBackgroundHandler();
} catch (e) {
  console.warn("[App] 백그라운드 핸들러 등록 실패:", e);
}

// 스플래시 자동 숨김 방지
SplashScreen.preventAutoHideAsync().catch(() => {});

export default function App() {
  const [initialPath, setInitialPath] = useState<string | undefined>(undefined);
  const [ready, setReady] = useState(false);

  // 현재 인증 토큰 (웹에서 전달받음)
  const authTokenRef = useRef<string | null>(null);

  // ── 초기화 ──
  useEffect(() => {
    async function init() {
      try {
        // 1. Android 알림 채널
        await createNotificationChannels();
      } catch (e) {
        console.warn("[App] 알림 채널 생성 실패:", e);
      }

      try {
        // 2. IAP 초기화 (타임아웃 5초)
        await Promise.race([
          initIAP(),
          new Promise((_, reject) =>
            setTimeout(() => reject(new Error("IAP timeout")), 5000),
          ),
        ]);
      } catch (e) {
        console.warn("[App] IAP 초기화 실패/타임아웃:", e);
      }

      try {
        // 3. 앱 종료 상태 알림으로 열림 → initialUrl
        const notifUrl = await getInitialNotificationUrl();
        if (notifUrl) {
          setInitialPath(notifUrl);
        }
      } catch (e) {
        console.warn("[App] 초기 알림 URL 확인 실패:", e);
      }

      setReady(true);
      // 스플래시는 WebView 첫 로드 완료 시 숨김 (onFirstLoadComplete)
    }

    init();

    return () => {
      cleanupIAP();
    };
  }, []);

  // ── 푸시 리스너 ──
  useEffect(() => {
    // 알림 클릭 → WebView 네비게이션
    const unsubOpen = setupNotificationOpenedHandler((url) => {
      sendMessageToWeb({ type: "PUSH_NOTIFICATION_CLICK", payload: { url } });
    });

    // 포그라운드 메시지 → 데이터만 로그 (notification 필드가 있으면 시스템 표시)
    const unsubFg = setupForegroundMessageHandler((_data) => {
      // 포그라운드에서는 네이티브 notification이 자동 표시됨 (notification payload)
      // data-only 메시지 처리가 필요하면 여기에 추가
    });

    // 토큰 리프레시
    const unsubRefresh = setupTokenRefreshListener((newToken) => {
      const authToken = authTokenRef.current;
      if (authToken) {
        registerTokenWithBackend(newToken, authToken);
      }
    });

    return () => {
      try { unsubOpen(); } catch {}
      try { unsubFg(); } catch {}
      try { unsubRefresh(); } catch {}
    };
  }, []);

  // ── IAP 리스너 ──
  useEffect(() => {
    setupPurchaseListeners(
      async (purchase) => {
        const authToken = authTokenRef.current;
        if (!authToken) {
          sendMessageToWeb({
            type: "PURCHASE_RESULT",
            payload: { success: false, error: "Not authenticated" },
          });
          return;
        }

        // 백엔드 검증
        const verified = await verifyPurchaseWithBackend(purchase, authToken);

        // 거래 완료
        await finishPurchase(purchase);

        // 결과를 웹에 전달
        sendMessageToWeb({
          type: "PURCHASE_RESULT",
          payload: {
            success: verified,
            productId: purchase.productId,
            purchaseToken: purchase.purchaseToken || undefined,
            transactionId: purchase.transactionId || undefined,
            error: verified ? undefined : "Verification failed",
          },
        });
      },
      (error) => {
        const cancelled = error.code === ErrorCode.UserCancelled;
        sendMessageToWeb({
          type: "PURCHASE_RESULT",
          payload: {
            success: false,
            cancelled,
            error: cancelled ? undefined : error.message,
          },
        });
      },
    );
  }, []);

  // ── Web → Native 메시지 핸들러 ──
  const handleNativeMessage = useCallback(
    async (msg: WebToNativeMessage) => {
      switch (msg.type) {
        case "PURCHASE_REQUEST": {
          authTokenRef.current = msg.payload.authToken;
          try {
            await purchaseProduct(msg.payload.productId);
          } catch (e) {
            sendMessageToWeb({
              type: "PURCHASE_RESULT",
              payload: {
                success: false,
                error: (e as Error).message,
              },
            });
          }
          break;
        }

        case "GET_PRODUCTS": {
          const products = await getProducts();
          sendMessageToWeb({
            type: "PRODUCTS_RESULT",
            payload: { products },
          });
          break;
        }

        case "GET_FCM_TOKEN": {
          const token = await requestPushPermissionAndGetToken();
          if (token) {
            sendMessageToWeb({
              type: "FCM_TOKEN",
              payload: { token },
            });
          }
          break;
        }

        case "REGISTER_FCM_TOKEN": {
          authTokenRef.current = msg.payload.authToken;
          const storedToken = await requestPushPermissionAndGetToken();
          if (storedToken) {
            await registerTokenWithBackend(
              storedToken,
              msg.payload.authToken,
            );
            sendMessageToWeb({
              type: "FCM_TOKEN",
              payload: { token: storedToken },
            });
          }
          break;
        }

        case "RESTORE_PURCHASES": {
          authTokenRef.current = msg.payload.authToken;
          // react-native-iap의 getAvailablePurchases()로 복원
          // 현재는 미구현 (필요시 추가)
          break;
        }

        case "OPEN_URL": {
          // mailto:/tel: 등 WebView에서 직접 열 수 없는 URL → OS 기본 앱
          Linking.openURL(msg.payload.url).catch(() => {});
          break;
        }
      }
    },
    [],
  );

  // WebView 첫 로드 완료 → 스플래시 숨기기
  const handleFirstLoadComplete = useCallback(() => {
    SplashScreen.hideAsync().catch(() => {});
  }, []);

  if (!ready) return null;

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar
        barStyle="light-content"
        backgroundColor="#1A1A2E"
        translucent={false}
      />
      <AppWebView
        initialPath={initialPath}
        onNativeMessage={handleNativeMessage}
        onFirstLoadComplete={handleFirstLoadComplete}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1A1A2E",
    // Android SafeAreaView는 StatusBar를 처리하지 않으므로 수동 패딩
    paddingTop: Platform.OS === "android" ? StatusBar.currentHeight : 0,
  },
});

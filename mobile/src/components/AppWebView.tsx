/**
 * 메인 WebView 컴포넌트.
 * - wewantpeace.live 로드
 * - Native 브릿지 주입
 * - 외부 링크 시스템 브라우저 열기
 * - Android 뒤로가기 지원
 */

import React, { useRef, useCallback, useEffect, useState } from "react";
import {
  BackHandler,
  Platform,
  Linking,
  StyleSheet,
  View,
  ActivityIndicator,
} from "react-native";
import { WebView, type WebViewNavigation } from "react-native-webview";
import type { WebViewMessageEvent } from "react-native-webview";
import { WEB_URL, API_BASE } from "../utils/constants";
import {
  getInjectedJavaScript,
  parseWebMessage,
  sendToWebView,
  type WebToNativeMessage,
  type NativeToWebMessage,
} from "../services/bridge";

interface AppWebViewProps {
  initialPath?: string;
  onNativeMessage: (msg: WebToNativeMessage) => void;
  onFirstLoadComplete?: () => void;
}

export const webViewRef = React.createRef<WebView>();

// Google/Firebase OAuth 인증에 필요한 도메인
// OAuth/인증에 필요한 외부 도메인
const AUTH_DOMAINS = [
  "accounts.google.com",
  "apis.google.com",
  "firebaseapp.com",
  "firebaseio.com",
  "googleapis.com",
  "gstatic.com",
  "google.com/recaptcha",
  "kauth.kakao.com",
  "accounts.kakao.com",
];

// Google OAuth는 WebView(user-agent에 "wv" 포함)를 차단함.
// 표준 Chrome UA를 사용하여 우회.
const CHROME_USER_AGENT =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.135 Mobile Safari/537.36";

export default function AppWebView({
  initialPath,
  onNativeMessage,
  onFirstLoadComplete,
}: AppWebViewProps) {
  const [canGoBack, setCanGoBack] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const firstLoadDone = useRef(false);

  const startUrl = initialPath
    ? `${WEB_URL}${initialPath}`
    : WEB_URL;

  // Android 뒤로가기 처리
  useEffect(() => {
    if (Platform.OS !== "android") return;

    const handler = BackHandler.addEventListener("hardwareBackPress", () => {
      if (canGoBack && webViewRef.current) {
        webViewRef.current.goBack();
        return true;
      }
      return false;
    });

    return () => handler.remove();
  }, [canGoBack]);

  const handleNavigationStateChange = useCallback(
    (navState: WebViewNavigation) => {
      setCanGoBack(navState.canGoBack);
    },
    [],
  );

  const handleMessage = useCallback(
    (event: WebViewMessageEvent) => {
      const msg = parseWebMessage(event.nativeEvent.data);
      if (msg) {
        onNativeMessage(msg);
      }
    },
    [onNativeMessage],
  );

  /**
   * 외부 링크는 시스템 브라우저로 열기.
   * wewantpeace.live 도메인(www 포함)만 WebView 내부에서 로드.
   */
  const handleShouldStartLoad = useCallback(
    (event: { url: string }): boolean => {
      const { url } = event;

      // 내부 도메인 (www / non-www 모두 허용)
      if (
        url.startsWith("https://wewantpeace.live") ||
        url.startsWith("https://www.wewantpeace.live") ||
        url.startsWith(API_BASE) ||
        url.startsWith("about:") ||
        url.startsWith("data:")
      ) {
        return true;
      }

      // Google/Firebase OAuth 도메인 → WebView 내부에서 로드
      if (AUTH_DOMAINS.some((domain) => url.includes(domain))) {
        return true;
      }

      // 외부 링크 → 시스템 브라우저
      Linking.openURL(url).catch(() => {});
      return false;
    },
    [],
  );

  // 로딩 타임아웃: 15초 후 강제 로딩 오버레이 제거
  useEffect(() => {
    if (!initialLoading) return;
    const timer = setTimeout(() => {
      setInitialLoading(false);
      if (!firstLoadDone.current) {
        firstLoadDone.current = true;
        onFirstLoadComplete?.();
      }
    }, 15000);
    return () => clearTimeout(timer);
  }, [initialLoading, onFirstLoadComplete]);

  const handleLoadEnd = useCallback(() => {
    if (!firstLoadDone.current) {
      firstLoadDone.current = true;
      setInitialLoading(false);
      onFirstLoadComplete?.();
    }
  }, [onFirstLoadComplete]);

  return (
    <View style={styles.container}>
      <WebView
        ref={webViewRef}
        source={{ uri: startUrl }}
        style={styles.webview}
        userAgent={CHROME_USER_AGENT}
        injectedJavaScriptBeforeContentLoaded={getInjectedJavaScript()}
        onNavigationStateChange={handleNavigationStateChange}
        onMessage={handleMessage}
        onShouldStartLoadWithRequest={handleShouldStartLoad}
        onLoadEnd={handleLoadEnd}
        onError={(syntheticEvent) => {
          console.warn("[WebView] 로드 에러:", syntheticEvent.nativeEvent);
          handleLoadEnd();
        }}
        onHttpError={(syntheticEvent) => {
          console.warn("[WebView] HTTP 에러:", syntheticEvent.nativeEvent.statusCode);
        }}
        javaScriptEnabled
        domStorageEnabled
        startInLoadingState={false}
        allowsBackForwardNavigationGestures={Platform.OS === "ios"}
        mediaPlaybackRequiresUserAction={false}
        allowsInlineMediaPlayback
        mixedContentMode="never"
        sharedCookiesEnabled
        thirdPartyCookiesEnabled
        cacheEnabled
        cacheMode="LOAD_DEFAULT"
        setSupportMultipleWindows={false}
        androidLayerType="hardware"
        overScrollMode="never"
        originWhitelist={["https://*", "http://*"]}
      />
      {initialLoading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color="#3b82f6" />
        </View>
      )}
    </View>
  );
}

/**
 * 외부에서 WebView로 메시지 전송 헬퍼
 */
export function sendMessageToWeb(message: NativeToWebMessage): void {
  sendToWebView(webViewRef, message);
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1A1A2E",
  },
  webview: {
    flex: 1,
    backgroundColor: "#1A1A2E",
  },
  loadingOverlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#1A1A2E",
    justifyContent: "center",
    alignItems: "center",
  },
});

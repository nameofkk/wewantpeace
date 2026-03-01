/**
 * WebView <-> Native 통신 브릿지.
 *
 * Web→Native: window.ReactNativeWebView.postMessage(JSON)
 * Native→Web: webViewRef.injectJavaScript → window.__handleNativeMessage(msg)
 */

import { WebView } from "react-native-webview";
import { Platform } from "react-native";
import { RefObject } from "react";

// ── Web → Native 메시지 타입 ──
export type WebToNativeMessage =
  | { type: "PURCHASE_REQUEST"; payload: { productId: string; authToken: string } }
  | { type: "GET_PRODUCTS"; payload: Record<string, never> }
  | { type: "GET_FCM_TOKEN"; payload: Record<string, never> }
  | { type: "RESTORE_PURCHASES"; payload: { authToken: string } }
  | { type: "REGISTER_FCM_TOKEN"; payload: { token: string; authToken: string } };

// ── Native → Web 메시지 타입 ──
export type NativeToWebMessage =
  | { type: "PURCHASE_RESULT"; payload: { success: boolean; cancelled?: boolean; error?: string; productId?: string; purchaseToken?: string; transactionId?: string } }
  | { type: "PRODUCTS_RESULT"; payload: { products: Array<{ productId: string; title: string; price: string }> } }
  | { type: "FCM_TOKEN"; payload: { token: string } }
  | { type: "PUSH_NOTIFICATION_CLICK"; payload: { url: string } };

/**
 * WebView에 주입할 JavaScript (로드 전).
 * window.__REACT_NATIVE__, __NATIVE_PLATFORM__, __nativeBridge 설정.
 */
export function getInjectedJavaScript(): string {
  const platform = Platform.OS; // "android" | "ios"
  return `
    (function() {
      window.__REACT_NATIVE__ = true;
      window.__NATIVE_PLATFORM__ = "${platform}";
      window.__nativeBridge = {
        postToNative: function(type, payload) {
          if (window.ReactNativeWebView) {
            window.ReactNativeWebView.postMessage(JSON.stringify({ type: type, payload: payload || {} }));
          }
        }
      };
      // Native→Web 메시지 핸들러 (네이티브에서 injectJavaScript로 호출)
      window.__handleNativeMessage = function(msg) {
        // 이벤트 디스패치 → 웹 코드에서 addEventListener로 수신
        window.dispatchEvent(new CustomEvent('nativeMessage', { detail: msg }));
      };
    })();
    true;
  `;
}

/**
 * Native → WebView 메시지 전송
 */
export function sendToWebView(
  webViewRef: RefObject<WebView | null>,
  message: NativeToWebMessage,
): void {
  const js = `
    if (window.__handleNativeMessage) {
      window.__handleNativeMessage(${JSON.stringify(message)});
    }
    true;
  `;
  webViewRef.current?.injectJavaScript(js);
}

/**
 * Web→Native 메시지 파싱 (onMessage 핸들러에서 사용)
 */
export function parseWebMessage(data: string): WebToNativeMessage | null {
  try {
    const msg = JSON.parse(data);
    if (msg && typeof msg.type === "string") {
      return msg as WebToNativeMessage;
    }
  } catch {
    // ignore parse errors
  }
  return null;
}

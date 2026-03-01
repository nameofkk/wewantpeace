/**
 * 플랫폼 감지: web / android-twa / android-native / ios-native / ios-app
 */

export type AppPlatform = "web" | "android-twa" | "android-native" | "ios-native" | "ios-app";

declare global {
  interface Window {
    getDigitalGoodsService?: (paymentMethod: string) => Promise<unknown>;
    webkit?: {
      messageHandlers?: {
        storekit?: {
          postMessage: (msg: unknown) => void;
        };
      };
    };
    __IOS_APP__?: boolean;
    __REACT_NATIVE__?: boolean;
    __NATIVE_PLATFORM__?: "android" | "ios";
    ReactNativeWebView?: {
      postMessage: (data: string) => void;
    };
    __nativeBridge?: {
      postToNative: (type: string, payload?: unknown) => void;
    };
    __handleNativeMessage?: (msg: unknown) => void;
  }
}

let _cachedPlatform: AppPlatform | null = null;

export function detectPlatform(): AppPlatform {
  if (_cachedPlatform) return _cachedPlatform;

  if (typeof window === "undefined") {
    _cachedPlatform = "web";
    return _cachedPlatform;
  }

  // React Native WebView (최우선 감지)
  if (window.__REACT_NATIVE__) {
    if (window.__NATIVE_PLATFORM__ === "ios") {
      _cachedPlatform = "ios-native";
    } else {
      _cachedPlatform = "android-native";
    }
    return _cachedPlatform;
  }

  // Android TWA: Digital Goods API 지원 여부
  if ("getDigitalGoodsService" in window) {
    _cachedPlatform = "android-twa";
    return _cachedPlatform;
  }

  // iOS 네이티브 앱: StoreKit 브릿지 또는 플래그 존재
  if (
    window.__IOS_APP__ ||
    window.webkit?.messageHandlers?.storekit
  ) {
    _cachedPlatform = "ios-app";
    return _cachedPlatform;
  }

  _cachedPlatform = "web";
  return _cachedPlatform;
}

export function isNativeApp(): boolean {
  const platform = detectPlatform();
  return platform === "android-twa" || platform === "android-native" || platform === "ios-native" || platform === "ios-app";
}

export function isReactNative(): boolean {
  const platform = detectPlatform();
  return platform === "android-native" || platform === "ios-native";
}

/**
 * 모바일 브라우저 여부 (웹에서 앱 설치 유도 시 사용)
 */
export function isMobileBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
}

export function isAndroidBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Android/i.test(navigator.userAgent);
}

export function isIOSBrowser(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPhone|iPad|iPod/i.test(navigator.userAgent);
}

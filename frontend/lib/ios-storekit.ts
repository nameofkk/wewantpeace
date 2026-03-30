/**
 * iOS 네이티브 StoreKit 2 브릿지.
 * WKWebView 환경에서 window.webkit.messageHandlers.storekit 사용.
 */

interface StoreKitResult {
  action: string;
  success: boolean;
  cancelled?: boolean;
  error?: string;
  transactionId?: string;
  originalTransactionId?: string;
  productId?: string;
  transactions?: Array<{
    transactionId: string;
    originalTransactionId: string;
    productId: string;
  }>;
  products?: Array<{
    id: string;
    displayName: string;
    description: string;
    price: string;
    displayPrice: string;
  }>;
}

type StoreKitResolver = (result: StoreKitResult) => void;

let _pendingResolvers: Map<string, StoreKitResolver> = new Map();

// 글로벌 콜백 등록
if (typeof window !== "undefined") {
  (window as unknown as { handleStoreKitResult: (result: StoreKitResult) => void }).handleStoreKitResult = (result: StoreKitResult) => {
    const resolver = _pendingResolvers.get(result.action);
    if (resolver) {
      resolver(result);
      _pendingResolvers.delete(result.action);
    }
  };
}

function postToStoreKit(message: Record<string, unknown>): boolean {
  if (typeof window === "undefined") return false;

  // React Native 환경: 네이티브 브릿지 사용
  if (window.__REACT_NATIVE__ || window.ReactNativeWebView) {
    const action = message.action as string;
    const msgType =
      action === "purchase" ? "PURCHASE_REQUEST" :
      action === "restore" ? "RESTORE_PURCHASES" :
      action === "getProducts" ? "GET_PRODUCTS" : action;

    if (window.__nativeBridge) {
      window.__nativeBridge.postToNative(msgType, message);
    } else if (window.ReactNativeWebView) {
      window.ReactNativeWebView.postMessage(JSON.stringify({ type: msgType, payload: message }));
    }

    // __handleNativeMessage가 없으면 세팅 (결과 수신용)
    if (!window.__handleNativeMessage) {
      window.__handleNativeMessage = (msg: unknown) => {
        window.dispatchEvent(new CustomEvent("nativeMessage", { detail: msg }));
      };
    }

    return true;
  }

  const handler = window.webkit?.messageHandlers?.storekit;
  if (!handler) return false;
  handler.postMessage(message);
  return true;
}

function waitForResult(action: string, timeoutMs: number = 180000): Promise<StoreKitResult> {
  return new Promise((resolve, reject) => {
    _pendingResolvers.set(action, resolve);
    setTimeout(() => {
      if (_pendingResolvers.has(action)) {
        _pendingResolvers.delete(action);
        reject(new Error("StoreKit response timeout"));
      }
    }, timeoutMs);
  });
}

/**
 * StoreKit으로 구독 결제
 * @returns { transactionId, productId } 또는 null (취소)
 */
export async function purchaseViaStoreKit(
  productId: string
): Promise<{ transactionId: string; productId: string } | null> {
  if (!postToStoreKit({ action: "purchase", productId })) {
    throw new Error("StoreKit bridge unavailable");
  }

  const result = await waitForResult("purchase");

  if (!result.success) {
    if (result.cancelled) return null;
    throw new Error(result.error || "Payment failed");
  }

  return {
    transactionId: result.transactionId || "",
    productId: result.productId || productId,
  };
}

/**
 * 구매 복원
 */
export async function restoreViaStoreKit(): Promise<StoreKitResult["transactions"]> {
  if (!postToStoreKit({ action: "restore" })) {
    throw new Error("StoreKit bridge unavailable");
  }

  const result = await waitForResult("restore");

  if (!result.success) {
    throw new Error(result.error || "Restore failed");
  }

  return result.transactions || [];
}

/**
 * 상품 정보 조회
 */
export async function getStoreKitProducts(): Promise<StoreKitResult["products"]> {
  if (!postToStoreKit({ action: "getProducts" })) {
    throw new Error("StoreKit bridge unavailable");
  }

  const result = await waitForResult("getProducts", 30000);

  if (!result.success) {
    throw new Error(result.error || "Product lookup failed");
  }

  return result.products || [];
}

/**
 * 인앱 결제 서비스 (react-native-iap v14).
 * Google Play / App Store 구독 처리.
 */

import {
  initConnection,
  endConnection,
  fetchProducts,
  requestPurchase,
  finishTransaction,
  purchaseUpdatedListener,
  purchaseErrorListener,
  type Purchase,
  type PurchaseError,
  type Product,
  type EventSubscription,
  ErrorCode,
} from "react-native-iap";
import { Platform } from "react-native";
import {
  GOOGLE_PRODUCT_IDS,
  APPLE_PRODUCT_IDS,
  API_BASE,
} from "../utils/constants";

const ALL_SKU_IDS = Platform.OS === "ios"
  ? Object.values(APPLE_PRODUCT_IDS)
  : Object.values(GOOGLE_PRODUCT_IDS);

let _purchaseUpdateSub: EventSubscription | null = null;
let _purchaseErrorSub: EventSubscription | null = null;

/**
 * IAP 초기화
 */
export async function initIAP(): Promise<void> {
  try {
    await initConnection();
  } catch (e) {
    console.warn("[IAP] initConnection 실패:", e);
  }
}

/**
 * IAP 정리
 */
export async function cleanupIAP(): Promise<void> {
  _purchaseUpdateSub?.remove();
  _purchaseErrorSub?.remove();
  _purchaseUpdateSub = null;
  _purchaseErrorSub = null;
  try {
    await endConnection();
  } catch {}
}

/**
 * 상품 목록 조회
 */
export async function getProducts(): Promise<
  Array<{ productId: string; title: string; price: string }>
> {
  try {
    const products = await fetchProducts({
      skus: ALL_SKU_IDS,
      type: "subs",
    });
    if (!products) return [];
    return (products as Product[]).map((p) => ({
      productId: p.id,
      title: p.title || p.id,
      price: p.displayPrice || "",
    }));
  } catch (e) {
    console.warn("[IAP] getProducts 실패:", e);
    return [];
  }
}

/**
 * 구독 결제 실행
 * 결과는 purchaseUpdatedListener를 통해 비동기로 전달됨.
 */
export async function purchaseProduct(productId: string): Promise<void> {
  try {
    if (Platform.OS === "android") {
      await requestPurchase({
        type: "subs",
        request: {
          google: {
            skus: [productId],
          },
        },
      });
    } else {
      await requestPurchase({
        type: "subs",
        request: {
          apple: {
            sku: productId,
          },
        },
      });
    }
  } catch (e) {
    console.warn("[IAP] purchaseProduct 실패:", e);
    throw e;
  }
}

/**
 * 구매 리스너 등록 (성공/실패 콜백)
 */
export function setupPurchaseListeners(
  onPurchase: (purchase: Purchase) => void,
  onError: (error: PurchaseError) => void,
): void {
  _purchaseUpdateSub?.remove();
  _purchaseErrorSub?.remove();

  _purchaseUpdateSub = purchaseUpdatedListener((purchase) => {
    onPurchase(purchase);
  });
  _purchaseErrorSub = purchaseErrorListener((error) => {
    onError(error);
  });
}

/**
 * 거래 완료 처리
 */
export async function finishPurchase(purchase: Purchase): Promise<void> {
  try {
    await finishTransaction({ purchase, isConsumable: false });
  } catch (e) {
    console.warn("[IAP] finishTransaction 실패:", e);
  }
}

/**
 * 백엔드에 구매 검증 요청
 */
export async function verifyPurchaseWithBackend(
  purchase: Purchase,
  authToken: string,
): Promise<boolean> {
  try {
    let url: string;
    let body: Record<string, string>;

    if (Platform.OS === "android") {
      url = `${API_BASE}/subscriptions/store/google/verify`;
      body = {
        purchase_token: purchase.purchaseToken || "",
        product_id: purchase.productId,
      };
    } else {
      url = `${API_BASE}/subscriptions/store/apple/verify`;
      body = {
        transaction_id: (purchase as { transactionId?: string }).transactionId || "",
        product_id: purchase.productId,
      };
    }

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authToken}`,
      },
      body: JSON.stringify(body),
    });

    return res.ok;
  } catch (e) {
    console.warn("[IAP] verifyPurchase 실패:", e);
    return false;
  }
}

export { ErrorCode };

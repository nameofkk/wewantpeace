/**
 * Google Play Billing - Digital Goods API + Payment Request API
 * Android TWA 환경에서만 동작
 *
 * 알려진 제한:
 * - Android 13+ (API 33+)에서 DelegationService 초기화 실패 가능
 *   (Chrome/android-browser-helper 플랫폼 버그, 미해결)
 * - 실패 시 upgrade/client.tsx에서 DodoPayments 웹 결제로 자동 폴백
 */

const PLAY_BILLING_SERVICE = "https://play.google.com/billing";

interface DigitalGoodsService {
  getDetails(itemIds: string[]): Promise<ItemDetails[]>;
}

interface ItemDetails {
  itemId: string;
  title: string;
  description: string;
  price: { currency: string; value: string };
  type?: string;
}

interface PaymentDetailsInit {
  supportedMethods: string;
  data: { sku: string };
}

/**
 * Digital Goods API 사용 가능 여부 확인
 */
export function isDigitalGoodsAvailable(): boolean {
  return typeof window !== "undefined" && "getDigitalGoodsService" in window;
}

/**
 * Digital Goods 서비스 획득
 * 실패 시 null 반환 (에러 로그만 출력, throw 안 함)
 */
async function getService(): Promise<DigitalGoodsService | null> {
  if (!isDigitalGoodsAvailable()) {
    return null;
  }
  try {
    const service = await window.getDigitalGoodsService!(PLAY_BILLING_SERVICE);
    return (service as DigitalGoodsService) ?? null;
  } catch (e) {
    // Android 13+에서 DelegationService 미초기화 → "unsupported context" / "clientAppUnavailable"
    console.warn("[PlayBilling] Digital Goods API 실패:", e);
    return null;
  }
}

/**
 * 상품 정보 조회
 */
export async function getProductDetails(productIds: string[]): Promise<ItemDetails[]> {
  const service = await getService();
  if (!service) return [];
  return service.getDetails(productIds);
}

/**
 * Play Billing으로 구독 결제
 * @returns purchaseToken (성공 시) 또는 null (취소/실패)
 * @throws 결제 불가 시 에러 (호출부에서 웹 결제 폴백 처리)
 *
 * React Native 환경에서는 네이티브 브릿지를 통해 결제를 처리합니다.
 */
export async function purchaseSubscription(
  productId: string,
  authToken?: string,
): Promise<string | null> {
  // React Native 환경: 네이티브 브릿지로 결제 요청
  // ReactNativeWebView는 RN WebView가 네이티브 레벨에서 자동 주입하므로
  // injectedJavaScriptBeforeContentLoaded 실패 시에도 항상 존재
  if (typeof window !== "undefined" && (window.__REACT_NATIVE__ || window.ReactNativeWebView)) {
    // __handleNativeMessage가 없으면 세팅 (결과 수신용)
    if (!window.__handleNativeMessage) {
      window.__handleNativeMessage = (msg: unknown) => {
        window.dispatchEvent(new CustomEvent("nativeMessage", { detail: msg }));
      };
    }

    return new Promise((resolve, reject) => {
      let settled = false;
      const handler = (e: Event) => {
        const msg = (e as CustomEvent).detail;
        if (msg?.type === "PURCHASE_RESULT") {
          settled = true;
          window.removeEventListener("nativeMessage", handler);
          if (msg.payload.success) {
            resolve(msg.payload.purchaseToken || msg.payload.transactionId || "native");
          } else if (msg.payload.cancelled) {
            resolve(null);
          } else {
            reject(new Error(msg.payload.error || "Payment failed"));
          }
        }
      };
      window.addEventListener("nativeMessage", handler);

      // 3분 타임아웃 — 네이티브 브릿지 무응답 시 무한 스피너 방지
      setTimeout(() => {
        if (!settled) {
          window.removeEventListener("nativeMessage", handler);
          reject(new Error("Payment response timeout"));
        }
      }, 180_000);

      const message = JSON.stringify({
        type: "PURCHASE_REQUEST",
        payload: { productId, authToken: authToken || "" },
      });

      // __nativeBridge가 있으면 사용, 없으면 ReactNativeWebView.postMessage 직접 사용
      if (window.__nativeBridge) {
        window.__nativeBridge.postToNative("PURCHASE_REQUEST", {
          productId,
          authToken: authToken || "",
        });
      } else if (window.ReactNativeWebView) {
        window.ReactNativeWebView.postMessage(message);
      } else {
        window.removeEventListener("nativeMessage", handler);
        reject(new Error("Native bridge unavailable"));
      }
    });
  }

  // TWA 환경: Digital Goods API
  const service = await getService();
  if (!service) {
    throw new Error("DGAPI_UNAVAILABLE");
  }

  // 상품 정보 조회
  const details = await service.getDetails([productId]);
  if (!details || details.length === 0) {
    throw new Error("Product not found");
  }

  // Payment Request API로 결제 UI 표시
  const methodData: PaymentDetailsInit[] = [
    {
      supportedMethods: PLAY_BILLING_SERVICE,
      data: { sku: productId },
    },
  ];

  const paymentDetails = {
    total: {
      label: details[0].title,
      amount: {
        currency: details[0].price.currency,
        value: details[0].price.value,
      },
    },
  };

  const request = new PaymentRequest(methodData as PaymentMethodData[], paymentDetails);

  try {
    const response = await request.show();
    const purchaseToken = (response.details as any)?.purchaseToken;

    if (!purchaseToken) {
      await response.complete("fail");
      throw new Error("Purchase token not received");
    }

    await response.complete("success");
    return purchaseToken;
  } catch (e) {
    // 사용자 취소
    if ((e as Error).name === "AbortError") {
      return null;
    }
    throw e;
  }
}

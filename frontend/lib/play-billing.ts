/**
 * Google Play Billing - Digital Goods API + Payment Request API
 * Android TWA 환경에서만 동작
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
 * Digital Goods 서비스 획득
 */
async function getService(): Promise<DigitalGoodsService | null> {
  if (typeof window === "undefined" || !("getDigitalGoodsService" in window)) {
    return null;
  }
  try {
    const service = await window.getDigitalGoodsService!(PLAY_BILLING_SERVICE);
    return service as DigitalGoodsService;
  } catch {
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
 */
export async function purchaseSubscription(productId: string): Promise<string | null> {
  const service = await getService();
  if (!service) {
    throw new Error("Digital Goods API를 사용할 수 없습니다.");
  }

  // 상품 정보 조회
  const details = await service.getDetails([productId]);
  if (!details || details.length === 0) {
    throw new Error("상품 정보를 찾을 수 없습니다.");
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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const purchaseToken = (response.details as any)?.purchaseToken;

    if (!purchaseToken) {
      await response.complete("fail");
      throw new Error("구매 토큰을 받지 못했습니다.");
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

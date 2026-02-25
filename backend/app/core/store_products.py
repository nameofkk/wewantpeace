"""스토어 상품ID ↔ 내부 plan 매핑."""

# Google Play 상품 ID
GOOGLE_PRODUCTS = {
    "com.wewantpeace.pro_monthly": "pro",
    "com.wewantpeace.proplus_monthly": "pro_plus",
}

# Apple App Store 상품 ID
APPLE_PRODUCTS = {
    "com.wewantpeace.pro.monthly": "pro",
    "com.wewantpeace.proplus.monthly": "pro_plus",
}

# 내부 plan → 스토어 상품 ID (역방향 매핑)
PLAN_TO_GOOGLE = {v: k for k, v in GOOGLE_PRODUCTS.items()}
PLAN_TO_APPLE = {v: k for k, v in APPLE_PRODUCTS.items()}

# plan별 금액
PLAN_AMOUNTS = {
    "pro": 4900,
    "pro_plus": 9900,
}


def google_product_to_plan(product_id: str) -> str | None:
    return GOOGLE_PRODUCTS.get(product_id)


def apple_product_to_plan(product_id: str) -> str | None:
    return APPLE_PRODUCTS.get(product_id)

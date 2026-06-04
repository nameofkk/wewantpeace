"""스토어 상품ID ↔ 내부 plan 매핑."""

# Google Play 상품 ID
GOOGLE_PRODUCTS = {
    "com.wewantpeace.pro_monthly": "pro",
    "com.wewantpeace.proplus_monthly": "pro_plus",
    "com.wewantpeace.pro_annual": "pro_annual",
    "com.wewantpeace.proplus_annual": "pro_plus_annual",
    "com.wewantpeace.pro_lifetime": "pro_lifetime",
    "com.wewantpeace.proplus_lifetime": "pro_plus_lifetime",
}

# Apple App Store 상품 ID
APPLE_PRODUCTS = {
    "com.wewantpeace.pro.monthly": "pro",
    "com.wewantpeace.proplus.monthly": "pro_plus",
    "com.wewantpeace.pro.annual": "pro_annual",
    "com.wewantpeace.proplus.annual": "pro_plus_annual",
    "com.wewantpeace.pro.lifetime": "pro_lifetime",
    "com.wewantpeace.proplus.lifetime": "pro_plus_lifetime",
}

# 내부 plan → 스토어 상품 ID (역방향 매핑, monthly만)
PLAN_TO_GOOGLE = {"pro": "com.wewantpeace.pro_monthly", "pro_plus": "com.wewantpeace.proplus_monthly"}
PLAN_TO_APPLE = {"pro": "com.wewantpeace.pro.monthly", "pro_plus": "com.wewantpeace.proplus.monthly"}

# plan별 금액 (USD 센트)
PLAN_AMOUNTS = {
    "pro": 699,               # $6.99
    "pro_plus": 999,           # $9.99
    "pro_annual": 6299,        # $62.99
    "pro_plus_annual": 8999,   # $89.99
    "pro_lifetime": 14999,     # $149.99
    "pro_plus_lifetime": 19999, # $199.99
}


def google_product_to_plan(product_id: str) -> str | None:
    return GOOGLE_PRODUCTS.get(product_id)


def apple_product_to_plan(product_id: str) -> str | None:
    return APPLE_PRODUCTS.get(product_id)


def plan_to_base(plan: str) -> str:
    """plan key → base plan (user.plan은 'pro'/'pro_plus'만 저장)."""
    if plan.startswith("pro_plus"):
        return "pro_plus"
    if plan.startswith("pro"):
        return "pro"
    return plan

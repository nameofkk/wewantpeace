# DodoPayments 웹 결제 통합 플랜

## Context
WeWantPeace 웹 결제를 기존 LemonSqueezy에서 DodoPayments로 교체. DodoPayments가 승인되어 바로 통합 필요. 기존 구조(LemonSqueezy 라우터)를 참고해 동일한 패턴으로 구현.

## 변경 파일 목록

### 백엔드 (신규)
1. **`backend/app/routers/dodopayments.py`** — 새 라우터 (기존 `lemonsqueezy.py` 패턴 동일)
2. **`backend/alembic/versions/XXXX_add_dodo_fields.py`** — DB 마이그레이션

### 백엔드 (수정)
3. **`backend/app/core/config.py`** — DodoPayments 환경변수 추가
4. **`backend/app/models/subscription.py`** — dodo 필드 추가
5. **`backend/app/main.py`** — 새 라우터 등록

### 프론트엔드 (수정)
6. **`frontend/lib/api.ts`** — `createDodoCheckout()` 함수 추가
7. **`frontend/app/(main)/upgrade/page.tsx`** — LemonSqueezy → DodoPayments 호출 전환

---

## 구현 상세

### Step 1: `backend/app/core/config.py` — 환경변수 추가

```python
# DodoPayments
dodo_api_key: str = ""           # DODO_API_KEY
dodo_webhook_key: str = ""       # DODO_WEBHOOK_KEY
dodo_product_pro: str = ""       # DodoPayments 대시보드에서 생성한 Pro 상품 ID
dodo_product_proplus: str = ""   # DodoPayments 대시보드에서 생성한 Pro+ 상품 ID
dodo_environment: str = "live_mode"  # "test_mode" | "live_mode"
```

### Step 2: `backend/app/models/subscription.py` — 필드 추가

기존 `ls_*` 필드와 동일한 패턴으로 `dodo_*` 필드 추가:

```python
# DodoPayments 필드
dodo_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
dodo_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
dodo_product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

### Step 3: Alembic 마이그레이션

`subscriptions` 테이블에 3개 컬럼 추가:
- `dodo_subscription_id` VARCHAR(64) NULLABLE
- `dodo_customer_id` VARCHAR(64) NULLABLE
- `dodo_product_id` VARCHAR(64) NULLABLE

### Step 4: `backend/app/routers/dodopayments.py` — 핵심 라우터

prefix: `/payments/dodo`, tags: `["dodopayments"]`

#### 엔드포인트 1: `POST /payments/dodo/create-checkout`
- 인증 필요 (`get_current_user`)
- Body: `{ plan: "pro" | "pro_plus" }`
- 동작:
  1. 기존 활성 구독 처리 (LemonSqueezy와 동일 로직)
  2. DodoPayments SDK로 checkout session 생성:
     ```python
     from dodopayments import DodoPayments

     client = DodoPayments(
         bearer_token=settings.dodo_api_key,
         environment=settings.dodo_environment,
     )
     session = client.checkout_sessions.create(
         product_cart=[{"product_id": product_id, "quantity": 1}],
         customer={"email": user.email or "", "name": user.display_name or ""},
         return_url="https://www.wewantpeace.live/upgrade/success",
         metadata={"user_id": str(user.id), "plan": plan},
     )
     ```
  3. 반환: `{ "checkout_url": session.checkout_url, "plan": plan }`

#### 엔드포인트 2: `POST /payments/dodo/webhook`
- 인증 불필요 (DodoPayments에서 호출)
- Standard Webhooks 서명 검증:
  ```python
  client = DodoPayments(
      bearer_token=settings.dodo_api_key,
      webhook_key=settings.dodo_webhook_key,
  )
  event = client.webhooks.unwrap(payload=raw_body, headers=headers)
  ```
- 이벤트 처리:
  - `subscription.active` → 구독 생성/활성화, user.plan 업데이트
  - `subscription.renewed` → expires_at 갱신, PaymentHistory 기록
  - `subscription.cancelled` → status=cancelled, auto_renewing=False
  - `subscription.expired` → status=expired, user.plan=free
  - `subscription.failed` → status=billing_retry
  - `subscription.on_hold` → status=billing_retry
  - `payment.succeeded` → PaymentHistory 기록
  - `payment.failed` → 로깅

#### 헬퍼 함수
- `_dodo_product_to_plan(product_id)` — product_id → plan 매핑
- `_plan_to_dodo_product(plan)` — plan → product_id 매핑
- `_find_sub_by_dodo_id(dodo_subscription_id, db)` — 구독 조회

### Step 5: `backend/app/main.py` — 라우터 등록

```python
from backend.app.routers import dodopayments as dodopayments_router
...
app.include_router(dodopayments_router.router)
```

### Step 6: `frontend/lib/api.ts` — API 함수 추가

```typescript
export async function createDodoCheckout(plan: string): Promise<{ checkout_url: string }> {
  return apiFetch("/payments/dodo/create-checkout", undefined, {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}
```

### Step 7: `frontend/app/(main)/upgrade/page.tsx` — 체크아웃 전환

`handleLemonSqueezyCheckout` → `handleDodoCheckout`으로 교체:

```typescript
import { createDodoCheckout } from "@/lib/api";

async function handleDodoCheckout(planId: string) {
  const { checkout_url } = await createDodoCheckout(planId);
  if (checkout_url) {
    window.location.href = checkout_url;
  }
}
```

`handleSubscribe()` 내의 `isWeb` 분기에서 `handleLemonSqueezyCheckout` → `handleDodoCheckout` 호출.

---

## 환경변수 (Railway에 설정 필요)

| 변수명 | 설명 |
|--------|------|
| `DODO_API_KEY` | DodoPayments API Bearer 토큰 |
| `DODO_WEBHOOK_KEY` | DodoPayments Webhook 검증 키 |
| `DODO_PRODUCT_PRO` | Pro 플랜 상품 ID |
| `DODO_PRODUCT_PROPLUS` | Pro+ 플랜 상품 ID |
| `DODO_ENVIRONMENT` | `live_mode` 또는 `test_mode` |

---

## 기존 LemonSqueezy 처리

- 라우터/코드는 **삭제하지 않고 유지** (기존 웹훅이 기존 구독에 대해 계속 동작해야 함)
- 프론트엔드에서만 새 결제를 DodoPayments로 전환
- 기존 LS 구독자가 갱신/취소 웹훅을 받으면 기존 `lemonsqueezy.py`가 처리

---

## 검증 방법

1. `DODO_ENVIRONMENT=test_mode`로 설정하여 테스트 결제 진행
2. 백엔드 시작 → `POST /payments/dodo/create-checkout` 호출 → checkout_url 반환 확인
3. DodoPayments 테스트 대시보드에서 webhook 테스트 발송 → 서명 검증 + 구독 생성 확인
4. 프론트엔드에서 Pro 구독 버튼 클릭 → DodoPayments 체크아웃 페이지 리다이렉트 확인
5. 체크아웃 완료 후 `/upgrade/success` 리다이렉트 + user.plan 업데이트 확인

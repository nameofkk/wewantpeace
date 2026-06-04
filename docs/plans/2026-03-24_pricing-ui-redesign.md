# WeWantPeace 가격 정책 변경 + 페이월/결제유도 UI 리디자인

## Context

현재 가격 Pro $3.90/월, Pro+ $6.90/월을 **Option B**로 변경하고, 연간/라이프타임 결제 옵션을 추가한다.
동시에 Claude/ChatGPT 스타일의 결제 주기 토글 UI, 할인율 표기, 체험판 결제 유도 강화를 구현한다.

**최종 가격표:**

| 플랜 | Monthly | Annual (25% off) | Lifetime |
|------|---------|-----------------|----------|
| Pro  | $6.99/월 | $62.99/년 ($5.25/월) | $149.99 |
| Pro+ | $9.99/월 | $89.99/년 ($7.50/월) | $199.99 |

**이미 적용된 변경 (client.tsx에 부분 반영됨):**
- `PRICING` 상수, `BillingCycle` 타입, `billingCycle` 상태 추가
- 결제 주기 토글 UI 삽입
- Pro/Pro+ 카드 가격 동적 표시
- Pro 카드 절약 배지 (연간/라이프타임)

---

## 수정 파일 목록

### A. 프론트엔드 (7개 파일)

| # | 파일 | 변경 |
|---|------|------|
| A1 | `frontend/app/(main)/upgrade/client.tsx` | 이미 일부 적용됨. Pro+ 절약 배지 추가, 체험판 결제 유도 섹션, CTA 버튼 텍스트 갱신 |
| A2 | `frontend/components/ui/PaywallModal.tsx` | CTA 가격 $3.90→$6.99 + 연간 할인 표기 + 체험판 잔여일 표시 |
| A3 | `frontend/lib/legal-data.ts` | 약관 가격 $3.90/$6.90 → $6.99/$9.99 + 연간/라이프타임 가격 추가 (ko+en) |
| A4 | `frontend/lib/i18n.ts` | 새 i18n 키 추가 (연간/라이프타임 레이블, 체험판 유도 문구) |
| A5 | `frontend/app/(main)/feed/client.tsx` | Trial 배너에 가격 표시 + 연간 할인 CTA |
| A6 | `frontend/app/(main)/settings/page.tsx` | Trial 섹션에 잔여일 프로그레스바 + 할인 CTA |
| A7 | `frontend/components/ui/UpgradeNudgeBanner.tsx` | 가격/할인율 표시 추가 |

### B. 백엔드 (5개 파일)

| # | 파일 | 변경 |
|---|------|------|
| B1 | `backend/app/core/store_products.py` | `PLAN_AMOUNTS` 390→699, 690→999 + 연간/라이프타임 매핑 |
| B2 | `backend/app/models/subscription.py` | `default=390`→`699` + `billing_interval` 컬럼 추가 |
| B3 | `backend/app/routers/admin.py` | `AppSettings` 기본값 390→699, 690→999 |
| B4 | `backend/app/core/config.py` | 연간/라이프타임 Dodo 상품 ID 환경변수 4개 추가 |
| B5 | `backend/app/routers/dodopayments.py` | 연간/라이프타임 plan 매핑 + checkout 시 billing_interval 전달 |

### C. DB 마이그레이션 (1개)

| # | 파일 | 변경 |
|---|------|------|
| C1 | `backend/alembic/versions/00XX_add_billing_interval.py` | `billing_interval` 컬럼 추가 (monthly/annual/lifetime) |

### D. Worker (1개)

| # | 파일 | 변경 |
|---|------|------|
| D1 | `worker/tasks.py` | `expire_subscriptions()`에서 lifetime 제외 |

### E. 모바일 (2개, 낮은 우선순위)

| # | 파일 | 변경 |
|---|------|------|
| E1 | `mobile/src/utils/constants.ts` | 연간/라이프타임 product ID 추가 |
| E2 | `ios/WeWantPeace/Config/AppConfig.swift` | 연간/라이프타임 product ID 추가 |

---

## 구현 상세

### A1. upgrade/client.tsx — 남은 작업

**현재 상태:** PRICING 상수, 토글, Pro/Pro+ 가격 동적 표시, Pro 절약 배지 완료.

**남은 작업:**

1. **Pro+ 카드 절약 배지 추가** (Pro 카드와 동일 패턴):
```tsx
{/* Pro+ 기능 리스트 뒤, CTA 버튼 앞에 삽입 */}
{billingCycle === "annual" && (
  <div className="mt-3 flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 px-3 py-2">
    <Tag className="h-3 w-3 text-green-500 shrink-0" />
    <span className="text-[11px] text-green-500 font-medium whitespace-nowrap">
      {lang === "ko" ? "3개월 무료 · 연 $29.89 절약" : "3 months free · Save $29.89/yr"}
    </span>
  </div>
)}
{billingCycle === "lifetime" && (
  <div className="mt-3 flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2">
    <Sparkles className="h-3 w-3 text-amber-500 shrink-0" />
    <span className="text-[11px] text-amber-500 font-medium whitespace-nowrap">
      {lang === "ko" ? "한 번 결제, 평생 이용" : "Pay once, use forever"}
    </span>
  </div>
)}
```

2. **체험판 중 결제 유도 강화** — 업그레이드 페이지 상단에 Trial 전용 배너:
```tsx
{/* 체험판 중일 때: 페이지 상단에 잔여일 + 특별 오퍼 배너 */}
{isCurrentlyTrial && trialEnd && (
  <div className="mb-6 rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 to-orange-500/10 p-4">
    {/* 프로그레스 바 (7일 중 남은 일수) */}
    <div className="flex items-center justify-between mb-2">
      <span className="text-xs font-bold text-amber-400">
        {lang === "ko" ? "무료 체험 중" : "Free Trial Active"}
      </span>
      <span className="text-xs font-semibold text-amber-400">
        {t(lang, "trial_remaining_days", { n: daysLeft })}
      </span>
    </div>
    <div className="h-1.5 rounded-full bg-amber-500/20 overflow-hidden mb-3">
      <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500 transition-all"
           style={{ width: `${Math.max(5, ((7 - daysLeft) / 7) * 100)}%` }} />
    </div>
    <p className="text-[11px] text-foreground/70 mb-2">
      {lang === "ko"
        ? "체험 종료 후 Free 플랜으로 전환됩니다. 지금 구독하면 중단 없이 계속 이용하세요."
        : "After trial ends, you'll switch to Free. Subscribe now for uninterrupted access."}
    </p>
    {billingCycle === "annual" && (
      <p className="text-[11px] font-semibold text-green-500">
        {lang === "ko" ? "💡 연간 구독 시 3개월 무료!" : "💡 Get 3 months free with annual!"}
      </p>
    )}
  </div>
)}
```

3. **푸터에 세금 안내 추가** — 가격에서 "세금 별도" 제거 → 푸터로 이동:
```tsx
<p style={{ wordBreak: "keep-all", lineHeight: "1.7" }}>
  {lang === "ko"
    ? "구독 취소 시 현재 결제 기간 만료까지 서비스 이용 가능 · 세금 별도"
    : "Cancel anytime · Service continues until current billing period ends · Excl. tax"}
</p>
```

### A2. PaywallModal.tsx — 리디자인

**변경 내용:**
1. CTA 버튼 가격: `$3.90` → `$6.99`
2. 연간 할인 표시: CTA 아래에 연간 가격 힌트
3. 체험판 잔여일 표시 (trial 상태인 경우)

```tsx
{/* CTA 버튼 — 수정 */}
<button onClick={handleUpgrade} className="...">
  <Zap className="inline h-4 w-4 mr-1.5 -mt-0.5" />
  {lang === "ko" ? "Pro 시작하기 — $6.99/월" : "Start Pro — $6.99/mo"}
</button>

{/* 연간 할인 힌트 — 신규 */}
<p className="text-center text-[10px] text-green-500/80 mt-1">
  {lang === "ko" ? "연간 구독 시 25% 할인 ($5.25/월)" : "Save 25% with annual ($5.25/mo)"}
</p>
```

**Pro+ 가격 안내도 추가:**
```tsx
{/* Pro 기능 목록 아래에 Pro+ 힌트 */}
<p className="mt-2 text-[10px] text-muted-foreground text-center">
  {lang === "ko" ? "Pro+ ($9.99/월)에서 무제한 기능 사용" : "Unlock everything with Pro+ ($9.99/mo)"}
</p>
```

### A3. legal-data.ts — 가격 업데이트

**라인 31 (ko):** `$3.90` → `$6.99`, `$6.90` → `$9.99`, 연간/라이프타임 가격 추가
**라인 82 (en):** 동일

```
① Pro 구독: 월 $6.99 / 연 $62.99 / 평생 $149.99
   Pro+ 구독: 월 $9.99 / 연 $89.99 / 평생 $199.99 (USD, 부가세 별도)
```

### A4. i18n.ts — 새 키 추가

```typescript
// ko 블록:
billing_monthly: "월간",
billing_annual: "연간",
billing_lifetime: "평생",
billing_annual_hint: "연간 구독 시 25% 할인",
billing_lifetime_hint: "한 번 결제, 평생 이용",
trial_upgrade_banner_title: "무료 체험 중",
trial_upgrade_banner_annual: "💡 연간 구독 시 3개월 무료!",
trial_upgrade_banner_desc: "체험 종료 후 Free 플랜으로 전환됩니다. 지금 구독하면 중단 없이 계속 이용하세요.",
paywall_annual_hint: "연간 구독 시 25% 할인 ($5.25/월)",
paywall_proplus_hint: "Pro+ ($9.99/월)에서 무제한 기능 사용",

// en 블록:
billing_monthly: "Monthly",
billing_annual: "Annual",
billing_lifetime: "Lifetime",
billing_annual_hint: "Save 25% with annual plan",
billing_lifetime_hint: "Pay once, use forever",
trial_upgrade_banner_title: "Free Trial Active",
trial_upgrade_banner_annual: "💡 Get 3 months free with annual!",
trial_upgrade_banner_desc: "After trial ends, you'll switch to Free. Subscribe now for uninterrupted access.",
paywall_annual_hint: "Save 25% with annual ($5.25/mo)",
paywall_proplus_hint: "Unlock everything with Pro+ ($9.99/mo)",
```

### A5. feed/client.tsx — Trial 배너 가격 표시

**Trial 만료 임박 배너 (L938-954) 수정:**
- 기존: 단순 텍스트 + `/upgrade` 링크
- 변경: **가격 + 연간 할인** 표시 추가

```tsx
{/* Trial 만료 임박 배너 — 가격 추가 */}
<p className="text-sm font-semibold text-amber-400">
  {t(lang, "trial_expiry_banner", { n: daysLeft })}
</p>
<p className="text-[10px] text-green-500/80 mt-0.5">
  {lang === "ko" ? "연간 구독 시 $5.25/월 (25% 할인)" : "Annual: $5.25/mo (25% off)"}
</p>
<Link href="/upgrade" className="text-xs text-primary font-medium hover:underline">
  {t(lang, "trial_expiry_cta")}
</Link>
```

**FOMO 배너 (L957-983) — 가격 추가:**
```tsx
<p className="text-[10px] text-blue-300/80 mt-0.5">
  {lang === "ko" ? "Pro $6.99/월부터 · 연간 시 25% 할인" : "Pro from $6.99/mo · 25% off annual"}
</p>
```

### A6. settings/page.tsx — Trial 섹션 강화

**Trial 정보 카드 (L1232-1252) 수정:**
- 프로그레스 바 추가 (잔여일 시각화)
- 가격/할인 정보 표시
- CTA 버튼 텍스트에 가격 포함

```tsx
{/* 체험판 프로그레스 바 */}
<div className="h-1.5 rounded-full bg-amber-500/20 overflow-hidden">
  <div className="h-full rounded-full bg-gradient-to-r from-amber-400 to-orange-500"
       style={{ width: `${Math.max(5, ((7 - daysLeft) / 7) * 100)}%` }} />
</div>

{/* 가격 힌트 */}
<p className="text-[10px] text-green-500">
  {lang === "ko" ? "연간 구독 시 $5.25/월 (25% 할인)" : "Annual: $5.25/mo (25% off)"}
</p>

{/* CTA 버튼에 가격 포함 */}
<Link href="/upgrade" className="...">
  {lang === "ko" ? "지금 Pro 구독하기 — $6.99/월" : "Subscribe Pro — $6.99/mo"}
</Link>
```

### A7. UpgradeNudgeBanner.tsx — 가격 표시 추가

**변경:** 기존 메시지 아래에 가격 정보 한 줄 추가

```tsx
<p className="text-[10px] text-blue-300/60 mt-0.5">
  {lang === "ko" ? "Pro $6.99/월 · 연간 25% 할인" : "Pro $6.99/mo · 25% off annual"}
</p>
```

### B1. store_products.py — 가격 매핑

```python
PLAN_AMOUNTS = {
    "pro": 699,        # $6.99
    "pro_plus": 999,   # $9.99
    "pro_annual": 6299,      # $62.99
    "pro_plus_annual": 8999,  # $89.99
    "pro_lifetime": 14999,    # $149.99
    "pro_plus_lifetime": 19999, # $199.99
}

# 연간/라이프타임 Google Play product ID
GOOGLE_PRODUCTS = {
    "com.wewantpeace.pro_monthly": "pro",
    "com.wewantpeace.proplus_monthly": "pro_plus",
    "com.wewantpeace.pro_annual": "pro_annual",
    "com.wewantpeace.proplus_annual": "pro_plus_annual",
    "com.wewantpeace.pro_lifetime": "pro_lifetime",
    "com.wewantpeace.proplus_lifetime": "pro_plus_lifetime",
}

# Apple product ID 동일 패턴
APPLE_PRODUCTS = {
    "com.wewantpeace.pro.monthly": "pro",
    "com.wewantpeace.proplus.monthly": "pro_plus",
    "com.wewantpeace.pro.annual": "pro_annual",
    "com.wewantpeace.proplus.annual": "pro_plus_annual",
    "com.wewantpeace.pro.lifetime": "pro_lifetime",
    "com.wewantpeace.proplus.lifetime": "pro_plus_lifetime",
}

def google_product_to_plan(product_id: str) -> str | None:
    return GOOGLE_PRODUCTS.get(product_id)

def apple_product_to_plan(product_id: str) -> str | None:
    return APPLE_PRODUCTS.get(product_id)

# plan → base plan (user.plan은 "pro"/"pro_plus"만 저장)
def plan_to_base(plan: str) -> str:
    if plan.startswith("pro_plus"):
        return "pro_plus"
    if plan.startswith("pro"):
        return "pro"
    return plan
```

### B2. subscription.py — billing_interval 컬럼

```python
# 새 컬럼 추가
billing_interval: Mapped[str] = mapped_column(
    String(20), nullable=False, default="monthly",
    server_default="monthly",
)

# CHECK constraint 수정 (새 migration에서)
# plan은 그대로 'pro', 'pro_plus' 유지
# billing_interval IN ('monthly', 'annual', 'lifetime')
```

`amount` default: `390` → `699`

### B3. admin.py — AppSettings 기본값

```python
pro_price: int = 699      # $6.99
pro_plus_price: int = 999  # $9.99
```

### B4. config.py — 환경변수

```python
dodo_product_pro_annual: str = ""
dodo_product_proplus_annual: str = ""
dodo_product_pro_lifetime: str = ""
dodo_product_proplus_lifetime: str = ""
```

### B5. dodopayments.py — 연간/라이프타임 매핑

`_plan_to_dodo_product()` 확장:
```python
def _plan_to_dodo_product(plan: str, billing_interval: str = "monthly") -> str | None:
    if billing_interval == "annual":
        if plan == "pro": return settings.dodo_product_pro_annual
        if plan == "pro_plus": return settings.dodo_product_proplus_annual
    elif billing_interval == "lifetime":
        if plan == "pro": return settings.dodo_product_pro_lifetime
        if plan == "pro_plus": return settings.dodo_product_proplus_lifetime
    else:  # monthly
        if plan == "pro": return settings.dodo_product_pro
        if plan == "pro_plus": return settings.dodo_product_proplus
    return None
```

Checkout 엔드포인트 body에 `billing_interval` 필드 추가.

### C1. Alembic 마이그레이션

```python
def upgrade():
    op.add_column("subscriptions",
        sa.Column("billing_interval", sa.String(20), nullable=False,
                  server_default="monthly"))
    op.create_check_constraint(
        "ck_subscriptions_billing_interval", "subscriptions",
        "billing_interval IN ('monthly', 'annual', 'lifetime')")
    # amount 기본값 변경
    op.alter_column("subscriptions", "amount", server_default="699")

def downgrade():
    op.drop_constraint("ck_subscriptions_billing_interval", "subscriptions")
    op.drop_column("subscriptions", "billing_interval")
    op.alter_column("subscriptions", "amount", server_default="390")
```

### D1. worker/tasks.py — lifetime 구독 만료 제외

`expire_subscriptions()` 수정:
```python
# 기존 쿼리에 조건 추가
.where(Subscription.billing_interval != "lifetime")
```

### E1-E2. 모바일/iOS product ID

연간/라이프타임 product ID 추가 (실제 스토어 등록 후).

---

## 체험판(Trial) 결제 유도 전략 정리

### 현재 상태

| 위치 | 트리거 | 현재 동작 |
|------|--------|----------|
| Feed 페이지 | 잔여 ≤3일 | 호박색 배너 + `/upgrade` 텍스트 링크 (가격 없음) |
| Feed 페이지 | 만료 후 7일 | FOMO 배너 + 놓친 알림 수 (가격 없음) |
| Settings 페이지 | Trial 진행중 | 잔여일 텍스트 + `/upgrade` 버튼 (가격 없음) |
| Upgrade 페이지 | Trial 진행중 | 호박색 "체험판" 배지 + 구독 버튼 |
| Worker | 만료 D+1, D+3 | 푸시 알림 (할인 오퍼) |

### 변경 후

| 위치 | 트리거 | 변경 후 동작 |
|------|--------|-------------|
| Feed 페이지 | 잔여 ≤3일 | 배너 + **가격 $6.99/월** + **"연간 25% 할인 $5.25/월"** 힌트 |
| Feed 페이지 | 만료 후 7일 | FOMO 배너 + 놓친 알림 수 + **가격 정보** |
| Settings 페이지 | Trial 진행중 | **프로그레스 바** + 잔여일 + **가격 + 할인** 표시 + 가격 포함 CTA |
| Upgrade 페이지 | Trial 진행중 | **전용 배너** (프로그레스바 + 잔여일 + "연간 시 3개월 무료" + 설명) |
| UpgradeNudgeBanner | Free + 놓친 알림 3+ | 기존 메시지 + **가격/할인 한 줄 추가** |
| PaywallModal | 잠금 기능 터치 | CTA 가격 $6.99 + **연간 할인 힌트** + **Pro+ 안내** |

**핵심 원칙:**
- 모든 결제 유도 포인트에 **구체적 가격** 표시 (현재는 대부분 가격 없음)
- **연간 할인**(25%) 을 항상 함께 노출 → 연간 전환 유도
- 체험판 **잔여일 프로그레스 바** → 긴급감 시각화
- Decoy 효과: Monthly/Annual/Lifetime 3옵션 표시 → Annual 선택 유도

---

## 작업 순서

1. **A1** — upgrade/client.tsx 완성 (Pro+ 절약 배지 + Trial 배너 + 푸터)
2. **A2** — PaywallModal.tsx 가격 + 할인 힌트
3. **A4** — i18n.ts 새 키
4. **A3** — legal-data.ts 약관 가격
5. **A5** — feed/client.tsx Trial 배너 가격
6. **A6** — settings/page.tsx Trial 프로그레스 바
7. **A7** — UpgradeNudgeBanner 가격
8. **B1** — store_products.py 가격 매핑
9. **B2** — subscription.py billing_interval
10. **B3** — admin.py 기본값
11. **B4** — config.py 환경변수
12. **B5** — dodopayments.py 매핑
13. **C1** — Alembic 마이그레이션
14. **D1** — worker lifetime 제외
15. **E1-E2** — 모바일 product ID (낮은 우선순위)

**프론트엔드 (A1~A7) → 백엔드 (B1~B5) → DB (C1) → Worker (D1) → 모바일 (E1~E2)**

---

## 사용자가 직접 해야 하는 외부 작업 (코드 배포 전후)

| # | 서비스 | 작업 |
|---|--------|------|
| 1 | DodoPayments | Pro 가격 $3.90→$6.99, Pro+ $6.90→$9.99 |
| 2 | DodoPayments | 연간 Pro ($62.99), 연간 Pro+ ($89.99) 상품 생성 |
| 3 | DodoPayments | Lifetime Pro ($149.99), Lifetime Pro+ ($199.99) 일회성 상품 생성 |
| 4 | Google Play Console | 월간 구독 가격 변경 (기존 구독자 grandfather 옵션) |
| 5 | Google Play Console | 연간 구독 2개 + Lifetime IAP 2개 생성 |
| 6 | Apple App Store Connect | 월간 구독 가격 tier 변경 |
| 7 | Apple App Store Connect | 연간 구독 2개 + Non-Consumable IAP 2개 생성 |
| 8 | Railway 환경변수 | 새 Dodo 상품 ID 4개 추가 |

---

## 검증 방법

1. **로컬 프론트엔드 확인**: `cd ~/Projects/wewantpeace/frontend && npm run dev` → `/upgrade` 페이지에서:
   - 토글 전환 시 가격 동적 변경 확인
   - 취소선/할인 배지 정상 표시
   - 연간 기본 선택 확인
2. **PaywallModal 확인**: 잠금 기능 터치 → 모달에 $6.99 + 할인 힌트 표시
3. **Trial 유도 확인**: Trial 상태에서 Feed/Settings/Upgrade 페이지의 배너/프로그레스 바 확인
4. **백엔드 테스트**: `PLAN_AMOUNTS` 변경 후 기존 subscription_service.py 로직 정상 동작
5. **마이그레이션**: `alembic upgrade head` → billing_interval 컬럼 확인
6. **배포 후**: Railway worker에서 lifetime 구독 만료 스킵 확인

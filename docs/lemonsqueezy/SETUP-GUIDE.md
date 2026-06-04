# LemonSqueezy 제품 설정 가이드

## 1. 할인 코드 생성 (WELCOME30)

### 경로
LemonSqueezy 대시보드 → **Store** → **Discounts** → **+ New discount**

### 설정값
| 항목 | 값 |
|------|---|
| **Name** | Welcome 30% Off |
| **Code** | `WELCOME30` |
| **Discount type** | Percentage |
| **Amount** | `30` % |
| **Duration** | Once (첫 결제만) |
| **Applies to** | All products (Pro + Pro+ 모두 적용) |
| **Limits** | Use limit per customer: `1` |
| **Expiry** | 설정 안 함 (무기한) |

### 저장 후 할 일
Railway 환경변수에 추가:
```
LEMONSQUEEZY_WELCOME_DISCOUNT=WELCOME30
```

---

## 2. Railway 환경변수 추가

### 방법 A: Dashboard (추천)
1. https://railway.app → WeWantPeace 프로젝트
2. **backend** 서비스 클릭
3. **Variables** 탭
4. **+ New Variable** 클릭
5. Key: `LEMONSQUEEZY_WELCOME_DISCOUNT`, Value: `WELCOME30`
6. **Deploy** 버튼으로 재배포

### 방법 B: API 호출
```bash
curl -s -X POST https://backboard.railway.app/graphql/v2 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer 383ab19c-f63d-4ad0-ae47-ef816b79645b" \
  -d '{
    "query": "mutation { variableUpsert(input: { projectId: \"8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed\", environmentId: \"92d7e229-1071-4b32-a12c-8336ef7be7d5\", serviceId: \"81e6a83e\", name: \"LEMONSQUEEZY_WELCOME_DISCOUNT\", value: \"WELCOME30\" }) }"
  }'
```

---

## 3. Pro Plan 제품 설정

### General
| 항목 | 값 |
|------|---|
| **Name** | `Pro Plan — WeWantPeace` |
| **Description (EN)** | `Real-time conflict monitoring for 5 countries. Get fast alerts, KScore filtering, and 30-day issue history. ₩4,900/month.` |
| **Description (KO)** | `195개국 분쟁·안보 실시간 모니터링. 관심국가 5개, 속보알림, KScore 필터, 30일 히스토리. 월 ₩4,900.` |

**사용할 Description** (영어 — LemonSqueezy는 국제 결제 플랫폼):
> Real-time conflict monitoring for 5 countries. Get fast alerts, KScore filtering, and 30-day issue history. ₩4,900/month.

### Pricing
- **Pricing model**: Standard pricing
- **Price**: ₩4,900
- **Repeat every**: 1 Month
- **Free trial**: OFF (우리 앱에서 자체 trial 관리)
- **Tax category**: Software as a service (SaaS) - personal use ✅

### Media
- 바탕화면 `LemonSqueezy/pro-plan.svg` 업로드 (브라우저에서 열어 스크린샷 → PNG 변환)
- 또는 `pro-plan-image.html`을 브라우저에서 열어 스크린샷

### Confirmation Modal
| 항목 | 값 |
|------|---|
| **Title** | `Welcome to Pro! 🎉` |
| **Message** | `Your Pro plan is now active. Open the app to start monitoring.` |
| **Button text** | `Open App` |
| **Button link** | `https://www.wewantpeace.live/home` |

### Email Receipt
| 항목 | 값 |
|------|---|
| **Thank you note** | `Thank you for subscribing to WeWantPeace Pro! Your plan is now active. Open the app to configure your monitored countries and alert preferences.` |
| **Button text** | `Open App` |
| **Button link** | `https://www.wewantpeace.live/home` |

### Settings
- **Display on storefront**: ON
- **Generate license keys**: OFF

---

## 4. Pro+ Plan 제품 설정

> Pro+ 제품이 아직 없으면: **Products → + New product** 로 생성

### General
| 항목 | 값 |
|------|---|
| **Name** | `Pro+ Plan — WeWantPeace` |
| **Description (EN)** | `Unlimited country monitoring with 50 daily alerts, extended KScore filtering (1.5+), and 90-day history. ₩9,900/month.` |
| **Description (KO)** | `관심국가 무제한, 일일 알림 50건, KScore 1.5 이상 필터, 90일 히스토리. 프리미엄 모니터링. 월 ₩9,900.` |

**사용할 Description** (영어):
> Unlimited country monitoring with 50 daily alerts, extended KScore filtering (1.5+), and 90-day history. ₩9,900/month.

### Pricing
- **Price**: ₩9,900
- **Repeat every**: 1 Month
- **Free trial**: OFF
- **Tax category**: Software as a service (SaaS) - personal use

### Media
- `pro-plus-plan.svg` 업로드

### Confirmation Modal
| 항목 | 값 |
|------|---|
| **Title** | `Welcome to Pro+! 🚀` |
| **Message** | `Your Pro+ plan is now active. Unlimited monitoring awaits.` |
| **Button text** | `Open App` |
| **Button link** | `https://www.wewantpeace.live/home` |

### Email Receipt
| 항목 | 값 |
|------|---|
| **Thank you note** | `Thank you for subscribing to WeWantPeace Pro+! You now have unlimited country monitoring and 50 daily alerts. Open the app to configure everything.` |
| **Button text** | `Open App` |
| **Button link** | `https://www.wewantpeace.live/home` |

---

## 5. 추가 추천 설정

### Variants (선택)
Pro+ 에 연간 플랜 variant 추가 고려:
- **Annual Pro**: ₩49,000/year (₩4,083/month, 17% 할인)
- **Annual Pro+**: ₩99,000/year (₩8,250/month, 17% 할인)

→ 연간 플랜은 LTV 증가 + 이탈 방지에 효과적

### Checkout Overlay
LemonSqueezy 설정 → Store → Checkout:
- **Overlay mode**: ON (페이지 이동 없이 모달로 결제)
- **Theme**: Dark (WeWantPeace 앱과 통일)
- **Accent color**: `#2563eb` (Pro) 또는 `#a855f7` (Pro+)

### Webhook 재확인
LemonSqueezy → Settings → Webhooks:
- **URL**: `https://api.wewantpeace.live/payments/ls/webhook`
- **Events**: subscription_created, subscription_payment_success, subscription_cancelled, subscription_expired, subscription_payment_failed
- **Signing secret**: Railway `LEMONSQUEEZY_WEBHOOK_SECRET` 환경변수와 일치 확인

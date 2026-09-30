---
name: money-stored-as-usd-cents
description: wewantpeace에서 결제 금액은 전부 USD 센트 정수로 저장됨 — 화면 표시 직전에만 달러로 변환
metadata:
  type: project
---

wewantpeace는 결제/구독 금액을 전부 "USD 센트" 정수로 저장하고 API도 센트로 반환한다.
예: Subscription.amount/PaymentHistory.amount 기본값 699 = $6.99, admin/stats·bot-stats의 monthly_revenue도 센트 합계.
i18n 라벨도 "요금 설정 (USD 센트)"로 명시돼 있음.

화면에 그대로 뿌리면 100배로 부풀려진다 (admin/page.tsx, subscriptions formatAmount에서 실제로 터졌던 버그).

How to apply: 금액을 표시할 땐 항상 frontend/lib/utils.ts의 formatMoneyFromCents(cents, currency?, locale?)로 변환해서 써라. DB·API는 센트 그대로 두고, 변환은 표시 단계에서만 한다. 새 금액 표시 UI 만들 때 raw 값에 직접 $ 붙이지 마라.

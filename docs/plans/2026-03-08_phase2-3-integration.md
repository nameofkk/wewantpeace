# Phase 2-3 통합 플랜 실행 결과 (2026-03-08)

## 완료된 작업

### Part A: 긴급 수정 (KScore 버그 + UI 텍스트)
- [x] A-1: KScore personalizedKScore 기준 정렬 + homeCountry 의존성 추가
- [x] A-1: DEFAULT_FACTOR 0.3→0.5 (impact-factors.ts + calibration.py)
- [x] A-2: KScore 툴팁 → "Key Impact Score" 설명 (ko/en 4곳)
- [x] A-3: 개인 이메일 → contact@wewantpeace.app (6곳)
- [x] A-4: App Store URL 미출시 조건부 숨김

### Part B: UI/UX 개선
- [x] B-1: Pro/Pro+ 하드코딩 → i18n 키(plan_country_limit_hint, btn_upgrade)
- [x] B-2: PLANS dict 프론트 기준 통일 + bilingual features
- [x] B-3: 에러 메시지 code 기반 통일 (한국어 제거, feature 필드 추가)

### Part C: Phase 2 구현
- [x] C-1: USGS 지진 수집기 (usgs_earthquake.py + tasks.py + celery_app.py)
- [x] C-2: sync_impact_factors.py + generate_neighbor_map.py + generated JSON
- [x] C-3: 공개 API 3개 (tension/all, tension/{cc}, trending/top) + limiter.py 분리
- [x] C-4: LinkedIn + Telegram 채널 브로드캐스트 어댑터 + config.py 업데이트

## 수정/생성된 파일 목록

### 수정된 파일 (11개)
- frontend/app/(main)/home/page.tsx
- frontend/app/(main)/tension/page.tsx
- frontend/app/(main)/upgrade/page.tsx
- frontend/lib/i18n.ts
- frontend/lib/impact-factors.ts
- frontend/lib/legal-data.ts
- frontend/package.json
- backend/app/routers/me.py
- backend/app/routers/subscriptions.py
- backend/app/routers/public.py
- worker/processor/calibration.py
- worker/tasks.py
- worker/celery_app.py
- worker/social/config.py

### 신규 파일 (8개)
- worker/collector/usgs_earthquake.py
- worker/social/adapters/linkedin_adapter.py
- worker/social/adapters/telegram_channel_adapter.py
- scripts/sync_impact_factors.py
- scripts/generate_neighbor_map.py
- frontend/lib/impact-factors.generated.json
- worker/processor/neighbor_map.generated.json
- backend/app/core/limiter.py

## 남은 작업 (Part D - Phase 3)
- [ ] D-1: B-Launch 실행 (METHODOLOGY.md, 백테스트 케이스 스터디)
- [ ] D-2: 알림 고도화 (Spike Alert 문맥 추가)
- [ ] D-3: 수익 최적화 (전환 유도 팝업)
- [ ] D-4: 소스 자동 평가
- [ ] D-5: 수렴 감지 + 이상 감지 (90일 데이터 축적 후)

## 환경변수 설정 필요 (Railway)
```
# LinkedIn 어댑터
SOCIAL_PLATFORM_LINKEDIN_ENABLED=true
LINKEDIN_ACCESS_TOKEN=<토큰>
LINKEDIN_ORG_ID=<조직ID>

# Telegram 채널 어댑터
SOCIAL_PLATFORM_TELEGRAM_CHANNEL_ENABLED=true
TELEGRAM_BROADCAST_BOT_TOKEN=<봇토큰>
TELEGRAM_BROADCAST_CHANNEL_ID=<채널ID>
```

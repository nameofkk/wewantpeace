# WeWantPeace

세계정세 실시간 모니터링 플랫폼 — 알림 · 지도 · 긴장도 지수
웹(PWA) + Android(TWA/Expo) + 토스 앱인토스

## 주요 기능

- **실시간 이슈 지도** — MapLibre GL 기반, 클러스터 마커 + 펄스 애니메이션 + 스파이크 감지
- **긴장도 지수** — 국가별 위기 수준 계산·시계열 추적
- **트렌딩 키워드** — 글로벌/개인화 트렌딩, K-score 기반 급상승 감지
- **커뮤니티** — 토론·분석·질문 게시판 (게시글·댓글·리액션)
- **푸시 알림** — FCM 기반, 관심국가·토픽·심각도 필터링
- **구독 결제** — Google Play Billing + Apple StoreKit + 토스 앱인토스
- **다국어** — 한국어/영어 완전 지원 (1,600+ 번역 키)
- **어드민 대시보드** — 이벤트·클러스터·긴장도·사용자·소스 관리

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| **Frontend** | Next.js 14 · React 18 · Tailwind CSS · MapLibre GL · Zustand · TanStack Query · Firebase Auth |
| **Backend** | FastAPI · SQLAlchemy 2.0 (async) · Celery · Redis |
| **Database** | PostgreSQL 15 + TimescaleDB · Supabase (프로덕션) |
| **Worker** | Celery Beat + Worker (collect/process 큐 분리) |
| **Mobile** | Expo 55 · React Native 0.83 · react-native-iap · FCM + Notifee |
| **수집** | RSS/feedparser · Telegram (Telethon) · OpenAI API (분류/번역) |
| **배포** | Railway.app · GitHub Actions CI/CD · Docker multi-stage |

## 프로젝트 구조

```
wewantpeace/
├── backend/
│   ├── app/
│   │   ├── routers/      # API (issues, trending, tension, community, auth, admin, me, subscriptions)
│   │   ├── models/       # SQLAlchemy 모델 (11개)
│   │   ├── services/     # Google Play / Apple StoreKit 결제 처리
│   │   └── core/         # config, database, auth, redis, firebase
│   ├── alembic/          # DB 마이그레이션 (23개)
│   └── tests/            # pytest 테스트 (173+ 통과)
├── worker/
│   ├── collector/        # RSS·Telegram 수집기
│   ├── processor/        # normalizer, clusterer, deduplicator, spike detector, tension calculator, trending engine
│   └── push/             # FCM 푸시 서비스
├── frontend/
│   ├── app/(main)/       # 사용자 페이지 (홈, 지도, 긴장도, 커뮤니티, 설정)
│   ├── app/admin/        # 어드민 대시보드
│   ├── components/       # UI 컴포넌트
│   └── lib/              # api, auth, i18n, store, fcm, play-billing
├── mobile/               # React Native Expo 앱
│   └── src/services/     # push, iap, bridge (네이티브 브릿지)
├── scripts/              # reprocess_topics, seed_channels, ai_retitle 등
├── infra/                # Dockerfile.backend, .frontend, .worker, docker-compose.yml
└── .github/workflows/    # CI 테스트 + Railway 배포
```

## 빠른 시작

```bash
# 1. 환경변수
cp .env.example .env
# DATABASE_URL, REDIS_URL, TELEGRAM_BOT_TOKEN, SECRET_KEY 등 설정

# 2. Docker로 인프라 실행
cd infra && docker-compose up -d

# 3. DB 마이그레이션 (backend 컨테이너 시작 시 자동 실행됨)
# 수동:
DATABASE_URL=postgresql+asyncpg://wwp:wwplocal@localhost/wewantpeace \
  python -m alembic -c backend/alembic.ini upgrade head

# 4. 프론트엔드
cd frontend && npm install && npm run dev

# 5. Worker (별도 터미널)
celery -A worker.celery_app worker --beat --loglevel=info -Q collect,process -c 2
```

## API

- Swagger UI: http://localhost:8000/docs (DEBUG=true 시)
- Health check: `GET /health`
- OpenAPI spec: `GET /openapi.json`

## 테스트

```bash
bash scripts/run_tests.sh           # 전체 (173+ 통과)
bash scripts/run_tests.sh -u        # 단위 테스트만
bash scripts/run_tests.sh -c        # 커버리지 포함
```

## 배포

- **Railway.app**: backend · worker · frontend (3 서비스)
- **CI/CD**: `main` 브랜치 push → GitHub Actions → Railway GraphQL API 호출
- **DB**: Supabase PostgreSQL (ap-northeast-2)
- **도메인**: `www.wewantpeace.live` (프론트) · `api.wewantpeace.live` (백엔드)

## 모바일 앱

- **버전**: 2.1.0 (Android versionCode 7)
- **패키지**: `com.wewantpeace.app`
- **빌드**: `cd mobile && npx expo prebuild && cd android && ./gradlew assembleRelease`
- **기능**: 푸시 알림, 인앱 결제, WebView 네이티브 브릿지 (mailto/tel 처리)

## 데이터 처리 파이프라인

```
RSS/Telegram 수집 → 정규화(topic/severity/geo) → 중복제거 → 클러스터링
    → 스파이크 감지 → 트렌딩 계산 → 긴장도 지수 → 푸시 알림
```

## 환경변수

| 변수 | 설명 |
|------|------|
| `DATABASE_URL` | PostgreSQL asyncpg URL |
| `REDIS_URL` | Redis 연결 URL |
| `SECRET_KEY` | JWT/세션 시크릿 (프로덕션 필수) |
| `TELEGRAM_BOT_TOKEN` | Telegram 수집용 봇 토큰 |
| `TELEGRAM_API_ID` / `API_HASH` | Telegram MTProto API |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | Firebase Admin SDK (푸시) |
| `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON` | Play Billing 서버 검증 |
| `ALLOWED_ORIGINS` | CORS 허용 도메인 (JSON 배열) |
| `NEXT_PUBLIC_API_URL` | 프론트→백엔드 API URL |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | MapLibre 지도 토큰 |

## 라이선스

Private — All rights reserved.

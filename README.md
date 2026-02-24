# WeWantPeace MVP-1

세계정세 알림·지도·긴장도 지수 플랫폼
웹(PWA) + 안드로이드(TWA)

## 빠른 시작

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일에서 TELEGRAM_BOT_TOKEN 등 설정

# 2. 전체 스택 실행
cd infra && docker-compose up -d

# 3. DB 마이그레이션 (자동: backend 컨테이너 시작 시 실행됨)
# 수동 실행:
DATABASE_URL=postgresql+asyncpg://wwp:wwplocal@localhost/wewantpeace \
  python -m alembic -c backend/alembic.ini upgrade head

# 4. 씨드 데이터
python scripts/seed_sources.py

# 5. 프론트엔드
cd frontend
cp frontend/.env.local.example .env.local  # Mapbox 토큰 설정
npm install
npm run dev
```

## API 확인

- FastAPI 문서: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## 테스트 실행

```bash
bash scripts/run_tests.sh           # 전체 테스트
bash scripts/run_tests.sh -u        # 단위 테스트만
bash scripts/run_tests.sh -c        # 커버리지 포함
```

## 6주 개발 일정

| 주차 | 목표 | 상태 |
|------|------|------|
| Week 1 | 기반 구축 (Docker + DB + 수집 + 지도 뼈대) | ✅ 완료 |
| Week 2 | 처리 엔진 (Normalizer + Dedup + Clusterer) | 🔲 예정 |
| Week 3 | 스파이크 + 트렌딩 + 긴장도 | 🔲 예정 |
| Week 4 | 사용자 시스템 + FCM 푸시 | 🔲 예정 |
| Week 5 | Pro 기능 + PWA + 배포 | 🔲 예정 |
| Week 6 | 안정화 + 출시 | 🔲 예정 |

## 기술 스택

- **Frontend**: Next.js 14 (PWA) + Tailwind CSS + Mapbox GL JS
- **Backend**: FastAPI + Celery + Redis
- **DB**: PostgreSQL 15 + TimescaleDB
- **수집**: Telegram Bot API + RSS/feedparser
- **배포**: Docker Compose → Fly.io

# SNS 자동 포스팅 시스템 — Sprint 1~3 구현 계획

## Context

WeWantPeace의 주요 이슈(Daily Movers, Spike Alert, Weekly Recap)를 X(Twitter)와 Threads에 자동 포스팅하는 시스템을 구축한다. Telegram 승인 봇을 통해 운영자가 콘텐츠를 검수하고, 위험도에 따라 자동/수동 발행을 제어한다.

**PRD**: v1.0 Rev.1 (사용자 확정)
**범위**: Sprint 1(핵심 파이프라인) → Sprint 2(카드 이미지, Instagram) → Sprint 3(운영 보고, KPI 대시보드)

---

## Sprint 1: 핵심 파이프라인 (10일)

### Task 1: DB 스키마 — social_posts + social_post_platform (SNS-1)

**파일:**
- `backend/app/models/social_post.py` (신규)
- `backend/app/models/__init__.py` (import 추가)
- `backend/alembic/versions/0031_social_posts.py` (신규)

**social_posts 테이블:**
```
id              UUID PK default uuid4
content_type    VARCHAR(32) NOT NULL  -- daily_movers | spike_alert | weekly_recap
lang            VARCHAR(4) NOT NULL   -- ko | en
body_text       TEXT NOT NULL          -- 본문 (280자 이내)
hashtags        TEXT[]                 -- 해시태그 배열 (StringArray)
image_url       VARCHAR(1024)         -- 카드 이미지 URL (Sprint 2)
risk_level      VARCHAR(8) NOT NULL DEFAULT 'medium' -- low | medium | high
source_cluster_id UUID FK → issue_clusters.id (nullable)
source_spike_id   UUID FK → spike_events.id (nullable)
dedup_key       VARCHAR(128) NOT NULL UNIQUE  -- daily_movers:ko:2026-03-06 / spike_alert:{spike_id}
status          VARCHAR(16) NOT NULL DEFAULT 'pending_review'
                -- pending_review | approved | published | rejected | failed
created_at      TIMESTAMP(tz) NOT NULL
approved_at     TIMESTAMP(tz)
approved_by     VARCHAR(64)           -- 텔레그램 username
published_at    TIMESTAMP(tz)
```

**social_post_platform 테이블:**
```
id              UUID PK default uuid4
post_id         UUID FK → social_posts.id (CASCADE) NOT NULL
platform        VARCHAR(16) NOT NULL  -- x | threads | instagram
platform_post_id VARCHAR(256)         -- 플랫폼 반환 ID
status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                -- pending | published | failed | skipped
error_message   TEXT
published_at    TIMESTAMP(tz)
```

**인덱스:**
- `ix_social_posts_status_created` (status, created_at)
- `ix_social_posts_content_type` (content_type)
- `UNIQUE(post_id, platform)` on social_post_platform

**마이그레이션 패턴:** 기존 `0030_add_image_url.py` 참고 — inspector 기반 idempotent

---

### Task 2: 콘텐츠 생성기 — Daily Movers (SNS-2)

**파일:**
- `worker/social/generators.py` (신규)

**로직:**
1. DB에서 지난 24시간 `issue_clusters` 중 severity 상위 3개 조회
2. 클러스터의 `title_ko`, `country_code`, `severity`, `kscore` 활용
3. OpenAI `gpt-4o-mini` 호출 (기존 `OPENAI_API_KEY` 재사용, `worker/processor/` 패턴 참고)
   - system prompt: "You are a concise news writer for social media about global conflicts"
   - 280자 이내 한국어 포스트 생성
4. hashtags: `#WeWantPeace` + 국가코드 기반 해시태그 자동 생성
5. risk_level 분류:
   - severity < 40 → low
   - 40 ≤ severity < 70 → medium
   - severity ≥ 70 → high
6. dedup_key: `daily_movers:ko:YYYY-MM-DD`
7. `social_posts` row INSERT (status=pending_review)

**재사용:**
- `worker/processor/normalizer.py`의 COUNTRY_MAP (국가코드→국가명)
- OpenAI 클라이언트 패턴: `worker/processor/` 기존 코드

---

### Task 3: 콘텐츠 생성기 — Spike Alert (SNS-3)

**파일:**
- `worker/social/generators.py` (Task 2와 동일 파일)

**로직:**
1. `spike_events` + `issue_clusters` JOIN
2. `SPIKE_SOCIAL_SEVERITY_MIN` (env, default=60) 이상인 스파이크만 처리
3. OpenAI로 긴급 속보 스타일 포스트 생성
4. dedup_key: `spike_alert:{spike_event.id}`
5. risk 분류: severity 70+ → high, else medium
6. UNIQUE(content_type, source_spike_id)로 중복 방지

---

### Task 4: 콘텐츠 생성기 — Weekly Recap (SNS-4)

**파일:**
- `worker/social/generators.py` (동일 파일)

**로직:**
1. 지난 7일 클러스터 통계 집계 (국가별 이벤트 수, 평균 severity)
2. OpenAI로 주간 요약 포스트 생성
3. dedup_key: `weekly_recap:ko:YYYY-WNN` (ISO week)
4. risk_level: 항상 low

---

### Task 5: Telegram 승인 봇 (SNS-5)

**파일:**
- `worker/social/telegram_bot.py` (신규)
- `backend/requirements.txt` (python-telegram-bot 추가)

**주의:** 기존 `telegram_collector.py`는 Telethon (수집용). 봇은 별도로 `python-telegram-bot` 사용.

**구현:**
1. `python-telegram-bot` v21+ (async) 설치
2. 환경변수: `SOCIAL_TG_BOT_TOKEN`, `SOCIAL_TG_CHAT_ID`
3. 콘텐츠 생성 시 → Telegram 메시지 전송:
   ```
   📢 [Daily Movers] 🇰🇷
   ──────────
   본문 텍스트...
   ──────────
   Risk: medium | Lang: ko
   [✅ 승인] [✏️ 수정] [❌ 거절]
   ```
4. InlineKeyboard 콜백:
   - `approve:{post_id}` → status=approved, approved_at=now, approved_by=username → 즉시 발행 트리거
   - `reject:{post_id}` → status=rejected
   - `edit:{post_id}` → "수정할 텍스트를 입력하세요" 대기 → body_text 업데이트 → 재승인 필요
5. instant-publish: Telegram에서 "즉시 발행" 콜백 → 즉시 X/Threads 발행

**봇 실행 방식:** Celery worker와 별도 프로세스 또는 worker 내 background thread
→ **선택: Celery worker 내 `@worker_ready` 시그널로 polling loop 시작** (별도 서비스 불필요)

---

### Task 6: X(Twitter) 어댑터 (SNS-6)

**파일:**
- `worker/social/adapters/x_adapter.py` (신규)
- `backend/requirements.txt` (tweepy 추가)

**구현:**
1. tweepy v4+ (OAuth 1.0a User Context)
2. 환경변수: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`
3. `publish(post: SocialPost) → platform_post_id`
   - `client.create_tweet(text=body_text + hashtags)`
   - 성공 시 platform_post_id 저장
   - 실패 시 error_message 저장, status=failed
4. Rate limit 대응: tweepy 내장 + retry (max 3)

---

### Task 7: Threads 어댑터 — PoC (SNS-7)

**파일:**
- `worker/social/adapters/threads_adapter.py` (신규)
- `backend/requirements.txt` (requests 이미 있음)

**구현:**
1. Meta Threads API (Graph API v21+)
2. 환경변수: `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN`
3. 2-step publish: create media container → publish
4. PoC 수준: 텍스트 전용, 이미지는 Sprint 2
5. **Fallback**: Sprint 1 Day 10까지 Threads API 접근 불가 시 → X 전용으로 진행, Threads는 Sprint 2로 이동

---

### Task 8: 스케줄러 — Celery Beat 등록 (SNS-8)

**파일:**
- `worker/celery_app.py` (beat_schedule 추가)
- `worker/tasks.py` (태스크 함수 추가)

**스케줄:**
```python
"generate-daily-social": {
    "task": "worker.tasks.generate_daily_social",
    "schedule": crontab(minute=0, hour=0),  # 매일 00:00 UTC = KST 09:00
    "options": {"queue": "process"},
},
"generate-spike-social": {
    "task": "worker.tasks.generate_spike_social",
    "schedule": crontab(minute="*/5"),  # 스파이크 감지 주기와 동일
    "options": {"queue": "process"},
},
"generate-weekly-social": {
    "task": "worker.tasks.generate_weekly_social",
    "schedule": crontab(minute=0, hour=0, day_of_week=1),  # 매주 월요일
    "options": {"queue": "process"},
},
"publish-approved-social": {
    "task": "worker.tasks.publish_approved_social",
    "schedule": crontab(minute="*/2"),  # 2분마다 approved 상태 게시물 발행
    "options": {"queue": "process"},
},
```

**태스크 함수:**
- `generate_daily_social()`: generators.generate_daily_movers() 호출
- `generate_spike_social()`: 미처리 spike_events 스캔 → generators.generate_spike_alert()
- `generate_weekly_social()`: generators.generate_weekly_recap()
- `publish_approved_social()`: status=approved인 포스트 → X/Threads 어댑터 발행

---

### Task 9: Kill Switch 환경변수 (SNS-9)

**파일:**
- `worker/social/config.py` (신규)

**환경변수:**
```python
SOCIAL_AUTOGEN_ENABLED = os.getenv("SOCIAL_AUTOGEN_ENABLED", "true") == "true"
SOCIAL_AUTOPUBLISH_LOW_ENABLED = os.getenv("SOCIAL_AUTOPUBLISH_LOW_ENABLED", "false") == "true"
SOCIAL_PLATFORM_X_ENABLED = os.getenv("SOCIAL_PLATFORM_X_ENABLED", "true") == "true"
SOCIAL_PLATFORM_THREADS_ENABLED = os.getenv("SOCIAL_PLATFORM_THREADS_ENABLED", "false") == "true"
SPIKE_SOCIAL_SEVERITY_MIN = int(os.getenv("SPIKE_SOCIAL_SEVERITY_MIN", "60"))
```

- 14일 의무 승인 기간: `SOCIAL_AUTOPUBLISH_LOW_ENABLED`는 처음 14일간 false 유지 후 수동으로 true 전환
- 모든 태스크 함수 시작 시 `SOCIAL_AUTOGEN_ENABLED` 체크

---

### Task 10: 어드민 SNS 관리 페이지 (Sprint 1 Admin)

**파일:**
- `frontend/app/admin/social/page.tsx` (신규)
- `frontend/app/admin/layout.tsx` (NAV_GROUPS에 추가)
- `frontend/lib/i18n.ts` (admin_social 키 추가)
- `backend/app/routers/admin.py` (API 엔드포인트 추가)

#### 10-1: 네비게이션 추가

`admin_group_ops` 그룹에 추가:
```typescript
{ href: "/admin/social", icon: Share2, labelKey: "admin_social" },
```
i18n: `admin_social`: ko="SNS 관리", en="Social Posts"

#### 10-2: 백엔드 API

`/admin/social` GET — 목록 조회 (페이지네이션, status/content_type/platform 필터)
```
Query params: page, status, content_type, platform, q (검색)
Response: { items: SocialPostWithPlatforms[], total: number }
```

`/admin/social/{id}` GET — 상세 조회
`/admin/social/{id}/approve` POST — 수동 승인 → approved 상태로 변경
`/admin/social/{id}/reject` POST — 거절
`/admin/social/{id}/retry` POST — failed 상태 → approved로 재시도
`/admin/social/{id}` PATCH — body_text/hashtags 수정
`/admin/social/stats` GET — 통계 (오늘/이번주 게시 수, 승인 대기, 실패)

#### 10-3: 프론트엔드 페이지

기존 `admin/partners/page.tsx` 패턴 그대로 적용:
- `useAuth()` + `useAppStore()` + inline `fetchWithToken`
- `useQuery` / `useMutation` (React Query)
- 상단: 통계 카드 (대기중 / 승인 / 발행 / 실패)
- 필터: status 탭 (all/pending_review/approved/published/rejected/failed) + content_type 드롭다운 + 검색
- 데스크톱: 테이블 (content_type, lang, body_text 일부, status 뱃지, risk 뱃지, 플랫폼 아이콘, created_at, 액션버튼)
- 모바일: 카드 레이아웃
- 상태별 색상:
  - pending_review: `bg-yellow-500/20 text-yellow-400`
  - approved: `bg-blue-500/20 text-blue-400`
  - published: `bg-green-500/20 text-green-400`
  - rejected: `bg-red-500/20 text-red-400`
  - failed: `bg-orange-500/20 text-orange-400`
- risk 뱃지: low=green, medium=yellow, high=red
- 액션: 승인/거절/재시도 버튼 (inline mutation)
- 클릭 시 본문 전체 + platform별 상태 + 에러메시지 표시 (모달 또는 확장행)
- 페이지네이션: 기존 partners 패턴 동일
- InlineGuide: "SNS 자동 포스팅 관리" 설명

---

## Sprint 2: 카드 이미지 + Instagram (7일)

### Task 11: 카드 이미지 생성 (SNS-S2-1)

**파일:**
- `worker/social/card_generator.py` (신규)
- `backend/requirements.txt` (Pillow 추가)

**구현:**
- Pillow로 720x720 카드 이미지 생성
- 다크 배경 + WeWantPeace 로고 + 제목 + severity 바 + 출처
- S3/Supabase Storage에 업로드 → image_url 저장
- 또는 OpenAI DALL-E 3로 관련 이미지 생성 (Option B)

### Task 12: Instagram 어댑터 (SNS-S2-2)

**파일:**
- `worker/social/adapters/instagram_adapter.py` (신규)

**구현:**
- Meta Graph API (Instagram Publish)
- image_url 필수 (카드 이미지)
- Sprint 2에서 추가, 환경변수: `SOCIAL_PLATFORM_INSTAGRAM_ENABLED`

### Task 13: 어드민 페이지 이미지 미리보기 (SNS-S2-3)

- social/page.tsx에 이미지 썸네일 표시 추가
- 클릭 시 원본 이미지 모달

---

## Sprint 3: 운영 보고 + KPI 대시보드 (5일)

### Task 14: 운영 보고 자동화 (SNS-S3-1)

**파일:**
- `worker/social/reporting.py` (신규)

**구현:**
- 매일/매주 Telegram 채널에 운영 리포트 전송
- 콘텐츠: 발행 수, 실패 수, 승인 대기, 플랫폼별 현황

### Task 15: 어드민 KPI 대시보드 확장 (SNS-S3-2)

**파일:**
- `frontend/app/admin/social/page.tsx` (기존 페이지 확장)

**구현:**
- 상단 통계 카드를 차트로 확장
- 일별 발행 추이 (7일), 플랫폼별 성공/실패율
- 기존 KPI 페이지(`admin/kpi/page.tsx`) 차트 패턴 참고

---

## 수정 파일 전체 목록

| # | 파일 | 작업 | Sprint |
|---|------|------|--------|
| 1 | `backend/app/models/social_post.py` | 신규 — SocialPost, SocialPostPlatform 모델 | 1 |
| 2 | `backend/app/models/__init__.py` | import 추가 | 1 |
| 3 | `backend/alembic/versions/0031_social_posts.py` | 신규 — 마이그레이션 | 1 |
| 4 | `worker/social/__init__.py` | 신규 — 패키지 | 1 |
| 5 | `worker/social/config.py` | 신규 — 환경변수/킬스위치 | 1 |
| 6 | `worker/social/generators.py` | 신규 — 콘텐츠 생성기 3종 | 1 |
| 7 | `worker/social/telegram_bot.py` | 신규 — Telegram 승인 봇 | 1 |
| 8 | `worker/social/adapters/__init__.py` | 신규 — 패키지 | 1 |
| 9 | `worker/social/adapters/x_adapter.py` | 신규 — X 어댑터 | 1 |
| 10 | `worker/social/adapters/threads_adapter.py` | 신규 — Threads 어댑터 | 1 |
| 11 | `worker/celery_app.py` | beat_schedule 4개 추가 | 1 |
| 12 | `worker/tasks.py` | 태스크 함수 4개 추가 | 1 |
| 13 | `backend/app/routers/admin.py` | /admin/social/* API 엔드포인트 | 1 |
| 14 | `frontend/app/admin/social/page.tsx` | 신규 — SNS 관리 페이지 | 1 |
| 15 | `frontend/app/admin/layout.tsx` | NAV_GROUPS에 social 추가 | 1 |
| 16 | `frontend/lib/i18n.ts` | admin_social 키 추가 (ko+en) | 1 |
| 17 | `backend/requirements.txt` | python-telegram-bot, tweepy 추가 | 1 |
| 18 | `worker/social/card_generator.py` | 신규 — 카드 이미지 | 2 |
| 19 | `worker/social/adapters/instagram_adapter.py` | 신규 — Instagram | 2 |
| 20 | `worker/social/reporting.py` | 신규 — 운영 보고 | 3 |

---

## 실행 순서 (의존성 기반)

```
Task 1 (DB 스키마)
  ├→ Task 2 (Daily Movers 생성기)
  ├→ Task 3 (Spike Alert 생성기)
  ├→ Task 4 (Weekly Recap 생성기)
  └→ Task 9 (Kill Switch config)
       └→ Task 8 (Celery 스케줄러) — generators + config 필요
            └→ Task 5 (Telegram 봇) — 포스트 생성 후 알림 필요
                 ├→ Task 6 (X 어댑터) — 승인 후 발행
                 └→ Task 7 (Threads 어댑터)
                      └→ Task 10 (어드민 페이지) — 전체 파이프라인 후 관리 UI
```

**배치 실행 계획:**
- Batch 1: Task 1 + Task 9 (DB + config)
- Batch 2: Task 2 + Task 3 + Task 4 (3개 생성기 병렬)
- Batch 3: Task 5 + Task 6 + Task 7 (Telegram 봇 + 어댑터)
- Batch 4: Task 8 (스케줄러)
- Batch 5: Task 10 (어드민 페이지 — 백엔드 API + 프론트엔드)

---

## 검증

1. `npx next build` — 프론트엔드 빌드 성공
2. `python -c "from backend.app.models.social_post import SocialPost, SocialPostPlatform"` — 모델 import 확인
3. Alembic migration dry-run: `alembic upgrade head` (로컬 DB)
4. 어드민 `/admin/social` 페이지 접속 — 목록/필터/승인/거절 동작 확인
5. `git commit && git push`

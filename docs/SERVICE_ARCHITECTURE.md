# WeWantPeace - Service Architecture Document

> **Last Updated**: 2026-03-07
> **Version**: 1.0
> **Purpose**: 개발자/기획자가 서비스 전체 구조와 동작 방식을 파악하기 위한 문서

---

## 1. Service Overview

**WeWantPeace**는 전 세계 분쟁/위기 뉴스를 실시간으로 수집 -> 분류 -> 클러스터링 -> 트렌딩/긴장도 산출 -> 사용자에게 전달하는 **모니터링 플랫폼**입니다.

### 핵심 가치
- 실시간 세계정세 모니터링
- 국가별 긴장도 지수 (Tension Index)
- KScore 기반 이슈 트렌딩
- 스파이크(급증) 감지 & 푸시 알림
- AI 기반 SNS 자동 포스팅

### Tech Stack
| 레이어 | 기술 |
|--------|------|
| **Frontend** | Next.js 14 (React 18), TypeScript, Tailwind CSS, Zustand, React Query |
| **Backend** | FastAPI (Python 3.11), SQLAlchemy 2.0 (async), Pydantic |
| **Worker** | Celery 5.3 + Redis (Beat 스케줄러) |
| **Database** | PostgreSQL 15 (Supabase), TimescaleDB |
| **Cache** | Redis 7 |
| **Auth** | Firebase Authentication |
| **Push** | Firebase Cloud Messaging (FCM) |
| **AI/NLP** | OpenAI GPT-4o-mini |
| **Infra** | Railway (Docker), GitHub Actions CI/CD |
| **SNS** | X(Twitter), Threads, Instagram API |
| **Telegram** | Telethon (수집) + python-telegram-bot (봇) |

---

## 2. Architecture Overview

```
                    ┌──────────────────────────────────┐
                    │          사용자 (Web/PWA/TWA)      │
                    └──────────────┬───────────────────┘
                                   │
                    ┌──────────────▼───────────────────┐
                    │       Frontend (Next.js)          │
                    │  - 페이지 렌더링 (SSR/CSR)         │
                    │  - React Query 캐싱               │
                    │  - Firebase Auth                  │
                    │  - FCM 푸시 수신                   │
                    └──────────────┬───────────────────┘
                                   │ REST API
                    ┌──────────────▼───────────────────┐
                    │       Backend (FastAPI)           │
                    │  - 12개 라우터, 70+ 엔드포인트      │
                    │  - 인증/인가 (Firebase JWT)        │
                    │  - 플랜별 기능 게이팅               │
                    │  - SlowAPI 레이트 리미팅           │
                    └────┬──────────────┬──────────────┘
                         │              │
              ┌──────────▼──┐    ┌──────▼──────────┐
              │ PostgreSQL  │    │     Redis        │
              │ (Supabase)  │    │  - 캐시           │
              │ - 23개 테이블│    │  - Celery 브로커   │
              └─────────────┘    │  - 세션/쿨다운     │
                                 └──────┬──────────┘
                                        │
                    ┌───────────────────▼──────────────┐
                    │        Worker (Celery)            │
                    │  ┌─── collect 큐 ───┐             │
                    │  │ RSS 수집 (5분)    │             │
                    │  │ Telegram 수집 (3분)│            │
                    │  └──────────────────┘             │
                    │  ┌─── process 큐 ───┐             │
                    │  │ 정규화 → 클러스터링 │            │
                    │  │ 긴장도 계산 (5분)  │             │
                    │  │ 트렌딩 계산 (5분)  │             │
                    │  │ 스파이크 감지      │             │
                    │  │ FCM 푸시 발송      │             │
                    │  │ SNS 자동 포스팅    │             │
                    │  └──────────────────┘             │
                    └──────────────────────────────────┘
```

---

## 3. Data Pipeline (데이터 흐름)

### 3.1 수집 -> 정규화 -> 클러스터링 -> 알림

```
[RSS/Telegram 피드]
       │
       ▼
   RawEvent 저장
       │
       ▼ process_raw_event (Celery 체이닝)
   ┌───────────────────────────────┐
   │ 1. AI 분류 (GPT-4o-mini)      │
   │    - Topic: conflict/terror/  │
   │      coup/sanctions/cyber/    │
   │      protest/diplomacy/       │
   │      maritime/disaster/health │
   │ 2. Severity 계산 (0-100)      │
   │ 3. 국가/좌표 추출              │
   │ 4. 중복 검사 (dedup_key)       │
   │ 5. 한국어 번역                 │
   └───────────┬───────────────────┘
               ▼
       NormalizedEvent 저장
               │
               ▼ assign_cluster
   ┌───────────────────────────────┐
   │ 제목 유사도 40%+ 매칭          │
   │ + 국가/토픽 일치 확인           │
   │ → 기존 클러스터 합류 or 신규 생성│
   └───────────┬───────────────────┘
               ▼
       IssueCluster 업데이트
               │
               ▼ spike_detector
   ┌───────────────────────────────┐
   │ 누적 기반 스파이크 감지         │
   │ → is_spike=True + FCM 발송    │
   └───────────────────────────────┘
```

### 3.2 KScore 계산 (트렌딩)

```
KScore (v4, 0-10 스케일):

  raw = 0.25 × velocity_norm    ← 이벤트 증가 속도
      + 0.15 × quality          ← 신뢰도 + 출처 등급
      + 0.40 × severity_norm    ← 심각도 (가장 큰 비중)
      + 0.20 × spread           ← 독립 출처 수

  KScore = raw × 10 × decay

  decay = max(0.15, exp(-0.04 × age_hours))

UI 임계값:
  안정 < 2 / 주의 2-4 / 경계 4-6 / 심각 6-8 / 극심 8+

시간 감쇠:
  6h → 79% / 12h → 62% / 24h → 38% / 48h+ → 15% (바닥)
```

### 3.3 긴장도 지수 (Tension Index)

```
Raw = 0.55 × EventScore + 0.35 × ActivityScore + 0.10 × Spillover

  EventScore    = 로그 스케일 severity×confidence 합계 (0-100)
  ActivityScore = 볼륨 60% + 가속도 40% (0-100)
  Spillover     = 인접국 최대 severity / 100

  tension_level:
    0 = 안정 (0-20)
    1 = 주의 (20-40)
    2 = 경계 (40-60)
    3 = 심각 (60-80)
    4 = 극심 (80-100)
```

---

## 4. Backend API

### 4.1 라우터 구조

| 라우터 | Prefix | 주요 기능 |
|--------|--------|-----------|
| **auth** | `/auth` | 회원가입, 로그인(Google/Apple/Kakao/Email/Toss), 프로필, 탈퇴 |
| **issues** | `/issues` | 이슈 클러스터 목록/상세 (지도용, bbox 필터) |
| **trending** | `/trending` | 글로벌/관심지역 트렌딩, KScore 히스토리, peek |
| **tension** | `/tension` | 국가별 긴장도, 히스토리, peek, 재계산 |
| **me** | `/me` | 내 정보, 관심지역 CRUD, 알림설정, FCM토큰, 알림 |
| **community** | `/community` | 게시글/댓글 CRUD, 반응(좋아요), 신고, 이미지 업로드 |
| **subscriptions** | `/subscriptions` | 플랜 조회, 구독 관리, Trial 시작 |
| **store** | `/subscriptions/store` | Google Play/Apple 영수증 검증, 웹훅 |
| **terms** | `/terms` | 약관 조회/동의 |
| **links** | `/r` | 단축 링크 리다이렉트 |
| **public** | `/public` | 주간 요약 (인증 불필요) |
| **admin** | `/admin` | 어드민 전용 40+ 엔드포인트 |

### 4.2 인증 체계

| 방식 | 헤더 | 용도 |
|------|------|------|
| Firebase JWT | `Authorization: Bearer <token>` | 프로덕션 인증 |
| Toss 앱인토스 | authorizationCode → Custom Token | 토스 앱 내 로그인 |
| Dev UID | `X-Dev-UID: <uid>` | 개발 환경 (DISABLE_AUTH=true) |

### 4.3 플랜 체계

| 기능 | Free | Pro (4,900원) | Pro+ (9,900원) |
|------|------|------|------|
| 관심국가 | 2개 | 5개 | 무제한 |
| KScore 히스토리 | 7일 | 30일 | 90일 |
| 긴장도 히스토리 | 7일 | 30일 | 90일 |
| 토픽 필터 알림 | X | O | O |
| 방해금지 시간 | X | O | O |
| min_kscore 조정 | 3.0 고정 | 3.0~10.0 | 1.5~10.0 |
| Fast 알림 | X | O | O |

### 4.4 캐싱 전략

| 엔드포인트 | 캐시 방식 | TTL |
|-----------|----------|-----|
| `/trending/global` | Redis + HTTP | 5분 |
| `/trending/mine` | HTTP (private) | 2분 |
| `/issues` | HTTP (public) | 2분 |
| `/tension/mine` | HTTP (private) | 2분 |
| `/public/weekly-summary` | HTTP | 30분 |
| `/r/{code}` | Redis | 5분 |

### 4.5 레이트 리미팅

- 기본: **200 req/min** (IP 기반, SlowAPI)
- Health: **60 req/min**

---

## 5. Frontend

### 5.1 페이지 구조

#### 인증 레이아웃 `(auth)`
| 경로 | 기능 |
|------|------|
| `/login` | 로그인/회원가입 (Google/Apple/Kakao/Email/Toss) |
| `/onboarding` | 초기 온보딩 |

#### 메인 레이아웃 `(main)`
| 경로 | 기능 |
|------|------|
| `/home` | 글로벌/관심지역 트렌딩 이슈 카드 목록 |
| `/map` | MapLibre GL 대화형 지도 (클러스터 마커) |
| `/tension` | 국가별 긴장도 지수 + 게이지 차트 |
| `/community` | 게시글 목록 (토론/분석/질문/공지) |
| `/community/new` | 게시글 작성 |
| `/community/[postId]` | 게시글 상세 + 댓글 |
| `/notifications` | 푸시 알림 목록 |
| `/settings` | 관심지역, 알림, 언어, 테마, 계정 |
| `/settings/referral` | 레퍼럴 프로그램 |
| `/settings/glossary` | 용어 사전 |
| `/issues/[id]` | 이슈 클러스터 상세 + 타임라인 |
| `/issues/country/[code]` | 국가별 이슈 목록 |
| `/tension` | 긴장도 대시보드 + 히스토리 차트 |
| `/reports/weekly` | 주간 리포트 |
| `/upgrade` | 구독 업그레이드 (Pro/Pro+) |

#### 어드민 `/admin`
24개 관리 페이지 (대시보드, 사용자, 구독, 클러스터, 이벤트, 소스, KPI, 소셜, 파트너, 링크, 마케팅, 파이프라인 등)

### 5.2 상태 관리 (Zustand)

```typescript
AppStore {
  // 지도
  mapViewport: { longitude, latitude, zoom }
  selectedClusterId: string | null
  activeFilters: { topics[], severityMin, showSpikesOnly }

  // 사용자
  userPlan: "free" | "pro" | "pro_plus"
  trendingTab: "global" | "mine"
  myCountries: string[]   // localStorage 영속

  // UI
  lang: "ko" | "en"
  theme: "dark" | "light"
}
```

### 5.3 주요 React Query 훅

| 훅 | 용도 |
|----|------|
| `useGlobalTrending()` | 글로벌 트렌딩 TOP20 |
| `useMineTrending(countries?)` | 관심지역 트렌딩 |
| `useKScoreHistory(clusterId, days)` | KScore 시계열 |
| `useClusters(params)` | 지도용 클러스터 |
| `useClusterDetail(id)` | 이슈 상세 |
| `useTensionMine(countries?)` | 긴장도 |
| `useTensionHistory(code, range)` | 긴장도 히스토리 |
| `useMe()` | 현재 유저 |
| `useMyAreas()` | 관심지역 DB 목록 |
| `useNotifications()` | 알림 목록 |
| `useUnreadCount()` | 미읽음 수 |

### 5.4 다국어 (i18n)

- 한국어(ko) / 영어(en) 지원
- `t(lang, "key")` 함수형 호출
- 모든 UI 텍스트는 `lib/i18n.ts`에서 관리

### 5.5 PWA / 플랫폼

- Service Worker (next-pwa): 오프라인 캐싱
- 지도 타일: CacheFirst (24시간)
- API: NetworkFirst (5분)
- Android TWA 앱 배포
- React Native WebView 지원
- 토스 앱인토스 지원

---

## 6. Worker (Celery)

### 6.1 Beat 스케줄

#### 데이터 수집
| 태스크 | 주기 | 큐 |
|--------|------|-----|
| `collect-rss` | 5분 | collect |
| `collect-telegram` | 3분 | collect |

#### 데이터 처리
| 태스크 | 주기 | 큐 |
|--------|------|-----|
| `calc-tension` | 5분 (+1분 오프셋) | process |
| `calc-trending` | 5분 (+2분 오프셋) | process |
| `reprocess-orphans` | 1시간 | process |
| `monitor-service-health` | 5분 (+3분 오프셋) | process |

#### 구독/토큰
| 태스크 | 주기 |
|--------|------|
| `expire-subscriptions` | 매일 02:00 UTC |
| `sync-store-subscriptions` | 4시간 |
| `cleanup-stale-tokens` | 매일 03:00 UTC |

#### 알림 무결성
| 태스크 | 주기 |
|--------|------|
| `timeout-pending-deliveries` | 10분 |
| `build-missed-spike-summary` | 30분 |
| `reconcile-delivery-logs` | 매일 04:00 UTC |

#### SNS 자동 포스팅
| 태스크 | 주기 |
|--------|------|
| `generate-daily-social` | 매일 00:00 UTC (KST 09:00) |
| `generate-spike-social` | 10분 |
| `generate-weekly-social` | 매주 월요일 00:00 UTC |
| `publish-approved-social` | 2분 |
| `send-daily-social-report` | 매일 23:00 UTC |
| `send-weekly-social-report` | 매주 일요일 23:00 UTC |

#### Trial/마케팅
| 태스크 | 주기 |
|--------|------|
| `send-trial-nudges` | 매일 09:00 UTC (KST 18:00) |
| `send-weekly-report` | 매주 월요일 09:00 UTC |
| `snapshot-weekly-kpi` | 매주 일요일 15:05 UTC |
| `aggregate-link-clicks` | 1시간 |

### 6.2 온디맨드 태스크 (체이닝)

```
process_raw_event(raw_event_id)
    → normalize → dedup → assign_cluster → spike_detect
        → push_spike_alert (FCM)
        → push_verified_alert (FCM)
```

### 6.3 FCM 푸시 알림

#### 레인 분리
| 레인 | 대상 | 조건 |
|------|------|------|
| **verified** | notify_verified=True | is_verified=True |
| **fast** | notify_fast=True (Pro) | 미확인 이슈도 포함 |

#### 필터링
1. 국가 기반 (UserArea)
2. 토픽 필터 (UserPreference.topics)
3. 방해금지 시간 (quiet_hours + timezone)
4. Min KScore (UserPreference.min_kscore)

#### 쿨다운 (Redis)
- severity >= 90: 30분
- 그 외: 1시간

---

## 7. Telegram

### 7.1 수집 (Telethon)
- MTProto 기반 공개 채널 메시지 수집
- 3분마다 실행
- 연속 실패 20회 → 채널 자동 비활성화

### 7.2 SNS 검수 봇
- 소셜 포스트 생성 시 Telegram 채널로 검수 요청
- 인라인 버튼: 승인/수정/거절
- 서비스 헬스 모니터링 알림

---

## 8. Database Schema

### 총 23개 테이블

#### 사용자
| 테이블 | 역할 |
|--------|------|
| `users` | 사용자 (firebase_uid, plan, role, status, nickname, referral) |
| `user_areas` | 관심지역 (country_code, area_type, notify 설정) |
| `user_push_tokens` | FCM 토큰 (platform, status, last_seen_at) |
| `user_preferences` | 알림 설정 (language, min_severity, topics, quiet_hours, timezone) |

#### 뉴스/이벤트
| 테이블 | 역할 |
|--------|------|
| `source_channels` | 뉴스 소스 (RSS/Telegram, tier A-D, feed_url) |
| `raw_events` | 수집 원본 (source_type, external_id, raw_text) |
| `normalized_events` | 정규화 완료 (topic, severity, country, lat/lon, dedup_key) |
| `issue_clusters` | 클러스터 (title, kscore, severity, event_count, is_spike) |
| `cluster_events` | 클러스터-이벤트 다대다 관계 |

#### 분석
| 테이블 | 역할 |
|--------|------|
| `tension_index` | 시계열 긴장도 (country_code, raw_score, tension_level) |
| `trending_keywords` | 트렌딩 키워드 (kscore, scope, cluster_ids) |
| `spike_events` | 스파이크 기록 (severity, kscore, triggered_at) |

#### 알림/배송
| 테이블 | 역할 |
|--------|------|
| `notifications` | 인앱 알림 (type, cluster_id, is_read) |
| `alert_delivery_log` | FCM 배송 추적 (decision, suppression_reason) |
| `user_missed_spike_summary` | 놓친 스파이크 (Pro 유도용) |

#### 커뮤니티
| 테이블 | 역할 |
|--------|------|
| `posts` | 게시글 (title, content, post_type, view/like/dislike count) |
| `comments` | 댓글 (parent_id로 대댓글) |
| `post_reactions` / `comment_reactions` | 좋아요/싫어요 |
| `reports` | 신고 (target_type, status) |

#### 결제
| 테이블 | 역할 |
|--------|------|
| `subscriptions` | 구독 (plan, status, platform, store_transaction_id) |
| `payment_history` | 결제 내역 |

#### 기타
| 테이블 | 역할 |
|--------|------|
| `term_versions` / `user_consents` | 약관/동의 |
| `social_posts` / `social_post_platform` | SNS 자동 포스팅 |
| `weekly_kpi_snapshots` | 주간 KPI 스냅샷 |
| `partners` | 파트너 CRM |
| `short_links` / `link_clicks` | 단축 링크 + 클릭 추적 |
| `admin_logs` | 어드민 활동 로그 |
| `feedbacks` | 사용자 피드백 |
| `app_events` | 이벤트 트래킹 |
| `paywall_events` | 페이월 이벤트 |
| `marketing_email_logs` | 마케팅 이메일 로그 |

---

## 9. Admin Panel

### 9.1 주요 기능 (24개 페이지)

| 카테고리 | 페이지 | 기능 |
|----------|--------|------|
| **Overview** | /admin | KPI 대시보드, 실시간 통계 |
| **Users** | /admin/users | 사용자 검색, 플랜/역할/정지 수정 |
| | /admin/subscriptions | 활성 구독 관리, 수동 부여 |
| | /admin/marketing | 마케팅 이메일 발송, CSV 내보내기 |
| **Content** | /admin/posts | 게시글 관리 (숨김/복원) |
| | /admin/comments | 댓글 관리 |
| | /admin/reports | 신고 처리 (resolved/dismissed) |
| | /admin/feedbacks | 사용자 피드백 조회 |
| **Data** | /admin/pipeline | 수집→처리→배포 파이프라인 모니터링 |
| | /admin/clusters | 클러스터 심각도/주제/제목 수정 |
| | /admin/events | 이벤트 목록, 일일 카운트 |
| | /admin/sources | 뉴스 소스 활성화/신뢰도 조정 |
| **Analytics** | /admin/kpi | 주간 KPI, 스냅샷 히스토리 |
| | /admin/kscore | KScore 트렌딩 분석 |
| | /admin/tension | 긴장도 분석, 재계산 |
| **Operations** | /admin/social | SNS 콘텐츠 승인/거절/재발행 |
| | /admin/partners | 파트너 CRM |
| | /admin/links | 단축 링크 + 클릭 추적 |
| | /admin/weekly-report | 주간 리포트 |
| | /admin/reports-perf | 성과 리포트 |
| **System** | /admin/settings | 유지보수 모드, 가입 허용, 배너 |
| | /admin/logs | 어드민 활동 로그 |
| | /admin/guide | 운영 가이드 |

### 9.2 데이터 품질 지표

```
unclassified_rate    : unknown 토픽 비율
translation_fail_rate: 한국어 번역 실패 비율
geo_fail_rate        : 지오코딩 실패 비율
error_sources        : 에러 발생 소스 수
noise_clusters       : 심각도 0 (노이즈) 클러스터
```

---

## 10. Infrastructure

### 10.1 Railway 배포

| 서비스 | Service ID | 역할 |
|--------|-----------|------|
| **backend** | `81e6a83e` | FastAPI API 서버 |
| **worker** | `2ee51089` | Celery Worker + Beat |
| **frontend** | `aefe12db` | Next.js SSR |

### 10.2 CI/CD

- **트리거**: Push to `main` branch
- **방식**: GitHub Actions → Railway GraphQL API `serviceInstanceRedeploy`
- 3개 서비스 순차 배포

### 10.3 Docker 구성

| 파일 | 용도 |
|------|------|
| `Dockerfile.frontend` | Next.js standalone 빌드 |
| `infra/Dockerfile.worker` | Celery worker |
| `infra/docker-compose.yml` | 로컬 개발 (PostgreSQL + Redis + 3 worker) |

### 10.4 모니터링

- **Sentry**: 에러 추적 (backend)
- **서비스 헬스체크**: 5분마다 Telegram 알림
- **KPI 스냅샷**: 매주 자동 생성 + 하락 시 이메일 경고

---

## 11. Key Business Metrics

### 추적 중인 KPI
- DAU/WAU/MAU
- 신규 가입 수
- Pro/Pro+ 전환율
- Trial → Paid 전환율
- 레퍼럴 전환율
- 데이터 품질 (분류율, 번역율, 지오코딩율)
- 푸시 발송율/실패율
- 페이월 노출/전환
- SNS 콘텐츠 승인율/발행율

---

## 12. File Structure

```
~/Projects/wewantpeace/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI 엔트리포인트
│   │   ├── core/
│   │   │   ├── config.py        # 환경변수 설정
│   │   │   └── auth.py          # 인증 의존성
│   │   ├── models/              # SQLAlchemy 모델 (21개)
│   │   ├── routers/             # API 라우터 (12개)
│   │   └── deps/                # 의존성 주입
│   ├── alembic/versions/        # DB 마이그레이션 (31개)
│   └── requirements.txt
│
├── frontend/
│   ├── app/                     # Next.js 페이지
│   │   ├── (auth)/              # 인증 페이지
│   │   ├── (main)/              # 메인 앱 페이지
│   │   └── admin/               # 어드민 패널 (24개 페이지)
│   ├── components/              # React 컴포넌트
│   │   ├── ui/                  # 기본 UI
│   │   ├── map/                 # 지도
│   │   ├── issue/               # 이슈 카드
│   │   ├── trending/            # 트렌딩 차트
│   │   └── tension/             # 긴장도 차트
│   ├── lib/                     # 유틸리티
│   │   ├── store.ts             # Zustand 스토어
│   │   ├── api.ts               # React Query 훅
│   │   ├── auth.ts              # Firebase Auth
│   │   ├── i18n.ts              # 다국어
│   │   ├── countries.ts         # 국가 정보
│   │   └── fcm.ts               # FCM 푸시
│   └── public/                  # 정적 자산
│
├── worker/
│   ├── celery_app.py            # Beat 스케줄 (30+ 태스크)
│   ├── tasks.py                 # 태스크 정의
│   ├── collector/               # RSS/Telegram 수집
│   ├── processor/               # 정규화, 클러스터링, 트렌딩, 긴장도
│   ├── push/                    # FCM 푸시 발송
│   └── social/                  # Telegram 봇, SNS 자동 포스팅
│
├── scripts/                     # 운영 스크립트
├── infra/                       # Docker 설정
├── android/                     # Android TWA 앱
└── .github/workflows/           # CI/CD
```

---

## 13. Environment Variables (주요)

| 변수 | 필수 | 설명 |
|------|------|------|
| `DATABASE_URL` | Y | PostgreSQL (asyncpg) |
| `REDIS_URL` | Y | Redis |
| `SECRET_KEY` | Y (프로덕션) | JWT 서명 |
| `ALLOWED_ORIGINS` | N | CORS 허용 도메인 |
| `FCM_PROJECT_ID` | Y | Firebase 프로젝트 |
| `GOOGLE_APPLICATION_CREDENTIALS` | Y | Firebase 서비스 계정 |
| `OPENAI_API_KEY` | Y | AI 분류/생성 |
| `TELEGRAM_API_ID/HASH/SESSION` | Y | Telegram 수집 |
| `TELEGRAM_BOT_TOKEN` | Y | Telegram 봇 |
| `TOSS_APP_SECRET` | N | 토스 앱인토스 |
| `ADMIN_EMAILS` | N | 자동 어드민 승격 |
| `SMTP_*` | N | 이메일 발송 |
| `SOCIAL_*` | N | SNS 자동 포스팅 |

---

*이 문서는 WeWantPeace 서비스의 전체 아키텍처를 다룹니다. 개선점 논의 시 참고해주세요.*

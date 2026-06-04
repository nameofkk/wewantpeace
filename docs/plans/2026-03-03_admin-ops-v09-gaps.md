# Admin Ops v0.9 누락 사항 수정 플랜
**날짜:** 2026-03-03
**상태:** 작성 완료, 승인 대기

## Context
Admin Ops v0.9 Sprint 1~2가 부분 구현됨. 사이드바 메뉴 미등록, 가이드 페이지 미생성, KPI alert 이메일 미발송 등 7개 갭 존재. 이 플랜은 누락 사항을 모두 보완한다.

## 누락 항목 요약

| # | 항목 | 심각도 |
|---|------|--------|
| 1 | 사이드바에 Partners/Links/Reports-Perf/Guide 메뉴 추가 | Critical |
| 2 | `/admin/guide` 가이드 페이지 신규 생성 | Critical |
| 3 | KPI drop alert 이메일 발송 기능 | High |
| 4 | Partner status에 prospect/rejected 추가 (lead 제거) | Medium |
| 5 | Partner 모델에 url, last_published_at 필드 추가 | Medium |
| 6 | weekly_kpi_snapshot에 data_source/referral 필드 | Medium |
| 7 | Partner "이번 주 follow-up" 필터 | Low |

## Phase 1: 백엔드 모델 + 마이그레이션 (GAP 4, 5, 6)

### 1-1. `backend/app/models/partner.py`
- `status` default: `"lead"` → `"prospect"`
- 필드 추가: `url` (String 512, nullable), `last_published_at` (TIMESTAMP, nullable)

### 1-2. `backend/app/models/weekly_kpi_snapshot.py`
- 필드 추가: `data_source` (String 16, default="auto")

### 1-3. `backend/alembic/versions/0028_admin_ops_v09.py`
- partners 테이블: `server_default="lead"` → `"prospect"`, `url`/`last_published_at` 컬럼 추가
- weekly_kpi_snapshots 테이블: `data_source` 컬럼 추가

## Phase 2: 백엔드 API (GAP 4, 5)

### 2-1. `backend/app/routers/admin.py`
- `PartnerCreate`: `url` 필드 추가, `status` default `"prospect"`
- `PartnerPatch`: `url` 필드 추가
- `create_partner`: `url=body.url` 전달
- `update_partner`: `"url"` 필드 iteration에 추가
- `list_partners`: 응답에 `url`, `last_published_at` 추가
- `generate_kpi_snapshot`: `data_source="manual"` 설정, referral 메트릭 추가
- 상태 검증: `VALID_PARTNER_STATUSES = {"prospect", "contacted", "negotiating", "active", "churned", "rejected"}`

## Phase 3: Worker 태스크 (GAP 3, 6)

### 3-1. `worker/tasks.py` — `snapshot_weekly_kpi`
- **referral 메트릭 추가**: `referral_install` (referred_by_code 있는 신규 유저), `referral_trial_start` (referred 유저의 trial 시작) → metrics JSONB에 포함
- **data_source="auto"** WeeklyKpiSnapshot 생성 시 설정
- **KPI drop alert 이메일**: alerts 생성 후, 비어있지 않으면 admin 유저들에게 SMTP 이메일 발송 (기존 send_weekly_report 패턴 재사용)

## Phase 4: 프론트엔드 (GAP 1, 2, 4, 5, 7)

### 4-1. `frontend/lib/i18n.ts`
- ko/en 블록에 추가: `admin_group_ops`, `admin_guide_title`, `admin_this_week_followup`, `admin_partner_url`, `admin_partner_prospect`, `admin_partner_rejected`

### 4-2. `frontend/app/admin/layout.tsx` — 사이드바 (GAP 1, CRITICAL)
- 아이콘 import 추가: `Handshake, Link2, FileBarChart, BookOpen`
- NAV_GROUPS에 "Operations" 그룹 추가 (Analytics와 System 사이):
  - `/admin/partners` (Handshake)
  - `/admin/links` (Link2)
  - `/admin/reports-perf` (FileBarChart)
  - `/admin/guide` (BookOpen)

### 4-3. `frontend/app/admin/partners/page.tsx` (GAP 4, 5, 7)
- STATUSES: `lead` → `prospect` 변경, `rejected` 추가
- STATUS_COLORS/STATUS_LABELS: 동일하게 업데이트
- Partner interface: `url` 필드 추가
- CreatePartnerModal: URL 입력 필드, default status `"prospect"`
- 테이블: url 링크 표시
- **"이번 주 팔로업" 필터 버튼** 추가 (client-side 필터링)

### 4-4. `frontend/app/admin/guide/page.tsx` — 신규 생성 (GAP 2, CRITICAL)
- 전체 어드민 메뉴 20개 섹션에 대한 종합 가이드 페이지
- 접이식(collapsible) 섹션, bilingual (ko/en)
- 섹션: Dashboard, Users, Subscriptions, Marketing, Posts, Comments, Reports, Feedbacks, Pipeline, Clusters, Events, Sources, KPI, Trending, Tension, Settings, Logs, Partners, Links, Reports-Perf

## 파일 수정 순서 (의존성 기반)

```
Phase 1 (모델+마이그레이션) ← 의존 없음
  ├── partner.py
  ├── weekly_kpi_snapshot.py
  └── 0028_admin_ops_v09.py

Phase 2 (백엔드 API) ← Phase 1 필요
  └── admin.py

Phase 3 (워커) ← Phase 1 필요
  └── tasks.py

Phase 4 (프론트엔드) ← Phase 2 API 계약 필요
  ├── i18n.ts
  ├── layout.tsx
  ├── partners/page.tsx
  └── guide/page.tsx (신규)
```

## 검증

1. Python 문법 검사: 모든 수정 백엔드 파일 `ast.parse()` 통과
2. 사이드바: `/admin` 접속 시 Operations 그룹에 4개 메뉴 표시 확인
3. 파트너: prospect/rejected 상태, url 필드, 이번 주 팔로업 필터 동작
4. KPI: snapshot에 data_source, referral 메트릭 포함 확인
5. 가이드: `/admin/guide` 20개 섹션 렌더링, ko/en 전환 확인
6. 커밋 & 푸시

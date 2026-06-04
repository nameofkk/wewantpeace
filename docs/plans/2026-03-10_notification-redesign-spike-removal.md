# WeWantPeace 알림 시스템 대개편 + Spike 제거 + SNS 개선

## Context

**문제**: 현재 Spike Detection 기반 알림은 첫 이벤트부터 스파이크 트리거까지 **4.8~185시간** 지연됨 (event_count >= 8 조건). 신속성이 생명인 서비스에서 치명적.

**해결**: Spike 개념을 완전히 제거하고, KScore가 사용자 임계값을 넘는 즉시 알림을 발송하는 새 모델로 전환. 시뮬레이션 결과 평균 지연이 **26.5시간 → 거의 즉시**로 단축됨.

**추가**: Threads SNS 포스팅 개선 (동적 토픽 + 댓글 링크) + 모든 문서/마케팅/UI 텍스트 일괄 업데이트.

**OG 이미지 502 수정**: 이미 커밋+푸시 완료 (`4d0bf95`). Railway 배포만 재트리거 필요 (GitHub integration 이슈). 이번 작업의 최종 커밋+푸시 시 함께 배포됨.

---

## SNS 소셜 포스트 트리거 조건 변경 (중요)

**기존**: SpikeEvent 기반 → severity >= 60인 스파이크만 SNS 자동 등록
**변경**: **KScore >= 5.0** 이상인 클러스터 신규 발생 시 SNS 자동 등록 (스파이크 무관)
- 시뮬레이션: 주 36건 (일 5.1건) — 적절한 볼륨
- dedup: 클러스터당 하루 1건 제한 유지

---

## 새 알림 모델 요약

| 기능 | Free | Pro | Pro+ |
|---|---|---|---|
| 신속 알림 (KScore+sev>=50) | ✅ | ✅ | ✅ |
| 신뢰 알림 (KScore+is_verified) | ❌ locked | ✅ | ✅ |
| 일일 상한 | 5 | 20 | 100 |
| Critical(sev>=80) 상한 무시 | ❌ | ✅ | ✅ |
| 개인화 컨텍스트 | ❌ | ✅ | ✅ |
| KScore 조절 | 3.0 고정 | 3.0~10.0 | 1.5~10.0 |
| 토픽/방해금지 | 고정 | 선택 | 선택 |

**알림 병합**: 신속+신뢰 동시 충족 시 1건만 발송. 신속만 발송 시 "추후 신뢰 인증될 수 있음" 안내 포함.

**UserArea 필드 변경**:
- 기존: `notify_fast=False` (기본값, Pro만 True로 변경 가능) → 신속 알림은 Pro 전용
- **변경**: `notify_fast` 필드의 의미를 뒤집음:
  - 모든 플랜에서 신속 알림(Fast) 수신 가능 → `notify_fast`는 기본 True, 사용자가 끌 수 있음
  - `notify_verified`는 Pro/Pro+ 전용 → Free 사용자는 UI에서 locked 표시
- 설정 페이지: Free 사용자에게 "신뢰 알림은 Pro에서 사용 가능" 잠금 표시 (기존 Fast 잠금 → Verified 잠금으로 변경)

**놓친 알림 표시 (Free 전환 유도)**:
- Free 사용자가 일일 상한(5건) 도달 시, 이후 억제된 알림 수를 Redis에 기록
- 홈 화면에 "놓친 알림 N건" 배너 표시 → Pro 업그레이드 유도
- 기존 `UserMissedSpikeSummary` → `UserMissedAlertSummary`로 변경

---

## 기존 vs 신규 비교표

| 항목 | 기존 (Spike 모델) | 신규 (KScore 모델) |
|---|---|---|
| **알림 트리거** | event_count>=8 + sev>=40 + sources>=3 | KScore >= user.min_kscore + sev>=50 |
| **평균 지연** | 26.5시간 (4.8~185시간) | 거의 즉시 (첫 KScore 초과 시) |
| **주간 알림 수** | ~6건 (스파이크 발생 시만) | ~450건 (KScore>=3.0 기준, 상한으로 조절) |
| **신속 알림** | Pro 전용 (Fast Lane) | 모든 플랜 |
| **신뢰 알림** | 모든 플랜 (Verified Lane) | Pro/Pro+ 전용 |
| **일일 상한** | 3/10/50 (free/pro/pro+) | 5/20/100 |
| **Critical 바이패스** | 없음 (FCFS) | Pro/Pro+ (sev>=80 시 상한 무시) |
| **SNS 자동 포스트** | SpikeEvent + sev>=60 | **KScore >= 5.0** (~5.1건/일) |
| **KScore 계산** | SPIKE_FACTOR 2.0x 적용 | SPIKE_FACTOR 제거 (1.0x) |
| **Threads 토픽** | 고정 #WeWantPeace | 동적 토픽 (내용+조회수 기반) |
| **Threads 댓글** | 없음 | 링크 + 홍보 문구 자동 댓글 |

---

## Phase 0: Feature Flag + 상수 변경 (파일 2개)

### `worker/processor/calibration.py`
- `SPIKE_FACTOR` → `1.0` (비활성화)
- 새 상수 추가:
  ```python
  USE_SPIKE_DETECTION = False  # 롤백 시 True로 복원
  ALERT_SEVERITY_MIN = 50
  CRITICAL_SEVERITY_MIN = 80
  KSCORE_SOCIAL_MIN = 5.0
  ```

### `worker/push/push_service.py`
- `DAILY_PUSH_LIMITS` 변경: `{"free": 5, "pro": 20, "pro_plus": 100}`

---

## Phase 1: Worker 핵심 로직 (파일 7개)

### 1-1. `worker/processor/spike_detector.py` — 비활성화
- `evaluate_spike()` 내부에 `USE_SPIKE_DETECTION` 가드 추가 → False면 즉시 `(False, None)` 반환
- 파일 삭제하지 않음 (롤백용 보존)

### 1-2. `worker/processor/trending_engine.py` — SPIKE_FACTOR 제거
- `_calc_kscore()`: `sf = 1.0` 고정 (is_spike 파라미터는 유지하되 무시)
- `calculate_global_trending()`: spike 무조건 포함 로직 제거 (`if kscore < KSCORE_MIN and not c.is_spike` → `if kscore < KSCORE_MIN`)
- `_make_reason()`: spike 분기 제거, scored dict에서 `is_spike=False` 고정

### 1-3. `worker/processor/clusterer.py` — is_spike 참조 제거
- `_calc_kscore()` 호출 시 `is_spike=False` 고정 (기존: `cluster.is_spike`)

### 1-4. `worker/push/push_service.py` — 핵심 리팩터링

**새 함수 `send_alert()`** (기존 `send_spike_alert()` 대체):
- 파라미터: `cluster_id, cluster_title, country_code, severity, kscore, is_verified, cluster_topic, alert_kind("fast"|"verified"|"combined"), db, redis`
- **신속 알림**: `notify_verified=True` 구독자 대상 (모든 플랜), KScore+severity 조건
- **신뢰 알림**: `notify_fast=True` 구독자 대상 → 이름 혼동 해결: `notify_verified` 유저에게 verified 알림, 모든 유저에게 fast 알림
- **Critical 바이패스**: `severity >= 80 AND plan in ("pro","pro_plus")` → 일일 상한 무시
- **Redis 중복방지**: `alert:fast:{cluster_id}` / `alert:verified:{cluster_id}` (TTL=72h, 클러스터 단위)
- **놓친 알림 추적**: Free 사용자 일일 상한 도달 시 `missed_alert_count:{user_id}:{date}` 기록 (TTL=7일)

`send_spike_alert()`: 내부에서 `send_alert()` 호출하는 wrapper로 변환 (하위호환)
`send_verified_alert()`: 내부에서 `send_alert(alert_kind="verified")` 호출
`save_in_app_notifications()`: `notif_type="spike"` → `"fast"` 또는 `"verified"`
`generate_spike_context()` → `generate_alert_context()` 리네임

**`_get_target_tokens_by_platform()` 핵심 변경**:
- 기존: `notify_fast=True` → Pro 사용자만 Fast Lane 대상
- 변경: Fast alert → 모든 플랜의 관심국가 구독자 대상 (notify_fast 체크 불필요)
- 변경: Verified alert → `notify_verified=True` AND `plan in ("pro","pro_plus")` 조건
- Free 사용자가 Verified 알림 받으려 하면 `plan_locked` suppression

### 1-5. `worker/tasks.py` — 파이프라인 변경

**`process_raw_event()`** (line 562-613):
- 스파이크 감지 블록 전체 제거 (evaluate_spike 호출 삭제)
- 신규 KScore 기반 알림 트리거:
  ```python
  if cluster.kscore >= KSCORE_MIN and cluster.severity >= ALERT_SEVERITY_MIN:
      fast_key = f"alert:fast:{cluster_id}"
      if not await redis.exists(fast_key):
          alert_kind = "combined" if cluster.is_verified else "fast"
          push_alert.delay(cluster_id, alert_kind)
          await redis.setex(fast_key, 259200, "1")  # 72h
  ```
- Verified 전환 시 추가 알림:
  ```python
  if just_verified:
      ver_key = f"alert:verified:{cluster_id}"
      if not await redis.exists(ver_key):
          push_alert.delay(cluster_id, alert_kind="verified")
          await redis.setex(ver_key, 259200, "1")
  ```

**`push_spike_alert` 태스크** → `push_alert` 태스크로 변경 (name="worker.tasks.push_alert")
**`push_verified_alert` 태스크**: `send_alert(alert_kind="verified")` 호출로 변경
**`cluster_async()`** (line 785): evaluate_spike 호출 제거
**`build_missed_spike_summary`** → `build_missed_alert_summary` (spike_event_id 참조 제거)
**`generate_spike_social`** → `generate_kscore_social`:
  - **트리거 조건**: SpikeEvent 테이블 조회 → **KScore >= 5.0** 클러스터 직접 조회로 변경
  - SpikeEvent 조인 완전 제거
  - 조회 쿼리: `SELECT * FROM issue_clusters WHERE kscore >= 5.0 AND severity >= 60 AND is_active = true AND last_event_at >= NOW() - INTERVAL '6 hours'`
  - dedup: `kscore_alert:{cluster_id}:{today}` (클러스터당 하루 1건)
  - severity 하한도 유지 (>=60, config에서 조정 가능)

### 1-6. `worker/social/generators.py`
- `generate_spike_alert()` → `generate_kscore_alert(cluster, db)` (SpikeEvent 파라미터 제거)
- `content_type`: `"spike_alert"` → `"kscore_alert"`
- `dedup_key`: `"kscore_alert:{cluster_id}:{today}"`
- `_build_hashtags()`: 고정 `#WeWantPeace` 외에 토픽+국가 기반 동적 해시태그 3개 선택

### 1-7. `worker/social/config.py`
- `SPIKE_SOCIAL_SEVERITY_MIN` → `KSCORE_SOCIAL_MIN = 5.0`

---

## Phase 2: Backend API + DB 마이그레이션 (파일 12개)

### 2-1. `backend/alembic/versions/0040_remove_spike_add_alert.py` (NEW)
```sql
-- 소프트 변경 (테이블/컬럼 삭제 안 함, 히스토리 보존)
ALTER TABLE user_missed_spike_summary RENAME TO user_missed_alert_summary;
ALTER TABLE user_missed_alert_summary RENAME COLUMN spike_event_id TO alert_cluster_id;
UPDATE notifications SET type = 'fast' WHERE type = 'spike';
-- issue_clusters.is_spike, spike_at 컬럼 유지 (deprecated)
-- spike_events 테이블 유지 (historical)
```

### 2-2. `backend/app/models/user_missed_spike.py` → 모델명/테이블명 변경
- `UserMissedSpikeSummary` → `UserMissedAlertSummary`, `__tablename__ = "user_missed_alert_summary"`
- `spike_event_id` → `alert_cluster_id`

### 2-3. `backend/app/models/notification.py` — type 주석: `"verified" | "fast"`
### 2-4. `backend/app/models/issue_cluster.py` — is_spike, spike_at에 deprecated 주석
### 2-5. `backend/app/models/spike_event.py` — deprecated 주석 (파일 유지)
### 2-6. `backend/app/models/alert_delivery_log.py` — spike_event_id 유지 (nullable)
### 2-7. `backend/app/routers/issues.py` — ClusterOut에서 `is_spike` 제거 (또는 `False` 고정)
### 2-8. `backend/app/routers/public.py` — is_spike 응답 제거
### 2-9. `backend/app/routers/admin.py` — spike 관련 엔드포인트를 KScore 기준으로 변경
### 2-10. `backend/app/routers/me.py`
- `/me/missed-spikes` → `/me/missed-alerts` (기존 경로 유지 + redirect)
- `MissedSpikeOut` → `MissedAlertOut`
- `notify_fast` Pro 제한 로직 변경:
  - 기존 (line 199-204): Free 사용자가 `notify_fast=True` 설정 시 거부
  - 변경: `notify_fast`는 모든 플랜에서 설정 가능 (신속 알림은 모든 플랜)
  - `notify_verified`에 Pro 제한 적용 (Free 사용자가 True 설정 시 거부)

### 2-11. `backend/app/main.py` — KScore 재계산에서 `is_spike=False` 고정
### 2-12. `backend/app/models/__init__.py` — 새 모델명 반영

---

## Phase 3: Frontend 변경 (파일 20개)

### 3-A. 핵심 라이브러리 (4개)

**`frontend/lib/i18n.ts`** (~70개 키 ko+en 동시 수정):
- 제거/변경 키: `glossary_spike*`, `issue_spike`, `map_spike`, `map_popup_spike`, `pipeline_stage_spike`, `pipeline_spike_clusters`, `pipeline_alert_spike*` (10개+), `missed_spike_*`, `notif_type_spike`, `banner_spike`, `tour_settings_notifications`
- 신규 키: `notif_type_fast`("신속 알림"/"Fast Alert"), `notif_type_verified`("신뢰 알림"/"Verified Alert"), `alert_plan_locked`, `missed_alert_banner`, `missed_alert_cta`
- 플랜 설명 업데이트: `settings_plan_free_desc`, `settings_plan_pro_desc`, `settings_plan_proplus_desc`
- 온보딩 텍스트: spike 언급 → KScore 기반 알림
- `paywall_pro_feature_countries`: "Fast alerts" → "Verified alerts"

**`frontend/lib/api.ts`**: `MissedSpike` → `MissedAlert`, `useMissedSpikes()` → `useMissedAlerts()`, API 경로 변경
**`frontend/lib/store.ts`**: `spikeAlertCount` → `missedAlertCount`, store version 증가
**`frontend/lib/server/issues.ts`**: `is_spike` 제거

### 3-B. 페이지 컴포넌트 (12개)

| 파일 | 변경 내용 |
|---|---|
| `home/page.tsx` | spike 지표 제거, 놓친 알림 배너를 missedAlerts 기반으로 변경 |
| `map/page.tsx` | spike 마커/카운트/CSS 클래스 제거 |
| `issues/[id]/client.tsx` | spike 배지 제거 |
| `issues/country/[code]/client.tsx` | spike 지표 제거 |
| `notifications/page.tsx` | NOTIF_TYPE_STYLES에서 "spike" → "fast" |
| `settings/page.tsx` | **핵심**: 기존 Fast 알림 잠금(Free) → Verified 알림 잠금(Free)으로 반전. 플랜별 접근 테이블 UI 추가 (5/20/100 상한, Critical 바이패스 등). KScore 범위: Free=3.0고정, Pro=3.0~10.0, Pro+=1.5~10.0 |
| `settings/glossary/page.tsx` | Spike 용어 제거, KScore Alert 용어 추가 |
| `api-docs/page.tsx` | is_spike 필드 제거 |
| `admin/clusters/page.tsx` | SPIKE 배지 제거 |
| `admin/kscore/page.tsx` | spike 지표/카운트 제거 |
| `admin/pipeline/page.tsx` | spike 파이프라인 스테이지 → "KScore 알림" |
| `admin/social/page.tsx` | spike_alert → kscore_alert |

### 3-C. UI 컴포넌트 (4개)

| 파일 | 변경 내용 |
|---|---|
| `new-event-banner.tsx` | is_spike 표시 제거 |
| `UpgradeNudgeBanner.tsx` | spike count → missed alert count 기반 |
| `globals.css` | `spike-ring` 애니메이션 → `alert-ring` 또는 제거 |

---

## Phase 4: Threads SNS 개선 + Worker 부속 변경 (파일 5개)

### 4-1. `worker/social/adapters/threads_adapter.py`
**댓글(reply) 기능 추가**:
- `publish()` 후 `reply_to_id` 파라미터로 댓글 발행
- 댓글 내용: 이슈 링크 + 서비스 홍보 문구 (bilingual)
  ```
  🔗 Full analysis: https://wewantpeace.live/issues/{id}
  📊 Real-time conflict tracking · WeWantPeace
  상세 분석 보기 · 실시간 분쟁 모니터링
  ```
- 댓글 실패 시 warning 로깅만 (메인 포스트 성공은 보존)

**동적 토픽 선택**:
- `_build_hashtags()` 변경: 고정 `#WeWantPeace` 제거
- 클러스터 topic + country_code 기반으로 조회수 높은 해시태그 3개 선택
- 토픽→해시태그 매핑 확장: conflict→`#Breaking #Conflict`, terror→`#Breaking #Terror` 등
- 국가별 트렌딩 해시태그 우선 사용

### 4-2. `worker/social/monitor.py`
- `_check_unpublished_spikes()` → `_check_unpublished_alerts()` (KScore >= 5.0 기준)

### 4-3. `worker/social/card_generator.py`
- `"spike_alert"` → `"kscore_alert"` content_type
- spike 특수 색상 로직 제거

### 4-4. `worker/social/telegram_bot.py`
- `spike_alert` 콘텐츠 타입 라벨 → `kscore_alert`
- 텔레그램 봇 메시지에서 "스파이크" 용어 제거

### 4-5. `worker/health/checker.py` + `worker/health/fixer.py`
- spike_events 관련 헬스체크/자동수정 로직 → KScore 기반으로 변경

---

## Phase 5: 문서 & 마케팅 전면 업데이트 (파일 10개)

| 파일 | 변경 |
|---|---|
| `README.md` | 파이프라인에서 "spike detect" 제거, "KScore-based alerts" 추가 |
| `README.ko.md` | 동일 (한국어) |
| `docs/METHODOLOGY.md` | Spike Detection 섹션 → KScore Alert System |
| `docs/DATA_DICTIONARY.md` | spike 필드 deprecated 표시, 새 알림 모델 문서화 |
| `docs/marketing/show-hn-post.md` | "spike alerts" → "KScore-based real-time alerts" |
| `docs/marketing/product-hunt-draft.md` | spike 언급 제거 |
| `docs/marketing/platform-content.md` | "스파이크 감지" → "KScore 기반 실시간 알림" |
| `docs/marketing/bellingcat-pitch-email.md` | spike detection → KScore alerts |
| `docs/marketing/case-studies.md` | spike 데이터 분석 → KScore 분석으로 재작성 |

---

## Phase 6: 테스트 + 시뮬레이션 (파일 3개)

### `backend/tests/test_spike_detector.py` → `test_alert_trigger.py` (재작성)
- KScore+severity 조건 충족 → 알림 트리거 확인
- 미충족 → 비트리거 확인
- Redis 중복방지 키 동작 확인
- 72h TTL 만료 후 재트리거

### `backend/tests/test_push_service.py` (업데이트)
- `send_alert()` fast/verified/combined 각 경우 테스트
- Critical 바이패스 (sev>=80, Pro) 테스트
- 일일 상한 (5/20/100) 테스트
- 놓친 알림 카운터 테스트

### 시뮬레이션
- 프로덕션 DB에서 최근 7일 데이터로 시뮬레이션 실행
- 기존 모델 vs 새 모델 비교표 생성:
  - 알림 수: 스파이크 6건/주 → KScore>=3.0 450건/주
  - 지연: 평균 26.5시간 → 거의 즉시
  - 일일 상한으로 Free 유저 실제 수신: 5건/일

---

## 배포 순서

| 순서 | 내용 | 파일 | 비고 |
|---|---|---|---|
| 배포 A | Phase 0+1+2 (Worker+Backend+Migration) | ~21개 | 동시 배포 |
| 배포 B | Phase 3 (Frontend) | ~20개 | 배포 A 후 |
| 배포 C | Phase 4 (SNS+Worker부속) | 5개 | 배포 A 후, B와 병렬 |
| 배포 D | Phase 5 (Docs) | 10개 | 독립 |
| 배포 E | Phase 6 (Tests) | 3개 | 전체 후 |

---

## 롤백 전략

**즉각 롤백 (5분)**: `calibration.py`에서 `USE_SPIKE_DETECTION=True`, `SPIKE_FACTOR=1.5`, `DAILY_PUSH_LIMITS` 원복 → Worker 재배포
**DB 롤백**: `alembic downgrade -1`
**프론트엔드 롤백**: git revert + 재배포

---

## 리스크 & 대응

| 리스크 | 대응 |
|---|---|
| Fast+Verified 이중 알림 | Redis 중복방지 키 + combined 분기로 1건만 |
| 마이그레이션 FK 충돌 | SET NULL FK라 안전, 테이블 삭제 안 함 |
| Free 과다 알림 | KScore + severity>=50 이중 필터 + 일일 5건 상한 |
| Threads reply 실패 | warning 로깅만, 메인 포스트 정상 반환 |
| spike_events 히스토리 유실 | 테이블 삭제 안 함, deprecated만 표시 |

---

## 검증 방법

1. Worker 로그에서 `evaluate_spike` 호출이 즉시 `(False, None)` 반환하는지 확인
2. 새 클러스터 생성 시 `push_alert` 태스크가 트리거되는지 확인
3. `alert_delivery_log`에 새 `alert_type="fast"/"verified"/"combined"` 로그 기록 확인
4. Free 사용자 일일 5건 상한 도달 후 `missed_alert_count` Redis 키 증가 확인
5. severity >= 80 클러스터에서 Pro 사용자 상한 무시 확인
6. Threads 포스트 발행 후 reply(댓글)가 달리는지 확인
7. 프론트엔드에서 "spike"/"스파이크" 텍스트가 어디에도 노출되지 않는지 전수 검색
8. `spike_events` 테이블에 새 레코드가 생기지 않는지 확인
9. **SNS 자동 포스트**: KScore >= 5.0 클러스터 발생 시 `generate_kscore_social` 태스크 트리거 확인
10. **Settings 페이지**: Free 사용자 → 신뢰 알림 locked 표시 확인, Pro → 신뢰 알림 활성화 확인
11. **시뮬레이션 실행**: 프로덕션 DB 최근 7일 데이터로 새 모델 시뮬레이션 → 기존 vs 신규 비교표 출력
12. **OG 이미지**: Railway 배포 후 기존 502 이슈 URL에서 OG 이미지 정상 렌더링 확인
13. **전체 문서**: README, docs/, marketing/ 디렉토리에서 "spike" grep 결과 0건 확인

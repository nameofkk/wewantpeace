# Intelligence Layers — 멀티소스 데이터 확장 + 비주얼 레이어 시스템

## Context

WeWantPeace는 현재 ~40개 RSS + 8 Telegram + 7 API 소스로 뉴스 기반 분쟁 모니터링을 제공.
업계 표준(Liveuamap, Dataminr, Bellingcat 등)은 **위성 열점, 인터넷 단절, GPS 교란** 등 비-뉴스 센서 데이터를 교차검증에 활용.
이번 작업으로 **3개 Phase를 한꺼번에** 구현:
- Phase 1: NASA FIRMS 열점 + IODA 인터넷 단절 + 교차검증 + WebGL 비주얼
- Phase 2: Cloudflare Radar + GPS 교란 레이어 + UCDP 역사 데이터
- Phase 3: 이슈 상세 교차검증 UI + 매칭 연결선 시각화 + RSS 소스 대량 추가

---

## Phase 1 (MVP) — 구현 순서

### Step 1: DB 스키마

**새 파일:** `backend/alembic/versions/0047_signal_points_table.py`
**새 파일:** `backend/app/models/signal_point.py`

`signal_points` 테이블:
```
id              UUID PK
signal_type     VARCHAR(20) NOT NULL  -- 'firms_hotspot' | 'ioda_outage' | 'cf_anomaly'
external_id     VARCHAR(256) NOT NULL UNIQUE
lat, lon        FLOAT NOT NULL
country_code    VARCHAR(4)
intensity       FLOAT NOT NULL DEFAULT 0  -- 정규화 0~1
raw_value       FLOAT                     -- 원본 (FRP, fraction 등)
confidence      FLOAT DEFAULT 0.5
metadata        JSONB DEFAULT '{}'
observed_at     TIMESTAMPTZ NOT NULL
collected_at    TIMESTAMPTZ NOT NULL DEFAULT now()
expires_at      TIMESTAMPTZ              -- 24h(열점), 48h(단절)
matched_cluster_id  UUID FK(issue_clusters.id, SET NULL)
match_distance_km   FLOAT
match_time_delta_h  FLOAT
```

인덱스: `(signal_type, observed_at DESC)`, `(country_code, observed_at DESC)`, `(expires_at)`

**수정:** `backend/app/models/issue_cluster.py` — 2개 컬럼 추가:
- `signal_corroboration_count: Int DEFAULT 0`
- `signal_types: Text[] DEFAULT '{}'`

설계 근거: raw_events 파이프라인에 넣지 않는 이유 — FIRMS는 1회 수집에 수천건, GPT 정규화/클러스터링 불필요. process_raw_event 큐 부하 방지.

---

### Step 2: FIRMS Collector

**새 파일:** `worker/collector/firms_collector.py`

- 패턴: `usgs_earthquake.py`와 동일 (dataclass Result, collect/collect_all)
- API: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/world/1`
- 센서: `MODIS_NRT` + `VIIRS_NOAA20_NRT`
- 필터: confidence >= 50(MODIS) / "nominal"(VIIRS), FRP >= 10 MW
- intensity 정규화: `min(1.0, frp / 500.0) * conf_multiplier`
- external_id: `firms:{source}:{acq_date}:{round(lat,3)}:{round(lon,3)}`
- country_code: 좌표→국가 매핑 (shapely + countries-110m.geojson, worker 시작 시 1회 로드)
- expires_at: observed_at + 24h
- **signal_points 테이블에 INSERT** (raw_events 아님)

환경변수: `FIRMS_MAP_KEY` (NASA FIRMS 무료 발급)

---

### Step 3: IODA Outage Collector

**새 파일:** `worker/collector/outage_collector.py`

- API: `https://ioda.caida.org/ioda/data/events`
- 인증 불필요
- 모니터링 대상: 분쟁 16개국 (UA, PS, SY, YE, MM, SD, SO, AF, IR, IQ, RU, BY, ET, LY, CD, ML)
- 단절 판단: fraction < 0.5 (50% 이상 영향)
- intensity: `1.0 - fraction` (0=정상, 1=완전단절)
- lat/lon: COUNTRY_CENTERS (normalizer.py에 이미 존재) 재사용
- external_id: `ioda:{cc}:{datasource}:{timestamp_5min_rounded}`
- expires_at: observed_at + 48h

---

### Step 4: Celery Tasks + Schedule

**수정:** `worker/tasks.py` — 4개 태스크 추가:
- `collect_firms` (queue=collect)
- `collect_outage` (queue=collect)
- `correlate_signals` (queue=process)
- `cleanup_expired_signals` (queue=process)

패턴: 기존 `collect_usgs` 태스크와 동일. `run_async(_run())` 래퍼.
단, signal_points INSERT이므로 `process_raw_event.delay()` 체이닝 **없음**.

**수정:** `worker/celery_app.py` — beat_schedule 추가:
```python
"collect-firms":    crontab(minute="*/15")    # 15분마다
"collect-outage":   crontab(minute="*/15")    # 15분마다
"correlate-signals": crontab(minute="0,5,10,15,20,25,30,35,40,45,50,55")  # 5분마다
"cleanup-expired-signals": crontab(minute=0, hour="*/6")  # 6시간마다
```

---

### Step 5: Signal Correlator (교차검증 엔진)

**새 파일:** `worker/processor/signal_correlator.py`

매칭 로직:
1. 미매칭 signal_points (matched_cluster_id IS NULL, 최근 48h) 조회
2. 활성 issue_clusters (is_active=True, 최근 48h) 조회
3. 지리(100km 이내) + 시간(24h 이내) 근접성 기반 매칭
4. 복합 점수: `(1 - dist/100km) * 0.6 + (1 - time_delta/24h) * 0.4`
5. 점수 > 0.3이면 매칭

클러스터 보정:
- `independent_sources += len(matched_signal_types)` (최대 SPREAD_SATURATION=12)
- `confidence += avg(signal_weight * signal_intensity) * 0.15` (cap 1.0)
- `signal_corroboration_count`, `signal_types` 업데이트

시그널별 가중치: firms_hotspot=0.3, ioda_outage=0.5

---

### Step 6: Tension/KScore 수치 반영

**수정:** `worker/processor/calibration.py` — 상수 추가 (v7 변경):
```python
# ── Signal Corroboration (v7) ───────────────────────
SIGNAL_BONUS_PER_TYPE: float = 5.0   # 시그널 유형당 tension 보너스
SIGNAL_BONUS_MAX: float = 15.0       # 최대 보너스
SIGNAL_CONFIDENCE_BOOST: float = 0.15 # confidence 최대 상승폭
```

**수정:** `worker/processor/tension_calculator.py`:
- `calculate_country_tension()`에서 해당 국가의 signal_points 집계
- EventScore에 signal_bonus 추가: `min(15.0, 5.0 * corroboration_types_count)`
- convergence_bonus와 동일한 패턴으로 raw_score에 가산

**KScore 반영** (자동): correlator가 `independent_sources`와 `confidence`를 올리면
trending_engine의 `_calc_kscore()`가 spread(0.30 가중치)와 quality(0.10 가중치)를 통해 자동 반영.
- independent_sources +1 = KScore +0.25
- confidence +0.1 = KScore +0.1

---

### Step 7: API 엔드포인트

**새 파일:** `backend/app/routers/signals.py`

```
GET /signals/firms     — FIRMS 열점 GeoJSON (Pro 전용)
GET /signals/outage    — 인터넷 단절 GeoJSON (Pro 전용)
GET /signals/summary   — 시그널 요약 카운트 (Free 접근 가능, 넛지용)
```

- GeoJSON FeatureCollection 형식 (MapLibre 직접 소비)
- Redis 캐시 5분 TTL
- Pro 게이팅: `plan_required("pro")` 의존성

**수정:** `backend/app/main.py` — signals 라우터 등록

---

### Step 8: 프론트엔드 — API 훅

**수정:** `frontend/lib/api.ts` — 추가:
```typescript
useFirmsSignals(enabled: boolean)   // enabled=레이어 ON일때만 fetch
useOutageSignals(enabled: boolean)
useSignalSummary()                  // Free 유저 넛지용
```
React Query: staleTime=5min, refetchInterval=5min, `enabled` flag로 lazy load

---

### Step 9: 프론트엔드 — WebGL 레이어 + 애니메이션

**수정:** `frontend/app/(main)/map/client.tsx`

#### FIRMS Heatmap 레이어 (WebGL, DOM 부하 0):
- Layer type: `heatmap` (저줌) + `circle` (고줌 >=6)
- 색상: 어두운 빨강 → 밝은 주황 → 흰색 그라데이션
- 줌 기반: radius 8(줌2) → 25(줌8), opacity 0.7 → 0.5
- **펄스 애니메이션**: `requestAnimationFrame`으로 `heatmap-intensity`를 sin 함수로 0.85~1.0 범위 변동 (2초 주기 breathing)

#### Outage Bubble 레이어 (WebGL):
- Layer type: `circle` (국가 중심 좌표)
- 색상: 인디고/보라 계열 (열점의 적색과 대비)
- radius: intensity 기반 10~50px
- **파동 애니메이션**: `requestAnimationFrame`으로 `circle-stroke-width` 1~4px 변동 (3초 주기 ripple)

#### 레이어 계층 (아래→위):
```
[4] HTML Markers (기존 이슈 마커)
[3] Outage bubbles (circle)
[2] FIRMS heatmap/circles
[1] Choropleth fill (기존 히트맵)
[0] Base map
```

---

### Step 10: 프론트엔드 — LayerControl UI

**수정:** `frontend/app/(main)/map/client.tsx`

상단 헤더 바 Row 2 히트맵 버튼 옆에 레이어 패널 토글 추가:

```
[히트맵] [🛡 Intel ▾]  ← 클릭하면 드롭다운
  ┌───────────────────────────────┐
  │ 🔥 위성 열점     [ON/OFF] 🔒 │ Pro
  │    1,234개 | 15분 전           │
  │ 🌐 인터넷 단절   [ON/OFF] 🔒 │ Pro
  │    3개국 | 15분 전             │
  │ 📡 GPS 교란      곧 출시      │ Phase 2
  └───────────────────────────────┘
```

- Free: 토글 클릭 → PaywallModal
- Pro: 토글 ON → useFirmsSignals(true) → map.addSource/addLayer
- 토글 OFF → removeLayer/removeSource + cancelAnimationFrame

**수정:** `frontend/lib/i18n.ts` — ko/en 동시 추가:
- `layer_panel_title`, `layer_firms`, `layer_outage`, `layer_gps_jam`
- `layer_count`, `layer_updated`, `layer_coming_soon`, `layer_pro_only`

---

---

## Phase 2 — Cloudflare Radar + GPS 교란 + UCDP

### Step 11: Cloudflare Radar Collector

**새 파일:** `worker/collector/cloudflare_radar_collector.py`

- API: `https://api.cloudflare.com/client/v4/radar/traffic_anomalies/latest`
- 인증: `Authorization: Bearer <CF_RADAR_TOKEN>` (무료 계정, 40req/min)
- 수집 대상: 분쟁 16개국 + 전체 글로벌 anomaly
- 응답 파싱: `anomalies[].locations[].code`, `estimatedImpact`, `startTime`
- intensity: `estimatedImpact` (0~1 그대로 사용)
- signal_type: `cf_anomaly`
- external_id: `cf:{location}:{startTime_iso}`
- expires_at: observed_at + 48h
- 수집 주기: 30분 (40req/min 레이트리밋 고려)

환경변수: `CF_RADAR_TOKEN` (Cloudflare 무료 계정에서 API 토큰 발급)

### Step 12: GPS 교란 탐지 Collector

**새 파일:** `worker/collector/gps_jam_collector.py`

GPSJam은 공식 API가 없으므로 **ADS-B Exchange 기반 간접 추론** 방식:

- 방법: 분쟁 지역 상공 항공기의 `nac_p` (위치 정확도) 값 분석
- 분쟁 지역별 bbox 정의 (UA, PS/IL, SY, YE, IR 등 10개 지역)
- nac_p < 6인 항공기 비율이 30% 초과 → GPS 교란 판정
- intensity: `low_accuracy_ratio` (예: 40% → 0.4)
- signal_type: `gps_jam`
- lat/lon: 교란 감지 영역 중심점
- external_id: `gps_jam:{region}:{timestamp_15min_rounded}`
- expires_at: observed_at + 12h (교란은 단기 현상)

대안 (ADS-B 접근 불가 시): GPSJam.org 웹에서 GeoTIFF/PNG 타일 다운 → 이미지 분석으로 교란 지역 추출 (복잡, Plan B)

수집 주기: 15분

### Step 13: UCDP 역사적 분쟁 데이터 Collector

**새 파일:** `worker/collector/ucdp_collector.py`

- API: `https://ucdpapi.pcr.uu.se/api/gedevents/v25.1`
- 인증: `x-ucdp-access-token: <UCDP_TOKEN>` (무료 발급)
- 데이터 특성: 1-2개월 지연, 검증된 학술 데이터
- **raw_events 파이프라인으로 투입** (signal_points 아님 — 뉴스 이벤트와 동일 취급)
- raw_metadata:
  ```python
  structured_topic: "conflict" / "terror" / "protest"  # event_type 매핑
  structured_severity: fatalities 기반 계산
  structured_country: country_code
  structured_lat, structured_lon: UCDP 좌표
  ```
- source_tier: "A" (학술 검증 데이터)
- external_id: `ucdp:{event_id_cnty}`
- 수집 주기: 매일 1회 (06:00 UTC) — 데이터 갱신 빈도가 낮으므로

환경변수: `UCDP_ACCESS_TOKEN`

### Step 14: Celery Tasks + Schedule (Phase 2 추가분)

**수정:** `worker/tasks.py` — 3개 태스크 추가:
- `collect_cloudflare_radar` (queue=collect)
- `collect_gps_jam` (queue=collect)
- `collect_ucdp` (queue=collect)

**수정:** `worker/celery_app.py` — beat_schedule 추가:
```python
"collect-cloudflare-radar": crontab(minute="*/30")   # 30분마다
"collect-gps-jam":          crontab(minute="*/15")   # 15분마다
"collect-ucdp":             crontab(minute=0, hour=6) # 매일 06:00 UTC
```

### Step 15: GPS 교란 WebGL 레이어

**수정:** `frontend/app/(main)/map/client.tsx`

#### GPS Jamming Zone 레이어:
- Layer type: `fill` (영역) + `line` (경계)
- 색상: 시안/전기 계열 (기존 빨강/보라와 구분)
- 투명도: intensity 기반 0.1~0.4
- **파동 애니메이션**: `requestAnimationFrame`으로 fill-opacity를 sin 함수로 변동 (4초 주기, 전자파 느낌)
- 경계선: 점선 패턴 (`line-dasharray: [4, 4]`)

레이어 계층 업데이트:
```
[5] HTML Markers (기존 이슈 마커)
[4] GPS Jamming zones (fill + line)
[3] Outage bubbles (circle)
[2] FIRMS heatmap/circles
[1] Choropleth fill (기존 히트맵)
[0] Base map
```

### Step 16: Signal Correlator 확장

**수정:** `worker/processor/signal_correlator.py` — 가중치 추가:
```python
SIGNAL_WEIGHTS = {
    "firms_hotspot": 0.3,
    "ioda_outage": 0.5,
    "cf_anomaly": 0.4,     # 추가
    "gps_jam": 0.6,         # 추가 (군사 활동 직접 증거)
}
```

### Step 17: API 엔드포인트 확장

**수정:** `backend/app/routers/signals.py` — 추가:
```
GET /signals/gps-jam   — GPS 교란 지역 GeoJSON (Pro 전용)
```

**수정:** `frontend/lib/api.ts`:
```typescript
useGpsJamSignals(enabled: boolean)
```

### Step 18: LayerControl UI 확장

**수정:** `frontend/app/(main)/map/client.tsx` — LayerControl에 GPS 교란 토글 활성화:
```
🔥 위성 열점     [ON/OFF] 🔒 Pro
🌐 인터넷 단절   [ON/OFF] 🔒 Pro
📡 GPS 교란      [ON/OFF] 🔒 Pro   ← "곧 출시" → 활성화
```

**수정:** `frontend/lib/i18n.ts` — GPS 교란 관련 번역 추가

---

## Phase 3 — 이슈 상세 교차검증 UI + 매칭 시각화 + RSS 대량 추가

### Step 19: signal_matches 이력 테이블

**새 파일:** `backend/alembic/versions/0048_signal_matches_table.py`

`signal_matches` 테이블:
```
id              SERIAL PK
signal_id       UUID FK(signal_points.id, CASCADE)
cluster_id      UUID FK(issue_clusters.id, CASCADE)
match_score     FLOAT NOT NULL      -- 매칭 점수 (0~1)
distance_km     FLOAT
time_delta_h    FLOAT
created_at      TIMESTAMPTZ DEFAULT now()
```
인덱스: `(cluster_id, created_at DESC)`, `(signal_id)`

**수정:** `worker/processor/signal_correlator.py` — 매칭 시 signal_matches에도 INSERT (이력 추적)

### Step 20: 이슈 상세 "교차검증 증거" 섹션

**수정:** `frontend/app/(main)/issues/[id]/client.tsx`

이슈 상세 페이지에 새 섹션 추가 (KScore 히스토리 아래):

```
┌─ 교차검증 증거 ──────────────────────────┐
│ 🔥 위성 열점 3건 매칭 (12km, 2시간 전)    │
│    FRP: 45MW, 82MW, 120MW                │
│ 🌐 인터넷 단절 감지 (이란, 45% 영향)      │
│                                          │
│ 📊 교차검증으로 신뢰도 +15% 상승          │
└──────────────────────────────────────────┘
```

- Pro/Pro+ 전용 (ProDemoWrapper)
- API: `GET /issues/{id}/signals` — 매칭된 signal_matches 목록

**새 파일 (또는 수정):** `backend/app/routers/issues.py` — `/issues/{id}/signals` 엔드포인트 추가

### Step 21: 매칭 연결선 시각화

**수정:** `frontend/app/(main)/map/client.tsx`

교차검증된 열점/교란 포인트 → 이슈 마커 사이 **연결선(arc)** 표시:

- MapLibre GL `line` 레이어 (대원호 근사)
- 색상: 매칭 점수 기반 그라데이션 (낮으면 연한, 높으면 진한)
- 애니메이션: `line-dasharray` 이동으로 흐르는 듯한 효과
- 트리거: 이슈 마커 호버/클릭 시 해당 이슈에 매칭된 시그널과의 연결선만 표시
- 성능: 호버 시에만 렌더링 (상시 표시하면 너무 복잡)

```typescript
// 마커 호버 이벤트에서:
const matchedSignals = await fetch(`/signals/matched/${clusterId}`);
// → GeoJSON LineString으로 변환
// → map.addSource("match-arcs", { type: "geojson", data: lineGeoJSON });
// → map.addLayer({ id: "match-arcs", type: "line", ... });

// 대원호 근사 (Bezier):
function greatCircleArc(from: [number, number], to: [number, number], steps = 20): [number, number][] {
  // 중간점을 위도 방향으로 살짝 올려서 곡선 효과
}
```

**라인 dash 애니메이션:**
```typescript
let dashOffset = 0;
function animateMatchArcs(map: maplibregl.Map) {
  dashOffset = (dashOffset + 0.5) % 12;
  map.setPaintProperty("match-arcs", "line-dasharray", [4, 4]);
  // line-offset으로 흐름 표현
  requestAnimationFrame(() => animateMatchArcs(map));
}
```

### Step 22: RSS 소스 대량 추가

**새 파일:** `backend/alembic/versions/0049_seed_intelligence_rss.py`

DB INSERT로 RSS 피드 추가 (코드 수정 없이 rss_collector가 자동 수집):

| 매체 | feed_url | tier | geo_focus |
|------|----------|------|-----------|
| SIPRI | `https://www.sipri.org/rss` | A | global |
| NK News | `https://www.nknews.org/feed/` | B | KP |
| ISW | `https://www.iswresearch.org/feeds/posts/default` | A | UA/RU |
| Breaking Defense | `https://breakingdefense.com/feed/` | B | global |
| Defense One | `https://www.defenseone.com/rss/` | B | global |
| The War Zone | `https://www.thedrive.com/the-war-zone/feed` | B | global |
| Haaretz | `https://www.haaretz.com/cmlink/1.628765` | B | IL/PS |
| NATO | `https://www.nato.int/cps/en/natohq/news.xml` | A | EU |
| Military Times | `https://www.militarytimes.com/arc/outboundfeeds/rss/` | B | US |

### Step 23: 이슈 상세 — UCDP 역사적 맥락 섹션

**수정:** `frontend/app/(main)/issues/[id]/client.tsx`

교차검증 증거 섹션 아래에:

```
┌─ 역사적 맥락 (UCDP) ─────────────────────┐
│ 이 지역의 분쟁 역사:                       │
│ • 2020-2026: 847건의 기록된 분쟁 이벤트     │
│ • 주요 행위자: Syrian govt, IS, SDF         │
│ • 최근 12개월 사망자: 1,234명              │
│ 📈 [분쟁 추이 미니 차트]                   │
└───────────────────────────────────────────┘
```

- API: `GET /issues/{id}/context` — UCDP 데이터 기반 역사적 맥락
- Pro+ 전용
- Recharts 미니 LineChart로 연도별 이벤트 추이

**수정:** `backend/app/routers/issues.py` — `/issues/{id}/context` 엔드포인트 추가

### Step 24: Free 유저 넛지 배너

**수정:** `frontend/app/(main)/map/client.tsx`

Free 유저가 지도를 볼 때, 하단에 반투명 배너:

```
"🛡 지금 이 지역에 위성 열점 12건, GPS 교란 2건이 감지되었습니다 — Pro로 확인하기"
```

- `useSignalSummary()` 훅 데이터 기반
- 분쟁 활성 지역에서만 표시
- 5초 후 자동 fade out, dismiss 가능
- `UpgradeNudgeBanner`와 유사한 패턴

---

## 수정 파일 요약 (전체 3 Phase)

### 새 파일 (14개):
```
backend/alembic/versions/0047_signal_points_table.py
backend/alembic/versions/0048_signal_matches_table.py
backend/alembic/versions/0049_seed_intelligence_rss.py
backend/app/models/signal_point.py
backend/app/routers/signals.py
worker/collector/firms_collector.py
worker/collector/outage_collector.py
worker/collector/cloudflare_radar_collector.py
worker/collector/gps_jam_collector.py
worker/collector/ucdp_collector.py
worker/processor/signal_correlator.py
docs/plans/2026-03-15_intelligence-layers.md  (이 플랜 사본)
```

### 수정 파일 (10개):
```
backend/app/models/issue_cluster.py     — signal_corroboration_count, signal_types 컬럼
backend/app/main.py                     — signals 라우터 등록
backend/app/routers/issues.py           — /issues/{id}/signals, /issues/{id}/context 추가
worker/celery_app.py                    — beat_schedule 7개 추가
worker/tasks.py                         — 7개 태스크 함수
worker/processor/calibration.py         — SIGNAL_BONUS 상수 (v7)
worker/processor/tension_calculator.py  — signal_bonus EventScore 반영
frontend/app/(main)/map/client.tsx      — WebGL 레이어 + LayerControl + 애니메이션 + 연결선 + 넛지
frontend/app/(main)/issues/[id]/client.tsx — 교차검증 증거 + 역사적 맥락 섹션
frontend/lib/api.ts                     — 시그널 관련 훅 4개
frontend/lib/i18n.ts                    — 레이어/교차검증 관련 ko/en 번역
```

### 새 파일 (7개):
```
backend/alembic/versions/0047_signal_points_table.py
backend/app/models/signal_point.py
backend/app/routers/signals.py
worker/collector/firms_collector.py
worker/collector/outage_collector.py
worker/processor/signal_correlator.py
docs/plans/2026-03-15_intelligence-layers.md  (이 플랜 사본)
```

### 수정 파일 (8개):
```
backend/app/models/issue_cluster.py    — signal_corroboration_count, signal_types 컬럼
backend/app/main.py                    — signals 라우터 등록
worker/celery_app.py                   — beat_schedule 4개 추가
worker/tasks.py                        — 4개 태스크 함수
worker/processor/calibration.py        — SIGNAL_BONUS 상수 (v7)
worker/processor/tension_calculator.py — signal_bonus EventScore 반영
frontend/app/(main)/map/client.tsx     — WebGL 레이어 + LayerControl + 애니메이션
frontend/lib/api.ts                    — useFirmsSignals, useOutageSignals 훅
frontend/lib/i18n.ts                   — 레이어 관련 ko/en 번역
```

---

## 성능 영향 분석

| 항목 | 영향 | 대응 |
|------|------|------|
| Worker 메모리 | +~50MB (shapely + geojson 캐시) | 허용 범위 |
| Celery 큐 부하 | +2 collect(15분) + 1 process(5분) | process_raw_event 큐 무관 |
| DB 쓰기 | FIRMS ~5K rows/일, IODA ~50 rows/일 | expires_at로 자동 정리 |
| 프론트엔드 로딩 | 레이어 OFF시 API 호출 0 | React Query enabled flag |
| 지도 렌더링 | WebGL heatmap/circle = GPU 렌더링 | 10K+ 포인트도 60fps |
| 번들 사이즈 | 추가 npm 의존성 0 | MapLibre GL 이미 설치됨 |

---

## 환경변수 (Railway에 추가)

```
FIRMS_MAP_KEY=<NASA FIRMS MAP_KEY>       # https://firms.modaps.eosdis.nasa.gov/api/map_key/
CF_RADAR_TOKEN=<Cloudflare API Token>    # https://dash.cloudflare.com/profile/api-tokens
UCDP_ACCESS_TOKEN=<UCDP Token>          # UCDP에 메일 요청 (무료)
```

---

## Verification (전체 Phase)

### Phase 1 검증:
1. Worker 로그: `FIRMS 수집 완료: collected=N`, `IODA 수집 완료: collected=N`
2. `correlate_signals` 로그: `matched=N, unmatched=N`
3. Admin KScore 페이지: signal_corroboration_count > 0 클러스터 확인
4. `curl /signals/firms` → GeoJSON 응답
5. Pro 지도 → Intel → 열점 ON → WebGL heatmap + 펄스 애니메이션
6. Free → Intel → 토글 클릭 → PaywallModal
7. 지도 pan/zoom 60fps 유지

### Phase 2 검증:
8. Worker 로그: `Cloudflare Radar 수집 완료`, `GPS 교란 감지: N건`, `UCDP 수집 완료`
9. `curl /signals/gps-jam` → GeoJSON 응답
10. GPS 교란 레이어 ON → 시안 영역 + 점선 경계 + 파동 애니메이션
11. correlator 로그: cf_anomaly, gps_jam 매칭 확인
12. UCDP 이벤트가 normalized_events에 source_tier="A"로 저장 확인

### Phase 3 검증:
13. 이슈 상세 → "교차검증 증거" 섹션에 매칭된 시그널 표시
14. 이슈 상세 → "역사적 맥락" 섹션에 UCDP 데이터 표시
15. 지도에서 이슈 마커 호버 → 매칭 시그널과의 연결선(arc) 표시 + dash 애니메이션
16. Free 유저 → 분쟁 지역에서 넛지 배너 표시 → "Pro로 확인하기" 클릭 → upgrade 페이지
17. 새 RSS 9개 추가 후 5분 내 수집 시작 확인 (SIPRI, NK News, ISW 등)

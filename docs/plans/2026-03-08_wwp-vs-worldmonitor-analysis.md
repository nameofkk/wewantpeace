# WeWantPeace vs World Monitor — 코드 기반 교차 검증 분석 (v3 최종)

> 작성일: 2026-03-08
> 근거: 전체 코드 리뷰 + World Monitor 딥서칭
> 목적: 외부 분석가 문서의 오류 수정 + 실제 개선 로드맵 도출
> v3 반영: 분석가 2차 피드백 (공수 재평가, 명명 재고, 수렴 감지 정교화, 실행 순서 조정)

---

## Part 1: 분석가 문서 vs 실제 코드 — 오류 및 수정사항

### 1. KScore 공식 — 완전히 다름 (가장 큰 오류)

**분석가 문서:**
```
kscore = base_relevance × geographic_proximity × economic_linkage × security_factor
```
"한국 영향도"라고 설명. geographic_proximity(지리적 근접도), economic_linkage(경제 연관도) 등 한국 특화 팩터가 있다고 기술.

**실제 코드 (`worker/processor/trending_engine.py`):**
```
raw = 0.30 × velocity_norm + 0.10 × quality + 0.30 × severity_norm + 0.30 × spread
KScore = raw × 10 × decay
```
- `velocity_norm` = 이벤트 발생 속도 (`event_count^0.7`)
- `quality` = confidence + tier_bonus
- `severity_norm` = severity / 100
- `spread` = independent_sources / 12
- `decay` = `exp(-0.025 × age_hours)`, 최소 0.30

**핵심 문제:** KScore는 현재 **특정 국가와 아무 관련 없는 일반 트렌딩 점수**다. "Korea Impact Score"라는 이름만 있고, 실제로는 속도+품질+심각도+확산도의 가중합이다. 국가별 영향도를 측정하는 팩터(지리적 근접도, 무역량, 안보 팩터)가 코드에 **전혀 구현되어 있지 않다.**

**개선 방향:**
- "Korea Impact Score"가 아닌, **"Key Impact Score" — 사용자가 선택한 기준 국가(Home Country) 기반 영향도**로 재정의
- 기본값은 KR이되, JP/US/TW/DE 등 어떤 국가든 선택 가능
- 기존 raw trending score에 국가별 영향 팩터를 곱하는 구조
- 이름은 KScore 그대로 유지 (브랜딩 일관성), 의미만 확장

---

### 2. Tension Index 공식 — 가중치가 다름

**분석가 문서:** Severity 30%, Spread 30%, Recency 20%, Persistence 20%

**실제 코드 (`worker/processor/tension_calculator.py`):**
```
Raw Score = 0.55 × EventScore + 0.35 × ActivityScore + 0.10 × Spillover
```
- **EventScore (55%)**: `25 × log10(1 + normalized_total)` — severity × confidence × log2(1+event_count)의 합, 7일 이동 평균 기준선 대비 정규화
- **ActivityScore (35%)**: `100 × (0.6 × volume + 0.4 × acceleration)` — 이벤트 볼륨 + 클러스터 성장률
- **Spillover (10%)**: 이웃 국가 평균 severity의 70%

구조 자체가 다르다. 분석가의 4축(Severity/Spread/Recency/Persistence)이 아니라 **3축(Event/Activity/Spillover)**이며, **Spillover(인접국 영향)**는 분석가 문서에서 아예 언급되지 않았다.

---

### 3. 소스 수 및 구성 — 부정확

**분석가 문서:** "100+ RSS 소스 중심"

**실제 코드:**

| 소스 | 수량 | 주기 |
|------|------|------|
| RSS 피드 | 37+ | 5분 |
| Telegram OSINT | 12개 화이트리스트 채널 | 5분 |
| GDELT | 1개 API | 15분 |
| ACLED | 1개 API | 주간 배치 |
| ReliefWeb | 1개 API | 30분 |

총 **58개 활성 소스** (`calibration.py` ACTIVE_CHANNELS = 58). 100+가 아니다.

---

### 4. 소스 Tier 가중치 — 수치가 다름

**분석가 문서:** A: 1.0, B: 0.7, C: 0.4, D: 0.2

**실제 코드 (`normalizer.py`):**

| Tier | Confidence Base | Tier Bonus | 합계 |
|------|----------------|------------|------|
| A | 0.85 | +0.05 | 0.90 |
| B | 0.70 | +0.03 | 0.73 |
| C | 0.55 | +0.01 | 0.56 |
| D | 0.35 | +0.00 | 0.35 |

최대값 0.95로 캡.

---

### 5. 클러스터링 임계값 — 수치가 다름

**분석가 문서:** Jaccard ≥ 0.20 자동 머지, 0.10~0.20 AI 판단

**실제 코드 (`clusterer.py`):**
- 일반 이벤트: `MIN_TITLE_OVERLAP = 0.15` (15%)
- 고심각도 (severity ≥ 50): `MIN_TITLE_OVERLAP_HIGH_SEV = 0.08` (8%)
- AI 판단 구간: `0.10 ≤ sim < threshold`
- 0.10 미만: 항상 별도 클러스터

---

### 6. 갱신 주기 — 30분이 아님

**분석가 문서:** "30분마다 갱신"

**실제 코드 (Celery beat):**

| 작업 | 실제 주기 |
|------|----------|
| Tension 계산 | **5분** (+1분 offset) |
| Trending 계산 | **5분** (+2분 offset) |
| RSS 수집 | **5분** |
| Telegram 수집 | **5분** |
| GDELT 수집 | **15분** |

→ 핵심 지표는 **5분마다** 갱신. World Monitor보다 빈번하다.

---

### 7. 모니터링 국가 수 — 195개가 아님

**분석가 문서:** "195개국 점수화"

**실제 코드:** `MONITORED_COUNTRIES` 리스트에 **69개국** 포함. 45개 이웃 국가 쌍(`NEIGHBOR_MAP`)이 Spillover에 사용.

---

### 8. Spike 감지 조건 — 완전히 다름

**분석가 문서:** `(current_tension - baseline_tension) ≥ 15 AND severity_max ≥ 60`

**실제 코드 (`spike_detector.py`):**
```python
event_count >= 8
AND severity >= 40
AND independent_sources >= 3
AND cluster_age <= 48h
AND NOT in cooldown (critical severity≥90: 3h, normal: 6h)
```
**긴장도 기반이 아니라 클러스터 누적 기반**. tension rise가 아닌 개별 클러스터의 이벤트 수, 심각도, 독립 소스 수로 판단한다.

---

### 9. TimescaleDB — 사용하지 않음

**분석가 문서:** "TimescaleDB에 시계열로 쌓고 있어서 추세 분석이 가능"

**실제 코드:** Supabase의 **일반 PostgreSQL**. `tension_index` 테이블에 `(country_code, time)` 인덱스로 시계열 데이터를 저장하지만, TimescaleDB 확장(하이퍼테이블, 연속 집계, 압축)은 사용하지 않는다.

---

### 10. 알림 채널 — 분석가 주장 대비 실태

**분석가 문서:** "Spike Alert + Daily Movers + 푸시 알림 + 텔레그램 봇을 이미 구축 중"

**실제 코드:**

| 기능 | 상태 |
|------|------|
| Spike Alert (FCM push) | 구현 완료 |
| Verified Alert (FCM push) | 구현 완료 |
| In-app 알림 | 구현 완료 |
| Delivery Integrity (AlertDeliveryLog) | 구현 완료 |
| 일일 푸시 한도 (Free 3/Pro 10/Pro+ 50) | 구현 완료 |
| DND (방해금지) 시간 | 구현 완료 |
| SNS 자동 포스팅 (Daily/Spike/Weekly) | 구현 완료 |
| 이미지 카드 자동 생성 (card_generator.py) | 구현 완료 |
| **Telegram 알림 봇** | **존재하지 않음** |
| **Daily Movers** | **존재하지 않음** |

---

### 11. Verification (Verified vs Fast) — 부분적으로 다름

**분석가 문서:** "≥2 independent Tier A/B sources confirm" → Verified

**실제 코드:**
```python
is_verified = (confidence >= 0.70
    AND "A" in source_tiers   # Tier A만 필요 (B만으로는 불가)
    AND independent_sources >= 2)
```

---

### 12. 토픽 분류 — 11개 (9개 아님)

**분석가 문서:** 9개 (conflict, diplomacy, protest, terrorism, disaster, economy, military, cyber, other)

**실제 코드:** 11개
```
conflict, terror, coup, sanctions, cyber, protest, diplomacy, maritime, disaster, health, unknown
```
`economy`와 `military`가 없고, `coup`, `sanctions`, `maritime`, `health`이 추가.

---

### 13. Severity 할당 — AI + 키워드 하이브리드

**분석가 문서:** "GPT-4o-mini가 0-100 할당"

**실제 코드:** 맞지만 **폴백 로직**이 있다:
1. **GPT-4o-mini** (1차) → topic + severity
2. **키워드 규칙** (폴백): 토픽별 base severity + 키워드 보정(±40) + 사상자 보너스(+5~30)

| 토픽 | Base Severity |
|------|--------------|
| conflict | 75 |
| terror | 70 |
| disaster | 65 |
| coup | 60 |
| sanctions | 55 |
| health | 55 |
| cyber | 50 |
| maritime | 45 |
| protest | 40 |
| diplomacy | 30 |
| unknown | 25 |

---

### 14. 분석가가 "구현 필요"라고 했지만 이미 있는 것들

| 분석가 제안 | 실제 상태 |
|-----------|----------|
| 국가 페이지 choropleth 히트맵 (1주 공수) | **이미 구현** — `/tension/all` → GeoJSON 렌더링, 줌 레벨별 동적 투명도 |
| SNS 주간 데이터 카드 | **이미 구현** — `worker/social/` 자동 생성 (Daily/Spike/Weekly 3종) |
| Source reliability auto-scoring | **이미 구현** — `evaluate_source_reliability` 매주 일요일 자동 실행 |
| Severity outlier detection | **이미 구현** — `detect_severity_outliers` 매일 05:00 UTC 자동 실행 |
| Push notification pipeline | **이미 구현** — FCM + Delivery Log + 일일 한도 + DND 완비 |

---

### 15. 수익 모델 — 실제 구현

| | Free | Pro (₩4,900/월) | Pro+ (₩9,900/월) |
|--|------|-----------------|-------------------|
| 관심 국가 | 2개 | 5개 | 무제한 |
| 실시간 지도 | 잠김 | 열림 | 열림 |
| 속보 알림 | 잠김 | 열림 | 열림 |
| KScore(영향도) 필터 | 고정 3.0 | 3.0~10.0 | 1.5~10.0 |
| 긴장도 히스토리 | 7일 | 30일 | 90일 |
| 일일 푸시 한도 | 3회 | 10회 | 50회 |
| 7일 무료체험 | - | 가능 | 불가 |

Google Play Billing + iOS StoreKit 통합 완료.

---

## Part 2: World Monitor 딥서칭 결과 — 분석가 주장 검증

### 분석가 주장 vs 실제 조사 결과

| 항목 | 분석가 주장 | 실제 검증 |
|------|-----------|----------|
| CII 4축 | 맞음 | Baseline Risk 40% + Unrest 20% + Security 20% + Info Velocity 20% |
| 체제 유형별 차등 가중치 | 맞음 | 23개 tier-1 국가에 튜닝된 baseline, 나머지는 universal |
| Welford 기반선 이상탐지 | 맞음 | 90일 윈도우, 이벤트 유형/지역/요일/월별 streaming mean/variance |
| 수렴 감지 | 맞음 | 1°×1° 지리 셀, 24시간 윈도우, 3+ 이벤트 유형 수렴 시 경보 |
| 435+ RSS | **과장** | "100+ 실시간 스트림", "190 ranked sources" |
| 200만 유저 | 맞음 | 피크 21.6만 일일 방문자 |
| iOS 앱 3.6점/9리뷰 | 맞음 | App Store 확인 |
| 서버 DB 없음 | 맞음 | Redis(Upstash) + 클라이언트사이드 계산 |
| 14가지 신호 유형 | 맞음 | RSS, ACLED, OpenSky, AIS, USGS, Markets, Polymarket, Internet outages, Weather, Military vessels, Webcams, Conflict DB, Economic, Infrastructure |
| 오픈소스 | **부분적** | 프론트엔드+Edge Functions 공개. 60+ API 키 필요. `vercel dev` + 자체 API 키 없으면 대부분 패널 작동 안 함 |
| Pro 구독 | **없음** | 완전 무료. Elie Habib: "should not be monetized" |
| WIRED 기사 | **확인 불가** | SiliconCanals, L'Orient Le Jour, Sunday Guardian Live, kottke.org 보도 확인 |

### World Monitor 추가 발견사항

1. **Hotspot Escalation Score**: news(35%) + CII(25%) + geo-convergence(25%) + military(15%) + 48시간 trend regression
2. **데스크톱 앱**: Electron v2.5.23, SourceForge 배포
3. **LLM 폴백 체인**: Groq → OpenRouter → 브라우저 T5 (서버 없이도 요약 가능)
4. **브라우저 ML**: ONNX 모델로 임베딩/NER/감성분석을 Web Worker에서 실행 (데스크톱 전용)
5. **지역별 사용자**: 아시아 35%, 유럽 20%, 중동 18%, 미국 10%
6. **뉴스 클러스터링**: Jaccard + semantic similarity 하이브리드 (inverted index 최적화)
7. **위협 분류**: 키워드 120패턴 즉시 분류 + LLM 비동기 검증 이중 레이어

---

## Part 3: 수정된 비교 분석표

### 1. 서비스 정체성 (수정판)

| 축 | WeWantPeace | World Monitor |
|----|-------------|---------------|
| 한 줄 정의 | "당신에게 중요한 위험을 알려주는 개인화 경보기" | "세상을 들여다보는 감시실" |
| 핵심 경험 | 기준 국가 설정 → 맞춤 알림 → 확인 → 행동 | 지도 탐색하며 발견 |
| 사용 빈도 | 하루 1~3회 (알림 기반) | 접속 시 30분~1시간 몰입 |
| 타깃 | 여행자, 해외 거주자, 투자자, 글로벌 워커 (일반인) | OSINT 매니아, 분석가, 밀덕, 트레이더 |
| 수익 모델 | Free → Pro (₩4,900) → Pro+ (₩9,900) 구독 | 완전 무료 (비수익화 선언) |
| 스택 | Next.js 14 + FastAPI + Celery + Supabase PostgreSQL | Vanilla TS + Vercel Edge Functions 60+ + Redis (서버 DB 없음) |
| 갱신 주기 | **5분** (Tension/Trending/RSS/Telegram) | 실시간 스트리밍 (Edge Functions) |
| 모니터링 국가 | 69개국 (확대 예정) | 23개 tier-1 + universal |
| 데이터 소스 | 58개 (RSS 37+ / Telegram 12 / API 3) | 100+ 스트림, 190 ranked sources |

### 2. WeWantPeace가 실제로 앞서는 것

| 항목 | 설명 | 코드 근거 |
|------|------|----------|
| **시계열 긴장도 DB 저장** | PostgreSQL에 5분 간격으로 시계열 저장. 국가별 30일/90일 추이 분석 가능. World Monitor는 서버 DB가 없어 히스토리 조회 불가 | `tension_index` 테이블, `percentile_30d` 계산 |
| **개인화 알림 파이프라인** | FCM Spike/Verified 2종, 관심 국가별 필터, DND, 일일 한도, Delivery Integrity 추적. World Monitor의 가장 많이 요청되는 미구현 기능 | `push_service.py`, `AlertDeliveryLog` |
| **이벤트 클러스터링 + 이슈 추적** | Filtered Jaccard + AI 경계판단으로 동일 사건 묶어 시간순 추적 (43.6% 머지율). World Monitor는 뉴스를 뿌리지만 이슈 단위 추적 없음 | `clusterer.py` |
| **모바일 퍼스트** | PWA + Android TWA + iOS StoreKit, 바텀 네비게이션. World Monitor iOS 앱은 3.6점/9리뷰 | `next-pwa`, `platform-detect.ts` |
| **구독 수익 모델** | Free/Pro/Pro+ 3단계 + Google Play/StoreKit 통합. 지속가능한 비즈니스 구조 | `subscription.py` |
| **Spillover 분석** | 인접국 긴장도가 자국 점수에 10% 반영 (45개 국가 쌍) | `NEIGHBOR_MAP` |
| **커뮤니티** | 이슈별 토론/분석 게시글 | `community.py` |
| **SNS 자동 포스팅** | Daily/Spike/Weekly 3종 자동 생성 + 이미지 카드 | `worker/social/` |

### 3. World Monitor가 실제로 앞서는 것

| 항목 | 상세 |
|------|------|
| **시각적 임팩트** | DeckGL 3D 글로브 + 25+ 레이어 + WebGL. 스크린샷 한 장이 마케팅 |
| **알고리즘 정교함** | CII 4축 + 23개 국가 커스텀 baseline + Welford 이상탐지 90일 윈도우 + conflict-zone floor + 정부 여행경보 연동 |
| **수렴 감지** | 1°×1° 지리 셀, 3+ 이벤트 유형 교차 시 자동 경보 |
| **데이터 소스 다양성** | 100+ 스트림 (RSS + ACLED + GDELT + USGS + OpenSky + AIS + Polymarket + Cloudflare Radar + OREF). 우리보다 ~2배 다양 |
| **LLM 폴백 체인** | Groq → OpenRouter → 브라우저 T5 (오프라인 요약 가능) |
| **바이럴 성장** | 200만 유저, 미디어 보도 다수, GitHub 오픈소스 |
| **데스크톱 앱** | Electron v2.5.23 |

### 4. 따라가면 안 되는 것

| 항목 | 이유 |
|------|------|
| 3D 글로브 | MapLibre + choropleth 이미 충분. WebGL 성능 이슈 위험 |
| 군사 비행/선박 추적 | 여행자 타깃에 불필요. OpenSky/AIS 소스 비용 높음 |
| 45개 토글 레이어 | information overload. "패널 드래그하면 멈춘다" 비판. Progressive Disclosure 유지 |
| 서버 DB 없는 아키텍처 | 시계열 저장/개인화/알림에 불리. 우리의 PostgreSQL이 장기적으로 유리 |
| 완전 오픈소스 | 파이프라인 코드 보호 필수. 방법론+샘플만 공개 |
| 비수익 모델 | World Monitor는 비수익화 선언했지만, 우리는 구독으로 지속가능성 확보 |

---

## Part 4: 실제 코드 기반 개선 우선순위

### Tier 1 — 즉시 (반나절~1일)

#### 1. Conflict-Zone Floor 도입

**현재 상태:** 미구현. UA/SY/YE 같은 분쟁지역이 이벤트 없는 시간에 0점으로 떨어짐.

**필요 작업:** `tension_calculator.py`에 국가별 최저점 테이블 추가

```python
CONFLICT_FLOOR = {
    "UA": 55, "SY": 50, "YE": 45, "MM": 40,
    "SD": 40, "SO": 35, "AF": 35, "LY": 30,
    "IQ": 25, "ML": 25, "CF": 25, "CD": 25,
}
raw_score = max(raw_score, CONFLICT_FLOOR.get(country_code, 0))
```

**주의:** 하드코딩은 빠르게 구식이 된다. 1차는 하드코딩으로 시작하되, 중기적으로는 ACLED 주간 데이터에서 최근 90일 이벤트 밀도 기반으로 자동 산출하는 로직이 필요하다.

**공수:** 반나절
**영향:** World Monitor는 이미 구현. 데이터 신뢰도에 직결.

---

#### 2. 정보 접근성 보정 (Information Accessibility Adjustment)

**현재 상태:** 모든 국가에 동일한 severity 계산.

**필요 작업:** 국가별 modifier 도입. 단, "체제 유형 가중치"가 아니라 **"정보 접근성 보정"**으로 명명한다.

**근거:** 언론 자유도가 낮은 국가에서 보도된 사건은 실제보다 과소보고될 가능성이 높다. RSF Press Freedom Index 같은 외부 지표를 근거로 상향 보정하면 정치적 편향 논란 없이 설명 가능하다.

```python
# RSF Press Freedom Index 기반 (0=자유, 100=통제)
# 보정 공식: modifier = 1.0 + (press_freedom_score / 100) * 0.3
# 자유국 (score 20): 1.06, 통제국 (score 80): 1.24
INFORMATION_ACCESSIBILITY = {
    "KP": 1.27,  # RSF ~90
    "TM": 1.26,  # RSF ~87
    "ER": 1.25,  # RSF ~84
    "CN": 1.22,  # RSF ~75
    "IR": 1.22,  # RSF ~74
    "RU": 1.20,  # RSF ~66
    # 자유언론 국가: 보정 불필요
    "US": 1.0, "GB": 1.0, "JP": 1.0, "DE": 1.0, "FR": 1.0,
}
adjusted_severity = severity * INFORMATION_ACCESSIBILITY.get(country_code, 1.0)
```

**방법론 공개 시 프레이밍:** "We apply an Information Accessibility Adjustment based on RSF Press Freedom Index. Events from countries with restricted media access are adjusted upward to compensate for systematic under-reporting."

**공수:** 1일
**영향:** 알고리즘 정교화. 방법론 공개 시 외부 지표 근거가 있으므로 편향 논란 최소화.

---

### Tier 2 — KScore 재설계 + 핵심 차별화 (1~2주)

#### 3. KScore: 사용자 선택 국가 기반 영향도로 재설계

**현재 상태:** KScore는 일반 트렌딩 점수. 어떤 국가와도 무관.

**개선 방향:**
- "Korea Impact Score" → "Key Impact Score"로 의미 재정의 (이름은 그대로)
- 사용자가 "기준 국가(Home Country)"를 설정
- 기존 raw trending score에 **국가별 영향 팩터**를 곱하는 구조

**실행 난이도 재평가:**
69개국(확대 시 120개국) × 69개국의 지리적/안보/경제 관계 테이블이 필요하다. 수작업으로 다 채우는 건 비현실적이다. **2단계로 분리한다.**

##### Phase 1 (1~2주): KR 기준 69개국 팩터 수작업

```python
# KR 기준 팩터만 먼저 수작업으로 정의
KR_IMPACT_FACTORS = {
    "KP": {"geo": 1.0, "sec": 1.0, "eco": 0.1},  # 안보 직결
    "JP": {"geo": 0.9, "sec": 0.6, "eco": 0.8},  # 이웃 + 주요 교역
    "CN": {"geo": 0.8, "sec": 0.5, "eco": 0.9},  # 최대 교역국
    "US": {"geo": 0.3, "sec": 0.8, "eco": 0.7},  # 동맹 + 주요 교역
    "RU": {"geo": 0.5, "sec": 0.5, "eco": 0.4},  # 에너지 + 인접
    "TW": {"geo": 0.6, "sec": 0.6, "eco": 0.7},  # 반도체 공급망
    "IR": {"geo": 0.2, "sec": 0.3, "eco": 0.5},  # 에너지 수입
    "UA": {"geo": 0.2, "sec": 0.3, "eco": 0.3},  # 간접 영향
    # ... 69개국 전체
}
```

- 서버: `/trending/global` 응답에 `raw_score` 필드 추가
- 프론트: `homeCountry` 설정 UI + 클라이언트에서 `raw_score × impact_factor` 계산
- 백엔드: `User.home_country` 필드 추가 (기본값 "KR")
- 기존 유저 영향 없음 (KR 기준 팩터가 적용되므로 기존 KScore와 유사한 결과)

##### Phase 2 (추가 1~2주): 다국가 팩터 자동 생성

- **CEPII 무역 거리 DB** → `economic_linkage` 자동 산출
- **지리적 거리 (국가 중심 좌표 간 거리)** → `geographic_proximity` 자동 산출
- **동맹 조약 DB (ATOP) + SIPRI 무기 수출** → `security_relevance` 자동 산출
- 스크립트로 120×120 매트릭스 생성 → JSON 번들

```python
# Phase 2: 자동 생성 스크립트
def generate_impact_matrix():
    for home in ALL_COUNTRIES:
        for event in ALL_COUNTRIES:
            geo = 1.0 - min(1.0, haversine(home, event) / MAX_DISTANCE)
            eco = trade_volume(home, event) / max_trade_volume(home)
            sec = alliance_score(home, event)  # ATOP DB 기반
            yield (home, event, {"geo": geo, "sec": sec, "eco": eco})
```

**토픽별 가중치 보정:**
```python
TOPIC_WEIGHTS = {
    "conflict":   {"geo": 0.35, "sec": 0.45, "eco": 0.20},
    "sanctions":  {"geo": 0.20, "sec": 0.25, "eco": 0.55},
    "diplomacy":  {"geo": 0.30, "sec": 0.40, "eco": 0.30},
    "disaster":   {"geo": 0.60, "sec": 0.10, "eco": 0.30},
    "terror":     {"geo": 0.40, "sec": 0.40, "eco": 0.20},
    "cyber":      {"geo": 0.20, "sec": 0.30, "eco": 0.50},
    "protest":    {"geo": 0.40, "sec": 0.30, "eco": 0.30},
    "coup":       {"geo": 0.30, "sec": 0.50, "eco": 0.20},
    "maritime":   {"geo": 0.40, "sec": 0.30, "eco": 0.30},
    "health":     {"geo": 0.50, "sec": 0.10, "eco": 0.40},
}
```

**계산 아키텍처: Option B (클라이언트 계산)**
- 서버: raw_score + event_country만 제공
- 프론트: 사용자의 home_country 기준으로 impact_factor를 곱함
- 팩터 테이블: JSON으로 프론트에 번들 (~50KB)
- 장점: 서버 부하 없음, 국가 변경 시 즉시 반영

**공수:** Phase 1: 1~2주 / Phase 2: 추가 1~2주
**영향:** 서비스의 핵심 차별화. "어떤 나라 사람이든 자기에게 중요한 위험을 점수로 본다."

---

#### 4. 정부 여행경보 RSS 수집 → 긴장도 보정

**현재 상태:** 미구현
**필요 작업:**
- 한국 외교부, US State Dept, UK FCDO 여행경보 RSS 수집기 추가
- `normalizer.py`에 `travel_advisory` 토픽 추가
- Tension에 travel advisory level을 가중치로 반영

**공수:** 2~3일
**영향:** 여행자 타깃 핵심. 공식 판단 반영 → 신뢰도 급상승.

---

#### 5. Spike Alert에 "왜 중요한지" 설명 추가

**현재 상태:** 알림 body에 제목+심각도만.

**필요 작업:** context 1줄 추가
- "이란: 핵시설 공습 (severity 92, 18개 독립 소스 확인)"
- KScore가 높은 이유도: "기준 국가(한국) 에너지 수입 의존도 높은 국가"

**공수:** 1일

---

### Tier 3 — 2~4주 (중기 개선)

#### 6. 수렴 감지 로직 (Multi-Signal Convergence)

**현재 상태:** 단일 이벤트 severity 기반. 교차 분석 없음.

**필요 작업:** 같은 국가에서 24시간 내 3+ 다른 topic 클러스터가 동시 활성화되면 수렴 보너스를 부여한다. 단, **콤보 유형에 따라 의미가 다르므로 구분이 필요하다.**

```python
# 정치/군사 수렴 — 의도적 위기 신호 (높은 가중치)
POLITICAL_MILITARY = {"conflict", "coup", "protest", "sanctions", "terror", "cyber"}

# 자연재해 수렴 — 복합 재난 (중간 가중치, 의도성 없음)
NATURAL_DISASTER = {"disaster", "health"}

def calc_convergence_bonus(active_topics: set[str]) -> float:
    pol_mil = active_topics & POLITICAL_MILITARY
    nat_dis = active_topics & NATURAL_DISASTER

    if len(pol_mil) >= 3:
        # 정치/군사 3+ 수렴: 높은 위기 신호
        return min(25, len(pol_mil) * 7)
    elif len(pol_mil) >= 2 and len(nat_dis) >= 1:
        # 혼합 수렴: 재난 + 정치 불안 (중간)
        return min(15, (len(pol_mil) + len(nat_dis)) * 4)
    elif len(active_topics) >= 3 and len(pol_mil) < 2:
        # 자연재해 중심 복합: 낮은 보너스
        return min(10, len(active_topics) * 3)
    return 0
```

**예시:**
- `{conflict, protest, sanctions}` → 정치/군사 수렴 → +21 (높은 위기)
- `{conflict, disaster, health}` → 혼합 수렴 → +12 (복합 재난)
- `{disaster, health, maritime}` → 자연재해 중심 → +9 (복합이지만 의도적 위기 아님)

**공수:** 1~2주
**영향:** World Monitor 핵심 기능. 콤보 유형 구분으로 오탐률 최소화.

---

#### 7. 모니터링 국가 확대

**현재 상태:** 69개국
**목표:** 최소 120개국
**필요:** `COUNTRY_CENTERS` + `NEIGHBOR_MAP` 확장

**공수:** 1~2일 (코드 변경 적음, 데이터 검증 필요)

---

#### 8. 데이터 소스 확대

| 추가 소스 | 용도 | 공수 |
|----------|------|------|
| Cloudflare Radar 인터넷 장애 | 위기 선행지표 (인터넷 차단 = 탄압/분쟁 신호) | 2~3일 |
| USGS 지진 데이터 | 자연재해 감지 | 2일 |
| ACLED 주기 변경 (주간→일간) | 분쟁 데이터 최신성 | 1일 |

---

#### 9. 공개 API (읽기 전용)

**필요 작업:**
- `GET /public/tension/{country_code}?range=30d`
- `GET /public/weekly-summary`
- Rate limit: IP당 60req/min
- OpenAPI 문서

**공수:** 1주
**전제조건:** conflict-zone floor + 데이터 안정화 완료 후

---

#### 10. Welford 기반선 이상탐지

**현재 상태:** 14일 percentile만 사용.

**필요 작업:**
- 90일 rolling window, 국가별/토픽별 streaming mean/variance
- z-score > 2.0이면 이상탐지 경보
- 데이터 3개월 축적 후 활성화

**공수:** 2주

---

## Part 5: 산출물(README/METHODOLOGY 등) 수정 목록

| 산출물 | 오류 | 수정 |
|--------|------|------|
| METHODOLOGY — Tension Index | "Severity 30%, Spread 30%, Recency 20%, Persistence 20%" | EventScore 55%, ActivityScore 35%, Spillover 10% |
| METHODOLOGY — KScore | "base_relevance × geographic_proximity × …" | 현재는 velocity+quality+severity+spread. KScore 구현 후 국가별 영향 팩터 문서화 |
| METHODOLOGY — Source Tiers | "A: 1.0, B: 0.7, C: 0.4, D: 0.2" | A: 0.85+0.05, B: 0.70+0.03, C: 0.55+0.01, D: 0.35 |
| README — Countries | "195 countries scored" | 69개국 (120+ 확대 예정) |
| README — Update frequency | "Every 30 minutes" | **5분** |
| README — KScore | "Korea impact score" | **KScore = Key Impact Score (사용자 선택 기준 국가 기반 영향도)** |
| METHODOLOGY — Clustering | "Jaccard ≥ 0.20" | 0.15 (일반), 0.08 (고심각도) |
| METHODOLOGY — Spike | "tension rise ≥ 15" | event_count ≥ 8 AND severity ≥ 40 AND independent_sources ≥ 3 |
| METHODOLOGY — Topics | 9개 | 11개 (coup, sanctions, maritime, health 추가) |
| METHODOLOGY — Verification | "≥2 Tier A/B sources" | confidence ≥ 0.70 AND Tier A present AND sources ≥ 2 |
| DATA_DICTIONARY — kscore | "Korea impact score" | KScore = Key Impact Score (user-selected home country relevance) |

---

## Part 6: 최종 실행 로드맵

> 분석가 2차 피드백 반영: METHODOLOGY.md를 최우선으로 배치. 코드 변경 전에 "현재 버전"과 "계획 중인 변경"을 분리하여 방법론부터 정리.

| 단계 | 작업 | 공수 | 전제조건 | 비고 |
|------|------|------|----------|------|
| **0 (즉시)** | METHODOLOGY.md + README.md 코드 기준 재작성 | 1일 | 없음 | 코드 변경 불필요. "현재 버전" vs "계획 중인 변경" 분리 기술. B-launch 전제조건 |
| **1주차** | Conflict-zone floor 도입 | 0.5일 | METHODOLOGY 완료 | 1차 하드코딩, 중기 ACLED 자동산출 |
| | 정보 접근성 보정 (Information Accessibility Adjustment) | 1일 | METHODOLOGY 완료 | RSF Press Freedom Index 근거 |
| **2주차** | KScore Phase 1 — KR 기준 69개국 팩터 수작업 | 1~2주 | Tier 1 완료 | home_country UI + 클라이언트 계산 |
| | 정부 여행경보 RSS 수집 | 2~3일 | 병렬 가능 | 외교부/State Dept/FCDO |
| | Spike Alert "왜 중요한지" 설명 추가 | 1일 | KScore Phase 1과 병렬 | context 1줄 추가 |
| **3~4주차** | 수렴 감지 로직 v1 (콤보 유형 구분 포함) | 1~2주 | Tier 1 완료 | 정치/군사 vs 자연재해 콤보 구분 |
| | 모니터링 국가 69→120+ 확대 | 1~2일 | COUNTRY_CENTERS 데이터 검증 | 수렴 감지와 병렬 |
| **5~6주차** | KScore Phase 2 — 다국가 팩터 자동 생성 | 1~2주 | Phase 1 검증 후 | CEPII/SIPRI/ATOP 기반 120×120 매트릭스 |
| | 공개 API + OpenAPI 문서 | 1주 | conflict-floor + 데이터 안정화 | 읽기 전용 엔드포인트 |
| **B-launch** | METHODOLOGY.md 수정본 GitHub 공개 | 1일 | 위 전체 완료 | 방법론 투명성 → 신뢰 구축 |

---

## 결론

분석가의 전략적 방향(알림 중심 서비스, 시계열 추적, 이슈 클러스터링)은 정확하다.

핵심 수정 4가지:

1. **METHODOLOGY.md 먼저.** 코드를 건드리기 전에 "현재 버전"과 "계획 중인 변경"을 분리하여 방법론 문서를 정리한다. B-launch의 전제조건이다.

2. **알고리즘 기반부터 다진다.** Conflict-zone floor + 정보 접근성 보정(RSF 근거)을 먼저 구현한다. 이것이 없으면 KScore가 아무리 정교해도 입력 데이터의 신뢰도가 떨어진다.

3. **KScore를 "Key Impact Score"로 재정의한다.** 2단계로: Phase 1(KR 기준 수작업)으로 빠르게 출시하고, Phase 2(CEPII/SIPRI/ATOP 기반 자동 생성)로 120개국 매트릭스를 확장한다. "한국 사용자를 위한 니치 서비스"가 아니라 "모든 나라 사람에게 개인화된 위험 점수를 제공하는 글로벌 서비스"가 된다.

4. **수렴 감지에서 콤보 유형을 구분한다.** `{conflict, protest, sanctions}` (정치/군사 수렴)과 `{disaster, health, conflict}` (복합 재난)은 다른 의미다. 단순 토픽 3개 이상 카운트로는 오탐이 많다.

실행 순서:
- **METHODOLOGY.md (즉시)** → Conflict-floor + 정보 접근성 (1주차) → KScore Phase 1 + 여행경보 (2주차) → 수렴 감지 + 국가 확대 (3~4주차) → KScore Phase 2 + 공개 API (5~6주차) → B-launch

KScore 재설계가 완료되면, 서비스의 한 줄 정의가 바뀐다:
- **Before:** "한국인을 위한 세계 위험 모니터링"
- **After:** "당신의 나라에 중요한 위험을 KScore로 알려주는 서비스"

이것이 World Monitor와의 가장 선명한 차별점이 된다. World Monitor는 "세상을 보여주는 도구"이고, WeWantPeace는 **"당신에게 중요한 것을 걸러주는 도구"**다.

# WeWantPeace — 핵심 컨텍스트

> 마지막 업데이트: 2026-03-08

---

## 서비스 현황

| 항목 | 상태 |
|------|------|
| **웹 (PWA)** | wewantpeace.live — **LIVE** |
| **Android** | Google Play **비공개 테스트** 중 |
| **iOS** | App Store 미제출 |
| **구독 결제** | 런칭 후 — 현재 수익 $0 |
| **이메일** | `krshin7@gmail.com` (커스텀 도메인 보류) |
| **배포** | Railway.app (GitHub Actions CI/CD) |
| **LICENSE** | CC BY-NC 4.0 |

---

## 핵심 개념 구분

### 기준 국가 (home_country) vs 관심 국가 (watched countries)

| | 기준 국가 | 관심 국가 |
|---|----------|----------|
| **목적** | KScore 개인화 기준점 | 알림 수신 대상 |
| **테이블** | `user_preferences.home_country` | `user_areas` (area_type="country") |
| **값** | 단일 문자열 (ISO 2자 or "" for BASIC) | 복수 레코드 |
| **API** | `PATCH /me/preferences` → `home_country` | `POST/DELETE /me/areas` |
| **Free** | BASIC("") + KR (고정, 변경 불가) | 2개 제한 |
| **Pro** | BASIC + 10개국 자유 변경 | 5개 제한 |
| **Pro+** | BASIC + 10개국 자유 변경 | 무제한 |
| **Store 필드** | `homeCountry` (Zustand) | `myCountries` (Zustand) |

### KScore 개인화 공식

```
personalizedKScore = rawKScore × calcImpactFactor(eventCountry, topic, homeCountry)

homeCountry="" (BASIC): factor = 1.0 (raw KScore 그대로)
homeCountry 매핑 없음: factor = 0.5 (DEFAULT_FACTOR)
homeCountry 매핑 있음: factor = geo_weight*geo + sec_weight*sec + eco_weight*eco
```

SUPPORTED_HOME_COUNTRIES: KR, US, JP, CN, TW, DE, GB, AU, IN, BR (10개국)
데이터 소스: `frontend/lib/impact-factors.generated.json` (scripts/sync_impact_factors.py로 동기화)

### Tension Index 공식

```
raw_score = 0.55*EventScore + 0.35*ActivityScore + 0.10*Spillover
+ convergence_bonus (최대 +25, 3개 이상 토픽 동시 활성화 시)
+ anomaly_z (Welford 90일 기반선 대비, z>2.5 시 보너스)
```

convergence_bonus와 anomaly_z는 DB(tension_index 테이블)에 저장되며 API 응답에 포함됨.

### KScore 공식 (서버 계산)

```
raw = 0.30*velocity + 0.10*quality + 0.30*severity + 0.30*spread
KScore = raw × 10 × decay (0~10 스케일)
```

---

## 수집 소스

| 소스 | 주기 | 비고 |
|------|------|------|
| RSS (58개 피드) | 5분 | feedparser |
| Telegram (18개 채널) | 5분 | Telethon |
| GDELT | 15분 | |
| ReliefWeb | 30분 | |
| USGS 지진 | 5분 | M5.0+ |
| ACLED 분쟁 | 일간 06:30 UTC | **환경변수 필요 (아래 참고)** |
| US Travel Advisory | 6시간 | Level 2+ |

---

## 주요 기술 결정

- **DB**: PostgreSQL (Supabase), TimescaleDB 미사용
- **AI 분류**: GPT-4o-mini (이벤트 정규화 + 클러스터 매칭)
- **KScore 개인화**: 클라이언트 계산 (impact-factors.ts ← generated JSON)
- **Tension Index**: 서버 계산 (tension_calculator.py, 5분 주기)
- **수렴 감지**: convergence_detector.py (정치/군사 vs 자연재해 구분) — 구현 완료, DB 저장됨
- **이상 감지**: anomaly_detector.py (Welford 온라인 알고리즘) — 구현 완료, Redis 누적 + DB 저장
- **SNS 포스팅**: X, Threads, Instagram, LinkedIn, Telegram (5개 플랫폼 어댑터 구현 완료)
- **에러 코드**: 백엔드 HTTPException은 `{"code": "ERROR_CODE"}` 형식으로 통일

---

## 공개 API (인증 불필요)

| 엔드포인트 | 설명 | Rate Limit |
|-----------|------|-----------|
| `GET /public/weekly-summary` | 주간 요약 (Top 10 이슈 + 긴장도) | 60/분 |
| `GET /public/tension/all` | 전체 국가 긴장도 | 60/분 |
| `GET /public/tension/{cc}` | 개별 국가 긴장도 + 30일 히스토리 | 60/분 |
| `GET /public/trending/top` | 상위 20개 트렌딩 | 60/분 |

---

## 플랜별 기능

| 기능 | Free | Pro (₩4,900) | Pro+ (₩9,900) |
|------|------|-------------|---------------|
| 관심국가 | 2개 | 5개 | 무제한 |
| 기준국가 | BASIC + KR | BASIC + 10개국 | BASIC + 10개국 |
| 이슈 지도 | 잠금 (paywall) | 실시간 | 실시간 |
| KScore 필터 | 5.0+ 고정 | 3.0~10.0 조절 | 1.5~10.0 조절 |
| 긴장도 히스토리 | 7일 | 30일 | 90일 |
| 속보 알림 | 확인된 이슈만 | 미확인 포함 | 미확인 포함 |
| 토픽 필터 | 불가 | 가능 | 가능 |
| 방해금지 시간 | 불가 | 가능 | 가능 |
| 일일 푸시 상한 | 3회 | 10회 | 50회 |

---

## B-Launch 우선순위

1. ~~LICENSE 파일 생성~~ ✅ CC BY-NC 4.0 완료
2. **GitHub 공개 저장소** (wewantpeace-methodology) — METHODOLOGY.md + DATA_DICTIONARY.md 준비됨
3. **4주 샘플 JSON** — 프로덕션 데이터 축적 후
4. **백테스트 케이스 스터디** — 코로플레스 맵 시간대별 스크린샷 + README GIF
5. **Reddit/HN/ProductHunt** 포스팅
6. **Disquiet/클리앙** 한국 커뮤니티

---

## Railway 환경

- **프로젝트 ID**: `8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed`
- **서비스 ID**: backend=`81e6a83e`, worker=`2ee51089`, frontend=`aefe12db`
- **배포**: GitHub Actions → Railway GraphQL API 직접 호출

### 필요한 환경변수 (미설정)

| 변수 | 용도 | 상태 |
|------|------|------|
| `ACLED_EMAIL` | ACLED 분쟁 데이터 수집 OAuth | **미설정** — ACLED 가입 필요 |
| `ACLED_PASSWORD` | ACLED OAuth 인증 | **미설정** |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn 포스팅 | **미설정** — OAuth2 설정 필요 |
| `TELEGRAM_CHANNEL_ID` | Telegram 채널 브로드캐스트 | **미설정** — 채널 생성 필요 |

---

## 미구현/보류 항목 (2026-03-08 기준)

### 보류 (당분간 불필요)

| 항목 | 이유 |
|------|------|
| OG 이미지 (opengraph-image.tsx) | 트래픽 없음, 보류 |
| 프론트 upgrade-prompt UI (Spike 3회 후 팝업) | 유저 0명, 보류 |
| Cloudflare Radar 수집기 | API 접근 제한 + 가치 대비 비용 높음 |
| OpenAPI 문서 자동 생성 | 공개 API 4개만, 우선순위 낮음 |
| 소스 자동 평가 (Tier 승격/강등) | Phase 3, 교차 확인 데이터 부족 |
| 한국 외교부/UK FCDO 여행경보 | US만으로 충분 |

### 데이터 축적 대기

| 항목 | 조건 |
|------|------|
| 이상 감지(anomaly_z) 실효성 | 90일(2160샘플) 축적 필요 — Welford MIN_SAMPLES=2160 |
| KScore Phase 2 (120x120 자동 생성) | UN Comtrade 경제 데이터 연동 복잡, 10개국 수작업 충분 |
| 백테스트 케이스 스터디 | 프로덕션 데이터 4주 이상 축적 필요 |

### 사용자 액션 대기

| 항목 | 필요 액션 |
|------|----------|
| ACLED 데이터 수집 | https://acleddata.com 가입 → ACLED_EMAIL/PASSWORD 환경변수 설정 |
| LinkedIn 포스팅 | LinkedIn Company Page + OAuth2 앱 등록 |
| Telegram 브로드캐스트 | 공개 채널 생성 + 봇 관리자 추가 |
| B-Launch 실행 | wewantpeace-methodology 저장소 공개 + 커뮤니티 포스팅 |
| App Store 등록 | iOS 빌드 + App Store 제출 → upgrade 페이지 URL 업데이트 |

---

## Phase 완료 현황

### Phase 1 ✅ (2026-03-07)
- KScore 개인화 (10개국 IMPACT_FACTORS)
- Conflict Floor (17개 분쟁지역)
- 200개국 확대 (129개국 활성)

### Phase 2 ✅ (2026-03-08)
- USGS 지진 수집기, US Travel Advisory 수집기
- KScore sync (impact-factors.generated.json)
- 공개 API 4개 엔드포인트
- 소셜 어댑터 5개 (X, Threads, Instagram, LinkedIn, Telegram)
- convergence/anomaly → DB 저장 + API 응답 통합
- 에러 메시지 code 기반 통일
- PaywallModal i18n 통합
- LICENSE (CC BY-NC 4.0)

### Phase 3 (다음)
- B-Launch 실행
- 알림 개인화 (KScore ≥ 6 + home_country 연관)
- 수익 최적화 (Spike 3회 후 Pro 전환 유도)
- 소스 자동 평가

---

*Last updated: 2026-03-08*

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

### Tension Index 공식

```
raw_score = 0.55*EventScore + 0.35*ActivityScore + 0.10*Spillover
+ convergence_bonus (최대 +25, 3개 이상 토픽 동시 활성화 시)
+ anomaly_z (Welford 90일 기반선 대비, z>2.5 시 보너스)
```

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
| ACLED 분쟁 | 일간 06:30 UTC | |
| US Travel Advisory | 6시간 | Level 2+ |

---

## 주요 기술 결정

- **DB**: PostgreSQL (Supabase), TimescaleDB 미사용
- **AI 분류**: GPT-4o-mini (이벤트 정규화 + 클러스터 매칭)
- **KScore 개인화**: 클라이언트 계산 (impact-factors.ts)
- **Tension Index**: 서버 계산 (tension_calculator.py, 5분 주기)
- **수렴 감지**: convergence_detector.py (정치/군사 vs 자연재해 구분)
- **이상 감지**: anomaly_detector.py (Welford 온라인 알고리즘, 90일 축적 중)
- **SNS 포스팅**: X, Threads, Instagram, LinkedIn, Telegram (Telegram 봇 승인 후 게시)

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

1. **LICENSE 파일 생성** (CC BY-NC 4.0)
2. **GitHub 공개 저장소** (wewantpeace-methodology) — METHODOLOGY.md + DATA_DICTIONARY.md 준비됨
3. **4주 샘플 JSON** — 프로덕션 데이터 축적 후
4. **Reddit/HN/ProductHunt** 포스팅
5. **Disquiet/클리앙** 한국 커뮤니티

---

## Railway 환경

- **프로젝트 ID**: `8c67cb03-6ad1-40ef-8cfc-47bf2954a1ed`
- **서비스 ID**: backend=`81e6a83e`, worker=`2ee51089`, frontend=`aefe12db`
- **배포**: GitHub Actions → Railway GraphQL API 직접 호출

---

## 미구현/보류 항목 (2026-03-08 기준)

| 항목 | 상태 | 판단 |
|------|------|------|
| OG 이미지 (opengraph-image.tsx) | 미구현 | 보류 |
| 프론트 upgrade-prompt UI | 미구현 | 보류 (유저 0) |
| KScore Phase 2 (120x120 자동 생성) | 미구현 | Phase 1 검증 후 |
| 한국 외교부/UK FCDO 여행경보 | 미구현 | US만으로 충분 |
| Cloudflare Radar | 미구현 | 보류 |
| 에러 메시지 code 통일 | 미확인 | 보류 |
| OpenAPI 문서 | 미확인 | 보류 |

---

*Last updated by automated analysis session, 2026-03-08.*

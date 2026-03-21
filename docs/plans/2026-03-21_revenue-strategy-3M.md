# WeWantPeace 월 300만원 수익 달성 전략 — 경쟁사 분석 기반 최종판

> 작성: 2026-03-21 | 현재 가격: Pro $3.90/월, Pro+ $6.90/월 (USD, DodoPayments)
> 목표: 월 ₩3,000,000 (≈$2,100) MRR
> **이전 버전 대비 변경점**: 경쟁사 실패/성공 사례를 분석하여 전략 전면 재구성

---

## Part 0. 경쟁사 분석 — 왜 실패했고, 왜 성공했는가

### 0.1 실패한 경쟁사 5곳 — 우리가 피해야 할 함정

#### 1) EQLIM (2019~2022, 사망)
- **투자**: $425,000 (3년)
- **실패 원인**:
  - **타겟이 너무 넓었음**: "세계 모든 분쟁을 모든 사람에게" → 아무도 돈 안 냄
  - **비기술 CEO**: 제품 개발 속도가 느려 시장 변화를 못 따라감
  - **Enterprise 세일즈 사이클 과소평가**: B2B 계약 하나에 6~12개월 → 그동안 현금 바닥
  - **IHS Markit/EIU 같은 기존 강자와 정면 승부**: 가격으로 이기려 했지만 신뢰도에서 짐
- **➜ WeWantPeace 개선점**:
  - 타겟을 좁혀라: "OSINT 커뮤니티 + 해외 주재원 안전 관리자"부터 시작
  - 1인 개발자가 강점: 기술 CEO = 빠른 제품 이터레이션
  - Enterprise 세일즈에 올인하지 말 것 → 커뮤니티에서 유기적으로 Enterprise가 찾아오게
  - 기존 강자와 정면 비교보다 "카테고리 창조"

#### 2) PeaceTech Lab (2008~2024, 해산)
- **최대 매출**: $4,350,000/년 (2016, IRS 990 기준)
- **최종**: $19,000 → 해산 (2024)
- **실패 원인**:
  - **100% 보조금 의존**: 자체 수익 $0 — 보조금 끊기면 즉사
  - **제품 없음**: "평화 기술" 교육/연구만 함, 유료로 팔 수 있는 제품이 없었음
  - ACLED는 비슷한 비영리지만 Program Services가 전체 수입의 29% → 최소한의 자체 매출 확보
- **➜ WeWantPeace 개선점**:
  - **절대 보조금/투자에 의존하지 말 것** — 자체 매출로 생존하는 구조 먼저
  - 매출 $0인 채로 3년 이상 운영하지 말 것 (PeaceTech의 패턴)
  - 제품이 있어야 한다 — 우리는 이미 있음 (이건 가장 큰 강점)

#### 3) CrisisNET (2014~2016, 사망)
- **투자**: Ushahidi 내부 프로젝트
- **실패 원인**:
  - **API만 있고 최종 사용자 제품 없음**: 개발자만 쓸 수 있음 → 시장이 너무 좁음
  - **수익 모델 없음**: 모든 것이 무료 → 지속 불가능
  - **모회사(Ushahidi)가 우선순위 변경**: 핵심 인력 이탈
- **➜ WeWantPeace 개선점**:
  - API와 최종 사용자 제품(웹/앱) 둘 다 가져야 함 — 우리는 이미 둘 다 있음
  - API에만 의존하지 말 것: API는 보조 매출, 주 매출은 구독
  - 수익 모델 없는 "무료 프로젝트"로 방치하지 말 것

#### 4) GeoQuant (2016~2022, Fitch에 인수됨)
- **투자**: $8,500,000
- **실패 원인**:
  - **헤지펀드만 타겟**: 시장이 너무 좁음 (전세계 지정학 리스크에 돈 쓰는 헤지펀드는 소수)
  - **전략적 투자자 함정**: Fitch가 투자자 겸 인수자 → 독립 성장 기회 상실
  - **커뮤니티 없음**: 유저와의 관계가 계약서뿐
- **➜ WeWantPeace 개선점**:
  - 특정 고객 유형에만 의존하지 말 것 → B2C + B2B 혼합
  - 전략적 투자 받을 때 인수 조건 주의 (현재는 해당 없지만 미래 참고)
  - 커뮤니티가 없으면 제품이 죽어도 아무도 모른다

#### 5) Predata (2014~2023, FiscalNote에 인수됨)
- **투자**: $14,300,000
- **실패 원인**:
  - **PMF(Product-Market Fit) 미달성**: 9년간 "누구에게 파는 건가"를 못 정함
  - **Enterprise-only**: B2C 없음 → 파이프라인 마르면 죽음
  - **$14.3M 태워도 독립 생존 불가** → 결국 FiscalNote에 흡수
- **➜ WeWantPeace 개선점**:
  - PMF를 빠르게 찾아야 함: "누가 우리한테 돈을 내고 있는가?"를 3개월 내 검증
  - Enterprise-only 전략 금지 → B2C 커뮤니티가 있어야 Enterprise가 찾아옴
  - 돈을 많이 태우는 것 ≠ 성공 — 린하게 운영하는 게 1인 개발자의 무기

---

### 0.2 성공한 경쟁사 5곳 — 우리가 배워야 할 것

#### 1) LiveUAMap — B2C 분쟁 모니터링 유일한 성공 사례
- **시작**: 2014년, 우크라이나 개발자 2명, 초기 자금 $10,000
- **현재**: $4,500,000~5,000,000/년, 월 방문 800M~900M
- **성공 공식**:
  1. **무료 시각 제품**: 지도에 핀만 찍었는데, 전쟁 나니까 사람들이 몰려옴
  2. **위기 = 성장 엔진**: 2022 우크라이나 전쟁 때 트래픽 폭발 → 그게 유지됨
  3. **광고 매출이 주력**: 구독 아닌 광고가 주 매출 (트래픽이 많으니까)
  4. **유료 전환 계단**: Free → 광고 수익 → PRO ($1.99/월) → API ($1,000/월)
  5. **10년 걸림**: 2014~2024, 느리지만 꾸준히
- **➜ WeWantPeace가 배울 점**:
  - **무료 제품이 충분히 매력적이어야 트래픽이 온다** — 무료를 너무 제한하면 트래픽 자체가 안 옴
  - **위기 이벤트에 즉시 반응하는 SNS 전략**: 전쟁/분쟁 터지면 1시간 내 데이터 공유
  - **광고 매출을 무시하지 말 것**: 트래픽이 오면 Google AdSense만으로도 상당한 수익
  - **10년 계획을 세우되, 1년 안에 첫 $100 벌기**: LiveUAMap도 첫 2년은 거의 $0

#### 2) Shodan — 1인 개발자 → $5~25M 매출, 5명 운영
- **시작**: 2009년, John Matherly 혼자 개발, $0 투자
- **현재**: $5,000,000~25,000,000/년 (추정), 직원 5명
- **성공 공식**:
  1. **카테고리 창조**: "인터넷에 연결된 디바이스 검색 엔진" — 아무도 안 하던 것
  2. **$49 원타임 진입장벽**: 신용카드만 있으면 누구나 시작 → 500만 유저 확보
  3. **유저가 오면 Enterprise는 따라옴**: Fortune 100 기업이 Shodan을 찾아옴 (역방향 세일즈)
  4. **5명으로 운영**: 인건비 최소화 = 이익률 극대화
  5. **Freemium → One-time → Monthly → Enterprise**: 단계별 업그레이드
- **➜ WeWantPeace가 배울 점**:
  - **"분쟁 데이터의 Shodan"이 되어라** — 카테고리를 만들어라
  - **원타임 결제 옵션 검토**: $49 평생 Basic (기능 제한) → 진입장벽 극적 하락
  - **유저 수가 많아지면 Enterprise가 알아서 온다** — 세일즈 팀 없이도 가능
  - **최소 인원 운영**: 1인이면 이익률 95%+ 가능
  - **핵심**: Shodan은 "아웃바운드 세일즈"를 거의 안 함 — 제품이 세일즈맨

#### 3) ACLED — 학술 데이터 → $15.7M 비영리
- **시작**: 2005년 박사 프로젝트 (Clionadh Raleigh, Sussex 대학)
- **현재**: $15,700,000/년 (2023 IRS 990), 직원 100+명
- **성장 곡선**:
  - 2015: $198,000
  - 2017: $857,000
  - 2018: $12,330,000 (**+1,338%** — 변곡점)
  - 2023: $15,700,000
- **성공 공식**:
  1. **무료 데이터 → 브랜드 신뢰 → 유료 서비스**: 데이터 자체는 무료, 상업 라이선스/컨설팅이 매출
  2. **학술적 엄격성**: "우리 데이터는 신뢰할 수 있다"가 핵심 브랜드
  3. **3년 참을성**: 2005~2018, 13년간 미미한 매출 → 2018 변곡점
  4. **Program Services 29%**: 보조금 의존이지만 최소한의 자체 매출이 있었음
  5. **데이터 품질 = 해자(moat)**: 코딩 방법론이 표준이 됨
- **➜ WeWantPeace가 배울 점**:
  - **데이터 품질이 장기 경쟁력**: 소스 66개 × 5분 실시간은 ACLED보다 빠름 (ACLED는 주간 배치)
  - **"학술급 신뢰성"을 목표로**: 정확도 메트릭 공개, 방법론 문서화
  - **변곡점은 갑자기 온다**: 3년 ₩0 → 갑자기 ₩1억 가능 (ACLED 패턴)
  - **무료 데이터로 브랜드 먼저, 돈은 그 다음**: LiveUAMap과 같은 패턴

#### 4) Bellingcat — 블로그 → EUR 4.5M/년
- **시작**: 2014년, Eliot Higgins 개인 블로그, Kickstarter $115,000
- **현재**: EUR 4,500,000/년 (2023), 직원 30+명
- **성공 공식**:
  1. **미션 드리븐**: "인터넷으로 전쟁범죄를 밝힌다" → 사람들이 모여듦
  2. **커뮤니티 자원봉사자**: 수천 명이 무급으로 조사에 참여
  3. **워크숍이 전체 매출의 14%**: OSINT 교육을 돈 받고 판매 → 자체 수익
  4. **콘텐츠가 제품**: 조사 보고서 자체가 가치 → 미디어 노출 → 더 많은 팬
  5. **Kickstarter → 재단 → 기부 + 워크숍**: 다양한 수익원
- **➜ WeWantPeace가 배울 점**:
  - **미션 스토리가 가장 강력한 마케팅**: "경보 공포 → 혼자 만든 195개국 모니터링"
  - **교육 콘텐츠 판매 가능성**: OSINT 워크숍, 분쟁 데이터 분석 교육
  - **커뮤니티를 만들어라**: 사용자가 데이터 품질 개선에 참여하는 구조
  - **콘텐츠 = 마케팅 + 매출**: 뉴스레터/보고서가 돈도 벌고 유저도 데려옴

#### 5) Recorded Future — $55M 투자 → $2.65B 인수
- **시작**: 2009년, MIT Media Lab 출신 Christopher Ahlberg
- **결과**: Mastercard가 $2,650,000,000에 인수 (2024)
- **성공 공식**:
  1. **사이버 보안으로 피벗**: 원래 지정학 → 사이버 보안으로 전환 (시장이 10배 큼)
  2. **정부가 첫 고객**: CIA의 In-Q-Tel이 초기 투자 → 정부 계약이 초기 매출
  3. **"위협 인텔리전스" 카테고리 창조**: Shodan처럼 새로운 시장을 만듦
  4. **무료 리서치 발행**: 정기적 위협 보고서 발행 → 브랜드 인지도 + 리드 획득
- **➜ WeWantPeace가 배울 점**:
  - **피벗 가능성 열어두기**: 분쟁 데이터 → 공급망 리스크, 여행 안전, 사이버 보안 등
  - **정부/공공기관이 잠재 고객**: 한국 국방부, 외교부, NIS 등도 이런 데이터 필요
  - **무료 보고서가 리드를 만든다**: "Q1 Global Conflict Risk Index" 같은 정기 보고서
  - **카테고리 창조가 핵심**: "개인용 분쟁 인텔리전스"는 아직 없는 카테고리

---

### 0.3 패턴 종합 — 살아남은 vs 죽은 회사의 차이

| 패턴 | 살아남은 회사 | 죽은 회사 |
|------|-------------|----------|
| **커뮤니티** | Shodan(500만), LiveUAMap(800M방문), Bellingcat(수천명 자원봉사) | EQLIM(없음), Predata(없음), CrisisNET(없음) |
| **무료 제품** | 모두 강력한 무료 티어 보유 | API-only 또는 Enterprise-only |
| **자체 매출** | 초기부터 작게라도 매출 발생 | 보조금/투자 의존 |
| **팀 규모** | Shodan 5명, LiveUAMap 2명 시작 | EQLIM/GeoQuant/Predata 10~30명 |
| **타겟** | 넓은 무료 유저 → 좁은 유료 | 처음부터 좁은 Enterprise |
| **위기 대응** | LiveUAMap: 전쟁 터지면 트래픽 폭발 | 위기에 무반응 |
| **카테고리** | Shodan: "IoT 검색엔진" 만듦 | 기존 카테고리에서 싸움 |
| **CEO** | 기술 CEO (직접 개발) | 비기술 CEO (외주/채용 의존) |
| **시간** | 5~10년 (인내) | 2~3년에 포기 |

**→ WeWantPeace의 현재 위치**: 기술 CEO ✅, 제품 완성 ✅, 무료 티어 ✅, 커뮤니티 ❌ (가장 시급), 자체 매출 ❌ (가장 시급)

---

## Part 1. 현황 진단

### 1.1 현재 가격 구조

| 플랜 | 월 가격 | 통화 | 결제 수단 |
|------|--------|------|----------|
| Free | $0 | - | - |
| Pro | $3.90 | USD (세금별도) | DodoPayments (웹), Google Play IAP, Apple IAP |
| Pro+ | $6.90 | USD (세금별도) | DodoPayments (웹), Google Play IAP, Apple IAP |

- 프로모 코드: PRODUCTHUNT (Pro 7일), THREADS (Pro+ 14일), testerforyou (Pro+ 30일)
- 7일 무료 Pro 트라이얼 (유저당 1회 제한)
- 레퍼럴: 친구 초대 시 referrer에게 Pro 7일 보상 (최대 30일)

### 1.2 $3.90으로 300만원 벌려면?

| 시나리오 | 단가 | 필요 구독자 수 |
|---------|------|--------------|
| Pro만 | $3.90 (≈₩5,700) | **527명** |
| Pro+만 | $6.90 (≈₩10,000) | **300명** |
| 6:4 믹스 | ~$5.10 (≈₩7,400) | **~405명** |

→ 분쟁 모니터링이라는 초니치 시장에서 유료 구독자 400~500명은 **비현실적**.

### 1.3 경쟁사 가격 비교 — 우리가 얼마나 싸게 팔고 있는가

| 서비스 | 가격 | 대상 | 데이터 |
|--------|------|------|--------|
| **Dataminr** | $10,000+/월 (1유저), 엔터프라이즈 $50,000~200,000/월 | 기업, 정부 | 실시간 AI 알림, 소셜미디어+뉴스 |
| **ACLED** | 상업 라이선스 $10,000~50,000+/년 | 연구기관, NGO, 기업 | 분쟁 이벤트 데이터 (배치, 주간 업데이트) |
| **Janes Intelligence** | $50,000+/년 | 군/정부, 대기업 | 군사·안보 분석 |
| **Crisis24 (GardaWorld)** | 기업 커스텀 견적 | 글로벌 기업 | 여행 안전, 위기 관리 |
| **Shodan** | $49 원타임 ~ $1,099/월 | 개인~기업 | IoT 디바이스 스캔 |
| **geoconflicts API (RapidAPI)** | $9~99/월 | 개발자 | UCDP 단일 소스 |
| **WeWantPeace** | **$3.90~$6.90/월** | 개인 | **66소스, 195개국, 5분 실시간** |

**결론:** 우리 데이터(66소스 × 195개국 × 5분 실시간 × AI 분석)는 기관급 인프라인데 $3.90에 팔고 있다. Dataminr의 **1/2,500 가격**. 가격을 10배 올려도 시장에서 가장 싸다.

### 1.4 현재 인프라 점검 (코드 기반)

#### 이미 갖춰진 것 ✅
| 인프라 | 상태 | 파일 위치 |
|--------|------|----------|
| 유저 세그먼테이션 (plan/status/마케팅동의) | ✅ 운영중 | `backend/app/models/user.py` |
| 이벤트 분석 (제네릭 + 페이월 퍼널) | ✅ 운영중 | `frontend/lib/analytics.ts`, `backend/app/models/app_event.py` |
| 페이월 시스템 (4개 트리거, 빈도 제한) | ✅ 운영중 | `frontend/components/ui/PaywallModal.tsx`, `frontend/lib/paywall-cap.ts` |
| 레퍼럴 시스템 | ✅ 운영중 | `backend/app/routers/me.py:844-903` |
| DodoPayments 결제 | ✅ 운영중 | `backend/app/routers/dodopayments.py` |
| SNS 자동발행 (X/Telegram/LinkedIn/Threads/Instagram) | ✅ 코드완성 | `worker/social/adapters/` |
| 마케팅 이메일 (SMTP 대량발송) | ✅ 기본동작 | `backend/app/routers/admin.py:1675-1840` |
| SEO (sitemap, OG이미지, JSON-LD, 검색엔진 인증) | ✅ 최적화됨 | `frontend/app/sitemap.ts`, `frontend/app/layout.tsx` |
| 어드민 대시보드 (DAU, 구독자, 매출, 데이터품질) | ✅ 운영중 | `frontend/app/admin/page.tsx` |
| Google/Naver 검색 등록 | ✅ 완료 | Search Console 인증 코드 포함 |

#### 없는 것 ❌
| 인프라 | 상태 | 필요 이유 |
|--------|------|----------|
| B2B 팀/기관 플랜 | ❌ 미구현 | 고단가 매출의 핵심 |
| 외부 공개 API + API 키 관리 | ❌ 미구현 | 데이터 판매 채널 |
| 연간 플랜 | ❌ 미구현 | LTV 증가 + 이탈 감소 |
| 이메일 자동화 (트라이얼 만료, 윈백) | ❌ 미구현 | 전환율 핵심 |
| 뉴스레터 시스템 | ❌ 미구현 | 리드 획득 + 전환 퍼널 |
| 커뮤니티 기능 | ❌ 미약 | 리텐션의 핵심 (경쟁사 분석 교훈) |

### 1.5 현재 페이월의 문제점 (코드 분석)

**트리거 4개뿐:**
| 트리거 | 발동 조건 | 문제 |
|--------|----------|------|
| `verified_locked` | 설정에서 신뢰 알림 토글 | 설정 페이지까지 안 감 |
| `kscore_threshold_locked` | 설정에서 KScore 슬라이더 4.0 이하 | KScore 자체를 모르는 유저 대다수 |
| `watch_country_limit_locked` | 3번째 관심국가 추가 시 | 2개로 충분한 유저 많음 |
| `intel_locked` | 지도 인텔 레이어 5초 프리뷰 후 | 5초로 흥미 못 느낌 |

**빈도 제한까지:**
- 30분 쿨다운 + 세션당 1회
- 하루 최대 2회 노출 (`paywall-cap.ts`)

→ **유저가 페이월을 만날 확률이 극히 낮음.** Free로 핵심 가치(지도, 이슈 상세, 커뮤니티)를 다 소비 가능.

**☠️ 경쟁사 교훈 적용**: LiveUAMap은 무료를 풍부하게 → 트래픽 → 광고 매출. CrisisNET은 무료만 있고 유료 없음 → 사망. **균형이 핵심.**

---

## Part 2. 전략 재구성 — 경쟁사 교훈 기반

### 기존 전략의 문제점 (자기비판)

| 기존 가정 | 현실 (경쟁사 증거) |
|----------|------------------|
| "B2B Team $49/월로 빠르게 매출" | EQLIM이 $425K 쓰고도 B2B 세일즈에 실패. B2B 세일즈 사이클 6~12개월. |
| "API를 RapidAPI에 올리면 $200~500/월" | RapidAPI 평균 수익 <$50/월. geoconflicts API도 거의 수익 없음. |
| "LinkedIn 아웃리치로 기관 2~4곳 확보" | 콜드 아웃리치 성공률 극히 낮음. Shodan/LiveUAMap은 아웃바운드 세일즈를 거의 안 함. |
| "개인 구독 85명 확보" | LiveUAMap PRO ($1.99) 전환율 추정 0.01% 미만. 트래픽이 수십만이어야 성립. |

### 새로운 전략 프레임워크: "Shodan 모델" 적용

```
                    ┌──────────────────────────────────────────┐
                    │  월 300만원 (≈$2,100) MRR — 12~18개월 목표  │
                    └─────────────────┬────────────────────────┘
                                      │
  ┌─────────────────────┬─────────────┼──────────────┬──────────────────────┐
  │                     │             │              │                      │
축 1: 커뮤니티 우선   축 2: 뉴스레터  축 3: API     축 4: 구독           축 5: 위기 매출
(LiveUAMap/         (Bellingcat/   (Shodan       (기존 Pro/Pro+     (LiveUAMap
 Bellingcat 모델)    ACLED 모델)    모델)          + 원타임)           교훈)
$0 직접매출         ₩300,000       ₩600,000       ₩600,000           ₩500,000+
→ 브랜드/트래픽     유료 구독 200명  5~8 고객       70~100명            위기 때 급등
```

**핵심 변화**: "아웃바운드 세일즈(LinkedIn DM, 콜드이메일)"에서 **"인바운드 + 커뮤니티 + 콘텐츠"**로 전환.

이유:
- 성공한 5개 회사 중 아웃바운드 세일즈가 주요 성장 동력인 곳 = 0개
- 5개 모두 "제품/콘텐츠가 유저를 끌어옴" → 유저가 유료 전환
- 실패한 5개 중 3개가 "아웃바운드/Enterprise 세일즈"에 의존

---

## Part 3. 축 1: 커뮤니티 우선 전략

> **교훈**: Shodan(500만 유저), LiveUAMap(800M 방문), Bellingcat(자원봉사 커뮤니티)
> **반면교사**: EQLIM(커뮤니티 없음→사망), CrisisNET(커뮤니티 없음→사망)

### 3.1 "분쟁 데이터의 Shodan" 포지셔닝

**카테고리 창조**: 기존 카테고리("분쟁 모니터링 플랫폼")에서 싸우지 말고, 새 카테고리를 만들어라.

| 기존 카테고리 | 경쟁자 | 우리 카테고리 (신규) |
|-------------|-------|-------------------|
| "Conflict Monitoring" | Dataminr, ACLED, LiveUAMap | **"Personal Conflict Intelligence"** |
| "Geopolitical Risk" | Janes, Crisis24, EIU | **"Real-time Conflict Search Engine"** |
| "OSINT Platform" | Maltego, SpiderFoot | **"Conflict Data Shodan"** |

→ "세계 분쟁의 Shodan" = 누구나 검색할 수 있는 실시간 분쟁 데이터 엔진
→ Shodan이 "인터넷에 뭐가 연결되어 있는가?"를 답했듯, WeWantPeace는 "지금 세계 어디서 무슨 분쟁이?"를 답한다

**메시지**: "The Shodan of Global Conflicts — Search any country, see real-time tension"

### 3.2 커뮤니티 구축 로드맵

#### Phase 1: 씨앗 뿌리기 (Month 1~2)

**Reddit — 가장 높은 ROI 채널 (경쟁사 증거 기반)**
- Shodan이 r/netsec에서 성장, OSINT 도구들이 r/OSINT에서 성장
- Reddit이 B2B 구매 결정의 75%에 영향 (2025 데이터)

| 서브레딧 | 멤버 수 | 포스트 전략 | 빈도 |
|---------|--------|-----------|------|
| r/OSINT | 180K+ | "I built a free conflict search engine" + 피드백 요청 | 첫 주 |
| r/geopolitics | 900K+ | 데이터 분석 포스트 (도구는 출처로만 언급) | 격주 |
| r/dataisbeautiful | 21M+ | 긴장도 히트맵 [OC] | 월 1회 |
| r/sideproject | 100K+ | 1인 개발자 빌딩 스토리 | 첫 주 |
| r/SaaS | 50K+ | "#BuildInPublic" 성장 공유 | 격주 |
| r/supplychain | 50K+ | 공급망 리스크 데이터 분석 | 월 1회 |

**r/OSINT 포스트 (완성본):**
```
제목: I built a free real-time conflict search engine —
      think "Shodan for global conflicts" — 195 countries,
      66 sources, updated every 5 minutes

본문:
Hey r/OSINT,

Solo dev from South Korea here. After the martial law scare
in Dec 2024 (woke up to emergency alerts at 1am), I realized
there was no affordable way to monitor global conflicts in
real-time.

Existing tools are either:
- Enterprise-only ($10K+/mo like Dataminr)
- Academic/batch (ACLED updates weekly)
- Single-region (LiveUAMap = Ukraine/Middle East focused)

So I built WeWantPeace — a real-time conflict search engine:

**What it does:**
- 66 sources: RSS (Reuters, AP, Al Jazeera), Telegram channels,
  GDELT, ACLED, UCDP
- Updates every 5 minutes
- AI clusters related events → per-country Tension Index (0-100)
- Intel layers: NASA FIRMS fire detection, GPS jamming,
  internet outages

**What makes it different:**
- ALL 195 countries (not just active war zones)
- Quantified tension scores, not just pins
- Free: full map + 5 daily alerts + issue details
- Korean + English bilingual

**Stack:** Next.js 14, FastAPI, PostgreSQL, Redis, Celery,
GPT-4o-mini for classification

Working on a public API next. Free at: wewantpeace.live

Questions for you:
1. What data sources am I missing?
2. Would an API be useful for your OSINT workflow?
3. Any features that would make this indispensable?
```

**Telegram OSINT 커뮤니티 진입:**
- 자체 채널 생성 (@wewantpeace_live)
- 하루 3~5건 자동 포스팅 (코드 이미 완성: `worker/social/adapters/telegram.py`)
- OSINT 관련 채널에서 활동 → 자연스러운 도구 소개

**X/Twitter #BuildInPublic:**
- 매일 1트윗: 개발 과정, 데이터 인사이트, 기술 스택
- 주 1쓰레드: 창업자 스토리, 기술 딥다이브
- 기존 준비된 7일 쓰레드 시리즈 실행 (`x-buildinpublic-threads.md`)
- **위기 이벤트 시 즉시 대응**: 분쟁 터지면 1시간 내 데이터 스크린샷 공유

#### Phase 2: 성장 가속 (Month 3~4)

**Product Hunt 런칭:**
- 4주 사전 활동 (매일 다른 제품 업보트/댓글)
- Hunter 섭외 (팔로워 1,000+ PH 유저에게 DM)
- 타이밍: 화~목, 미국 동부 00:01
- 에셋: 로고, 갤러리 5장, 30초 데모 영상

**Show HN:**
- "Show HN: I built a real-time conflict search engine after Korea's martial law scare"
- 미국 동부 오전 9~10시 (화~목)
- **Shodan이 HN에서 시작됨** → 같은 경로 복제

**한국 커뮤니티:**
- 디스콰이엇: 메이커로그 주 1회 (이미 Bronze 배지 보유)
- GeekNews: Show HN 스타일 포스트
- 커리어리: 1인 개발자 + 분쟁 모니터링 스토리

#### Phase 3: 커뮤니티 심화 (Month 5~6)

**Bellingcat 모델 — 사용자 참여형 데이터 개선:**
- "Missing Source" 신고 기능: 유저가 놓친 소스를 제보
- "Data Quality" 피드백: 잘못된 분류 신고
- 월간 "Community Contributor" 하이라이트
- **Bellingcat은 자원봉사자가 콘텐츠를 만듦 → 우리도 유저가 데이터를 개선**

**Discord/Slack 커뮤니티:**
- 100명 이상 활성 유저 확보 후 개설
- #general, #data-quality, #feature-requests, #api-dev 채널
- Shodan의 커뮤니티: 유저끼리 use case 공유 → 제품의 가치를 유저가 만들어줌

### 3.3 위기 = 성장 엔진 (LiveUAMap 핵심 교훈)

**LiveUAMap의 성장 공식**: 전쟁/분쟁 이벤트 → 트래픽 폭발 → 유저 일부 잔류 → 구독/광고 매출

**WeWantPeace 위기 대응 SOP:**
1. **분쟁 이벤트 발생 감지** (긴장도 급등 자동 감지, 이미 구현)
2. **30분 내**: X에 데이터 스크린샷 + 분석 공유 (해시태그: #OSINT #BreakingNews #해당국가)
3. **1시간 내**: Telegram 채널에 상세 데이터 포스트
4. **2시간 내**: Reddit r/worldnews 또는 r/geopolitics에 데이터 기반 코멘트 (도구 소개는 자연스럽게)
5. **24시간 내**: 뉴스레터 특별호 발행

**벤치마크**: LiveUAMap은 2022 우크라이나 전쟁 때 하루 방문 수가 기존의 50배 → 그 트래픽의 10~20%가 전쟁 후에도 잔류

→ **분쟁은 슬프지만, 분쟁이 일어날 때 사람들은 정보를 찾는다. 그때 우리가 최고의 정보를 제공하면 된다.**

---

## Part 4. 축 2: 뉴스레터 — 한국 지정학 블루오션

> **교훈**: Bellingcat 워크숍(매출 14%), ACLED 무료 데이터→유료 서비스(29%)
> **리서치 결과**: 한국어 지정학 유료 뉴스레터 = **블루오션** (경쟁자 0)

### 4.1 왜 뉴스레터인가?

| 근거 | 데이터 |
|------|--------|
| 한국 지정학 유료 뉴스레터 | **없음** (블루오션) |
| 글로벌 지정학 뉴스레터 | SpyTalk, OSINT Newsletter(26K+ 구독), Geopolitical Dispatch |
| Substack 유료 전환율 | 5~10% (무료 구독자 → 유료) |
| 한국 뉴스레터 플랫폼 | 스티비 (수수료 0%) |
| WeWantPeace 우위 | 데이터가 이미 있음 → 뉴스레터 콘텐츠 자동 생성 가능 |

### 4.2 "Conflict Intelligence Brief" — 이중 언어 뉴스레터

**플랫폼**: Substack (글로벌) + 스티비 (한국)
**빈도**: 주 1회 (매주 월요일 아침)
**가격**:
- 무료 티어: 주간 TOP 5 이슈 요약
- 유료 ($10/월): 전체 분석 + 데이터 테이블 + 국가별 심층 분석

**무료 뉴스레터 예시:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Conflict Intelligence Brief #001
   2026년 3월 24일 | WeWantPeace
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 이번 주 TOP 5 위기 상황
1. 미얀마: 긴장도 89 (+12) — 카렌주 전투 격화
2. 수단: 긴장도 92 (+5) — RSF 엘파셔 공세
3. 우크라이나: 긴장도 85 (-3) — 전선 교착
4. 가자: 긴장도 91 (+1) — 인도적 위기 심화
5. 에티오피아: 긴장도 67 (+15) — 아무하라 민병대 활동

📈 긴장도 급등 국가 (이번 주)
[국가별 수치 변화 테이블]

🗺 이번 주 하이라이트
[지도 스크린샷 + 한 문단 분석]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💎 PRO 구독자만 읽을 수 있는 콘텐츠:
• 195개국 전체 긴장도 테이블 (주간 변화)
• "한국에 미치는 영향" 심층 분석 (공급망, 에너지, 여행)
• 다음 주 예측: AI 기반 긴장도 전망
• 국가별 딥다이브: 이번 주는 [미얀마]

→ 월 $10으로 전체 인텔리전스를 받아보세요
   [구독하기]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

이 데이터는 WeWantPeace에서 자동 수집됩니다.
실시간 모니터링: www.wewantpeace.live
```

### 4.3 뉴스레터 성장 시뮬레이션

| 기간 | 무료 구독자 | 유료 구독자 ($10/월) | 월 매출 |
|------|----------|-------------------|---------|
| Month 1~3 | 200~500 | 10~25 | $100~250 |
| Month 4~6 | 500~1,500 | 25~75 | $250~750 |
| Month 7~12 | 1,500~3,000 | 75~200 | $750~2,000 |
| Month 13~18 | 3,000~5,000 | 200~300 | **$2,000~3,000** |

**전환 경로:**
```
무료 뉴스레터 구독 → 유료 뉴스레터 ($10/월) → WeWantPeace Pro ($3.90/월) → API
```

### 4.4 콘텐츠 자동화 (우리만의 무기)

**경쟁자와의 차이**: 일반 뉴스레터 작가는 매주 수시간 리서치+집필. 우리는 **데이터가 이미 DB에 있다**.

**자동 생성 가능한 섹션:**
- TOP 5 이슈: DB에서 `severity` 상위 5건 쿼리
- 긴장도 변화: `tension_history` 테이블에서 주간 변동 계산
- 국가별 테이블: 전체 국가 긴장도 + 변동폭
- 타임라인: 주요 이벤트 시간순 정렬

**수동 작성 섹션 (유료 가치):**
- "한국에 미치는 영향" 분석
- 다음 주 전망/예측
- 국가별 딥다이브 (배경 맥락)
- 개인적 인사이트/의견

→ 자동 70% + 수동 30% = 주당 1~2시간으로 고품질 뉴스레터 발행 가능

---

## Part 5. 축 3: 유료 API — Shodan 모델 적용

> **교훈**: Shodan은 $49 원타임으로 500만 유저 확보 → Enterprise가 알아서 찾아옴
> **반면교사**: CrisisNET은 API만 있고 유저 없어서 사망

### 5.1 가격 재설계 (Shodan 모델)

**기존 계획**: Free/Starter $29/Pro $99/Enterprise $299 (월간만)

**Shodan 교훈 적용 — 원타임 진입장벽:**

| 티어 | 가격 | 일일 콜 | 특징 |
|------|------|--------|------|
| **Free API** | $0 | 50 | 리드 획득용, 이메일 등록 필요 |
| **One-time Basic** | **$49 (1회)** | 100 | **Shodan의 $49 모델 복제** — 평생 사용 |
| **Monthly Pro** | $29/월 | 1,000 | 웹훅 + 히스토리 + 인텔 시그널 |
| **Monthly Pro+** | $99/월 | 5,000 | 스트리밍 + CSV 내보내기 |
| **Enterprise** | $299/월 | 무제한 | SLA 99.5% + 전용 지원 |

**왜 $49 원타임?**
- Shodan의 핵심 전략: **진입장벽을 극적으로 낮추면 유저가 폭발적으로 늘어남**
- 500만 Shodan 유저 중 대부분이 $49 원타임 → 이 중 소수가 $69~$1,099/월로 업그레이드
- $49 × 1,000명 = $49,000 (한 번에) + 월간 업그레이드 수익

### 5.2 API 엔드포인트 (핵심만)

```
# 기본 (Free + One-time)
GET /api/v1/events             — 실시간 이벤트 (필터: country, topic, severity, since)
GET /api/v1/clusters           — AI 클러스터링된 이슈
GET /api/v1/tension            — 전체 국가 긴장도
GET /api/v1/tension/{code}     — 국가별 긴장도 + 히스토리

# Pro 이상
GET /api/v1/signals/firms      — 위성 화재 감지
GET /api/v1/signals/gps-jam    — GPS 교란
GET /api/v1/signals/outage     — 인터넷 장애
POST /api/v1/webhooks          — 웹훅 등록
```

### 5.3 API 판매 채널

**1) 직접 (DodoPayments) — 주 채널**
- 수수료 2.9%만
- API 문서 페이지 (FastAPI Swagger + 별도 랜딩)
- SEO: "conflict data API", "geopolitical risk API", "ACLED alternative"

**2) RapidAPI — 보조 채널**
- 수수료 25%
- 기존 개발자 풀 접근
- 등록 즉시 가능

**3) API SEO 콘텐츠 (Shodan이 성장한 방식)**
```
1. "Top 5 Geopolitical Risk APIs for Developers (2026)"
   → 우리를 1위로 소개 (가격 대비 최고 가치)

2. "How to Monitor Global Conflicts with Python (Tutorial)"
   → 우리 API 사용 튜토리얼 → 개발자 유입

3. "Dataminr vs WeWantPeace: 99% Cheaper Alternative"
   → Dataminr 가격 검색 유저 가로채기

4. "Building a Supply Chain Risk Dashboard (Free API)"
   → 실무 튜토리얼 → API 구독
```

### 5.4 API 매출 시뮬레이션 (보수적)

| 기간 | One-time $49 | Monthly | 합계 |
|------|------------|---------|------|
| Month 1~3 | 10~30건 = $490~1,470 | $0~100 | $490~1,570 |
| Month 4~6 | 20~50건/월 = $980~2,450 | $200~500 | $1,180~2,950 |
| Month 7~12 | 30~80건/월 | $500~1,500 | $1,500~5,000/월 |

**현실 체크**: Shodan도 첫 2~3년은 $100/월 이하. **API만으로 ₩3M/월은 12개월 이내 달성 불가능.** 하지만 장기적으로 가장 스케일러블한 매출원.

---

## Part 6. 축 4: 개인 구독 — 전환율 개선 + 원타임 옵션

> **교훈**: LiveUAMap PRO는 $1.99/월이지만 전환율은 0.01% 미만. 트래픽이 핵심.
> Shodan은 $49 원타임이 주 매출.

### 6.1 가격 재구성

| 플랜 | 가격 | 타겟 |
|------|------|------|
| Free | $0 | 모든 유저 — 지도, 이슈 5건/일, 알림 5건/일 |
| **Lifetime Basic** | **$29 (1회)** | "한번만 내면 영원히" — Shodan 패턴 |
| Pro | $3.90/월 | 기존 유지 |
| Pro+ | $6.90/월 | 기존 유지 |
| Pro 연간 | $35/년 (25% 할인) | LTV 증가 |
| Pro+ 연간 | $62/년 (25% 할인) | LTV 증가 |

**Lifetime Basic ($29)에 포함:**
- 이슈 상세 무제한 열람
- 알림 20건/일
- 관심 국가 5개
- 7일 히스토리
- **Pro의 80%를 한 번에 $29로** → 진입장벽 극적 하락

**왜 원타임?**
- Shodan: $49 원타임이 전체 유저의 80%+ → 이 유저들이 브랜드 확산
- 분쟁 모니터링은 "매달 돈 낼 가치"보다 "가끔 확인하는 용도" 유저가 대다수
- $29 × 100명 = $2,900 (즉시) + 이 중 10%가 Pro+ 월간 업그레이드

### 6.2 Free 제한 조정 (LiveUAMap 교훈 반영)

**⚠️ 핵심 교훈: LiveUAMap은 무료를 풍부하게 → 트래픽 → 매출**
**반면: 무료가 너무 풍부하면 업그레이드 동기 없음 (현재 우리 문제)**

**균형점:**

| 기능 | Free | Lifetime $29 | Pro $3.90/월 | Pro+ $6.90/월 |
|------|------|-------------|-------------|--------------|
| 이슈 지도 | ✅ 전체 | ✅ | ✅ | ✅ |
| 이슈 상세 | **5건/일** | 무제한 | 무제한 | 무제한 |
| 홈 피드 | 5건 후 CTA | 무제한 | 무제한 | 무제한 |
| 타임라인 | 최근 3건 | 전체 | 전체 | 전체 |
| 알림 | 5건/일 | 20건/일 | 20건/일 | 100건/일 |
| 관심 국가 | 2개 | 5개 | 5개 | 무제한 |
| 히스토리 | 7일 | 7일 | 30일 | 90일 |
| 인텔 레이어 | 5초 프리뷰 | ❌ | ✅ | ✅ |
| 신뢰 알림 | ❌ | ❌ | ✅ | ✅ |
| KScore | ❌ | ❌ | ✅ | ✅ |

**핵심**: 지도와 기본 브라우징은 Free로 풍부하게 (트래픽용) → 깊이 들어가면 유료

### 6.3 페이월 트리거 추가

**현재 4개 → 변경 후 8~10개:**

| 트리거 | 발동 조건 | 예상 노출 빈도 |
|--------|----------|--------------|
| (기존) verified_locked | 설정에서 토글 | 낮음 |
| (기존) kscore_threshold | KScore 조정 | 낮음 |
| (기존) country_limit | 3번째 국가 | 중간 |
| (기존) intel_locked | 인텔 5초 | 중간 |
| **(신규) issue_detail_limit** | 하루 5건 초과 | **높음** |
| **(신규) timeline_locked** | 3건 이후 blur | **높음** |
| **(신규) briefing_locked** | 3건 이후 잠금 | **높음** |
| **(신규) feed_upgrade_card** | 5번째 카드 후 | **높음** |
| **(신규) alert_exhausted** | 5건 소진 시 | 중간 |
| **(신규) lifetime_cta** | 이슈 하단 | **높음** — "$29 한 번이면 영원히" |

### 6.4 트라이얼 → 유료 전환 자동화

| 시점 | 액션 | 메시지 |
|------|------|--------|
| D-2 | 푸시 + 이메일 | "Pro 체험이 2일 후 종료됩니다" |
| D-1 | 푸시 | "내일 Pro 기능이 비활성화됩니다" |
| D-day | 인앱 모달 | "Pro 종료 — [구독] 또는 [$29 Lifetime]" |
| D+3 | 이메일 | "Pro 기능이 제한됐습니다. $29 한 번이면 영원히" |
| D+7 | 이메일 | "COMEBACK30 — 첫 달 30% 할인" |

---

## Part 7. 축 5: 위기 매출 — 분쟁 이벤트 기반 수익

> **교훈**: LiveUAMap은 2022 우크라이나 전쟁 때 트래픽 50배 폭발. 이게 매출의 핵심.

### 7.1 위기 대응 매출 메커니즘

```
분쟁 이벤트 발생
    ↓
자동 감지 (긴장도 급등, 이미 구현)
    ↓
30분 내: X/Telegram 자동 포스트 (SNS 어댑터 이미 완성)
    ↓
트래픽 급증 (위기 때 10~100배)
    ↓
┌─────────────┬──────────────┬──────────────┐
│  광고 매출   │  구독 전환    │  API 트래픽   │
│  (트래픽     │  (위기 중     │  (개발자가    │
│   기반)      │  정보 필요)   │  데이터 호출) │
└─────────────┴──────────────┴──────────────┘
```

### 7.2 광고 매출 검토 (LiveUAMap의 핵심 매출원)

**현재 상태**: 광고 없음
**검토 필요**: Google AdSense or 직접 광고 영업

| 월간 DAU | 예상 페이지뷰/월 | AdSense RPM | 월 광고 매출 |
|---------|---------------|-------------|------------|
| 500 | 15,000 | $3~5 | $45~75 |
| 2,000 | 60,000 | $3~5 | $180~300 |
| 10,000 | 300,000 | $3~5 | $900~1,500 |
| 50,000 | 1,500,000 | $3~5 | $4,500~7,500 |

→ **DAU 2,000 이상이면 광고도 의미 있는 매출.** 현재는 시기상조이지만 트래픽이 오면 즉시 적용.

### 7.3 위기 프리미엄 콘텐츠

**위기 발생 시 특별 제공 (유료만):**
- 실시간 업데이트 스트림 (5분→1분 간격)
- 위기 지역 상세 분석 보고서
- 위기 알림 무제한
- 뉴스레터 특별호

→ **"위기 때 정보가 돈이 된다"** — 이건 비윤리적인 게 아니라, 정보에 가치를 매기는 것

---

## Part 8. B2B — "세일즈하지 마라, 찾아오게 만들어라" (Shodan 모델)

> **교훈**: Shodan은 세일즈팀 없이 Fortune 100을 고객으로 확보. EQLIM은 $425K으로 세일즈해도 실패.
> **결론**: 1인 개발자가 아웃바운드 B2B 세일즈를 하는 것은 시간 낭비. 인바운드로 전환.

### 8.1 B2B 인바운드 전략

**Shodan의 B2B 확보 과정:**
1. 개인 유저 500만 확보 (대부분 무료/원타임)
2. 그 중 기업 소속 유저가 사내에서 추천
3. 기업이 Enterprise 플랜 문의
4. → **세일즈팀 없이도 Enterprise 계약**

**WeWantPeace 적용:**
1. 커뮤니티 + 뉴스레터 + API로 **개인 유저 1,000~5,000명** 확보
2. 그 중 기업/기관 소속 유저가 사내에서 "이 도구 유용하다"
3. 기관이 Team/Business 플랜 문의
4. → 세일즈 없이 B2B 계약 (ARPU $49~$349)

### 8.2 B2B 플랜 (찾아오면 파는 용도)

| 플랜 | 가격 | 시트 | API | 기능 |
|------|------|------|-----|------|
| **Team** | $49/월 | 5명 | 1,000콜/일 | Pro+ 전체 + CSV 내보내기 |
| **Business** | $149/월 | 20명 | 10,000콜/일 | Team + 웹훅 + 커스텀 알림 |
| **Enterprise** | $349/월 | 무제한 | 무제한 | Business + SLA 99.5% |

**B2B 랜딩페이지만 만들고 기다리기:**
```
wewantpeace.live/enterprise

"Fortune 500 companies use Dataminr for $10,000+/month.
 Same capability, 99% cheaper.
 [Request Demo] [Start 14-day Trial]"
```

### 8.3 아웃바운드는 최소한만 — 기자 콜드이메일

**경쟁사 분석 결론**: 아웃바운드 세일즈는 시간 대비 효과 낮음. **단 하나의 예외: 기자.**

이유:
- 기자는 도구에 관심이 높음 (뉴스 속보 경쟁)
- 기사화 가능성 → 언론 노출 = 무료 마케팅
- 이미 1,198명 이메일 확보 + 템플릿 준비됨
- **기자 개인이 유료 구독하는 게 목적이 아님 → 기사화가 목적**

**실행:**
- 하루 50통 × 24일 = 1,198명 전량 발송
- 3~5% 답변 → 36~60명 관심
- 1~3건 기사화 기대
- **기사 1건 = Reddit/HN 포스트 100개의 효과**

### 8.4 대학/연구기관 — 무료 제공 후 유료 전환

**ACLED의 성공 패턴**: 대학에 무료 데이터 → 학계에서 표준이 됨 → 상업 라이선스 매출

**WeWantPeace 적용:**
- 국제관계학과 교수에게 **1학기 무료 Team 플랜** 제공
- 학생들이 사용 → 졸업 후 기업에서 "이 도구 좋았는데" → 기업 유입
- 한국 + 해외 10개 대학 타겟

```
제목: 수업용 실시간 분쟁 데이터 플랫폼 — 무료 제공

교수님 안녕하세요,

[학과명]에서 국제관계를 가르치시는 것을 알게 되어 연락드립니다.

WeWantPeace는 195개국 실시간 분쟁 모니터링 플랫폼입니다.
(66개 데이터소스, 5분 간격, AI 분석, 한/영 이중 언어)

수업에서 학생들이 실시간 분쟁 상황을 추적하고 분석하는
도구로 활용하시면 좋을 것 같습니다.

Academic Team 플랜(5인)을 1학기 무료로 제공해 드리겠습니다.

www.wewantpeace.live
```

---

## Part 9. 콘텐츠 마케팅 — 데이터가 이미 있으니까

> **교훈**: ACLED은 무료 데이터로 브랜드를 만들고, Recorded Future는 무료 보고서로 리드를 획득함

### 9.1 분기별 무료 보고서 (리드 생성)

**"Q1 2026 Global Conflict Risk Index: 195 Countries Ranked"**
- 형식: PDF (20~30페이지), 이메일 게이팅 (다운로드 시 이메일 수집)
- 내용: 국가별 긴장도 순위 + 주요 이슈 분석 + 트렌드
- **데이터는 DB에서 쿼리하면 끝** — 새로운 리서치 불필요
- SEO: "country risk ranking 2026", "global conflict index" 키워드

### 9.2 인터랙티브 무료 도구 (Product-Led Growth)

**Country Risk Checker (구현 간단):**
```
https://www.wewantpeace.live/risk-check

[국가 선택 드롭다운]
→ 현재 긴장도 + 최근 이슈 3건 + 30일 트렌드
→ "더 자세한 분석: Pro $3.90/월 or Lifetime $29"
→ "이 데이터를 API로: $49 원타임"
```

### 9.3 SEO 콘텐츠 (장기 유입)

이미 세팅됨: sitemap, OG이미지, JSON-LD, Search Console 등록

**추가 필요:**
```
블로그 페이지 시스템 (SSR)
→ "Dataminr vs WeWantPeace" (경쟁사 비교)
→ "Top 5 Conflict Data APIs" (API SEO)
→ "How to Monitor Supply Chain Risks" (튜토리얼)
→ "Building a Geopolitical Risk Dashboard" (개발자 타겟)
```

---

## Part 10. 현실적 타임라인 & 매출 시뮬레이션

### 10.1 솔로 파운더 벤치마크 (경쟁사 실증 기반)

| 사례 | 첫 $100/월 | 첫 $1,000/월 | 첫 $10,000/월 | 방법 |
|------|-----------|-------------|--------------|------|
| Shodan | ~2년 | ~3년 | ~5년 | HN + Reddit + API |
| LiveUAMap | ~3년 | ~5년 | ~8년 | 전쟁 트래픽 + 광고 |
| Bannerbear | 2개월 | 6개월 | 2년 | 콘텐츠 + SEO |
| Plausible | 1개월 | 4개월 | 18개월 | HN + Reddit |

**WeWantPeace 현실적 예측:**
- 첫 $100/월: 2~4개월 (원타임 $29/$49 2~3건이면 달성)
- 첫 $1,000/월: 6~12개월
- 첫 $2,100/월 (₩3M): **12~18개월** (매우 공격적 실행 시)

### 10.2 확률 평가 (솔직하게)

| 시나리오 | 확률 | 조건 |
|---------|------|------|
| 12개월 내 ₩3M/월 달성 | **20~30%** | 위기 이벤트 + 바이럴 + 꾸준한 실행 |
| 18개월 내 ₩3M/월 달성 | **40~50%** | 꾸준한 커뮤니티 성장 + API 매출 |
| 24개월 내 ₩3M/월 달성 | **60~70%** | 현실적 달성 시점 |
| 달성 실패 | **30~40%** | 트래픽 부족 or 시장 자체가 작음 |

**실패 리스크:**
1. EQLIM 패턴: 시장이 너무 작아서 돈을 내는 사람이 없음 (30% 확률)
2. PeaceTech 패턴: 수익 $0인 채로 열정만으로 3년 운영 → 번아웃 (15% 확률)
3. 위기 이벤트가 안 터짐: 분쟁이 줄면 트래픽도 줄음 (10% 확률)

**성공 가속기:**
1. 대형 분쟁 이벤트 발생 → 트래픽 10~100배 (LiveUAMap 증거)
2. HN/Reddit 프론트 페이지 → 하루 5,000~10,000 방문
3. 언론 기사 1건 → 지속적 검색 유입
4. OSINT 커뮨니티에서 표준 도구로 채택 → 유기적 성장

### 10.3 월별 상세 로드맵

**Month 1 (즉시 실행)**

| 주차 | 코드 작업 | 커뮤니티/마케팅 | 예상 매출 |
|------|----------|--------------|----------|
| Week 1 | 페이월 트리거 추가 (4→8개) | r/OSINT 첫 포스트, X #BuildInPublic 시작 | ₩0 |
| Week 2 | Lifetime $29 결제 구현 | Telegram 채널 생성+자동발행, 기자 이메일 1차 (500명) | ₩0~50,000 |
| Week 3 | API 키 시스템 + Swagger 문서 | 기자 이메일 팔로업, r/sideproject 포스트 | ₩50,000~100,000 |
| Week 4 | RapidAPI 등록, 연간 플랜 | 뉴스레터 1호 (Substack+스티비), 디스콰이엇 | ₩100,000~200,000 |

**Month 2**

| 주차 | 코드 작업 | 커뮤니티/마케팅 | 예상 매출 |
|------|----------|--------------|----------|
| Week 5 | API 원타임 $49 구현 | LinkedIn 롱폼 포스트, r/geopolitics | ₩150,000~250,000 |
| Week 6 | 트라이얼 만료 알림 | 뉴스레터 2~3호, PH 사전 활동 시작 | ₩200,000~300,000 |
| Week 7 | Country Risk Checker | r/dataisbeautiful [OC], SEO 콘텐츠 1개 | ₩250,000~350,000 |
| Week 8 | B2B 플랜 + 랜딩 | 기자 이메일 2차 (나머지), Bellingcat 아웃리치 | ₩300,000~400,000 |

**Month 3**

| 주차 | 코드 작업 | 커뮤니티/마케팅 | 예상 매출 |
|------|----------|--------------|----------|
| Week 9 | 뉴스레터 자동화 | Product Hunt 런칭 | ₩400,000~600,000 |
| Week 10 | API 웹훅 | Show HN, SEO 콘텐츠 2개 | ₩500,000~700,000 |
| Week 11 | 광고 시스템 검토 (DAU 따라) | "Q1 Conflict Risk Index" 보고서 | ₩600,000~800,000 |
| Week 12 | 최적화 | 대학 교수 아웃리치 (10곳) | ₩700,000~1,000,000 |

**Month 4~6: 축적**
- 뉴스레터 유료 구독 50~100명 ($500~1,000/월)
- API 원타임 누적 50~150건 ($2,450~7,350)
- 개인 구독 20~40명 ($78~276/월)
- B2B 인바운드 1~2곳 ($49~$149/월)
- 예상 MRR: ₩800,000~1,500,000

**Month 7~12: 가속**
- 뉴스레터 유료 100~200명 ($1,000~2,000/월)
- API Monthly 5~10곳 ($145~990/월)
- 개인 구독 40~70명 ($156~483/월)
- B2B 인바운드 2~4곳 ($98~$596/월)
- 위기 이벤트 매출 스파이크 (불규칙)
- 예상 MRR: ₩1,500,000~2,500,000

**Month 13~18: 목표 달성**
- 뉴스레터 유료 200~300명 ($2,000~3,000/월)
- API 전체 $500~1,500/월
- 개인 구독 70~100명 + Lifetime 누적
- B2B 3~5곳 ($147~$745/월)
- 예상 MRR: ₩2,500,000~3,500,000

### 10.4 최종 매출 분해 (Month 18 목표 달성 시)

| 매출원 | 세부 | 월 매출 |
|--------|------|---------|
| 뉴스레터 유료 | 250명 × $10 | $2,500 (₩3,640,000) |
| API Monthly | 5곳 × $29~99 평균 $55 | $275 (₩400,000) |
| API 원타임 (월 평균) | 20건 × $49 ÷ 12 | $82 (₩119,000) |
| 개인 Pro/Pro+ | 50명 × $5 평균 | $250 (₩364,000) |
| 개인 Lifetime | 월 5건 × $29 | $145 (₩211,000) |
| B2B Team/Business | 3곳 × $99 평균 | $297 (₩432,000) |
| **소계** | | **$3,549 (₩5,166,000)** |

→ **뉴스레터가 핵심 매출원** (전체의 70%). 이건 Bellingcat 교훈(워크숍 14%가 아닌, 콘텐츠 자체가 매출)의 확장.

**보수적 시나리오** (뉴스레터 성장이 느린 경우):

| 매출원 | 보수적 | 월 매출 |
|--------|-------|---------|
| 뉴스레터 유료 | 100명 × $10 | $1,000 |
| API 전체 | $200 | $200 |
| 개인 구독 + Lifetime | $300 | $300 |
| B2B | $200 | $200 |
| **소계** | | **$1,700 (₩2,475,000)** |

→ 보수적으로도 ₩2.5M/월은 가능. ₩3M까지는 위기 이벤트나 바이럴 하나가 필요.

---

## Part 11. 투자 비용 & ROI

| 항목 | 월 비용 | 언제부터 | 비고 |
|------|---------|---------|------|
| Substack + 스티비 | $0 | Month 1 | 무료 플랜 (유료 구독 수수료만) |
| RapidAPI | $0 | Month 1 | 수수료 25% (매출 차감) |
| Railway | 기존 | - | 이미 운영중 |
| Instantly.ai (콜드이메일) | $47/월 | 보류 | 기자 이메일은 기존 SMTP로 가능 |
| **총 월 비용** | **$0~47** | | |

**ROI:**
- Lifetime Basic 1건 ($29) = 첫 달 비용 회수
- 뉴스레터 유료 5명 ($50/월) = 매월 흑자
- **1인 운영이므로 인건비 = $0 → 거의 모든 매출이 순이익**

---

## Part 12. 핵심 원칙 — 경쟁사 교훈 기반

### 12.1 생존 원칙 (실패 회사에서 배운 것)

1. **절대 Enterprise-only로 가지 마라** (EQLIM, GeoQuant, Predata 실패)
   - B2C 커뮤니티가 먼저, Enterprise는 나중에 알아서 온다

2. **자체 매출 $0 상태를 3개월 이상 유지하지 마라** (PeaceTech Lab 실패)
   - 원타임 $29/$49라도 빨리 팔아라

3. **API-only 제품이 되지 마라** (CrisisNET 실패)
   - 최종 사용자 제품(웹/앱)이 있어야 API도 산다

4. **아웃바운드 세일즈에 시간 낭비하지 마라** (EQLIM 실패, $425K)
   - 1인 개발자의 시간 = 제품 개선에 써야 함

5. **전략적 투자자 함정 조심** (GeoQuant → Fitch 인수)
   - 투자 없이 자생할 수 있는 구조가 최선

### 12.2 성장 원칙 (성공 회사에서 배운 것)

1. **카테고리를 만들어라** (Shodan: "IoT 검색엔진")
   - → "Personal Conflict Intelligence" 또는 "Conflict Search Engine"

2. **무료를 풍부하게, 깊이에서 유료로** (LiveUAMap: 무료 지도→PRO)
   - → 지도/기본 피드는 풍부하게, 상세 분석/알림에서 유료

3. **위기 = 성장 엔진** (LiveUAMap: 전쟁 때 트래픽 50배)
   - → 분쟁 터지면 30분 내 SNS에 데이터 공유

4. **데이터 품질이 장기 경쟁력** (ACLED: 학술급 신뢰성이 브랜드)
   - → 정확도 메트릭 공개, 방법론 문서화

5. **커뮤니티가 해자(moat)다** (Bellingcat: 자원봉사 조사단)
   - → 유저가 데이터 품질에 기여하는 구조

6. **콘텐츠 = 마케팅 + 매출** (Bellingcat 워크숍 14%, Recorded Future 보고서)
   - → 뉴스레터가 동시에 마케팅과 매출

7. **인내하라, 변곡점은 갑자기 온다** (ACLED: 13년 → +1,338%)
   - → 1~2년 ₩0~50만원 → 갑자기 ₩300만원 가능

### 12.3 매일/매주 루틴

| 빈도 | 활동 | 시간 |
|------|------|------|
| **매일** | X #BuildInPublic 1트윗 | 10분 |
| **매일** | Telegram/SNS 자동발행 확인 | 5분 |
| **매일** | 위기 이벤트 체크 → 즉시 공유 | 10분 |
| **매주** | 뉴스레터 1호 (자동 70% + 수동 30%) | 1~2시간 |
| **매주** | Reddit 포스트 1개 (로테이션) | 30분 |
| **매주** | 디스콰이엇 메이커로그 | 20분 |
| **격주** | SEO 콘텐츠 or 블로그 포스트 | 1시간 |
| **매월** | Conflict Risk Index 보고서 | 2시간 |

**주당 총 시간: ~5~7시간** (이전 8~10시간에서 줄임 — 아웃바운드 세일즈 제거)

---

## Part 13. 즉시 실행 우선순위 (구현 코드)

| 순위 | 작업 | 예상 시간 | 근거 (경쟁사 교훈) |
|------|------|----------|------------------|
| **P0** | Telegram 채널 생성 + 자동발행 환경변수 | 30분 | 코드 이미 완성, 환경변수만 등록 |
| **P0** | X API 키 발급 + 자동발행 | 1시간 | LiveUAMap: SNS가 위기 트래픽의 핵심 |
| **P0** | 뉴스레터 셋업 (Substack + 스티비) | 2시간 | 한국 블루오션, 핵심 매출원 |
| **P0** | r/OSINT + r/sideproject 첫 포스트 | 1시간 | Shodan: Reddit에서 성장 |
| **P1** | 페이월 트리거 추가 (4→8개) | 1일 | 전환율 2~3배 |
| **P1** | Lifetime $29 결제 구현 | 1일 | Shodan: 원타임이 유저 폭발의 핵심 |
| **P1** | API 키 발급 + Swagger 문서 | 2일 | API 매출 시작 |
| **P1** | 기자 콜드이메일 발송 (1,198명) | 진행중 | 기사화 = 최고의 마케팅 |
| **P2** | API 원타임 $49 구현 | 1일 | Shodan 모델 |
| **P2** | 연간 플랜 | 1일 | LTV 증가 |
| **P2** | RapidAPI 등록 | 반나절 | 보조 유입 |
| **P2** | Country Risk Checker | 1일 | Product-Led Growth |
| **P3** | B2B 플랜 + 랜딩 | 2일 | 인바운드용 (세일즈 아님) |
| **P3** | 뉴스레터 자동 생성 스크립트 | 1일 | 주간 70% 자동화 |
| **P3** | SEO 블로그 시스템 | 1일 | 장기 유입 |

---

## 부록 A: 경쟁사 데이터 출처

| 경쟁사 | 재무 데이터 출처 | 정확도 |
|--------|---------------|--------|
| ACLED | IRS Form 990 (2015~2023) | 정확 (세금 신고서) |
| PeaceTech Lab | IRS Form 990 (2016~2024) | 정확 |
| LiveUAMap | Crunchbase + SimilarWeb + 추정 | 중간 |
| Shodan | 인터뷰 + 추정 ($5~25M 범위) | 낮음 |
| Bellingcat | 네덜란드 재단 보고서 | 정확 |
| Dataminr | 언론 보도 ($222M ARR, 2023) | 높음 |
| Recorded Future | Mastercard 인수 공시 ($2.65B) | 정확 |
| EQLIM | Crunchbase ($425K 시드) | 높음 |
| GeoQuant | Crunchbase ($8.5M) | 높음 |
| Predata | Crunchbase ($14.3M) | 높음 |

## 부록 B: 현재 보유 마케팅 자산

| 자산 | 상태 | 위치 |
|------|------|------|
| 기자 이메일 1,198명 | ✅ 수집 완료 | `docs/marketing/press-contacts.csv` |
| 콜드이메일 3종 템플릿 | ✅ 작성 완료 | `docs/marketing/cold-email-templates/` |
| X #BuildInPublic 7일 쓰레드 | ✅ 초안 완료 | `docs/marketing/x-buildinpublic-threads.md` |
| Show HN 포스트 | ✅ 초안 완료 | `docs/marketing/show-hn-post.md` |
| Product Hunt 전략 | ✅ 문서 완료 | `docs/marketing/producthunt-strategy.md` |
| Reddit 전략 | ✅ 문서 완료 | `docs/marketing/reddit-strategy.md` |
| Bellingcat/GIJN 피치 | ✅ 초안 완료 | `docs/marketing/bellingcat-pitch-email.md` |
| SNS 자동발행 5개 플랫폼 | ✅ 코드 완성 | `worker/social/adapters/` |
| SEO 풀세팅 | ✅ 운영중 | sitemap, OG, JSON-LD, Search Console |
| 레퍼럴 시스템 | ✅ 운영중 | `backend/app/routers/me.py` |
| 마케팅 이메일 SMTP | ✅ 기본동작 | `backend/app/routers/admin.py` |
| Disquiet Bronze 배지 | ✅ 획득 | 스플래시/온보딩에 표시 |
| 창업자 스토리 | ✅ 작성 완료 | `docs/marketing/platform-content.md` |

## 부록 C: 참고 자료 & 출처

**경쟁사 분석:**
- [ACLED IRS 990 (2015~2023)](https://projects.propublica.org/nonprofits/organizations/273684060): $198K → $15.7M 성장 곡선
- [PeaceTech Lab IRS 990](https://projects.propublica.org/nonprofits/): $4.35M peak → 해산
- [Dataminr 가격 — Vendr](https://www.vendr.com/marketplace/dataminr): $10,000+/월
- [Shodan 창업 스토리](https://en.wikipedia.org/wiki/Shodan_(website)): $0 투자, 5명 운영
- [Bellingcat 재정 보고서](https://www.bellingcat.com/about/): EUR 4.5M/년
- [Recorded Future Mastercard 인수](https://www.mastercard.com/news/press/2024/september/mastercard-to-acquire-recorded-future/): $2.65B
- [EQLIM Crunchbase](https://www.crunchbase.com/organization/eqlim): $425K, 사망
- [GeoQuant Fitch 인수](https://www.fitchratings.com/): $8.5M
- [Predata FiscalNote 인수](https://www.fiscalnote.com/): $14.3M
- [CrisisNET 기록](https://ushahidi.com/): Ushahidi 내부 프로젝트, 사망

**시장 데이터:**
- [geoconflicts API — RapidAPI](https://rapidapi.com/gisfromscratch/api/geoconflicts/pricing): $9~99/월
- [Dataminr & Crisis24 파트너십](https://www.prnewswire.com/news-releases/dataminr-and-crisis24-announce-strategic-partnership): 2025년
- [Reddit B2B 영향력](https://getathenic.com/blog/community-led-growth-reddit-discord-forums-revenue): 75% 구매 결정 영향
- [SaaS 콘텐츠 마케팅 2026](https://www.seriesxmarketing.com/blog/content-marketing-trends/): 인터랙티브 2배 전환
- [솔로 파운더 벤치마크](https://www.bannerbear.com/journey-to-10k-mrr/): $10K MRR까지 2년

**뉴스레터 시장:**
- [OSINT Newsletter](https://osintnewsletter.com/): 26,000+ 구독자
- [SpyTalk Substack](https://www.spytalk.co/): 지정학/정보기관 뉴스레터
- [Geopolitical Dispatch](https://geopoliticaldispatch.substack.com/): 2,000+ 구독자
- [스티비](https://stibee.com/): 한국 뉴스레터 플랫폼 (수수료 0%)

---

> **한 줄 요약**: "아웃바운드 세일즈를 멈추고, 커뮤니티를 만들고, 뉴스레터를 팔아라.
> Shodan처럼 제품이 세일즈맨이 되게 하고, LiveUAMap처럼 위기를 성장 엔진으로 써라.
> EQLIM/PeaceTech처럼 죽지 않으려면, 첫 $29부터 빨리 벌어라."

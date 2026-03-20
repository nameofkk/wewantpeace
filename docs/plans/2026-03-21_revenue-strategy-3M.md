# WeWantPeace 월 300만원 수익 달성 전략 — 완전판

> 작성: 2026-03-21 | 현재 가격: Pro $3.90/월, Pro+ $6.90/월 (USD, DodoPayments)
> 목표: 월 ₩3,000,000 (≈$2,100) MRR

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
| **S&P Global 지정학 리스크** | 엔터프라이즈 커스텀 | 금융기관 | 지정학 리스크 스코어링 |
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
| CRM/리드 추적 | ❌ 미구현 | B2B 영업 파이프라인 |
| 코호트 분석/이탈 예측 | ❌ 미구현 | 데이터 기반 최적화 |

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

---

## Part 2. 매출 전략 — 3개 축

### 전체 구조

```
                    ┌─────────────────────────────────────┐
                    │       월 300만원 (≈$2,100) MRR       │
                    └───────────┬─────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
  축 1: B2B 기관          축 2: 유료 API          축 3: 개인 구독
  월 ₩1,200,000          월 ₩900,000           월 ₩900,000
  ARPU $99~349           ARPU $29~299          ARPU $3.90~6.90
  고객 3~5곳             고객 5~8곳             구독자 60~85명
```

---

## Part 3. 축 1: B2B 기관 구독 — 상세 판매 전략

### 3.1 신설 플랜

| 플랜 | 가격 | 시트 | API | 기능 |
|------|------|------|-----|------|
| **Team** | $49/월 | 5명 | 1,000콜/일 | Pro+ 전체 + CSV 내보내기 + 팀 공유 대시보드 |
| **Business** | $149/월 | 20명 | 10,000콜/일 | Team + 웹훅 알림 + 전담 온보딩 + 커스텀 알림 규칙 |
| **Enterprise** | $349/월 | 무제한 | 무제한 | Business + SLA 99.5% + 전용 지원 + 데이터 피드 |

**가격 근거:**
- Dataminr 대비 1/200 ~ 1/30 → "가격 대비 최고 가치" 포지셔닝
- geoconflicts API (RapidAPI) $99/월 대비 동일 가격에 66배 더 많은 소스
- 대학/NGO 예산 범위: 연간 $600~$4,200 → 일반 연구 도구 예산으로 충분히 결재 가능

### 3.2 타겟 바이어 — 구체적 회사/기관명

#### Tier A: 이번 달 즉시 접근 (ACV $600~$2,000)

**1) 한국 대학 국제관계학과**
| 대학 | 학과/프로그램 | 접근법 |
|------|-------------|--------|
| 서울대 | 정치외교학부, 국제대학원 | 교수 이메일 직접 |
| 연세대 | 정치외교학과, 국제학대학원(UIC) | 교수 이메일 + 조교 경유 |
| 고려대 | 정치외교학과, 국제대학원 | 교수 이메일 직접 |
| KAIST | 과학기술정책대학원 | 교수 이메일 직접 |
| 이화여대 | 국제학부 | 교수 이메일 직접 |
| 한국외대 | 국제관계학과 | 교수 이메일 직접 |
| 경희대 | 국제학부, 평화복지대학원 | 교수 이메일 직접 (평화 연구 특화) |

**접근 이메일:**
```
제목: 수업/연구용 실시간 분쟁 데이터 플랫폼 소개 (195개국)

교수님 안녕하세요,

[학과명]에서 국제관계/안보를 가르치시는 것을 알게 되어 연락드립니다.

저는 WeWantPeace라는 실시간 글로벌 분쟁 모니터링 플랫폼을
개발·운영하고 있습니다.

- 195개국, 66개 데이터소스 (RSS, Telegram, GDELT, ACLED)
- 5분 간격 실시간 업데이트
- AI 기반 이슈 클러스터링 + 국가별 긴장도 지수(0~100)
- 한국어/영어 이중 언어 지원

수업에서 학생들이 실시간으로 글로벌 분쟁 상황을 추적하고
분석하는 도구로 활용하시면 좋을 것 같습니다.

Academic Team 플랜(5인, 월 $49)을 1학기 무료로 제공해 드리겠습니다.
관심 있으시면 15분 정도 온라인 데모를 보여드릴 수 있습니다.

www.wewantpeace.live

감사합니다.
[이름]
```

**2) OSINT 프리랜서/컨설턴트**
- 접근: Reddit r/OSINT, X #OSINT, Bellingcat Discord
- 이들은 개인이지만 Pro/Pro+ $6.90은 도구 비용으로 즉시 결제 가능
- 이들이 클라이언트(기업)에게 우리 도구를 추천 → B2B 리드 파이프라인

**3) 정치 리스크 컨설팅 소형 펌**
- 한국: 한반도평화연구원, 세종연구소, 아산정책연구원 등
- 해외: Control Risks, Eurasia Group 같은 대형은 나중에, 소형 부티크 펌부터
- LinkedIn 검색: "Political Risk Consultant" OR "Geopolitical Analyst"

**4) 외국계 기업 한국 지사 안전팀**
- 타겟 직함: "Regional Security Manager", "Travel Security", "Global Safety"
- LinkedIn 검색: site:linkedin.com "security manager" "Korea"
- 이들은 기존에 Crisis24나 International SOS를 쓰는데 연 수천만원 → 우리 $149/월이면 부서 예산으로 바로 결재

#### Tier B: 1~3개월 내 접근 (ACV $2,000~$4,200)

| 타겟 | 구체적 회사/기관 | 의사결정자 직함 | 접근법 |
|------|-----------------|---------------|--------|
| 글로벌 기업 안전팀 | 삼성, LG, 현대, SK, 포스코 (해외 공장/주재원) | VP Global Security, 해외안전팀장 | LinkedIn + 소개 |
| 보험 브로커 | 한화손보, DB손보, 삼성화재 (해외보험팀) | 정치 리스크 언더라이터 | 콜드이메일 + 웨비나 |
| NGO 한국 사무소 | UNHCR 한국, MSF 한국, Save the Children | 프로그램 매니저, 안전담당 | 직접 방문/이메일 |
| 언론사 국제부 | 조선, 중앙, 동아, KBS, MBC, JTBC | 국제부 데스크/부장 | 기자 이메일 → 데스크 소개 요청 |
| 여행사/항공사 | 하나투어, 모두투어, 대한항공, 아시아나 | 안전관리팀 | 콜드이메일 |

#### Tier C: 3~6개월 장기 (ACV $4,200+)

| 타겟 | 왜 돈을 내는가 | 예상 가격 |
|------|---------------|----------|
| Fortune 500 글로벌 리스크팀 | Dataminr 대안 (1/100 가격) | Enterprise $349/월+ |
| 정부기관 (국방/외교) | 100+ 미국 정부기관이 Dataminr 사용 중 | 커스텀 |
| 대형 보험사 (Lloyd's 신디케이트) | Political Risk Insurance 데이터 | Enterprise $349/월+ |
| 국제기구 (UN, World Bank) | 분쟁 모니터링 | 커스텀 |

### 3.3 판매 채널 상세

#### Channel 1: LinkedIn 아웃리치

**도구:** LinkedIn 무료 or Sales Navigator ($99/월)
- Sales Navigator 사용 시: 연결 수락률 30% → 68% (인텐트 기반), 5배 파이프라인
- 무료로 시작해서 첫 계약 후 업그레이드 가능

**프로필 최적화:**
```
이름: [본명]
헤드라인: Founder @ WeWantPeace | Real-time Conflict Intelligence for 195 Countries
          — 99% cheaper than Dataminr

About:
🚨 2024년 12월 3일, 한국에 계엄이 선포됐을 때
경보 소리에 잠에서 깬 그 공포를 기억합니다.

그때 깨달았습니다 — 전쟁과 분쟁은 "뉴스"가 아니라
내 삶에 직접 영향을 미치는 "위험"이라는 것을.

그래서 만들었습니다:
✅ 195개국, 66개 데이터소스, 5분 간격 실시간 모니터링
✅ AI 기반 이슈 클러스터링 + 국가별 긴장도 지수
✅ 위성 화재 감지, GPS 교란, 인터넷 장애 인텔 레이어
✅ 한국어/영어 이중 언어

Dataminr이 월 $10,000+ 하는 걸, 우리는 $49/월부터.

👉 www.wewantpeace.live
📩 DM으로 14일 무료 체험 요청하세요

#ConflictIntelligence #GeopoliticalRisk #OSINT #SecurityIntelligence
```

**아웃리치 시퀀스 (주 30~50명, 5단계):**

**Day 1 — 연결 요청:**
```
안녕하세요 [이름]님, [회사]에서 [직함]으로 계신 걸 보고
연결 요청 드립니다. 글로벌 리스크 모니터링 분야에서
일하고 있습니다.
```

**Day 3 — 연결 수락 후 첫 메시지 (가치 제공):**
```
연결 감사합니다!

혹시 [회사]에서 해외 사업장이나 출장자 안전 관리는
어떻게 하고 계신지 궁금합니다.

저는 WeWantPeace라는 195개국 실시간 분쟁 모니터링
플랫폼을 만들고 있는데요, 66개 데이터소스를 5분 간격으로
수집해서 긴장도 지수와 AI 분석을 제공합니다.

Dataminr이 월 $10,000+인데, 저희는 팀 플랜 $49/월입니다.
14일 무료 체험 가능한데, 관심 있으시면 링크 보내드릴까요?
```

**Day 7 — 팔로업 1 (최근 이벤트 활용):**
```
[최근 실제 분쟁 이벤트 — 예: "어제 미얀마 전투 격화"]
관련해서, 저희 플랫폼이 [구체적 데이터 — 예: "미얀마
긴장도가 72 → 89로 급등"]한 것을 [시간 — 예: "발생 12분 후"]에
감지했습니다.

이런 데이터가 [회사] 리스크 관리에 도움이 될 것 같아서요.
혹시 15분 정도 데모 보실 의향 있으신가요?
```

**Day 14 — 팔로업 2 (케이스 스터디):**
```
바쁘신 거 이해합니다. 참고로 저희 플랫폼 한 가지만
공유드립니다:

[구체적 수치 — 예: "지난 30일간 195개국에서 12,000건의
이벤트를 수집하고 340개 이슈로 클러스터링했습니다.
긴장도 급등 국가는 [국가1], [국가2], [국가3]이었습니다."]

이 데이터를 무료로 체험해보실 수 있습니다:
www.wewantpeace.live
```

**Day 21 — 마지막 (깔끔한 마무리):**
```
[이름]님, 몇 번 연락드렸는데 바쁘신 것 같습니다.

혹시 주변에 글로벌 리스크 모니터링에 관심 있는
동료분이 계시면, 이 메시지를 포워드해 주시면
감사하겠습니다.

좋은 하루 보내세요!
```

**LinkedIn 벤치마크 (2025~2026 데이터):**
- 연결 수락률: 일반 30%, Sales Navigator 인텐트 기반 68%
- 답변율: 일반 15%, 멀티채널(이메일 병행) 시 50%까지
- 주 50명 접근 → 월 200명 → 30~60명 답변 → 5~10명 데모 → 2~4명 전환
- **80%의 세일즈가 5회 이상 팔로업 필요, 92%가 4번째에 포기 — 이 갭이 기회**

#### Channel 2: 콜드이메일

**도구:** Instantly.ai ($47/월) — 무제한 발송 계정, 빌트인 웜업, 4.5억+ 연락처 DB
- 대안: Smartlead ($39/월), Lemlist ($59/월)
- **필수**: SPF, DKIM, DMARC 설정 (2025년부터 딜리버리 기준 더 엄격)

**기존 보유 자산: 1,198명 기자 이메일 + 콜드이메일 3종 템플릿**
→ 기자 개인이 아니라 **소속사 국제부 데스크**에 팀 플랜 제안으로 전환

**이메일 시퀀스 (5통, 21일):**

**Email 1 (Day 0) — 가치 제안:**
```
제목: [언론사] 국제부를 위한 실시간 분쟁 인텔리전스 도구

[이름] 기자님 안녕하세요,

[최근 실제 분쟁 뉴스 — 예: "미얀마 내전 확대 보도"]를
보도하신 기사 잘 봤습니다.

저는 WeWantPeace라는 195개국 실시간 분쟁 모니터링 플랫폼을
운영하고 있습니다.

• 66개 글로벌 소스 (RSS, Telegram 채널, GDELT, ACLED, UCDP)
• 5분 간격 실시간 수집
• AI가 자동 분류·클러스터링 → 국가별 긴장도 지수(0~100)
• 위성 화재 감지(FIRMS), GPS 교란, 인터넷 장애 인텔 레이어
• 한국어/영어 이중 언어

국제부 취재에 도움이 될 수 있을 것 같아 연락드립니다.
14일 무료 팀 체험(5인)을 제공하고 있는데, 관심 있으시면
답장 주시겠어요?

www.wewantpeace.live

감사합니다.
[이름]
WeWantPeace 대표
```

**Email 2 (Day 3) — 구체적 데이터:**
```
제목: Re: 실시간 분쟁 인텔리전스 도구

[이름] 기자님,

지난 메일 관련해서, 참고로 저희 플랫폼이
[최근 구체적 이벤트 — 예: "수단 파라메군 RSF의
엘파셔 공세"]를 [시간 — 예: "발생 8분 후"] 감지했습니다.

[첨부 스크린샷: 긴장도 그래프 + 이슈 타임라인]

이런 데이터를 국제부에서 실시간으로 활용하시면,
속보 경쟁에서 상당한 우위를 가지실 수 있습니다.
```

**Email 3 (Day 8) — 소셜 프루프:**
```
제목: Disquiet Bronze 배지 + 195개국 커버리지

[이름] 기자님,

혹시 바쁘신 거라면 간단히만 —

• Disquiet(한국 스타트업 커뮤니티) Bronze 배지 획득
• 한국어·영어 이중 언어 완전 지원
• PWA + Android 앱 + 토스 앱인토스 등록
• 1인 개발자가 기획부터 운영까지 전담

15분 데모면 충분합니다.
편하신 시간 말씀해주시면 맞추겠습니다.
```

**Email 4 (Day 14) — 문제 프레이밍:**
```
제목: 국제부가 분쟁 소식을 놓치는 이유

[이름] 기자님,

국제부 기자분들과 이야기해보면, 가장 큰 고충이
"주요 분쟁 외의 소규모 이슈를 놓치는 것"이라고 합니다.

WeWantPeace는 195개국의 모든 분쟁·안보 이슈를
자동으로 수집·분류합니다.
"놓친 이슈"가 없어집니다.

혹시 이런 문제를 겪고 계시다면,
답장 한 줄만 주시면 체험 계정을 바로 보내드리겠습니다.
```

**Email 5 (Day 21) — 마지막 + 포워드 요청:**
```
제목: 마지막으로 한번만 여쭤볼게요

[이름] 기자님,

이 주제에 관심이 없으시다면 전혀 문제 없습니다.
더 이상 이메일 보내지 않겠습니다.

혹시 국제부 내에서 이런 도구에 관심 가질 분이 계시면
이 메일을 포워드해 주시면 감사하겠습니다.

좋은 취재 하세요!
```

**콜드이메일 벤치마크 (2025~2026 SaaS/Tech):**
- 오픈율: 35~45%
- 답변율: 3~8%
- 80%의 세일즈가 5회 이상 팔로업 필요
- 1,198명 × 5% 답변 = ~60명 관심
- 60명 중 데모 수락: ~15명
- 15명 중 전환: ~5명 (개인 Pro/Pro+)
- 그 중 소속사 팀 플랜 전환: ~1~2곳

**멀티채널 (LinkedIn + Email 동시):**
- 단일 채널 대비 50% 높은 인게이지먼트
- 시퀀스: LinkedIn 연결 요청 → 24시간 후 이메일 → 3일 후 LinkedIn 메시지 → 5일 후 이메일 팔로업

#### Channel 3: 커뮤니티 마케팅

**3-A. Reddit (가장 높은 B2B ROI)**

Reddit이 B2B 구매 결정의 75%에 영향을 미침 (2025 데이터).
2025 Q4 Reddit "Community-First" 알고리즘은 교육적 콘텐츠에 300% 더 좋은 결과.

**타겟 서브레딧:**

| 서브레딧 | 멤버 수 | 포스트 전략 | 셀프 프로모 규칙 |
|---------|--------|-----------|----------------|
| r/OSINT | 180K+ | 도구 소개 + 피드백 요청 | 허용 (가치 제공 시) |
| r/geopolitics | 900K+ | 데이터 분석 포스트 (도구는 출처로만) | 직접 홍보 금지, 분석 콘텐츠만 |
| r/dataisbeautiful | 21M+ | 긴장도 히트맵 시각화 [OC] | 직접 홍보 금지, 시각화만 |
| r/supplychain | 50K+ | 공급망 리스크 데이터 분석 | 가치 제공 시 허용 |
| r/SecurityAnalysis | 300K+ | 지정학 리스크 → 투자 시그널 분석 | 분석 위주 |
| r/sideproject | 100K+ | 1인 개발자 프로젝트 소개 | 허용 |
| r/SaaS | 50K+ | 성장 전략 공유 + 도구 소개 | 허용 |

**r/OSINT 포스트 (완성본):**
```
제목: I built a free real-time conflict monitor covering
      195 countries with 66 data sources — looking for
      OSINT community feedback

본문:
Hey r/OSINT,

I'm a solo developer from South Korea. After the martial law
scare in December 2024 (woke up to emergency alerts at 1am),
I realized there was no affordable tool for regular people to
monitor global conflicts in real-time.

So I built WeWantPeace. Here's what it does:

**Data Collection (every 5 minutes):**
- 66 sources: RSS feeds from Reuters, AP, Al Jazeera, etc.
- Telegram channels (conflict-specific)
- GDELT (Global Database of Events)
- ACLED (Armed Conflict Location & Event Data)
- UCDP (Uppsala Conflict Data Program)

**Analysis:**
- AI (GPT-4o-mini) clusters related events into issues
- Per-country Tension Index (0-100) calculated in real-time
- Personalized KScore (how much a conflict affects YOU)

**Intel Layers:**
- FIRMS satellite fire detection
- GPS jamming zones
- Internet outage monitoring
- Trade disruption signals

**What makes it different from LiveUAMap or similar:**
- Covers ALL 195 countries (not just Ukraine/Middle East)
- Quantified tension scores, not just pins on a map
- Free tier: full map + 5 daily alerts
- Korean + English bilingual

I'm working on a public API next — would be great for OSINT
researchers and developers.

Free at: https://www.wewantpeace.live

Would love your feedback, especially:
1. What data sources am I missing?
2. What features would make this useful for your OSINT work?
3. Any UX improvements?

Happy to answer any technical questions about the stack
(Next.js + FastAPI + Celery + PostgreSQL).
```

**r/geopolitics 포스트 (데이터 분석):**
```
제목: [OC] I tracked tension levels across 195 countries
      for 3 months — here are the most volatile regions
      right now

본문:
[시각화: 세계 지도 긴장도 히트맵 스크린샷]

I've been running a conflict monitoring platform that
collects data from 66 sources every 5 minutes. Here's
what 3 months of data shows:

**Top 10 Most Volatile Countries (Q1 2026):**
[실제 데이터 테이블]

**Key Trends:**
1. [트렌드 1 — 실제 데이터 기반]
2. [트렌드 2]
3. [트렌드 3]

**Methodology:**
- Tension Index combines event frequency, severity,
  source diversity, and historical baseline
- 66 sources including GDELT, ACLED, Telegram, RSS
- Updated every 5 minutes

Data source: WeWantPeace (www.wewantpeace.live) —
a project I built as a solo developer.

What patterns are you seeing in your analysis?
```

**3-B. Telegram OSINT 커뮤니티**
- Conflict News 관련 채널에 도구 소개
- OSINT 학습/공유 그룹 참여
- 자체 Telegram 채널 운영 (SNS 자동발행 코드 이미 완성)

**3-C. Discord/Slack**
- Bellingcat 커뮤니티 — OSINT 전문가 집단
- OSINT Curious Discord — OSINT 학습/공유
- Data Engineering Slack — API 데이터 소비자
- Indie Hackers — SaaS 파운더 네트워크

**3-D. 한국 커뮤니티**
- 디스콰이엇: 메이커로그 주 1회 (이미 Bronze 배지 보유)
- GeekNews (긱뉴스): Show HN 스타일 포스트
- 커리어리: 1인 개발자 + 분쟁 모니터링 스토리
- 블라인드/리멤버: IT 직장인 타겟 (분쟁이 경제에 미치는 영향 프레임)

---

## Part 4. 축 2: 유료 API — 상세 전략

### 4.1 구현 필요 사항 (코드)

| 항목 | 설명 | 우선순위 |
|------|------|---------|
| API 키 발급/관리 | 유저별 API 키 생성, 활성화/비활성화, 사용량 추적 | P0 |
| Rate Limiting | 티어별 일일 콜 제한 (Redis 기반) | P0 |
| API 문서 | FastAPI 내장 Swagger/Redoc + 별도 랜딩페이지 | P0 |
| 사용량 대시보드 | 유저가 자기 API 사용량 확인 | P1 |
| 웹훅 시스템 | 긴장도 급등, 신규 클러스터 시 POST 콜백 | P1 |
| RapidAPI 프록시 | RapidAPI 요청을 우리 API로 라우팅 | P1 |

### 4.2 API 엔드포인트 설계

```
# 기본 이벤트
GET /api/v1/events                     — 실시간 이벤트 목록 (필터: country, topic, severity, since)
GET /api/v1/events/{id}                — 이벤트 상세

# 이슈 클러스터
GET /api/v1/clusters                   — AI 클러스터링된 이슈 목록
GET /api/v1/clusters/{id}              — 이슈 상세 + 타임라인

# 긴장도
GET /api/v1/tension                    — 전체 국가 긴장도 현황
GET /api/v1/tension/{country_code}     — 국가별 긴장도 + 히스토리
GET /api/v1/tension/history            — 긴장도 시계열 데이터

# 인텔 시그널 (Pro API 이상)
GET /api/v1/signals/firms              — 위성 화재 감지
GET /api/v1/signals/gps-jam            — GPS 교란
GET /api/v1/signals/outage             — 인터넷 장애

# 웹훅 (Pro API 이상)
POST /api/v1/webhooks                  — 웹훅 등록
DELETE /api/v1/webhooks/{id}           — 웹훅 삭제
```

### 4.3 API 가격 티어

| 티어 | 가격 | 일일 콜 | 엔드포인트 | 부가 기능 |
|------|------|--------|-----------|----------|
| **Free API** | $0/월 | 100 | events, clusters, tension (기본) | 리드 획득용 |
| **Starter** | $29/월 | 500 | 전체 기본 + 필터링 | 이메일 지원 |
| **Pro API** | $99/월 | 5,000 | 전체 + 인텔 시그널 | 웹훅 + 히스토리 |
| **Enterprise** | $299/월 | 무제한 | 전체 + 스트리밍 | SLA 99.5% + 전용 지원 |

**가격 근거:**
- RapidAPI geoconflicts API: $9~99/월 (단일 UCDP 소스)
- 우리: 66개 소스, 5분 실시간 → 동일 가격에 66배 가치
- Enterprise $299/월 = Dataminr $10,000/월의 3%

### 4.4 API 판매 채널

**1) RapidAPI (즉시)**
- 수수료: 25%
- 장점: 기존 개발자 풀, 검색 트래픽, 결제 인프라
- 단점: 높은 수수료
- **등록 즉시 가능** — API만 구현하면 됨
- 예상: 첫 3개월 $200~500/월 → 6개월 $500~1,500/월

**2) 직접 API (DodoPayments)**
- 수수료: 2.9%만
- API 키 발급 페이지 + Swagger 문서 + SEO
- 장기적으로 메인 채널

**3) AWS Data Exchange**
- 수수료: ~20%
- 장점: 엔터프라이즈 바이어 접근, 기존 AWS 결제
- 단점: 심사 까다로움
- 중기 목표 (3~6개월)

**4) Datarade**
- 데이터 바이어 전용 마켓플레이스
- 리드 기반 (직접 클로징 필요)
- ACLED도 여기 등록되어 있음

### 4.5 API SEO 전략

**타겟 키워드:**
```
"geopolitical risk API" — 검색량 낮지만 전환율 극고
"conflict data API" — 개발자 타겟
"ACLED alternative API" — 경쟁사 트래픽 가로채기
"Dataminr alternative" — 고가치 키워드
"real-time conflict monitoring API" — 롱테일
"country risk score API" — 핀테크/보험 타겟
```

**비교 SEO 콘텐츠 (높은 전환):**
```
1. "Dataminr vs WeWantPeace: 99% Cheaper Alternative for
    Real-time Conflict Monitoring"
   → 타겟: Dataminr 가격에 놀란 기업

2. "ACLED Data API Alternatives for Commercial Use (2026)"
   → 타겟: ACLED 상업 라이선스 비용에 놀란 연구자

3. "Top 5 Geopolitical Risk APIs for Developers (2026 Guide)"
   → 타겟: 지정학 데이터 통합하려는 개발자

4. "How to Monitor Global Conflicts Without $10K/month"
   → 타겟: 예산 부족한 기업/연구기관

5. "Building a Supply Chain Risk Dashboard with Free
    Conflict Data"
   → 타겟: 공급망 SaaS 개발자 (튜토리얼)
```

이 콘텐츠를 `wewantpeace.live/blog/` 경로에 SSR 페이지로 만들면 SEO + API 전환 동시 달성.

### 4.6 API 매출 시뮬레이션

| 기간 | RapidAPI | 직접 API | 합계 |
|------|---------|---------|------|
| Month 1~3 | $100~300 | $0~100 | $100~400 |
| Month 4~6 | $300~700 | $200~500 | $500~1,200 |
| Month 7~12 | $500~1,000 | $500~1,500 | $1,000~2,500 |

---

## Part 5. 축 3: 개인 구독 전환율 개선 — 코드 변경 상세

### 5.1 Free 제한 강화

**현재 Free 유저가 무료로 쓰는 것:**
- ✅ 실시간 이슈 지도 전체 접근
- ✅ 이슈 상세 페이지 무제한 열람
- ✅ 커뮤니티 전체 접근
- ✅ 일일 5건 알림
- ✅ 7일 히스토리
- ✅ 글로벌 트렌딩
- ✅ 영향 흐름도
- ✅ 종합 영향도

→ **핵심 가치를 전부 무료로 소비 가능. 업그레이드 동기 없음.**

**변경안:**
| 기능 | 현재 Free | 변경 후 Free | Pro |
|------|----------|------------|-----|
| 이슈 상세 열람 | 무제한 | **하루 5건** (초과 시 페이월) | 무제한 |
| 홈 피드 | 무제한 | 5건 후 **"더 보기 → Pro"** 카드 | 무제한 |
| 타임라인 이벤트 | 전체 | **최근 3건만** (나머지 blur) | 전체 |
| 브리핑 | 전체 | **상위 3건** (나머지 잠금) | 전체 |
| 알림 소진 시 | 안내 없음 | **"Pro면 20건" 인앱 메시지** | - |

**구현 파일:**
- `frontend/lib/store.ts` — 열람 카운터 (localStorage)
- `frontend/components/ui/PaywallModal.tsx` — 신규 트리거 추가
- `frontend/app/(main)/issues/[id]/page.tsx` — 열람 제한 체크
- `frontend/app/(main)/home/page.tsx` — 피드 카드 삽입

### 5.2 페이월 트리거 추가

**현재 4개 → 변경 후 8~10개:**

| 트리거 | 발동 조건 | 위치 | 예상 노출 빈도 |
|--------|----------|------|--------------|
| (기존) verified_locked | 설정에서 토글 | 설정 | 낮음 |
| (기존) kscore_threshold | KScore 조정 | 설정 | 낮음 |
| (기존) country_limit | 3번째 국가 | 설정 | 중간 |
| (기존) intel_locked | 인텔 5초 | 지도 | 중간 |
| **(신규) issue_detail_limit** | 하루 5건 초과 | 이슈 상세 | **높음** |
| **(신규) timeline_locked** | 3건 이후 blur | 이슈 상세 | **높음** |
| **(신규) briefing_locked** | 3건 이후 잠금 | 홈 브리핑 | **높음** |
| **(신규) feed_upgrade_card** | 5번째 카드 후 | 홈 피드 | **높음** |
| **(신규) alert_exhausted** | 5건 소진 시 | 푸시/인앱 | 중간 |
| **(신규) intel_signal_cta** | 이슈 하단 | 이슈 상세 | **높음** |

### 5.3 트라이얼 → 유료 전환 자동화

**현재: 트라이얼 종료 후 아무 액션 없음.**

구현할 자동화 시퀀스:

| 시점 | 액션 | 채널 | 메시지 |
|------|------|------|--------|
| D-2 (만료 2일 전) | 알림 | 푸시 + 이메일 | "Pro 체험이 2일 후 종료됩니다. 지금 구독하면 끊김 없이 이용하세요." |
| D-1 (만료 1일 전) | 알림 | 푸시 | "내일 Pro 기능이 비활성화됩니다. 마지막 기회!" |
| D-day (만료일) | 인앱 모달 | 앱 내 | "Pro 체험이 종료됐습니다. [구독하기] [나중에]" + 첫 달 20% 할인 |
| D+3 (만료 3일 후) | 리마인더 | 이메일 | "Pro를 사용하시던 [기능들]이 Free로 제한됐습니다. 다시 활성화하세요." |
| D+7 (만료 7일 후) | 윈백 | 이메일 | "다시 돌아오세요! 첫 달 30% 할인 코드: COMEBACK30" |
| D+14 (만료 14일 후) | 마지막 | 이메일 | "마지막 제안: Pro 첫 달 $2.73 (30% 할인). [구독하기]" |

**구현:**
- `worker/tasks/trial_expiry.py` (신규) — 매일 1회 만료 임박 유저 조회 → 푸시/이메일 발송
- `backend/app/routers/subscriptions.py` — 만료 시 인앱 모달 트리거 플래그
- `frontend/components/ui/TrialExpiredModal.tsx` (신규) — 만료 인앱 모달

### 5.4 연간 플랜 추가

| 플랜 | 월간 | 연간 | 할인율 | 월 환산 |
|------|------|------|--------|--------|
| Pro | $3.90/월 | $35/년 | 25% | $2.92/월 |
| Pro+ | $6.90/월 | $62/년 | 25% | $5.17/월 |

**효과:**
- 선결제 → 즉시 매출 (Pro 연간 1건 = Pro 월간 9개월분)
- LTV 증가 (연간 갱신율 > 월간 갱신율)
- 이탈률 감소 (1년 약정)

**구현:**
- DodoPayments에 연간 상품 추가
- `frontend/app/(main)/upgrade/client.tsx` — 월간/연간 토글
- `backend/app/routers/subscriptions.py` — 연간 플랜 처리

---

## Part 6. 콘텐츠 마케팅 — 전환을 만드는 콘텐츠

### 6.1 데이터 주도 무료 보고서 (가장 높은 전환)

**보고서 1: "2026 Q1 Global Conflict Risk Index: 195 Countries Ranked"**
- 형식: PDF (20~30페이지), 이메일 게이팅 (다운로드 시 이메일 수집)
- 내용: 국가별 긴장도 순위 + 주요 이슈 분석 + 트렌드
- 타겟: 기업 리스크 관리자, 컨설턴트, 연구자
- SEO: "country risk ranking 2026", "global conflict index" 키워드
- **데이터는 이미 다 있음** — DB에서 쿼리해서 시각화만 하면 됨

**보고서 2: 지역별 딥다이브 (월간)**
```
"Middle East Tension Monitor: March 2026"
"Southeast Asia Conflict Tracker: March 2026"
"Africa Security Index: March 2026"
```
- 각 보고서에 WeWantPeace 데이터 출처 명시
- 무료 배포 → 이메일 리스트 구축 → 유료 전환

### 6.2 인터랙티브 무료 도구 (Product-Led Growth)

2026년 SaaS 마케팅 트렌드: 인터랙티브 콘텐츠가 정적 콘텐츠 대비 2배 전환.

**도구 1: Country Risk Checker (구현 간단)**
```
https://www.wewantpeace.live/risk-check

[국가 선택 드롭다운]
→ 현재 긴장도 점수 + 최근 이슈 3건 + 30일 트렌드 그래프
→ "더 자세한 분석은 Pro에서" CTA
→ "이 데이터를 API로 받으세요" CTA
```

**도구 2: Supply Chain Risk Map (중기)**
```
https://www.wewantpeace.live/supply-chain-risk

[제조 거점 국가 3개 입력]
→ 각 국가 리스크 히트맵 + 상호 영향 분석
→ "팀 플랜으로 실시간 모니터링" CTA
```

**도구 3: Travel Safety Alert (간단)**
```
https://www.wewantpeace.live/travel-safety

[여행 목적지 선택]
→ 현재 위험도 + 최근 이슈 + 권고사항
→ "Pro 알림으로 여행 중 실시간 업데이트" CTA
```

### 6.3 뉴스레터 — "Conflict Intelligence Brief"

**플랫폼:** Substack or Beehiiv (무료)
**빈도:** 주 1회 (매주 월요일)
**내용:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Conflict Intelligence Brief #001
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 이번 주 TOP 5 이슈
1. [이슈 1] — 긴장도 변화, 영향
2. [이슈 2]
...

📈 긴장도 급등 국가
[국가 + 수치 + 원인]

🗺 이번 주 지도 하이라이트
[스크린샷 + 분석]

📌 이 데이터는 WeWantPeace에서 자동 수집됩니다.
   실시간으로 모니터링하세요: www.wewantpeace.live

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**목표:** 3,000 구독자 시 전환 시작 (2~3% → 60~90명 유료)

### 6.4 X(Twitter) #BuildInPublic 쓰레드

**7일 쓰레드 시리즈 (전략 문서 `x-buildinpublic-threads.md` 기존 보유):**

Day 1: "2024년 12월 3일 새벽 1시, 경보 소리에 잠에서 깼다..."
Day 2: "66개 데이터소스를 5분마다 수집하는 시스템을 혼자 만들었다"
Day 3: "AI가 뉴스를 분류하고 긴장도를 계산하는 방법"
Day 4: "위성 데이터로 전쟁을 감지하는 3가지 방법 (FIRMS, GPS, Internet)"
Day 5: "1인 개발자가 195개국을 모니터링하는 기술 스택"
Day 6: "Dataminr은 $10K/월인데 나는 $3.90에 팔고 있다"
Day 7: "다음 목표: B2B API + 기관 플랜"

---

## Part 7. Product Hunt / Show HN

### 7.1 Product Hunt 준비

**사전 준비 (4주):**
- PH 커뮤니티 활동: 매일 다른 제품 업보트 + 댓글 2~3개
- Hunter 섭외: 팔로워 1,000+ PH 유저에게 DM
- 에셋 준비: 로고, 갤러리 이미지 5장, 30초 동영상 데모

**런칭 전략:**
- 타이밍: 화~목, 미국 동부 00:01 (한국 14:01)
- 제목: "WeWantPeace — Real-time conflict monitor for 195 countries"
- 태그라인: "Know before it hits the news. 66 data sources, 5-minute updates."

**런칭 당일:**
- X, Telegram, Discord, 디스콰이엇 동시 홍보
- 첫 1시간 100+ 업보트가 핵심 (친구/커뮤니티 동원)
- 모든 댓글에 10분 내 답변

**벤치마크:** Product Hunt Top 5 시 1,000~5,000 방문 → 3~5% 가입 → 30~250 신규 유저

### 7.2 Show HN

**이전 게시물 삭제 이슈 해결 확인 필요 (모더레이터 이메일)**

**포스트:**
```
제목: Show HN: I built a real-time global conflict monitor
      after Korea's martial law scare

본문:
After waking up to emergency alerts during South Korea's
martial law declaration in Dec 2024, I built a platform
that monitors conflicts across 195 countries.

Technical details:
- 66 data sources (RSS, Telegram, GDELT, ACLED, UCDP)
- 5-minute update cycle via Celery workers
- AI (GPT-4o-mini) clusters events into issues
- Per-country Tension Index (0-100) calculated in real-time
- Stack: Next.js 14, FastAPI, PostgreSQL, Redis, Celery

Intel layers:
- NASA FIRMS satellite fire detection
- GPS jamming monitoring
- Internet outage tracking

Free tier includes full map access and 5 daily alerts.
Working on a public API for developers.

https://www.wewantpeace.live

Solo developer, happy to answer questions about the
architecture or data pipeline.
```

**타이밍:** 미국 동부 오전 9~10시, 화~목
**벤치마크:** HN 프론트 페이지 시 2,000~10,000 방문

---

## Part 8. 현실적 타임라인 & 매출 시뮬레이션

### 8.1 솔로 파운더 벤치마크 (2025~2026 데이터)

| 사례 | 첫 $1K MRR | 첫 $10K MRR | 방법 |
|------|-----------|-------------|------|
| Bannerbear | 6개월 | 2년 | 콘텐츠 + SEO + API |
| Unicorn Platform | 3개월 | 1년 | Product Hunt + 콘텐츠 |
| Plausible | 4개월 | 18개월 | HN + Reddit + 프라이버시 포지셔닝 |
| 평균 (기존 오디언스 없음) | 3~6개월 | 18~24개월 | 다양 |

**WeWantPeace 조건:**
- 제품: ✅ 이미 완성 (이게 가장 큰 장점)
- 오디언스: 소규모 (기존 유저 있지만 적음)
- 운영: 파트타임 (사이드 프로젝트)
- 가격: B2B 티어 추가 예정

### 8.2 월별 상세 로드맵

**Month 1 (즉시 실행)**

| 주차 | 코드 작업 | 영업/마케팅 | 예상 매출 |
|------|----------|-----------|----------|
| Week 1 | 페이월 트리거 추가, Free 제한 강화 | LinkedIn 프로필 최적화, 첫 r/OSINT 포스트 | ₩0 |
| Week 2 | API 키 발급 시스템 구축 | 기자 콜드이메일 1차 (500명), LinkedIn 아웃리치 시작 | ₩0~50,000 |
| Week 3 | RapidAPI 등록, Swagger 문서 | 기자 콜드이메일 팔로업, r/geopolitics 포스트 | ₩50,000~100,000 |
| Week 4 | 연간 플랜 추가, 트라이얼 만료 알림 | 기자 콜드이메일 2차 (나머지 698명), 디스콰이엇 | ₩100,000~200,000 |

**Month 2**

| 주차 | 코드 작업 | 영업/마케팅 | 예상 매출 |
|------|----------|-----------|----------|
| Week 5 | B2B 팀 플랜 구현 (멀티시트) | LinkedIn 주 50명 아웃리치, 대학 교수 이메일 | ₩200,000~300,000 |
| Week 6 | API 웹훅 시스템 | Product Hunt 준비 시작, 뉴스레터 1호 | ₩250,000~350,000 |
| Week 7 | Country Risk Checker 무료 도구 | r/supplychain 포스트, SEO 콘텐츠 1개 | ₩300,000~400,000 |
| Week 8 | B2B 랜딩페이지 | Instantly.ai 셋업 + 기관 이메일 웜업 | ₩350,000~500,000 |

**Month 3**

| 주차 | 코드 작업 | 영업/마케팅 | 예상 매출 |
|------|----------|-----------|----------|
| Week 9 | 사용량 대시보드 | Product Hunt 런칭, 기관 콜드이메일 시작 | ₩500,000~700,000 |
| Week 10 | API 스트리밍 | Show HN, SEO 콘텐츠 2개 | ₩600,000~800,000 |
| Week 11 | B2B Enterprise 플랜 | 첫 B2B 데모, 뉴스레터 확대 | ₩700,000~1,000,000 |
| Week 12 | 최적화/버그 수정 | "Q1 Global Conflict Risk Index" 보고서 | ₩800,000~1,200,000 |

**Month 4~6: 축적 & 확장**
- B2B 2~3곳 계약 (Team/Business)
- API 구독 5~8곳
- 개인 구독 50~70명
- 뉴스레터 1,000+ 구독자
- 예상 MRR: ₩1,200,000~1,800,000

**Month 7~9: 가속**
- 첫 Enterprise 계약
- API Pro/Enterprise 추가
- 개인 구독 70~85명
- PH/HN 여파 장기 유입
- 예상 MRR: ₩1,800,000~2,500,000

**Month 10~12: 목표 달성**
- B2B 3~5곳 안정
- API 5~8곳 안정
- 개인 85명+
- 예상 MRR: ₩2,500,000~3,000,000+

### 8.3 최종 매출 분해

**Month 12 목표 달성 시나리오:**

| 축 | 세부 | 월 매출 |
|----|------|---------|
| B2B Team × 2 | $49 × 2 = $98 | ₩143,000 |
| B2B Business × 1 | $149 × 1 = $149 | ₩217,000 |
| B2B Enterprise × 1 | $349 × 1 = $349 | ₩508,000 |
| API Starter × 3 | $29 × 3 = $87 | ₩127,000 |
| API Pro × 2 | $99 × 2 = $198 | ₩289,000 |
| API Enterprise × 1 | $299 × 1 = $299 | ₩435,000 |
| 개인 Pro × 45 | $3.90 × 45 = $176 | ₩256,000 |
| 개인 Pro+ × 20 | $6.90 × 20 = $138 | ₩201,000 |
| 연간 Pro × 10 | $35/12 × 10 = $29 | ₩42,000 |
| 연간 Pro+ × 5 | $62/12 × 5 = $26 | ₩38,000 |
| **합계** | **$1,549** × ₩1,456 | **≈₩2,256,000** |

+ DodoPayments 이외 채널 (Google Play, Apple, RapidAPI):
| RapidAPI 수익 | $200~500 | ₩291,000~728,000 |

**보수적 총합: ₩2,550,000~₩2,980,000**
**낙관적 총합: ₩3,000,000+**

---

## Part 9. 투자 비용 & ROI

| 항목 | 월 비용 | 언제부터 | 비고 |
|------|---------|---------|------|
| Instantly.ai | $47/월 | Month 2 | 콜드이메일 자동화 |
| LinkedIn Sales Navigator | $99/월 | Month 3 (필요시) | 무료로 시작 가능 |
| Substack/Beehiiv | $0 | Month 1 | 무료 플랜 |
| RapidAPI | $0 | Month 1 | 수수료 25% (매출에서 차감) |
| **총 월 비용** | **$47~146** | | |

**ROI:**
- B2B Team 1건 ($49/월) 계약만으로 Instantly 비용 회수
- B2B Business 1건 ($149/월) 계약으로 전체 도구 비용 회수 + 흑자

---

## Part 10. 핵심 원칙 & 마인드셋

### 10.1 판매 원칙

1. **$3.90 × 538명 ❌ → $149 × 14명 ✅**
   가격을 10배 올리고 고객 수를 10분의 1로 줄여라.

2. **"우리 제품 좋아요" ❌ → "당신의 문제를 해결합니다" ✅**
   판매는 기능 소개가 아니라 문제 해결 제안이다.

3. **실시간 이벤트가 판매 기회**
   분쟁 이벤트 터지면 1시간 내 데이터 분석 공유 → "이걸 실시간으로 받으세요"

4. **매주 꾸준히 > 한번에 몰아서**
   주 30명 LinkedIn + 일 50통 이메일 = 월 200+ 접점

5. **무료 → 리드 → 유료 (Product-Led Growth)**
   무료 도구/보고서/뉴스레터로 리드 획득 → 관계 구축 → 유료 전환

6. **데이터가 상품이다**
   앱 UI는 데이터 소비의 한 형태일 뿐. API로도 팔아야 한다.

### 10.2 매일/매주 루틴

| 빈도 | 활동 | 시간 |
|------|------|------|
| **매일** | LinkedIn 5~10명 연결 요청 + 메시지 | 30분 |
| **매일** | X/Telegram 자동발행 확인 + 수동 #BuildInPublic 1개 | 15분 |
| **매주** | Reddit 포스트 1개 (서브레딧 로테이션) | 1시간 |
| **매주** | 뉴스레터 1호 발행 | 1시간 |
| **매주** | 디스콰이엇 메이커로그 1건 | 30분 |
| **격주** | SEO 콘텐츠 1개 | 2시간 |
| **매월** | "Monthly Conflict Risk Index" 보고서 | 3시간 |
| **매월** | LinkedIn 롱폼 포스트 1개 | 1시간 |

**주당 총 시간: ~8~10시간** (파트타임으로 충분)

---

## 부록 A: 현재 보유 마케팅 자산 목록

| 자산 | 상태 | 위치 |
|------|------|------|
| 기자 이메일 1,198명 | ✅ 수집 완료 | `docs/marketing/press-contacts.csv` |
| 콜드이메일 3종 템플릿 | ✅ 작성 완료 | `docs/marketing/cold-email-templates/` |
| X #BuildInPublic 7일 쓰레드 | ✅ 초안 완료 | `docs/marketing/x-buildinpublic-threads.md` |
| Show HN 포스트 | ✅ 초안 완료 | `docs/marketing/show-hn-post.md` |
| Product Hunt 전략 | ✅ 문서 완료 | `docs/marketing/producthunt-strategy.md` |
| Reddit 전략 | ✅ 문서 완료 | `docs/marketing/reddit-strategy.md` |
| Bellingcat/GIJN 피치 이메일 | ✅ 초안 완료 | `docs/marketing/bellingcat-pitch-email.md` |
| SNS 자동발행 (5개 플랫폼) | ✅ 코드 완성 | `worker/social/adapters/` |
| SEO (sitemap, OG, JSON-LD) | ✅ 운영중 | `frontend/app/sitemap.ts` 등 |
| 레퍼럴 시스템 | ✅ 운영중 | `backend/app/routers/me.py` |
| 마케팅 이메일 SMTP | ✅ 기본동작 | `backend/app/routers/admin.py` |
| Disquiet Bronze 배지 | ✅ 획득 | 스플래시/온보딩에 표시 |
| 창업자 스토리 | ✅ 작성 완료 | `docs/marketing/platform-content.md` |

## 부록 B: 구현 필요 코드 우선순위

| 순위 | 작업 | 예상 시간 | 매출 영향 |
|------|------|----------|----------|
| P0 | 페이월 트리거 추가 + Free 제한 | 1일 | 개인 전환율 2~3배 |
| P0 | API 키 발급/관리 + Rate Limiting | 2일 | API 매출 시작 |
| P0 | RapidAPI 등록 | 반나절 | API 유입 채널 |
| P1 | 연간 플랜 (DodoPayments + UI) | 1일 | LTV 증가 |
| P1 | 트라이얼 만료 알림 자동화 | 1일 | 트라이얼 전환율 2배 |
| P1 | Swagger API 문서 페이지 | 반나절 | API 가입 전환 |
| P2 | B2B 팀 플랜 (멀티시트) | 2~3일 | B2B 매출 시작 |
| P2 | Country Risk Checker 무료 도구 | 1일 | 리드 획득 |
| P2 | B2B 랜딩페이지 | 1일 | B2B 전환 |
| P3 | API 웹훅 시스템 | 2일 | API Pro 가치 |
| P3 | 뉴스레터 자동 생성 | 1일 | 콘텐츠 마케팅 |
| P3 | SEO 블로그 페이지 시스템 | 1일 | 검색 유입 |

## 부록 C: 참고 자료 & 출처

- [Dataminr 가격 — Vendr](https://www.vendr.com/marketplace/dataminr): 기본 $10,000/월
- [Dataminr 가격 — ITQlick](https://www.itqlick.com/dataminr/pricing): 엔터프라이즈 $50K~200K/월
- [ACLED on Datarade](https://datarade.ai/data-providers/acled-data/profile): 상업 라이선스 비공개
- [geoconflicts API — RapidAPI](https://rapidapi.com/gisfromscratch/api/geoconflicts/pricing): $9~99/월
- [LinkedIn Sales Navigator 통계](https://martal.ca/linkedin-statistics-lb/): 42% 더 큰 딜, 5x 파이프라인
- [B2B 콜드이메일 벤치마크](https://saleshive.com/blog/b2b-benchmarks-email-marketing-saas-you-need-know-2025/): 오픈 35~45%, 답변 3~8%
- [커뮤니티 기반 성장](https://getathenic.com/blog/community-led-growth-reddit-discord-forums-revenue): Reddit B2B 75% 영향
- [Supabase 사례](https://getathenic.com/blog/community-led-growth-reddit-discord-forums-revenue): Discord 30K+로 80% 초기 성장
- [솔로 파운더 $0→$10K MRR](https://www.softwareseni.com/solo-founder-saas-metrics-from-0-to-10k-mrr-in-6-months-with-realistic-timelines/)
- [Bannerbear $10K MRR까지 2년](https://www.bannerbear.com/journey-to-10k-mrr/)
- [Instantly.ai 콜드이메일](https://instantly.ai/blog/best-cold-email-software-for-founders-2026-7-tools/): $47/월
- [Dataminr & Crisis24 전략적 파트너십](https://www.prnewswire.com/news-releases/dataminr-and-crisis24-announce-strategic-partnership-to-pioneer-the-future-of-ai-powered-global-risk-management-302717404.html)
- [공급망 지정학 리스크](https://www.z2data.com/insights/the-6-most-critical-geopolitical-supply-chain-risks-today): EU CBAM 2026
- [SaaS 콘텐츠 마케팅 트렌드 2026](https://www.seriesxmarketing.com/blog/content-marketing-trends/): 인터랙티브 2배 전환
- [RapidAPI 가격 전략 가이드](https://rapidapi.com/guides/pricing-strategies): 4티어 권장

# WeWantPeace 월 300만원 수익 달성 전략

> 작성: 2026-03-21 | 현재 가격: Pro $3.90/월, Pro+ $6.90/월 (USD)

---

## 핵심 진단: 왜 지금 안 팔리는가

### 1. 가격이 B2C인데 시장은 B2B다
- $3.90/월로 300만원(≈$2,100) 벌려면 **538명** 필요 → 니치 시장에서 비현실적
- 경쟁사 가격: Dataminr $10,000+/월, ACLED $10,000+/년, Janes $50,000+/년
- **우리 데이터는 $3.90 가치가 아니다.** 66개 소스 × 195개국 × 5분 간격 실시간 = 기관급 인프라

### 2. 돈 낼 사람한테 안 팔고 있다
- 현재 타겟: 일반인 (분쟁 관심자)
- 실제 돈 내는 사람: 기업 안전팀, 보험사, 컨설팅, NGO, 언론사, 핀테크
- 이 사람들은 $3.90이 아니라 $100~$500/월도 싸다고 느낌

### 3. 공개 API가 없다
- 데이터 자체가 상품인데 API로 팔 수 있는 채널이 없음
- RapidAPI에 이미 geoconflicts API (경쟁 제품)가 등록되어 있음 → 시장 수요 검증됨

---

## 매출 구조: 3개 축

| 축 | 월 목표 | ARPU | 필요 고객 |
|----|---------|------|----------|
| B2B 팀/기관 구독 | ₩1,200,000 | $99~349/월 | 3~5곳 |
| 유료 API | ₩900,000 | $29~299/월 | 5~8곳 |
| 개인 구독 (기존) | ₩900,000 | $3.90~6.90/월 | 60~85명 |
| **합계** | **₩3,000,000** | | |

---

## 축 1: B2B 기관 구독 — 어떻게 파는가

### 신설 플랜 (코드 구현 필요)

```
Team      $49/월  — 5시트, API 1,000콜/일, CSV 내보내기
Business  $149/월 — 20시트, API 10,000콜/일, 웹훅, 전담 온보딩
Enterprise $349/월 — 무제한, 커스텀 알림, SLA, 전용 지원
```

### 타겟 바이어 (구체적으로 누구한테 파는가)

#### Tier A: 당장 이번 달 접근 가능
| 바이어 | 왜 필요한가 | 어떻게 접근 |
|--------|-----------|-----------|
| 한국 대학 국제관계학과 | 수업/연구 도구 | 교수 이메일 직접 (서울대, 연대, 고대, KAIST 국제학) |
| 외국계 기업 한국 지사 안전팀 | 해외 출장자 안전 관리 | LinkedIn 직접 DM |
| 정치 리스크 컨설팅 소형 펌 | 클라이언트 보고서 데이터 | LinkedIn + 콜드이메일 |
| OSINT 프리랜서/컨설턴트 | 실시간 모니터링 도구 | Reddit r/OSINT, X #OSINT |

#### Tier B: 1~3개월 내 접근
| 바이어 | 왜 필요한가 | 어떻게 접근 |
|--------|-----------|-----------|
| 글로벌 기업 Corporate Security | 주재원/공장 안전 | LinkedIn Sales Navigator |
| 보험 브로커 (Political Risk) | 언더라이팅 리스크 평가 | 콜드이메일 + 웨비나 |
| NGO 한국 사무소 (UNHCR, MSF) | 현장 직원 안전 | 직접 방문/이메일 |
| 여행사/항공사 안전팀 | 여행지 위험도 | API 연동 제안 |

### 판매 방법 (구체적 실행)

#### Step 1: LinkedIn 아웃리치 (비용: $0~99/월)

**프로필 최적화:**
```
헤드라인: "Founder @ WeWantPeace | 195개국 실시간 분쟁 모니터링 — Dataminr의 1/100 가격"
About: 경보 공포 → 1인 개발 → 195개국 모니터링 스토리 + CTA
```

**아웃리치 시퀀스 (주 30~50명):**

Day 1 — 연결 요청 (메시지 없이 or 짧게):
```
안녕하세요 [이름]님, [회사]에서 [직함] 하시는 걸 보고 연결 요청 드립니다.
글로벌 리스크 모니터링 쪽에서 일하고 있습니다.
```

Day 3 — 연결 수락 후 첫 메시지:
```
연결 감사합니다! 혹시 [회사]에서 해외 사업장/출장자 안전 관리는
어떻게 하고 계신지 궁금합니다.

저는 WeWantPeace라는 195개국 실시간 분쟁 모니터링 플랫폼을
만들고 있는데요, 66개 데이터소스를 5분 간격으로 수집해서
긴장도 지수와 AI 분석을 제공합니다.

Dataminr이 월 $10,000+인데, 저희는 팀 플랜 $49/월입니다.
14일 무료 체험 가능한데, 관심 있으시면 링크 보내드릴까요?
```

Day 7 — 팔로업 (답장 없을 시):
```
[최근 실제 분쟁 이벤트] 관련해서, 저희 플랫폼이 [구체적 데이터]를
[시간] 만에 감지했습니다. 이런 데이터가 [회사] 리스크 관리에
도움이 될 것 같아서요.

혹시 15분 정도 데모 보실 의향 있으신가요?
```

**벤치마크:** 연결 수락률 30%, 답변율 15% → 주 50명 접근 시 월 30명 답변 → 3~5명 데모 → 1~2명 전환

#### Step 2: 콜드이메일 (비용: $47/월 — Instantly.ai)

**기존 보유: 1,198명 기자 이메일**
→ 기자 개인이 아니라 **소속사 국제부 데스크**에 팀 플랜 제안

이메일 시퀀스 (5통, 3주):

Email 1 — 가치 제안:
```
제목: [언론사]  국제부를 위한 실시간 분쟁 인텔리전스 도구

[이름] 기자님 안녕하세요,

[최근 실제 분쟁 뉴스]를 보도하신 기사 잘 봤습니다.

저는 WeWantPeace라는 195개국 실시간 분쟁 모니터링 플랫폼을
운영하고 있습니다. 66개 글로벌 소스를 5분 간격으로 수집하고,
AI가 자동으로 분류·분석합니다.

국제부 취재에 도움이 될 수 있을 것 같아 연락드립니다.
14일 무료 팀 체험을 제공하고 있는데, 관심 있으시면
답장 주시겠어요?

www.wewantpeace.live
```

Email 2 (3일 후) — 구체적 데이터:
```
제목: Re: 실시간 분쟁 인텔리전스 도구

지난 메일 관련해서, 참고로 저희 플랫폼이
[최근 이벤트]를 [시간] 전에 감지했습니다.

첨부된 스크린샷처럼, 국가별 긴장도 변화를
실시간으로 추적할 수 있습니다.
```

Email 3 (5일 후) — 소셜 프루프:
```
제목: Disquiet Bronze 배지 + 195개국 커버리지

혹시 바쁘신 거라면 간단히만 —
저희 플랫폼은 출시 후 Disquiet Bronze 배지를 받았고,
한국·영어 이중 언어를 지원합니다.

15분 데모면 충분합니다. 시간 되시면 말씀해주세요.
```

Email 4 (7일 후) — 마지막 시도:
```
제목: 마지막으로 한번만 여쭤볼게요

이 주제에 관심이 없으시다면 전혀 문제 없습니다.
혹시 국제부 내에서 이런 도구에 관심 가질 분이 계시면
이 메일을 포워드해 주시면 감사하겠습니다.
```

**벤치마크:** 오픈율 35~45%, 답변율 3~8% → 1,198명 × 5% = ~60명 관심 → 10~15명 데모 → 3~5명 전환

#### Step 3: 커뮤니티 (비용: $0)

**Reddit (가장 높은 ROI):**

r/OSINT (180K+ 멤버) — 포스트 예시:
```
제목: I built a free real-time conflict monitor covering 195 countries
      with 66 data sources

본문:
Hey r/OSINT,

I'm a solo developer who built WeWantPeace after the
martial law scare in South Korea last year.

What it does:
- Monitors 66 sources (RSS, Telegram, GDELT, ACLED) every 5 minutes
- AI clusters related events into issues
- Calculates per-country Tension Index (0-100)
- Intel layers: satellite fire detection, GPS jamming, internet outages

Free tier gives you full map access + 5 daily alerts.
API is coming soon for developers.

Would love feedback from the OSINT community.
[link]
```

r/geopolitics (900K+ 멤버) — 데이터 분석 포스트:
```
제목: [OC] I tracked tension levels across 195 countries for 3 months —
      here's what the data shows

본문: [시각화 이미지 + 분석 + 데이터 출처로 WeWantPeace 언급]
```

r/dataisbeautiful — 긴장도 히트맵 시각화

**Telegram OSINT 그룹:**
- Conflict News 채널에 도구 소개
- OSINT 커뮤니티 그룹에 참여

---

## 축 2: 유료 API — 어떻게 파는가

### 구현 필요 사항
1. API 키 발급/관리 시스템
2. Rate limiting (티어별)
3. API 문서 (Swagger/Redoc)
4. RapidAPI 등록

### API 가격

```
Free API    $0/월   100콜/일   기본 이벤트 (리드 획득용)
Starter     $29/월  500콜/일   전체 이벤트 + 필터
Pro API     $99/월  5,000콜/일 웹훅 + 히스토리 + 인텔
Enterprise  $299/월 무제한     스트리밍 + SLA
```

### 판매 채널

**1. RapidAPI (즉시 실행)**
- 이미 geoconflicts API가 등록되어 있음 → 시장 수요 검증
- 우리 차별화: 66개 소스 vs 단일 UCDP, 5분 실시간 vs 일 배치
- 수수료 25%지만 마케팅 비용 0
- 예상: 첫 3개월 $200~500/월

**2. 직접 API (DodoPayments 연동)**
- API 키 발급 페이지 + Swagger 문서
- 수수료 2.9%만 (vs RapidAPI 25%)
- SEO: "geopolitical risk API", "conflict data API" 키워드

**3. 비교 SEO 콘텐츠**
```
블로그 포스트 (프로젝트 내 페이지로):
- "Dataminr Alternative: 99% cheaper real-time conflict monitoring"
- "ACLED Data API Alternative for Commercial Use"
- "Top 5 Geopolitical Risk APIs for Developers 2026"
- "How to Monitor Global Conflicts Without $10K/month"
```
→ intent-rich 검색 트래픽 → API 가입 전환

### API 바이어

| 바이어 | 왜 사는가 | 어떤 티어 |
|--------|----------|----------|
| 핀테크 스타트업 | 지정학 → 투자 시그널 | Pro/Enterprise |
| 여행 앱 | 목적지 안전도 | Starter/Pro |
| 공급망 SaaS | 리스크 데이터 임베드 | Pro/Enterprise |
| 보험 플랫폼 | 정치 리스크 스코어링 | Enterprise |
| 학생/연구자 | 논문 데이터 | Free/Starter |

---

## 축 3: 개인 구독 전환율 개선 — 코드로 해결

### 현재 문제점 (코드 분석 결과)

1. **페이월 트리거 4개뿐** + 30분 쿨다운 + 세션당 1회
   → 유저가 페이월을 만날 확률 극히 낮음

2. **Free가 너무 관대**
   → 지도, 이슈 상세, 커뮤니티 전부 무료

3. **업그레이드 넛지가 수동적**
   → missedAlertCount ≥ 3이어야 배너 표시

### 코드 변경 사항

**A. Free 제한 강화:**
- 이슈 상세 열람: 하루 5건 → 초과 시 페이월
- 홈 피드: 스크롤 5건 후 "Pro에서 더 보기" 카드 삽입
- 알림 5건 소진 시: "Pro면 20건" 인앱 메시지

**B. 페이월 트리거 추가:**
- 이슈 상세 하단: "관련 인텔 시그널 N건 → Pro"
- 타임라인: 최근 3건만 → 나머지 blur
- 브리핑: 상위 3건만 → 나머지 잠금

**C. 트라이얼 전환 자동화:**
- D-2: "체험 종료 임박" 푸시
- D-day: "Pro 비활성화" 인앱 모달
- D+7: "다시 돌아오세요" 이메일

**D. 연간 플랜:**
- Pro $35/년 (25% 할인)
- Pro+ $62/년 (25% 할인)

---

## 실행 타임라인

### Week 1 (이번 주)
- [ ] LinkedIn 프로필 최적화
- [ ] r/OSINT, r/geopolitics 첫 포스트 (판매 아닌 가치 제공)
- [ ] 기자 콜드이메일 1차 발송 (하루 50통)
- [ ] B2B 플랜 가격 결정 + 랜딩페이지 초안

### Week 2~3
- [ ] 외부 API 엔드포인트 구축 (API 키 발급 + rate limiting)
- [ ] RapidAPI 등록
- [ ] API 문서 사이트 (Swagger)
- [ ] 페이월 트리거 추가 + Free 제한 강화
- [ ] 연간 플랜 결제 옵션

### Week 4~5
- [ ] B2B 팀/기관 플랜 구현 (멀티시트)
- [ ] LinkedIn 아웃리치 시작 (주 30~50명)
- [ ] 비교 SEO 콘텐츠 3개 작성
- [ ] "Q1 2026 Global Conflict Risk Index" 무료 보고서

### Month 2~3
- [ ] Instantly.ai 콜드이메일 (기관 타겟)
- [ ] Product Hunt 런칭
- [ ] 뉴스레터 시작 (주간 Conflict Intelligence Brief)
- [ ] 대학 국제관계학과 아웃리치

### Month 4~6
- [ ] Enterprise 리드 전환
- [ ] AWS Data Exchange / Datarade 등록 검토
- [ ] 첫 케이스 스터디 작성

---

## 현실적 매출 예상

| 기간 | 월 매출 | 주요 매출원 |
|------|---------|-----------|
| Month 1~2 | ₩200,000~500,000 | 개인 Pro 전환 + API Free→Starter |
| Month 3~4 | ₩500,000~1,000,000 | 첫 B2B Team 계약 + API Pro |
| Month 5~6 | ₩1,000,000~1,800,000 | B2B 2~3곳 + API 5곳 + 개인 50명 |
| Month 7~9 | ₩1,800,000~2,500,000 | Enterprise 1곳 + 축적 효과 |
| Month 10~12 | ₩2,500,000~3,000,000+ | 목표 달성 |

**보수적 예상: 10~12개월**
**낙관적 (바이럴 이벤트 + PH 히트): 6~8개월**

---

## 투자 비용

| 항목 | 월 비용 | 비고 |
|------|---------|------|
| LinkedIn Sales Navigator | $0~99 | Core 플랜, 없어도 시작 가능 |
| Instantly.ai | $47 | 콜드이메일 자동화 |
| RapidAPI | $0 | 수수료 25% (매출에서 차감) |
| 총 월 비용 | **$47~146** | |

ROI: B2B 1건 계약($149/월)이면 첫 달부터 흑자

---

## 가장 중요한 원칙

1. **$3.90 × 538명이 아니라 $149 × 14명을 노려라**
2. **판매는 "우리 제품 좋아요"가 아니라 "당신의 문제를 해결합니다"**
3. **실시간 분쟁 이벤트가 터질 때가 판매 기회** — 이벤트 발생 1시간 내 데이터 분석 공유
4. **매주 꾸준히 > 한번에 몰아서** — 주 30명 LinkedIn + 일 50통 이메일
5. **무료 도구/보고서로 리드 획득 → 유료 전환** (Product-Led Growth)

# 플랫폼별 마케팅 콘텐츠 (창업자 스토리 기반)

---

## 1. 뉴스와이어 보도자료

### 제목
50억 매출 엑싯 창업자, AI 기반 글로벌 분쟁 모니터링 플랫폼 'WeWantPeace' 정식 출시

### 부제목
195개국 실시간 안보 데이터를 수집·분석하는 1인 개발 SaaS, 3~5분 간격 업데이트로 "전쟁 전에 아는 서비스" 구현

### 본문

2026년 3월 — 시리얼 앙트러프러너 출신 개발자가 195개국의 분쟁·안보 상황을 실시간으로 모니터링하는 플랫폼 'WeWantPeace(위원트피스)'를 정식 출시했다.

WeWantPeace는 60개 이상의 글로벌 뉴스 소스에서 3~5분 간격으로 안보 관련 뉴스를 수집하고, GPT-4o-mini 기반 AI 엔진으로 분류·분석해 사용자에게 전달하는 SaaS 서비스다. 국가별 긴장도를 0~100으로 수치화한 'Tension Index'와 개인 맞춤형 영향도를 0~10으로 산출하는 'KScore' 등 독자적인 지표를 제공하며, 긴장 수치가 급등하면 실시간 푸시 알림을 보낸다.

서비스를 만든 창업자는 18세에 첫 스타트업을 창업한 뒤 군 복무, 약 5년간의 실무 경험을 거쳐 재창업에 나서 누적 약 50억 원의 매출을 달성하고 엑싯한 이력을 보유하고 있다. 이후 제주도에서 게스트하우스를 운영하며 "진짜 하고 싶은 것"을 모색하던 중, 스마트폰 재난 경보가 울릴 때마다 화들짝 놀라는 자신의 경험에서 서비스 아이디어를 얻었다.

창업자는 "뉴스가 보도될 때는 이미 늦은 경우가 많다. 세계 곳곳의 안보 상황을 실시간으로 추적하고, 나에게 영향을 미치기 전에 미리 대비할 수 있는 도구가 필요하다고 생각했다"며 "사업 기획 경험을 살려 사용자 경험 중심으로 설계했고, 기획부터 개발, 운영까지 1인으로 전담하고 있다"고 말했다.

WeWantPeace는 Freemium SaaS 모델로 운영된다. 무료 플랜으로 기본 모니터링 기능을 이용할 수 있으며, Pro(월 4,900원)와 Pro+(월 9,900원) 플랜에서 고급 분석, 알림 커스터마이징 등 확장 기능을 제공한다. 한국어·영어를 지원하고, PWA와 Android 앱으로 접속할 수 있으며, 공개 API도 제공해 외부 서비스 연동이 가능하다.

기술적으로는 Next.js 14 기반 프론트엔드, FastAPI·Celery·PostgreSQL 기반 백엔드로 구성되어 있으며, KScore 기반 실시간 알림 시스템을 통해 급변 상황을 자동으로 포착한다.

### 서비스 개요
- 서비스명: WeWantPeace
- URL: https://www.wewantpeace.live
- 분류: AI 기반 글로벌 안보 모니터링 SaaS
- 데이터 소스: 60+ 글로벌 뉴스 소스
- 업데이트 주기: 3~5분
- 주요 지표: Tension Index(국가별 긴장도 0~100), KScore(개인화 영향도 0~10)
- 요금제: Free / Pro ₩4,900 / Pro+ ₩9,900
- 지원: 한국어, 영어 / PWA, Android, 공개 API

### 회사 소개
WeWantPeace는 "모든 사람이 안전한 세상을 미리 준비할 수 있도록"이라는 비전 아래, 글로벌 분쟁·안보 정보를 실시간으로 분석·제공하는 플랫폼이다. 시리얼 앙트러프러너 출신 1인 개발자가 기획부터 개발, 운영까지 전담하고 있다.

---

## 2. Velog 개발기

### 제목
50억 매출 CEO를 그만두고 혼자 코딩을 시작한 이유

### 태그
사이드프로젝트, Next.js, FastAPI, AI, 1인개발, GPT, Celery, 창업, 인디해커, SaaS

### 본문

## 경보가 울릴 때마다 심장이 멈추는 사람

제주도 게스트하우스를 운영하던 어느 날이었다.
스마트폰에서 재난 경보가 울렸다. 나는 반사적으로 몸이 굳었다.

"북한 미사일? 지진? 뭐지?"

알고 보면 태풍 경로 안내 같은 것이었지만, 그 짧은 순간의 공포는 매번 똑같았다. 경보가 울리고 나서야 급하게 검색하고, 단편적인 뉴스를 조각조각 맞추는 경험. 이미 늦은 정보. 맥락 없는 헤드라인.

"왜 미리 알 수는 없을까?"

이 질문 하나가 지금의 WeWantPeace를 만들었다.

## 거꾸로 가는 이력서

잠깐 제 이야기를 하겠습니다.

18세에 첫 스타트업을 창업했다. 군대를 다녀오고, 약 5년간 실무를 거치며 사업 감각을 키웠다. 재창업 후 누적 약 50억 원의 매출을 만들고, 엑싯했다.

그리고 제주도로 갔다. 게스트하우스를 열었다. 돈이 목적이 아니었다. "내가 진짜 하고 싶은 게 뭘까"를 찾으려고.

답은 의외로 빨리 왔다. 경보 알림이 울릴 때마다 느꼈던 그 공포. 세계 곳곳에서 벌어지는 분쟁을 체계적으로 추적할 수 있는 서비스가 없다는 사실. 직접 만들기로 했다.

## 기술 스택 — 혼자서 풀스택

1인 개발이니 선택 기준은 명확했다: **빠르게, 안정적으로, 확장 가능하게.**

**프론트엔드**
- Next.js 14 (App Router)
- PWA + Android (TWA)
- 한국어/영어 i18n

**백엔드**
- FastAPI — 비동기 처리에 최적
- Celery + Redis — 60개 이상의 뉴스 소스를 3~5분 간격으로 수집하는 워커
- PostgreSQL — 정규화된 이벤트 데이터 저장
- GPT-4o-mini — 뉴스 분류, 국가 매핑, 심각도 산정

**핵심 지표**
- Tension Index: 국가별 긴장도를 0~100으로 수치화. 뉴스 빈도, 심각도, 소스 다양성 등 다차원 분석.
- KScore: 사용자 위치·관심 국가 기반 개인화 영향도 (0~10)
- KScore 기반 실시간 알림: 긴장도 급등 시 실시간 푸시 알림

## 어려웠던 것들

**1. 노이즈 필터링**
60개 이상의 소스에서 쏟아지는 뉴스 중 "진짜 안보 이슈"만 걸러내는 게 가장 어려웠다. 스포츠 기사에 "전쟁"이 비유로 쓰이고, 영화 리뷰에 "폭격"이 등장한다. normalizer.py를 수십 번 고치며 _NON_MILITARY_CONTEXT, _SPAM_PATTERNS 같은 규칙들을 다듬었다.

**2. 195개국 매핑**
기사 하나에 여러 국가가 언급되고, 국가명이 약어·별칭·현지어로 다양하게 표기된다. COUNTRY_MAP이 수백 줄이 넘어갔다.

**3. 1인 개발의 외로움**
기획자도, 디자이너도, QA도 나 혼자다. 새벽 3시에 크롤러가 멈추면 나만 안다. 하지만 사용자 한 명이 "이 서비스 덕분에 가족 여행 전에 확인했어요"라고 보내온 메시지가 모든 걸 상쇄했다.

## 배운 것

- **사업 기획 능력은 개발에서 무기가 된다.** 무엇을 만들지 결정하는 게 어떻게 만들지보다 어렵다. 수 년간의 사업 경험이 "사용자 경험 중심 설계"로 이어졌다.
- **완벽한 타이밍은 없다.** 엑싯 후 쉬고 있을 때 시작하길 잘했다. 기다렸으면 안 만들었을 거다.
- **1인 개발은 제약이 아니라 집중이다.** 의사결정이 빠르고, 사용자 피드백에 즉시 반응할 수 있다.

## 링크

- 서비스: https://www.wewantpeace.live
- 요금: Free / Pro ₩4,900 / Pro+ ₩9,900
- 공개 API 제공

전쟁은 예방이 최선입니다.
세상을 모니터링하는 일, 혼자 시작했지만 함께 할 수 있길 바랍니다.

---

## 3. OKKY 프로젝트 소개

### 제목
WeWantPeace — 195개국 분쟁·안보 실시간 모니터링 플랫폼

### 본문

안녕하세요. 1인 개발자입니다.

스마트폰 재난 경보가 울릴 때마다 심장이 덜컥하는 경험, 다들 한 번쯤 있으시죠? 그 공포에서 출발해 "세계 안보 상황을 실시간으로 추적하고, 미리 대비할 수 있는 서비스"를 만들었습니다.

**서비스 소개**
WeWantPeace는 60개 이상의 글로벌 뉴스 소스에서 3~5분 간격으로 안보 뉴스를 수집하고, AI로 분석해 국가별 긴장도(Tension Index, 0~100)와 개인화 영향도(KScore, 0~10)를 제공합니다. 긴장도가 급등하면 실시간 푸시 알림도 보내드립니다.

**기술 스택**
- Frontend: Next.js 14 (App Router), PWA, Android(TWA)
- Backend: FastAPI, Celery, Redis, PostgreSQL
- AI: GPT-4o-mini (뉴스 분류·국가 매핑·심각도 산정)
- 언어: 한국어/영어
- 기타: 공개 API, Freemium SaaS

**주요 기능**
- 195개국 실시간 분쟁 모니터링
- 국가별 Tension Index (0~100)
- 개인 맞춤 KScore (0~10)
- KScore 기반 알림 → 푸시 알림
- 지도 기반 시각화

**요금**
- Free: 기본 모니터링
- Pro: ₩4,900/월
- Pro+: ₩9,900/월

링크: https://www.wewantpeace.live

기획부터 개발·운영까지 혼자 하고 있습니다. 피드백 환영합니다!

---

## 4. X (Twitter) 쓰레드

### 한국어 버전

**트윗 1 (후킹)**
18살에 창업하고, 50억 매출 만들고, 엑싯했다.

그리고 전부 내려놓고 제주도 게스트하우스를 열었다.

지금은 혼자 코딩하며 "전쟁 모니터링 서비스"를 만들고 있다.

왜 이런 선택을 했는지 이야기해보려 한다.

**트윗 2**
제주도에서 한가롭게 살던 어느 날, 스마트폰에서 경보 알림이 울렸다.

심장이 멈추는 것 같았다. 결국 별거 아닌 알림이었지만, 그 몇 초간의 공포는 진짜였다.

"왜 세상에서 무슨 일이 벌어지는지 미리 알 수 없을까?"

이 질문이 시작이었다.

**트윗 3**
찾아보니 195개국의 안보 상황을 실시간으로 추적해주는 서비스가 없었다.

뉴스는 이미 터진 후에 나오고, 단편적이고, 맥락이 없다.

그래서 직접 만들기로 했다. 1인 개발로.

**트윗 4**
60개 이상의 글로벌 뉴스 소스를 3~5분 간격으로 수집하고, GPT-4o-mini로 분류·분석한다.

국가별 긴장도(0~100), 개인화 영향도(0~10)를 실시간 산출.

긴장도가 급등하면 바로 푸시 알림.

Next.js 14 + FastAPI + Celery + PostgreSQL 풀스택.

**트윗 5**
사업 기획을 수 년간 해왔기에, "무엇을 만들지"를 결정하는 건 자신있었다.

하지만 새벽 3시에 크롤러가 죽었을 때 깨워줄 동료가 없는 건 다른 문제였다.

1인 개발의 외로움과 자유. 둘 다 진짜다.

**트윗 6**
50억 매출보다 의미 있는 건, 한 사용자가 보내준 메시지였다.

"가족 여행 전에 이 서비스로 확인했어요."

이게 계속 만드는 이유다.

**트윗 7 (CTA)**
WeWantPeace — 195개국 분쟁·안보 실시간 모니터링

무료로 시작할 수 있습니다.
https://www.wewantpeace.live

#WeWantPeace #인디해커 #1인개발 #SaaS #AI #스타트업

### English Version

**Tweet 1 (Hook)**
I started my first company at 18. Built it to ~$3.5M revenue. Exited.

Then I left everything behind and opened a guesthouse on Jeju Island.

Now I'm solo-coding a real-time war monitoring platform.

Here's why.

**Tweet 2**
One day on Jeju, an emergency alert went off on my phone.

My heart stopped. It turned out to be nothing serious. But those few seconds of pure terror were real.

"Why can't I know what's happening in the world before it reaches me?"

That question started everything.

**Tweet 3**
I looked everywhere. There was no service that tracked security situations across 195 countries in real time.

News comes after the fact. Fragmented. No context.

So I decided to build it myself. Solo.

**Tweet 4**
60+ global news sources, collected every 3-5 minutes.

GPT-4o-mini classifies, maps countries, and scores severity.

Tension Index (0-100) per country. KScore (0-10) personalized to you.

KScore-based real-time alerts → instant push notifications.

Next.js 14 + FastAPI + Celery + PostgreSQL.

**Tweet 5**
Years of business planning taught me how to decide WHAT to build.

But at 3 AM when your crawler dies and there's no one to call — that's a different kind of skill.

Solo development: lonely and liberating. Both are real.

**Tweet 6**
More meaningful than any revenue milestone was one user message:

"I checked your service before my family trip."

That's why I keep building.

**Tweet 7 (CTA)**
WeWantPeace — Real-time conflict & security monitoring for 195 countries.

Free to start.
https://www.wewantpeace.live

#WeWantPeace #indiehacker #solodev #SaaS #AI #buildinpublic

---

## 5. LinkedIn 포스팅

50억 매출을 만들고 엑싯한 뒤, 제주도에서 게스트하우스를 열었습니다.

사업을 접은 게 아니라, "진짜 풀고 싶은 문제"를 찾으려 한 거였습니다.

답은 예상치 못한 곳에서 왔습니다.

스마트폰에서 재난 경보가 울릴 때마다 심장이 덜컥하는 경험. 급하게 뉴스를 검색해도 단편적인 헤드라인뿐. 세계에서 무슨 일이 벌어지고 있는지, 그것이 나에게 어떤 영향을 미치는지 체계적으로 알려주는 서비스가 없었습니다.

그래서 직접 만들었습니다.

WeWantPeace는 195개국의 분쟁·안보 상황을 실시간으로 모니터링하는 플랫폼입니다.

• 60개 이상의 글로벌 뉴스 소스에서 3~5분 간격으로 수집
• AI(GPT-4o-mini)가 분류·분석하여 국가별 긴장도(Tension Index)와 개인화 영향도(KScore) 산출
• 긴장도가 급등하면 실시간 푸시 알림

18세에 첫 창업을 한 뒤, 군 복무와 약 5년의 실무를 거쳐 재창업하고 엑싯까지 — 그 과정에서 얻은 가장 큰 자산은 "사용자 경험 중심으로 사고하는 능력"이었습니다. WeWantPeace는 그 경험을 기술 제품에 온전히 녹인 프로젝트입니다.

현재 기획부터 개발, 운영까지 1인으로 전담하고 있습니다. Freemium SaaS 모델로, 무료 플랜부터 Pro(₩4,900/월), Pro+(₩9,900/월)까지 제공합니다. 한국어·영어를 지원하고, PWA·Android 앱과 공개 API도 운영 중입니다.

전쟁은 예방이 최선이고, 예방의 첫걸음은 정보입니다.

세상의 안보 상황을 모니터링하는 일, 혼자 시작했지만 더 많은 분들과 함께 하고 싶습니다.

https://www.wewantpeace.live

#WeWantPeace #SerialEntrepreneur #AI #SaaS #ConflictMonitoring #IndieHacker #Startup #1인개발

---

## 6. 요즘IT 기고 제안서

### 기고 주제 후보 3개

1. "50억 매출 엑싯 후 1인 개발자로 — 사업 기획자가 풀스택 서비스를 만드는 법"
2. "60개 뉴스 소스를 3분마다 수집하고 AI로 분류하기 — 실시간 글로벌 모니터링 시스템 구축기"
3. "Freemium SaaS를 혼자 만들고 운영하는 현실 — WeWantPeace 195개국 분쟁 모니터링 개발기"

### 기고 개요 (후보 1 기준)

1. 들어가며 — 경보 알림 하나에서 시작된 서비스
2. 창업자에서 개발자로 — 역할 전환의 현실
3. 아키텍처 설계 — 1인 개발자의 기술 선택 기준
4. 핵심 기능 구현기 — Tension Index와 KScore
5. 1인 SaaS 운영의 현실
6. 비즈니스 관점에서 본 PeaceTech
7. 마치며 — 혼자 시작했지만 함께 하고 싶은 이야기

### 타겟 독자
- 예비 창업자/사이드 프로젝트 개발자
- 풀스택 개발자 (FastAPI + Next.js + Celery 실제 운영 사례)
- 비개발 출신 창업자 (기획→기술 전환)
- AI/데이터 엔지니어 (GPT 실시간 뉴스 파이프라인)

### 예상 분량
- 약 5,000~7,000자 (원고지 15~20매)
- 아키텍처 다이어그램, 스크린샷 등 3~5장

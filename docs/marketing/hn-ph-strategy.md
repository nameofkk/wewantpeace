# Show HN & Product Hunt 재시도 전략 (2026-03-09)

## 현황

### Show HN (item?id=47303606)
- **상태: dead + deleted** — HN API에서 확인됨
- 게시 시간: 2026-03-09 01:10 UTC (일요일)
- 포인트: 0, 댓글: 0
- 원인 추정: 일요일 게시 + 새 계정 + 외부 링크 공유로 투표 조작 감지 가능성

### Product Hunt
- 등록 완료, 반응 없음

---

## Part 1: Show HN 복구 및 재시도

### 즉시 (오늘)

1. **hn@ycombinator.com 이메일 보내기**
   ```
   Subject: Show HN post dead/deleted - requesting review (id: 47303606)

   Hi,

   My Show HN post (https://news.ycombinator.com/item?id=47303606)
   appears to be dead/deleted. I'm a solo developer from South Korea
   who built a real-time conflict monitoring platform.

   I did not engage in any vote manipulation. Could you review the post
   and advise on whether I can resubmit?

   I've added my email to my HN profile for repost invitations.

   Thank you,
   Shin
   ```

2. **HN 프로필에 이메일 등록** — 모더레이터가 `/invited` 재게시 초대를 보낼 수 있음

### 재게시 준비 (36시간+ 대기 후)

**최적 타이밍:**
- **화~목요일, 오전 8-9시 EST** = KST 밤 10-11시
- 추천: 화요일 밤 10시 KST (3/11)

**타이틀 후보 (62자 이내):**
1. `Show HN: Real-time conflict tracker for 195 countries with severity scoring`
2. `Show HN: I built a geopolitical risk dashboard as a solo dev`
3. `Show HN: WeWantPeace – RSS + AI pipeline monitoring global conflicts`

**첫 댓글 (게시 직후 반드시 작성):**
```
Hi HN, solo dev from South Korea.

I built this after the Dec 2024 martial law incident — couldn't find
a single place to see what was happening globally in real-time.
Existing tools were either $$$$ intelligence platforms or slow
academic datasets.

How it works:
- Celery workers poll 60+ RSS feeds every 3-5 min
- GPT-4o-mini extracts structured data (country, severity, topic)
- Clustering groups related events into "issue clusters"
- Two scoring algorithms: Tension Index (0-100 per country) and
  KScore (0-10, personalized impact)

Stack: Next.js 14 + FastAPI + PostgreSQL + Celery + Redis

What I'd love feedback on:
- Is the scoring methodology intuitive?
- Any RSS/data sources I'm missing?
- UX on mobile (it's also a PWA)

Happy to share architecture details.
```

### 절대 하지 말 것
- ❌ 직접 링크(`news.ycombinator.com/item?id=xxx`)를 카톡/슬랙으로 공유하며 업보트 요청 — 즉시 감지됨
- ❌ 여러 계정으로 업보트
- ❌ 게시 후 타이틀 수정
- ❌ 마케팅 언어 사용 ("revolutionary", "game-changing" 등)

### 합법적 초기 모멘텀
- 3-5명의 **기존 HN 유저**에게 스크린샷 이미지로 알림 (링크 대신)
- "Show HN에 올렸어" 정도만 — 업보트 요청 X, 댓글은 OK
- 모든 댓글에 **5분 이내** 답변 (알고리즘이 활발한 포스트를 상위 유지)

### Second-Chance Pool
- HN에는 트랙션 못 받은 양질의 포스트를 프론트 페이지에 다시 올려주는 시스템 존재
- 모더레이터에게 이메일로 요청 가능: hn@ycombinator.com
- 확인: https://news.ycombinator.com/pool

---

## Part 2: Product Hunt 재런칭 전략

### 현실 인식
- 2025-2026 기준 **Featured 비율 10%** (과거 60-98%에서 급락)
- Featured 안 되면: 방문자 100-500명, 가입 1-15명
- Featured 되면: 방문자 1,000-5,000명, 가입 10-150명
- **최소 준비 시간: 50-120시간 (4-6주)**

### 재런칭 조건
- "significant product iteration" 이 있어야 재런칭 가능
- 버그 수정만으로는 불충분 — 대규모 UI 개편, 새 핵심 기능, 새 플랫폼 등
- 6개월 미만이어도 변경사항이 크면 심사 후 승인 가능

### 4주 준비 체크리스트

**Week 1: 커뮤니티 활동**
- [ ] PH에서 다른 프로젝트에 양질의 피드백 댓글 5개+
- [ ] 관련 카테고리 메이커 10명+ 팔로우
- [ ] 메이커 프로필 완성 (사진, 스토리, 링크)

**Week 2: 에셋 준비**
- [ ] 고대비 썸네일 (240x240)
- [ ] 히어로 이미지 (제품 맥락에서 사용 장면)
- [ ] 4-6개 스크린샷 (결과물 중심, UI만 X)
- [ ] 30-90초 데모 영상 (진솔한 파운더 내레이션)
- [ ] 첫 스크린샷 = "아하 모먼트" (지도 위에 실시간 이벤트)

**Week 3: 서포터 확보**
- [ ] 50-200명 서포터 리스트 (기존 계정, 365일+ 활동 이력)
- [ ] 타임존별 세분화 (US, EU, APAC)
- [ ] "솔직한 피드백 부탁" (업보트 부탁 X)
- [ ] X/Twitter, LinkedIn에서 사전 공유

**Week 4: 런칭 실행**
- [ ] 10초 피치 완성: "WeWantPeace monitors conflicts across 195 countries in real-time with AI severity scoring — free for everyone"
- [ ] Maker 첫 댓글 초안 준비
- [ ] Wave별 아웃리치 스케줄 확정

### 런칭 타이밍
- **12:01 AM PST** (KST 17:01) — 풀 24시간 노출
- **화~목요일** — 가장 높은 트래픽 + 적절한 경쟁
- 2주 전 PH 캘린더 확인하여 대형 런칭과 겹치지 않게

### 런칭일 Wave 전략

| Wave | PST | KST | 타겟 | 목표 |
|------|-----|-----|------|------|
| 1 | 12:01-2 AM | 17:01-19:00 | 코어팀 + EU/Asia | 초기 100-150 업보트 |
| 2 | 7-9 AM | 00:00-02:00 | US 서부 | 모멘텀 유지 |
| 3 | 12-3 PM | 05:00-08:00 | US 동부/EU 저녁 | 포지션 방어 |
| 4 | 5-11 PM | 10:00-16:00 | APAC + US 후반 | 최종 순위 확보 |

### 댓글 = 최강 무기
- **양질의 댓글 1개 = 업보트 40-50개** 와 동일한 랭킹 효과
- 50개+ 실질적 댓글 → 업보트만 많은 프로젝트보다 높은 순위
- 런칭 5분 이내 메이커 첫 댓글 필수
- 모든 댓글에 15분 이내 답변

### 필터 트리거 회피
- 처음 10분에 20개+ 업보트 = 인위적 간주
- 댓글:업보트 비율 1:20 이하 = 투표 조작 시그널
- 런칭 직전 만든 신규 계정 업보트 = 무시됨
- **일정한 모멘텀 > 한번에 몰아치기**

---

## Part 3: 공통 교훈

### 왜 반응이 없었나?
1. **타이밍**: 일요일 게시 (최악의 요일)
2. **사전 커뮤니티 없음**: 서포터 0명 상태로 런칭
3. **외부 링크 공유**: 직접 링크 공유 시 투표 조작으로 감지될 수 있음
4. **새 계정**: HN/PH 모두 신규 계정에 불이익

### 해야 할 것 (우선순위)
1. 🔴 **오늘**: HN 모더레이터에게 이메일
2. 🟡 **이번 주**: HN 재게시 (화~목, 밤 10시 KST)
3. 🟡 **이번 주**: PH/HN 외 채널 병행 (Reddit, Indie Hackers, Dev.to)
4. 🟢 **4주 후**: PH 재런칭 (에셋 + 서포터 확보 후)

### 현실적 기대치
- HN: 프론트 페이지 진입 시 1,000-5,000 방문자. 진입 못하면 50-200명.
- PH: Featured 시 1,000-5,000 방문자. 아니면 100-500명.
- **두 플랫폼 모두 장기 성장 채널이 아닌 일회성 스파이크** — SEO, 커뮤니티 빌딩이 진짜 성장 채널

---

## 참고 자료
- [HN Show Guidelines](https://news.ycombinator.com/showhn.html)
- [HN FAQ](https://news.ycombinator.com/newsfaq.html)
- [HN Undocumented Rules](https://github.com/minimaxir/hacker-news-undocumented)
- [Ask HN: Repost failed Show HN?](https://news.ycombinator.com/item?id=22422112)
- [PH Launch Guide 2026](https://calmops.com/indie-hackers/product-hunt-launch-guide/)
- [PH Algorithm Changes 2025](https://awesome-directories.com/blog/product-hunt-launch-guide-2025-algorithm-changes/)
- [How to Launch on PH 2026](https://hackmamba.io/developer-marketing/how-to-launch-on-product-hunt/)

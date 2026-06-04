# WeWantPeace 마케팅 포스팅 실행 가이드

> 신혁님이 1~5번 채널을 순서대로 실행하기 위한 step-by-step 가이드입니다.
> 각 단계에서 어디에 가서, 뭘 클릭하고, 뭘 복붙하는지 상세히 설명합니다.

---

## 실행 순서 요약

| 순서 | 채널 | 예상 소요 시간 | 선행 조건 | 참조 파일 |
|------|------|--------------|----------|----------|
| 1 | Show HN | 15분 | HN 계정 | `show-hn-draft.md` |
| 2 | Bellingcat 이메일 | 20분 | 이메일 계정 | `bellingcat-pitch-email.md` |
| 3 | X #BuildInPublic | 7일 (하루 10분) | @wewantpeace_ 계정 | `x-buildinpublic-threads.md` |
| 4 | Awesome Lists PR | 30분 | GitHub 계정 + 레포 public | `awesome-lists-prs.md` |
| 5 | Reddit | 2~4주 (카르마 빌딩) + 포스팅 3일 | Reddit 계정 | `reddit-strategy.md` |

**권장 순서**: 1 -> 3 (동시 시작) -> 2 (HN 결과 보고 3일 후) -> 4 -> 5

---

## 1. Show HN 포스팅

### 사전 준비
- [ ] HN 계정 (https://news.ycombinator.com) -- 없으면 가입 (즉시 가능)
- [ ] 기존 계정이 있으면 더 좋음 (karma가 있는 계정)
- [ ] `docs/marketing/show-hn-draft.md` 파일을 열어둘 것

### Step-by-step

**Step 1: HN에 로그인**
1. https://news.ycombinator.com 접속
2. 우측 상단 `login` 클릭
3. 계정/비밀번호 입력 후 로그인

**Step 2: 새 포스트 작성**
1. 상단 메뉴에서 `submit` 클릭
2. `title` 필드에 복붙:
   ```
   Show HN: WeWantPeace – Real-time global conflict tracker with personalized severity scoring
   ```
3. `url` 필드에 복붙:
   ```
   https://www.wewantpeace.live
   ```
4. `text` 필드는 **비워둘 것** (URL과 text는 동시에 사용 불가)
5. `submit` 버튼 클릭

**Step 3: First Comment 작성 (제출 직후 즉시)**
1. 방금 만든 포스트 클릭해서 들어감
2. 하단 댓글 입력란에 `show-hn-draft.md`의 "First Comment" 섹션 전체를 복붙
3. `add comment` 클릭

**Step 4: 모니터링 (2시간 동안)**
1. 30분마다 새 댓글 확인
2. 모든 댓글에 답글 작성 (기술적, 겸손하게)
3. `show-hn-draft.md`의 "Common HN questions" 섹션 참고

### 최적 포스팅 시간
- **화요일~목요일**, 오전 8:00~9:00 AM ET (한국 시간 밤 10:00~11:00)
- 월요일 아침, 금요일은 피할 것

### 주의사항
- 친구에게 업보트 부탁하지 말 것 (HN이 감지하고 패널티 부여)
- 자랑 톤 절대 금지
- 모든 댓글에 성실히 답변

---

## 2. Bellingcat 이메일 발송

### 사전 준비
- [ ] `docs/marketing/bellingcat-pitch-email.md` 파일을 열어둘 것
- [ ] 이메일 클라이언트 준비 (Gmail 등)

### Step-by-step

**Step 1: Bellingcat 이메일 작성 (최우선)**
1. Gmail (또는 사용 중인 이메일) 열기
2. 새 메일 작성 (`+` 또는 `Compose`)
3. 수신자: `tech@bellingcat.com`
4. 제목에 복붙:
   ```
   Tool submission: WeWantPeace — real-time multi-source conflict monitor (24.5h early detection demonstrated)
   ```
5. 본문에 `bellingcat-pitch-email.md`의 "Email 1: Bellingcat" Body 섹션 전체 복붙
6. 하단의 `[Name]` 부분을 실명으로 교체
7. 보내기

**Step 2: GIJN 이메일 (3일 후)**
1. 수신자: `hello@gijn.org`
2. `bellingcat-pitch-email.md`의 "Email 2: GIJN" 섹션 복붙
3. 보내기

**Step 3: OCCRP 이메일 (같은 날)**
1. 수신자: `info@occrp.org`
2. `bellingcat-pitch-email.md`의 "Email 3: OCCRP" 섹션 복붙
3. 보내기

**Step 4: 팔로업**
- Bellingcat에서 7일 내 답장 없으면 **1회만** 팔로업
- 팔로업 제목: `Re: [원래 제목]` (같은 스레드)
- 팔로업 내용: "Just following up on my previous email. Happy to answer any questions or provide a walkthrough."
- 2회 이상 팔로업 절대 금지

---

## 3. X #BuildInPublic 쓰레드 포스팅

### 사전 준비
- [ ] @wewantpeace_ 계정 로그인
- [ ] `docs/marketing/x-buildinpublic-threads.md` 파일을 열어둘 것
- [ ] 각 쓰레드용 이미지/스크린샷 준비 (선택사항이지만 강력 권장)

### 이미지 준비 목록
| 쓰레드 | 추천 이미지 |
|--------|-----------|
| Thread 1 (월) | 메인 대시보드 스크린샷 |
| Thread 2 (화) | 아키텍처 다이어그램 |
| Thread 3 (수) | KScore 비교 차트 (서울 vs 베를린 vs 나이로비) |
| Thread 4 (목) | 텔레그램 시그널 -> 시스템 감지 스크린샷 |
| Thread 5 (금) | 가격 비교표 이미지 |
| Thread 6 (토) | 데이터 파이프라인 플로우 다이어그램 |
| Thread 7 (일) | 로드맵 비주얼 |

### Step-by-step (매일 반복)

**Step 1: X.com 접속**
1. https://x.com 로그인 (@wewantpeace_ 계정)
2. 홈 화면에서 `Post` (글쓰기) 버튼 클릭

**Step 2: 쓰레드 작성**
1. 첫 번째 트윗 내용 복붙 (해당 날짜의 Thread에서 Tweet 1 내용)
2. 이미지 첨부 (있으면)
3. 트윗 입력칸 아래 `+` 버튼 클릭 → 다음 트윗 추가
4. 두 번째 트윗 내용 복붙
5. 이 과정을 마지막 트윗까지 반복 (5~8개)
6. 모든 트윗 확인 후 `Post all` 클릭

**Step 3: 포스팅 후**
1. @wewantpeace_ 프로필에서 Thread 1을 **고정 트윗**으로 설정
   - 첫 번째 트윗의 `...` 메뉴 → `Pin to your profile`
2. 1시간 이내에 들어오는 답글에 응답

### 포스팅 일정

| 요일 | 쓰레드 | 주제 |
|------|--------|------|
| 월요일 | Thread 1 | 창업자 소개 + WeWantPeace |
| 화요일 | Thread 2 | 기술 스택 공개 |
| 수요일 | Thread 3 | KScore 알고리즘 |
| 목요일 | Thread 4 | 24.5시간 조기 감지 케이스 |
| 금요일 | Thread 5 | 수익 모델 (Free/Pro/Pro+) |
| 토요일 | Thread 6 | 데이터 파이프라인 |
| 일요일 | Thread 7 | 다음 목표 + 피드백 |

### 최적 포스팅 시간
- 매일 오전 9:00 AM ET (한국 시간 밤 11:00)
- 또는 오전 12:00 PM ET (한국 시간 오전 2:00) -- 미국 점심시간

---

## 4. Awesome Lists PR 제출

### 사전 준비
- [ ] GitHub 계정 로그인
- [ ] WeWantPeace 레포가 **public**으로 설정되어 있는지 확인
- [ ] 영어 README가 있는지 확인
- [ ] `docs/marketing/awesome-lists-prs.md` 파일을 열어둘 것

### Step-by-step: awesome-osint PR (최우선)

**Step 1: 레포 포크**
1. https://github.com/jivoi/awesome-osint 접속
2. 우측 상단 `Fork` 버튼 클릭
3. `Create fork` 클릭 (자신의 계정으로 포크됨)

**Step 2: 파일 수정**
1. 포크된 레포에서 `README.md` 파일 클릭
2. 연필 아이콘 (Edit this file) 클릭
3. `Ctrl+F`로 "News" 검색 → "News Digest and Discovery Tools" 섹션 찾기
4. 알파벳 순서(W 위치)에 다음 내용 추가:
   ```
   - [WeWantPeace](https://www.wewantpeace.live) - Real-time global conflict monitoring platform aggregating 200+ open sources (RSS feeds, Telegram OSINT channels) across 195 countries with AI-powered severity scoring, multi-tier source clustering, interactive crisis map, and country-level tension index tracking. Open methodology published.
   ```
5. 하단의 `Commit changes` 클릭
6. 커밋 메시지: `Add WeWantPeace - real-time global conflict monitoring platform`
7. `Commit changes` 확인

**Step 3: PR 생성**
1. 포크된 레포 상단에 `Contribute` → `Open pull request` 클릭
2. PR 제목:
   ```
   Add WeWantPeace to News Digest and Discovery Tools
   ```
3. PR 본문에 `awesome-lists-prs.md`의 "Priority 1" PR Body 섹션 복붙
4. `Create pull request` 클릭

**Step 4: 나머지 PR (같은 날 또는 다음 날)**

같은 방식으로:
1. **awesome-disastertech** -- `awesome-lists-prs.md`의 "Priority 2" 참조
2. **awesome-humanitarian-foss** -- "Priority 3" 참조
3. **ALL-about-RSS** -- "Priority 4" 참조

각 레포를 포크 → 파일 수정 → PR 생성.

### 주의사항
- PR 설명에 self-promotion disclosure를 반드시 포함할 것
- 머지 안 되면 정중하게 1회 코멘트. 그 이상 push하지 말 것.
- awesome-selfhosted는 2026-06-25 이후에 제출 (4개월 규칙)

---

## 5. Reddit 포스팅

### 사전 준비 (2~4주 필요)
- [ ] Reddit 계정 (https://www.reddit.com) -- 기존 계정이 있으면 그것 사용
- [ ] `docs/marketing/reddit-strategy.md` 파일을 열어둘 것
- [ ] r/dataisbeautiful 포스트용 데이터 시각화 이미지 1장 제작

### Phase 1: 카르마 빌딩 (2~4주)

**이것이 가장 중요합니다.** 카르마 없이 바로 포스팅하면 삭제됩니다.

**매일 10분씩:**
1. Reddit 로그인
2. r/dataisbeautiful, r/InternetIsBeautiful, r/geopolitics 접속
3. 흥미로운 포스트 3~5개에 **진심 어린 댓글** 작성
4. 방법론, 데이터 소스, 시각화 선택에 대해 의미 있는 의견 제시
5. **WeWantPeace를 절대 언급하지 말 것** (이 단계에서는)

**목표: 500+ 코멘트 카르마**

### Phase 2: 데이터 시각화 포스트 (선행 포스트)

WeWantPeace를 직접 홍보하지 않는 데이터 분석 포스트를 먼저 올립니다.

**Step 1: 시각화 제작**
- 주제: "500개 분쟁 이벤트 분석: 지역 미디어가 국제 미디어보다 평균 12.9시간 먼저 보도"
- matplotlib/plotly/d3.js 등으로 bar chart 또는 scatter plot 제작
- PNG로 저장

**Step 2: r/dataisbeautiful에 포스트**
1. https://www.reddit.com/r/dataisbeautiful/ 접속
2. `Create Post` 클릭
3. `Images & Video` 탭 선택
4. 제목:
   ```
   [OC] I tracked every major conflict event across 195 countries for 9 days. Regional media reported events an average of 12.9 hours before international outlets.
   ```
5. 이미지 업로드
6. Flair: `[OC]` 선택
7. 댓글로 데이터 소스 + 방법론 설명 추가 (reddit-strategy.md의 "Post 2" Comment 참조)
8. Submit

### Phase 3: WeWantPeace 포스팅 (Phase 2 성공 후 3~5일 뒤)

**Post A: r/InternetIsBeautiful**
1. https://www.reddit.com/r/InternetIsBeautiful/ 접속
2. `Create Post` → `Link` 탭
3. 제목 복붙 (reddit-strategy.md의 "Post 1" Title)
4. URL: `https://www.wewantpeace.live`
5. Submit
6. **즉시** First Comment 복붙 (reddit-strategy.md의 "Post 1" First Comment)

**Post B: r/SideProject (3~5일 후)**
1. https://www.reddit.com/r/SideProject/ 접속
2. `Create Post` → `Text` 탭
3. 제목 + 본문 복붙 (reddit-strategy.md의 "Post 3")
4. Submit

### 포스팅 최적 시간
- r/InternetIsBeautiful: 화~수요일, 오전 10 AM ET (한국 시간 밤 12:00)
- r/dataisbeautiful: 수~목요일, 오전 9 AM ET (한국 시간 밤 11:00)
- r/SideProject: 토~일요일, 오전 11 AM ET (한국 시간 오전 1:00)

### Reddit 절대 금지 사항
1. 업보트 부탁 금지 (즉시 벤)
2. 같은 날 여러 서브레딧에 같은 내용 포스팅 금지
3. 부계정 사용 금지 (Reddit이 감지함)
4. 부정적 댓글에 방어적 반응 금지 (감사하고 인정하기)
5. 마케팅 용어 ("혁신적", "게임 체인저") 사용 금지

---

## 전체 타임라인 (권장)

```
Week 1:
  - Day 1 (화): Show HN 포스팅 + X Thread 1 시작
  - Day 2 (수): X Thread 2
  - Day 3 (목): X Thread 3
  - Day 4 (금): Bellingcat 이메일 발송 + X Thread 4
  - Day 5 (토): X Thread 5
  - Day 6 (일): X Thread 6
  - Day 7 (월): X Thread 7 + GIJN/OCCRP 이메일

Week 2:
  - Awesome Lists PR 4건 제출 (하루에 2건씩)
  - Reddit 카르마 빌딩 시작 (매일 10분)
  - HN/X 결과 분석, 후속 대응

Week 3-4:
  - Reddit 카르마 빌딩 계속
  - r/dataisbeautiful 선행 데이터 시각화 포스트

Week 5:
  - r/InternetIsBeautiful 포스팅
  - r/SideProject 포스팅 (3~5일 후)
```

---

## 성과 추적

각 채널별 결과를 기록하세요:

| 채널 | 날짜 | 결과 (조회/업보트/댓글) | 유입 트래픽 | 가입 수 | 메모 |
|------|------|----------------------|-----------|---------|------|
| Show HN | | | | | |
| Bellingcat | | 답장 여부: | | | |
| X Thread 1 | | | | | |
| X Thread 2 | | | | | |
| X Thread 3 | | | | | |
| X Thread 4 | | | | | |
| X Thread 5 | | | | | |
| X Thread 6 | | | | | |
| X Thread 7 | | | | | |
| awesome-osint PR | | 머지 여부: | | | |
| awesome-disastertech PR | | 머지 여부: | | | |
| awesome-humanitarian-foss PR | | 머지 여부: | | | |
| ALL-about-RSS PR | | 머지 여부: | | | |
| Reddit r/dataisbeautiful | | | | | |
| Reddit r/InternetIsBeautiful | | | | | |
| Reddit r/SideProject | | | | | |

---

## 긴급 대응 가이드

### Show HN가 프론트페이지에 올랐을 때
1. 2시간 동안 모든 댓글에 5분 이내 답변
2. 서버 상태 모니터링 (트래픽 급증 대비)
3. X에서 "We're on the HN front page!" 트윗 (겸손하게)

### 부정적 반응이 많을 때
1. 절대 방어적으로 대응하지 말 것
2. 유효한 비판은 "Good point. I'll look into this." 로 인정
3. 악의적 댓글은 무시 (답글 달지 말 것)
4. 포스트 삭제하지 말 것 (더 나쁜 인상)

### 서버가 다운됐을 때 (HN 허그)
1. Railway 대시보드에서 인스턴스 스케일업
2. HN 댓글에 "Working on scaling, back soon" 메시지
3. 서버 복구 후 "We're back up!" 댓글 추가

---

## 체크리스트: 포스팅 전 최종 확인

- [ ] https://www.wewantpeace.live 접속 정상 확인
- [ ] 영어 UI로 전환 정상 작동 확인
- [ ] 지도, 트렌딩, 긴장도 페이지 모두 로딩 확인
- [ ] 모바일에서도 정상 표시 확인
- [ ] https://github.com/nameofkk/wewantpeace-methodology 접근 가능 확인
- [ ] Open Graph / Twitter Card 미리보기 정상 확인 (https://cards-dev.twitter.com/validator)
- [ ] 서버 응답 속도 양호 확인 (3초 이내)

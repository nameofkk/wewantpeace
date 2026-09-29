# r/OSINT 게시 초안 — 방법론 글 (홍보 아님)

상태: 초안. 올리지 않았음. 올리는 건 사장님 몫.

## 올리기 전 확인할 것

- [ ] r/OSINT 사이드바 규칙을 다시 읽는다. 자기 도구 홍보 금지 규칙이 있으면 링크를 빼고 방법론만 올린다.
- [ ] 계정 카르마·활동 이력 확인. 새 계정이면 먼저 다른 글에 댓글로 몇 주 참여한다(90/10).
- [ ] 아래 숫자가 올리는 날에도 맞는지 다시 잰다(2026-09-30 기준 값이다).
- [ ] 본문에 링크는 넣지 않는다. 누가 물어보면 댓글로만.
- [ ] 제목에 "I built"를 넣지 않는다. 지난번 r/ClaudeAI 글은 개발자만 모였다.

---

## Title

What broke when we tried to count "independent sources" for conflict events automatically

## Body

For the past six months I've been running a pipeline that pulls conflict reporting from about 60 RSS feeds, a handful of Telegram channels and a few APIs, groups reports about the same event, and counts how many independent outlets back each one. The counting turned out to be the easy part. The data underneath it was not. Some of what I found, in case it helps anyone doing similar work:

**1. A lot of "new" RSS items are old.** In one week, 1,627 of 11,226 items (14%) had a publish date more than 72 hours before we collected them, and 1,163 were more than a month old. Search-style feeds (Google News queries, think-tank feeds) were the worst. If you timestamp by collection time, old stories show up as today's news. We now drop anything published more than 72 hours before collection, and keep undated items on collection time.

**2. Event grouping drifts.** Our merge step compared a new cluster with an old one by size but not by age. Each day a small fresh cluster absorbed the previous day's big one, so a single "Iran" issue ended up holding 1,475 reports going back to March. The fix was boring: refuse any merge where the combined span passes five days or the combined size passes a cap, and close clusters after five quiet days. Before that, 27,000 clusters that had been silent for over a month were still marked active.

**3. "Max severity" saturates.** Keeping the highest severity ever seen meant every long-running story sat at 100/100 within days, which made the score useless for ranking. A peak that halves every 48 hours behaves much better.

**4. Source counts need a floor on what counts.** Aggregator channels repost wire copy within minutes, and state or partisan channels inflate counts for their own side. We count each outlet once, and channels we can't verify are labelled and left out of the count rather than removed from the timeline.

**5. Most of our "traffic" wasn't people.** Social link previews (Meta's crawler alone came from over 1,300 IPs) and scrapers on residential IPs outnumbered real browsers. Filtering out visitors that never load JavaScript left about 14 real people a day.

Questions for people who do this by hand: how do you decide when two reports are the same event, and what do you do with a claim that only appears in one channel but is later picked up by wires? I'd like to compare our rules with how analysts actually work.

---

## 댓글로 물어보면 답할 것 (미리)

- 소스 목록: 공개 가능 (METHODOLOGY.md). 등급 기준 A/B/C/D.
- "정확도 어떻게 검증?"(지난번 최다 추천 질문): 출처 수를 보여 주는 것까지가 현재 수준이라고 솔직하게. 사람 검수 없음.
- 링크 요청 시에만: https://www.wewantpeace.live/?ref=reddit

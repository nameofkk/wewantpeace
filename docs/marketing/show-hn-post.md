# Show HN 포스트 — WeWantPeace

## 제목 후보

### A (추천)
> Show HN: WeWantPeace – Real-time conflict monitoring for 195 countries with AI scoring

### B (API 강조)
> Show HN: WeWantPeace – Open API for global conflict data with AI-powered crisis scores

### C (1인 개발 강조)
> Show HN: WeWantPeace – I built a real-time geopolitical risk dashboard as a solo dev

---

## 본문

```
Hi HN,

I'm a solo developer from South Korea, and I built WeWantPeace — a real-time
platform that monitors conflicts and security events across 195 countries.

**Why I built this:**

During the brief martial law incident in South Korea (Dec 2024), I realized how
hard it was to get a clear, real-time picture of what was happening from an
international security perspective. Existing tools were either paywalled
intelligence platforms ($$$), slow academic datasets, or scattered news feeds
with no structure. I wanted something that anyone could use to understand "what's
happening where, and how bad is it" at a glance.

**How it works:**

- Ingests 60+ global RSS news sources every 3-5 minutes
- GPT-4o-mini classifies, deduplicates, and summarizes each event
- Events are clustered by topic/region and plotted on an interactive map
- Two custom scoring algorithms run continuously:
  - **Tension Index** (0-100): Country-level risk score updated every 5 min,
    weighted by event severity (55%), activity volume (35%), and regional
    spillover (10%)
  - **KScore** (0-10): Personalized impact score — "how much does this issue
    affect YOUR country" based on geographic proximity, alliances, and economic
    ties
- KScore-based real-time alerts flag sudden surges and send push notifications

**Tech stack:**

- Frontend: Next.js 14 (App Router) + Tailwind, deployed on Vercel
- Backend: FastAPI + SQLAlchemy + PostgreSQL (Supabase), deployed on Railway
- Worker: Celery + Redis for async news ingestion and scoring pipelines
- Data sources: RSS feeds, GDELT, ACLED, USGS earthquake API
- AI: GPT-4o-mini for classification/summarization
- Push: Firebase Cloud Messaging
- Also available as a PWA and Android app

**What makes it different:**

1. It's free to use (with a Pro tier for power users)
2. It covers ALL 195 countries, not just the ones in the news cycle
3. The scoring is transparent — you can see exactly how Tension Index and KScore
   are calculated
4. There's a public API (free tier included) if you want to build on top of it
5. Bilingual (Korean/English) from day one

**What I'd love feedback on:**

- Is the scoring methodology (Tension Index / KScore) intuitive?
- Any data sources I'm missing that would improve coverage?
- UX feedback — especially the map experience on mobile
- Ideas for the API — what endpoints would be most useful?

The whole thing is built and maintained by me alone, so I'm sure there are rough
edges. Would really appreciate honest feedback from this community.

URL: https://www.wewantpeace.live
API docs: https://www.wewantpeace.live/api (free tier available)
```

---

## 예상 질문 + 답변

### Q1: "How do you handle bias in your news sources?"

```
Great question. A few things I do to mitigate this:

1. Source diversity: I pull from 60+ sources across multiple regions and
   languages (Reuters, Al Jazeera, KCNA Watch, Xinhua, etc.) — the goal is to
   have conflicting perspectives cancel out extreme bias rather than relying on
   any single source.

2. The AI classification step focuses on extracting factual claims (who, what,
   where, severity) rather than editorial framing. GPT-4o-mini is prompted to
   ignore opinion and focus on verifiable events.

3. The scoring algorithms weight event frequency and cross-source corroboration.
   A claim reported by 5 independent sources scores higher than one from a
   single outlet.

That said, bias is an inherent challenge and I don't claim to have solved it.
If you notice specific blind spots, I'd genuinely appreciate the feedback.
```

### Q2: "Why GPT-4o-mini instead of running your own model?"

```
Practical reasons: as a solo dev, training and hosting my own classification
model would be a massive time/cost sink with marginal quality gains for this
use case. GPT-4o-mini hits a sweet spot — it's cheap (~$0.15/1M input tokens),
fast, and accurate enough for news classification and summarization.

My current costs are roughly $30-50/month for the AI layer processing thousands
of articles daily. If costs become a problem at scale, I have a few options:
fine-tune a smaller open model (Llama/Mistral) on my labeled dataset, or add
more rule-based pre-filtering to reduce the number of API calls. But right now,
the ROI of using GPT-4o-mini is hard to beat.
```

### Q3: "How is this different from GDELT or ACLED?"

```
GDELT and ACLED are fantastic datasets and I actually use both as data sources.
The difference is in the layer I build on top:

- GDELT is raw event data (millions of records) — powerful but requires
  significant processing to be human-readable. WeWantPeace does that processing
  for you.
- ACLED is curated but focuses on political violence/protests and updates
  weekly. WeWantPeace updates every 3-5 minutes and covers a broader range of
  security events.
- Neither provides a personalized impact score. KScore answers "why should I
  care about this event in country X" based on your home country's relationship
  with the affected region.

Think of it as: GDELT/ACLED are databases. WeWantPeace is a dashboard that
makes them (plus 60+ other sources) actionable for non-researchers.
```

### Q4: "What's your data pipeline architecture?"

```
The pipeline is:

1. Celery workers poll RSS feeds every 3-5 minutes
2. New articles get fingerprinted (title + source + timestamp hash) for dedup
3. GPT-4o-mini extracts structured data: event type, countries, severity, summary
4. A clustering algorithm groups related events — e.g., 15 articles about the
   same missile test become one "issue cluster"
5. Each cluster gets scored (Tension Index contribution + KScore) and plotted

The clustering uses entity matching (country/actor overlap), temporal proximity,
and semantic similarity from the AI-generated summaries. It's not perfect —
sometimes related events end up in separate clusters — but it handles the 80%
case well.
```

### Q5: "Solo dev — how do you plan to sustain this?"

```
Honest answer: I'm not sure yet, and I think that's okay at this stage.

Current hosting costs are ~$80-100/month (Railway + Vercel + Supabase + OpenAI
API). The Pro tier ($4.99/month) doesn't need many subscribers to cover that.

My priority right now is making something genuinely useful and getting real user
feedback. If it gains traction, there are natural expansion paths: enterprise
API access, custom alerting for NGOs/journalists, regional deep-dives.

As for burnout: the system is mostly automated. Once the pipeline is stable,
daily maintenance is ~30 min of checking data quality and tweaking
classification rules. The hardest part was building it; running it is manageable.
```

---

## 포스팅 팁

- **최적 시간**: 미국 동부 오전 8-10시 = 한국 밤 10시~자정, 화~목이 최적
- **첫 1-2시간** 댓글에 빠르게 응답 (알고리즘이 활발한 포스트를 상위 유지)
- **톤**: 겸손+솔직, "You're right, I hadn't thought of that"가 HN 최고의 답변
- **비판에도 감사 표하기**

# Show HN: WeWantPeace -- Real-time global conflict tracker with personalized severity scoring

> **Purpose**: Get on HN front page to build awareness in the tech community + collect feedback
> **Goal**: 100+ upvotes, 30+ comments, 3,000-20,000 visits
> **Expected**: Front page = 5,000-20,000 visits/day. Miss = 200-500.

---

## Title

```
Show HN: WeWantPeace – Real-time global conflict tracker with personalized severity scoring
```

## URL

```
https://www.wewantpeace.live
```

---

## First Comment (post immediately after submission)

Hi HN. I'm the solo developer behind this. Some context on why I built it.

I started my first company at 18. After military service, I spent 5 years in the industry, then co-founded another startup that grew to ~$3.7M in annual revenue before I exited. I moved to Jeju Island and ran a guesthouse for a while, trying to figure out what I actually wanted to work on.

Then the phone alerts started getting to me. Every time a civil defense alarm or emergency notification went off on my phone, my heart would race. I realized I had a genuine fear of conflict -- but no good tool to make sense of what was actually happening in the world. Academic datasets (ACLED, GDELT) update too slowly. News is fragmented. Risk platforms cost five figures a year.

So I started building what I wanted: a single dashboard that answers "What's happening right now, and how much should I care?" -- updated every 5 minutes, not monthly.

### How it works

1. **Collection** -- ~200 RSS feeds + Telegram OSINT channels polled every 3-5 minutes via Celery beat.
2. **Normalization** -- GPT-4o-mini classifies each event: topic (conflict, terrorism, coup, sanctions, cyber, etc.), severity (0-100), country extraction, Korean translation, deduplication.
3. **Clustering** -- Events are grouped into IssueCluster objects using title similarity (40%+ threshold) + country/topic matching.
4. **KScore** -- Key Impact Score (0-10) personalizes importance to your home country. Formula: `raw = 0.25*velocity + 0.15*quality + 0.40*severity + 0.20*spread`, then scaled with time decay. A country-specific impact factor (geography, security alliances, economic ties) adjusts the final score.
5. **Tension Index** -- Per-country risk score (0-100), updated every 5 minutes: `0.55*EventScore + 0.35*ActivityScore + 0.10*Spillover`.
6. **Spike Detection** -- Cumulative event-count anomaly detection triggers real-time push notifications via FCM.

### Does it actually work? Some numbers (March 1-9, 2026)

During the recent Iran escalation, I ran a retrospective analysis comparing when our system first collected a signal (via Tier-B/C sources) vs. when Tier-A outlets (Reuters, AP, BBC) published:

- Mojtaba Khamenei succession was collected via a Telegram OSINT channel **24.5 hours** before major outlets covered it.
- Lebanese airstrike casualty reports (102 killed) appeared **18 hours** before Tier-A confirmation.
- UAE drone/missile interception (131 drones, 6 missiles) -- regional sources hit our pipeline **12.9 hours** ahead.
- Across 50 high-severity clusters, Tier-B/C sources beat Tier-A in **46% of cases**, with a median lead time of ~12.9 hours.

The largest single cluster tracked 119 events from 21 independent sources over 7 days.

I want to be upfront: this isn't magic. Regional and Arabic-language media simply report on local events faster than international outlets, which have additional verification cycles. The system's value is in aggregating those signals automatically and scoring them consistently.

### Tech stack

- Frontend: Next.js 14, TypeScript, Tailwind CSS, Zustand, React Query
- Backend: FastAPI (Python 3.11), SQLAlchemy 2.0 (async), Pydantic
- Worker: Celery 5.3 + Redis (Beat scheduler)
- Database: PostgreSQL 15 (Supabase) + TimescaleDB
- AI: OpenAI GPT-4o-mini for classification/normalization
- Auth: Firebase Authentication
- Push: Firebase Cloud Messaging
- Infra: Railway (Docker), GitHub Actions CI/CD
- Auto-posting: X, Threads, Instagram (automated via worker)

### What makes it different

- **KScore personalization**: The same event scores differently depending on whether you're in Seoul, Berlin, or Nairobi. A missile test in the Pacific scores 8.5 for Seoul, 3.2 for Berlin -- because the real-world impact IS different.
- **5-minute freshness**: Not a daily digest -- data flows continuously from 200+ sources.
- **Multi-tier source aggregation**: Telegram OSINT channels + regional media + international wires, all scored and clustered together.
- **Bilingual**: Full Korean/English UI.
- **Free tier**: Trending issues, tension overview, and spike alerts without paywall.
- **Open methodology**: Scoring formulas, source tiers, and case studies are published at https://github.com/nameofkk/wewantpeace-methodology

### Pricing (since someone will ask)

- **Free**: 2 watched countries, basic alerts (3/day), tension history 7 days
- **Pro** ($3.50/mo): 5 countries, real-time map, KScore filter 3.0+, 30-day history, 10 alerts/day
- **Pro+** ($7/mo): Unlimited countries, KScore filter 1.5+, 90-day history, 50 alerts/day

I funded the development myself from the exit. No VC money. Running costs are manageable on Railway.

### Open methodology

Full scoring formulas, source tier definitions, and case studies: https://github.com/nameofkk/wewantpeace-methodology

I'd love feedback on the scoring methodology, data coverage gaps, or features you'd find useful. Happy to dive into any technical details.

---

## HN Posting Tips (internal notes, do not post)

### Timing
- Post on Tuesday, Wednesday, or Thursday
- Best time: 8:00-9:00 AM ET (HN peak traffic)
- Avoid Monday mornings and Fridays

### Engagement strategy
- Reply to every comment within the first 2 hours
- Be specific and technical in responses
- If someone points out a flaw, acknowledge it genuinely
- Don't be defensive -- HN rewards humility

### Common HN questions to prepare for
1. "Why GPT-4o-mini instead of local models?" -- Cost vs. accuracy tradeoff at scale; open to exploring local alternatives.
2. "What about bias in AI classification?" -- Publish methodology openly for this reason; severity scores are formula-based, not pure LLM output.
3. "How do you handle misinformation from Telegram?" -- Tier system exists precisely for this; Tier-C signals are weighted lower until corroborated.
4. "Privacy concerns with Firebase?" -- Standard auth flow; no tracking beyond what's needed for personalization.
5. "What's the API like?" -- Public API endpoints exist (rate-limited). Full API for researchers is on the roadmap.
6. "How does this compare to ACLED/GDELT?" -- They're academic datasets (great for research, slow updates). This is real-time monitoring with personalization.

### What NOT to do
- Do not mention revenue/exit in a bragging way -- frame as "this is why I could afford to build this full-time"
- Do not use marketing language ("revolutionary", "game-changing")
- Do not post from a new HN account -- use an established account if possible
- Do not ask friends to upvote (HN detects and penalizes this)

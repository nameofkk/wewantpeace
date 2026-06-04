# X (Twitter) #BuildInPublic -- 7 Thread Series

> **Purpose**: Build follower base in the indie hacker community + sustained interest
> **Goal**: 10-50 likes per tweet, 50-200 new followers per week
> **Expected**: All 7 threads combined = 10,000-50,000 total impressions
>
> **Posting schedule**: 1 thread per day, Mon-Sun, 9 AM ET
> **Hashtags**: #BuildInPublic #IndieHacker #SaaS
> **Account**: @wewantpeace_

---

## Thread 1: Founder Intro + What Is WeWantPeace (Monday)

### Tweet 1/7 (Hook)
I started my first company at 18.

Built it to ~$3.7M revenue. Exited. Moved to Jeju Island. Ran a guesthouse.

Then I got obsessed with one question: "Is the world getting more dangerous, or does it just feel that way?"

So I built something to find out.

Thread

### Tweet 2/7
Every time a civil defense alert hit my phone, my heart would race.

Not because I was in danger. But because I had NO way to tell what was real vs. noise.

That fear became the seed for @wewantpeace_

### Tweet 3/7
WeWantPeace monitors 195 countries in real-time.

Every 5 minutes it:
- Scans 200+ sources (RSS + Telegram)
- AI-classifies each event
- Scores severity (0-100)
- Clusters related reports
- Calculates a personalized impact score for YOUR country

### Tweet 4/7
The key feature: KScore (0-10)

Same event, different score depending on where you live.

A missile test in the Pacific:
- Seoul: 8.5
- Berlin: 3.2
- Nairobi: 1.8

Because the real impact IS different.

### Tweet 5/7
During the March 2026 Iran crisis, our system detected events up to 24.5 HOURS before Reuters/AP/BBC.

Not because we're smarter. Regional media just reports faster. We aggregate those signals automatically.

### Tweet 6/7
Current stats:
- 200+ sources monitored 24/7
- 195 countries covered
- 5-minute refresh cycle
- Bilingual (Korean/English)
- PWA + Android app
- Solo developer (yes, really)

### Tweet 7/7
Try it free: https://www.wewantpeace.live

No signup wall for core features. Trending issues, tension overview, spike alerts -- all free.

I'm building this in public. Follow along for the technical deep dives this week.

#BuildInPublic #IndieHacker #SaaS

---

## Thread 2: Tech Stack Deep Dive (Tuesday)

### Tweet 1/7 (Hook)
Here's the entire tech stack behind a platform that monitors 195 countries in real-time.

Solo dev. No team. $0 VC.

Let me walk you through every piece.

### Tweet 2/7
Frontend:
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- Zustand (state)
- React Query (data fetching)
- MapLibre GL (interactive map)

SSR for SEO. PWA for mobile. TWA for Android app.

### Tweet 3/7
Backend:
- FastAPI (Python 3.11)
- SQLAlchemy 2.0 (fully async)
- Pydantic v2 (validation)
- Alembic (migrations)

Why FastAPI? Async native. Type hints. Auto-generated docs. Perfect for a solo dev who needs speed.

### Tweet 4/7
Worker pipeline:
- Celery 5.3 + Redis
- Beat scheduler (5-min cycle)

Every 5 minutes:
1. Poll 200+ RSS feeds + Telegram
2. GPT-4o-mini normalizes each event
3. Deduplicate
4. Cluster into issues
5. Score (KScore + Tension Index)
6. Spike detection -> push alert

### Tweet 5/7
Database:
- PostgreSQL 15 (Supabase)
- TimescaleDB extension (time-series)

Why TimescaleDB? Tension Index needs efficient time-series queries. Hourly rollups. 90-day retention for Pro+ users.

### Tweet 6/7
Infrastructure:
- Railway (Docker containers)
- GitHub Actions CI/CD
- Firebase Auth + FCM (push)
- OpenAI API (GPT-4o-mini)

Monthly infra cost: surprisingly manageable for a solo project. Railway's been solid.

### Tweet 7/7
Total cost breakdown (monthly):
- Railway: ~$30-50
- Supabase: ~$25
- OpenAI API: ~$40-80
- Firebase: free tier
- Domain: $12/yr

Building a global monitoring platform for under $150/mo.

The exit money buys me time to do it right.

#BuildInPublic #IndieHacker #SaaS

---

## Thread 3: KScore Algorithm Explained (Wednesday)

### Tweet 1/8 (Hook)
How do you score "how much should I care about this crisis?"

I built an algorithm called KScore. It personalizes every global event to YOUR country.

Here's exactly how it works (with real examples).

### Tweet 2/8
KScore formula:

raw = 0.25 * velocity
    + 0.15 * quality
    + 0.40 * severity
    + 0.20 * spread

Then: time decay + country impact factor

Output: 0 to 10 scale.

Let me break down each component.

### Tweet 3/8
**Velocity** (25%): How fast are new reports coming in?

A cluster going from 3 to 15 events in 2 hours = high velocity.

This catches escalation before severity alone would flag it.

### Tweet 4/8
**Quality** (15%): Source diversity.

5 reports from the same outlet = low quality.
5 reports from 5 different outlets across 3 tiers = high quality.

More independent sources = more confidence the event is real.

### Tweet 5/8
**Severity** (40%): How bad is the event?

GPT-4o-mini scores each event 0-100 based on:
- Type (nuclear > border skirmish)
- Scale (casualties, geographic scope)
- Precedent (first strike vs. ongoing)

Heaviest weight because... it matters most.

### Tweet 6/8
**Spread** (20%): Geographic footprint.

Events spanning multiple countries score higher.

Iran-US escalation touching Iran + UAE + Lebanon + Saudi = high spread.

### Tweet 7/8
**Country impact factor**: The secret sauce.

Same raw score, different final KScore:

Iran missile test:
- Seoul (alliance, proximity): 8.5
- Berlin (NATO ally, less exposed): 4.1
- Buenos Aires (distant, limited ties): 2.3

Factors: geography, alliances, trade dependencies, diaspora.

### Tweet 8/8
KScore isn't perfect. It's v1.

Known limitations:
- Economic tie data needs updating
- Small countries underweighted
- Cyber events hard to geolocate

But it's better than "everything is equally scary."

Try it: https://www.wewantpeace.live

#BuildInPublic #IndieHacker #SaaS

---

## Thread 4: Case Study -- 24.5 Hours Early Detection (Thursday)

### Tweet 1/7 (Hook)
Our system detected the Mojtaba Khamenei succession story 24.5 HOURS before Reuters, AP, and BBC.

Here's exactly how that happened. No magic. Just multi-source aggregation.

### Tweet 2/7
March 3, 2026, 21:33 UTC.

A Telegram OSINT channel posts about Mojtaba Khamenei's appointment as Iran's new Supreme Leader.

Our Celery worker picks it up within 2 minutes. Tags it: Tier-C source, severity 91, topic "political transition."

### Tweet 3/7
For the next 24 hours: silence from major outlets.

Our system had it classified, scored, and clustered. But Reuters, AP, BBC? Nothing yet.

They were still verifying.

### Tweet 4/7
March 4, 2026, ~22:00 UTC.

Al Jazeera: "Iran's wartime succession: What direction after Khamenei?"
BBC: "Leaving leadership in the hands of temporary council..."

24.5 hours after our first signal.

### Tweet 5/7
Why the gap?

Tier-A outlets have verification cycles. That's GOOD -- it means they're accurate.

But for situational awareness? You want the early signal too.

That's what multi-tier aggregation gives you.

### Tweet 6/7
More examples from the same week:

- Lebanon airstrike (102 killed): 18h early
- UAE drone interception (131 drones): 12.9h early
- Tehran military academy strike: 4.3h early

46% of high-severity clusters = Tier-B/C detected first.

### Tweet 7/7
I'm not claiming to beat Reuters at journalism.

I'm saying: if you aggregate regional + Telegram sources alongside wire services, you get a more complete picture, faster.

That's the whole thesis.

Full case studies: https://github.com/nameofkk/wewantpeace-methodology

#BuildInPublic #IndieHacker #SaaS

---

## Thread 5: Revenue Model -- Free/Pro/Pro+ (Friday)

### Tweet 1/6 (Hook)
Time to talk money.

WeWantPeace has 3 tiers. Here's what each costs, what it includes, and why I priced it this way.

Full transparency.

### Tweet 2/6
**Free tier** ($0/forever):
- 2 watched countries
- Trending issues feed
- Tension overview (7-day history)
- 3 push alerts/day
- Spike notifications

No signup wall for browsing.

Most people probably never need to upgrade.

### Tweet 3/6
**Pro** ($3.50/mo):
- 5 watched countries
- Real-time interactive crisis map
- KScore filter: 3.0~10.0
- 30-day tension history
- 10 push alerts/day
- Topic filter + DND hours

### Tweet 4/6
**Pro+** ($7/mo):
- Unlimited watched countries
- KScore filter: 1.5~10.0
- 90-day tension history
- 50 push alerts/day
- Everything in Pro

Target users: journalists, analysts, security professionals, researchers.

### Tweet 5/6
Why these prices?

I exited a previous startup at ~$3.7M revenue. I don't need this to be a unicorn.

Goal: cover infrastructure costs + fund full-time development.

$150/mo infra cost. 50 Pro users = break even.

### Tweet 6/6
Current revenue: $0.

Just launched. Zero paying users yet.

But the free tier is fully functional and I'm using it myself every day.

If you want to try it: https://www.wewantpeace.live

Will share revenue updates as they come.

#BuildInPublic #IndieHacker #SaaS

---

## Thread 6: Data Pipeline Deep Dive (Saturday)

### Tweet 1/7 (Hook)
Every 5 minutes, my system processes hundreds of events from 200+ sources in 195 countries.

Here's the entire data pipeline, from raw RSS feed to push notification.

### Tweet 2/7
**Step 1: Collection** (Celery Beat, every 3-5 min)

- 200+ RSS feeds (Reuters, AP, Al Jazeera, regional outlets...)
- Telegram OSINT channels (defense/security focused)
- Source tiers: A (international), B (regional), C (Telegram)

Each source has its own polling interval.

### Tweet 3/7
**Step 2: Normalization** (GPT-4o-mini)

Each raw event goes through AI classification:
- Topic: conflict, terrorism, coup, sanctions, cyber, etc.
- Severity: 0-100
- Country/coordinate extraction
- Korean translation (bilingual platform)
- Deduplication hash

### Tweet 4/7
**Step 3: Clustering**

Events about the same incident get grouped into IssueCluster objects.

Algorithm:
- Title similarity > 40% threshold
- Same country + same topic
- Time proximity

The Iran oil depot cluster: 119 events, 21 sources, 7 days.

### Tweet 5/7
**Step 4: Scoring**

Two scores computed per cycle:
- KScore (0-10): personalized impact per user's home country
- Tension Index (0-100): per-country risk level

Formula: 0.55*EventScore + 0.35*ActivityScore + 0.10*Spillover

### Tweet 6/7
**Step 5: Spike Detection**

Cumulative event-count anomaly detection.

When a country's event count deviates significantly from its baseline:
-> Spike triggered
-> FCM push notification sent
-> Auto-posted to X, Threads, Instagram

### Tweet 7/7
**Step 6: Delivery**

- Web: Next.js SSR + React Query polling
- Push: Firebase Cloud Messaging
- Social: Automated posting via worker
- PWA: Installable on mobile
- Android: TWA (Trusted Web Activity)

Total pipeline latency: ~30 seconds from source publication to user notification.

#BuildInPublic #IndieHacker #SaaS

---

## Thread 7: What's Next + Feedback Request (Sunday)

### Tweet 1/6 (Hook)
It's been a week of building in public.

Here's what's on the roadmap for WeWantPeace -- and I need your input on what to prioritize.

### Tweet 2/6
**Near-term (Q1-Q2 2026):**

1. Public API for researchers
2. Historical analysis tools (backtest events)
3. More data sources (500+ target)
4. Weekly digest emails
5. Browser extension for contextual alerts

### Tweet 3/6
**Mid-term (Q2-Q3 2026):**

1. iOS app (native)
2. Collaboration features (shared watchlists)
3. Event correlation engine (detect connected crises)
4. Integration with existing OSINT tools
5. Localization (Japanese, Arabic, Spanish)

### Tweet 4/6
**Things I'm debating:**

- Open-source the whole platform? (currently methodology-only is open)
- Add a free API tier for researchers?
- Community-contributed source feeds?
- Integrate satellite imagery for verification?

What would YOU prioritize?

### Tweet 5/6
**Biggest lesson this week:**

Building a product is 20% of the work.
Getting people to care about it is the other 80%.

I went from "just ship it" to "oh, I actually need to tell people about this."

Solo dev life.

### Tweet 6/6
Thanks for following this thread series.

If any of this resonated, here's how to help:

1. Try it: https://www.wewantpeace.live
2. Give feedback (DMs open)
3. RT if you know someone who'd find this useful
4. Follow for weekly updates

See you next week with more data.

#BuildInPublic #IndieHacker #SaaS

---

## Internal Notes: Thread Posting Strategy

### Character count verification
- All tweets above are within 280 character limit
- Links count as 23 characters (t.co shortening)
- Thread numbering (Tweet X/Y) is for internal reference only -- do not include in actual tweets

### Image/media suggestions
- Thread 1, Tweet 3: Screenshot of the main dashboard
- Thread 2, Tweet 4: Architecture diagram
- Thread 3, Tweet 7: KScore comparison chart (visual)
- Thread 4, Tweet 2: Screenshot of the Telegram signal in the system
- Thread 5, Tweet 2-4: Pricing page screenshot or comparison table image
- Thread 6, Tweet 1: Data flow diagram
- Thread 7, Tweet 2: Roadmap visual

### Engagement tactics
- Quote-tweet each thread from @wewantpeace_ account
- Engage with replies within 1 hour
- Tag relevant people in QRTs, not in original thread
- Pin Thread 1 to profile

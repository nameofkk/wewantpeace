# Show HN Draft

## Title
Show HN: WeWantPeace -- Real-time global conflict monitor with AI-scored impact per country

## Body

I built a platform that monitors conflicts and security events across 195 countries in real-time.

**Live:** https://www.wewantpeace.live
**Open methodology:** https://github.com/nameofkk/wewantpeace-methodology

**The problem:** Existing conflict trackers (ACLED, GDELT) are great datasets but update slowly and require expertise to interpret. News aggregators give you headlines but no structure. I wanted a single dashboard that answers: "What's happening in the world right now, and how much should I care?"

**How it works:**

1. **Collection** -- ~200 RSS feeds and Telegram channels are polled every 3-5 minutes via a Celery beat scheduler.
2. **Normalization** -- Each raw event is processed by GPT-4o-mini: topic classification (conflict, terrorism, coup, sanctions, cyber, etc.), severity scoring (0-100), country/coordinate extraction, Korean translation, and deduplication.
3. **Clustering** -- Events are grouped into IssueCluster objects using title similarity (40%+ threshold) + country/topic matching.
4. **KScore** -- Key Impact Score (0-10) personalizes each issue's importance to your home country. Formula: `raw = 0.25*velocity + 0.15*quality + 0.40*severity + 0.20*spread`, then scaled with time decay. A country-specific impact factor (geography, security alliances, economic ties) adjusts the final score.
5. **Tension Index** -- Per-country risk score (0-100), updated every 5 minutes: `0.55*EventScore + 0.35*ActivityScore + 0.10*Spillover`.
6. **Spike Detection** -- Cumulative event-count anomaly detection triggers real-time push notifications via FCM.

**Does it actually work? Some early numbers (March 1-9, 2026):**

During the recent Iran escalation, I ran a retrospective analysis comparing when our system first collected a signal (via Tier-B/C sources) vs. when Tier-A outlets (Reuters, AP, BBC) published:

- The Mojtaba Khamenei succession story was collected via a Telegram OSINT channel **24.5 hours** before major outlets covered it.
- Lebanese airstrike casualty reports (102 killed) appeared in our system **18 hours** before Tier-A confirmation.
- UAE drone/missile interception (131 drones, 6 missiles) -- regional sources hit our pipeline **12.9 hours** ahead.
- Across 50 high-severity clusters analyzed, Tier-B/C sources beat Tier-A in **46% of cases**, with a median lead time of ~12.9 hours.

The largest single cluster tracked 119 events from 21 independent sources over 7 days. Full case studies and methodology are in the repo linked above.

I want to be upfront: this isn't magic. Regional and Arabic-language media simply report on local events faster than international outlets, which have additional verification cycles. The system's value is in aggregating those signals automatically and scoring them consistently.

**Tech stack:**
- Frontend: Next.js 14, TypeScript, Tailwind CSS, Zustand, React Query
- Backend: FastAPI (Python 3.11), SQLAlchemy 2.0 (async), Pydantic
- Worker: Celery 5.3 + Redis (Beat scheduler)
- Database: PostgreSQL 15 (Supabase) + TimescaleDB
- AI: OpenAI GPT-4o-mini
- Auth: Firebase Authentication
- Push: Firebase Cloud Messaging
- Infra: Railway (Docker), GitHub Actions CI/CD
- SNS auto-posting: X, Threads, Instagram

**Data sources:** International wire services, regional outlets, defense/security Telegram channels. Currently ~200 feeds covering all major conflict zones.

**What makes it different:**
- **KScore personalization:** The same event scores differently depending on whether you're in Seoul, Berlin, or Nairobi.
- **5-minute freshness:** Not a daily digest -- data flows continuously.
- **Multi-tier source aggregation:** Telegram OSINT channels + regional media + international wires, all scored and clustered together.
- **Bilingual:** Full Korean/English UI with auto-detection.
- **Free tier:** No paywall for trending issues, tension overview, and spike alerts.
- **Open methodology:** Scoring formulas, source tiers, and case studies are published openly.

I'd love feedback on the scoring methodology, data coverage, or features you'd find useful. Happy to dive into technical details.

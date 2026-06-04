# Reddit Marketing Strategy for WeWantPeace

> **Purpose**: Drive large-scale traffic from r/InternetIsBeautiful, r/dataisbeautiful, r/SideProject
> **Goal**: Front page entry = 10,000-50,000 visits
> **Expected**: Karma building requires 2-4 weeks. Post success rate ~30%.
>
> **Critical rule**: Reddit HATES self-promotion. "I made this" humble tone only. Data visualization focus.

---

## Pre-requisites: Karma Building Plan (2-4 weeks before posting)

### Why This Matters
Reddit's spam filters and community rules require established accounts. Posting promotional content from a new or low-karma account will get auto-removed or downvoted to oblivion.

### Karma Building Strategy

**Week 1-2: Become a genuine participant**

| Day | Subreddit | Action |
|-----|-----------|--------|
| 1-3 | r/dataisbeautiful | Comment thoughtfully on 3-5 posts. Discuss methodology, data sources, visualization choices. |
| 4-5 | r/InternetIsBeautiful | Comment on interesting tool submissions. Ask genuine questions about tech stack. |
| 6-7 | r/geopolitics | Share informed analysis on current events. DO NOT mention WeWantPeace. |
| 8-10 | r/SideProject | Comment on other people's side projects with genuine feedback. |
| 11-14 | r/webdev, r/learnprogramming | Answer questions about FastAPI, Next.js, or Celery. Be helpful. |

**Week 3-4: Build credibility**

| Day | Action |
|-----|--------|
| 15-17 | Post a non-promotional data analysis in r/dataisbeautiful (e.g., "I analyzed 500 conflict events and found that regional media reports 12.9 hours faster than international outlets [OC]") |
| 18-20 | Engage with the comments on your data post. Be responsive, humble, grateful for feedback. |
| 21-25 | Continue participating naturally. Build to ~500 comment karma minimum. |
| 26+ | Ready to post WeWantPeace submissions. |

### Account Requirements
- **Minimum karma**: 500+ comment karma (recommended: 1,000+)
- **Account age**: 30+ days
- **Genuine participation**: Visible history of non-promotional comments
- **Flair**: Set relevant flair in each subreddit if available

---

## Post 1: r/InternetIsBeautiful

### Subreddit Info
- 17M+ members
- Rule: "websites that are interesting, unique, or beautiful"
- Self-promotion is allowed IF genuinely interesting and disclosed
- NO "app" posts -- must be a website

### Title
```
WeWantPeace.live – A real-time interactive map of every conflict happening in the world right now, updated every 5 minutes
```

### Post Type
Link post: `https://www.wewantpeace.live`

### First Comment (post immediately)

I built this as a solo developer. Quick context on why:

After exiting a startup I co-founded, I spent time on Jeju Island trying to figure out what I wanted to work on. Every time a civil defense alert popped up on my phone, I'd get this spike of anxiety -- but I had no way to quickly understand what was actually happening globally.

Existing tools were either academic (updated monthly) or behind massive paywalls. So I started building what I wanted: a dashboard that answers "what's happening right now, and how concerned should I be?"

The system scans 200+ news sources and Telegram channels every 5 minutes, uses AI to classify and score each event, and clusters them on an interactive map. There's a "Tension Index" for each country (0-100) and a personalized "KScore" that adjusts each event's importance based on your home country.

It's free to browse -- no signup wall. I'd genuinely love feedback on what's useful and what's not.

### Backup Comment (if asked "how does it work")

Technical overview:

- ~200 RSS feeds + Telegram OSINT channels polled every 3-5 minutes
- GPT-4o-mini classifies each event (topic, severity 0-100, location)
- Events are clustered into issues (title similarity + geographic matching)
- KScore (0-10) = personalized impact for your country (factors: proximity, alliances, trade)
- Tension Index (0-100) = per-country risk score, updated every 5 minutes
- Spike detection triggers push notifications

During the recent Iran crisis, the system detected events up to 24.5 hours before Reuters/AP/BBC -- not because it's smarter, but because regional media simply reports faster. The system aggregates those early signals automatically.

Stack: Next.js + FastAPI + PostgreSQL + TimescaleDB + Celery + MapLibre GL

---

## Post 2: r/dataisbeautiful

### Subreddit Info
- 21M+ members
- Strict rules: must include [OC] tag, must have data source
- Focus on DATA VISUALIZATION, not the tool itself
- Posts must include a chart, graph, or visualization

### Strategy
DO NOT post the website directly. Instead, create a data visualization FROM WeWantPeace data and share that. The website is mentioned as the source.

### Title
```
[OC] I tracked every major conflict event across 195 countries for 9 days. Regional media reported events an average of 12.9 hours before international outlets.
```

### Post Type
Image post with a visualization (create before posting)

### Required Visualization
Create one of these:
1. **Bar chart**: Lead time comparison (Tier-A vs Tier-B/C) for the 5 case study events
2. **Scatter plot**: Event severity vs. detection lead time
3. **Heatmap**: Country-level tension index over 9 days (March 1-9)
4. **Timeline**: Event cascade during Iran escalation showing when each tier reported

### Comment (post with image)

Source: I built a real-time conflict monitoring platform called WeWantPeace (https://www.wewantpeace.live) that aggregates 200+ news sources and Telegram OSINT channels every 5 minutes.

Data period: March 1-9, 2026 (during the Iran-US escalation).

Methodology: Each event is tagged with its source tier -- Tier-A (Reuters, AP, BBC, Al Jazeera), Tier-B (regional/local media), Tier-C (Telegram OSINT channels). "Lead time" = when a Tier-B or Tier-C source first reported vs. when the first Tier-A source published.

Key findings:
- 50 high-severity event clusters analyzed
- 46% (23/50) were first detected through Tier-B/C sources
- Median lead time: ~12.9 hours
- Maximum: 24.5 hours (Mojtaba Khamenei succession via Telegram)
- Largest cluster: 119 events from 21 independent sources over 7 days

This isn't magic -- regional and Arabic-language media simply report on local events faster than international outlets, which have verification cycles. The system's value is in aggregating those signals automatically.

Tools: Python (data collection + analysis), the visualization was created with [matplotlib/plotly/d3.js -- whichever you use].

Full case studies and methodology: https://github.com/nameofkk/wewantpeace-methodology

### Required Flair
`[OC]` -- Original Content

---

## Post 3: r/SideProject

### Subreddit Info
- 100k+ members
- Explicitly welcomes side project self-promotion
- Community is supportive, gives constructive feedback
- Much smaller audience but higher engagement rate

### Title
```
I quit my job after a successful exit and built a real-time global conflict tracker as a solo dev. It monitors 195 countries every 5 minutes.
```

### Post Type
Text post with link

### Body

**What is it?**

WeWantPeace (https://www.wewantpeace.live) is a real-time global conflict monitoring platform. It scans 200+ news sources and Telegram OSINT channels every 5 minutes, classifies each event with AI, and presents them on an interactive map with severity scoring.

**Why I built it:**

I started my first company at 18. After military service and 5 years in industry, I co-founded another startup that hit ~$3.7M in annual revenue. After the exit, I moved to Jeju Island and ran a guesthouse while figuring out what I actually wanted to work on.

The catalyst was surprisingly personal: every time a civil defense alert would pop up on my phone, my heart would race. I realized I had a genuine fear of conflict -- but no good way to make sense of what was actually happening in the world. Academic trackers update monthly. News is fragmented. Risk platforms cost five figures a year.

So I started building what I wanted.

**Tech stack:**
- Frontend: Next.js 14, TypeScript, Tailwind, MapLibre GL
- Backend: FastAPI (Python), SQLAlchemy (async), Celery + Redis
- Database: PostgreSQL + TimescaleDB (Supabase)
- AI: GPT-4o-mini for event classification
- Infra: Railway (Docker), GitHub Actions CI/CD
- Push: Firebase Cloud Messaging

**Key features:**
- KScore (0-10): Personalized impact score -- same event, different score depending on your country
- Tension Index (0-100): Per-country risk level, updated every 5 minutes
- Spike detection: Anomaly-based push alerts
- Multi-tier sources: Telegram OSINT + regional media + wire services, all clustered together
- Bilingual: Korean/English

**Does it work?**

During the March 2026 Iran crisis, the system detected events up to 24.5 hours before major outlets. Regional media reports faster than international wires; we just aggregate those signals automatically. 46% of high-severity clusters were detected first through non-traditional sources.

**Revenue model:**
- Free: 2 countries, basic alerts, 7-day history
- Pro ($3.50/mo): 5 countries, map, 30-day history
- Pro+ ($7/mo): Unlimited countries, 90-day history

Current revenue: $0. Just launched. Funded from exit savings.

**What I'd love feedback on:**
1. Is the map visualization intuitive?
2. Is KScore personalization actually useful?
3. What data sources am I missing?
4. Would you pay for this? At what price?

Thanks for reading. Happy to answer any technical questions.

---

## Internal Notes: Reddit Strategy

### Timing
- r/InternetIsBeautiful: Tuesday or Wednesday, 10 AM ET
- r/dataisbeautiful: Wednesday or Thursday, 9 AM ET (with [OC] visualization)
- r/SideProject: Saturday or Sunday, 11 AM ET (less competition on weekends)
- Space posts 3-5 days apart

### What to NEVER do on Reddit
1. **Never mention you're doing "marketing"** -- this is sharing a project you built
2. **Never post the same content to multiple subreddits on the same day** -- cross-posting is visible and looks spammy
3. **Never ask for upvotes** -- instant ban
4. **Never use alt accounts** -- Reddit detects and bans these
5. **Never get defensive in comments** -- thank critics, acknowledge issues genuinely
6. **Never delete negative comments** -- it looks worse than leaving them
7. **Never use marketing buzzwords** -- "revolutionary", "game-changing", "disruptive" = instant downvotes

### How to Handle Negative Comments

| Comment Type | Response Strategy |
|-------------|-------------------|
| "This is just a news aggregator" | "Fair point. The main difference is the scoring/personalization layer. But I'd love to hear what you'd add to make it more useful." |
| "Why should I trust AI classification?" | "Great question. That's why the methodology is published openly. The AI handles classification, but the scoring formulas are deterministic and auditable." |
| "This looks like self-promotion" | "It is. I built this and I'm sharing it because I think it's useful. Happy to take feedback." (Honesty wins on Reddit) |
| "GPT-4o-mini isn't reliable" | "For classification tasks at this scale it's been surprisingly consistent. But I'm exploring local model alternatives. Any recommendations?" |
| "What about misinformation?" | "The tier system helps -- Tier-C signals (Telegram) are weighted lower until corroborated by Tier-A/B sources. But it's not perfect, and I'm transparent about that." |

### Additional Subreddits to Consider (Phase 2)

| Subreddit | Members | Approach | When |
|-----------|---------|----------|------|
| r/geopolitics | 700k+ | Data-driven analysis post (NOT product promotion) | After karma building |
| r/worldnews | 30M+ | Never self-promote here; wait for organic mentions | Passive only |
| r/opensource | 50k+ | If/when code goes open source | After open-sourcing |
| r/selfhosted | 300k+ | Docker Compose deployment guide | After docker-compose is polished |
| r/OSINT | 50k+ | Tool submission with early detection case study | After karma building |
| r/webdev | 2M+ | Tech stack deep dive (focus on FastAPI + Next.js architecture) | After Reddit presence established |

### Success Metrics
- r/InternetIsBeautiful: 500+ upvotes = front page, expect 10,000-30,000 visits
- r/dataisbeautiful: 1,000+ upvotes = front page, expect 20,000-50,000 visits
- r/SideProject: 50+ upvotes = top of subreddit, expect 1,000-3,000 visits
- Total estimated: 30,000-80,000 visits if at least one hits front page
- Conversion to registered users: ~5-10% of visitors

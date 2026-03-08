# WeWantPeace - Awesome Lists PR Strategy

> **Purpose**: Permanent backlinks + exposure to OSINT/developer community (18k+ stars repos)
> **Goal**: 1+ PR merged
> **Expected**: Once merged, 50-200 clicks/month permanently
>
> Updated: 2026-03-09
> Status: Ready to submit

---

## Summary: Eligibility Assessment

| # | List | Stars | Eligible | Submit When | Notes |
|---|------|-------|----------|-------------|-------|
| 1 | awesome-selfhosted/awesome-selfhosted | 180k+ | **Conditional** | After 2026-06-25 | CC-BY-NC-4.0 = non-free section, 4-month rule |
| 2 | jnv/lists | 10k+ | **N/A** | - | Meta-list of lists, not for individual projects |
| 3 | jivoi/awesome-osint | 18k+ | **Eligible** | Immediately | News Digest / Geospatial category |
| 4 | EticaAI/awesome-humanitarian-foss | 500+ | **Eligible** | Immediately | Humanitarian Platform category |
| 5 | DisasterTechCrew/awesome-disastertech | 300+ | **Eligible** | Immediately | General solutions category |
| 6 | AboutRSS/ALL-about-RSS | 5k+ | **Eligible** | Immediately | RSS-based collection platform |

---

## Priority 1: jivoi/awesome-osint (18k+ stars) -- SUBMIT FIRST

### Repository
https://github.com/jivoi/awesome-osint

### Why It's the Best Target
- 18k+ stars = highest exposure among eligible lists
- WeWantPeace is fundamentally an OSINT tool (open-source intelligence aggregation)
- Category "News Digest and Discovery Tools" is a perfect fit
- No minimum age requirement

### Category
**"News Digest and Discovery Tools"** (primary) or **"Geospatial Research and Mapping Tools"** (secondary)

### Line to Add (alphabetical order within category)

```markdown
- [WeWantPeace](https://www.wewantpeace.live) - Real-time global conflict monitoring platform aggregating 200+ open sources (RSS feeds, Telegram OSINT channels) across 195 countries with AI-powered severity scoring, multi-tier source clustering, interactive crisis map, and country-level tension index tracking. Open methodology published.
```

### PR Title
```
Add WeWantPeace to News Digest and Discovery Tools
```

### Commit Message
```
Add WeWantPeace - real-time global conflict monitoring platform
```

### PR Body

```markdown
## Add WeWantPeace to News Digest and Discovery Tools

### What is WeWantPeace?

WeWantPeace is a real-time global conflict monitoring and OSINT platform that:

- **Aggregates** 200+ open sources (RSS feeds + Telegram OSINT channels) covering 195 countries
- **Classifies** each event by topic, severity (0-100), and geographic location using AI
- **Clusters** related events from multiple sources into unified issues with source diversity metrics
- **Scores** personalized impact via KScore (0-10) based on geographic proximity, security alliances, and economic ties
- **Visualizes** conflicts on an interactive MapLibre GL map with severity color-coding
- **Tracks** per-country tension indices (0-100) with historical trends
- **Detects** spikes via anomaly-based early warning and sends push notifications

### Why it belongs in awesome-osint

WeWantPeace is an OSINT tool for monitoring global conflicts and geopolitical events in real-time. It processes publicly available information sources (RSS feeds, Telegram channels) and provides analytical capabilities (severity scoring, multi-source corroboration, trend detection, tension indices) valuable for researchers, journalists, analysts, and investigators.

During the March 2026 Iran-US escalation, the platform demonstrated measurable early detection: non-traditional sources (Tier-B regional media, Tier-C Telegram OSINT) detected events before major outlets in 46% of high-severity cases, with a median lead time of ~12.9 hours. Full case studies published in the open methodology repository.

### Links
- **Live platform**: https://www.wewantpeace.live
- **Open methodology**: https://github.com/nameofkk/wewantpeace-methodology
- **Tech stack**: FastAPI + Next.js + PostgreSQL + TimescaleDB + Celery + MapLibre GL

### Self-promotion disclosure
I am the developer of WeWantPeace. This is a self-promotional submission.
```

---

## Priority 2: DisasterTechCrew/awesome-disastertech (300+ stars)

### Repository
https://github.com/DisasterTechCrew/awesome-disastertech

### Category
**"Awesome projects > General solutions"**

### Line to Add

```markdown
- [WeWantPeace](https://www.wewantpeace.live) - Real-time global conflict monitoring platform aggregating 200+ sources across 195 countries. Features AI-powered severity scoring, interactive crisis map, country-level tension indices, spike detection, and personalized alerts. ([GitHub](https://github.com/nameofkk/wewantpeace)) ([Methodology](https://github.com/nameofkk/wewantpeace-methodology))
```

### PR Title
```
Add WeWantPeace - Real-time global conflict monitoring
```

### PR Body

```markdown
## Add WeWantPeace to General solutions

### What is it?

WeWantPeace is a real-time global conflict monitoring platform designed to help people track and understand ongoing crises worldwide. Similar to existing entries like CrisisTracker and Ushahidi, it provides situational awareness through automated data collection and analysis.

### Key features relevant to disaster/crisis tech

- **Real-time monitoring**: 5-minute refresh cycle across 200+ sources (RSS feeds + Telegram OSINT channels)
- **AI severity scoring**: Automated 0-100 severity classification for each event
- **Multi-source clustering**: Events from different sources about the same incident grouped automatically
- **Interactive map**: MapLibre GL-based conflict visualization with clustering and drill-down
- **Tension index**: Country-level crisis tracking (0-100) with time-series analysis
- **Spike detection**: Anomaly-based early warning system for escalating situations
- **Push notifications**: Personalized alerts for monitored regions
- **Coverage**: 195 countries monitored

### Early detection capability
During the March 2026 Iran-US escalation, the platform demonstrated 46% early detection rate through multi-tier source aggregation, with median lead times of ~12.9 hours ahead of major international outlets.

### Technical details
- **Stack**: Python (FastAPI) + React (Next.js) + PostgreSQL + TimescaleDB + Redis + Celery
- **License**: CC-BY-NC-4.0
- **Live**: https://www.wewantpeace.live
- **Open methodology**: https://github.com/nameofkk/wewantpeace-methodology
```

---

## Priority 3: EticaAI/awesome-humanitarian-foss (500+ stars)

### Repository
https://github.com/EticaAI/awesome-humanitarian-foss

### Category
**"Humanitarian Platform"** or propose new category **"Conflict Monitoring / Peacebuilding"**

### Table Row to Add

```markdown
| Conflict Monitoring | [WeWantPeace](https://www.wewantpeace.live) | [nameofkk/wewantpeace](https://github.com/nameofkk/wewantpeace) | Python, JavaScript, Docker | conflict, monitoring, OSINT, maps, peacebuilding | Real-time global conflict monitoring with AI severity scoring, interactive map, and tension index tracking across 195 countries. Open methodology. |
```

### PR Title
```
Add WeWantPeace - Real-time conflict monitoring platform
```

### PR Body

```markdown
## Add WeWantPeace - Real-time global conflict monitoring platform

### About

WeWantPeace is a humanitarian-focused platform that monitors global conflicts in real-time. It aggregates 200+ open sources across 195 countries, providing:

- AI-powered severity scoring for each conflict event
- Interactive crisis map with geographic visualization
- Country-level tension index tracking with historical trends
- Spike detection and trending analysis
- Personalized alerts for regions of interest
- Multi-tier source aggregation (international wires + regional media + Telegram OSINT)

### Humanitarian purpose

The platform's core mission is to increase awareness of global conflicts and their humanitarian impact. It helps:

- **Journalists** track developing crises in real-time
- **Researchers** analyze conflict patterns and trends
- **NGO workers** monitor situations in their operational areas
- **Citizens** stay informed about global security through personalized impact analysis

### Technical details
- **License**: CC-BY-NC-4.0
- **Stack**: FastAPI (Python) + Next.js (React) + PostgreSQL + TimescaleDB + Redis + Celery
- **Deployment**: Docker-based, deployed on Railway
- **Data sources**: RSS feeds + Telegram channels (all publicly available)
- **Open methodology**: https://github.com/nameofkk/wewantpeace-methodology

### Category suggestion
I suggest adding a new category "Conflict Monitoring / Peacebuilding" as this area is currently not represented in the list. Alternatively, it fits under "Humanitarian Platform".
```

---

## Priority 4: AboutRSS/ALL-about-RSS (5k+ stars)

### Repository
https://github.com/AboutRSS/ALL-about-RSS

### Category
**"Information Aggregators"** or **"RSS Feed Enhancement"**

### Line to Add

```markdown
- [WeWantPeace](https://www.wewantpeace.live) [![Open-Source Software](https://github.com/AboutRSS/ALL-about-RSS/raw/master/media/open-source.png)](https://github.com/nameofkk/wewantpeace) - Real-time global conflict monitoring platform that aggregates 200+ RSS feeds across 195 countries with AI-powered analysis, interactive crisis map, severity scoring, and tension index tracking.
```

### PR Title
```
Add WeWantPeace - RSS-based global conflict monitoring
```

### PR Body

```markdown
## Add WeWantPeace - RSS-based global conflict monitoring platform

WeWantPeace heavily relies on RSS as its primary data collection mechanism:

- **200+ RSS feeds** from major news agencies (Reuters, AP, BBC, Al Jazeera, regional outlets)
- Automated RSS collection with 3-5 minute polling cycles via Celery Beat
- AI-powered analysis pipeline: RSS collection -> normalization -> deduplication -> clustering -> scoring
- Additional sources: Telegram OSINT channels + APIs

The platform transforms raw RSS feeds into actionable conflict intelligence with severity scoring, geographic mapping, personalized impact analysis, and trend detection.

### Links
- **Live**: https://www.wewantpeace.live
- **Open methodology**: https://github.com/nameofkk/wewantpeace-methodology
- **License**: CC-BY-NC-4.0
```

---

## Deferred: awesome-selfhosted (180k+ stars) -- After 2026-06-25

### Eligibility Issues
1. **4-month rule**: First release must be 4+ months old. First commit: 2026-02-25. Earliest submission: **2026-06-25**.
2. **License**: CC-BY-NC-4.0 is classified as "non-free." Entry goes in `non-free.md`, not the main list.
3. **Source code**: Repository must be public with `source_code_url` field.

### Resolution Options
- Change license to AGPL-3.0 for main list eligibility (180k stars exposure)
- Keep CC-BY-NC-4.0 and accept non-free section placement

### YAML Entry (for awesome-selfhosted-data repo)

```yaml
# software/wewantpeace.yml
name: WeWantPeace
website_url: https://www.wewantpeace.live
source_code_url: https://github.com/nameofkk/wewantpeace
description: >-
  Real-time global conflict monitoring platform with AI-powered severity scoring,
  interactive crisis map, country-level tension index tracking, and personalized
  impact analysis. Aggregates 200+ RSS/Telegram sources across 195 countries
  with 5-minute refresh cycle.
licenses:
  - CC-BY-NC-4.0
platforms:
  - Python
  - Nodejs
  - Docker
tags:
  - Maps and Global Positioning System (GPS)
demo_url: https://www.wewantpeace.live
depends_3rdparty: true
```

---

## Pre-submission Checklist

- [ ] GitHub repo set to public (or methodology repo linked)
- [ ] English README.md in repo (or separate README.en.md)
- [ ] Docker Compose install guide verified
- [ ] `.env.example` file with documented environment variables
- [ ] Demo screenshots or GIF in repo README
- [ ] GitHub Release / version tag created
- [ ] LICENSE file with correct SPDX identifier (CC-BY-NC-4.0)
- [ ] Open methodology repo accessible at github.com/nameofkk/wewantpeace-methodology

---

## Submission Order

1. **awesome-osint** (18k stars) -- submit first, highest impact
2. **awesome-disastertech** (300 stars) -- submit same day, quick win
3. **awesome-humanitarian-foss** (500 stars) -- submit next day
4. **ALL-about-RSS** (5k stars) -- submit when RSS angle is strongest
5. **awesome-selfhosted** (180k stars) -- submit after 2026-06-25

---

## Key Recommendations

### License Strategy
CC-BY-NC-4.0 is classified as "non-free" by awesome-selfhosted. Changing to AGPL-3.0 would:
- Enable main list placement on awesome-selfhosted (180k stars)
- AGPL-3.0 still effectively restricts commercial use (source disclosure obligation)
- Recognized as FOSS by all awesome lists

### English README
International awesome lists require English documentation. Options:
- Make README.md English, add README.ko.md for Korean
- Or maintain bilingual README.md with English first

### Repository Visibility
GitHub repo must be public for `source_code_url` links. awesome-selfhosted requires this field.

# Bellingcat & OSINT Community Outreach Emails

> **Purpose**: Introduce WeWantPeace to the OSINT community and acquire expert users
> **Goal**: At least 1 email reply; mention in Bellingcat newsletter/tweet
> **Expected**: Reply rate 5-15%. If shared in OSINT community, 100-500 targeted user acquisitions.

---

## Email 1: Bellingcat (Primary)

### To
`tech@bellingcat.com` (primary) or `info@bellingcat.com` (fallback)

### Subject
```
Tool submission: WeWantPeace — real-time multi-source conflict monitor (24.5h early detection demonstrated)
```

### Body

Hi Bellingcat team,

I'd like to submit WeWantPeace for consideration in your Digital Investigation Toolkit.

I built this because I needed a better way to track global conflicts in real-time. After exiting a startup I'd co-founded, I moved to Jeju Island and spent time figuring out what I wanted to work on next. The answer came every time a civil defense notification popped up on my phone -- I had a real, visceral fear of conflict, but no good tool to actually understand what was happening in the world at any given moment.

WeWantPeace is a free, real-time conflict monitoring dashboard that aggregates ~200 sources -- including RSS feeds from international and regional outlets, plus defense/security Telegram OSINT channels -- every 3-5 minutes across 195 countries.

**Live platform:** https://www.wewantpeace.live
**Open methodology:** https://github.com/nameofkk/wewantpeace-methodology

### Why this matters for OSINT investigators

The platform's core design principle is **multi-tier source aggregation**: international wire services (Tier-A), regional/local media (Tier-B), and Telegram OSINT channels (Tier-C) are ingested, scored, and clustered together. This matters because non-traditional and regional sources frequently surface signals ahead of major outlets.

### Demonstrated early detection (March 1-9, 2026)

During the recent Iran-US escalation, retrospective analysis showed measurable lead times:

| Event | First signal source | Lead time vs. Tier-A |
|-------|-------------------|---------------------|
| Mojtaba Khamenei succession | Telegram OSINT channel (Tier-C) | **24.5 hours** |
| Lebanon airstrike casualties (102 killed) | Regional media (Tier-B) | **18.0 hours** |
| UAE intercepts 131 drones + 6 missiles | Gulf regional outlets (Tier-B) | **12.9 hours** |
| Tehran military academy strike | Arabic-language media (Tier-B) | **4.3 hours** |

Across 50 high-severity clusters analyzed: **46% were detected first through Tier-B/C sources**, with a median lead time of ~12.9 hours before Tier-A confirmation.

The largest single cluster tracked 119 events from 21 independent sources across 7 days (Tehran oil depot strikes), demonstrating continuous situational awareness across a multi-theater escalation.

### Features relevant to OSINT workflows

- **Multi-source event clustering**: Events from different sources about the same incident are automatically grouped, showing source diversity and corroboration strength at a glance.
- **Source tier visibility**: Each event is tagged with its source tier (A/B/C), so investigators can assess information provenance immediately.
- **Telegram channel monitoring**: Defense and security-focused Telegram channels are included as Tier-C sources -- the Khamenei succession case was first detected via this layer.
- **Interactive crisis map**: Geolocated events plotted in real-time with severity color-coding and cluster drill-down.
- **Tension Index**: Per-country risk score (0-100) updated every 5 minutes, with historical trends for pattern analysis.
- **KScore-based alerts**: Anomaly-based notifications for rapid escalation events.
- **KScore personalization**: Key Impact Score (0-10) adjusts event importance based on geographic proximity, security alliances, and economic ties to the user's home country.
- **Bilingual UI**: Full Korean/English toggle.

### Open methodology

All scoring formulas (KScore, Tension Index), source tier definitions, classification taxonomy, and detailed case studies are published in the methodology repository. Transparency in conflict monitoring is core to this project, and I welcome scrutiny from the investigative community.

### Technical details

- **Collection**: Celery beat scheduler polling ~200 sources every 3-5 minutes
- **NLP pipeline**: GPT-4o-mini for classification, severity scoring, entity extraction, deduplication
- **Clustering**: Title similarity (40%+ threshold) + country/topic matching
- **Stack**: FastAPI, PostgreSQL + TimescaleDB, Next.js, Railway

The platform is free to use (trending issues, tension overview, KScore alerts). No account required to browse.

I'd welcome the opportunity to provide a walkthrough, answer technical questions, or discuss how the system could complement existing OSINT investigation workflows.

Best regards,
Shinhyuk Kim
Solo developer, WeWantPeace
https://www.wewantpeace.live

---

## Email 2: GIJN (Global Investigative Journalism Network)

### To
`hello@gijn.org`

### Subject
```
Tool for investigative journalists: WeWantPeace — real-time conflict monitoring with multi-source early detection
```

### Body

Hi GIJN team,

I'm reaching out because WeWantPeace may be a useful resource for your member journalists covering conflict zones.

WeWantPeace is a free, real-time global conflict monitoring platform I built as a solo developer. It aggregates ~200 sources (RSS feeds + Telegram OSINT channels) every 3-5 minutes across 195 countries, automatically clustering related events and scoring their severity.

**Live platform:** https://www.wewantpeace.live
**Open methodology:** https://github.com/nameofkk/wewantpeace-methodology

### Relevance for investigative journalists

During the March 2026 Iran-US escalation, the platform demonstrated measurable early detection:

- **24.5 hours** before major outlets: Mojtaba Khamenei succession (via Telegram OSINT)
- **18 hours** before Tier-A confirmation: Lebanon airstrike casualties (102 killed)
- **12.9 hours** ahead: UAE intercepts 131 drones + 6 missiles

Across 50 high-severity event clusters, non-traditional sources (regional media + Telegram) beat Reuters/AP/BBC in 46% of cases.

### How journalists can use it

1. **Early signal detection**: Monitor a region and get KScore-based alerts when event counts surge abnormally
2. **Source corroboration**: See how many independent sources are reporting the same event, with tier labels (A/B/C) for provenance assessment
3. **Trend analysis**: Country-level Tension Index (0-100) with historical charts for identifying escalation patterns
4. **Geographic context**: Interactive map with severity-coded clusters and drill-down

The platform is entirely free for core features. The methodology is openly published for transparency.

I'd be happy to provide a demo or contribute a piece about early detection methodology for your resource library.

Best regards,
Shinhyuk Kim
https://www.wewantpeace.live

---

## Email 3: OCCRP (Organized Crime and Corruption Reporting Project)

### To
`info@occrp.org`

### Subject
```
Tool submission: WeWantPeace — open-methodology conflict monitoring with real-time multi-source aggregation
```

### Body

Hi OCCRP team,

I'd like to share WeWantPeace as a potential tool for your investigative network.

WeWantPeace is a free, real-time global conflict monitoring platform that aggregates ~200 open sources (international wire services, regional media, and Telegram OSINT channels) every 3-5 minutes across 195 countries. It automatically clusters related events, scores severity, and provides early warning through KScore-based alert detection.

**Live platform:** https://www.wewantpeace.live
**Open methodology:** https://github.com/nameofkk/wewantpeace-methodology

### Key capability: multi-tier early detection

In a retrospective analysis of the March 2026 Iran-US escalation (50 high-severity clusters), Tier-B/C sources (regional media, Telegram) detected events first in 46% of cases, with a median lead time of 12.9 hours before Tier-A (Reuters, AP, BBC) confirmation.

Notable examples:
- Mojtaba Khamenei succession: 24.5h early via Telegram OSINT
- UAE missile/drone interception: 12.9h early via Gulf media
- Tehran military academy strike: 4.3h early via Arabic-language sources

### OCCRP-relevant features

- **Sanctions monitoring**: Events tagged with "sanctions" topic category, filtered by country
- **Cross-border tracking**: Events spanning multiple countries are linked via cluster system
- **Source transparency**: Every event tagged with source name, tier, and collection timestamp
- **Country risk trends**: Tension Index time-series for identifying patterns
- **Open methodology**: All scoring formulas and source definitions published

Free to use. No account required for browsing. Open methodology for full transparency.

Best regards,
Shinhyuk Kim
https://www.wewantpeace.live

---

## Internal Notes: Follow-up Strategy

### Timeline
- Send Bellingcat email first (highest priority target)
- Wait 3 days, then send GIJN and OCCRP emails
- If no reply from Bellingcat after 7 days, follow up once
- Never follow up more than once

### Additional outreach targets (phase 2)
- **InvestigateEurope** (investigate-europe.eu) -- European investigative network
- **ICIJ** (icij.org) -- International Consortium of Investigative Journalists
- **Lighthouse Reports** (lighthousereports.com) -- Data-driven investigations
- **Individual OSINT researchers on X** -- @oaborisade, @christogrozev (Bellingcat), @IntelDoge

### What to avoid
- Do not mass-email -- personalize each outreach
- Do not follow up more than once per recipient
- Do not claim to be a competitor to existing OSINT tools -- frame as complementary
- Do not oversell early detection -- always caveat with "regional media reports faster, we just aggregate"

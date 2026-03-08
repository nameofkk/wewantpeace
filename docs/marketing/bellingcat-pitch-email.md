# Bellingcat Toolkit Pitch Email

## Subject: Tool submission -- WeWantPeace (real-time multi-source conflict monitor with open methodology)

## Body

Hi Bellingcat team,

I'd like to submit WeWantPeace for your Digital Investigation Toolkit. It's a free, real-time conflict monitoring dashboard that aggregates ~200 sources -- including RSS feeds from international and regional outlets, plus defense/security Telegram OSINT channels -- every 3-5 minutes across 195 countries.

**Live platform:** https://www.wewantpeace.live
**Open methodology:** https://github.com/nameofkk/wewantpeace-methodology

### Why it might be useful for OSINT investigators

The platform's core design principle is **multi-tier source aggregation**: international wire services (Tier-A), regional/local media (Tier-B), and Telegram OSINT channels (Tier-C) are all ingested, scored, and clustered together. This matters because in our experience, non-traditional and regional sources frequently surface signals ahead of major outlets.

### Early detection data (March 1-9, 2026)

We ran a retrospective analysis during the recent Iran-US escalation and found measurable lead times:

| Event | First signal source | Lead time vs. Tier-A |
|-------|-------------------|---------------------|
| Mojtaba Khamenei succession | Telegram OSINT channel (Tier-C) | **24.5 hours** |
| Lebanon airstrike casualties (102 killed) | Regional media (Tier-B) | **18.0 hours** |
| UAE intercepts 131 drones + 6 missiles | Gulf regional outlets (Tier-B) | **12.9 hours** |
| Tehran military academy strike | Arabic-language media (Tier-B) | **4.3 hours** |

Across 50 high-severity clusters analyzed: **46% were detected first through Tier-B/C sources**, with a median lead time of ~12.9 hours before Tier-A confirmation.

The largest single cluster in the dataset tracked 119 events from 21 independent sources across 7 days (Tehran oil depot strikes), demonstrating continuous situational awareness across a multi-theater escalation.

### Features relevant to the OSINT community

- **Multi-source event clustering:** Events from different sources about the same incident are automatically grouped, showing source diversity and corroboration strength at a glance.
- **Source tier visibility:** Each event is tagged with its source tier (A/B/C), so investigators can assess information provenance.
- **Telegram channel monitoring:** Defense and security-focused Telegram channels are included as Tier-C sources -- the Khamenei succession case was first detected via this channel layer.
- **Interactive crisis map:** Geolocated events plotted in real-time with severity color-coding and cluster drill-down.
- **Tension Index:** Per-country risk score (0-100) updated every 5 minutes, with historical trends for pattern analysis.
- **Spike detection alerts:** Anomaly-based notifications for rapid escalation events.
- **Bilingual (Korean/English):** Full UI language toggle.

### Open methodology

Scoring formulas (KScore, Tension Index), source tier definitions, classification taxonomy, and detailed case studies are published in our methodology repository. We believe transparency in conflict monitoring methodology is important, and we welcome scrutiny and feedback from the investigative community.

### Technical details

- Collection: Celery beat scheduler polling ~200 sources every 3-5 minutes
- NLP: GPT-4o-mini for classification, severity scoring, entity extraction, deduplication
- Clustering: Title similarity (40%+ threshold) + country/topic matching
- Stack: FastAPI, PostgreSQL + TimescaleDB, Next.js, Railway

The platform is free to use (trending issues, tension overview, spike alerts). No account required to browse.

Happy to provide a walkthrough, answer technical questions, or discuss how the system could complement existing OSINT workflows.

Best regards,
[Name]

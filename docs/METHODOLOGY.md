# WeWantPeace Methodology

> **Version 3.0** | March 2026
>
> This document describes the data collection, processing, scoring, and alerting
> methodology used by the WeWantPeace global conflict and crisis monitoring
> platform. All formulas, constants, and thresholds correspond to the production
> codebase as of March 2026. The document is intended for researchers,
> journalists, and policy analysts who wish to understand how the platform's
> metrics are derived.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Data Sources](#2-data-sources)
3. [Data Processing Pipeline](#3-data-processing-pipeline)
   - 3.1 Collection
   - 3.2 Normalization
   - 3.3 Clustering
   - 3.4 Deduplication
4. [KScore (Key Impact Score)](#4-kscore-key-impact-score)
   - 4.1 Formula
   - 4.2 Personalization
5. [Tension Index](#5-tension-index)
6. [Spike Detection](#6-spike-detection)
7. [Limitations and Known Biases](#7-limitations-and-known-biases)
8. [Changelog](#8-changelog)

---

## 1. Overview

**WeWantPeace** is a real-time global conflict and crisis monitoring service
that continuously ingests news reports and structured data feeds from multiple
independent sources, classifies and clusters them, and produces two
complementary metrics:

| Metric | Scope | Scale | Update Frequency |
|--------|-------|-------|------------------|
| **KScore** (Key Impact Score) | Per issue cluster | 0--10 | Every 5 minutes |
| **Tension Index** | Per country | 0--100 | Every 5 minutes |

The overarching goal is to provide a transparent, quantitative, and
near-real-time picture of geopolitical instability worldwide, accessible to both
casual users and professional analysts.

### Data Pipeline Overview

```
Sources (RSS / Telegram / GDELT / ACLED / USGS / ReliefWeb / Travel Advisory)
    |
    v
Collection  --  Raw events ingested, deduplicated by external ID
    |
    v
Normalization  --  AI classification (GPT-4o-mini) + keyword fallback
    |                Topic (11 categories) + Severity (0-100) + Country extraction
    v
Clustering  --  Filtered Jaccard similarity + AI boundary judgment
    |                24-hour sliding window, country:topic buckets
    v
Scoring  --  KScore (per cluster) + Tension Index (per country)
    |
    v
Alerting  --  Spike detection -> push notifications + SNS auto-posting
```

---

## 2. Data Sources

The platform monitors **58 active source channels** across 7 distinct data
source types. Each source is registered with metadata including its reliability
tier, language, geographic focus, and topic focus.

### 2.1 Source Inventory

| Source Type | Count | Interval | Data Format | Authentication | Description |
|-------------|-------|----------|-------------|----------------|-------------|
| **RSS / Atom feeds** | 37+ | 5 min | XML (feedparser) | None | International wire services (Reuters, AP, AFP), regional news outlets, specialized conflict monitors |
| **Telegram OSINT** | 18 channels | 5 min | MTProto (Telethon) | API ID + Hash + Session | Public channels providing first-hand reports from conflict zones |
| **GDELT** | 1 API | 15 min | JSON (DOC API 2.0) | None | Global event database with structured tone, theme, and geo data |
| **ACLED** | 1 API | Daily (06:30 UTC) | JSON (REST) | OAuth (email + password) | Armed Conflict Location & Event Data Project; fully structured event_type, fatalities, and geo fields |
| **USGS Earthquake** | 1 API | 5 min | GeoJSON | None | United States Geological Survey; M5.0+ earthquakes from the 4.5_day summary feed |
| **ReliefWeb** | 1 API | 30 min | JSON (v1 API) | None | UN OCHA humanitarian reports covering disasters, health crises, and conflicts |
| **US Travel Advisory** | 1 API | 6 hours | JSON | None | US State Department travel advisories, Level 2 (Exercise Increased Caution) and above |

### 2.2 Source Tier System

Every source channel is assigned a reliability tier (A through D) that
determines the base confidence score assigned to events it produces. The tier
also contributes a bonus to the KScore quality component.

| Tier | Base Confidence | KScore Tier Bonus | Examples |
|------|----------------|-------------------|----------|
| **A** | 0.85 | +0.05 per source | Reuters, AP, BBC, Al Jazeera |
| **B** | 0.70 | +0.03 per source | Regional wire services, France24 |
| **C** | 0.55 | +0.01 per source | Local outlets, niche monitors |
| **D** | 0.35 | +0.00 | Unverified, social media aggregators |

Confidence is capped at 0.95 regardless of tier accumulation.

### 2.3 Structured vs. Unstructured Sources

Sources fall into two processing categories:

- **Structured sources** (GDELT, ACLED, USGS, Travel Advisory): provide
  machine-readable event types, coordinates, and severity indicators. These are
  mapped directly to the internal taxonomy without requiring AI classification,
  significantly reducing per-event processing cost.

- **Unstructured sources** (RSS, Telegram, ReliefWeb): provide free-text
  articles requiring AI-based classification and entity extraction.

---

## 3. Data Processing Pipeline

### 3.1 Collection

Each collector runs on a Celery Beat schedule. The RSS collector uses
`feedparser` with `asyncio.to_thread()` to avoid blocking, limited to 5
concurrent HTTP requests via `asyncio.Semaphore`. Telegram collection uses
Telethon's MTProto client with StringSession authentication.

**Spam and noise filtering** is applied at collection time. Articles are
rejected if they fall below minimum length thresholds (8 words / 60 characters)
or match spam patterns (subscription prompts, 404 pages, site closures,
newsletter sign-ups).

Telegram channels that fail to resolve for 20 consecutive attempts (approximately
5 hours at 5-minute intervals) are automatically deactivated.

### 3.2 Normalization

Each raw event is normalized into a structured record containing: topic,
severity, confidence, country code, geographic coordinates, geohash, language,
and a deduplication key.

#### 3.2.1 Topic Classification

Classification follows a two-layer approach:

1. **Primary: GPT-4o-mini** -- receives the article title (first 200
   characters) and body (first 500 characters) and returns a JSON object
   `{"topic": "...", "severity": N}`. Temperature is set to 0 for
   deterministic output.

2. **Fallback: keyword rule engine** -- activated when AI classification
   fails or the API key is unavailable. The engine matches against a curated
   dictionary of ~500 English keywords organized by topic, with additional
   dictionaries for Korean, Arabic, Russian, Chinese, Japanese, French, Spanish,
   and German.

The system classifies events into **10 topics** plus an `unknown` category:

| Topic | Description | Keyword Examples |
|-------|-------------|------------------|
| `conflict` | Armed conflict, military operations, airstrikes, war, casualties | attack, missile, bomb, airstrike, troops, casualties, ceasefire |
| `terror` | Terrorism, hostage situations, mass shootings, assassinations, cartel violence | terrorist, hostage, extremist, suicide bomb, mass shooting, kidnapping |
| `coup` | Coups, military takeovers, martial law, insurrection | coup, overthrow, junta, martial law, insurrection, sedition |
| `sanctions` | Economic sanctions, embargoes, tariffs, financial crises | sanctions, embargo, tariff, market crash, trade war, currency crisis |
| `cyber` | Cyberattacks, hacking, ransomware, internet shutdowns | cyberattack, ransomware, data breach, election interference |
| `protest` | Protests, demonstrations, riots, civil unrest | protest, demonstration, riot, strike, uprising, crackdown |
| `diplomacy` | Diplomatic events, treaties, summits, elections, political developments | summit, treaty, negotiation, election, impeachment |
| `maritime` | Naval operations, shipping disruptions, piracy, migrant crossings | naval, strait, blockade, piracy, shipwreck, migrant |
| `disaster` | Natural disasters, industrial accidents, humanitarian crises | earthquake, flood, hurricane, wildfire, famine, building collapse |
| `health` | Disease outbreaks, epidemics, pandemics, public health emergencies | outbreak, pandemic, epidemic, cholera, ebola, mpox |

**Keyword matching details:**

- **Strong keywords** are domain-specific terms (e.g., "ceasefire" for
  conflict, "suicide bomb" for terror). A single strong keyword match is
  sufficient for classification.
- **Weak keywords** are more ambiguous terms (e.g., "attack", "emergency").
  For topics like `conflict`, `terror`, `diplomacy`, and `protest`, at least 2
  weak keyword matches are required. Narrow-domain topics (`coup`, `cyber`,
  `maritime`, `sanctions`, `disaster`, `health`) require only 1.
- **Non-military context filter**: patterns matching sports, entertainment,
  festivals, memorials, and personal deaths suppress `conflict` and `terror`
  weak keywords to prevent false positives (e.g., "battle with cancer", "orange
  battle festival").
- **Word boundary matching**: keywords are matched with boundary checks to
  prevent substring false positives (e.g., "coup" does not match "coupang").

#### 3.2.2 Severity Scoring (0--100)

Severity indicates the estimated real-world impact of an event. It uses the
full 0--100 range.

**AI path:** GPT-4o-mini assigns severity directly, guided by calibration
examples in the system prompt:

| Severity Range | Description | Calibration Examples |
|----------------|-------------|----------------------|
| 0--19 | Minimal | Routine exercises, policy discussions, population statistics |
| 20--39 | Low | Minor incidents, diplomatic statements, small protests, 1--2 casualties |
| 40--59 | Moderate | Significant protests, trade disputes, localized skirmishes, 3--20 casualties |
| 60--79 | High | Major military operations, severe crises, 20--100 casualties |
| 80--89 | Very High | Large-scale attacks, 100+ casualties, war escalation |
| 90--100 | Critical | Mass casualties 200+, active inter-state war, nuclear threats, confirmed WMD use |

**Keyword fallback path:**

```
severity = base_severity + keyword_modifier + casualty_bonus
```

- **Base severity** is topic-dependent: `coup` 65, `conflict` 60, `terror` 60,
  `maritime` 50, `disaster` 50, `sanctions` 45, `cyber` 40, `health` 40,
  `protest` 35, `diplomacy` 30, `unknown` 20.
- **Keyword modifier**: a curated list of ~120 upward modifiers (e.g.,
  "killed" +10, "genocide" +20, "nuclear" +20, "invasion" +18) and ~40
  downward modifiers (e.g., "ceasefire" -10, "hoax" -15, "military exercise"
  -10). The net modifier is uncapped.
- **Casualty bonus** (up to +30): regex patterns extract casualty counts from
  text. The bonus follows a logarithmic scale:
  `bonus = weight * (3 + log10(max(1, N)) * 6)`, where N is the casualty
  count. This yields approximately +3 for 1 casualty, +7 for 10, +13 for 100,
  +20 for 1,000.

**Structured source severity**: ACLED, USGS, and Travel Advisory data use
direct mappings without AI or keyword processing:

- **ACLED**: `Battles` -> 65, `Violence against civilians` -> 70,
  `Explosions/Remote violence` -> 70, `Protests` -> 35, `Riots` -> 45.
  Fatality counts provide additional adjustment.
- **USGS**: Piecewise linear interpolation: M5.0 -> 40, M6.0 -> 55,
  M7.0 -> 75, M8.0 -> 95, capped at 100.
- **Travel Advisory**: Level 2 -> 30, Level 3 -> 55, Level 4 -> 80.

#### 3.2.3 Information Accessibility Adjustment

Countries with restricted press freedom tend to systematically under-report
events. To compensate, severity scores are adjusted upward using a modifier
derived from the Reporters Without Borders (RSF) Press Freedom Index:

```
modifier = 1.0 + (rsf_score / 100) * 0.3
adjusted_severity = min(100, severity * modifier)
```

| Press Freedom Level | RSF Score (approx) | Modifier | Example Countries |
|---------------------|--------------------|----------|-------------------|
| Highly restricted | 80--90 | 1.24--1.27 | North Korea (1.27), Turkmenistan (1.26), Eritrea (1.25) |
| Restricted | 60--80 | 1.18--1.24 | China (1.22), Iran (1.22), Russia (1.20) |
| Partially restricted | 40--60 | 1.12--1.18 | Saudi Arabia (1.17), Egypt (1.16) |
| Mostly free | 20--40 | 1.06--1.12 | India (1.10), Mexico (1.09) |
| Free press | 0--20 | 1.00 | No adjustment applied |

This adjustment is derived from the `INFORMATION_ACCESSIBILITY` table in
`calibration.py`, covering 26 countries with RSF scores above 28.

#### 3.2.4 Country and Region Extraction

Geographic attribution uses a dictionary of **750+ keywords** mapping country
names, demonyms, capital cities, major cities, regional names, and prominent
political figures to ISO 3166-1 alpha-2 country codes and representative
coordinates.

- Multi-word phrases are matched with longest-match priority (e.g., "South
  China Sea" matches before "China").
- Korean, Arabic, and other non-Latin place names are included to handle
  multilingual sources.
- The `COUNTRY_MAP` provides (country_code, latitude, longitude) tuples used
  to generate geohash5 values for spatial indexing.
- Prominent political figures are mapped to their countries (e.g., mentions of
  "Trump" or "Rubio" map to "US") to handle policy articles that do not
  explicitly name a country.

### 3.3 Clustering

Normalized events are grouped into **IssueCluster** entities using a 24-hour
sliding window. The clustering algorithm prevents both over-merging (combining
unrelated events in the same country/topic) and over-splitting (creating
duplicate clusters for the same event reported by different outlets).

#### 3.3.1 Cluster Key

Each event receives a cluster key that determines its candidate bucket:

1. `{country_code}:{topic}` -- preferred, when a country code is extracted
2. `{geohash4}:{topic}` -- fallback, when only coordinates are available
3. `0000:{topic}` -- last resort, capped at 2 events per cluster

#### 3.3.2 Filtered Jaccard Similarity

Within each bucket, the event's title is compared to existing cluster titles
using **Filtered Jaccard** -- a variant of Jaccard similarity that removes
country names, topic-generic keywords, demonyms, and stop words before
computing the intersection-over-union of remaining content words.

**Preprocessing steps:**
1. Tokenize into words, convert to lowercase
2. Remove English stop words (40 common words)
3. Apply basic stemming (suffix removal: -ing, -ed, -es, -s, -ies)
4. Normalize demonyms to base country names (e.g., "Russian" -> "russia")
5. Remove country name stems (39 countries)
6. Remove topic-generic stems (54 stems covering all 10 topics + generic news
   words like "government", "official", "report")

**Why Filtered Jaccard outperforms standard Jaccard:**

Standard Jaccard on news headlines produces false positives when two different
events in the same country share country names and topic words. For example:

| Pair | Standard Jaccard | Filtered Jaccard | Correct Decision |
|------|-----------------|-----------------|------------------|
| "Iran nuclear talks resume" vs. "Iran missile strikes on Iraq" | 0.11 (shared: "iran") | 0.00 | Separate |
| "Syria Aleppo fighting intensifies" vs. "Fighting erupts in Aleppo" | 0.14 | 0.50 (shared: "aleppo") | Merge |

**Matching thresholds:**

| Condition | Threshold | Rationale |
|-----------|-----------|-----------|
| General events | >= 0.15 | Standard threshold after noise removal |
| High-severity (both sides >= 50) | >= 0.08 | Relaxed for critical events to reduce false splits |
| AI judgment zone | 0.10 -- 0.20 | Ambiguous zone requiring AI confirmation |
| Always separate | < 0.10 | Insufficient content overlap |

Korean titles use standard (unfiltered) Jaccard over 2+ character Korean words,
and the final similarity is `max(english_filtered, korean_standard)`.

#### 3.3.3 AI Boundary Judgment

When Filtered Jaccard falls in the boundary zone (0.10 to threshold),
GPT-4o-mini is queried: *"Are these two headlines about the SAME specific
event/incident?"*

- Maximum 2 AI calls per incoming event (cost control)
- LRU cache of 256 entries prevents duplicate API calls
- On API failure: default to separation (conservative)

#### 3.3.4 Cluster State Updates

When an event joins an existing cluster:
- `event_count` increments by 1
- `confidence` is updated as a running average
- `severity` takes the maximum across all member events
- `source_tiers` list is appended with the new source's tier
- `window_end` extends by 24 hours from the latest event
- Junk titles (hashtag-only, greeting patterns, date-only) are automatically
  replaced with the most descriptive event title
- AI-generated bilingual cluster titles (English + Korean) are preferred when
  available

### 3.4 Deduplication

Deduplication operates at three levels:

1. **Collection-level**: `external_id` (RSS GUID, Telegram message ID, API
   record ID) prevents re-ingesting the same raw item.
2. **Normalization-level**: `dedup_key` (MD5 hash of normalized title text)
   catches near-identical articles from syndicated feeds.
3. **Cluster-level**: Filtered Jaccard similarity ensures that events reporting
   the same incident from different outlets merge into a single cluster rather
   than creating parallel clusters.

---

## 4. KScore (Key Impact Score)

KScore measures the significance of an issue cluster on a 0--10 scale,
combining four weighted signals: event velocity, source quality, severity, and
multi-source spread.

### 4.1 Formula

```
raw = 0.30 * velocity_norm + 0.10 * quality + 0.30 * severity_norm + 0.30 * spread
KScore = raw * 10 * decay
```

#### Component Definitions

**Velocity (weight: 0.30)** -- event accumulation speed:

```
velocity_raw = min(6.0, event_count^0.7 * spike_factor)
velocity_norm = velocity_raw / 6.0
```

- `event_count` is the number of events in the cluster
- `spike_factor` = 1.5 if the cluster is flagged as a spike, 1.0 otherwise
- The exponent 0.7 provides diminishing returns: small clusters (1--10 events)
  show strong differentiation, while large clusters converge toward the cap

**Quality (weight: 0.10)** -- source reliability:

```
tier_bonus = sum(0.05 if tier == "A" else 0.03 if tier == "B" else 0.01 for each source)
quality = min(1.0, confidence + tier_bonus)
```

**Severity (weight: 0.30)** -- normalized event severity:

```
severity_norm = cluster_max_severity / 100
```

**Spread (weight: 0.30)** -- independent source diversity:

```
spread = min(1.0, independent_sources / 12)
```

Independent sources are counted as distinct `source_channel` records, not
individual articles. A cluster reported by Reuters, BBC, and Al Jazeera counts
as 3 independent sources even if each outlet publishes multiple articles.
The saturation point of 12 represents the top ~20% of multi-source coverage
in the current 58-channel ecosystem.

**Decay** -- exponential time decay:

```
decay = max(0.30, exp(-0.025 * age_hours))
```

| Age | Decay Factor | Remaining Score |
|-----|-------------|-----------------|
| 0 hours | 1.00 | 100% |
| 6 hours | 0.86 | 86% |
| 12 hours | 0.74 | 74% |
| 24 hours | 0.55 | 55% |
| 36 hours | 0.41 | 41% |
| 48+ hours | 0.30 | 30% (floor) |

The half-life is approximately **28 hours** (ln(2) / 0.025 = 27.7h). The decay
floor of 0.30 ensures that significant ongoing events retain meaningful scores
even after 48 hours.

#### KScore Thresholds

| Level | KScore Range | Interpretation |
|-------|-------------|----------------|
| Stable | < 2.0 | Low-impact or declining events |
| Caution | 2.0 -- 4.0 | Noteworthy events with limited scope |
| Alert | 4.0 -- 6.0 | Significant events with multi-source confirmation |
| Severe | 6.0 -- 8.0 | Major events with high severity and broad coverage |
| Extreme | >= 8.0 | Critical events: mass casualties, active wars, nuclear threats |

Events with KScore below **1.5** (`KSCORE_MIN`) are excluded from the trending
list, unless the cluster is flagged as a spike.

The top **30** clusters by KScore are stored in the `trending_keywords` table
each cycle.

### 4.2 Personalization

KScore is personalized based on the user's **home country**. The frontend
computes:

```
personalizedKScore = rawKScore * impactFactor(homeCountry, eventCountry, topic)
```

The impact factor is a weighted combination of three bilateral dimensions:

| Dimension | Symbol | Description |
|-----------|--------|-------------|
| Geographic proximity | `geo` | Physical distance and regional adjacency (0--1) |
| Security relevance | `sec` | Military alliances, threat perception, historical conflict (0--1) |
| Economic linkage | `eco` | Trade volume, supply chain dependency, energy imports (0--1) |

Each topic type determines how much weight each dimension receives:

| Topic | geo weight | sec weight | eco weight |
|-------|-----------|-----------|-----------|
| conflict | 0.35 | 0.45 | 0.20 |
| terror | 0.40 | 0.40 | 0.20 |
| coup | 0.30 | 0.50 | 0.20 |
| sanctions | 0.20 | 0.25 | **0.55** |
| cyber | 0.20 | 0.30 | **0.50** |
| protest | 0.40 | 0.30 | 0.30 |
| diplomacy | 0.30 | 0.40 | 0.30 |
| maritime | 0.40 | 0.30 | 0.30 |
| disaster | **0.60** | 0.10 | 0.30 |
| health | **0.50** | 0.10 | 0.40 |

The factor computation is:

```
weights = TOPIC_IMPACT_WEIGHTS[topic]
factors = IMPACT_FACTORS[homeCountry][eventCountry]
impactFactor = weights.geo * factors.geo + weights.sec * factors.sec + weights.eco * factors.eco
```

**Example**: A user with `homeCountry = "KR"` (South Korea) viewing a
`conflict` event in North Korea (`KP`):

```
weights = {geo: 0.35, sec: 0.45, eco: 0.20}
factors = {geo: 1.0, sec: 1.0, eco: 0.1}   # KR -> KP in IMPACT_FACTORS
impactFactor = 0.35*1.0 + 0.45*1.0 + 0.20*0.1 = 0.82
```

A raw KScore of 7.0 would become 7.0 * 0.82 = 5.74 for a Korean user.

#### Supported Home Countries (Phase 1)

Impact factors are currently defined for **10 home countries**, each with
bilateral factor tuples for 5--16 event countries:

KR (South Korea), US (United States), JP (Japan), CN (China), TW (Taiwan),
DE (Germany), GB (United Kingdom), AU (Australia), IN (India), BR (Brazil).

For home countries not in the supported list, a **default factor of 0.5** is
applied uniformly. When no home country is selected (BASIC plan), the raw
KScore is used without modification (factor = 1.0).

---

## 5. Tension Index

The Tension Index is a per-country composite risk score (0--100) computed every
5 minutes for all monitored countries.

### 5.1 Raw Score Formula

```
Raw Score = 0.55 * EventScore + 0.35 * ActivityScore + 0.10 * Spillover
```

#### EventScore (0--100)

Cumulative severity of active clusters, weighted by confidence and event count,
on a logarithmic scale:

```
raw_total = sum(
    cluster.severity * cluster.confidence * log2(1 + cluster.event_count)
    for cluster in country_clusters
)
```

Clusters older than 24 hours receive a `STALE_DECAY` factor of 0.5.

The raw total is then normalized against a **7-day rolling baseline** to
automatically adapt to changes in data volume:

```
baseline = 7-day moving average of global median raw_total across all countries
normalized_total = (raw_total / baseline) * 1000
EventScore = min(100, 25.0 * log10(1 + normalized_total))
```

This normalization means that adding new source channels does not
systematically inflate all tension scores -- the global baseline rises
correspondingly.

#### ActivityScore (0--100)

A composite of event volume (60%) and acceleration (40%):

```
volume = min(1.0, total_events / 100)           # 100 events = saturation
accel = min(1.0, max(0.0, (current - prev) / max(prev, 1)))   # cluster count delta
ActivityScore = (0.6 * volume + 0.4 * accel) * 100
```

#### Spillover (0--100)

Neighboring countries' crises influence a country's tension through geographic
proximity. The platform defines neighbor relationships for **112 countries**
(124 unique country codes) based on shared borders, regional conflict dynamics,
and historical spillover patterns.

```
avg_neighbor_severity = mean(max(c.severity for c in neighbor_clusters) for each neighbor)
Spillover = (avg_neighbor_severity / 100) * 0.7 * 100
```

The 0.7 dampening factor limits the maximum spillover contribution to 70% of
the neighbor's peak severity.

### 5.2 Convergence Bonus

When 3 or more distinct topic types are active simultaneously in a single
country within 24 hours, a convergence bonus is added to the raw score. This
signals escalating multi-dimensional instability.

Different topic combinations carry different weights:

| Combination | Condition | Maximum Bonus |
|-------------|-----------|---------------|
| Political/military convergence | 3+ of {conflict, coup, protest, sanctions, terror, cyber} | +25 (7 pts per topic) |
| Mixed convergence | 2+ political/military + 1+ natural disaster | +15 (4 pts per topic) |
| Natural disaster compound | 3+ topics, < 2 political/military | +10 (3 pts per topic) |

### 5.3 Anomaly Detection

An online anomaly detection system based on **Welford's algorithm** maintains
streaming mean and variance statistics for each country's tension scores.

```
z_score = (current_tension - running_mean) / running_stddev
```

When `|z_score| > 2.5`, the anomaly is flagged and stored. The system requires
a minimum of **2,160 samples** (approximately 90 days at hourly granularity) to
produce meaningful z-scores. Before this threshold is reached, anomaly
detection is disabled.

### 5.4 Percentile Ranking

The raw score is ranked against the country's own **14-day history** using
midrank percentile (ties at +/- 0.5 are counted at half weight). During warmup
(fewer than 20 historical records), the raw score is discounted by a factor of
0.6 to prevent overestimation.

### 5.5 Conflict-Zone Floor

Active conflict zones maintain a minimum tension score even during reporting
gaps (nighttime, weekends, internet shutdowns). This prevents unrealistically
low scores for countries with ongoing wars.

| Country | Floor | Context |
|---------|-------|---------|
| Ukraine (UA) | 55 | Russia full-scale war |
| Palestine (PS) | 50 | Israel-Hamas war |
| Syria (SY) | 50 | Civil war + external airstrikes |
| Yemen (YE) | 45 | Houthi rebellion + coalition strikes |
| Myanmar (MM) | 40 | Post-coup civil war |
| Sudan (SD) | 40 | RSF vs. SAF |
| Somalia (SO) | 35 | Al-Shabaab insurgency |
| Afghanistan (AF) | 35 | Taliban governance + IS-K |
| South Sudan (SS) | 30 | Inter-communal violence |
| Ethiopia (ET) | 30 | Tigray aftermath |
| Libya (LY) | 30 | East-west political division |
| Burkina Faso (BF) | 30 | Jihadist insurgency |
| Iraq (IQ) | 25 | Sporadic IS attacks |
| Mali (ML) | 25 | Sahel conflict |
| Central African Republic (CF) | 25 | Rebel activity |
| DR Congo (CD) | 25 | Eastern armed groups |
| Niger (NE) | 25 | Sahel spillover |

The floor is applied after convergence bonus and percentile calculation but
before tension level determination. These values are currently manually curated;
a planned improvement is to auto-calculate them from ACLED 90-day event density
data.

### 5.6 Tension Levels

| Level | Label | Score Range |
|-------|-------|-------------|
| 0 | Stable | 0--20 |
| 1 | Caution | 20--40 |
| 2 | Alert | 40--60 |
| 3 | Severe | 60--80 |
| 4 | Extreme | 80--100 |

Hard rules: a raw score below 20 forces level 0; a raw score below 40 caps at
level 1.

---

## 6. Spike Detection

Spikes identify clusters that represent rapidly developing, high-impact events
requiring immediate attention. Spike detection operates on **accumulated
cluster state** rather than real-time event rate, reflecting the batch
collection model (5-minute polling cycles).

### 6.1 Trigger Conditions

All four conditions must be simultaneously satisfied:

| Condition | Threshold | Rationale |
|-----------|-----------|-----------|
| `event_count >= 8` | Sufficient reporting volume | Multiple outlets must cover the event |
| `severity >= 40` | Minimum risk threshold | Eliminates routine events |
| `independent_sources >= 3` | Multi-source confirmation | Prevents single-source false alarms |
| `cluster_age <= 48h` | Recency | Excludes stale clusters |

### 6.2 Cooldown Mechanism

To prevent repeated alerts for the same developing story, a cooldown period is
enforced per cluster via Redis:

| Severity Level | Cooldown Duration |
|----------------|-------------------|
| Critical (severity >= 90) | 3 hours |
| Normal | 6 hours |

### 6.3 Spike Effects

When a spike is triggered:
1. A `SpikeEvent` record is created in the database
2. The cluster's `is_spike` flag is set to `True`
3. The cluster appears in trending results regardless of `KSCORE_MIN` threshold
4. Push notifications are dispatched to users watching the affected country
5. An SNS post candidate is generated for editorial review

---

## 7. Limitations and Known Biases

### 7.1 English-Language Source Bias

The majority of RSS feeds and the GDELT database are English-language sources.
While Telegram channels include Arabic, Russian, and Ukrainian content, and the
keyword classification engine supports 8 languages, the system's coverage is
inherently weighted toward events that receive English-language media attention.

**Mitigation**: The Information Accessibility Adjustment (Section 3.2.3)
partially compensates for under-reporting in countries with restricted press
freedom.

### 7.2 Latency

The platform is near-real-time but not instantaneous:
- RSS and Telegram polling occurs every 5 minutes
- GDELT data has a ~15-minute publication delay
- ACLED data is updated daily (not real-time)
- Tension Index and KScore calculations run on 5-minute cycles with staggered
  offsets
- Total end-to-end latency from event occurrence to dashboard appearance is
  typically **5--20 minutes** for well-covered events

### 7.3 Country Extraction Limitations

Geographic attribution relies on keyword matching against a curated dictionary.
This approach has known failure modes:
- Events mentioning multiple countries may be attributed to the wrong one
  (longest-match heuristic mitigates but does not eliminate this)
- Events in locations not in the dictionary default to a `0000:{topic}` bucket
  with limited geographic resolution
- Ambiguous place names (e.g., "Georgia" can refer to the US state or the
  Caucasus nation) may be misattributed

### 7.4 AI Classification Costs

GPT-4o-mini is called for every unstructured event normalization and for
boundary-zone cluster matching decisions. Processing costs scale linearly
with event volume. At the current scale (~1,000 events per 15-minute cycle),
this is manageable, but significant source expansion would increase costs
proportionally.

### 7.5 Impact Factor Coverage

The personalization system currently supports only 10 home countries, covering
5--16 bilateral relationships each. Events in countries not in a user's impact
factor table receive a default factor of 0.5, which may under- or over-weight
their true significance.

### 7.6 Conflict-Zone Floor Subjectivity

The minimum tension scores for conflict zones are manually assigned based on
editorial judgment of ongoing conflict intensity. These values may lag behind
rapid changes in conflict dynamics (e.g., a sudden ceasefire or escalation).

### 7.7 Temporal Clustering Window

The 24-hour clustering window may merge distinct events that happen in rapid
succession within the same country and topic (e.g., two separate airstrikes in
Ukraine on the same day). The Filtered Jaccard similarity check mitigates this,
but events with very similar descriptions may still be merged.

---

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| v6 | 2026-03-07 | KScore weight rebalance: severity 40% -> 30%, velocity 25% -> 30%, spread 20% -> 30%. Decay softened: lambda 0.04 -> 0.025, floor 0.15 -> 0.30. Filtered Jaccard introduced. Clustering window 12h -> 24h. |
| v5 | 2026-03-07 | Source expansion 37 -> 58 channels. Spread saturation 8 -> 12. Spike thresholds tightened: event_count 5 -> 8, sources 2 -> 3. |
| v4 | 2026-02-27 | KScore normalized to 0--10 scale. Velocity normalized to 0--1 (fixed 63% dominance bug). KSCORE_MIN recalibrated to 1.5. |
| v3 | 2026-02-27 | Rolling baseline normalization for Tension Index. Automatic adaptation to source volume changes. |
| v2 | 2026-02-25 | Scaled from 10 to 37 channels. VOLUME_SATURATION 20 -> 100. TRENDING_LIMIT 20 -> 30. |
| v1 | 2025 | Initial release. 10 channels, ~158 events/cycle. |

---

## References

| Component | Source File |
|-----------|------------|
| KScore formula | `worker/processor/trending_engine.py` |
| Calibration constants | `worker/processor/calibration.py` |
| Topic classification & severity | `worker/processor/normalizer.py` |
| Clustering algorithm | `worker/processor/clusterer.py` |
| Tension Index | `worker/processor/tension_calculator.py` |
| Spike detection | `worker/processor/spike_detector.py` |
| Convergence detection | `worker/processor/convergence_detector.py` |
| Anomaly detection | `worker/processor/anomaly_detector.py` |
| Impact factors | `worker/processor/calibration.py` (IMPACT_FACTORS) |
| RSS collector | `worker/collector/rss_collector.py` |
| Telegram collector | `worker/collector/telegram_collector.py` |
| GDELT collector | `worker/collector/gdelt_collector.py` |
| ACLED collector | `worker/collector/acled_collector.py` |
| USGS earthquake collector | `worker/collector/usgs_earthquake.py` |
| ReliefWeb collector | `worker/collector/reliefweb_collector.py` |
| Travel Advisory collector | `worker/collector/travel_advisory.py` |

---

*This document is published under CC BY-NC 4.0. For questions or corrections,
please open an issue on the
[wewantpeace-methodology](https://github.com/nameofkk/wewantpeace-methodology)
repository.*

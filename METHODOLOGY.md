# WeWantPeace Methodology

> Version 2.0 | Last updated: 2026-03-08
>
> This document describes the algorithms and data pipeline **as implemented in code**.
> All formulas, thresholds, and constants reference specific source files.

---

## 1. Overview

WeWantPeace is a global conflict and crisis monitoring service that collects news events from multiple sources, normalizes and classifies them, clusters related reports into issues, and produces two core metrics:

- **Tension Index** -- a per-country risk score (0--100) updated every 5 minutes
- **KScore (Key Impact Score)** -- a per-issue relevance score (0--10) personalized to the user's home country

The data pipeline runs on Celery Beat with the following stages:

```
Collect (RSS/Telegram/GDELT/ACLED/ReliefWeb/USGS)
   -> Normalize (GPT-4o-mini + keyword fallback)
      -> Cluster (Filtered Jaccard + AI boundary judgment)
         -> Score (Tension Index + KScore + Spike Detection)
            -> Deliver (Push notifications, in-app, SNS auto-posting)
```

---

## 2. Data Sources

**58 active channels** (`calibration.py` ACTIVE_CHANNELS = 58)

| Source Type | Count | Collection Interval | Description |
|-------------|-------|---------------------|-------------|
| RSS feeds | 37+ | Every 5 minutes | International wire services, regional outlets |
| Telegram OSINT | 12 whitelisted channels | Every 5 minutes | Conflict zone first-hand reports |
| GDELT | 1 API | Every 15 minutes | Global event database |
| ACLED | 1 API | Daily (06:30 UTC) | Armed Conflict Location & Event Data |
| ReliefWeb | 1 API | Every 30 minutes | UN humanitarian updates |
| USGS | 1 API | Every 5 minutes | Earthquakes M5.0+ |
| Travel Advisory | 1 API | Every 6 hours | US State Dept Level 2+ advisories |

Each source is registered in the `source_channels` table with a tier (A/B/C/D), base confidence, language, topic focus, and geographic focus.

Reference: `worker/celery_app.py` (beat_schedule), `backend/app/models/source_channel.py`

---

## 3. Source Tier System

Every source channel is assigned a tier that determines the base confidence of events it produces.

| Tier | Base Confidence | Tier Bonus (KScore quality) | Effective Range | Examples |
|------|----------------|----------------------------|-----------------|----------|
| A | 0.85 | +0.05 | 0.85--0.95 | Reuters, AP, BBC, Al Jazeera |
| B | 0.70 | +0.03 | 0.70--0.95 | Regional wire services |
| C | 0.55 | +0.01 | 0.55--0.95 | Local outlets, niche sources |
| D | 0.35 | +0.00 | 0.35 | Unverified, social media aggregators |

Confidence is capped at **0.95** regardless of tier accumulation.

```python
# normalizer.py: _calculate_confidence()
base = {"A": 0.85, "B": 0.70, "C": 0.55, "D": 0.35}.get(tier, 0.50)
return round(min(0.95, base), 2)
```

The tier bonus contributes to the KScore **quality** component:

```python
# trending_engine.py: _calc_kscore()
tier_bonus = sum(0.05 if t == "A" else 0.03 if t == "B" else 0.01 for t in source_tiers)
quality = min(1.0, confidence + tier_bonus)
```

Reference: `worker/processor/normalizer.py`, `worker/processor/trending_engine.py`

---

## 4. Event Normalization

Each raw event is normalized into a structured `NormalizedEvent` with topic, severity, confidence, geo-coordinates, and language.

### 4.1 Topic Classification (11 topics)

Classification uses a two-layer approach:

1. **GPT-4o-mini** (primary): Receives title + body (truncated), returns `{topic, severity}` as JSON.
2. **Keyword rule fallback**: If AI fails or is unavailable, matches against `TOPIC_KEYWORDS` dictionary with strong/weak keyword scoring.

The 11 topics are:

| Topic | Description |
|-------|-------------|
| `conflict` | Armed conflict, military operations, airstrikes, war |
| `terror` | Terrorism, hostage situations, mass shootings, extremist attacks |
| `coup` | Coups, military takeovers, martial law |
| `sanctions` | Economic sanctions, embargoes, tariffs, financial crises |
| `cyber` | Cyberattacks, hacking, ransomware, internet shutdowns |
| `protest` | Protests, demonstrations, riots, civil unrest |
| `diplomacy` | Diplomatic events, treaties, summits, elections |
| `maritime` | Naval operations, shipping disruptions, piracy |
| `disaster` | Natural disasters, industrial accidents, humanitarian crises |
| `health` | Disease outbreaks, epidemics, pandemics |
| `unknown` | Unclassifiable events |

Reference: `worker/processor/normalizer.py` (_VALID_TOPICS, TOPIC_KEYWORDS)

### 4.2 Severity Scoring (0--100)

**AI path**: GPT-4o-mini assigns severity directly on a 0--100 scale with calibration examples in the system prompt.

**Keyword fallback path**: `severity = base + keyword_modifier + casualty_bonus`

| Topic | Base Severity |
|-------|--------------|
| coup | 65 |
| conflict | 60 |
| terror | 60 |
| maritime | 50 |
| disaster | 50 |
| sanctions | 45 |
| cyber | 40 |
| health | 40 |
| protest | 35 |
| diplomacy | 30 |
| unknown | 20 |

- **Keyword modifier**: SEVERITY_UP (e.g., "killed" +10, "genocide" +20) and SEVERITY_DOWN (e.g., "ceasefire" -10, "hoax" -15). Capped at +/-40.
- **Casualty bonus**: Extracted from text. Up to +30 for mass casualty events.

Reference: `worker/processor/normalizer.py` (TOPIC_BASE_SEVERITY, SEVERITY_UP, SEVERITY_DOWN, _casualty_bonus)

---

## 5. Clustering

Events are grouped into `IssueCluster` entities using a 24-hour sliding window.

### 5.1 Cluster Key

Each event is assigned a cluster key: `{country_code}:{topic}` (preferred) or `{geohash4}:{topic}` (fallback when no country code), or `0000:{topic}` (no geo info).

### 5.2 Filtered Jaccard Similarity

Within the same cluster key bucket, events are matched to existing clusters using **Filtered Jaccard** -- a Jaccard similarity metric that removes country names, topic keywords, and stop words before comparison. This isolates content-specific terms and prevents false merges where two different events in the same country/topic share only generic words.

| Condition | Threshold |
|-----------|-----------|
| General events | `MIN_TITLE_OVERLAP = 0.15` |
| High-severity (both sides severity >= 50) | `MIN_TITLE_OVERLAP_HIGH_SEV = 0.08` |
| AI judgment zone | `0.10 <= sim < threshold` |
| Always separate | `sim < 0.10` |

### 5.3 AI Boundary Judgment

When Filtered Jaccard falls in the boundary zone (0.10 to threshold), GPT-4o-mini is asked: "Are these two headlines the same event?" This prevents both false merges and false splits at the boundary.

- Maximum 2 AI calls per event (cost control)
- LRU cache (256 entries) prevents duplicate API calls for the same headline pair
- Fallback on API failure: treat as separate events

### 5.4 Cluster Updates

When an event joins an existing cluster:
- `event_count` increments
- `confidence` is updated as a running average
- `severity` takes the maximum across all events
- `source_tiers` list is appended
- Junk titles are automatically replaced with better event titles
- AI-generated bilingual titles (en/ko) are preferred

Reference: `worker/processor/clusterer.py`

---

## 6. Tension Index

The Tension Index is a per-country risk score (0--100) computed every 5 minutes for all active monitored countries.

### 6.1 Formula

```
Raw Score = 0.55 * EventScore + 0.35 * ActivityScore + 0.10 * Spillover
```

**EventScore** (0--100): Log-scale cumulative severity of active clusters, normalized against a rolling baseline.

```python
# tension_calculator.py: _calc_event_score()
total = sum(c.severity * c.confidence * log2(1 + c.event_count) for c in clusters)
normalized = (total / baseline) * BASELINE_REFERENCE_SCALE  # baseline = 7-day rolling median
EventScore = min(100, EVENT_SCORE_MULTIPLIER * log10(1 + normalized))
# EVENT_SCORE_MULTIPLIER = 25.0, BASELINE_REFERENCE_SCALE = 1000.0
```

Clusters older than 24 hours receive a decay factor of `STALE_DECAY = 0.5`.

**ActivityScore** (0--100): Volume and acceleration mix.

```python
# tension_calculator.py: _calc_accel_score()
volume = min(1.0, current_events / VOLUME_SATURATION)  # VOLUME_SATURATION = 100
accel = min(1.0, max(0.0, (current_count - prev_count) / max(prev_count, 1)))
ActivityScore = (0.6 * volume + 0.4 * accel) * 100
```

**Spillover** (0--100): Influence from neighboring countries.

```python
# tension_calculator.py: _calc_spillover()
avg_neighbor_max_severity = mean(max(c.severity for c in neighbor_clusters) for each neighbor)
Spillover = (avg_neighbor_max_severity / 100) * 0.7 * 100
```

### 6.2 Percentile Ranking

The raw score is ranked against the country's own 14-day history using midrank percentile. During warmup (fewer than 20 historical records), the raw score is discounted by `TENSION_WARMUP_FACTOR = 0.6` to prevent overestimation.

### 6.3 Tension Levels

| Level | Label | Range |
|-------|-------|-------|
| 0 | Stable | 0--20 |
| 1 | Caution | 20--40 |
| 2 | Alert | 40--60 |
| 3 | Severe | 60--80 |
| 4 | Extreme | 80--100 |

Absolute floor rules: raw_score < 20 forces level 0; raw_score < 40 caps at level 1.

### 6.4 Rolling Baseline Normalization

To automatically adapt to changes in data volume (e.g., adding new source channels), EventScore is normalized against a **7-day rolling baseline**:

1. Each cycle: compute the median of all countries' raw totals
2. Store in Redis with 8-day TTL
3. Baseline = 7-day moving average of these medians
4. `normalized_total = (country_total / baseline) * 1000`

This means adding 20 new RSS feeds does not inflate all scores -- the baseline rises correspondingly.

Reference: `worker/processor/tension_calculator.py`, `worker/processor/calibration.py`

---

## 7. KScore -- Key Impact Score

KScore measures how important an issue cluster is, combining event velocity, source quality, severity, and multi-source spread. It is computed on a 0--10 scale.

### 7.1 Raw KScore Formula

```
raw = 0.30 * velocity_norm + 0.10 * quality + 0.30 * severity_norm + 0.30 * spread
KScore = raw * KSCORE_SCALE * decay
```

Where:
- `KSCORE_SCALE = 10` (maps 0--1 raw to 0--10 output)

**velocity_norm** -- Event accumulation speed:
```python
velocity_raw = min(VELOCITY_CAP, event_count^VELOCITY_EXPONENT * spike_factor)
velocity_norm = velocity_raw / VELOCITY_CAP
# VELOCITY_EXPONENT = 0.7, VELOCITY_CAP = 6.0, SPIKE_FACTOR = 1.5 (if is_spike)
```

**quality** -- Source reliability:
```python
quality = min(1.0, confidence + tier_bonus)
# tier_bonus: A=+0.05, B=+0.03, C=+0.01, D=+0.00
```

**severity_norm** -- Normalized severity:
```python
severity_norm = severity / 100.0
```

**spread** -- Independent source diversity:
```python
spread = min(1.0, independent_sources / SPREAD_SATURATION)
# SPREAD_SATURATION = 12
```

**decay** -- Time decay:
```python
decay = max(DECAY_FLOOR, exp(-DECAY_LAMBDA * age_hours))
# DECAY_LAMBDA = 0.025 (half-life ~28 hours), DECAY_FLOOR = 0.30
```

Decay curve: 6h=86%, 12h=74%, 24h=55%, 48h=30% (floor).

### 7.2 KScore UI Thresholds

| Level | KScore Range |
|-------|-------------|
| Stable | < 2.0 |
| Caution | 2.0--4.0 |
| Alert | 4.0--6.0 |
| Severe | 6.0--8.0 |
| Extreme | >= 8.0 |

Minimum inclusion threshold: `KSCORE_MIN = 1.5` (below this, excluded from trending unless spike).

### 7.3 Personalization -- Impact Factors

KScore is personalized per user's **home country**. The frontend multiplies the raw KScore by a country-pair impact factor:

```typescript
// frontend/lib/impact-factors.ts: calcImpactFactor()
const factor = w.geo * f.geo + w.sec * f.sec + w.eco * f.eco;
personalizedKScore = rawScore * factor;
```

Where for each (home_country, event_country) pair:
- `geo` -- geographic proximity (0--1)
- `sec` -- security relevance (0--1)
- `eco` -- economic linkage (0--1)

And topic-specific weights determine how much each axis matters:

| Topic | geo | sec | eco |
|-------|-----|-----|-----|
| conflict | 0.35 | 0.45 | 0.20 |
| terror | 0.40 | 0.40 | 0.20 |
| coup | 0.30 | 0.50 | 0.20 |
| sanctions | 0.20 | 0.25 | 0.55 |
| cyber | 0.20 | 0.30 | 0.50 |
| protest | 0.40 | 0.30 | 0.30 |
| diplomacy | 0.30 | 0.40 | 0.30 |
| maritime | 0.40 | 0.30 | 0.30 |
| disaster | 0.60 | 0.10 | 0.30 |
| health | 0.50 | 0.10 | 0.40 |

Currently supported home countries (Phase 1, 10 countries): KR, US, JP, CN, TW, DE, GB, AU, IN, BR.

For unsupported home countries, a default factor of 0.5 is applied.

Reference: `worker/processor/trending_engine.py`, `worker/processor/calibration.py` (IMPACT_FACTORS, TOPIC_IMPACT_WEIGHTS), `frontend/lib/impact-factors.ts`

---

## 8. Spike Detection

Spikes identify clusters that represent rapidly developing, high-impact events requiring immediate attention.

### 8.1 Trigger Conditions (all must be met)

```python
event_count >= 8            # sufficient reporting volume
AND severity >= 40          # minimum risk threshold
AND independent_sources >= 3  # multi-source confirmation
AND cluster_age <= 48h      # recent cluster only
```

### 8.2 Cooldown

To prevent repeated alerts for the same developing story:
- **Critical severity (>= 90)**: 3-hour cooldown
- **Normal**: 6-hour cooldown

Cooldown state is stored in Redis.

### 8.3 Spike Events

When triggered, a `SpikeEvent` record is created linking to the cluster, and the cluster's `is_spike` flag is set to `True`. Spike clusters always appear in trending results regardless of KSCORE_MIN threshold.

Reference: `worker/processor/spike_detector.py`

---

## 9. Conflict-Zone Floor

Active conflict zones maintain a minimum tension score even during reporting gaps (e.g., nighttime, weekend lulls). This prevents unrealistically low scores for countries with ongoing wars.

```python
# calibration.py: CONFLICT_FLOOR
CONFLICT_FLOOR = {
    "UA": 55.0,   # Ukraine: Russia full-scale war
    "PS": 50.0,   # Palestine: Israel-Hamas war
    "SY": 50.0,   # Syria: civil war + airstrikes
    "YE": 45.0,   # Yemen: Houthi + coalition strikes
    "MM": 40.0,   # Myanmar: post-coup civil war
    "SD": 40.0,   # Sudan: RSF vs SAF
    "SO": 35.0,   # Somalia: Al-Shabaab
    "AF": 35.0,   # Afghanistan: Taliban + IS
    "SS": 30.0,   # South Sudan: tribal clashes
    "ET": 30.0,   # Ethiopia: Tigray
    "LY": 30.0,   # Libya: east-west division
    "BF": 30.0,   # Burkina Faso: jihadist insurgency
    "IQ": 25.0,   # Iraq: sporadic IS
    "ML": 25.0,   # Mali: Sahel conflict
    "CF": 25.0,   # Central African Republic: rebels
    "CD": 25.0,   # DRC: eastern armed groups
    "NE": 25.0,   # Niger: Sahel spillover
}
```

The floor is applied **after** percentile calculation but **before** level determination:

```python
raw_score = max(raw_score, CONFLICT_FLOOR.get(country_code, 0.0))
```

Reference: `worker/processor/calibration.py`, `worker/processor/tension_calculator.py`

---

## 10. Information Accessibility Adjustment

Countries with restricted press freedom tend to systematically under-report events. To compensate, severity scores are adjusted upward using a modifier derived from the RSF Press Freedom Index.

```python
# calibration.py: INFORMATION_ACCESSIBILITY
# Formula: modifier = 1.0 + (rsf_score / 100) * 0.3
# Free press (RSF ~20): modifier ~1.06
# Restricted press (RSF ~80): modifier ~1.24

adjusted_severity = min(100, int(severity * INFORMATION_ACCESSIBILITY.get(country_code, 1.0)))
```

Selected values:

| Country | Modifier | RSF Score (approx) |
|---------|----------|-------------------|
| North Korea (KP) | 1.27 | ~90 |
| Turkmenistan (TM) | 1.26 | ~87 |
| Eritrea (ER) | 1.25 | ~84 |
| China (CN) | 1.22 | ~75 |
| Iran (IR) | 1.22 | ~74 |
| Myanmar (MM) | 1.21 | ~70 |
| Syria (SY) | 1.21 | ~70 |
| Russia (RU) | 1.20 | ~66 |
| Cuba (CU) | 1.18 | ~62 |
| Saudi Arabia (SA) | 1.17 | ~57 |

Countries not in the table receive no adjustment (modifier = 1.0).

Reference: `worker/processor/calibration.py` (INFORMATION_ACCESSIBILITY), `worker/processor/normalizer.py` (application in normalize())

---

## 11. Verification System

Clusters are automatically verified or unverified based on source quality criteria.

### Verification Conditions (all must be met)

```python
is_verified = (
    confidence >= 0.70
    AND "A" in source_tiers      # At least one Tier A source present
    AND independent_sources >= 2  # At least 2 independent source channels
)
```

Verification is **bidirectional**: if conditions cease to hold (e.g., confidence drops due to new low-quality sources), the cluster is automatically un-verified.

Note: Tier B sources alone are not sufficient for verification -- at least one Tier A source is required.

Reference: `worker/processor/clusterer.py` (assign_cluster, is_verified logic)

---

## 12. Monitoring Coverage

### 12.1 Monitored Countries

**198 countries and territories** are tracked in the `MONITORED_COUNTRIES` list, covering:
- Europe (49), Middle East (16), East Asia (7), Southeast Asia (11), South Asia (8), Central Asia (5), Africa (54), North America (3), Central America/Caribbean (20), South America (12), Oceania (14).

### 12.2 Neighbor Map (Spillover)

**112 countries** have defined neighbor relationships in `NEIGHBOR_MAP`, covering **124 unique country codes** in total. These neighbor pairs are used for the Spillover component of the Tension Index.

Reference: `worker/processor/tension_calculator.py` (MONITORED_COUNTRIES, NEIGHBOR_MAP)

---

## 13. Update Cadence

| Task | Frequency | Offset | Queue |
|------|-----------|--------|-------|
| RSS collection | Every 5 min | :00 | collect |
| Telegram collection | Every 5 min | :00 | collect |
| USGS earthquake collection | Every 5 min | :00 | collect |
| GDELT collection | Every 15 min | :00 | collect |
| ReliefWeb collection | Every 30 min | :00 | collect |
| ACLED collection | Daily (06:30 UTC) | -- | collect |
| Travel Advisory collection | Every 6 hours | :00 | collect |
| **Tension Index calculation** | **Every 5 min** | +1 min | process |
| **KScore/Trending calculation** | **Every 5 min** | +2 min | process |
| Service health monitoring | Every 5 min | +3 min | process |
| Orphan event reprocessing | Every 1 hour | :00 | process |
| Source reliability evaluation | Weekly (Sun 15:30) | -- | process |
| Severity outlier detection | Daily (05:00 UTC) | -- | process |
| Stale cluster deactivation | Daily (06:00 UTC) | -- | process |

Core metrics (Tension Index and KScore) are refreshed every **5 minutes**.

Reference: `worker/celery_app.py` (beat_schedule)

---

## 14. Limitations and Future Work

### Current Limitations

1. **Conflict-Zone Floor values are manually defined.** Future: auto-calculate from ACLED 90-day event density.
2. **Impact Factors cover 10 home countries.** Future: auto-generate 120x120 matrix from CEPII trade data, geographic distance, and ATOP alliance data.
3. **Convergence detection implemented.** When 3+ different topic clusters activate simultaneously in one country, a convergence bonus (up to +25 points) is added to the tension raw_score. Political/military combos (conflict, coup, protest, sanctions, terror, cyber) receive higher bonus than natural disaster combos.
4. **Partial travel advisory integration.** US State Dept advisory data is collected (Level 2+). Future: add MFA Korea (0404.go.kr), UK FCDO advisories and reflect advisory levels directly in tension scoring.
5. **Standard PostgreSQL, not TimescaleDB.** Time-series data is stored in regular PostgreSQL tables with `(country_code, time)` indexes. TimescaleDB hypertables and continuous aggregates are not used.
6. **AI classification costs.** GPT-4o-mini is called for every event normalization and for boundary-zone cluster matching. Cost scales linearly with event volume.

### Planned Improvements

- Welford-based anomaly detection active (accumulating 90-day baseline, z-score > 2.5 threshold)
- Multi-signal convergence detection active (political/military vs. natural disaster differentiation)
- Expand travel advisory to MFA Korea + UK FCDO
- KScore Phase 2: auto-generated impact factor matrix for 120+ countries
- Public read-only API with rate limiting

---

*Last code audit: 2026-03-08. All formulas verified against source files in `worker/processor/`.*

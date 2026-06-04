# WeWantPeace Data Dictionary

> Version 1.0 | Last updated: 2026-03-08
>
> Defines all core data entities, their fields, types, and relationships.
> All definitions are derived from SQLAlchemy models in `backend/app/models/`.

---

## Entity Relationship Overview

```
source_channels (1) --< (N) raw_events
raw_events (1) --< (1) normalized_events
normalized_events (N) -->< (N) issue_clusters  [via cluster_events junction]
issue_clusters (1) --< (N) spike_events
issue_clusters (1) --< (N) trending_keywords
tension_index (standalone time-series, keyed by country_code + time)
```

---

## 1. source_channels

Registered data sources (RSS feeds, Telegram channels, API endpoints).

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | Integer (PK, auto) | No | Internal source ID |
| `channel_id` | BigInteger (unique) | Yes | Telegram channel numeric ID (null for RSS/API) |
| `username` | String(128) | Yes | Telegram username or RSS feed identifier |
| `display_name` | String(256) | No | Human-readable source name |
| `tier` | String(1) | No | Source tier: A, B, C, or D (CHECK constraint) |
| `base_confidence` | Float | No | Default confidence score (default 0.70) |
| `language` | String(8) | Yes | Primary language code (default "en") |
| `topics` | StringArray | No | Topic focus areas (e.g., ["conflict", "terror"]) |
| `geo_focus` | StringArray | No | Country codes this source covers (e.g., ["UA", "RU"]) |
| `source_type` | String(16) | No | "telegram", "rss", "api" (default "telegram") |
| `feed_url` | String | Yes | RSS feed URL (null for Telegram/API) |
| `api_endpoint` | String | Yes | API base URL (for GDELT, ACLED, etc.) |
| `api_params` | JSON | Yes | API-specific parameters |
| `last_fetch_cursor` | String | Yes | Pagination cursor for incremental fetching |
| `is_active` | Boolean | No | Whether this source is currently being collected |
| `created_at` | Timestamp (TZ) | No | Record creation time |
| `updated_at` | Timestamp (TZ) | No | Last modification time |

**Tier definitions:**

| Tier | Base Confidence | Description |
|------|----------------|-------------|
| A | 0.85 | Major wire services (Reuters, AP, BBC, Al Jazeera) |
| B | 0.70 | Regional wire services, established outlets |
| C | 0.55 | Local outlets, niche sources |
| D | 0.35 | Unverified, social media aggregators |

Model: `backend/app/models/source_channel.py`

---

## 2. raw_events

Unprocessed events as collected from source channels.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID (PK) | No | Unique event identifier |
| `source_channel_id` | Integer (FK -> source_channels) | Yes | Source that produced this event (SET NULL on delete) |
| `source_type` | String(16) | No | "telegram", "rss", "gdelt", "acled", "reliefweb", "usgs" |
| `external_id` | String(256) | No | Source-specific unique ID (message ID, article URL hash, etc.) |
| `raw_text` | String | No | Full original text content |
| `raw_metadata` | JSON | No | Source-specific metadata (author, URL, publish date, etc.) |
| `lang` | String(8) | Yes | Detected language code |
| `collected_at` | Timestamp (TZ) | No | When the event was fetched |
| `processed` | Boolean | No | Whether normalization has been attempted (default false) |

**Unique constraint:** (`source_type`, `external_id`) -- prevents duplicate ingestion.

Model: `backend/app/models/raw_event.py`

---

## 3. normalized_events

Structured events after classification, severity scoring, and geo-extraction.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID (PK) | No | Unique event identifier |
| `raw_event_id` | UUID (FK -> raw_events) | Yes | Link to source raw event |
| `title` | String | No | English event title (translated if non-English source) |
| `title_ko` | String | Yes | Korean translation of title |
| `body` | String | Yes | Event body text (truncated) |
| `topic` | String(32) | No | One of 11 topics (see below) |
| `entity_anchor` | String(256) | Yes | Key entity name for dedup (e.g., person, organization) |
| `lat` | Float | Yes | Latitude of event location |
| `lon` | Float | Yes | Longitude of event location |
| `geohash5` | String(8) | Yes | 5-character geohash for spatial indexing |
| `country_code` | String(4) | Yes | ISO 3166-1 alpha-2 country code |
| `severity` | SmallInteger | No | Risk severity score (0--100, default 0) |
| `source_tier` | String(1) | No | Tier of the originating source (A/B/C/D) |
| `confidence` | Float | No | Confidence score (0.0--0.95, default 0.0) |
| `dedup_key` | String(64) | No | MD5 hash of normalized text (first 60 words) |
| `is_duplicate` | Boolean | No | Whether this is a detected duplicate (default false) |
| `translation_status` | String(16) | Yes | "ok", "failed", or "skipped" |
| `geo_method` | String(16) | Yes | How geo was determined: "keyword", "geocoder", "fallback", "none" |
| `image_url` | String(1024) | Yes | Associated image URL from source |
| `event_time` | Timestamp (TZ) | No | When the event occurred (published_at or collected_at) |
| `created_at` | Timestamp (TZ) | No | Record creation time |

### Topic values

```
conflict | terror | coup | sanctions | cyber | protest | diplomacy | maritime | disaster | health | unknown
```

### Severity ranges

| Range | Label | Examples |
|-------|-------|---------|
| 0--19 | Minimal | Routine exercises, policy discussions |
| 20--39 | Low | Minor incidents, diplomatic statements, 1--2 casualties |
| 40--59 | Moderate | Significant protests, localized skirmishes, 3--20 casualties |
| 60--79 | High | Major military operations, 20--100 casualties |
| 80--89 | Very High | Large-scale attacks, 100+ casualties, war escalation |
| 90--100 | Critical | Mass casualties 200+, nuclear threats, confirmed WMD use |

Severity may be adjusted upward by the Information Accessibility modifier for countries with restricted press freedom (see `calibration.py`).

Model: `backend/app/models/normalized_event.py`

---

## 4. issue_clusters

Aggregated clusters of related normalized events representing a single issue/incident.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID (PK) | No | Unique cluster identifier |
| `cluster_key` | String(512) (indexed) | No | Grouping key: `{country_code}:{topic}` or `{geohash4}:{topic}` |
| `geohash5` | String(8) | No | 5-character geohash of cluster location |
| `topic` | String(32) | No | Topic classification (same 11 values as normalized_events) |
| `entity_anchor` | String(256) | Yes | Primary entity name |
| `country_code` | String(4) | Yes | ISO country code |
| `lat` | Float | Yes | Cluster centroid latitude |
| `lon` | Float | Yes | Cluster centroid longitude |
| `title` | String | No | English cluster title (AI-generated or best event title) |
| `title_ko` | String | Yes | Korean cluster title |
| `event_count` | Integer | No | Number of events in this cluster |
| `severity` | SmallInteger | No | Maximum severity across all member events (0--100) |
| `confidence` | Float | No | Running average confidence across member events |
| `kscore` | Float | No | Current KScore (0--10, recalculated every 5 min) |
| `is_spike` | Boolean | No | Whether a spike has been triggered for this cluster |
| `spike_at` | Timestamp (TZ) | Yes | When spike was last triggered |
| `source_tiers` | StringArray | No | List of all source tiers (e.g., ["A", "B", "B", "C"]) |
| `independent_sources` | Integer | No | Count of distinct source channels reporting this issue |
| `first_event_at` | Timestamp (TZ) | No | Earliest event time in cluster |
| `last_event_at` | Timestamp (TZ) | No | Most recent event time in cluster |
| `window_start` | Timestamp (TZ) | No | 24-hour window start |
| `window_end` | Timestamp (TZ) | No | 24-hour window end (extends as new events arrive) |
| `image_url` | String(1024) | Yes | Representative image URL |
| `is_verified` | Boolean | No | Auto-verified status (see verification conditions) |
| `is_active` | Boolean | No | Whether cluster is active (false = deactivated noise) |
| `is_flagged` | Boolean | No | Admin flag for review |
| `created_at` | Timestamp (TZ) | No | Record creation time |
| `updated_at` | Timestamp (TZ) | No | Last modification time |

### Aggregation logic

- **severity**: MAX of all member events
- **confidence**: Running average (weighted by event count)
- **independent_sources**: COUNT DISTINCT source_channel_id across member events (synced in batch)
- **source_tiers**: Append-only list of each event's source tier
- **kscore**: Recalculated using `trending_engine._calc_kscore()` on each event arrival and every 5-minute batch

### Verification conditions

```python
is_verified = (confidence >= 0.70 AND "A" in source_tiers AND independent_sources >= 2)
```

### Indexes

- `ix_clusters_country_severity` -- (country_code, severity)
- `ix_clusters_topic_last_event` -- (topic, last_event_at)
- `ix_clusters_country_last_event` -- (country_code, last_event_at)
- `cluster_key` -- single-column index

Model: `backend/app/models/issue_cluster.py`

---

## 5. cluster_events (Junction Table)

Maps normalized events to issue clusters (many-to-many).

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `cluster_id` | UUID (PK, FK -> issue_clusters) | No | Cluster reference (CASCADE delete) |
| `event_id` | UUID (PK, FK -> normalized_events) | No | Event reference (CASCADE delete) |

Composite primary key: (`cluster_id`, `event_id`).

Model: `backend/app/models/issue_cluster.py` (ClusterEvent)

---

## 6. tension_index

Time-series of per-country tension scores, recorded every 5 minutes.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `time` | Timestamp (TZ, PK) | No | Measurement timestamp |
| `country_code` | String(4, PK) | No | ISO country code |
| `region_code` | String(16) | Yes | Sub-region code (reserved for future use) |
| `raw_score` | Float | No | Tension raw score (0--100, may have conflict-zone floor) |
| `tension_level` | SmallInteger | No | Discrete level (0=Stable, 1=Caution, 2=Alert, 3=Severe, 4=Extreme) |
| `event_score` | Float | Yes | EventScore component (0--100) |
| `accel_score` | Float | Yes | ActivityScore component (0--100) |
| `spillover_score` | Float | Yes | Spillover component (0--100) |
| `percentile_30d` | Float | Yes | Percentile rank in 14-day history (0--100) |

**Composite primary key:** (`time`, `country_code`).

### Formula

```
raw_score = 0.55 * event_score + 0.35 * accel_score + 0.10 * spillover_score
raw_score = max(raw_score, CONFLICT_FLOOR.get(country_code, 0))
```

### Tension levels

| Level | Value | Score Range |
|-------|-------|-------------|
| Stable | 0 | 0--20 |
| Caution | 1 | 20--40 |
| Alert | 2 | 40--60 |
| Severe | 3 | 60--80 |
| Extreme | 4 | 80--100 |

### Data retention

Records are kept indefinitely. Pro users can query 30-day history; Pro+ users can query 90-day history.

Model: `backend/app/models/tension_index.py`

---

## 7. spike_events

Records of spike triggers -- moments when a cluster meets all spike conditions.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | UUID (PK) | No | Spike event identifier |
| `cluster_id` | UUID (FK -> issue_clusters) | No | Cluster that triggered the spike (CASCADE delete) |
| `severity` | SmallInteger | No | Cluster severity at spike time |
| `kscore` | Float | No | Cluster KScore at spike time |
| `c1` | Integer | No | Event count at spike time (field reused from legacy schema) |
| `c10` | Integer | No | Independent sources at spike time (field reused from legacy schema) |
| `baseline` | Float | No | Cluster age in hours at spike time (field reused from legacy schema) |
| `ratio` | Float | No | Reserved (currently 0.0) |
| `unique_sources` | Integer | No | Independent source count (same as c10) |
| `triggered_at` | Timestamp (TZ) | No | When the spike was triggered |

### Trigger conditions

All four must be true simultaneously:

```
event_count >= 8
AND severity >= 40
AND independent_sources >= 3
AND cluster_age <= 48 hours
```

### Cooldown

- Critical (severity >= 90): 3-hour cooldown
- Normal: 6-hour cooldown
- Cooldown tracked in Redis key `spike:cooldown:{cluster_id}`

Model: `backend/app/models/spike_event.py`, `worker/processor/spike_detector.py`

---

## 8. trending_keywords

KScore-ranked trending issues, stored every 5 minutes. Top 30 per cycle.

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `id` | Integer (PK, auto) | No | Auto-incrementing ID |
| `keyword` | String(256) | No | English cluster title |
| `keyword_ko` | String(256) | Yes | Korean cluster title |
| `normalized_kw` | String(256) | No | Lowercased keyword for dedup |
| `kscore` | Float | No | KScore after time decay (0--10) |
| `raw_score` | Float | No | KScore before time decay (0--10) |
| `topic` | String(32) | Yes | Topic classification |
| `country_codes` | StringArray | No | Countries involved |
| `cluster_ids` | UUIDArray | No | Source cluster IDs |
| `event_count` | Integer | No | Total events in source clusters |
| `severity` | Integer | No | Cluster severity |
| `is_spike` | Boolean | No | Whether source cluster is a spike |
| `scope` | String(64) | No | Always "global" currently (default "global") |
| `calculated_at` | Timestamp (TZ) | No | When this KScore was calculated |
| `valid_until` | Timestamp (TZ) | No | Expiry time (calculated_at + 24 hours) |

### KScore formula

```
raw = 0.30 * velocity_norm + 0.10 * quality + 0.30 * severity_norm + 0.30 * spread
kscore = raw * 10 * decay
```

| Component | Formula | Range |
|-----------|---------|-------|
| velocity_norm | `min(VELOCITY_CAP, event_count^0.7 * spike_factor) / VELOCITY_CAP` | 0--1 |
| quality | `min(1.0, confidence + tier_bonus)` | 0--1 |
| severity_norm | `severity / 100` | 0--1 |
| spread | `min(1.0, independent_sources / 12)` | 0--1 |
| decay | `max(0.30, exp(-0.025 * age_hours))` | 0.30--1.0 |

### Personalization (client-side)

The `raw_score` field is sent to the frontend, which applies `calcImpactFactor(eventCountry, topic, homeCountry)` to produce a personalized KScore per user. Factors are defined for 10 home countries with 3 axes: geographic proximity, security relevance, and economic linkage.

### Data retention

- Recent 7 days: full 5-minute resolution
- 7--91 days: hourly resolution (deduplicated)
- Over 91 days: deleted

### Index

- `ix_trending_kw_scope_nkw_calcat` -- (scope, normalized_kw, calculated_at)

Model: `backend/app/models/trending_keyword.py`, `worker/processor/trending_engine.py`

---

## 9. KScore Calibration Constants

All tunable constants are centralized in `worker/processor/calibration.py`.

### Tension Index constants

| Constant | Value | Used In | Description |
|----------|-------|---------|-------------|
| `VOLUME_SATURATION` | 100 | tension_calculator | Events needed for volume=1.0 |
| `ACCEL_BASELINE` | 20 | tension_calculator | Cluster count for max acceleration |
| `EVENT_SCORE_MULTIPLIER` | 25.0 | tension_calculator | Log normalization coefficient |
| `BASELINE_WINDOW_DAYS` | 7 | tension_calculator | Rolling baseline window |
| `BASELINE_REFERENCE_SCALE` | 1000.0 | tension_calculator | Normalization reference |
| `STALE_DECAY` | 0.5 | tension_calculator | Decay for 24h+ clusters |
| `TENSION_WARMUP_RECORDS` | 20 | tension_calculator | Min history for percentile |
| `TENSION_WARMUP_FACTOR` | 0.6 | tension_calculator | Warmup discount factor |

### KScore constants

| Constant | Value | Used In | Description |
|----------|-------|---------|-------------|
| `VELOCITY_EXPONENT` | 0.7 | trending_engine | Velocity curve shape |
| `VELOCITY_CAP` | 6.0 | trending_engine | Max velocity value |
| `SPIKE_FACTOR` | 1.5 | trending_engine | Spike bonus multiplier |
| `SPREAD_SATURATION` | 12 | trending_engine | Sources needed for spread=1.0 |
| `KSCORE_SCALE` | 10.0 | trending_engine | Output scale (0--10) |
| `KSCORE_MIN` | 1.5 | trending_engine | Minimum for trending inclusion |
| `TRENDING_LIMIT` | 30 | trending_engine | Max trending items per cycle |
| `DECAY_LAMBDA` | 0.025 | trending_engine | Time decay rate (half-life ~28h) |
| `DECAY_FLOOR` | 0.30 | trending_engine | Minimum decay value |

### Environment parameters

| Constant | Value | Description |
|----------|-------|-------------|
| `ACTIVE_CHANNELS` | 58 | Current active source count |
| `EVENTS_PER_CYCLE` | 1000 | Average events per 15-min cycle |

Reference: `worker/processor/calibration.py`

---

## 10. Source Tier Confidence Summary

| Tier | Base Confidence | Tier Bonus (KScore) | Confidence Cap | Verification Eligible |
|------|----------------|---------------------|----------------|----------------------|
| A | 0.85 | +0.05 | 0.95 | Yes (required) |
| B | 0.70 | +0.03 | 0.95 | No (alone) |
| C | 0.55 | +0.01 | 0.95 | No |
| D | 0.35 | +0.00 | 0.35 | No |

Confidence formula: `min(0.95, base)` -- the tier bonus only applies to KScore quality, not to the stored confidence value.

---

*Last audit: 2026-03-08. All field definitions verified against SQLAlchemy models and processor code.*

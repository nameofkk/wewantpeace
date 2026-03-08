# WeWantPeace Data Dictionary

A comprehensive reference for the database schema, API response formats, and domain-specific enumerations used in the WeWantPeace platform.

---

## Core Tables

### raw_events

Stores unprocessed events collected from RSS feeds, Telegram channels, and other OSINT sources.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key (auto-generated UUIDv4) |
| source_channel_id | INTEGER | Yes | FK to `source_channels.id` (SET NULL on delete) |
| source_type | VARCHAR(16) | No | Collection source type: `rss`, `telegram`, `api` |
| external_id | VARCHAR(256) | No | Source-specific unique identifier (e.g. RSS GUID, Telegram message ID) |
| raw_text | TEXT | No | Full original text of the event |
| raw_metadata | JSON | No | Source-specific metadata (e.g. `{"link": "https://..."}` for RSS) |
| lang | VARCHAR(8) | Yes | Detected language code (e.g. `en`, `ar`, `uk`) |
| collected_at | TIMESTAMPTZ | No | UTC timestamp when the event was collected |
| processed | BOOLEAN | No | Whether this event has been normalized (default: `false`) |

**Constraints:**
- `uq_raw_events_source_external` -- UNIQUE(source_type, external_id) prevents duplicate collection.

---

### normalized_events

Events after NLP processing: topic classification, severity scoring, geolocation extraction, and translation.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key (auto-generated UUIDv4) |
| raw_event_id | UUID | Yes | FK to `raw_events.id` (SET NULL on delete) |
| title | VARCHAR | No | English headline (max ~120 chars) |
| title_ko | VARCHAR | Yes | Korean translation of the title |
| body | TEXT | Yes | Full English body text |
| topic | VARCHAR(32) | No | Classified topic (see [Topics](#topics-11-types)) |
| entity_anchor | VARCHAR(256) | Yes | Primary entity (usually country_code or named entity) |
| lat | FLOAT | Yes | Latitude of the event location |
| lon | FLOAT | Yes | Longitude of the event location |
| geohash5 | VARCHAR(8) | Yes | 5-character geohash for spatial clustering |
| country_code | VARCHAR(4) | Yes | ISO 3166-1 alpha-2 country code |
| severity | SMALLINT | No | Severity score 0-100 (see [Severity Ranges](#severity-ranges)) |
| source_tier | VARCHAR(1) | No | Source reliability tier: `A`, `B`, `C`, or `D` |
| confidence | FLOAT | No | Confidence score 0.0-0.95 (derived from source_tier) |
| dedup_key | VARCHAR(64) | No | SHA-based hash for near-duplicate detection |
| is_duplicate | BOOLEAN | No | Whether this event is a detected duplicate (default: `false`) |
| translation_status | VARCHAR(16) | Yes | `ok`, `failed`, or `skipped` |
| geo_method | VARCHAR(16) | Yes | How geo was determined: `keyword`, `geocoder`, `fallback`, `none` |
| image_url | VARCHAR(1024) | Yes | Representative image URL from the source article |
| event_time | TIMESTAMPTZ | No | When the event actually occurred (from source) |
| created_at | TIMESTAMPTZ | No | Record creation timestamp |

---

### issue_clusters

Groups of related normalized_events, aggregated by topic + geohash + time window. The primary entity displayed on the map and in trending feeds.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key (auto-generated UUIDv4) |
| cluster_key | VARCHAR(512) | No | Unique clustering key: `{topic}:{geohash5}:{entity_anchor}` |
| geohash5 | VARCHAR(8) | No | 5-character geohash representing cluster centroid |
| topic | VARCHAR(32) | No | Dominant topic of the cluster |
| entity_anchor | VARCHAR(256) | Yes | Primary entity (country or named entity) |
| country_code | VARCHAR(4) | Yes | ISO 3166-1 alpha-2 country code |
| lat | FLOAT | Yes | Cluster centroid latitude |
| lon | FLOAT | Yes | Cluster centroid longitude |
| title | VARCHAR | No | Representative English headline |
| title_ko | VARCHAR | Yes | Korean translation |
| event_count | INTEGER | No | Number of normalized_events in this cluster |
| severity | SMALLINT | No | Maximum severity among member events (0-100) |
| confidence | FLOAT | No | Weighted confidence score |
| kscore | FLOAT | No | KScore value 0-10 (see [KScore Formula](#kscore-formula)) |
| is_spike | BOOLEAN | No | Whether a spike was detected (sudden event surge) |
| spike_at | TIMESTAMPTZ | Yes | When the spike was detected |
| source_tiers | TEXT[] | No | Array of distinct source tiers (e.g. `["A","B","C"]`) |
| independent_sources | INTEGER | No | Count of distinct source_channels contributing events |
| first_event_at | TIMESTAMPTZ | No | Earliest event_time in the cluster |
| last_event_at | TIMESTAMPTZ | No | Latest event_time in the cluster |
| window_start | TIMESTAMPTZ | No | Clustering time window start |
| window_end | TIMESTAMPTZ | No | Clustering time window end |
| image_url | VARCHAR(1024) | Yes | Representative image URL |
| is_verified | BOOLEAN | No | Admin-verified cluster (default: `false`) |
| is_active | BOOLEAN | No | Whether displayed on map (default: `true`; set to `false` for noise) |
| is_flagged | BOOLEAN | No | Flagged for admin review (default: `false`) |
| created_at | TIMESTAMPTZ | No | Record creation timestamp |
| updated_at | TIMESTAMPTZ | No | Last update timestamp |

**Indexes:**
- `ix_clusters_country_severity` -- (country_code, severity)
- `ix_clusters_topic_last_event` -- (topic, last_event_at)
- `ix_clusters_country_last_event` -- (country_code, last_event_at)

---

### cluster_events

Join table linking issue_clusters to normalized_events (many-to-many).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| cluster_id | UUID | No | FK to `issue_clusters.id` (CASCADE on delete) |
| event_id | UUID | No | FK to `normalized_events.id` (CASCADE on delete) |

**Primary Key:** (cluster_id, event_id)

---

### trending_keywords (KScore)

Periodically computed trending issues ranked by KScore. Calculated every 5 minutes by the worker, with 90-day history retention for Pro+ users.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Auto-increment primary key |
| keyword | VARCHAR(256) | No | English headline (from cluster title) |
| keyword_ko | VARCHAR(256) | Yes | Korean translation |
| normalized_kw | VARCHAR(256) | No | Lowercased keyword for deduplication |
| kscore | FLOAT | No | KScore after time decay (0-10 scale) |
| raw_score | FLOAT | No | KScore before time decay (0-10 scale) |
| topic | VARCHAR(32) | Yes | Topic of the source cluster |
| country_codes | TEXT[] | No | Array of related country codes |
| cluster_ids | UUID[] | No | Array of source cluster UUIDs |
| event_count | INTEGER | No | Number of events in the source cluster |
| severity | INTEGER | No | Severity of the source cluster (0-100) |
| is_spike | BOOLEAN | No | Whether the source cluster has a spike |
| scope | VARCHAR(64) | No | Scope identifier: `global` or user-specific |
| calculated_at | TIMESTAMPTZ | No | When this KScore was computed |
| valid_until | TIMESTAMPTZ | No | Expiration timestamp for this entry |

**Index:**
- `ix_trending_kw_scope_nkw_calcat` -- (scope, normalized_kw, calculated_at) for efficient latest-per-keyword queries.

**Retention policy:**
- Records older than 90 days are deleted.
- Records older than 7 days are deduplicated to 1 per hour (per keyword) to prevent database bloat.

---

### tension_index

Time-series table storing per-country tension levels. Computed every 5 minutes by the worker.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| time | TIMESTAMPTZ | No | PK -- Timestamp of computation |
| country_code | VARCHAR(4) | No | PK -- ISO 3166-1 alpha-2 country code |
| region_code | VARCHAR(16) | Yes | Sub-national region (reserved for future use) |
| raw_score | FLOAT | No | Composite tension score (0-100) |
| tension_level | SMALLINT | No | Discrete level 0-4 (see [Tension Levels](#tension-levels)) |
| event_score | FLOAT | Yes | Log-scaled cumulative severity score component |
| accel_score | FLOAT | Yes | Volume + acceleration score component |
| spillover_score | FLOAT | Yes | Neighbor country spillover component |
| percentile_30d | FLOAT | Yes | Percentile rank within 30-day history (0-100) |
| convergence_bonus | FLOAT | Yes | Multi-topic convergence bonus |
| anomaly_z | FLOAT | Yes | Z-score anomaly detection value |

**Primary Key:** (time, country_code)

**Tension formula:**
```
Raw = 0.55 * EventScore + 0.35 * ActivityScore + 0.10 * Spillover
```

---

### spike_events

Records detected spike events -- sudden surges in event volume for a cluster.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key (auto-generated UUIDv4) |
| cluster_id | UUID | No | FK to `issue_clusters.id` (CASCADE on delete) |
| severity | SMALLINT | No | Severity at the time of spike detection |
| kscore | FLOAT | No | KScore at the time of spike detection |
| c1 | INTEGER | No | Event count in the last 1 minute |
| c10 | INTEGER | No | Event count in the last 10 minutes |
| baseline | FLOAT | No | Historical baseline event rate |
| ratio | FLOAT | No | c1/baseline ratio (spike magnitude) |
| unique_sources | INTEGER | No | Number of distinct sources during the spike |
| triggered_at | TIMESTAMPTZ | No | When the spike was detected |

---

### source_channels

Registry of OSINT data sources (RSS feeds, Telegram channels, API endpoints).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Auto-increment primary key |
| channel_id | BIGINT | Yes | Telegram channel numeric ID (unique) |
| username | VARCHAR(128) | Yes | Telegram channel username (for URL generation) |
| display_name | VARCHAR(256) | No | Human-readable source name |
| tier | VARCHAR(1) | No | Reliability tier: `A`, `B`, `C`, or `D` |
| base_confidence | FLOAT | No | Default confidence score for this source |
| language | VARCHAR(8) | Yes | Primary language (default: `en`) |
| topics | TEXT[] | No | Array of topics this source covers |
| geo_focus | TEXT[] | No | Array of country codes this source focuses on |
| source_type | VARCHAR(16) | No | `telegram`, `rss`, or `api` |
| feed_url | VARCHAR | Yes | RSS feed URL (for rss type) |
| api_endpoint | VARCHAR | Yes | API endpoint URL (for api type) |
| api_params | JSON | Yes | API-specific parameters |
| last_fetch_cursor | VARCHAR | Yes | Pagination cursor for incremental fetching |
| is_active | BOOLEAN | No | Whether this source is actively collected |
| created_at | TIMESTAMPTZ | No | Record creation timestamp |
| updated_at | TIMESTAMPTZ | No | Last update timestamp |

**Constraint:** `ck_source_channels_tier` -- tier IN ('A','B','C','D')

---

### cluster_change_logs

Audit trail for administrative or system changes to clusters (corrections, reclassifications).

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Auto-increment primary key |
| cluster_id | UUID | No | FK to `issue_clusters.id` (CASCADE on delete) |
| field | VARCHAR(32) | No | Changed field: `title`, `severity`, `title_ko`, `topic` |
| old_value | VARCHAR | Yes | Previous value |
| new_value | VARCHAR | Yes | New value |
| reason | VARCHAR(256) | No | Reason: `admin_edit`, `reprocess`, `system` |
| updated_by | VARCHAR(64) | No | Actor: `admin`, `system` |
| created_at | TIMESTAMPTZ | No | When the change was made |

---

### notifications

Push notification records sent to users.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | INTEGER | No | Auto-increment primary key |
| user_id | UUID | No | FK to `users.id` (CASCADE on delete) |
| type | VARCHAR(16) | No | Notification type: `verified`, `spike` |
| cluster_id | UUID | Yes | FK to `issue_clusters.id` (SET NULL on delete) |
| title | VARCHAR(256) | No | Notification title |
| body | VARCHAR(512) | No | Notification body |
| is_read | BOOLEAN | No | Whether the user has read this notification |
| feedback | VARCHAR(16) | Yes | User feedback: `thumbs_up`, `thumbs_down` |
| created_at | TIMESTAMPTZ | No | Timestamp |

---

### social_posts

Auto-generated social media post drafts based on trending clusters.

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| id | UUID | No | Primary key |
| content_type | VARCHAR(32) | No | Post type (e.g. `breaking`, `analysis`) |
| lang | VARCHAR(4) | No | Language code |
| body_text | TEXT | No | Post body content |
| hashtags | TEXT[] | No | Array of hashtags |
| image_url | VARCHAR(1024) | Yes | Attached image URL |
| risk_level | VARCHAR(8) | No | Content risk: `low`, `medium`, `high` |
| source_cluster_id | UUID | Yes | FK to `issue_clusters.id` |
| source_spike_id | UUID | Yes | FK to `spike_events.id` |
| dedup_key | VARCHAR(128) | No | Unique key to prevent duplicate posts |
| status | VARCHAR(16) | No | `pending_review`, `approved`, `published`, `rejected` |
| created_at | TIMESTAMPTZ | No | Creation timestamp |
| approved_at | TIMESTAMPTZ | Yes | Admin approval timestamp |
| approved_by | VARCHAR(64) | Yes | Approving admin identifier |
| published_at | TIMESTAMPTZ | Yes | Actual publication timestamp |

---

## API Response Schemas

### GET /issues (List Clusters)

Returns active issue clusters for map display. 48-hour rolling window, filtered by severity.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| bbox | string | null | Bounding box: `min_lon,min_lat,max_lon,max_lat` |
| topic | string | null | Filter by topic |
| country_code | string | null | Filter by country (e.g. `US`, `KR`) |
| severity_min | int | 1 | Minimum severity (0-100) |
| limit | int | 2000 | Max results (1-5000) |
| sort_by | string | null | Sort: `kscore`, `severity`, or `latest` (default: latest) |

**Response:** `ClusterOut[]`

```json
{
  "id": "uuid",
  "cluster_key": "conflict:w21zg:UA",
  "topic": "conflict",
  "title": "Russian missile strikes on Kyiv",
  "title_ko": "[분쟁] 러시아, 키이우에 미사일 공격",
  "lat": 50.45,
  "lon": 30.52,
  "country_code": "UA",
  "severity": 75,
  "confidence": 0.85,
  "event_count": 12,
  "is_spike": false,
  "is_verified": true,
  "kscore": 6.42,
  "independent_sources": 5,
  "source_tiers": ["A", "B", "C"],
  "image_url": "https://...",
  "first_event_at": "2026-03-09T10:00:00+00:00",
  "last_event_at": "2026-03-09T14:30:00+00:00"
}
```

---

### GET /issues/{cluster_id} (Cluster Detail)

Returns a cluster with its event timeline and change logs.

**Response:** `ClusterDetailOut` (extends `ClusterOut`)

```json
{
  "...all ClusterOut fields...",
  "events": [
    {
      "id": "uuid",
      "title": "Ukraine reports missile strikes on Kyiv infrastructure",
      "title_ko": "우크라이나, 키이우 인프라 미사일 공격 보고",
      "body": "Full text...",
      "topic": "conflict",
      "severity": 75,
      "confidence": 0.85,
      "source_tier": "A",
      "source_name": "Reuters",
      "source_url": "https://reuters.com/...",
      "event_time": "2026-03-09T12:00:00+00:00",
      "country_code": "UA",
      "entity_anchor": "UA"
    }
  ],
  "change_logs": [
    {
      "field": "severity",
      "old_value": "60",
      "new_value": "75",
      "reason": "admin_edit",
      "updated_by": "admin",
      "created_at": "2026-03-09T15:00:00+00:00"
    }
  ]
}
```

---

### GET /trending/global (Global Trending)

Returns the top 30 trending issues worldwide, ranked by KScore. Cached for 5 minutes.

**Response:** `TrendingItem[]`

```json
{
  "id": 1234,
  "keyword": "Russian missile strikes on Kyiv",
  "keyword_ko": "[분쟁] 러시아, 키이우에 미사일 공격",
  "kscore": 7.25,
  "raw_score": 8.10,
  "topic": "conflict",
  "country_codes": ["UA"],
  "cluster_ids": ["uuid"],
  "scope": "global",
  "calculated_at": "2026-03-09T14:00:00+00:00",
  "first_event_at": "2026-03-09T10:00:00+00:00",
  "is_spike": false,
  "event_count": 15,
  "severity": 75,
  "reason": "5개 독립출처 동시 보도 (KScore 7.3)",
  "independent_sources": 5,
  "kscore_delta_24h": 2.1
}
```

---

### GET /trending/mine (My Trending)

Same schema as `/trending/global` but filtered by user's watched countries.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| countries | string | null | Comma-separated country codes (e.g. `UA,PS,IL`) |

---

### GET /trending/kscore-history/{cluster_id}

KScore time-series history for a specific cluster.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| days | int | 7 | History range (Free: 7d, Pro: 30d, Pro+: 90d) |

**Response:** `KScoreHistoryPoint[]`

```json
{
  "time": "2026-03-09T12:00:00+00:00",
  "kscore": 6.42
}
```

---

### GET /tension/mine (My Tension)

Returns tension index for watched countries with top-5 contributing clusters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| countries | string | null | Comma-separated country codes |

**Response:** `TensionOut[]`

```json
{
  "country_code": "UA",
  "raw_score": 72.5,
  "tension_level": 3,
  "tension_label": "심각",
  "percentile_30d": 85.2,
  "event_score": 65.0,
  "accel_score": 40.0,
  "spillover_score": 12.0,
  "convergence_bonus": 3.5,
  "anomaly_z": 1.8,
  "delta_24h": 5.3,
  "updated_at": "2026-03-09T14:00:00+00:00",
  "top5_clusters": [
    {
      "id": "uuid",
      "title": "...",
      "title_ko": "...",
      "severity": 75,
      "confidence": 0.85,
      "topic": "conflict",
      "kscore": 6.42,
      "event_count": 12,
      "image_url": "https://...",
      "country_code": "UA"
    }
  ]
}
```

---

### GET /tension/country/{country_code}

Single country's latest tension data. Same `TensionOut` schema.

---

### GET /tension/country/{country_code}/history

Tension time-series for a specific country.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| range | string | `7d` | `7d` (Free), `30d` (Pro), `90d` (Pro+) |

**Response:** `TensionHistoryPoint[]`

```json
{
  "time": "2026-03-09T12:00:00+00:00",
  "raw_score": 72.5,
  "tension_level": 3,
  "percentile_30d": 85.2
}
```

---

### GET /tension/all

All countries' latest tension levels (for choropleth heatmap). Cached for 5 minutes.

**Response:** `TensionAllItem[]`

```json
{
  "country_code": "UA",
  "raw_score": 72.5,
  "tension_level": 3
}
```

---

## Enums & Constants

### Topics (11 types)

| Topic | Base Severity | Description |
|-------|--------------|-------------|
| `conflict` | 60 | Armed conflict, military operations, airstrikes, artillery, casualties |
| `terror` | 60 | Terrorism, hostage situations, mass shootings, organized crime |
| `coup` | 65 | Coups, military takeovers, martial law, constitutional crises |
| `sanctions` | 45 | Economic sanctions, embargoes, trade wars, financial crises |
| `cyber` | 40 | Cyberattacks, data breaches, internet shutdowns, information warfare |
| `protest` | 35 | Protests, demonstrations, riots, civil unrest, crackdowns |
| `diplomacy` | 30 | Diplomatic events, treaties, elections, political crises |
| `maritime` | 50 | Naval incidents, piracy, migrant crossings, shipping disruptions |
| `disaster` | 50 | Natural disasters, industrial accidents, humanitarian crises |
| `health` | 40 | Disease outbreaks, epidemics, public health emergencies |
| `unknown` | 20 | Unclassified events (filtered out if severity <= 20) |

---

### Severity Ranges

Severity is scored on a 0-100 scale, computed as:

```
severity = base(topic) + keyword_modifier + casualty_bonus + IA_modifier
```

| Range | Label | Typical Events |
|-------|-------|----------------|
| 0-20 | Minimal | Unclassified, routine diplomatic statements |
| 20-40 | Low | Minor protests, diplomatic tensions, small-scale cyber incidents |
| 40-60 | Moderate | Significant protests, sanctions, armed skirmishes |
| 60-80 | High | Major military operations, terror attacks, coups |
| 80-100 | Critical | Mass casualties, WMD use, genocide, full-scale war |

**Modifiers:**
- **Keyword modifiers** (SEVERITY_UP / SEVERITY_DOWN): Add/subtract up to +/-40 based on specific keywords (e.g. "massacre" +15, "unconfirmed" -10).
- **Casualty bonus**: Additional +5 to +30 based on reported casualty numbers.
- **Information Accessibility (IA)**: Multiplier based on RSF Press Freedom Index. Restricted-press countries (e.g. North Korea x1.27) receive a severity boost to compensate for under-reporting.

---

### Source Tiers

| Tier | Base Confidence | Description |
|------|----------------|-------------|
| `A` | 0.85 | Major wire services (Reuters, AP, AFP), official government sources |
| `B` | 0.70 | Established regional outlets, verified OSINT accounts |
| `C` | 0.55 | Local media, social media aggregators |
| `D` | 0.35 | Unverified sources, raw Telegram channels |

---

### KScore Formula

KScore is a composite trending relevance score on a 0-10 scale, updated every 5 minutes.

```
raw = 0.30 * velocity + 0.10 * quality + 0.30 * severity + 0.30 * spread
KScore = raw * 10 * decay
```

**Components (all normalized to 0-1):**

| Component | Weight | Formula |
|-----------|--------|---------|
| velocity | 30% | `min(6.0, event_count^0.7 * spike_factor) / 6.0` |
| quality | 10% | `min(1.0, confidence + tier_bonus)` |
| severity | 30% | `severity / 100` |
| spread | 30% | `min(1.0, independent_sources / 12)` |

**Time decay:**
```
decay = max(0.30, exp(-0.025 * age_hours))
```
- Half-life: ~28 hours
- Floor: 30% (even after 48 hours, 30% of the score is retained)

**UI Thresholds:**

| KScore Range | Level | Label |
|-------------|-------|-------|
| 0.0 - 1.9 | -- | Stable (filtered from trending if < 1.5) |
| 2.0 - 3.9 | 1 | Caution |
| 4.0 - 5.9 | 2 | Elevated |
| 6.0 - 7.9 | 3 | Severe |
| 8.0 - 10.0 | 4 | Critical |

---

### Tension Levels

Country-level tension is computed from cluster activity within that country. Stored as `tension_level` (0-4) derived from `raw_score` (0-100).

**Formula:**
```
Raw = 0.55 * EventScore + 0.35 * ActivityScore + 0.10 * Spillover
```

| Level | Label | Raw Score Range |
|-------|-------|----------------|
| 0 | Stable | 0 - 20 |
| 1 | Caution | 20 - 40 |
| 2 | Elevated | 40 - 60 |
| 3 | Severe | 60 - 80 |
| 4 | Critical | 80 - 100 |

**Sub-components:**
- **EventScore**: Log-scaled cumulative (severity * confidence) of recent clusters.
- **ActivityScore**: 60% volume saturation + 40% acceleration (event count growth rate).
- **Spillover**: Maximum severity from neighbor-country clusters / 100.
- **Conflict Floor**: Active conflict zones have a minimum raw_score (e.g. Ukraine: 55, Palestine: 50) to prevent false "stable" readings during reporting gaps.

---

### User Plans

| Plan | Value | KScore History | Tension History |
|------|-------|---------------|----------------|
| `free` | Free | 7 days | 7 days |
| `pro` | Pro | 30 days | 30 days |
| `pro_plus` | Pro+ | 90 days | 90 days |

---

### Notification Types

| Type | Trigger | Description |
|------|---------|-------------|
| `verified` | Admin verifies a cluster in user's watched area | Confirmed-event alert |
| `spike` | Spike detected in user's watched area | Sudden event surge alert |

---

### User Roles

| Role | Permissions |
|------|------------|
| `user` | Standard access |
| `moderator` | Content moderation capabilities |
| `admin` | Full admin panel access, cluster editing, tension recalculation |

---

### Social Post Statuses

| Status | Description |
|--------|-------------|
| `pending_review` | Auto-generated, awaiting admin review |
| `approved` | Admin approved, ready for publication |
| `published` | Published to social platforms |
| `rejected` | Admin rejected |

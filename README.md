<p align="center">
  <img src="docs/images/logo-eye.png" alt="WeWantPeace" width="80" />
</p>

<h1 align="center">WeWantPeace</h1>

<p align="center">
  <strong>AI-powered real-time conflict & crisis monitoring platform</strong><br/>
  Track global tensions, receive instant alerts, and stay informed with data-driven insights.
</p>

<p align="center">
  <a href="https://www.wewantpeace.live">Live Demo</a> &middot;
  <a href="./METHODOLOGY.md">Methodology</a> &middot;
  <a href="./DATA_DICTIONARY.md">Data Dictionary</a> &middot;
  <a href="./README.ko.md">한국어</a>
</p>

---

## Screenshots

### Desktop — Today's Issues

![Home](docs/images/01-home-desktop.png)

Real-time issue feed with **RISING NOW** cards, KScore ticker, severity/speed/spread indicators, and live update status.

### Issue Detail — Event Timeline

![Issue Detail](docs/images/02-issue-detail.png)

Deep dive into each issue cluster: severity score, confidence level, event count, source verification badges, KScore bar, and a chronological event timeline with original sources.

### Tension Index — Country Risk Scores

![Tension Index](docs/images/03-tension-desktop.png)

Country-level tension scoring with breakdown (Events, Acceleration, Spillover), 30-day trend comparison, and Top Causes ranked by KScore.

### Country Issues — Israel

![Country Issues](docs/images/04-country-issues.png)

Per-country view with tension trend chart (7-day history), severity-coded issue cards, and live event counts.

### Mobile Views

<p align="center">
  <img src="docs/images/05-mobile-home.png" alt="Mobile Home" width="280" />
  &nbsp;&nbsp;
  <img src="docs/images/06-mobile-tension.png" alt="Mobile Tension" width="280" />
</p>

Fully responsive PWA — works on any device, installable as a native app on Android and iOS.

---

## Key Features

- **Real-time Issue Tracking** — Collects from 100+ RSS feeds, Telegram channels, and APIs every 5 minutes
- **AI Classification** — Automatic topic categorization, severity scoring, and country detection using OpenAI
- **KScore (Key Impact Score)** — Proprietary 0-10 composite metric measuring Speed, Severity, and Spread
- **Tension Index** — Country-level risk scores with daily trend tracking and acceleration detection
- **KScore-based Real-time Alerts** — Automatic identification of rapidly escalating events with instant push notifications
- **Interactive Conflict Map** — MapLibre GL-based visualization with cluster markers and pulse animations
- **Push Notifications** — FCM-based alerts filtered by your countries, topics, and severity thresholds
- **Community Forum** — Discussion board for analysis, questions, and debate
- **Bilingual** — Full Korean/English support (1,600+ translation keys)
- **Admin Dashboard** — Complete control panel for events, clusters, sources, users, and pipeline health

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  RSS Feeds  │     │  Telegram   │     │  USGS / APIs │
│  (100+)     │     │  Channels   │     │              │
└──────┬──────┘     └──────┬──────┘     └──────┬───────┘
       │                   │                    │
       └───────────┬───────┘────────────────────┘
                   ▼
         ┌─────────────────┐
         │   Celery Worker  │  ← collect queue (5-min cycle)
         │                  │
         │  normalize →     │
         │  deduplicate →   │
         │  cluster →       │
         │  KScore alerts → │
         │  tension calc →  │
         │  trending →      │
         │  push alerts     │
         └────────┬─────────┘
                  │
         ┌────────▼─────────┐
         │   PostgreSQL      │  (Supabase)
         │   + Redis         │
         └────────┬─────────┘
                  │
         ┌────────▼─────────┐     ┌──────────────────┐
         │  FastAPI Backend  │────▶│  Next.js Frontend │
         │  (REST API)       │     │  (PWA)            │
         └──────────────────┘     └──────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Next.js 14, React 18, Tailwind CSS, MapLibre GL, Zustand, TanStack Query, Firebase Auth |
| **Backend** | FastAPI, SQLAlchemy 2.0 (async), Celery, Redis |
| **Database** | PostgreSQL 15 (Supabase) |
| **Worker** | Celery Beat + Worker (separate collect/process queues) |
| **Collection** | RSS/feedparser, Telegram (Telethon), OpenAI API (classification/translation) |
| **Mobile** | Android TWA + Expo React Native (Google Play) |
| **Deployment** | Railway.app, GitHub Actions CI/CD |

## Data Pipeline

```
RSS/Telegram Collection → Normalization (topic/severity/geo) → Deduplication → Clustering
    → KScore Alerts → Trending Calculation → Tension Index → Push Notifications
```

| Metric | Current |
|--------|---------|
| Data Sources | 58+ (RSS 37+ / Telegram 12 / API 3) |
| Countries Monitored | 69 (expanding to 120+) |
| Refresh Interval | Every 5 minutes |
| KScore Range | 0–10 (personalized by user's tracked countries) |

## Project Structure

```
wewantpeace/
├── backend/
│   ├── app/
│   │   ├── routers/        # API endpoints (issues, tension, trending, community, auth, admin)
│   │   ├── models/         # SQLAlchemy models (22 tables)
│   │   ├── services/       # Payment processing (Google Play / Apple StoreKit)
│   │   └── core/           # config, database, auth, redis, firebase
│   ├── alembic/            # DB migrations (37+)
│   └── tests/              # pytest tests (173+ passing)
├── worker/
│   ├── collector/          # RSS & Telegram collectors
│   ├── processor/          # normalizer, clusterer, deduplicator, alert engine, tension calculator
│   └── push/               # FCM push notification service
├── frontend/
│   ├── app/(main)/         # User pages (home, map, tension, community, settings)
│   ├── app/admin/          # Admin dashboard (14 sections)
│   ├── components/         # Shared UI components
│   └── lib/                # api, auth, i18n (1,600+ keys), store, fcm
├── scripts/                # Maintenance scripts (reprocess, seed, retitle)
├── infra/                  # Docker configs (backend, frontend, worker)
└── .github/workflows/      # CI tests + Railway deployment
```

## Quick Start

```bash
# 1. Environment variables
cp .env.example .env
# Set DATABASE_URL, REDIS_URL, TELEGRAM_BOT_TOKEN, SECRET_KEY, etc.

# 2. Start infrastructure with Docker
cd infra && docker-compose up -d

# 3. Run DB migrations
DATABASE_URL=postgresql+asyncpg://wwp:wwplocal@localhost/wewantpeace \
  python -m alembic -c backend/alembic.ini upgrade head

# 4. Start frontend
cd frontend && npm install && npm run dev

# 5. Start worker (separate terminal)
celery -A worker.celery_app worker --beat --loglevel=info -Q collect,process -c 2
```

## API

- **Swagger UI**: http://localhost:8000/docs (when `DEBUG=true`)
- **Health check**: `GET /health`
- **Public API**: `GET /api/v1/issues`, `GET /api/v1/tension` — [API Docs](https://www.wewantpeace.live/api-docs)

## Testing

```bash
bash scripts/run_tests.sh           # Full suite (173+ passing)
bash scripts/run_tests.sh -u        # Unit tests only
bash scripts/run_tests.sh -c        # With coverage report
```

## Deployment

- **Railway.app**: 3 services (backend, worker, frontend)
- **CI/CD**: Push to `main` → GitHub Actions → Railway GraphQL API deployment
- **Database**: Supabase PostgreSQL (ap-northeast-2)
- **Domains**: `www.wewantpeace.live` (frontend), `api.wewantpeace.live` (backend)

## Methodology

Our algorithms are fully documented in [METHODOLOGY.md](./METHODOLOGY.md), covering:
- KScore calculation (Speed, Severity, Spread composite)
- Tension Index formula (Events, Acceleration, Spillover)
- KScore-based alert thresholds and alerting logic
- Data quality scoring and source grading

## Contributing

We welcome contributions! Please see our data dictionary and methodology docs for context on how the system works.

## License

[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) — Creative Commons Attribution-NonCommercial 4.0 International

Copyright (c) 2026 WeWantPeace

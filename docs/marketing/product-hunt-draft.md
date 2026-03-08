# Product Hunt Launch Draft

## Tagline (60 chars max)
> See every conflict on Earth, scored for your country.

## Subtitle (200 chars max)
> WeWantPeace monitors 195 countries in real-time, using AI to score how each crisis impacts you. Track tensions, get spike alerts, and explore an interactive conflict map -- all from one dashboard.

## Description (500 chars)

Every 5 minutes, WeWantPeace scans hundreds of RSS feeds and Telegram channels for conflict and security events worldwide. Our AI pipeline classifies each event, assigns severity, and clusters related reports into issues.

**KScore** (0-10) tells you how much an issue matters from your country's perspective, factoring in geography, security alliances, and economic ties. The **Tension Index** (0-100) tracks each nation's risk level over time.

Get push notifications when a spike is detected. Explore crises on an interactive global map. Free tier included -- no signup wall for core features.

Built with Next.js, FastAPI, Celery, PostgreSQL, and GPT-4o-mini.

## Recommended Categories
- Artificial Intelligence
- Data Visualization
- World News / Geopolitics
- Developer Tools (open data pipeline angle)

## Suggested First Comment

> Hey PH! I built WeWantPeace because I was frustrated by how hard it is to get a clear, real-time picture of global security.
>
> Most conflict trackers are either academic (updated monthly) or paywalled. I wanted something that refreshes every 5 minutes, scores events for *my* country, and sends me a push when something spikes.
>
> The tech: ~200 RSS feeds + Telegram channels -> FastAPI worker pipeline -> GPT-4o-mini classification -> PostgreSQL + TimescaleDB -> Next.js frontend. All deployed on Railway.
>
> KScore is the feature I'm most proud of: it personalizes every issue's importance based on your home country's geographic, security, and economic relationships.
>
> Free tier is fully functional. Pro unlocks the interactive map, more watched countries, and extended history.
>
> Would love your feedback -- especially on what metrics or regions you'd want to see next.

## Maker Info
- Website: https://www.wewantpeace.live
- Twitter/X: @wewantpeace_

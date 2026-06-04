# r/dataisbeautiful Post Draft

## Title
[OC] I built a real-time dashboard that monitors conflicts across 195 countries and visualizes each nation's Tension Index

## Body

I've been collecting global conflict and security event data for the past several months and built a visualization platform around it.

**Live dashboard:** https://www.wewantpeace.live

**What you're looking at:**
- An interactive world map where each country is colored by its Tension Index (0-100 scale)
- A trending issues feed ranked by KScore (Key Impact Score), showing the most impactful global crises right now
- Per-country tension history charts showing how risk levels evolve over days and weeks

**Data sources:**
- ~200 international RSS feeds (wire services, regional news, defense/security outlets)
- Telegram channels covering conflict zones
- Events collected every 3-5 minutes, 24/7

**Tools:**
- Collection & processing: Python (FastAPI, Celery), GPT-4o-mini for event classification
- Database: PostgreSQL + TimescaleDB
- Visualization: Next.js 14, React, Tailwind CSS, custom map rendering
- Infrastructure: Railway (Docker)

**Methodology:**
- Each news event is classified into topics (conflict, terrorism, coup, sanctions, cyber, protest, diplomacy, maritime, disaster, health)
- Severity is scored 0-100 based on keyword analysis (armed conflict, casualties, nuclear threats, etc.)
- The Tension Index per country combines event severity (55%), activity volume/acceleration (35%), and spillover from neighboring countries (10%)
- KScore (0-10) personalizes issue impact based on your home country's geographic, security, and economic ties

**Some insights from the data:**
- Tension levels spike sharply during breaking events but decay follows a predictable exponential curve
- Countries with active conflicts maintain sustained high tension, but the *acceleration* metric is what distinguishes a new escalation from baseline violence
- Spillover effects from neighboring conflicts are measurable and often precede diplomatic responses by 24-48 hours
- Source spread (number of independent outlets reporting) correlates strongly with event significance -- single-source events are 3x more likely to be noise

This is an ongoing project. Feedback on the visualization, methodology, or coverage gaps is very welcome.

---

## First Comment (mandatory for r/dataisbeautiful)

**Source:** ~200 international RSS news feeds and Telegram channels, collected every 3-5 minutes using a Celery worker pipeline.

**Tools:** Python (FastAPI, Celery, SQLAlchemy), GPT-4o-mini for NLP classification, PostgreSQL + TimescaleDB for storage, Next.js 14 + React + Tailwind CSS for the frontend visualization. Deployed on Railway.

**Methodology notes:** Tension Index = 0.55 * EventScore + 0.35 * ActivityScore + 0.10 * Spillover. EventScore uses log-scaled severity*confidence sums. ActivityScore combines volume (60%) and acceleration (40%). All scores updated every 5 minutes.

Live at https://www.wewantpeace.live -- feedback welcome.

# X (Twitter) #buildinpublic Thread

---

## Tweet 1 (Hook)
I built a real-time conflict monitor that covers 195 countries.

It scans 200+ news sources every 5 minutes, scores each crisis by how much it impacts YOUR country, and sends you a push when something spikes.

It's called WeWantPeace. Here's the story.

https://www.wewantpeace.live

## Tweet 2 (Problem)
The problem: getting a clear picture of global security in real-time is stupidly hard.

Academic datasets update monthly. News is fragmented. Risk platforms cost $$$$.

I wanted one dashboard that answers: "What's happening right now, and how much should I care?"

## Tweet 3 (How it works)
How it works:

1. ~200 RSS feeds + Telegram channels polled every 3-5 min
2. GPT-4o-mini classifies each event (topic, severity, location)
3. Events are clustered into issues
4. KScore (0-10) = personalized impact for your country
5. Tension Index (0-100) = per-country risk level

## Tweet 4 (KScore -- the differentiator)
KScore is the feature I'm most proud of.

Same event, different score depending on where you live.

It factors in:
- Geographic proximity
- Security alliances
- Economic ties

A missile test in the Pacific scores 8.5 for Seoul, 3.2 for Berlin.

Because the real impact IS different.

## Tweet 5 (Tech stack)
Tech stack for the curious:

- Frontend: Next.js 14 + TypeScript + Tailwind
- Backend: FastAPI + SQLAlchemy (async)
- Workers: Celery + Redis
- DB: PostgreSQL (Supabase) + TimescaleDB
- AI: GPT-4o-mini
- Push: Firebase Cloud Messaging
- Infra: Railway
- CI/CD: GitHub Actions

## Tweet 6 (Traction / what's next)
Current status:
- Monitoring 195 countries 24/7
- Bilingual (Korean/English)
- PWA + Android TWA
- Free tier fully functional
- Auto-posting to X, Threads, Instagram

Next up: more data sources, historical analysis, and an API for researchers.

## Tweet 7 (CTA)
If you work in security, journalism, geopolitics, or just want to understand the world better -- try it out.

Free. No signup wall for core features.

https://www.wewantpeace.live

Feedback, ideas, and roasts all welcome.

#buildinpublic #geopolitics #AI #security #indiehacker

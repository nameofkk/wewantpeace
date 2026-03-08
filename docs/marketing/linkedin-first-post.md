# LinkedIn First Post -- Founder Personal Account

---

I spent the last few months building something I couldn't find anywhere else.

Every day, hundreds of conflict and security events unfold around the world. But unless you're a SIGINT analyst or paying thousands for a Bloomberg terminal, getting a clear, real-time picture of global risk is surprisingly hard.

Academic datasets like ACLED update monthly. News aggregators give you headlines but no structure. Government advisories lag behind reality.

So I built WeWantPeace -- a real-time monitoring platform that covers 195 countries.

Here's what it does:
- Scans ~200 news feeds and Telegram channels every 3-5 minutes
- Uses AI to classify events (conflict, terrorism, coups, sanctions, cyber attacks...)
- Calculates a Tension Index (0-100) for every country, updated every 5 minutes
- Scores each issue with KScore -- a personalized metric that tells you how much a crisis matters *from your country's perspective*
- Sends push alerts when a spike is detected

The hardest part wasn't the tech. It was designing a scoring system that's both transparent and genuinely useful. KScore factors in geographic proximity, security alliances, and economic interdependence. The same event in the Middle East scores differently for someone in Seoul vs. someone in Berlin -- because the real-world impact IS different.

The tech stack: Next.js, FastAPI, Celery, PostgreSQL, GPT-4o-mini, deployed on Railway.

Free to use. No paywall for core features.

If you work in geopolitics, security, journalism, or just want to understand the world a little better -- I'd love your feedback.

https://www.wewantpeace.live

#buildinpublic #geopolitics #security #AI #startup #sideproject

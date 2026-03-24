# WeWantPeace Newsletter — Handlebars Template Schema

> **Template files:** `newsletter-v1-final-en.html` (EN) · `newsletter-v1-final-ko.html` (KO)
> **Total variables:** 55 (37 text + 18 HTML blocks) — identical in both templates
> **Last updated:** 2026-03-24 (R659)

---

## Text Variables (`{{variable}}`)

| # | Variable | Type | Example | Description |
|---|----------|------|---------|-------------|
| 1 | `vol_number` | int | `1` | Issue volume number. Used in title, banner, editor's note |
| 2 | `preheader_text` | string | `23 countries in crisis — Hormuz blocked, oil $127...` | Gmail/Apple Mail preview text (max ~120 chars) |
| 3 | `issue_date_short` | string | `Mar 23, Sun` | Header date, abbreviated |
| 4 | `hero_image_url` | url | `https://...strait-of-hormuz-1920.jpg` | Hero banner background image (1200x630 recommended) |
| 5 | `issue_date` | string | `2026.03.23` | Full date in YYYY.MM.DD format |
| 6 | `crisis_countries_count` | int | `23` | Hero big number — countries with tension ≥ 50 |
| 7 | `crisis_prev` | int | `18` | Previous week's crisis country count |
| 8 | `crisis_current` | int | `23` | Current week's crisis country count |
| 9 | `crisis_trend` | string | `3 weeks rising` | Trend description |
| 10 | `events_24h` | int | `854` | Events detected in last 24 hours |
| 11 | `events_7d` | string | `11,861` | Total events in 7 days (comma-formatted) |
| 12 | `key_stats_line` | string | `3 wars active · 491 conflicts · 23 countries ≥50` | One-liner stats summary |
| 13 | `issue_datetime` | string | `2026.3.23 Sun 09:00` | Issue publication timestamp |
| 14 | `issue_label` | string | `Inaugural` | Short label (Inaugural / Week 2 / etc.) |
| 15 | `issue_label_long` | string | `Inaugural issue` | Long label for "Today's Brief" section |
| 16 | `deep_dive_nav_label` | string | `Hormuz Deep Dive` | Section 04 navigation label (changes topic weekly) |
| 17 | `total_conflicts` | int | `491` | Total active conflicts tracked |
| 18 | `urgent_count` | int | `4` | Number of urgent stories featured |
| 19 | `active_issues_count` | int | `948` | Active issue count for "View all" CTA |
| 20 | `deep_dive_title` | string | `Strait of Hormuz — 72-Hour Timeline` | Section 04 main title |
| 21 | `country_name` | string | `South Korea` | Reader's country (personalized) |
| 22 | `country_rank` | int | `8` | Country's tension ranking (1-195) |
| 23 | `country_code` | string | `KR` | ISO 3166-1 alpha-2 code |
| 24 | `tension_level` | int | `3` | Tension level (1-5) |
| 25 | `tension_score` | float | `96.8` | Country's tension score (0-100) |
| 26 | `tension_level_text` | string | `Elevated Risk` | Level description text |
| 27 | `tension_change` | string | `▲ +12.4` | Weekly change with arrow |
| 28 | `prev_tension` | float | `84.4` | Previous week's tension score |
| 29 | `streak_text` | string | `Rising 3 weeks` | Streak description |
| 30 | `country_summary` | string | `Oil prices up 40%, export logistics disrupted...` | One-liner country impact summary |
| 31 | `next_vol_number` | int | `2` | Next issue volume number |
| 32 | `share_headline` | string | `The world looks different from 2 minutes ago.` | Share section headline |
| 33 | `share_subtext` | string | `Colleagues, investors, anyone who cares...` | Share section subtext |
| 34 | `mailto_subject` | string (url-encoded) | `WeWantPeace%20Weekly%20Brief%20...` | Email forward subject (pre-encoded) |
| 35 | `mailto_body` | string (url-encoded) | `The%20Strait%20of%20Hormuz%20...` | Email forward body (pre-encoded) |
| 36 | `pro_cta_subtext` | string | `You're reading this on Sunday.` | Pro section subtext |
| 37 | `unsubscribe_url` | url | `https://...unsubscribe?token=xxx` | Per-user unsubscribe link |

---

## HTML Block Variables (`{{{variable}}}`)

These use triple-brace syntax to render raw HTML without escaping.

| # | Variable | ~Lines | Example Content |
|---|----------|--------|-----------------|
| 1 | `hero_headline_html` | 3-5 | `Iran has <b>blocked</b> the Strait of Hormuz...` with styled spans |
| 2 | `todays_brief_items_html` | 20-30 | 3 `<tr>` rows with numbered headlines, tags, links |
| 3 | `tension_table_html` | 60-80 | Full TOP 10 table with flags, scores, ranks, changes |
| 4 | `tension_warning_html` | 1-3 | `<b>Warning:</b> All top 6 scored <span>100</span>...` |
| 5 | `conflict_stories_html` | 80-120 | 4 conflict story cards with images, tags, descriptions |
| 6 | `energy_section_intro_html` | 3-5 | Intro paragraph for energy section |
| 7 | `energy_section_html` | 60-80 | Breaking card + analysis rows + quote box |
| 8 | `deep_dive_section_html` | 80-120 | Image + timeline table + analysis paragraphs |
| 9 | `country_issues_html` | 20-40 | 3-4 issue cards for the reader's country |
| 10 | `country_impact_html` | 20-30 | Impact cards (oil, stocks, travel, etc.) |
| 11 | `did_you_know_html` | 3-5 | Fun fact with styled text |
| 12 | `travel_advisory_intro_html` | 3-5 | Intro paragraph with counts |
| 13 | `travel_advisory_html` | 30-50 | Level 4 + Level 3 country tables |
| 14 | `numbers_section_html` | 60-80 | 6 number cards + insight text + WoW table |
| 15 | `calendar_html` | 30-50 | D-Day calendar items for the week |
| 16 | `editors_note_html` | 15-25 | Editor's weekly note body paragraphs |
| 17 | `next_week_items_html` | 10-15 | 3 preview bullet items for next week |
| 18 | `pro_cta_headline_html` | 2-3 | Pro section headline with `<br>` and `<b>` |

---

## Static Content (Not Templatized)

These elements are intentional constants (localized per template):

| Element | EN Template | KO Template |
|---------|-------------|-------------|
| Section labels | `TENSION INDEX`, `CONFLICT`, etc. | Same English labels (brand identity) |
| Feedback buttons | Useful / OK / Not great | 유용했어요 / 보통 / 별로 |
| Pro features | 4 English items | 4 Korean items |
| Footer disclaimer | Not investment advice | 투자 조언 아님 |
| Subscribe CTA | Subscribe → | 다음 호 받기 → |
| Reading badge | 2 min read | 2분 소요 |
| Tension footnote | density + acceleration + spillover | 밀도 + 가속도 + 파급효과 |
| Share buttons | Email forward only | KakaoTalk + Email forward |
| UTM structure | `utm_source=nl&utm_medium=em&utm_campaign=v1` | Same |

---

## Usage Notes

1. **URL-encoded values:** `mailto_subject` and `mailto_body` must be pre-encoded for `mailto:` links
2. **HTML blocks:** Use triple-brace `{{{var}}}` — these bypass HTML escaping
3. **Country personalization:** Variables 21-30 change per recipient based on their country setting
4. **Hero image:** Use a high-quality 1200x630px news photo related to the week's top story
5. **Gmail 102KB limit:** After variable injection, total HTML must stay under 102KB to avoid clipping
6. **Language selection:** Use `--template newsletter-v1-final-ko.html` for Korean, default is EN

---

## Rendering Commands

```bash
# EN — US personalization
python render-newsletter.py --data vol1-us-sample.json --output newsletter-v1-rendered-us.html

# KO — KR personalization
python render-newsletter.py --template newsletter-v1-final-ko.html --data vol1-kr-sample.json --output newsletter-v1-rendered-kr.html
```

## File Structure

```
docs/marketing/
├── newsletter-v1-final-en.html       # EN Handlebars template (55 vars)
├── newsletter-v1-final-ko.html       # KO Handlebars template (55 vars)
├── render-newsletter.py              # Renderer (chevron/Mustache)
├── extract-blocks.py                 # Block extractor utility
├── newsletter-template-schema.md     # This file
├── vol1-us-sample.json               # Vol.1 US data
├── vol1-kr-sample.json               # Vol.1 KR data
├── newsletter-v1-rendered-*.html     # Rendered outputs
└── blocks/
    ├── vol1-us-*.html                # 15 EN-US block files
    └── vol1-kr-*.html                # 15 KO-KR block files
```

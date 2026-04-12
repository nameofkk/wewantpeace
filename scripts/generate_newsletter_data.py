#!/usr/bin/env python3
"""뉴스레터 데이터 완전 자동 생성 — DB + GPT로 모든 변수를 채워 Redis 초안으로 저장.

사용:
  python scripts/generate_newsletter_data.py --vol 1 --lang kr
  python scripts/generate_newsletter_data.py --vol 1 --lang us

모든 변수를 자동 생성 (수동 입력 0개):
  - DB 쿼리: 통계, 긴장도, 원자재, 여행경보, 이슈 클러스터
  - GPT: 헤드라인, 브리핑, 심층분석, 에디터 노트, 공유 텍스트
결과: Redis key `admin:newsletter:draft:vol{N}-{lang}` 에 JSON 저장 (TTL 90일)
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from backend.app.core.database import AsyncSessionLocal

# ── 국가명 매핑 (EN, KO) ─────────────────────────────────────────────────────
COUNTRY_NAMES = {
    "UA": ("Ukraine", "우크라이나"), "RU": ("Russia", "러시아"),
    "IL": ("Israel", "이스라엘"), "PS": ("Palestine", "팔레스타인"),
    "SD": ("Sudan", "수단"), "MM": ("Myanmar", "미얀마"),
    "SY": ("Syria", "시리아"), "YE": ("Yemen", "예멘"),
    "CD": ("DR Congo", "콩고민주공화국"), "ET": ("Ethiopia", "에티오피아"),
    "SO": ("Somalia", "소말리아"), "AF": ("Afghanistan", "아프가니스탄"),
    "IQ": ("Iraq", "이라크"), "LY": ("Libya", "리비아"),
    "NG": ("Nigeria", "나이지리아"), "ML": ("Mali", "말리"),
    "MZ": ("Mozambique", "모잠비크"), "HT": ("Haiti", "아이티"),
    "PK": ("Pakistan", "파키스탄"), "LB": ("Lebanon", "레바논"),
    "CN": ("China", "중국"), "KP": ("North Korea", "북한"),
    "TW": ("Taiwan", "대만"), "IR": ("Iran", "이란"),
    "KR": ("South Korea", "대한민국"), "JP": ("Japan", "일본"),
    "US": ("United States", "미국"), "GB": ("United Kingdom", "영국"),
    "FR": ("France", "프랑스"), "DE": ("Germany", "독일"),
    "IN": ("India", "인도"), "PH": ("Philippines", "필리핀"),
    "TH": ("Thailand", "태국"), "VN": ("Vietnam", "베트남"),
    "MX": ("Mexico", "멕시코"), "CO": ("Colombia", "콜롬비아"),
    "BR": ("Brazil", "브라질"), "AR": ("Argentina", "아르헨티나"),
    "EG": ("Egypt", "이집트"), "SA": ("Saudi Arabia", "사우디아라비아"),
    "AE": ("UAE", "아랍에미리트"), "TR": ("Turkey", "튀르키예"),
    "PL": ("Poland", "폴란드"), "BF": ("Burkina Faso", "부르키나파소"),
    "NE": ("Niger", "니제르"), "TD": ("Chad", "차드"),
    "CF": ("Central African Republic", "중앙아프리카공화국"),
    "CM": ("Cameroon", "카메룬"), "SS": ("South Sudan", "남수단"),
    "ER": ("Eritrea", "에리트레아"), "DJ": ("Djibouti", "지부티"),
    "KE": ("Kenya", "케냐"), "UG": ("Uganda", "우간다"),
}

SEVERITY_COLORS = {5: "#ef4444", 4: "#f97316", 3: "#eab308", 2: "#22c55e", 1: "#94a3b8"}
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
WEEKDAY_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def get_flag(cc: str) -> str:
    if not cc or len(cc) != 2:
        return "\U0001f3f3\ufe0f"
    return chr(0x1F1E6 + ord(cc[0]) - ord("A")) + chr(0x1F1E6 + ord(cc[1]) - ord("A"))


def get_country_name(cc: str, lang: str) -> str:
    names = COUNTRY_NAMES.get(cc)
    if not names:
        return cc or "Unknown"
    return names[1] if lang == "kr" else names[0]


def severity_color(sev: int) -> str:
    if sev >= 5:
        return SEVERITY_COLORS[5]
    return SEVERITY_COLORS.get(sev, "#94a3b8")


def tension_level_text(score: float, lang: str) -> str:
    if score >= 80:
        return "위기" if lang == "kr" else "Critical"
    if score >= 60:
        return "경고" if lang == "kr" else "Warning"
    if score >= 40:
        return "주의" if lang == "kr" else "Elevated"
    if score >= 20:
        return "관심" if lang == "kr" else "Watch"
    return "안정" if lang == "kr" else "Stable"


def tension_level_num(score: float) -> int:
    if score >= 80: return 5
    if score >= 60: return 4
    if score >= 40: return 3
    if score >= 20: return 2
    return 1


# ── GPT 호출 ─────────────────────────────────────────────────────────────────

async def call_gpt(prompt: str, system: str = "") -> str:
    """OpenAI GPT-4o-mini 호출."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY", ""))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=3000,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  GPT 호출 실패: {e}")
        return ""


async def generate_editorial_content(context: dict, lang: str) -> dict:
    """GPT로 편집 콘텐츠 일괄 생성 — 한 번의 호출로 모든 텍스트 생성."""
    lang_instruction = (
        "한국어로 작성. 구어체, ~해요 체. 비유 활용. 일상에 연결."
        if lang == "kr" else
        "Write in English. Casual, conversational. Connect to daily life."
    )

    system = f"""You are an editor for WeWantPeace, a conflict monitoring newsletter.
{lang_instruction}
Never give investment advice. Use "may", "could" — never predict with certainty.
Output ONLY valid JSON with the exact keys requested. No markdown fences."""

    prompt = f"""Based on this week's conflict data, generate newsletter content.

DATA CONTEXT:
- Top issue: {context.get('top_issue_title', 'N/A')}
- Top 3 countries: {context.get('top_countries', 'N/A')}
- Crisis countries: {context.get('crisis_count', 0)}
- Events (24h/7d): {context.get('events_24h', 0)} / {context.get('events_7d', 0)}
- Oil price: ${context.get('oil_price', 'N/A')} ({context.get('oil_change', 'N/A')}%)
- Wheat price: ${context.get('wheat_price', 'N/A')} ({context.get('wheat_change', 'N/A')}%)
- Target country tension: {context.get('target_tension', 'N/A')}
- Top cluster titles: {context.get('cluster_titles', 'N/A')}
- Travel advisories L4: {context.get('travel_l4_count', 0)} countries

Generate this JSON (all values are strings):
{{
  "hero_headline_html": "(2-3 lines with <br>, attention-grabbing headline about the #1 issue this week. Use <span class=\\"ce\\"> for emphasis on key numbers.)",
  "preheader_text": "(1 sentence, 60-80 chars, email preview text that hooks the reader)",
  "key_stats_line": "(HTML span tags with classes: w6=bold, ce=red, cy=yellow, cx=blue. Format: key stat 1 · stat 2 · stat 3)",
  "todays_brief_items_html": "(3 bullet items as <div> blocks, each with a bold title + 1 sentence explanation. Most important issues of the week.)",
  "energy_section_intro_html": "(1 punchy sentence about energy/commodity impact on daily life)",
  "energy_section_html": "(3-4 paragraphs about commodity price changes and how they affect daily costs — gas, groceries, delivery. Include specific price numbers from the data.)",
  "deep_dive_nav_label": "(3-4 word navigation label for deep dive section)",
  "deep_dive_title": "(short title for the deep dive — the #1 story this week)",
  "deep_dive_section_html": "(4-5 paragraphs deep analysis of the top issue. Include: what happened, why it matters, how it affects the reader's country, what to watch next week. Use <b> for emphasis.)",
  "country_impact_html": "(numbered list of 4 impact chain steps: event → market → daily life → consequence. Use → arrows.)",
  "country_issues_html": "(HTML table of 4-6 key issues affecting the target country, with event counts)",
  "did_you_know_html": "(1 surprising fact related to this week's conflicts, in 1-2 sentences)",
  "editors_note_html": "(3-4 sentences personal note from the editor. Reflective tone, end with encouragement to share.)",
  "numbers_section_html": "(6 KPI cards in a 2x3 grid using inline styles. Each card: number + label + change%. Use the actual data numbers.)",
  "next_week_items_html": "(3 things to watch next week as <div> blocks with bold titles)",
  "share_headline": "(catchy 1-line share CTA)",
  "share_subtext": "(who to share with — coworker, friend, family)",
  "pro_cta_headline_html": "(1-2 lines persuading upgrade to Pro, mention real-time alerts)",
  "pro_cta_subtext": "(1 sentence comparing free vs pro timing)",
  "tension_warning_html": "(1 sentence highlighting an alarming pattern in the tension data)",
  "calendar_html": "(next 4 days events as styled div blocks with dates and expected events)",
  "og_title": "(OpenGraph title, 50-60 chars)",
  "og_description": "(OpenGraph description, 100-150 chars)"
}}"""

    result_text = await call_gpt(prompt, system)
    try:
        # GPT가 ```json ... ``` 으로 감쌀 수 있으므로 제거
        cleaned = result_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
        return json.loads(cleaned)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  GPT JSON 파싱 실패: {e}")
        print(f"  원본: {result_text[:200]}")
        return {}


# ── HTML 빌더 ─────────────────────────────────────────────────────────────────

def build_tension_table_html(rows: list, lang: str, target_cc: str = "KR") -> str:
    if not rows:
        return "<p>No data available</p>"
    html = ['<table style="width:100%;border-collapse:collapse;">']
    for i, (cc, score, delta) in enumerate(rows[:10]):
        flag = get_flag(cc)
        name = get_country_name(cc, lang)
        color = severity_color(tension_level_num(score))
        width_pct = min(int(score), 100)
        delta_str = f"▲{abs(delta):.1f}" if delta > 0 else f"▼{abs(delta):.1f}" if delta < 0 else "—"
        highlight = ' style="background:#fffbeb;"' if cc == target_cc else ""
        you_tag = f' <span style="background:#eab308;color:white;padding:1px 6px;border-radius:8px;font-size:10px;">YOU</span>' if cc == target_cc else ""
        html.append(
            f'<tr{highlight}>'
            f'<td style="padding:8px;white-space:nowrap;font-size:13px;">{flag} {name}{you_tag}</td>'
            f'<td style="padding:8px;width:35%;">'
            f'<div style="background:{color};height:8px;border-radius:4px;width:{width_pct}%;"></div></td>'
            f'<td style="padding:8px;text-align:right;font-weight:bold;color:{color};font-size:13px;">{score:.1f}</td>'
            f'<td style="padding:8px;text-align:right;font-size:11px;color:#666;">{delta_str}</td>'
            f'</tr>'
        )
    html.append("</table>")
    return "\n".join(html)


def build_conflict_stories_html(clusters: list, lang: str) -> str:
    if not clusters:
        return "<p>No stories available</p>"
    html = []
    for title, title_ko, cc, sev, kscore, event_count in clusters[:5]:
        flag = get_flag(cc)
        color = severity_color(sev)
        bg = {"#ef4444": "#fef2f2", "#f97316": "#fff7ed", "#eab308": "#fefce8",
              "#22c55e": "#f0fdf4"}.get(color, "#f8fafc")
        display = (title_ko or title or "") if lang == "kr" else (title or title_ko or "")
        sev_label = f"심각도 {sev}" if lang == "kr" else f"Severity {sev}"
        events_label = f"{event_count}건" if lang == "kr" else f"{event_count} events"
        html.append(
            f'<div style="margin-bottom:16px;padding:12px;border-left:3px solid {color};background:{bg};">'
            f'<div style="font-weight:bold;margin-bottom:4px;">{flag} {display[:80]}</div>'
            f'<div style="margin-top:4px;display:flex;gap:8px;">'
            f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">{sev_label}</span>'
            f'<span style="color:#666;font-size:11px;">{events_label}</span></div></div>'
        )
    return "\n".join(html)


def build_travel_html(advisories: list, lang: str) -> str:
    if not advisories:
        return ""
    l4 = [a for a in advisories if a["level"] >= 4]
    l3 = [a for a in advisories if a["level"] == 3]
    html = []
    if l4:
        label = "여행 금지" if lang == "kr" else "Do Not Travel"
        html.append(f'<div style="margin-bottom:12px;"><b style="color:#ef4444;">LEVEL 4 — {label} ({len(l4)})</b>')
        html.append(f'<div style="font-size:12px;color:#666;margin-top:4px;">')
        html.append(", ".join(f'{get_flag(a["cc"])} {get_country_name(a["cc"], lang)}' for a in l4[:25]))
        html.append("</div></div>")
    if l3:
        label = "여행 재고" if lang == "kr" else "Reconsider Travel"
        html.append(f'<div><b style="color:#f97316;">LEVEL 3 — {label} ({len(l3)})</b>')
        html.append(f'<div style="font-size:12px;color:#666;margin-top:4px;">')
        html.append(", ".join(f'{get_flag(a["cc"])} {get_country_name(a["cc"], lang)}' for a in l3[:30]))
        html.append("</div></div>")
    return "\n".join(html)


# ── 메인 생성 ─────────────────────────────────────────────────────────────────

async def generate(vol: int, lang: str) -> dict:
    """DB + GPT로 뉴스레터 데이터 완전 자동 생성."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)
    twenty_four_hours_ago = now - timedelta(hours=24)
    target_cc = "KR" if lang == "kr" else "US"

    data = {}

    async with AsyncSessionLocal() as db:
        # ── 1. 기본 메타 ──
        data["vol_number"] = vol
        data["next_vol_number"] = vol + 1
        data["current_year"] = now.year
        wd = now.weekday()
        if lang == "kr":
            data["issue_date"] = f"{now.year}년 {now.month}월 {now.day}일"
            data["issue_date_short"] = f"{now.month}.{now.day} {WEEKDAY_KO[wd]}요일"
            data["issue_datetime"] = f"{now.year}.{now.month}.{now.day} {WEEKDAY_KO[wd]} 09:00"
            data["issue_label"] = f"Vol.{vol}"
            data["issue_label_long"] = f"Vol.{vol}"
        else:
            data["issue_date"] = now.strftime("%B %d, %Y")
            data["issue_date_short"] = now.strftime("%b %d, %a")
            data["issue_datetime"] = now.strftime("%Y.%m.%d %a 09:00")
            data["issue_label"] = f"Vol.{vol}"
            data["issue_label_long"] = f"Vol.{vol}"

        # ── 2. 클러스터 통계 ──
        r = await db.execute(text(
            "SELECT COUNT(*) FROM issue_clusters WHERE is_active = true AND severity >= 2"
        ))
        total_conflicts = r.scalar() or 0
        data["total_conflicts"] = total_conflicts

        r = await db.execute(text(
            "SELECT COUNT(*) FROM issue_clusters WHERE is_active = true AND severity >= 4"
        ))
        data["urgent_count"] = r.scalar() or 0

        r = await db.execute(text(
            "SELECT COUNT(*) FROM issue_clusters WHERE is_active = true"
        ))
        data["active_issues_count"] = r.scalar() or 0

        r = await db.execute(text(
            "SELECT COUNT(DISTINCT country_code) FROM issue_clusters "
            "WHERE is_active = true AND severity >= 4 AND country_code IS NOT NULL"
        ))
        crisis_count = r.scalar() or 0
        data["crisis_countries_count"] = crisis_count
        data["crisis_current"] = crisis_count

        # 지난주 위기 국가 수 (비교용)
        r = await db.execute(text(
            "SELECT COUNT(DISTINCT country_code) FROM issue_clusters "
            "WHERE is_active = true AND severity >= 4 AND country_code IS NOT NULL "
            "AND created_at < :cutoff"
        ), {"cutoff": seven_days_ago})
        crisis_prev = r.scalar() or crisis_count
        data["crisis_prev"] = crisis_prev
        diff = crisis_count - crisis_prev
        if diff > 0:
            data["crisis_trend"] = f"↑{diff}" if lang != "kr" else f"{diff}개국 증가"
        elif diff < 0:
            data["crisis_trend"] = f"↓{abs(diff)}" if lang != "kr" else f"{abs(diff)}개국 감소"
        else:
            data["crisis_trend"] = "—" if lang != "kr" else "변동 없음"

        # ── 3. 이벤트 수 ──
        r = await db.execute(text(
            "SELECT COUNT(*) FROM normalized_events WHERE event_time >= :cutoff"
        ), {"cutoff": twenty_four_hours_ago})
        events_24h = r.scalar() or 0
        data["events_24h"] = events_24h

        r = await db.execute(text(
            "SELECT COUNT(*) FROM normalized_events WHERE event_time >= :cutoff"
        ), {"cutoff": seven_days_ago})
        events_7d = r.scalar() or 0
        data["events_7d"] = f"{events_7d:,}"

        # ── 4. 상위 클러스터 ──
        r = await db.execute(text("""
            SELECT id, title, title_ko, country_code, severity, kscore, event_count
            FROM issue_clusters
            WHERE is_active = true AND severity >= 2
            ORDER BY kscore DESC
            LIMIT 5
        """))
        top_clusters = [
            (row.title, row.title_ko, row.country_code, row.severity, row.kscore, row.event_count)
            for row in r.fetchall()
        ]
        data["conflict_stories_html"] = build_conflict_stories_html(top_clusters, lang)

        # ── 5. 긴장도 (tension_index) ──
        r = await db.execute(text("""
            SELECT DISTINCT ON (country_code) country_code, raw_score
            FROM tension_index
            WHERE country_code IS NOT NULL
            ORDER BY country_code, time DESC
        """))
        tension_current = {row.country_code: row.raw_score for row in r.fetchall()}

        r = await db.execute(text("""
            SELECT DISTINCT ON (country_code) country_code, raw_score
            FROM tension_index
            WHERE country_code IS NOT NULL AND time < :cutoff
            ORDER BY country_code, time DESC
        """), {"cutoff": seven_days_ago})
        tension_prev = {row.country_code: row.raw_score for row in r.fetchall()}

        # 상위 10개
        sorted_tension = sorted(tension_current.items(), key=lambda x: x[1], reverse=True)[:10]
        tension_rows = [
            (cc, score, score - tension_prev.get(cc, score))
            for cc, score in sorted_tension
        ]
        data["tension_table_html"] = build_tension_table_html(tension_rows, lang, target_cc)

        # target 국가 긴장도
        target_score = tension_current.get(target_cc, 0)
        target_prev = tension_prev.get(target_cc, target_score)
        target_delta = target_score - target_prev
        data["country_name"] = get_country_name(target_cc, lang)
        data["country_code"] = target_cc
        data["tension_score"] = f"{target_score:.1f}"
        data["tension_level"] = tension_level_num(target_score)
        data["tension_level_text"] = tension_level_text(target_score, lang)
        data["tension_change"] = f"▲{abs(target_delta):.1f}" if target_delta > 0 else f"▼{abs(target_delta):.1f}" if target_delta < 0 else "—"
        data["prev_tension"] = f"{target_prev:.1f}"
        # target 국가 순위
        all_sorted = sorted(tension_current.items(), key=lambda x: x[1], reverse=True)
        data["country_rank"] = next((i + 1 for i, (cc, _) in enumerate(all_sorted) if cc == target_cc), 0)
        data["streak_text"] = ""  # GPT가 채울 수도 있지만 간단한 디폴트

        # ── 6. Country Spotlight (이슈 수 상위 3개) ──
        r = await db.execute(text("""
            SELECT country_code, COUNT(*) as issue_count, MAX(severity) as max_sev
            FROM issue_clusters
            WHERE is_active = true AND severity >= 2 AND country_code IS NOT NULL
            GROUP BY country_code
            ORDER BY issue_count DESC, max_sev DESC
            LIMIT 3
        """))
        spotlight_rows = r.fetchall()
        for i in range(3):
            idx = i + 1
            if i < len(spotlight_rows):
                row = spotlight_rows[i]
                cc = row.country_code
                data[f"country_{idx}_name"] = get_country_name(cc, lang)
                data[f"country_{idx}_flag"] = get_flag(cc)
                data[f"country_{idx}_severity"] = row.max_sev
                data[f"country_{idx}_event_count"] = row.issue_count
                sr = await db.execute(text(
                    "SELECT title, title_ko FROM issue_clusters "
                    "WHERE is_active = true AND country_code = :cc AND severity >= 2 "
                    "ORDER BY kscore DESC LIMIT 1"
                ), {"cc": cc})
                srow = sr.fetchone()
                if srow:
                    data[f"country_{idx}_summary"] = ((srow.title_ko or srow.title) if lang == "kr" else (srow.title or srow.title_ko))[:150]
                else:
                    data[f"country_{idx}_summary"] = ""
            else:
                for key in ["name", "flag", "severity", "event_count", "summary"]:
                    data[f"country_{idx}_{key}"] = "" if key != "severity" and key != "event_count" else 0

        # ── 7. 원자재 가격 ──
        oil_price, oil_change = None, None
        wheat_price, wheat_change = None, None
        for symbol, name in [("CL=F", "oil"), ("BZ=F", "oil_brent"), ("ZW=F", "wheat")]:
            r = await db.execute(text(
                "SELECT price_usd, change_pct FROM commodity_price "
                "WHERE symbol = :sym ORDER BY price_date DESC LIMIT 1"
            ), {"sym": symbol})
            row = r.fetchone()
            if row:
                if "CL" in symbol and not oil_price:
                    oil_price, oil_change = row.price_usd, row.change_pct
                elif "BZ" in symbol and not oil_price:
                    oil_price, oil_change = row.price_usd, row.change_pct
                elif "ZW" in symbol:
                    wheat_price, wheat_change = row.price_usd, row.change_pct

        # ── 8. 여행 경보 ──
        r = await db.execute(text(
            "SELECT DISTINCT ON (country_code) country_code, level "
            "FROM travel_advisory WHERE level >= 3 "
            "ORDER BY country_code, updated_at DESC"
        ))
        advisories = [{"cc": row.country_code, "level": row.level} for row in r.fetchall()]
        data["travel_advisory_html"] = build_travel_html(advisories, lang)
        travel_l4 = len([a for a in advisories if a["level"] >= 4])
        travel_l3 = len([a for a in advisories if a["level"] == 3])
        if lang == "kr":
            data["travel_advisory_intro_html"] = f"여행 금지 {travel_l4}개국, 여행 재고 {travel_l3}개국."
        else:
            data["travel_advisory_intro_html"] = f"Do Not Travel: {travel_l4} countries. Reconsider: {travel_l3} countries."

        # ── 9. 구독자 수 ──
        r = await db.execute(text(
            "SELECT COUNT(*) FROM users WHERE marketing_agreed_at IS NOT NULL"
        ))
        data["subscriber_count"] = r.scalar() or 0

    # ── 10. GPT 편집 콘텐츠 생성 ──
    top_title = ""
    cluster_titles = []
    if top_clusters:
        top_title = (top_clusters[0][1] or top_clusters[0][0]) if lang == "kr" else (top_clusters[0][0] or top_clusters[0][1])
        for t, tko, cc, sev, ks, ec in top_clusters:
            cluster_titles.append((tko or t) if lang == "kr" else (t or tko))

    top_countries = ", ".join(
        f"{get_country_name(cc, lang)} ({score:.0f})"
        for cc, score in sorted_tension[:3]
    ) if tension_rows else "N/A"

    gpt_context = {
        "top_issue_title": top_title,
        "top_countries": top_countries,
        "crisis_count": crisis_count,
        "events_24h": events_24h,
        "events_7d": events_7d,
        "oil_price": f"{oil_price:.1f}" if oil_price else "N/A",
        "oil_change": f"{oil_change:+.1f}" if oil_change is not None else "N/A",
        "wheat_price": f"{wheat_price:.1f}" if wheat_price else "N/A",
        "wheat_change": f"{wheat_change:+.1f}" if wheat_change is not None else "N/A",
        "target_tension": f"{get_country_name(target_cc, lang)} {target_score:.1f} (rank #{data['country_rank']})",
        "cluster_titles": " / ".join(cluster_titles[:5]),
        "travel_l4_count": travel_l4,
    }

    print("  GPT 편집 콘텐츠 생성 중...")
    editorial = await generate_editorial_content(gpt_context, lang)

    # GPT 결과를 data에 병합
    gpt_keys = [
        "hero_headline_html", "preheader_text", "key_stats_line",
        "todays_brief_items_html", "energy_section_intro_html", "energy_section_html",
        "deep_dive_nav_label", "deep_dive_title", "deep_dive_section_html",
        "country_impact_html", "country_issues_html", "did_you_know_html",
        "editors_note_html", "numbers_section_html", "next_week_items_html",
        "share_headline", "share_subtext", "pro_cta_headline_html", "pro_cta_subtext",
        "tension_warning_html", "calendar_html", "og_title", "og_description",
    ]
    for key in gpt_keys:
        data[key] = editorial.get(key, "")

    # ── 11. 프리뷰/메타/공유 텍스트 ──
    data["preview_text"] = data.get("preheader_text") or (
        f"이번 주 핵심: {top_title[:50]}" if lang == "kr" else f"This week: {top_title[:50]}"
    )
    data["og_image_url"] = ""
    data["hero_image_url"] = ""
    data["hero_subheadline_html"] = ""
    data["deep_dive_image_url"] = ""
    data["banner_image_url"] = ""
    data["map_snapshot_url"] = ""

    # 에디터 정보 (고정)
    data["editors_name"] = "WeWantPeace Team"
    data["editors_photo_url"] = ""

    # 공유 링크
    share_text = data.get("share_headline", "WeWantPeace Weekly Brief")
    data["social_share_text"] = share_text
    data["mailto_subject"] = quote(f"WeWantPeace Vol.{vol} — {share_text[:40]}")
    data["mailto_body"] = quote(f"{share_text}\n\nhttps://www.wewantpeace.live/?ref=share")

    # CTA
    data["call_to_action_text"] = "앱에서 실시간 확인" if lang == "kr" else "Check live in the app"
    data["call_to_action_url"] = "https://www.wewantpeace.live/"
    data["call_to_action_html"] = ""

    # 스폰서 (없음)
    data["sponsor_section_html"] = ""
    data["sponsor_logo_url"] = ""
    data["featured_quote"] = ""
    data["featured_quote_author"] = ""
    data["additional_resources_html"] = ""

    # 기타
    data["country_summary"] = data.get("country_impact_html", "")[:200] if data.get("country_impact_html") else ""
    data["footer_address"] = "WeWantPeace | wewantpeace.live"
    data["unsubscribe_url"] = "#"
    data["web_version_url"] = "https://wewantpeace.live/newsletter"

    # ── 12. 생성 메타 ──
    data["_generated_at"] = now.isoformat()
    data["_lang"] = lang
    data["_status"] = "draft"

    return data


async def main():
    parser = argparse.ArgumentParser(description="뉴스레터 데이터 완전 자동 생성")
    parser.add_argument("--vol", type=int, required=True, help="뉴스레터 볼륨 번호")
    parser.add_argument("--lang", choices=["kr", "us"], required=True, help="언어 (kr/us)")
    args = parser.parse_args()

    print(f"=== 뉴스레터 데이터 생성: Vol.{args.vol} ({args.lang}) ===")

    data = await generate(args.vol, args.lang)

    # Redis에 저장
    import redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    r = redis.from_url(redis_url, decode_responses=True)

    key = f"admin:newsletter:draft:vol{args.vol}-{args.lang}"
    ttl = 90 * 24 * 3600  # 90일

    r.set(key, json.dumps(data, ensure_ascii=False, default=str), ex=ttl)

    filled = len([k for k in data if not k.startswith('_') and data[k] not in ('', 0, None)])
    empty = len([k for k in data if not k.startswith('_') and data[k] in ('', 0, None)])
    print(f"\n저장 완료: {key} (TTL {ttl // 86400}일)")
    print(f"  - total_conflicts: {data['total_conflicts']}")
    print(f"  - crisis_countries_count: {data['crisis_countries_count']}")
    print(f"  - events: {data['events_24h']}(24h) / {data['events_7d']}(7d)")
    print(f"  - tension: {data['country_name']} {data['tension_score']} (#{data['country_rank']})")
    print(f"  - hero: {data.get('hero_headline_html', '')[:60]}")
    print(f"  - 자동 채움: {filled}개 / 빈 변수: {empty}개")

    return data


if __name__ == "__main__":
    asyncio.run(main())

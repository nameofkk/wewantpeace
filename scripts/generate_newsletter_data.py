#!/usr/bin/env python3
"""뉴스레터 데이터 자동 생성 — DB에서 자동화 가능한 변수를 채워 Redis 초안으로 저장.

사용:
  python scripts/generate_newsletter_data.py --vol 1 --lang kr
  python scripts/generate_newsletter_data.py --vol 1 --lang us

자동 채우는 변수: ~30개 (DB 쿼리 기반)
수동 입력 변수: ~25개 (hero_headline_html, deep_dive 등) → 빈 문자열로 설정
결과: Redis key `admin:newsletter:draft:vol{N}-{lang}` 에 JSON 저장 (TTL 90일)
"""

import asyncio
import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta

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

# ── severity 색상 ────────────────────────────────────────────────────────────
SEVERITY_COLORS = {
    5: "#ef4444",
    4: "#f97316",
    3: "#eab308",
    2: "#22c55e",
    1: "#94a3b8",
}


def get_flag(cc: str) -> str:
    """국가 코드 → 국기 이모지."""
    if not cc or len(cc) != 2:
        return "\U0001f3f3\ufe0f"
    return chr(0x1F1E6 + ord(cc[0]) - ord("A")) + chr(0x1F1E6 + ord(cc[1]) - ord("A"))


def get_country_name(cc: str, lang: str) -> str:
    """국가 코드 → 로컬라이즈된 이름."""
    names = COUNTRY_NAMES.get(cc)
    if not names:
        return cc or "Unknown"
    return names[1] if lang == "kr" else names[0]


def severity_color(sev: int) -> str:
    """severity 값에 대한 색상 반환."""
    if sev >= 5:
        return SEVERITY_COLORS[5]
    return SEVERITY_COLORS.get(sev, "#94a3b8")


def format_date(lang: str) -> str:
    """오늘 날짜를 언어에 맞게 포맷."""
    now = datetime.now(timezone.utc)
    if lang == "kr":
        return f"{now.year}년 {now.month}월 {now.day}일"
    else:
        return now.strftime("%B %d, %Y")


def build_tension_table_html(rows: list, lang: str) -> str:
    """상위 10개 국가 긴장도 HTML 테이블 생성.

    rows: list of (country_code, max_severity) tuples
    """
    if not rows:
        return "<p>No data available</p>"

    html_parts = ['<table style="width:100%;border-collapse:collapse;">']
    for cc, sev in rows[:10]:
        flag = get_flag(cc)
        name = get_country_name(cc, lang)
        color = severity_color(sev)
        width_pct = min(sev * 20, 100)
        sev_label = f"Severity {sev}" if lang == "us" else f"심각도 {sev}"
        html_parts.append(
            f'<tr style="border-bottom:1px solid #eee;padding:8px;">'
            f'<td style="padding:8px;white-space:nowrap;">{flag} {name}</td>'
            f'<td style="padding:8px;width:40%;">'
            f'<div style="background:{color};height:8px;border-radius:4px;width:{width_pct}%;"></div>'
            f'</td>'
            f'<td style="padding:8px;text-align:right;font-weight:bold;color:{color};">{sev}</td>'
            f'</tr>'
        )
    html_parts.append("</table>")
    return "\n".join(html_parts)


def build_conflict_stories_html(clusters: list, lang: str) -> str:
    """상위 5개 클러스터 HTML 카드 생성.

    clusters: list of (title, title_ko, country_code, severity, kscore) tuples
    """
    if not clusters:
        return "<p>No stories available</p>"

    html_parts = []
    for title, title_ko, cc, sev, kscore in clusters[:5]:
        flag = get_flag(cc)
        color = severity_color(sev)
        bg_color = {
            "#ef4444": "#fef2f2",
            "#f97316": "#fff7ed",
            "#eab308": "#fefce8",
            "#22c55e": "#f0fdf4",
            "#94a3b8": "#f8fafc",
        }.get(color, "#f8fafc")

        display_title = (title_ko or title or "")
        if lang == "us":
            display_title = title or title_ko or ""
        # 100자 제한
        summary = display_title[:100] + ("..." if len(display_title) > 100 else "")

        sev_label = f"Severity {sev}" if lang == "us" else f"심각도 {sev}"

        html_parts.append(
            f'<div style="margin-bottom:16px;padding:12px;border-left:3px solid {color};background:{bg_color};">'
            f'<div style="font-weight:bold;margin-bottom:4px;">{flag} {display_title[:60]}</div>'
            f'<div style="font-size:13px;color:#666;">{summary}</div>'
            f'<div style="margin-top:4px;">'
            f'<span style="background:{color};color:white;padding:2px 8px;border-radius:12px;font-size:11px;">'
            f'{sev_label}</span></div>'
            f'</div>'
        )
    return "\n".join(html_parts)


async def generate(vol: int, lang: str) -> dict:
    """DB를 쿼리하여 뉴스레터 초안 데이터를 생성."""
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    twenty_four_hours_ago = now - timedelta(hours=24)

    data = {}

    async with AsyncSessionLocal() as db:
        # ── 1. 기본 메타데이터 ──
        data["vol_number"] = vol
        data["issue_date"] = format_date(lang)
        data["current_year"] = now.year

        # ── 2. 활성 클러스터 통계 (severity >= 2) ──
        r = await db.execute(text(
            "SELECT COUNT(*) FROM issue_clusters WHERE is_active = true AND severity >= 2"
        ))
        data["total_conflicts"] = r.scalar() or 0

        # ── 3. 긴급 클러스터 (severity >= 4) ──
        r = await db.execute(text(
            "SELECT COUNT(*) FROM issue_clusters WHERE is_active = true AND severity >= 4"
        ))
        data["urgent_count"] = r.scalar() or 0

        # ── 4. 위기 국가 수 (severity >= 4인 고유 국가) ──
        r = await db.execute(text(
            "SELECT COUNT(DISTINCT country_code) FROM issue_clusters "
            "WHERE is_active = true AND severity >= 4 AND country_code IS NOT NULL"
        ))
        data["crisis_countries_count"] = r.scalar() or 0

        # ── 5. 이벤트 수 (24h / 7d) ──
        r = await db.execute(text(
            "SELECT COUNT(*) FROM normalized_events WHERE event_time >= :cutoff"
        ), {"cutoff": twenty_four_hours_ago})
        data["events_24h"] = r.scalar() or 0

        r = await db.execute(text(
            "SELECT COUNT(*) FROM normalized_events WHERE event_time >= :cutoff"
        ), {"cutoff": seven_days_ago})
        data["events_7d"] = r.scalar() or 0

        # ── 6. 긴장도 테이블 (상위 10개 국가, severity 기준) ──
        r = await db.execute(text("""
            SELECT country_code, MAX(severity) as max_sev
            FROM issue_clusters
            WHERE is_active = true AND severity >= 2 AND country_code IS NOT NULL
            GROUP BY country_code
            ORDER BY max_sev DESC, COUNT(*) DESC
            LIMIT 10
        """))
        tension_rows = [(row.country_code, row.max_sev) for row in r.fetchall()]
        data["tension_table_html"] = build_tension_table_html(tension_rows, lang)

        # ── 7. 주요 이슈 스토리 (kscore 상위 5개) ──
        r = await db.execute(text("""
            SELECT title, title_ko, country_code, severity, kscore
            FROM issue_clusters
            WHERE is_active = true AND severity >= 2
            ORDER BY kscore DESC
            LIMIT 5
        """))
        top_clusters = [
            (row.title, row.title_ko, row.country_code, row.severity, row.kscore)
            for row in r.fetchall()
        ]
        data["conflict_stories_html"] = build_conflict_stories_html(top_clusters, lang)

        # ── 8. Country Spotlight (이슈 수 상위 3개 국가) ──
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

                # 해당 국가의 최상위 클러스터 제목을 요약으로 사용
                sr = await db.execute(text("""
                    SELECT title, title_ko FROM issue_clusters
                    WHERE is_active = true AND country_code = :cc AND severity >= 2
                    ORDER BY kscore DESC LIMIT 1
                """), {"cc": cc})
                summary_row = sr.fetchone()
                if summary_row:
                    if lang == "kr":
                        data[f"country_{idx}_summary"] = (summary_row.title_ko or summary_row.title or "")[:150]
                    else:
                        data[f"country_{idx}_summary"] = (summary_row.title or summary_row.title_ko or "")[:150]
                else:
                    data[f"country_{idx}_summary"] = ""
            else:
                data[f"country_{idx}_name"] = ""
                data[f"country_{idx}_flag"] = ""
                data[f"country_{idx}_severity"] = 0
                data[f"country_{idx}_event_count"] = 0
                data[f"country_{idx}_summary"] = ""

        # ── 9. 구독자 수 (마케팅 동의자) ──
        r = await db.execute(text(
            "SELECT COUNT(*) FROM users WHERE marketing_agreed_at IS NOT NULL"
        ))
        data["subscriber_count"] = r.scalar() or 0

        # ── 10. 프리뷰 텍스트 (상위 이슈 기반) ──
        if top_clusters:
            top_title = top_clusters[0][1] if lang == "kr" else top_clusters[0][0]
            top_title = top_title or top_clusters[0][0] or ""
            if lang == "kr":
                data["preview_text"] = f"이번 주 핵심 이슈: {top_title[:50]}"
            else:
                data["preview_text"] = f"This week's key issue: {top_title[:50]}"
        else:
            data["preview_text"] = (
                "이번 주 글로벌 분쟁 현황" if lang == "kr"
                else "This week's global conflict update"
            )

        # ── 11. 템플릿 메타데이터 ──
        data["footer_address"] = "WeWantPeace | wewantpeace.live"
        data["unsubscribe_url"] = "#"
        data["web_version_url"] = "https://wewantpeace.live/newsletter"

        # ── 12. 수동 입력 변수 (빈 문자열) ──
        manual_fields = [
            "hero_headline_html",
            "hero_subheadline_html",
            "hero_image_url",
            "preheader_text",
            "energy_section_html",
            "deep_dive_title",
            "deep_dive_section_html",
            "deep_dive_image_url",
            "editors_note_html",
            "editors_name",
            "editors_photo_url",
            "call_to_action_html",
            "call_to_action_url",
            "call_to_action_text",
            "sponsor_section_html",
            "sponsor_logo_url",
            "social_share_text",
            "og_image_url",
            "og_title",
            "og_description",
            "banner_image_url",
            "featured_quote",
            "featured_quote_author",
            "map_snapshot_url",
            "additional_resources_html",
        ]
        for field in manual_fields:
            data[field] = ""

        # ── 13. 생성 메타 ──
        data["_generated_at"] = now.isoformat()
        data["_lang"] = lang
        data["_status"] = "draft"

    return data


async def main():
    parser = argparse.ArgumentParser(description="뉴스레터 데이터 자동 생성")
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

    print(f"\n저장 완료: {key} (TTL {ttl // 86400}일)")
    print(f"  - total_conflicts: {data['total_conflicts']}")
    print(f"  - urgent_count: {data['urgent_count']}")
    print(f"  - crisis_countries_count: {data['crisis_countries_count']}")
    print(f"  - events_24h: {data['events_24h']}")
    print(f"  - events_7d: {data['events_7d']}")
    print(f"  - subscriber_count: {data['subscriber_count']}")
    print(f"  - country_1: {data.get('country_1_name', 'N/A')}")
    print(f"  - country_2: {data.get('country_2_name', 'N/A')}")
    print(f"  - country_3: {data.get('country_3_name', 'N/A')}")
    print(f"  - preview_text: {data['preview_text'][:60]}")
    print(f"\n자동 채움: {len([k for k in data if not k.startswith('_') and data[k] != ''])}개 변수")
    print(f"수동 입력 필요: {len([k for k in data if not k.startswith('_') and data[k] == ''])}개 변수")

    return data


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""실제 DB 데이터 기반 카드 시안 생성 + 브라우저 프리뷰 HTML 출력.

Usage:
    cd ~/Projects/wewantpeace
    python scripts/_preview_real_cards.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── DB 설정 ───────────────────────────────────────────────────────────────────
import asyncpg

_DB = dict(
    host="aws-1-ap-northeast-2.pooler.supabase.com",
    port=6543,
    user="postgres.smxitufpgfuzepldglfo",
    password="WwpAdmin2026",
    database="postgres",
    statement_cache_size=0,
)

_COLS = """
    id, title, title_ko, country_code,
    severity, kscore, independent_sources, source_tiers,
    is_verified, event_count, image_url, last_event_at
"""


async def _fetch() -> tuple:
    conn = await asyncpg.connect(**_DB)

    # kscore_alert: 최고 kscore 클러스터
    alert = await conn.fetchrow(f"""
        SELECT {_COLS}
        FROM issue_clusters
        WHERE is_active = true
          AND severity >= 50
          AND last_event_at >= NOW() - INTERVAL '72 hours'
        ORDER BY kscore DESC, severity DESC
        LIMIT 1
    """)

    # daily_movers: 최근 48h 상위 3개 (severity 기준)
    daily = await conn.fetch(f"""
        SELECT {_COLS}
        FROM issue_clusters
        WHERE is_active = true
          AND severity > 0
          AND country_code IS NOT NULL
          AND last_event_at >= NOW() - INTERVAL '48 hours'
        ORDER BY severity DESC, kscore DESC
        LIMIT 3
    """)

    # weekly_recap: 최근 7일 상위 5개
    weekly = await conn.fetch(f"""
        SELECT {_COLS}
        FROM issue_clusters
        WHERE is_active = true
          AND severity > 0
          AND country_code IS NOT NULL
          AND last_event_at >= NOW() - INTERVAL '7 days'
        ORDER BY severity DESC, kscore DESC
        LIMIT 5
    """)

    await conn.close()
    return alert, daily, weekly


def _row(r) -> dict:
    tiers = r["source_tiers"]
    return {
        "title_en":            r["title"] or "",
        "title_ko":            r["title_ko"] or r["title"] or "",
        "country_code":        r["country_code"] or "",
        "severity":            r["severity"] or 0,
        "kscore":              float(r["kscore"] or 0),
        "independent_sources": r["independent_sources"] or 0,
        "source_tiers":        list(tiers) if tiers else [],
        "is_verified":         bool(r["is_verified"]),
        "event_count":         r["event_count"] or 0,
        "image_url":           r["image_url"] or None,
    }


def _make_preview(a_html: str, d_html: str, w_html: str) -> str:
    def enc(h: str) -> str:
        return h.replace("&", "&amp;").replace('"', "&quot;")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ background:#0a0a0a; margin:0; padding:40px 30px; font-family:'DM Sans',sans-serif; }}
  h3 {{ color:#555; font-size:11px; letter-spacing:.14em; text-transform:uppercase;
        margin:0 0 10px; font-weight:600; }}
  .row {{ display:flex; gap:36px; align-items:flex-start; }}
  .col {{ flex-shrink:0; }}
  iframe {{ border:none; border-radius:10px;
            box-shadow:0 24px 80px rgba(0,0,0,.7); display:block; }}
</style>
</head>
<body>
<div class="row">
  <div class="col">
    <h3>kscore_alert — BREAKING NEWS</h3>
    <iframe srcdoc="{enc(a_html)}" width="720" height="900" scrolling="no"></iframe>
  </div>
  <div class="col">
    <h3>daily_movers — DAILY BRIEF</h3>
    <iframe srcdoc="{enc(d_html)}" width="720" height="900" scrolling="no"></iframe>
  </div>
  <div class="col">
    <h3>weekly_recap — WEEK IN REVIEW</h3>
    <iframe srcdoc="{enc(w_html)}" width="720" height="900" scrolling="no"></iframe>
  </div>
</div>
</body>
</html>"""


async def main() -> None:
    print("DB 연결 중...")
    alert_row, daily_rows, weekly_rows = await _fetch()

    date_str = datetime.now(timezone.utc).strftime("%Y.%m.%d")

    alert_issue = _row(alert_row) if alert_row else {}
    daily_issues = [_row(r) for r in daily_rows]
    weekly_issues = [_row(r) for r in weekly_rows]

    print(f"\n[kscore_alert]")
    print(f"  {alert_issue.get('title_en','(없음)')}")
    print(f"  severity={alert_issue.get('severity')}  kscore={alert_issue.get('kscore'):.1f}  image={'있음' if alert_issue.get('image_url') else '없음'}")

    print(f"\n[daily_movers] {len(daily_issues)}개")
    for i in daily_issues:
        print(f"  [{i['country_code']}] sev={i['severity']}  {i['title_en'][:55]}")

    print(f"\n[weekly_recap] {len(weekly_issues)}개")
    for i in weekly_issues:
        print(f"  [{i['country_code']}] sev={i['severity']}  {i['title_en'][:55]}")

    from worker.social.card_html_generator import _alert_html, _daily_html, _weekly_html

    a_html = _alert_html(
        [alert_issue] if alert_issue else [],
        date_str,
        image_url=alert_issue.get("image_url"),
    )
    d_html = _daily_html(daily_issues, date_str)
    w_html = _weekly_html(weekly_issues, date_str)

    preview = _make_preview(a_html, d_html, w_html)

    out = "/tmp/real_card_preview.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(preview)
    print(f"\n프리뷰 저장: {out}")


if __name__ == "__main__":
    asyncio.run(main())

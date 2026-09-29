"""나라별 주간 브리프 — 초안 뽑기 / 보내기 (2주 검증 실험용, 사람이 쓰고 사람이 보낸다).

진단 보고서의 제안: 자동화부터 만들지 말고, 2주 동안 손으로 써서 보내 보며
구독·열람·답장이 실제로 생기는지 먼저 본다. 이 스크립트는 그 수작업을 덜어 준다.

  draft  나라 지난 7일 이슈를 출처 수와 함께 뽑아 초안(markdown)을 찍는다 (읽기 전용)
  count  나라별 확인 완료 구독자 수
  send   편집한 markdown 을 그 나라 구독자(status=active)에게 보낸다
         --test 주소 로 먼저 한 통, --dry-run 으로 받는 사람 수만

워커 컨테이너에서 실행 (DB·RESEND_API_KEY 필요):
  python scripts/country_brief.py draft UA > /tmp/ua.md
  python scripts/country_brief.py send UA /tmp/ua.md --test me@example.com
  python scripts/country_brief.py send UA /tmp/ua.md --dry-run
  python scripts/country_brief.py send UA /tmp/ua.md
"""
import argparse
import asyncio
import html
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SITE = "https://www.wewantpeace.live"


async def draft(cc: str) -> None:
    from sqlalchemy import select
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.models.issue_cluster import IssueCluster
    from worker.social import brief as B

    since = datetime.now(timezone.utc) - timedelta(days=7)
    async with AsyncSessionLocal() as db:
        clusters = (await db.execute(
            select(IssueCluster)
            .where(IssueCluster.country_code == cc, IssueCluster.last_event_at >= since)
            .order_by(IssueCluster.kscore.desc())
            .limit(15)
        )).scalars().all()
        name = B.country_name(cc)
        start, end = since.strftime("%b %d"), datetime.now(timezone.utc).strftime("%b %d")
        print(f"# {name}: week of {start} to {end}\n")
        print("<!-- 아래 재료로 3~5개 항목을 직접 쓰세요. 항목마다: 무슨 일 / 왜 중요 / 지켜볼 점 / 출처 수 -->\n")
        shown = 0
        for c in clusters:
            if B.is_template_title(c):
                continue
            ctx = await B.gather_context(db, c, hours=24 * 7)
            if ctx["n_sources"] < 2:
                continue
            shown += 1
            print(f"## {B._clean(c.title)}")
            print(f"- {ctx['n_sources']} independent sources: {', '.join(ctx['source_names'][:6])}")
            print(f"- {c.first_event_at:%b %d} to {c.last_event_at:%b %d}, {c.event_count} reports")
            print(f"- Timeline: {SITE}/issues/{c.id}?ref=brief")
            for r in ctx["reports"][:3]:
                print(f"  {r[:220]}")
            print("\nWhat happened: \nWhy it matters: \nWhat to watch: \n")
            if shown >= 6:
                break
        if not shown:
            print("(출처 2곳 이상인 이슈가 없습니다)")


def md_to_html(md: str) -> str:
    """제목·굵게·링크·문단만 — 브리프에 필요한 만큼."""
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    out = []
    for block in re.split(r"\n\s*\n", md.strip()):
        b = html.escape(block.strip())
        b = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", b)
        b = re.sub(r"(https?://[^\s<]+)", r"<a href='\1'>\1</a>", b)
        if b.startswith("# "):
            out.append(f"<h1 style='font-size:20px;margin:0 0 12px'>{b[2:]}</h1>")
        elif b.startswith("## "):
            out.append(f"<h2 style='font-size:16px;margin:20px 0 6px'>{b[3:]}</h2>")
        else:
            out.append("<p style='margin:0 0 10px;line-height:1.5'>" + b.replace("\n", "<br>") + "</p>")
    return "\n".join(out)


def wrap(body_html: str, token: str, lang: str) -> tuple[str, str]:
    unsub = f"{SITE}/brief/unsubscribe?token={token}"
    foot = (
        f"<p style='color:#666;font-size:12px;margin-top:28px'>WeWantPeace weekly brief. "
        f"<a href='{unsub}'>{'수신거부' if lang == 'ko' else 'Unsubscribe'}</a></p>"
    )
    page = (
        "<div style='font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:600px;"
        f"margin:0 auto;color:#15181c'>{body_html}{foot}</div>"
    )
    return page, unsub


async def send(cc: str, path: str, test: str | None, dry_run: bool) -> None:
    from sqlalchemy import select
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.core.mailer import send_email
    from backend.app.models.brief_subscriber import BriefSubscriber

    md = open(path, encoding="utf-8").read()
    subject = (re.search(r"^# (.+)$", md, re.M) or [None, f"{cc} weekly brief"])[1].strip()
    body = md_to_html(md)

    if test:
        page, unsub = wrap(body, "TEST-TOKEN", "en")
        ok = send_email(test, f"[TEST] {subject}", page, headers={"List-Unsubscribe": f"<{unsub}>"})
        print("test sent" if ok else "test FAILED")
        return

    async with AsyncSessionLocal() as db:
        subs = (await db.execute(select(BriefSubscriber).where(BriefSubscriber.status == "active"))).scalars().all()
    targets = [s for s in subs if cc in (s.countries or [])]
    print(f"{cc}: 확인 완료 구독자 {len(targets)}명")
    if dry_run:
        return
    sent = 0
    for s in targets:
        page, unsub = wrap(body, s.token, s.lang)
        if send_email(s.email, subject, page, headers={
            "List-Unsubscribe": f"<{unsub}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }):
            sent += 1
        time.sleep(0.6)  # Resend 무료 요금제 초당 2건
    print(f"보냄 {sent}/{len(targets)}")


async def count() -> None:
    from collections import Counter
    from sqlalchemy import select
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.models.brief_subscriber import BriefSubscriber

    async with AsyncSessionLocal() as db:
        subs = (await db.execute(select(BriefSubscriber))).scalars().all()
    print("status:", Counter(s.status for s in subs))
    print("active by country:", Counter(c for s in subs if s.status == "active" for c in s.countries))
    print("source:", Counter(s.source or "-" for s in subs))


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft")
    d.add_argument("cc")
    sub.add_parser("count")
    s = sub.add_parser("send")
    s.add_argument("cc")
    s.add_argument("path")
    s.add_argument("--test")
    s.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.cmd == "draft":
        asyncio.run(draft(a.cc.upper()))
    elif a.cmd == "count":
        asyncio.run(count())
    else:
        asyncio.run(send(a.cc.upper(), a.path, a.test, a.dry_run))


if __name__ == "__main__":
    main()

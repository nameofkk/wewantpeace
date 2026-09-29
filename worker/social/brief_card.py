"""Threads 브리프 카드 — 1080×1350 (4:5) PNG.

2026-09-30 개편. 예전 카드(검정 바탕 + 빨간 BREAKING 배지 + 세리프 + 심각도 막대,
크림색 에디토리얼)는 흔한 AI 생성 뉴스 카드처럼 보였다. 새 카드는 브리핑 문서처럼:
- 연한 회녹색 종이 바탕, 먹색 글자, 강조색은 짙은 바다색 하나
- IBM Plex Sans(본문) + Plex Mono(시각·라벨) — 상황 보고서 서식
- 글이 주인공: 헤드라인 → 무슨 일 / 왜 중요 / 지켜볼 점 → 출처 수
- 심각도 점수·막대·국기·이모지 없음
"""
from __future__ import annotations

import html as _html
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

W, H = 1080, 1350

_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Mono:wght@500&family=IBM+Plex+Sans:wght@400;500;600&display=swap"
)

_BASE_CSS = """
:root{--paper:#F1F3EF;--ink:#14181B;--muted:#5A626A;--rule:#CDD2CC;--accent:#0E5A8A}
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;background:var(--paper);color:var(--ink);
  font-family:'IBM Plex Sans','Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased}
.page{position:relative;width:1080px;height:1350px;padding:84px 88px}
.mono{font-family:'IBM Plex Mono','SFMono-Regular',Menlo,monospace;font-weight:500;
  letter-spacing:.12em;text-transform:uppercase}
.top{display:flex;justify-content:space-between;align-items:baseline;font-size:21px;
  padding-bottom:26px;border-bottom:3px solid var(--ink)}
.top .brand{color:var(--ink)}
.top .time{color:var(--muted)}
.main{position:absolute;left:88px;right:88px;top:190px;bottom:230px;overflow:hidden}
.kicker{font-size:25px;color:var(--accent);margin-bottom:26px;letter-spacing:.16em}
h1{font-weight:600;letter-spacing:-.022em;line-height:1.08;text-wrap:balance;max-width:900px}
.rows{margin-top:54px;border-top:1px solid var(--rule)}
.row{display:grid;grid-template-columns:220px 1fr;gap:28px;padding:26px 0;border-bottom:1px solid var(--rule)}
.row .label{font-size:19px;color:var(--muted);padding-top:7px;line-height:1.35}
.row .text{font-size:31px;line-height:1.36}
.foot{position:absolute;left:88px;right:88px;bottom:84px;display:flex;justify-content:space-between;
  align-items:flex-end;padding-top:26px;border-top:1px solid var(--ink)}
.foot .count{font-size:27px;font-weight:500}
.foot .names{font-size:18px;color:var(--muted);margin-top:10px;letter-spacing:.06em;
  max-width:640px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.foot .site{font-size:22px;color:var(--ink);letter-spacing:.08em}
.items{margin-top:48px;border-top:1px solid var(--rule)}
.item{display:grid;grid-template-columns:86px 1fr;gap:18px;padding:30px 0;border-bottom:1px solid var(--rule)}
.item .num{font-size:24px;color:var(--accent);padding-top:6px}
.item .ck{font-size:19px;color:var(--muted);margin-bottom:10px}
.item .hl{font-size:36px;font-weight:500;line-height:1.24;letter-spacing:-.01em}
"""

# 넘치면 글자를 조금씩 줄인다 (문장 길이는 AI 가 정해서 매번 다르다)
_FIT_JS = """
(() => {
  const main = document.querySelector('.main');
  const pick = (s) => Array.from(document.querySelectorAll(s));
  for (let i = 0; i < 10 && main.scrollHeight > main.clientHeight + 1; i++) {
    pick('.row .text, .item .hl').forEach(el => {
      el.style.fontSize = (parseFloat(getComputedStyle(el).fontSize) - 1.5) + 'px';
    });
    const h1 = document.querySelector('h1');
    if (h1 && i % 2) h1.style.fontSize = (parseFloat(getComputedStyle(h1).fontSize) - 3) + 'px';
  }
})();
"""


def _e(s) -> str:
    return _html.escape(str(s or ""))


def _stamp(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%d %b %Y, %H:%M UTC").upper()


def _headline_px(text: str) -> int:
    n = len(text)
    if n <= 45:
        return 78
    if n <= 65:
        return 70
    return 62


def _page(body: str, time_label: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<link rel='stylesheet' href='{_FONTS}'><style>{_BASE_CSS}</style></head><body>"
        "<div class='page'>"
        "<div class='top mono'><span class='brand'>WeWantPeace / Conflict brief</span>"
        f"<span class='time'>{_e(time_label)}</span></div>"
        f"{body}</div></body></html>"
    )


def alert_html(brief: dict, *, country: str, n_sources: int, source_names: list[str],
               when: datetime | None = None) -> str:
    rows = []
    for label, key in (("What happened", "what"), ("Why it matters", "why"), ("What to watch", "watch")):
        if brief.get(key):
            rows.append(
                f"<div class='row'><div class='label mono'>{label}</div>"
                f"<div class='text'>{_e(brief[key])}</div></div>"
            )
    names = " · ".join(source_names[:6])
    body = (
        "<div class='main'>"
        f"<div class='kicker mono'>{_e(country or 'Global')}</div>"
        f"<h1 style='font-size:{_headline_px(brief['headline'])}px'>{_e(brief['headline'])}</h1>"
        f"<div class='rows'>{''.join(rows)}</div>"
        "</div>"
        "<div class='foot'><div>"
        f"<div class='count'>{n_sources} independent sources</div>"
        f"<div class='names mono'>{_e(names)}</div>"
        "</div><div class='site mono'>wewantpeace.live</div></div>"
    )
    return _page(body, _stamp(when))


def list_html(title: str, subtitle: str, items: list[dict]) -> str:
    """items: [{country, headline, meta}] — 일간·주간 요약용."""
    parts = []
    for i, it in enumerate(items[:4], 1):
        meta = f" · {_e(it['meta'])}" if it.get("meta") else ""
        parts.append(
            f"<div class='item'><div class='num mono'>{i:02d}</div><div>"
            f"<div class='ck mono'>{_e(it.get('country') or 'Global')}{meta}</div>"
            f"<div class='hl'>{_e(it['headline'])}</div></div></div>"
        )
    body = (
        "<div class='main'>"
        f"<div class='kicker mono'>{_e(subtitle)}</div>"
        f"<h1 style='font-size:76px'>{_e(title)}</h1>"
        f"<div class='items'>{''.join(parts)}</div>"
        "</div>"
        "<div class='foot'><div>"
        "<div class='names mono' style='margin-top:0'>Wire services · local press · official statements</div>"
        "</div><div class='site mono'>wewantpeace.live</div></div>"
    )
    return _page(body, _stamp())


def render_png(html_src: str) -> bytes | None:
    """Playwright 로 1080×1350 PNG. 실패하면 None (호출부가 폴백)."""
    try:
        from playwright.sync_api import sync_playwright
        from worker.social.card_html_generator import _CHROMIUM_ARGS

        with sync_playwright() as p:
            browser = p.chromium.launch(args=_CHROMIUM_ARGS)
            try:
                page = browser.new_page(viewport={"width": W, "height": H})
                try:
                    page.set_content(html_src, wait_until="networkidle", timeout=15000)
                except Exception:
                    pass
                page.evaluate("() => document.fonts.ready")
                page.evaluate(_FIT_JS)
                return page.screenshot(clip={"x": 0, "y": 0, "width": W, "height": H}, type="png")
            finally:
                browser.close()
    except Exception:
        logger.exception("브리프 카드 렌더 실패")
        return None


async def attach_card(post, html_src: str) -> bool:
    """카드를 그려 R2 에 올리고 post.image_url 에 공개 URL 을 넣는다.

    실패하면 이미지 없이 글만 나간다 (예전처럼 기본 OG 이미지를 붙이지 않는다 —
    사이트 로고 한 장이 매번 붙는 게 더 광고처럼 보였다).
    """
    import asyncio
    import functools

    loop = asyncio.get_running_loop()
    # sync_playwright 는 이벤트 루프 스레드에서 못 돈다 → 별도 스레드
    png = await loop.run_in_executor(None, functools.partial(render_png, html_src))
    if not png:
        return False
    try:
        from worker.social.card_generator import save_card_temp
        from worker.social.image_uploader import upload_image, is_configured

        path = save_card_temp(png, str(post.id))
        if path and is_configured():
            url = upload_image(path, str(post.id))
            if url:
                post.image_url = url
                return True
    except Exception:
        logger.exception("브리프 카드 업로드 실패: post=%s", post.id)
    return False

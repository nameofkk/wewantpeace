"""Threads 카드뉴스(캐러셀) — 1080×1350, 기사 사진 배경.

2026-09-30 두 번째 개편. 사장님 지적: "배경 이미지 있는 버전으로, 한 장에 다 넣지 말고 카드뉴스처럼".
스레드에서 실제로 운영 중인 계정 약 70곳을 로그인 없이 열어 보고 따라 만들었다.
- 표지: Politico·Daily Mail·Al Jazeera·War Monitor — 사진 전체 + 아래로 어두워지는 막 + 굵은 흰 헤드라인,
  핵심 구절만 색(Al Jazeera·War Monitor 빨강 / Horizon 노랑), 칩(Ground News "443 sources")
- 속 장: Novara Media·Times of Israel — 장마다 다른 기사 사진, 번호 원 + 굵은 소제목 + 2~3줄,
  사진 출처는 작게, 오른쪽 아래 → (Novara·Brut·Let's Talk Palestine 공통)
- 마지막 장: Let's Talk Palestine(출처 목록) + Horizon Geopolitics·Zeteo(구독·전문 보기 CTA)
"""
from __future__ import annotations

import base64
import html as _html
import logging
from datetime import datetime, timezone
from io import BytesIO

logger = logging.getLogger(__name__)

W, H = 1080, 1350
ACCENT = "#FFD23F"

_FONTS = "https://fonts.googleapis.com/css2?family=Inter:wght@500;600;800;900&display=swap"

_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:1080px;height:1350px;overflow:hidden;background:#0c0d10;color:#fff;
  font-family:'Inter','Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased}
.bg{position:absolute;inset:0;background-size:cover;background-position:center 30%}
.bg.none{background:radial-gradient(120% 90% at 30% 20%,#2a2f38 0%,#101216 70%)}
.shade{position:absolute;inset:0;background:linear-gradient(to bottom,
  rgba(0,0,0,.45) 0%,rgba(0,0,0,0) 20%,rgba(0,0,0,.05) 38%,rgba(0,0,0,.78) 64%,rgba(0,0,0,.93) 100%)}
.shade.heavy{background:linear-gradient(to bottom,
  rgba(0,0,0,.5) 0%,rgba(0,0,0,.1) 22%,rgba(0,0,0,.35) 42%,rgba(0,0,0,.88) 62%,rgba(0,0,0,.95) 100%)}
.top{position:absolute;left:64px;right:64px;top:56px;display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:900;font-size:26px;letter-spacing:.08em}
.page{font-weight:600;font-size:24px;color:rgba(255,255,255,.75)}
.content{position:absolute;left:64px;right:64px;bottom:130px}
.chips{display:flex;gap:12px;margin-bottom:26px;flex-wrap:wrap}
.chip{font-weight:800;font-size:24px;letter-spacing:.06em;text-transform:uppercase;padding:9px 16px;border-radius:6px}
.chip.cc{background:rgba(0,0,0,.55);border:2px solid rgba(255,255,255,.35)}
.chip.cc::before{content:'';display:inline-block;width:12px;height:12px;border-radius:50%;background:#FF3B30;margin-right:10px;vertical-align:1px}
.chip.src{background:#fff;color:#111}
h1{font-weight:900;font-size:86px;line-height:1.04;letter-spacing:-.025em;text-wrap:balance}
h1 em{font-style:normal;color:""" + ACCENT + """}
.dek{margin-top:24px;font-weight:500;font-size:34px;line-height:1.32;color:rgba(255,255,255,.88)}
.label{display:flex;align-items:center;gap:20px;margin-bottom:24px}
.num{width:60px;height:60px;border:3px solid #fff;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:30px;flex:none}
.label span{font-weight:900;font-size:50px;letter-spacing:-.015em}
.body{font-weight:500;font-size:42px;line-height:1.36}
.foot{position:absolute;left:64px;right:64px;bottom:44px;display:flex;justify-content:space-between;align-items:center}
.credit{font-size:20px;color:rgba(255,255,255,.62);font-weight:500}
.arrow{width:64px;height:64px;border:3px solid #fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:34px;font-weight:600}
.end .bg{filter:blur(18px) brightness(.45);transform:scale(1.1)}
.end .content{top:150px;bottom:130px;display:flex;flex-direction:column;justify-content:center}
.end h2{font-weight:800;font-size:28px;letter-spacing:.12em;text-transform:uppercase;color:rgba(255,255,255,.7);margin-bottom:26px}
.end ul{list-style:none;font-size:42px;line-height:1.5;font-weight:600}
.end ul li::before{content:'\\2014  ';color:rgba(255,255,255,.45)}
.end .rule{height:2px;background:rgba(255,255,255,.25);margin:56px 0}
.end .cta{font-weight:900;font-size:74px;line-height:1.08;letter-spacing:-.02em;text-wrap:balance}
.end .url{margin-top:22px;font-weight:800;font-size:36px;color:""" + ACCENT + """}
.end .note{margin-top:18px;font-size:28px;color:rgba(255,255,255,.7);font-weight:500}
"""

# 긴 문장이 위쪽 머리글과 겹치면 글자를 줄인다 (문장 길이는 AI 가 정해서 매번 다르다)
_FIT_JS = """
(() => {
  const c = document.querySelector('.content'); if (!c) return;
  const shrink = (sel, step) => document.querySelectorAll(sel).forEach(el => {
    el.style.fontSize = (parseFloat(getComputedStyle(el).fontSize) - step) + 'px'; });
  // 끝 장은 content 가 고정 상자라 안쪽 넘침(scrollHeight)으로 본다
  const over = () => c.getBoundingClientRect().top < 150 || c.getBoundingClientRect().bottom > 1230
    || c.scrollHeight > c.clientHeight + 1;
  for (let i = 0; i < 16 && over(); i++) {
    shrink('h1', 4); shrink('.body', 2); shrink('.dek', 1.5); shrink('.end ul', 1.5); shrink('.end .cta', 2);
  }
})();
"""


def _e(s) -> str:
    return _html.escape(str(s or ""))


# ── 사진 ─────────────────────────────────────────────────────────────────────

def fetch_photo(url: str) -> str | None:
    """기사 사진을 받아 data URI 로. 핫링크 차단·깨진 이미지·작은 썸네일은 버린다."""
    try:
        import httpx
        from PIL import Image

        r = httpx.get(url, timeout=10.0, follow_redirects=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
        })
        if r.status_code != 200 or len(r.content) < 8000:
            return None
        im = Image.open(BytesIO(r.content)).convert("RGB")
        if im.width < 480 or im.height < 300:
            return None
        if im.width > 1400:
            im = im.resize((1400, int(im.height * 1400 / im.width)))
        buf = BytesIO()
        im.save(buf, "JPEG", quality=84)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def load_photos(photos: list[tuple[str, str]], want: int) -> list[tuple[str, str]]:
    """(url, 출처) 목록에서 받아지는 사진을 want 장까지. 모자라면 있는 사진을 돌려 쓴다."""
    ok: list[tuple[str, str]] = []
    for url, credit in photos:
        uri = fetch_photo(url)
        if uri:
            ok.append((uri, credit))
        if len(ok) >= want:
            break
    if not ok:
        return [("", "")] * want
    return [ok[i % len(ok)] for i in range(want)]


# ── 장 ───────────────────────────────────────────────────────────────────────

def _page(inner: str, photo: str, *, shade: str = "", cls: str = "", pos: str = "center 30%") -> str:
    bg = (f"<div class='bg' style=\"background-image:url('{photo}');background-position:{pos}\"></div>"
          if photo else "<div class='bg none'></div>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<link rel='stylesheet' href='{_FONTS}'><style>{_CSS}</style></head>"
        f"<body class='{cls}'>{bg}<div class='shade {shade}'></div>{inner}</body></html>"
    )


def _top(i: int, n: int) -> str:
    return f"<div class='top'><div class='brand'>WEWANTPEACE</div><div class='page'>{i}/{n}</div></div>"


def _foot(credit: str, arrow: bool = True) -> str:
    c = f"Photo: {_e(credit)}" if credit else ""
    a = "<div class='arrow'>&rarr;</div>" if arrow else ""
    return f"<div class='foot'><div class='credit'>{c}</div>{a}</div>"


def _headline_html(headline: str, highlight: str) -> str:
    h = _e(headline)
    hl = _e(highlight)
    if hl:
        k = h.lower().find(hl.lower())
        if k >= 0:
            h = f"{h[:k]}<em>{h[k:k + len(hl)]}</em>{h[k + len(hl):]}"
    return h


def cover_html(*, headline: str, highlight: str = "", dek: str = "", chips: list[tuple[str, str]],
               photo: str, credit: str, i: int, n: int) -> str:
    chip_html = "".join(f"<div class='chip {k}'>{_e(t)}</div>" for k, t in chips if t)
    inner = (
        _top(i, n)
        + "<div class='content'>"
        + f"<div class='chips'>{chip_html}</div>"
        + f"<h1>{_headline_html(headline, highlight)}</h1>"
        + (f"<div class='dek'>{_e(dek)}</div>" if dek else "")
        + "</div>" + _foot(credit)
    )
    return _page(inner, photo)


def point_html(*, num: int, label: str, body: str, photo: str, credit: str, i: int, n: int,
               pos: str = "center 30%") -> str:
    inner = (
        _top(i, n)
        + "<div class='content'>"
        + f"<div class='label'><div class='num'>{num}</div><span>{_e(label)}</span></div>"
        + f"<div class='body'>{_e(body)}</div>"
        + "</div>" + _foot(credit)
    )
    return _page(inner, photo, shade="heavy", pos=pos)


def end_html(*, lines: list[str], heading: str, country: str, cc: str, photo: str, i: int, n: int) -> str:
    items = "".join(f"<li>{_e(s)}</li>" for s in lines)
    cta = f"Get a weekly brief on {_e(country)}" if country else "Get a weekly conflict brief by email"
    url = "wewantpeace.live/brief" + (f"?c={cc.upper()}" if cc else "")
    inner = (
        _top(i, n)
        + "<div class='content'>"
        + f"<h2>{_e(heading)}</h2><ul>{items}</ul>"
        + "<div class='rule'></div>"
        + f"<div class='cta'>{cta}</div><div class='url'>{_e(url)}</div>"
        + "<div class='note'>One email a week. Free. Unsubscribe any time.</div>"
        + "</div>" + _foot("", arrow=False)
    )
    return _page(inner, photo, cls="end")


def alert_slides(brief: dict, *, country: str, cc: str, n_sources: int, source_names: list[str],
                 photos: list[tuple[str, str]], when: datetime | None = None) -> list[str]:
    """단건 브리프 5장: 표지 / 무슨 일 / 왜 중요 / 지켜볼 점 / 출처·구독."""
    points = [(lbl, brief.get(k)) for lbl, k in
              (("What happened", "what"), ("Why it matters", "why"), ("What to watch", "watch")) if brief.get(k)]
    n = 2 + len(points)
    pics = load_photos(photos, 1 + len(points))
    date = (when or datetime.now(timezone.utc)).strftime("%b %d").upper()
    slides = [cover_html(
        headline=brief["headline"], highlight=brief.get("highlight", ""), dek=brief.get("dek", ""),
        chips=[("cc", f"{country} · {date}" if country else date), ("src", f"{n_sources} sources")],
        photo=pics[0][0], credit=pics[0][1], i=1, n=n,
    )]
    for k, (label, body) in enumerate(points):
        photo, credit = pics[k + 1]
        # 같은 사진을 돌려 쓸 때는 잘리는 위치를 바꿔 다른 장처럼 보이게
        pos = ("center 30%", "left 40%", "right 40%")[k % 3]
        slides.append(point_html(num=k + 1, label=label, body=body, photo=photo, credit=credit,
                                 i=k + 2, n=n, pos=pos))
    shown = source_names[:6]
    lines = list(shown) + ([f"and {n_sources - len(shown)} more"] if n_sources > len(shown) else [])
    slides.append(end_html(lines=lines, heading=f"{n_sources} independent sources", country=country, cc=cc,
                           photo=pics[0][0], i=n, n=n))
    return slides


def list_slides(*, title: str, dek: str, kicker: str, items: list[dict]) -> list[str]:
    """일간·주간 요약: 표지 + 이슈마다 한 장 + 끝 장. items: {country, headline, meta, photos}"""
    n = len(items) + 2
    pics = [load_photos(it.get("photos") or [], 1)[0] for it in items]
    # 표지는 1번 이슈의 두 번째 사진 — 같은 사진이 표지와 2장째에 연달아 나오지 않게
    first_two = load_photos((items[0].get("photos") or [])[1:], 1)[0] if items else ("", "")
    cover_pic = first_two if first_two[0] else pics[0]
    slides = [cover_html(headline=title, dek=dek, chips=[("cc", kicker)], photo=cover_pic[0],
                         credit=cover_pic[1], i=1, n=n)]
    for k, it in enumerate(items):
        slides.append(point_html(num=k + 1, label=it["country"], body=f"{it['headline']} ({it['meta']})",
                                 photo=pics[k][0], credit=pics[k][1], i=k + 2, n=n))
    slides.append(end_html(lines=[f"{it['country']}: {it['meta']}" for it in items], heading="In this brief",
                           country="", cc="", photo=pics[0][0], i=n, n=n))
    return slides


# ── 렌더·업로드 ───────────────────────────────────────────────────────────────

def render_pngs(htmls: list[str]) -> list[bytes]:
    """Playwright 로 장마다 PNG. 한 장이라도 실패하면 빈 목록 (반쪽짜리 캐러셀은 안 올린다)."""
    try:
        from playwright.sync_api import sync_playwright
        from worker.social.card_html_generator import _CHROMIUM_ARGS

        out = []
        with sync_playwright() as p:
            browser = p.chromium.launch(args=_CHROMIUM_ARGS)
            try:
                page = browser.new_page(viewport={"width": W, "height": H})
                for src in htmls:
                    try:
                        page.set_content(src, wait_until="networkidle", timeout=15000)
                    except Exception:
                        pass
                    page.evaluate("() => document.fonts.ready")
                    page.evaluate(_FIT_JS)
                    out.append(page.screenshot(clip={"x": 0, "y": 0, "width": W, "height": H}, type="png"))
            finally:
                browser.close()
        return out
    except Exception:
        logger.exception("카드뉴스 렌더 실패")
        return []


async def attach_carousel(post, htmls: list[str]) -> bool:
    """장마다 그려 R2 에 올리고 post.image_urls / post.image_url(표지) 에 넣는다."""
    import asyncio
    import functools

    loop = asyncio.get_running_loop()
    # 사진 받기·렌더 둘 다 동기 작업이라 별도 스레드 (sync_playwright 는 이벤트 루프 안에서 못 돈다)
    pngs = await loop.run_in_executor(None, functools.partial(render_pngs, htmls))
    if not pngs:
        return False
    try:
        from worker.social.card_generator import save_card_temp
        from worker.social.image_uploader import upload_image, is_configured

        if not is_configured():
            return False
        urls = []
        for k, png in enumerate(pngs, 1):
            path = save_card_temp(png, f"{post.id}-{k}")
            url = upload_image(path, f"{post.id}-{k}") if path else None
            if not url:
                return False
            urls.append(url)
        post.image_urls = urls
        post.image_url = urls[0]
        return True
    except Exception:
        logger.exception("카드뉴스 업로드 실패: post=%s", post.id)
        return False

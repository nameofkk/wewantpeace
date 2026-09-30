"""주간 브리핑 그리기 — 지도·차트 PNG, 메일 HTML(표 기반·인라인 스타일), 텍스트판.

디자인 근거 (2026-10-01, 실제 메일 원본 27개를 캡처해 보고 치수를 잰 것):
- 영어판 뼈대는 NYT The Morning (390px 폭 실측): 좌우 여백 16px, 가운데 제호, 날짜 Georgia 12px,
  굵은 세리프 인사말, 두꺼운 검정 줄로 기사 구분, 헤드라인 28/31px 굵은 세리프, 본문 Georgia 17/25px #333,
  사진 전폭 + 캡션 13px #666 · 사진 출처 11px #888, "FOUR MORE BIG STORIES" 산세리프 굵게 17px,
  번호 헤드라인 24/31px.
- 한국어판 글자는 뉴닉 데일리 (실측): 좌우 여백 12px, 항목 "분야 | 굵은 제목" 16/27px, 본문 14/24px #333,
  사진 16:9 + 출처 12px #B6BBBF 오른쪽 정렬, 강조 링크 굵게.
- 지도+번호 목록, 기사 옆 자체 차트는 Semafor Flagship.
- 사진 위에 글자를 얹은 머리 이미지·알약 칩·색 테두리 카드·어두운 배경은 쓰지 않는다 (실제 뉴스레터 어디에도 없었다).
- Gmail 은 <style> 을 걷어내는 경우가 많아 전부 인라인 스타일 + 표 레이아웃.
"""
from __future__ import annotations

import html as _html
import json
import logging
import math
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SITE = "https://www.wewantpeace.live"
API = os.getenv("PUBLIC_API_BASE", "https://api.wewantpeace.live").rstrip("/")
ASSETS = Path(__file__).parent / "assets"

ACCENT = "#B3261E"      # 강조색 하나 (라벨·링크·번호)
INK = "#000000"
BODY = "#333333"
GRAY = "#666666"
LIGHT = "#888888"
RULE = "#DDDDDD"
SERIF = "Georgia,'Times New Roman',serif"
SANS_EN = "Arial,Helvetica,sans-serif"
SANS_KO = "'Apple SD Gothic Neo','AppleSDGothic','Malgun Gothic','맑은 고딕','Noto Sans KR',sans-serif"

# 언어별 글자 체계 (en = NYT The Morning 실측, ko = 뉴닉 실측)
TYPE = {
    "en": {"pad": 16, "font": SERIF, "label": SANS_EN, "title": 34, "intro": (18, 27, 700), "h1": (28, 31),
           "h2": (24, 31), "body": (17, 25), "cap": 13, "credit": 11, "list": (17, 25)},
    "ko": {"pad": 12, "font": SANS_KO, "label": SANS_KO, "title": 30, "intro": (15, 26, 400), "h1": (22, 33),
           "h2": (17, 28), "body": (15, 26), "cap": 12, "credit": 12, "list": (15, 25)},
}

ADVISORY = {
    1: ("Level 1 · exercise normal precautions", "1단계 · 일반 주의"),
    2: ("Level 2 · exercise increased caution", "2단계 · 주의 강화"),
    3: ("Level 3 · reconsider travel", "3단계 · 여행 재고"),
    4: ("Level 4 · do not travel", "4단계 · 여행 금지"),
}

T = {
    "en": {
        "title": "The Weekly Brief", "view": "View in browser", "other_lang": "한국어로 보기",
        "switch_top": "한국어로 받기", "desk": "By the WeWantPeace desk",
        "map": "THIS WEEK", "more": "FOUR MORE BIG STORIES", "else": "HERE'S WHAT ELSE HAPPENED",
        "yours": "COUNTRIES YOU FOLLOW", "why": "Why it matters:", "watch": "What to watch:",
        "reported": "Reported by", "timeline": "Full timeline", "outlets": "independent outlets",
        "chart_title": "Reports on this story per day", "chart_src": "Chart: WeWantPeace · Source: {n} independent outlets",
        "photo": "Photo", "stories_n": "{n} stories this week", "no_story": "No story reported by three or more outlets this week.",
        "talks": "Talks", "markets": "Oil",
        "brent": "Brent crude closed at ${now:.2f}, {dir} {pct:.1f}% from a week earlier.",
        "up": "up", "down": "down",
        "useful": "Was this useful?", "yes": "Yes", "no": "Not really",
        "app": "Get one alert when a country you follow flares up, not every headline:",
        "app_cta": "the WeWantPeace Android app",
        "how": "How we choose stories:",
        "how_body": "WeWantPeace groups reports from more than 100 outlets into stories. A story appears here only if at least three independent outlets reported it this week. Photos belong to the outlets credited.",
        "why_get_user": "You get this because you agreed to receive WeWantPeace news.",
        "why_get_sub": "You get this because you asked for the weekly brief.",
        "switch": "Always send me the Korean edition", "unsub": "Unsubscribe",
    },
    "ko": {
        "title": "주간 브리핑", "view": "잘림 없이 읽기", "other_lang": "Read in English",
        "switch_top": "Get this in English", "desk": "WeWantPeace 편집팀",
        "map": "이번 주 지도", "more": "이번 주 주요 뉴스", "else": "이번 주 다른 소식",
        "yours": "내가 고른 나라", "why": "왜 중요해?", "watch": "앞으로 볼 것",
        "reported": "보도", "timeline": "타임라인 자세히 보기", "outlets": "개 매체",
        "chart_title": "이 사건 하루 보도 건수", "chart_src": "차트: WeWantPeace · 독립 매체 {n}곳 보도",
        "photo": "사진", "stories_n": "이번 주 {n}건", "no_story": "이번 주 매체 3곳 이상이 보도한 기사가 없어요.",
        "talks": "협상", "markets": "유가",
        "brent": "브렌트유는 배럴당 {now:.2f}달러로 한 주 전보다 {pct:.1f}% {dir}어요.",
        "up": "올랐", "down": "내렸",
        "useful": "이번 브리핑 어땠나요?", "yes": "유용했어요", "no": "별로예요",
        "app": "고른 나라에 큰일이 생기면 한 번만 알려드려요.",
        "app_cta": "안드로이드 앱 받기",
        "how": "기사를 고르는 방법.",
        "how_body": "WeWantPeace는 100곳이 넘는 매체의 보도를 사건 단위로 묶어요. 이번 주 서로 다른 매체 3곳 이상이 보도한 사건만 실어요. 사진 저작권은 표기된 매체에 있어요.",
        "why_get_user": "WeWantPeace 소식 받기에 동의하셔서 보내드려요.",
        "why_get_sub": "주간 브리핑을 신청하셔서 보내드려요.",
        "switch": "앞으로 영어판으로 받기", "unsub": "수신거부",
    },
}

_WD_KO = ["월", "화", "수", "목", "금", "토", "일"]


def esc(s) -> str:
    return _html.escape(str(s or ""), quote=True)


def country(cc: str | None, lang: str) -> str:
    if not cc:
        return ""
    if lang == "ko":
        from worker.processor.clusterer import _COUNTRY_NAMES_KO
        return _COUNTRY_NAMES_KO.get(cc.upper(), cc.upper())
    from worker.social.brief import country_name
    return country_name(cc)


def issue_date(data: dict, lang: str) -> str:
    """발행일 (end 다음 날 아침 발송이라 end 날짜를 쓴다)."""
    d = datetime.fromisoformat(data["end"])
    if lang == "ko":
        return f"{d:%Y.%m.%d}. {_WD_KO[d.weekday()]}요일"
    return f"{d:%B} {d.day}, {d.year}"


def date_range(data: dict, lang: str) -> str:
    s, e = datetime.fromisoformat(data["start"]), datetime.fromisoformat(data["end"])
    if lang == "ko":
        return f"{s.month}월 {s.day}일 – {e.month}월 {e.day}일"
    return f"{s:%b} {s.day} – {e:%b} {e.day}"


def story_url(cluster_id: str, week: str, lang: str) -> str:
    return f"{SITE}/issues/{cluster_id}?ref=weekly&utm_source=newsletter&utm_medium=email&utm_campaign={week}&lang={lang}"


def web_url(week: str, lang: str) -> str:
    return f"{SITE}/weekly/{week}?lang={lang}"


def sources_line(names: list[str], n: int, lang: str) -> str:
    shown = names[:3]
    rest = max(0, n - len(shown))
    if lang == "ko":
        return ", ".join(shown) + (f" 외 {rest}곳" if rest else "")
    return ", ".join(shown) + (f" and {rest} more" if rest else "")


# ── 이미지: 지도·차트 ────────────────────────────────────────────────────────

MAP_W, MAP_H = 1200, 640


def _merc(lon: float, lat: float) -> tuple[float, float]:
    lat = max(min(lat, 80), -80)
    return lon, math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def map_svg(data: dict) -> str:
    """번호 핀 지도 (Semafor 'The World Today' 식). 외부 요청 없이 그린다."""
    pins = [(i + 1, s["lon"], s["lat"], s["cc"]) for i, s in enumerate(data["stories"])
            if s.get("lat") is not None and s.get("lon") is not None]
    geo = json.loads((ASSETS / "countries-110m.geojson").read_text(encoding="utf-8"))
    story_cc = {s["cc"] for s in data["stories"] if s.get("cc")}
    if pins:
        xs = [_merc(p[1], p[2])[0] for p in pins]
        ys = [_merc(p[1], p[2])[1] for p in pins]
        minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    else:
        minx, maxx, miny, maxy = -20, 60, 0, 60
    span_x, span_y = max(maxx - minx, 40), max(maxy - miny, 22)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    scale = min(MAP_W / (span_x * 1.35), MAP_H / (span_y * 1.35))

    def proj(lon, lat):
        x, y = _merc(lon, lat)
        return MAP_W / 2 + (x - cx) * scale, MAP_H / 2 - (y - cy) * scale

    paths = []
    for f in geo["features"]:
        g = f.get("geometry") or {}
        iso2 = ((f.get("properties") or {}).get("cc") or "").upper()
        polys = g.get("coordinates") or []
        if g.get("type") == "Polygon":
            polys = [polys]
        d = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in (proj(lo, la) for lo, la in ring)) + "Z"
                    for poly in polys for ring in poly)
        fill = "#E9C9C6" if iso2 in story_cc else "#E6E6E1"
        paths.append(f'<path d="{d}" fill="{fill}" stroke="#FFFFFF" stroke-width="1.2"/>')
    pin_svg = []
    for n, lon, lat, cc in pins:
        x, y = proj(lon, lat)
        pin_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="24" fill="{ACCENT}" stroke="#fff" stroke-width="4"/>'
            f'<text x="{x:.1f}" y="{y + 9:.1f}" text-anchor="middle" font-size="26" font-weight="700" '
            f'font-family="Georgia,serif" fill="#fff">{n}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{MAP_W}" height="{MAP_H}" viewBox="0 0 {MAP_W} {MAP_H}">'
            f'<rect width="100%" height="100%" fill="#F7F7F4"/>{"".join(paths)}{"".join(pin_svg)}</svg>')


CHART_W, CHART_H = 1200, 600


def chart_svg(story: dict, lang: str) -> str:
    """이 사건 하루 보도 건수 막대 차트 (Semafor 식: 제목·축·출처 줄·검정 띠)."""
    t = T[lang]
    days = story.get("daily") or []
    font = "Arial,Helvetica,sans-serif" if lang == "en" else "'Noto Sans KR','Malgun Gothic',sans-serif"
    top, left, right, bottom = 90, 80, 40, 120
    w, h = CHART_W - left - right, CHART_H - top - bottom
    peak = max([d["n"] for d in days] + [1])
    step = 10 ** max(0, len(str(peak)) - 1)
    ymax = math.ceil(peak / step) * step or 1
    grid, bars = [], []
    for k in range(5):
        v = ymax * k / 4
        y = top + h - h * k / 4
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + w}" y2="{y:.1f}" stroke="#DDDDDD" stroke-width="2"/>'
                    f'<text x="{left - 14}" y="{y + 9:.1f}" text-anchor="end" font-size="26" fill="#666" font-family="{font}">{int(v)}</text>')
    n = max(len(days), 1)
    bw = w / n * 0.62
    for i, d in enumerate(days):
        x = left + w / n * i + (w / n - bw) / 2
        bh = h * d["n"] / ymax
        color = ACCENT if i == n - 1 else "#3D3D3D"
        dt = datetime.fromisoformat(d["date"])
        label = f"{dt.month}/{dt.day}" if lang == "ko" else f"{dt:%b} {dt.day}"
        bars.append(f'<rect x="{x:.1f}" y="{top + h - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{color}"/>'
                    f'<text x="{x + bw / 2:.1f}" y="{top + h + 40}" text-anchor="middle" font-size="26" fill="#666" font-family="{font}">{label}</text>')
    src = t["chart_src"].format(n=story.get("n_sources", 0))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{CHART_W}" height="{CHART_H}" viewBox="0 0 {CHART_W} {CHART_H}">'
            f'<rect width="100%" height="100%" fill="#FFFFFF"/>'
            f'<text x="{left - 60}" y="52" font-size="32" font-weight="700" fill="#000" font-family="{font}">{esc(t["chart_title"])}</text>'
            f'{"".join(grid)}{"".join(bars)}'
            f'<text x="{left - 60}" y="{CHART_H - 42}" font-size="24" fill="#666" font-family="{font}">{esc(src)}</text>'
            f'<rect x="{left - 60}" y="{CHART_H - 26}" width="{CHART_W - left + 60 - right}" height="26" fill="#000"/>'
            f'<text x="{left - 48}" y="{CHART_H - 6}" font-size="18" font-weight="700" letter-spacing="2" fill="#fff" font-family="Arial,sans-serif">WEWANTPEACE</text>'
            f'</svg>')


def render_pngs(pages: list[tuple[str, int, int]]) -> list[bytes | None]:
    from playwright.sync_api import sync_playwright
    try:
        from worker.social.card_html_generator import _CHROMIUM_ARGS
    except Exception:
        _CHROMIUM_ARGS = []
    out: list[bytes | None] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=_CHROMIUM_ARGS)
        try:
            for src, w, h in pages:
                try:
                    page = browser.new_page(viewport={"width": w, "height": h})
                    page.set_content(src, wait_until="networkidle", timeout=20000)
                    page.evaluate("() => document.fonts.ready")
                    out.append(page.screenshot(clip={"x": 0, "y": 0, "width": w, "height": h}, type="png"))
                    page.close()
                except Exception:
                    logger.exception("주간 브리핑 이미지 렌더 실패")
                    out.append(None)
        finally:
            browser.close()
    return out


def _store(data_bytes: bytes, fname: str, ext: str, upload: bool, save_dir: str | None) -> str | None:
    if upload:
        from worker.social.card_generator import save_card_temp
        from worker.social.image_uploader import upload_image
        path = save_card_temp(data_bytes, fname)
        ctype = "image/jpeg" if ext == "jpg" else "image/png"
        return upload_image(path, fname, content_type=ctype, ext=ext) if path else None
    d = Path(save_dir or "/tmp")
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{fname}.{ext}").write_bytes(data_bytes)
    return (d / f"{fname}.{ext}").resolve().as_uri()


def _first_photo(story: dict) -> tuple[str | None, dict | None]:
    """받아지는 첫 사진 (data URI, 원래 항목). 핫링크 차단·작은 썸네일은 다음 장으로."""
    from worker.social.brief_card import fetch_photo
    for ph in story.get("photos") or ([story["photo"]] if story.get("photo") else []):
        uri = fetch_photo(ph["url"])
        if uri:
            return uri, ph
    return None, None


def build_images(data: dict, upload: bool = True, save_dir: str | None = None) -> dict:
    """1~3번 기사 사진을 우리 저장소로 옮기고, 지도·1번 기사 차트(영·한)를 그린다.

    기사 사진을 매체 주소 그대로 메일에 넣으면 핫링크를 막는 곳에서 빈칸이 된다(9/30 드라이런).
    """
    import base64

    stories = data.get("stories") or []
    if not stories:
        return {}
    stamp = datetime.utcnow().strftime("%m%d%H%M")
    base = f"weekly-{data['week_key']}"
    for i in range(min(3, len(stories))):
        uri, ph = _first_photo(stories[i])
        if uri and ph:
            url = _store(base64.b64decode(uri.split(",", 1)[1]), f"{base}-s{i + 1}-{stamp}", "jpg", upload, save_dir)
            stories[i]["photo"] = {"url": url, "credit": ph.get("credit")} if url else None
        else:
            stories[i]["photo"] = None
    pages = [(f"<html><body style='margin:0'>{map_svg(data)}</body></html>", MAP_W, MAP_H)]
    names = ["map"]
    if stories[0].get("daily") and sum(d["n"] for d in stories[0]["daily"]) > 0:
        for lang in ("en", "ko"):
            pages.append((f"<html><body style='margin:0'>{chart_svg(stories[0], lang)}</body></html>", CHART_W, CHART_H))
            names.append(f"chart_{lang}")
    images: dict = {}
    for name, png in zip(names, render_pngs(pages)):
        if png:
            url = _store(png, f"{base}-{name}-{stamp}", "png", upload, save_dir)
            if url:
                images[name] = url
    return images


# ── 메일 HTML ────────────────────────────────────────────────────────────────

def _row(inner: str, pad: int, top: int = 0, bottom: int = 0) -> str:
    return f'<tr><td style="padding:{top}px {pad}px {bottom}px;">{inner}</td></tr>'


def _para(text: str, ty: dict, color: str = BODY, weight: int = 400, margin: int = 16) -> str:
    fs, lh = ty["body"]
    return (f'<p style="margin:0 0 {margin}px;font-family:{ty["font"]};font-size:{fs}px;line-height:{lh}px;'
            f'color:{color};font-weight:{weight};word-break:keep-all;">{text}</p>')


def _label(text: str, ty: dict, lang: str) -> str:
    size = 17 if lang == "en" else 16
    return (f'<div style="font-family:{ty["label"]};font-size:{size}px;line-height:25px;font-weight:700;color:{INK};'
            f'letter-spacing:{".02em" if lang == "en" else "0"};">{esc(text)}</div>')


def _photo(photo: dict | None, ty: dict, lang: str, alt: str) -> str:
    if not photo or not photo.get("url"):
        return ""
    credit = photo.get("credit") or ""
    if lang == "ko":
        cap = (f'<div style="font-family:{ty["font"]};font-size:12px;line-height:20px;color:#B6BBBF;text-align:right;">'
               f'©{esc(credit)}</div>') if credit else ""
    else:
        cap = (f'<div style="font-family:{SERIF};font-size:11px;line-height:16px;color:{LIGHT};margin-top:4px;">'
               f'{esc(credit)}</div>') if credit else ""
    return (f'<img src="{esc(photo["url"])}" width="568" alt="{esc(alt)}" '
            f'style="display:block;width:100%;max-width:568px;height:auto;border:0;margin:0 0 6px;">{cap}')


def _run_in(label: str, text: str, ty: dict) -> str:
    return _para(f'<b style="color:{INK};">{esc(label)}</b> {esc(text)}', ty)


def _link(text: str, url: str, ty: dict) -> str:
    fs, lh = ty["body"]
    return (f'<a href="{esc(url)}" style="font-family:{ty["font"]};font-size:{fs - 1}px;line-height:{lh}px;'
            f'color:{ACCENT};font-weight:700;text-decoration:underline;">{esc(text)} →</a>')


def _sources(s: dict, lang: str, ty: dict) -> str:
    t = T[lang]
    src = sources_line(s.get("source_names") or [], s["n_sources"], lang)
    return (f'<div style="font-family:{ty["label"]};font-size:13px;line-height:19px;color:{GRAY};margin:0 0 6px;">'
            f'{esc(t["reported"])}: {esc(src)}</div>')


def _bar() -> str:
    return '<div style="height:8px;line-height:8px;font-size:0;background:#000;">&nbsp;</div>'


def _hair() -> str:
    return f'<div style="height:1px;line-height:1px;font-size:0;background:{RULE};">&nbsp;</div>'


def _lead_story(s: dict, data: dict, lang: str, ty: dict) -> str:
    t = T[lang]
    p = s[lang]
    url = story_url(s["cluster_id"], data["week_key"], lang)
    fs, lh = ty["h1"]
    head = (f'<h1 style="margin:22px 0 14px;font-family:{ty["font"]};font-size:{fs}px;line-height:{lh}px;'
            f'font-weight:700;color:{INK};word-break:keep-all;">'
            f'<a href="{esc(url)}" style="color:{INK};text-decoration:none;">{esc(p["headline"])}</a></h1>')
    body = ""
    if p.get("what"):
        body += _para(esc(p["what"]), ty)
    if p.get("why"):
        body += _run_in(t["why"], p["why"], ty)
    if p.get("watch"):
        body += _run_in(t["watch"], p["watch"], ty)
    chart = ""
    img = (data.get("images") or {}).get(f"chart_{lang}")
    if img:
        chart = (f'<img src="{esc(img)}" width="568" alt="{esc(t["chart_title"])}" '
                 f'style="display:block;width:100%;max-width:568px;height:auto;border:0;margin:6px 0 18px;">')
    return head + _photo(s.get("photo"), ty, lang, p["headline"]) + '<div style="height:14px;"></div>' + \
        body + chart + _sources(s, lang, ty) + _link(t["timeline"], url, ty)


def _more_story(i: int, s: dict, data: dict, lang: str, ty: dict) -> str:
    t = T[lang]
    p = s[lang]
    url = story_url(s["cluster_id"], data["week_key"], lang)
    fs, lh = ty["h2"]
    if lang == "ko":
        # 뉴닉 항목 제목: "분야 | 굵은 제목" — 분야 자리에 나라
        title = f'{esc(country(s["cc"], lang))} | {esc(p["headline"])}'
    else:
        title = f'{i}. {esc(p["headline"])}'
    head = (f'<h2 style="margin:26px 0 12px;font-family:{ty["font"]};font-size:{fs}px;line-height:{lh}px;'
            f'font-weight:700;color:{INK if lang == "en" else BODY};word-break:keep-all;">'
            f'<a href="{esc(url)}" style="color:inherit;text-decoration:none;">{title}</a></h2>')
    photo = _photo(s.get("photo"), ty, lang, p["headline"]) if i <= 3 else ""
    body = ""
    if p.get("what"):
        body += _para(esc(p["what"]), ty)
    if p.get("why"):
        body += _run_in(t["why"], p["why"], ty)
    if p.get("watch"):
        body += _run_in(t["watch"], p["watch"], ty)
    return head + photo + ('<div style="height:12px;"></div>' if photo else "") + body + \
        _sources(s, lang, ty) + _link(t["timeline"], url, ty)


def _bullets(items: list[str], ty: dict) -> str:
    fs, lh = ty["body"]
    return "".join(
        f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%"><tr>'
        f'<td valign="top" style="width:18px;font-family:{ty["font"]};font-size:{fs}px;line-height:{lh}px;color:{BODY};">•</td>'
        f'<td style="font-family:{ty["font"]};font-size:{fs}px;line-height:{lh}px;color:{BODY};padding-bottom:12px;word-break:keep-all;">{it}</td>'
        f'</tr></table>' for it in items)


def render_email(data: dict, lang: str, *, follow: list[str] | None = None,
                 unsubscribe_url: str | None = None, switch_url: str | None = None,
                 feedback_token: str = "", subscriber: bool = False) -> dict:
    """{subject, preheader, html, text}. follow=구독자가 고른 나라(없으면 칸 생략)."""
    t = T[lang]
    ty = TYPE[lang]
    pad = ty["pad"]
    week = data["week_key"]
    intro = (data.get("intro") or {}).get(lang) or {}
    stories = data.get("stories") or []
    images = data.get("images") or {}
    other = "en" if lang == "ko" else "ko"
    s1 = stories[0] if stories else None

    # 맨 위 작은 링크 (NYT: 12px Arial #666)
    lang_link = (f'<a href="{esc(switch_url)}" style="color:{GRAY};text-decoration:underline;">{esc(t["switch_top"])}</a>'
                 if switch_url else
                 f'<a href="{esc(web_url(week, other))}" style="color:{GRAY};text-decoration:underline;">{esc(t["other_lang"])}</a>')
    top = (f'<div style="text-align:center;font-family:{SANS_EN if lang == "en" else SANS_KO};font-size:12px;line-height:18px;color:{GRAY};">'
           f'<a href="{esc(web_url(week, lang))}" style="color:{GRAY};text-decoration:underline;">{esc(t["view"])}</a>'
           f' <span style="color:#DCDCDC;">|</span> {lang_link}</div>')

    # 제호 (NYT: 가운데, 위아래 얇은 줄, 날짜)
    mast = (_hair() +
            f'<div style="text-align:center;padding:18px 0 4px;font-family:{SANS_EN};font-size:12px;line-height:16px;'
            f'letter-spacing:.18em;font-weight:700;color:{ACCENT};">WEWANTPEACE</div>'
            f'<div style="text-align:center;font-family:{ty["font"]};font-size:{ty["title"]}px;line-height:{ty["title"] + 6}px;'
            f'font-weight:700;color:{INK};">{esc(t["title"])}</div>'
            f'<div style="text-align:center;padding:8px 0 16px;font-family:{ty["font"]};font-size:12px;line-height:16px;color:{BODY};">'
            f'{esc(issue_date(data, lang))} · {esc(date_range(data, lang))}</div>' + _hair())

    # 인사말 (NYT: 굵은 세리프 18/27 · 뉴닉: 보통 14~15)
    ifs, ilh, iw = ty["intro"]
    greet = "Good morning." if lang == "en" else "좋은 아침이에요."
    intro_text = intro.get("intro") or ""
    desk = (f'<div style="font-family:{ty["label"]};font-size:13px;line-height:18px;font-weight:600;color:{INK};margin:16px 0 10px;">'
            f'{esc(t["desk"])}</div>')
    intro_html = desk + (f'<p style="margin:0 0 18px;font-family:{ty["font"]};font-size:{ifs}px;line-height:{ilh}px;'
                         f'font-weight:{iw};color:{INK if lang == "en" else BODY};word-break:keep-all;">'
                         f'{"" if lang == "en" else "<b>"}{esc(greet)}{"" if lang == "en" else "</b>"} {esc(intro_text)}</p>')

    # 이번 주 지도 + 번호 목록 (Semafor)
    map_html = ""
    if images.get("map") and len(stories) > 1:
        lfs, llh = ty["list"]
        items = "".join(
            f'<tr><td valign="top" style="width:26px;font-family:{ty["font"]};font-size:{lfs}px;line-height:{llh}px;color:{ACCENT};font-weight:700;">{k}.</td>'
            f'<td style="font-family:{ty["font"]};font-size:{lfs}px;line-height:{llh}px;color:{INK};padding-bottom:4px;word-break:keep-all;">'
            f'{esc(s[lang].get("short") or s[lang]["headline"])}'
            f'<span style="color:{LIGHT};font-size:{lfs - 3}px;"> · {esc(country(s["cc"], lang))}</span></td></tr>'
            for k, s in enumerate(stories, 1))
        map_html = (_label(t["map"], ty, lang) +
                    f'<img src="{esc(images["map"])}" width="568" alt="" style="display:block;width:100%;max-width:568px;height:auto;border:0;margin:10px 0 12px;">'
                    f'<table role="presentation" cellpadding="0" cellspacing="0" width="100%">{items}</table>')

    lead = _lead_story(s1, data, lang, ty) if s1 else ""
    more = ""
    if len(stories) > 1:
        more = _label(t["more"], ty, lang) + "".join(_more_story(i, s, data, lang, ty) for i, s in enumerate(stories, 1) if i > 1)

    # 내가 고른 나라
    yours = ""
    if follow:
        rows = []
        for cc in follow[:3]:
            entry = (data.get("countries") or {}).get(cc)
            lv = (data.get("advisories") or {}).get(cc)
            adv = ADVISORY[lv][1 if lang == "ko" else 0] if lv in ADVISORY else ""
            line = f'<b style="color:{INK};">{esc(country(cc, lang))}</b>'
            if adv:
                line += f' <span style="color:{GRAY};font-size:13px;">({esc(adv)})</span>'
            if entry and entry.get("top"):
                top_item = entry["top"]
                u = story_url(top_item["cluster_id"], week, lang)
                line += (f'<br><a href="{esc(u)}" style="color:{BODY};text-decoration:underline;">{esc(top_item[lang]["headline"])}</a>'
                         f' <span style="color:{GRAY};font-size:13px;">· {esc(t["stories_n"].format(n=entry["n"]))}</span>')
            else:
                line += f'<br><span style="color:{GRAY};">{esc(t["no_story"])}</span>'
            rows.append(line)
        yours = _label(t["yours"], ty, lang) + '<div style="height:10px;"></div>' + _bullets(rows, ty)

    # 이번 주 다른 소식 (NYT "Here's what else is happening")
    else_items = []
    for it in (data.get("easing") or []):
        u = story_url(it["cluster_id"], week, lang)
        else_items.append(f'<b style="color:{INK};">{esc(t["talks"])} · {esc(country(it["cc"], lang))}:</b> '
                          f'<a href="{esc(u)}" style="color:{BODY};text-decoration:underline;">{esc(it[lang]["headline"])}</a>')
    for it in (data.get("also") or []):
        u = story_url(it["cluster_id"], week, lang)
        else_items.append(f'<b style="color:{INK};">{esc(country(it["cc"], lang))}:</b> '
                          f'<a href="{esc(u)}" style="color:{BODY};text-decoration:underline;">{esc(it[lang]["headline"])}</a>')
    br = (data.get("numbers") or {}).get("brent")
    if br and br.get("pct") is not None:
        direction = t["up"] if br["pct"] > 0 else t["down"]
        else_items.append(f'<b style="color:{INK};">{esc(t["markets"])}:</b> '
                          + esc(t["brent"].format(now=br["now"], pct=abs(br["pct"]), dir=direction)))
    else_html = (_label(t["else"], ty, lang) + '<div style="height:10px;"></div>' + _bullets(else_items, ty)) if else_items else ""

    fb = f"{API}/newsletter/weekly/{week}/feedback?lang={lang}&t={esc(feedback_token)}"
    fs_b, lh_b = ty["body"]
    feedback = (f'<p style="margin:0;font-family:{ty["font"]};font-size:{fs_b}px;line-height:{lh_b}px;color:{BODY};">'
                f'{esc(t["useful"])} <a href="{fb}&v=good" style="color:{ACCENT};font-weight:700;">{esc(t["yes"])}</a>'
                f' · <a href="{fb}&v=bad" style="color:{ACCENT};font-weight:700;">{esc(t["no"])}</a></p>')
    app = (f'<p style="margin:10px 0 0;font-family:{ty["font"]};font-size:{fs_b}px;line-height:{lh_b}px;color:{BODY};word-break:keep-all;">'
           f'{esc(t["app"])} <a href="https://play.google.com/store/apps/details?id=com.wewantpeace.app&utm_source=newsletter&utm_campaign={week}" '
           f'style="color:{ACCENT};font-weight:700;">{esc(t["app_cta"])}</a></p>')

    why_get = t["why_get_sub"] if subscriber else t["why_get_user"]
    foot_links = []
    if switch_url:
        foot_links.append(f'<a href="{esc(switch_url)}" style="color:{GRAY};">{esc(t["switch"])}</a>')
    if unsubscribe_url:
        foot_links.append(f'<a href="{esc(unsubscribe_url)}" style="color:{GRAY};">{esc(t["unsub"])}</a>')
    footer = (f'<div style="font-family:{SANS_EN if lang == "en" else SANS_KO};font-size:12px;line-height:19px;color:{GRAY};">'
              f'<b style="color:{BODY};">{esc(t["how"])}</b> {esc(t["how_body"])}<br><br>{esc(why_get)} '
              f'{" · ".join(foot_links)}<br>WeWantPeace · Seoul, South Korea</div>')

    subject = intro.get("subject") or (s1[lang]["headline"] if s1 else "WeWantPeace")
    preheader = intro.get("preheader") or ""

    body_rows = [
        _row(top, pad, 14, 12),
        _row(mast, pad),
        _row(intro_html, pad),
        _row(map_html, pad, 6, 24) if map_html else "",
        _row(_bar() + lead, pad, 4, 30) if lead else "",
        _row(_bar() + '<div style="height:14px;"></div>' + more, pad, 0, 30) if more else "",
        _row(_hair() + '<div style="height:20px;"></div>' + yours, pad, 0, 20) if yours else "",
        _row(_hair() + '<div style="height:20px;"></div>' + else_html, pad, 0, 20) if else_html else "",
        _row(_hair() + '<div style="height:18px;"></div>' + feedback + app, pad, 0, 24),
        f'<tr><td style="padding:18px {pad}px 28px;background:#F4F4F4;">{footer}</td></tr>',
    ]
    html = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>{esc(subject)}</title></head>
<body style="margin:0;padding:0;background:#FFFFFF;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{esc(preheader)}&#8199;&#65279;&#847;&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;">
{''.join(r for r in body_rows if r)}
</table></td></tr></table></body></html>"""

    text_lines = [subject, "", intro_text, ""]
    for i, s in enumerate(stories, 1):
        p = s[lang]
        text_lines.append(f"{i}. {p['headline']}")
        if p.get("what"):
            text_lines.append(f"   {p['what']}")
        text_lines += [f"   {t[k]} {p[k]}" for k in ("why", "watch") if p.get(k)] + \
                      [f"   {story_url(s['cluster_id'], week, lang)}", ""]
    if unsubscribe_url:
        text_lines += [f"{t['unsub']}: {unsubscribe_url}"]
    return {"subject": subject, "preheader": preheader, "html": html, "text": "\n".join(text_lines)}

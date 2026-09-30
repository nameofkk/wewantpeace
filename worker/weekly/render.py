"""주간 브리핑 그리기 — 머리 이미지·지도 PNG, 메일 HTML(표 기반·인라인 스타일), 텍스트판.

디자인 근거 (2026-09-30 사장님 피드백 + 레퍼런스 실물 확인):
- 옛 뉴스레터에서 눈에 띈 건 어두운 사진 머리, 큰 숫자, 색 카드, 칩이었다. 모양은 살리고 숫자는
  전부 실제로 센 값으로 바꾼다(옛 "192개국 위기"는 포화된 지수였다).
- Semafor: 번호 지도 + 번호 목록 / Uppity 머니레터: 맨 위 시세 한 줄 + 세 줄 요약 /
  Axios: 굵은 라벨(Why it matters) / 뉴닉: 질문형 소제목(무슨 일이야?) 해요체.
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

INK = "#0F172A"
MUTED = "#5B6472"
LINE = "#E5E7EB"
RED = "#E5484D"
NAVY = "#0B1220"
GREEN = "#15803D"
PAGE = "#EEF0F3"
FONT = "-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR','Segoe UI',Roboto,Arial,sans-serif"

ADVISORY = {
    1: ("#DCFCE7", "#166534", "Level 1 · Normal precautions", "1단계 · 일반 주의"),
    2: ("#FEF9C3", "#854D0E", "Level 2 · Increased caution", "2단계 · 주의 강화"),
    3: ("#FFEDD5", "#9A3412", "Level 3 · Reconsider travel", "3단계 · 여행 재고"),
    4: ("#FEE2E2", "#991B1B", "Level 4 · Do not travel", "4단계 · 여행 금지"),
}

T = {
    "en": {
        "kicker": "WEEKLY BRIEF", "view": "View in browser", "other_lang": "한국어로 보기",
        "three": "The week in three lines", "map": "Where it happened", "what": "What happened",
        "why": "Why it matters", "watch": "What to watch", "reported": "Reported by", "more": "more",
        "timeline": "Full timeline", "outlets": "outlets", "also": "Also this week", "easing": "Talks and ceasefires",
        "easing_sub": "Diplomatic moves reported by at least three outlets this week.",
        "yours": "Countries you follow", "yours_sub": "The top story this week and the current US travel advisory.",
        "stories_n": "stories this week", "no_story": "No story reported by three or more outlets this week.",
        "brent": "Brent crude", "wk": "vs a week ago", "stories": "stories confirmed by 3+ outlets", "sources": "outlets read",
        "switch_top": "한국어로 받기 (Get this in Korean)", "num_src": "Source",
        "useful": "Was this useful?", "yes": "Yes", "no": "Not really",
        "app_title": "Get an alert when a country you follow flares up",
        "app_body": "The WeWantPeace app sends one alert when a story is confirmed by several outlets, not every headline.",
        "app_cta": "Get the Android app",
        "how": "How we choose stories.",
        "how_body": "WeWantPeace groups reports from more than 100 outlets into stories. A story appears here only if at least three independent outlets reported it this week. Photos belong to the outlets credited.",
        "why_get_user": "You get this because you agreed to receive WeWantPeace news.",
        "why_get_sub": "You get this because you asked for the weekly brief.",
        "switch": "Always send me the Korean edition", "unsub": "Unsubscribe",
        "date_fmt": "%b %d",
    },
    "ko": {
        "kicker": "주간 브리핑", "view": "브라우저로 보기", "other_lang": "Read in English",
        "three": "이번 주 세 줄 요약", "map": "어디서 일어났나", "what": "무슨 일이야?",
        "why": "왜 중요해?", "watch": "앞으로 볼 것", "reported": "보도", "more": "곳",
        "timeline": "타임라인 보기", "outlets": "개 매체", "also": "이번 주 다른 소식", "easing": "협상·휴전 소식",
        "easing_sub": "이번 주 매체 3곳 이상이 보도한 외교 움직임이에요.",
        "yours": "내가 고른 나라", "yours_sub": "이번 주 대표 기사와 미 국무부 여행경보 단계예요.",
        "stories_n": "건", "no_story": "이번 주 매체 3곳 이상이 보도한 기사가 없어요.",
        "brent": "브렌트유", "wk": "지난주 대비", "stories": "매체 3곳 이상 확인한 이슈", "sources": "읽은 매체",
        "switch_top": "Get this in English", "num_src": "출처",
        "useful": "이번 브리핑 어땠나요?", "yes": "유용했어요", "no": "별로예요",
        "app_title": "고른 나라에 큰일이 생기면 바로 알려드려요",
        "app_body": "여러 매체가 확인한 소식만 한 번씩 알려드려요. 헤드라인마다 울리지 않아요.",
        "app_cta": "안드로이드 앱 받기",
        "how": "기사를 고르는 방법.",
        "how_body": "WeWantPeace는 100곳이 넘는 매체의 보도를 사건 단위로 묶어요. 이번 주 서로 다른 매체 3곳 이상이 보도한 사건만 여기에 실어요. 사진 저작권은 표기된 매체에 있어요.",
        "why_get_user": "WeWantPeace 소식 받기에 동의하셔서 보내드려요.",
        "why_get_sub": "주간 브리핑을 신청하셔서 보내드려요.",
        "switch": "앞으로 영어판으로 받기", "unsub": "수신거부",
        "date_fmt": "%m월 %d일",
    },
}

COUNTRY_KO_FALLBACK = {}


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


def date_range(data: dict, lang: str) -> str:
    fmt = T[lang]["date_fmt"]
    s = datetime.fromisoformat(data["start"]).strftime(fmt)
    e = datetime.fromisoformat(data["end"]).strftime(fmt)
    if lang == "ko":
        s, e = s.lstrip("0").replace("월 0", "월 "), e.lstrip("0").replace("월 0", "월 ")
    return f"{s} – {e}"


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


# ── 이미지: 머리(사진+헤드라인)·지도 ─────────────────────────────────────────

HERO_W, HERO_H = 1200, 760


def hero_html(data: dict, lang: str, photo_data_uri: str | None) -> str:
    s = data["stories"][0]
    t = T[lang]
    part = s[lang]
    num = s.get("number")
    big = esc(num["value"]) if num else str(s["n_sources"])
    big_label = esc(num[lang]) if num else (f"독립 매체가 보도" if lang == "ko" else "independent outlets reported it")
    bg = f"background-image:url('{photo_data_uri}');" if photo_data_uri else ""
    credit = esc((s.get("photo") or {}).get("credit") or "")
    font = "'Inter','Noto Sans KR',sans-serif"
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@500;700;800;900&family=Noto+Sans+KR:wght@500;700;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{HERO_W}px;height:{HERO_H}px;overflow:hidden;background:{NAVY};font-family:{font};color:#fff}}
.bg{{position:absolute;inset:0;{bg}background-size:cover;background-position:center 30%}}
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(11,18,32,.55) 0%,rgba(11,18,32,.15) 30%,rgba(11,18,32,.78) 62%,rgba(11,18,32,.97) 100%)}}
.top{{position:absolute;top:44px;left:56px;right:56px;display:flex;justify-content:space-between;align-items:center;font-weight:800;letter-spacing:.14em;font-size:22px}}
.top .dot{{display:inline-block;width:12px;height:12px;border-radius:50%;background:{RED};margin-right:12px;vertical-align:middle}}
.top .d{{font-weight:600;letter-spacing:.02em;opacity:.9}}
.body{{position:absolute;left:56px;right:56px;bottom:56px}}
.num{{display:flex;align-items:baseline;gap:22px;margin-bottom:22px}}
.num b{{font-size:150px;line-height:.9;font-weight:900;letter-spacing:-.04em}}
.num span{{font-size:32px;font-weight:700;color:#FFB4B6;max-width:560px;line-height:1.2}}
.chips{{display:flex;gap:12px;margin-bottom:18px}}
.chip{{font-size:22px;font-weight:700;padding:8px 16px;border-radius:999px;background:rgba(255,255,255,.14);letter-spacing:.02em}}
.chip.r{{background:{RED}}}
h1{{font-size:{56 if lang == 'en' else 58}px;line-height:1.14;font-weight:800;letter-spacing:-.015em;word-break:keep-all}}
.cr{{position:absolute;right:56px;bottom:22px;font-size:16px;opacity:.7}}
</style></head><body><div class="bg"></div><div class="shade"></div>
<div class="top"><div><span class="dot"></span>WEWANTPEACE · {esc(t['kicker'])}</div><div class="d">{esc(date_range(data, lang))}</div></div>
<div class="body">
<div class="num"><b>{big}</b><span>{big_label}</span></div>
<div class="chips"><span class="chip r">{esc(country(s['cc'], lang))}</span><span class="chip">{s['n_sources']}{esc(t['outlets']) if lang == 'ko' else ' ' + esc(t['outlets'])}</span></div>
<h1>{esc(part['headline'])}</h1></div>
{f'<div class="cr">Photo: {credit}</div>' if credit else ''}
</body></html>"""


MAP_W, MAP_H = 1200, 640


def _merc(lon: float, lat: float) -> tuple[float, float]:
    lat = max(min(lat, 80), -80)
    return lon, math.degrees(math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))


def map_svg(data: dict) -> str:
    """번호 핀 지도 (외부 요청 없이 그리는 SVG). 이번 주 기사 나라는 붉게."""
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
    # 핀이 몰려 있어도 너무 확대되지 않게 최소 범위, 가장자리 여백
    span_x = max(maxx - minx, 40)
    span_y = max(maxy - miny, 22)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    pad = 1.35
    scale = min(MAP_W / (span_x * pad), MAP_H / (span_y * pad))

    def proj(lon, lat):
        x, y = _merc(lon, lat)
        return MAP_W / 2 + (x - cx) * scale, MAP_H / 2 - (y - cy) * scale

    def ring_path(ring):
        pts = [proj(lon, lat) for lon, lat in ring]
        return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z"

    paths = []
    for f in geo["features"]:
        g = f.get("geometry") or {}
        props = f.get("properties") or {}
        iso2 = (props.get("cc") or props.get("ISO_A2") or "").upper()
        polys = g.get("coordinates") or []
        if g.get("type") == "Polygon":
            polys = [polys]
        d = "".join(ring_path(r) for poly in polys for r in poly)
        fill = "#F6C9CB" if iso2 in story_cc else "#DDE3EA"
        paths.append(f'<path d="{d}" fill="{fill}" stroke="#FFFFFF" stroke-width="1.2"/>')
    pin_svg = []
    for n, lon, lat, cc in pins:
        x, y = proj(lon, lat)
        pin_svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="26" fill="{RED}" stroke="#fff" stroke-width="5"/>'
            f'<text x="{x:.1f}" y="{y + 10:.1f}" text-anchor="middle" font-size="28" font-weight="800" '
            f'font-family="Inter,Arial,sans-serif" fill="#fff">{n}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{MAP_W}" height="{MAP_H}" viewBox="0 0 {MAP_W} {MAP_H}">'
            f'<rect width="100%" height="100%" fill="#F3F5F8"/>{"".join(paths)}{"".join(pin_svg)}</svg>')


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
    """머리 이미지(영·한)·지도를 그리고, 2·3번 기사 사진은 우리 저장소로 옮긴다.

    upload=True 면 R2 주소, 아니면 로컬 파일 경로. 기사 사진을 매체 주소 그대로 메일에 넣으면
    핫링크를 막는 곳(9/30 드라이런: 1번 기사 사진)에서 빈칸이 된다.
    """
    import base64

    stories = data.get("stories") or []
    if not stories:
        return {}
    stamp = datetime.utcnow().strftime("%m%d%H%M")
    base = f"weekly-{data['week_key']}"
    images: dict = {}

    hero_uri, hero_ph = _first_photo(stories[0])
    stories[0]["photo"] = hero_ph
    for i in (1, 2):
        if i < len(stories):
            uri, ph = _first_photo(stories[i])
            if uri and ph:
                url = _store(base64.b64decode(uri.split(",", 1)[1]), f"{base}-s{i + 1}-{stamp}", "jpg", upload, save_dir)
                stories[i]["photo"] = {"url": url, "credit": ph.get("credit")} if url else None
            else:
                stories[i]["photo"] = None

    svg = map_svg(data)
    pages = [(hero_html(data, "en", hero_uri), HERO_W, HERO_H),
             (hero_html(data, "ko", hero_uri), HERO_W, HERO_H),
             (f"<html><body style='margin:0'>{svg}</body></html>", MAP_W, MAP_H)]
    for name, png in zip(["hero_en", "hero_ko", "map"], render_pngs(pages)):
        if png:
            url = _store(png, f"{base}-{name}-{stamp}", "png", upload, save_dir)
            if url:
                images[name] = url
    return images


# ── 메일 HTML ────────────────────────────────────────────────────────────────

def _chip(text: str, bg: str, fg: str) -> str:
    return (f'<span style="display:inline-block;padding:4px 10px;border-radius:999px;background:{bg};color:{fg};'
            f'font-size:12px;font-weight:700;line-height:16px;margin:0 6px 6px 0;">{esc(text)}</span>')


def _section_title(text: str, sub: str = "") -> str:
    return (f'<tr><td style="padding:30px 28px 10px;font-family:{FONT};">'
            f'<div style="font-size:12px;font-weight:800;letter-spacing:.14em;color:{RED};text-transform:uppercase;">{esc(text)}</div>'
            + (f'<div style="font-size:14px;color:{MUTED};margin-top:6px;line-height:20px;">{esc(sub)}</div>' if sub else "")
            + "</td></tr>")


def _story_card(i: int, s: dict, data: dict, lang: str) -> str:
    t = T[lang]
    p = s[lang]
    week = data["week_key"]
    url = story_url(s["cluster_id"], week, lang)
    photo = s.get("photo")
    img = ""
    if photo and i <= 3 and i > 1:  # 1번 기사 사진은 머리 이미지에 이미 있다
        img = (f'<tr><td style="padding:0 0 14px;"><a href="{esc(url)}"><img src="{esc(photo["url"])}" width="544" alt="" '
               f'style="display:block;width:100%;max-width:544px;height:auto;border-radius:10px;"></a>'
               + (f'<div style="font-size:11px;color:{MUTED};margin-top:5px;">Photo: {esc(photo.get("credit"))}</div>' if photo.get("credit") else "")
               + "</td></tr>")
    num = s.get("number")
    num_html = ""
    if num and i > 1:
        num_html = (f'<tr><td style="padding:0 0 12px;"><table role="presentation" cellpadding="0" cellspacing="0"><tr>'
                    f'<td style="font-family:{FONT};font-size:40px;line-height:40px;font-weight:900;color:{RED};padding-right:12px;letter-spacing:-.02em;">{esc(num["value"])}</td>'
                    f'<td style="font-family:{FONT};font-size:14px;line-height:18px;font-weight:700;color:{INK};">{esc(num[lang])}'
                    + (f'<div style="font-size:12px;font-weight:500;color:{MUTED};margin-top:2px;">{esc(t["num_src"])}: {esc(num.get("source"))}</div>' if num.get("source") else "")
                    + '</td></tr></table></td></tr>')
    rows = []
    for key in ("what", "why", "watch"):
        if p.get(key):
            rows.append(f'<tr><td style="padding:0 0 10px;font-family:{FONT};font-size:15px;line-height:24px;color:{INK};">'
                        f'<span style="font-weight:800;color:{RED if key == "what" else INK};">{esc(t[key])}</span> {esc(p[key])}</td></tr>')
    chips = _chip(f"{i}", RED, "#fff") + _chip(country(s["cc"], lang), "#F1F5F9", INK) + \
        _chip(f"{s['n_sources']}{t['outlets']}" if lang == "ko" else f"{s['n_sources']} {t['outlets']}", "#ECFDF5", GREEN)
    src = sources_line(s.get("source_names") or [], s["n_sources"], lang)
    return f"""
<tr><td style="padding:10px 28px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#FFFFFF;border:1px solid {LINE};border-left:4px solid {RED if i == 1 else NAVY};border-radius:12px;">
<tr><td style="padding:18px 20px 8px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
<tr><td style="padding:0 0 4px;font-family:{FONT};">{chips}</td></tr>
<tr><td style="padding:0 0 12px;font-family:{FONT};font-size:21px;line-height:28px;font-weight:800;color:{INK};word-break:keep-all;">
<a href="{esc(url)}" style="color:{INK};text-decoration:none;">{esc(p['headline'])}</a></td></tr>
{img}{num_html}{''.join(rows)}
<tr><td style="padding:2px 0 12px;font-family:{FONT};font-size:13px;line-height:19px;color:{MUTED};">
{esc(t['reported'])}: {esc(src)} · <a href="{esc(url)}" style="color:#1D4ED8;font-weight:700;text-decoration:none;">{esc(t['timeline'])} →</a></td></tr>
</table></td></tr></table></td></tr>"""


def _list_block(items: list[dict], data: dict, lang: str, accent: str, first_border: bool = True) -> str:
    out = []
    for k, it in enumerate(items):
        url = story_url(it["cluster_id"], data["week_key"], lang)
        border = f"border-top:1px solid {LINE};" if (k or first_border) else ""
        out.append(f'<tr><td style="padding:10px 0;{border}font-family:{FONT};">'
                   f'<div style="font-size:12px;font-weight:800;color:{accent};letter-spacing:.04em;">{esc(country(it["cc"], lang))}'
                   f' · <span style="color:{MUTED};font-weight:600;">{it["n_sources"]}{esc(T[lang]["outlets"]) if lang == "ko" else " " + esc(T[lang]["outlets"])}</span></div>'
                   f'<a href="{esc(url)}" style="display:block;margin-top:3px;font-size:15px;line-height:22px;font-weight:700;color:{INK};text-decoration:none;word-break:keep-all;">{esc(it[lang]["headline"])}</a></td></tr>')
    return "".join(out)


def _yours_block(ccs: list[str], data: dict, lang: str) -> str:
    t = T[lang]
    cards = []
    for cc in ccs[:3]:
        entry = (data.get("countries") or {}).get(cc)
        lv = (data.get("advisories") or {}).get(cc)
        adv = ""
        if lv in ADVISORY:
            bg, fg, en, ko = ADVISORY[lv]
            adv = _chip(ko if lang == "ko" else en, bg, fg)
        if entry and entry.get("top"):
            top = entry["top"]
            url = story_url(top["cluster_id"], data["week_key"], lang)
            n = entry["n"]
            count = f"이번 주 {n}건" if lang == "ko" else f"{n} {t['stories_n']}"
            body = (f'<a href="{esc(url)}" style="display:block;font-size:15px;line-height:22px;font-weight:700;color:{INK};text-decoration:none;word-break:keep-all;">{esc(top[lang]["headline"])}</a>'
                    f'<div style="font-size:13px;color:{MUTED};margin-top:4px;">{esc(count)}</div>')
        else:
            body = f'<div style="font-size:14px;color:{MUTED};">{esc(t["no_story"])}</div>'
        cards.append(f'<tr><td style="padding:14px 16px;border-top:1px solid {LINE};font-family:{FONT};">'
                     f'<div style="font-size:16px;font-weight:800;color:{INK};margin-bottom:6px;">{esc(country(cc, lang))}</div>'
                     f'{adv}{body}</td></tr>')
    return "".join(cards)


def render_email(data: dict, lang: str, *, follow: list[str] | None = None,
                 unsubscribe_url: str | None = None, switch_url: str | None = None,
                 feedback_token: str = "", subscriber: bool = False) -> dict:
    """{subject, preheader, html, text}. follow=구독자가 고른 나라(없으면 칸 생략)."""
    t = T[lang]
    week = data["week_key"]
    intro = (data.get("intro") or {}).get(lang) or {}
    stories = data.get("stories") or []
    images = data.get("images") or {}
    other = "en" if lang == "ko" else "ko"
    fb = f"{API}/newsletter/weekly/{week}/feedback?lang={lang}&t={esc(feedback_token)}"

    # 맨 위 어두운 띠: 세 줄 요약 + 실제 숫자 한 줄
    lines = intro.get("lines") or [s[lang].get("short") or s[lang]["headline"] for s in stories[:3]]
    three = "".join(
        f'<tr><td style="padding:0 0 12px;font-family:{FONT};"><table role="presentation" cellpadding="0" cellspacing="0"><tr>'
        f'<td valign="top" style="width:30px;"><div style="width:24px;height:24px;border-radius:12px;background:{RED};color:#fff;font-size:13px;font-weight:800;line-height:24px;text-align:center;">{k}</div></td>'
        f'<td style="font-size:16px;line-height:24px;color:#F8FAFC;font-weight:600;word-break:keep-all;">{esc(line)}</td></tr></table></td></tr>'
        for k, line in enumerate(lines[:3], 1))
    nums = data.get("numbers") or {}
    ticks = []
    br = nums.get("brent")
    if br:
        up = br["pct"] > 0
        arrow = "▲" if up else ("▼" if br["pct"] < 0 else "–")
        color = "#FCA5A5" if up else "#93C5FD"
        ticks.append(f'{esc(t["brent"])} <b style="color:#fff;">${br["now"]:.2f}</b> '
                     f'<span style="color:{color};font-weight:700;">{arrow}{abs(br["pct"]):.1f}%</span> <span style="color:#94A3B8;">{esc(t["wk"])}</span>')
    if nums.get("stories"):
        ticks.append(f'{esc(t["stories"])} <b style="color:#fff;">{nums["stories"]:,}</b>')
    if nums.get("outlets"):
        ticks.append(f'{esc(t["sources"])} <b style="color:#fff;">{nums["outlets"]:,}</b>')
    tick_html = " &nbsp;·&nbsp; ".join(ticks)

    hero = images.get(f"hero_{lang}")
    s1 = stories[0] if stories else None
    hero_html_block = ""
    if hero and s1:
        hero_html_block = (f'<tr><td style="padding:0;"><a href="{esc(story_url(s1["cluster_id"], week, lang))}">'
                           f'<img src="{esc(hero)}" width="600" alt="{esc(s1[lang]["headline"])}" style="display:block;width:100%;max-width:600px;height:auto;border:0;border-radius:14px 14px 0 0;"></a></td></tr>')
    lead_text = ""
    if s1:
        p = s1[lang]
        rows = "".join(
            f'<div style="margin-top:10px;font-size:15px;line-height:24px;color:#E2E8F0;"><span style="font-weight:800;color:{"#FCA5A5" if k == "what" else "#fff"};">{esc(t[k])}</span> {esc(p[k])}</div>'
            for k in ("what", "why", "watch") if p.get(k))
        if not hero:
            rows = f'<div style="font-size:24px;line-height:32px;font-weight:800;color:#fff;">{esc(p["headline"])}</div>' + rows
        n1 = s1.get("number")
        if hero and n1 and n1.get("source"):
            rows = (f'<div style="font-size:12px;color:#94A3B8;">{esc(n1["value"])} {esc(n1[lang])} · '
                    f'{esc(t["num_src"])}: {esc(n1["source"])}</div>') + rows
        src = sources_line(s1.get("source_names") or [], s1["n_sources"], lang)
        lead_text = (f'<tr><td style="padding:18px 28px 22px;font-family:{FONT};background:{NAVY};">{rows}'
                     f'<div style="margin-top:12px;font-size:13px;color:#94A3B8;">{esc(t["reported"])}: {esc(src)} · '
                     f'<a href="{esc(story_url(s1["cluster_id"], week, lang))}" style="color:#93C5FD;font-weight:700;text-decoration:none;">{esc(t["timeline"])} →</a></div></td></tr>')

    intro_html = ""
    if intro.get("intro"):
        intro_html = (f'<tr><td style="padding:24px 28px 4px;font-family:{FONT};font-size:17px;line-height:28px;color:{INK};word-break:keep-all;">'
                      f'{esc(intro["intro"])}</td></tr>')

    map_block = ""
    if images.get("map") and len(stories) > 1:
        glance = "".join(
            f'<tr><td style="padding:5px 0;font-family:{FONT};font-size:15px;line-height:22px;color:{INK};">'
            f'<b style="color:{RED};">{k}</b>&nbsp;&nbsp;{esc(country(s["cc"], lang))} · {esc(s[lang].get("short") or s[lang]["headline"])}</td></tr>'
            for k, s in enumerate(stories, 1))
        map_block = (_section_title(t["map"]) +
                     f'<tr><td style="padding:0 28px;"><img src="{esc(images["map"])}" width="544" alt="" style="display:block;width:100%;max-width:544px;height:auto;border-radius:10px;border:1px solid {LINE};"></td></tr>'
                     f'<tr><td style="padding:10px 28px 0;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{glance}</table></td></tr>')

    cards = "".join(_story_card(i, s, data, lang) for i, s in enumerate(stories, 1) if i > 1)

    easing = data.get("easing") or []
    easing_block = ""
    if easing:
        easing_block = (_section_title(t["easing"], t["easing_sub"]) +
                        f'<tr><td style="padding:0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                        f'style="background:#F0FDF4;border-radius:12px;"><tr><td style="padding:2px 16px 6px;">'
                        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{_list_block(easing, data, lang, GREEN, first_border=False)}</table>'
                        f'</td></tr></table></td></tr>')
    also = data.get("also") or []
    also_block = ""
    if also:
        also_block = (_section_title(t["also"]) +
                      f'<tr><td style="padding:0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{_list_block(also, data, lang, NAVY)}</table></td></tr>')
    yours_block = ""
    if follow:
        yours_block = (_section_title(t["yours"], t["yours_sub"]) +
                       f'<tr><td style="padding:0 28px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                       f'style="border:1px solid {LINE};border-radius:12px;">{_yours_block(follow, data, lang)}</table></td></tr>')

    feedback = (f'<tr><td style="padding:28px 28px 6px;font-family:{FONT};text-align:center;">'
                f'<div style="font-size:15px;font-weight:700;color:{INK};margin-bottom:10px;">{esc(t["useful"])}</div>'
                f'<a href="{fb}&v=good" style="display:inline-block;padding:9px 18px;margin:0 4px;border-radius:999px;background:#DCFCE7;color:#166534;font-size:14px;font-weight:700;text-decoration:none;">{esc(t["yes"])}</a>'
                f'<a href="{fb}&v=bad" style="display:inline-block;padding:9px 18px;margin:0 4px;border-radius:999px;background:#F1F5F9;color:#475569;font-size:14px;font-weight:700;text-decoration:none;">{esc(t["no"])}</a></td></tr>')

    app = (f'<tr><td style="padding:24px 28px 8px;"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{NAVY};border-radius:14px;">'
           f'<tr><td style="padding:22px 22px;font-family:{FONT};">'
           f'<div style="font-size:17px;line-height:24px;font-weight:800;color:#fff;word-break:keep-all;">{esc(t["app_title"])}</div>'
           f'<div style="font-size:14px;line-height:21px;color:#CBD5E1;margin-top:6px;word-break:keep-all;">{esc(t["app_body"])}</div>'
           f'<a href="https://play.google.com/store/apps/details?id=com.wewantpeace.app&utm_source=newsletter&utm_campaign={week}" '
           f'style="display:inline-block;margin-top:14px;padding:10px 18px;border-radius:10px;background:#fff;color:{NAVY};font-size:14px;font-weight:800;text-decoration:none;">{esc(t["app_cta"])} →</a>'
           f'</td></tr></table></td></tr>')

    why_get = t["why_get_sub"] if subscriber else t["why_get_user"]
    foot_links = []
    if switch_url:
        foot_links.append(f'<a href="{esc(switch_url)}" style="color:{MUTED};">{esc(t["switch"])}</a>')
    if unsubscribe_url:
        foot_links.append(f'<a href="{esc(unsubscribe_url)}" style="color:{MUTED};">{esc(t["unsub"])}</a>')
    footer = (f'<tr><td style="padding:24px 28px 30px;font-family:{FONT};font-size:12px;line-height:19px;color:{MUTED};">'
              f'<b style="color:{INK};">{esc(t["how"])}</b> {esc(t["how_body"])}<br><br>{esc(why_get)} '
              f'{" · ".join(foot_links)}<br>WeWantPeace · Seoul, South Korea</td></tr>')

    subject = intro.get("subject") or (s1[lang]["headline"] if s1 else "WeWantPeace")
    preheader = intro.get("preheader") or ""
    if switch_url:
        lang_link = (f'<a href="{esc(switch_url)}" style="color:{INK};font-weight:700;text-decoration:underline;">'
                     f'{esc(t["switch_top"])}</a>')
    else:
        lang_link = f'<a href="{esc(web_url(week, other))}" style="color:{MUTED};text-decoration:underline;">{esc(t["other_lang"])}</a>'
    top_links = (f'<a href="{esc(web_url(week, lang))}" style="color:{MUTED};text-decoration:underline;">{esc(t["view"])}</a>'
                 f' &nbsp;·&nbsp; {lang_link}')

    html = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<title>{esc(subject)}</title></head>
<body style="margin:0;padding:0;background:{PAGE};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{esc(preheader)}&#8199;&#65279;&#847;&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAGE};">
<tr><td align="center" style="padding:14px 10px 6px;font-family:{FONT};font-size:12px;color:{MUTED};">{top_links}</td></tr>
<tr><td align="center" style="padding:0 10px 30px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#FFFFFF;border-radius:14px;">
{hero_html_block}
{lead_text}
<tr><td style="padding:22px 28px 10px;background:{NAVY};font-family:{FONT};border-top:1px solid #1E293B;">
<div style="font-size:12px;font-weight:800;letter-spacing:.14em;color:#FCA5A5;text-transform:uppercase;margin-bottom:14px;">{esc(t["three"])}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{three}</table></td></tr>
{f'<tr><td style="padding:12px 28px 16px;background:{NAVY};font-family:{FONT};font-size:13px;line-height:20px;color:#CBD5E1;border-top:1px solid #1E293B;">{tick_html}</td></tr>' if tick_html else ''}
{intro_html}
{map_block}
{cards}
{yours_block}
{easing_block}
{also_block}
{feedback}
{app}
{footer}
</table></td></tr></table></body></html>"""

    text_lines = [subject, "", intro.get("intro", ""), ""]
    for i, s in enumerate(stories, 1):
        p = s[lang]
        text_lines += [f"{i}. {p['headline']}"] + [f"   {t[k]} {p[k]}" for k in ("what", "why", "watch") if p.get(k)] + \
                      [f"   {story_url(s['cluster_id'], week, lang)}", ""]
    if unsubscribe_url:
        text_lines += [f"{t['unsub']}: {unsubscribe_url}"]
    return {"subject": subject, "preheader": preheader, "html": html, "text": "\n".join(text_lines)}

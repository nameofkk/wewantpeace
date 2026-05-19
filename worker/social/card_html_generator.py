"""SNS 카드 HTML → Playwright 스크린샷 이미지 생성기.

Editorial / News 품질 720×900px PNG 카드:
  - kscore_alert : BREAKING NEWS 다크 카드
  - daily_movers : DAILY BRIEF 에디토리얼 크림 카드
  - weekly_recap : WEEK IN REVIEW 데이터 네이비 카드
"""
from __future__ import annotations

import html as _html
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ── 국가 정보 ──────────────────────────────────────────────────────────────────
_COUNTRY_NAMES: dict[str, str] = {
    "UA": "Ukraine",      "RU": "Russia",       "IL": "Israel",
    "PS": "Palestine",    "IR": "Iran",          "CN": "China",
    "TW": "Taiwan",       "KP": "N.Korea",       "KR": "S.Korea",
    "US": "USA",          "SY": "Syria",         "YE": "Yemen",
    "MM": "Myanmar",      "SD": "Sudan",         "ET": "Ethiopia",
    "AF": "Afghanistan",  "IQ": "Iraq",          "LB": "Lebanon",
    "PK": "Pakistan",     "IN": "India",         "JP": "Japan",
    "TR": "Turkey",       "EG": "Egypt",         "SA": "Saudi Arabia",
    "NG": "Nigeria",      "CD": "Congo",         "SO": "Somalia",
    "LY": "Libya",        "ML": "Mali",          "CF": "C.African Rep.",
}

_GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2?"
    "family=Playfair+Display:ital,wght@0,700;0,900;1,700&"
    "family=DM+Sans:wght@400;500;600;700&"
    "family=Noto+Serif+KR:wght@400;600;700;900&"
    "display=swap"
)


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _flag_img(cc: str, h: int = 20) -> str:
    """ISO 2-letter → flagcdn.com <img> 태그 (headless 브라우저 호환)."""
    if not cc or len(cc) != 2:
        return ""
    lc = cc.lower()
    return (
        f'<img src="https://flagcdn.com/w40/{lc}.png" alt="{cc}" '
        f'style="height:{h}px;width:auto;border-radius:2px;'
        f'object-fit:cover;vertical-align:middle;display:inline-block;" '
        f'onerror="this.style.display=\'none\'">'
    )


def _sev(sev: int) -> dict[str, str]:
    if sev >= 80:
        return {"label": "CRITICAL",  "stripe": "#EF4444", "bar": "#EF4444",
                "text": "#FCA5A5",  "bg": "rgba(239,68,68,0.18)"}
    if sev >= 60:
        return {"label": "SERIOUS",   "stripe": "#F59E0B", "bar": "#F59E0B",
                "text": "#FCD34D",  "bg": "rgba(245,158,11,0.18)"}
    if sev >= 40:
        return {"label": "ELEVATED",  "stripe": "#EAB308", "bar": "#EAB308",
                "text": "#FDE047",  "bg": "rgba(234,179,8,0.18)"}
    if sev >= 20:
        return {"label": "MODERATE",  "stripe": "#3B82F6", "bar": "#3B82F6",
                "text": "#93C5FD",  "bg": "rgba(59,130,246,0.18)"}
    return     {"label": "LOW",       "stripe": "#22C55E", "bar": "#22C55E",
                "text": "#86EFAC",  "bg": "rgba(34,197,94,0.18)"}


def _source_meta(issue: dict) -> str:
    parts: list[str] = []
    n = issue.get("independent_sources", 0)
    if n > 0:
        parts.append(f"{n} independent source{'s' if n != 1 else ''}")
    tiers = issue.get("source_tiers", [])
    for t, lbl in [("gov", "Official"), ("t1", "Major Wire"), ("t2", "National")]:
        if t in tiers:
            parts.append(lbl)
            break
    if issue.get("is_verified"):
        parts.append("Verified")
    return " · ".join(parts)


def _en_sz(text: str) -> int:
    n = len(text)
    if n < 38: return 68
    if n < 60: return 58
    if n < 85: return 48
    return 40


def _ko_sz(text: str) -> int:
    n = len(text)
    if n < 16: return 48
    if n < 28: return 42
    if n < 42: return 36
    return 30


# ── HTML 빌더: kscore_alert ────────────────────────────────────────────────────

def _alert_html(issues: list[dict], date_str: str, image_url: str | None = None) -> str:
    iss   = issues[0] if issues else {}
    cc    = iss.get("country_code", "")
    en    = _html.escape(iss.get("title_en", "Breaking Alert"))
    ko    = _html.escape(iss.get("title_ko", en))
    sev_n = int(iss.get("severity", 50))
    si    = _sev(sev_n)
    src   = _source_meta(iss)
    en_fs = _en_sz(en)
    ko_fs = _ko_sz(ko)
    pct   = min(sev_n, 100)
    cname = _COUNTRY_NAMES.get(cc, cc).upper()
    flag_html = _flag_img(cc, h=24)

    # 배경 이미지: 이미지 URL이 있으면 어두운 오버레이와 함께 배경으로 사용
    if image_url:
        bg_css = f"""
  background-image: url('{image_url}');
  background-size: cover;
  background-position: center top;"""
        overlay_html = '<div class="img-overlay"></div>'
    else:
        bg_css = ""
        overlay_html = ""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
@import url('{_GOOGLE_FONTS_URL}');
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:720px;height:900px;overflow:hidden;-webkit-font-smoothing:antialiased;}}
body{{background:#0B0B0F;font-family:'DM Sans',sans-serif;{bg_css}}}

/* 배경 이미지 오버레이 */
.img-overlay{{
  position:fixed;inset:0;
  background:linear-gradient(
    to bottom,
    rgba(11,11,15,0.72) 0%,
    rgba(11,11,15,0.60) 40%,
    rgba(11,11,15,0.88) 75%,
    rgba(11,11,15,0.97) 100%
  );
  z-index:0;pointer-events:none;
}}
.stripe{{position:relative;z-index:1;height:4px;background:{si['stripe']};width:100%;}}

.card{{
  position:relative;z-index:1;
  padding:28px 44px 26px;
  height:896px;
  display:flex;
  flex-direction:column;
}}

.mast{{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}}
.brand{{display:flex;align-items:center;gap:9px;font-weight:700;font-size:14px;
        letter-spacing:.1em;text-transform:uppercase;color:#fff;}}
.dot{{width:9px;height:9px;background:{si['stripe']};border-radius:50%;flex-shrink:0;}}
.badge{{background:#DC2626;color:#fff;font-weight:700;font-size:11px;
        letter-spacing:.13em;text-transform:uppercase;padding:5px 12px;border-radius:3px;}}

.rule{{height:1px;background:rgba(255,255,255,.1);}}

.crow{{display:flex;align-items:center;gap:10px;margin:20px 0 14px;}}
.cname{{font-weight:700;font-size:15px;letter-spacing:.14em;color:rgba(255,255,255,.48);}}

/* 메인 헤드라인 영역 — flex:1 로 카드 중앙부를 채움 */
.main{{flex:1;display:flex;flex-direction:column;justify-content:center;
       padding:10px 0 20px;}}

.hen{{
  font-family:'Playfair Display',Georgia,serif;
  font-weight:900;
  font-size:{en_fs}px;
  line-height:1.1;
  color:#fff;
  letter-spacing:-.018em;
  display:-webkit-box;
  -webkit-line-clamp:5;
  -webkit-box-orient:vertical;
  overflow:hidden;
  margin-bottom:18px;
}}
.hko{{
  font-family:'Noto Serif KR','Noto Serif',Georgia,serif;
  font-weight:700;
  font-size:{ko_fs}px;
  line-height:1.4;
  color:rgba(255,255,255,.80);
  display:-webkit-box;
  -webkit-line-clamp:3;
  -webkit-box-orient:vertical;
  overflow:hidden;
}}

/* severity + footer 고정 하단 */
.bottom{{}}
.sep{{height:1px;background:rgba(255,255,255,.1);margin-bottom:15px;}}
.sev-row{{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}}
.sev-lbl{{font-weight:700;font-size:11px;letter-spacing:.14em;color:{si['text']};}}
.sev-sc{{font-weight:500;font-size:11px;color:rgba(255,255,255,.40);}}
.track{{height:5px;background:rgba(255,255,255,.08);border-radius:3px;overflow:hidden;margin-bottom:12px;}}
.fill{{height:100%;width:{pct}%;background:{si['bar']};border-radius:3px;}}
.srcm{{font-size:11px;color:rgba(255,255,255,.33);margin-bottom:14px;letter-spacing:.02em;}}
.foot{{display:flex;align-items:center;justify-content:space-between;
       padding-top:13px;border-top:1px solid rgba(255,255,255,.1);}}
.fl,.fr{{font-size:11px;color:rgba(255,255,255,.28);letter-spacing:.05em;}}
</style>
</head>
<body>
{overlay_html}
<div class="stripe"></div>
<div class="card">
  <div class="mast">
    <div class="brand"><div class="dot"></div>WEWANTPEACE</div>
    <div class="badge">BREAKING</div>
  </div>
  <div class="rule"></div>

  <div class="crow">
    {flag_html}
    <span class="cname">{cname}</span>
  </div>

  <div class="main">
    <div class="hen">{en}</div>
    <div class="hko">{ko}</div>
  </div>

  <div class="bottom">
    <div class="sep"></div>
    <div class="sev-row">
      <span class="sev-lbl">{si['label']}</span>
      <span class="sev-sc">{sev_n}&thinsp;/&thinsp;100</span>
    </div>
    <div class="track"><div class="fill"></div></div>
    {'<div class="srcm">' + _html.escape(src) + '</div>' if src else ''}
    <div class="foot">
      <span class="fl">wewantpeace.live</span>
      <span class="fr">{_html.escape(date_str)}</span>
    </div>
  </div>
</div>
</body></html>"""


# ── HTML 빌더: daily_movers ───────────────────────────────────────────────────

def _daily_html(issues: list[dict], date_str: str) -> str:
    top = issues[:3]
    rows = ""
    for idx, iss in enumerate(top):
        cc    = iss.get("country_code", "")
        en    = _html.escape(iss.get("title_en", ""))
        ko    = _html.escape(iss.get("title_ko", en))
        sev_n = int(iss.get("severity", 0))
        si    = _sev(sev_n)
        rank  = f"{idx + 1:02d}"
        cname = _COUNTRY_NAMES.get(cc, cc).upper()
        flag_html = _flag_img(cc, h=18)
        last_cls = " last" if idx == len(top) - 1 else ""

        rows += f"""
<div class="irow{last_cls}">
  <div class="ihdr">
    <div class="ileft">
      <span class="rank">{rank}</span>
      {flag_html}
      <span class="icc">{cname}</span>
    </div>
    <span class="iscore" style="color:{si['text']};background:{si['bg']};">{sev_n}</span>
  </div>
  <div class="ien">{en}</div>
  <div class="iko">{ko}</div>
  <div class="isev">
    <div class="itrack">
      <div class="ifill" style="width:{min(sev_n,100)}%;background:{si['bar']};"></div>
    </div>
    <span class="isevlbl" style="color:{si['text']};">{si['label']}</span>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
@import url('{_GOOGLE_FONTS_URL}');
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:720px;height:900px;overflow:hidden;-webkit-font-smoothing:antialiased;}}
body{{background:#F5F1EA;font-family:'DM Sans',sans-serif;color:#1A1A1A;}}

.card{{padding:28px 42px 24px;height:900px;display:flex;flex-direction:column;}}

.mast{{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;}}
.brand{{font-weight:700;font-size:15px;letter-spacing:.04em;color:#1A1A1A;}}
.badge{{background:#1E3A5F;color:#fff;font-weight:700;font-size:10px;
        letter-spacing:.14em;text-transform:uppercase;padding:5px 12px;border-radius:3px;}}

.drule{{height:2px;background:#1A1A1A;margin-bottom:0;}}

/* 이슈 목록 — flex:1 로 공간 채움, space-around 배분 */
.issues{{flex:1;display:flex;flex-direction:column;justify-content:space-around;
         padding:12px 0;}}

.irow{{padding-bottom:16px;border-bottom:1px solid rgba(0,0,0,.09);}}
.irow.last{{border-bottom:none;padding-bottom:0;}}

.ihdr{{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}}
.ileft{{display:flex;align-items:center;gap:8px;}}
.rank{{font-weight:700;font-size:26px;color:rgba(0,0,0,.1);line-height:1;}}
.icc{{font-weight:700;font-size:12px;letter-spacing:.1em;color:rgba(0,0,0,.42);}}
.iscore{{font-weight:700;font-size:13px;padding:3px 10px;border-radius:3px;letter-spacing:.03em;}}

.ien{{
  font-family:'Playfair Display',Georgia,serif;
  font-weight:700;
  font-size:24px;
  line-height:1.28;
  color:#1A1A1A;
  display:-webkit-box;
  -webkit-line-clamp:2;
  -webkit-box-orient:vertical;
  overflow:hidden;
  margin-bottom:6px;
}}
.iko{{
  font-family:'Noto Serif KR','Noto Serif',Georgia,serif;
  font-weight:400;
  font-size:17px;
  line-height:1.45;
  color:rgba(0,0,0,.58);
  display:-webkit-box;
  -webkit-line-clamp:2;
  -webkit-box-orient:vertical;
  overflow:hidden;
  margin-bottom:10px;
}}

.isev{{display:flex;align-items:center;gap:10px;}}
.itrack{{flex:1;height:4px;background:rgba(0,0,0,.09);border-radius:2px;overflow:hidden;}}
.ifill{{height:100%;border-radius:2px;}}
.isevlbl{{font-weight:700;font-size:10px;letter-spacing:.1em;white-space:nowrap;}}

.drule2{{height:2px;background:#1A1A1A;margin-top:0;}}
.foot{{display:flex;align-items:center;justify-content:space-between;padding-top:12px;}}
.fl,.fr{{font-size:11px;color:rgba(0,0,0,.32);letter-spacing:.05em;}}
</style>
</head>
<body>
<div class="card">
  <div class="mast">
    <span class="brand">WeWantPeace</span>
    <span class="badge">DAILY BRIEF</span>
  </div>
  <div class="drule"></div>

  <div class="issues">
    {rows}
  </div>

  <div class="drule2"></div>
  <div class="foot">
    <span class="fl">{_html.escape(date_str)}</span>
    <span class="fr">wewantpeace.live</span>
  </div>
</div>
</body></html>"""


# ── HTML 빌더: weekly_recap ───────────────────────────────────────────────────

def _weekly_html(issues: list[dict], date_str: str) -> str:
    top5    = issues[:5]
    sevs    = [iss.get("severity", 0) for iss in top5]
    max_sev = max(sevs) if sevs else 100

    bars = ""
    for iss in top5:
        cc    = iss.get("country_code", "")
        sev_n = int(iss.get("severity", 0))
        si    = _sev(sev_n)
        cname = _COUNTRY_NAMES.get(cc, cc).upper()
        bar_pct = int(sev_n / max(max_sev, 1) * 82)
        flag_html = _flag_img(cc, h=18)

        bars += f"""
<div class="brow">
  <div class="blabel">{flag_html}<span class="bcc">{cname}</span></div>
  <div class="btrack">
    <div class="bfill" style="width:{bar_pct}%;background:{si['bar']};"></div>
  </div>
  <span class="bscore" style="color:{si['text']};">{sev_n}</span>
</div>"""

    total_events = sum(iss.get("event_count", 0) for iss in issues)
    n_conflicts  = len(issues)

    try:
        from datetime import date as _date
        today    = _date.today()
        week_num = today.isocalendar()[1]
        week_label = f"Week {week_num} · {today.strftime('%b %Y')}"
    except Exception:
        week_label = date_str

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<style>
@import url('{_GOOGLE_FONTS_URL}');
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:720px;height:900px;overflow:hidden;-webkit-font-smoothing:antialiased;}}
body{{background:#0F172A;font-family:'DM Sans',sans-serif;color:#fff;}}

.card{{padding:28px 44px 24px;height:900px;display:flex;flex-direction:column;}}

.mast{{display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;}}
.brand{{font-weight:700;font-size:14px;letter-spacing:.08em;color:#fff;}}
.badge{{background:#7C3AED;color:#fff;font-weight:700;font-size:10px;
        letter-spacing:.14em;text-transform:uppercase;padding:5px 11px;border-radius:3px;}}
.week-lbl{{font-size:12px;color:rgba(255,255,255,.38);letter-spacing:.04em;margin-bottom:14px;}}

.drule{{height:2px;background:rgba(255,255,255,.1);margin-bottom:18px;}}
.drule2{{height:2px;background:rgba(255,255,255,.1);margin:0 0 24px;}}
.drule3{{height:2px;background:rgba(255,255,255,.1);}}

.sec-hdr{{font-weight:700;font-size:11px;letter-spacing:.18em;
          color:rgba(255,255,255,.35);text-transform:uppercase;margin-bottom:18px;}}

/* 바 차트 — flex:1 로 공간 채움 */
.bars{{flex:1;display:flex;flex-direction:column;justify-content:space-around;
       padding-bottom:4px;}}

.brow{{display:flex;align-items:center;gap:14px;}}
.blabel{{display:flex;align-items:center;gap:8px;width:160px;flex-shrink:0;}}
.bcc{{font-weight:600;font-size:12px;letter-spacing:.1em;color:rgba(255,255,255,.65);}}
.btrack{{flex:1;height:7px;background:rgba(255,255,255,.08);border-radius:4px;overflow:hidden;}}
.bfill{{height:100%;border-radius:4px;}}
.bscore{{font-weight:700;font-size:13px;width:30px;text-align:right;flex-shrink:0;}}

/* 통계 */
.stats{{display:flex;gap:40px;padding:24px 0;}}
.stat-num{{
  font-family:'Playfair Display',Georgia,serif;
  font-weight:900;
  font-size:48px;
  line-height:1;
  color:#fff;
  margin-bottom:5px;
}}
.stat-lbl{{font-size:11px;color:rgba(255,255,255,.35);letter-spacing:.1em;text-transform:uppercase;}}

.foot{{display:flex;align-items:center;justify-content:space-between;
       padding-top:13px;border-top:1px solid rgba(255,255,255,.1);}}
.fl,.fr{{font-size:11px;color:rgba(255,255,255,.28);letter-spacing:.05em;}}
</style>
</head>
<body>
<div class="card">
  <div class="mast">
    <span class="brand">WeWantPeace</span>
    <span class="badge">WEEK IN REVIEW</span>
  </div>
  <div class="week-lbl">{_html.escape(week_label)}</div>
  <div class="drule"></div>

  <div class="sec-hdr">Top Conflicts This Week</div>
  <div class="bars">{bars}</div>

  <div class="drule2"></div>

  <div class="stats">
    <div>
      <div class="stat-num">{n_conflicts}</div>
      <div class="stat-lbl">Conflicts Tracked</div>
    </div>
    <div>
      <div class="stat-num">{total_events if total_events else "—"}</div>
      <div class="stat-lbl">Events This Week</div>
    </div>
  </div>

  <div class="drule3"></div>
  <div style="height:13px;"></div>
  <div class="foot">
    <span class="fl">wewantpeace.live</span>
    <span class="fr">{_html.escape(date_str)}</span>
  </div>
</div>
</body></html>"""


# ── Playwright 스크린샷 ────────────────────────────────────────────────────────

_CHROMIUM_ARGS = [
    # 컨테이너/제한 환경 필수 플래그
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--no-zygote",
    # 렌더링 안정화
    "--disable-software-rasterizer",
    "--disable-background-networking",
    "--no-first-run",
]


def _store_error_to_redis(err: str) -> None:
    """Railway 진단용: 에러를 Redis에 저장 (1시간 TTL)."""
    try:
        import os, redis as _redis
        url = os.environ.get("REDIS_URL", "")
        if not url:
            return
        r = _redis.from_url(url, socket_connect_timeout=3)
        r.setex("playwright_error", 3600, err)
    except Exception:
        pass


def _screenshot(html_src: str) -> bytes:
    import traceback as _tb
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=_CHROMIUM_ARGS)
            try:
                page = browser.new_page(viewport={"width": 720, "height": 900})
                try:
                    page.set_content(html_src, wait_until="networkidle", timeout=15000)
                except Exception:
                    pass  # 타임아웃이어도 현재 렌더 상태로 스크린샷
                page.evaluate("() => document.fonts.ready")
                data = page.screenshot(
                    full_page=False,
                    clip={"x": 0, "y": 0, "width": 720, "height": 900},
                    type="png",
                )
            finally:
                browser.close()
        return data
    except Exception:
        err = _tb.format_exc()
        logger.error("Playwright 스크린샷 실패:\n%s", err)
        _store_error_to_redis(err)
        raise


# ── Public API ────────────────────────────────────────────────────────────────

def generate_html_card(
    content_type: str,
    issues: list[dict] | None = None,
    hashtags: list[str] | None = None,
    date: str | None = None,
    image_url: str | None = None,
) -> bytes | None:
    """HTML → Playwright 스크린샷 방식으로 720×900 카드 PNG 생성.

    Parameters
    ----------
    content_type : str
        'kscore_alert' | 'daily_movers' | 'weekly_recap'
    issues : list[dict]
        각 dict: title_en, title_ko, country_code, severity,
                 independent_sources, source_tiers, is_verified, event_count
    hashtags : list[str]
        SNS 해시태그 (카드 내 표시되지 않음, 향후 확장용)
    date : str
        날짜 문자열 (없으면 오늘 UTC, 형식: YYYY.MM.DD)

    Returns
    -------
    bytes or None
        PNG bytes (720×900px), 실패 시 None
    """
    try:
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y.%m.%d")

        issues = issues or []

        if content_type in ("kscore_alert", "spike_alert"):
            # issues[0].image_url 도 폴백으로 사용
            img = image_url or (issues[0].get("image_url") if issues else None)
            html_src = _alert_html(issues, date, image_url=img)
        elif content_type == "daily_movers":
            html_src = _daily_html(issues, date)
        elif content_type == "weekly_recap":
            html_src = _weekly_html(issues, date)
        else:
            logger.warning("generate_html_card: 알 수 없는 content_type=%s → daily_movers 폴백", content_type)
            html_src = _daily_html(issues, date)

        return _screenshot(html_src)

    except Exception:
        logger.exception("HTML 카드 생성 실패 (content_type=%s)", content_type)
        return None

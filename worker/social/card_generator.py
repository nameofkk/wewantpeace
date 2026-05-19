"""SNS 카드 이미지 생성기 — 720x900 (직사각형).

각 이슈를 국가 + EN/KO 제목 + 개별 severity + 신뢰도로 표시.
"""
import io
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from urllib.request import urlretrieve

# 이모지/특수 유니코드 제거 (카드에는 국가배지가 별도 표시됨)
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"  # 국기
    "\U0001F300-\U0001FAFF"  # 이모지
    "\u2600-\u27BF"          # 기호
    "\u200d\ufe0f\u20e3"     # ZWJ, variation selector
    "]+", re.UNICODE,
)


def _strip_emoji(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()

logger = logging.getLogger(__name__)

_FONT_BOLD = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_FONT_REGULAR = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

_WHITE = (255, 255, 255)
_LIGHT = (220, 225, 235)
_MUTED = (140, 148, 165)
_ACCENT = (96, 165, 250)
_BG_DARK = (10, 10, 18)
_DIVIDER = (45, 50, 65)

_SEV_COLORS = {
    "low": (34, 197, 94),
    "medium": (250, 204, 21),
    "high": (239, 68, 68),
}

_TYPE_CONFIG = {
    "daily_movers": ("DAILY BRIEF", _ACCENT),
    "kscore_alert": ("BREAKING", (239, 68, 68)),
    "spike_alert": ("BREAKING", (239, 68, 68)),  # 하위호환
    "weekly_recap": ("WEEKLY", (168, 85, 247)),
}

_COUNTRY_NAMES = {
    "UA": "Ukraine", "RU": "Russia", "IL": "Israel", "PS": "Palestine",
    "IR": "Iran", "CN": "China", "TW": "Taiwan", "KP": "N.Korea",
    "KR": "S.Korea", "US": "USA", "SY": "Syria", "YE": "Yemen",
    "MM": "Myanmar", "SD": "Sudan", "ET": "Ethiopia", "AF": "Afghanistan",
    "IQ": "Iraq", "LB": "Lebanon", "PK": "Pakistan", "IN": "India",
    "JP": "Japan", "TR": "Turkey", "EG": "Egypt", "SA": "Saudi Arabia",
    "NG": "Nigeria", "CD": "Congo", "SO": "Somalia", "LY": "Libya",
}

# source_tier → 표시 라벨
_TIER_LABELS = {
    "t1": "Major Wire",
    "t2": "National",
    "t3": "Regional",
    "gov": "Official",
}


def _load_font(paths, size):
    from PIL import ImageFont
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _tw(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _wrap(text, font, max_w, draw):
    lines = []
    for raw in text.split("\n"):
        if not raw.strip():
            continue
        words = raw.split(" ")
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip() if cur else w
            if _tw(draw, test, font) <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
    return lines or [text]


def _sev_color(severity):
    if severity < 40:
        return _SEV_COLORS["low"]
    if severity < 70:
        return _SEV_COLORS["medium"]
    return _SEV_COLORS["high"]


def _download_image(url):
    try:
        from urllib.request import Request
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; WeWantPeace/1.0)"})
        import urllib.request
        with urllib.request.urlopen(req, timeout=10) as resp, open(tmp.name, "wb") as f:
            f.write(resp.read())
        return tmp.name
    except Exception:
        logger.warning("이미지 다운로드 실패: %s", url[:80])
        return None


def _build_credibility_text(issue: dict) -> str | None:
    """신뢰도 한 줄 텍스트 생성."""
    parts = []
    sources = issue.get("independent_sources", 0)
    if sources > 0:
        parts.append(f"{sources} independent sources")

    tiers = issue.get("source_tiers", [])
    top_tier = None
    for t in ("gov", "t1", "t2"):
        if t in tiers:
            top_tier = _TIER_LABELS.get(t, t)
            break
    if top_tier:
        parts.append(top_tier)

    if issue.get("is_verified"):
        parts.append("Verified")

    events = issue.get("event_count", 0)
    if events > 1:
        parts.append(f"{events} reports")

    if not parts:
        return None
    return " · ".join(parts)


def generate_card(
    content_type: str,
    issues: list[dict] | None = None,
    body_text: str | None = None,
    hashtags: list[str] | None = None,
    bg_image_url: str | None = None,
    date_str: str | None = None,
) -> bytes | None:
    """720x900 SNS 카드 (직사각형).

    issues: [{"title_en", "title_ko", "country_code", "severity",
              "independent_sources", "source_tiers", "is_verified", "event_count"}, ...]
    body_text: issues 없을 때 폴백용 flat 텍스트
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("Pillow 미설치")
        return None

    try:
        W, H = 720, 900
        M = 40

        is_spike = content_type == "spike_alert"

        # ── 배경 ──
        if is_spike:
            img = Image.new("RGBA", (W, H), (25, 5, 5, 255))
        else:
            img = Image.new("RGBA", (W, H), (*_BG_DARK, 255))
        if bg_image_url:
            bg_path = _download_image(bg_image_url)
            if bg_path:
                try:
                    bg = Image.open(bg_path).convert("RGBA")
                    ratio = max(W / bg.width, H / bg.height)
                    bg = bg.resize(
                        (int(bg.width * ratio), int(bg.height * ratio)),
                        Image.LANCZOS,
                    )
                    lx = (bg.width - W) // 2
                    ly = (bg.height - H) // 2
                    bg = bg.crop((lx, ly, lx + W, ly + H))
                    if is_spike:
                        overlay = Image.new("RGBA", (W, H), (40, 5, 5, 150))
                    else:
                        overlay = Image.new("RGBA", (W, H), (10, 10, 18, 140))
                    img = Image.alpha_composite(bg, overlay)
                    os.unlink(bg_path)
                except Exception:
                    if bg_path and os.path.exists(bg_path):
                        os.unlink(bg_path)

        # ── spike_alert 긴박감 효과 ──
        if is_spike:
            alert_bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ab_draw = ImageDraw.Draw(alert_bar)
            ab_draw.rectangle([(0, 0), (W, 6)], fill=(239, 68, 68, 220))
            ab_draw.rectangle([(0, H - 6), (W, H)], fill=(239, 68, 68, 220))
            for i in range(20):
                alpha = int(60 * (1 - i / 20))
                ab_draw.rectangle([(i, 0), (i + 1, H)], fill=(180, 20, 20, alpha))
                ab_draw.rectangle([(W - i - 1, 0), (W - i, H)], fill=(180, 20, 20, alpha))
            img = Image.alpha_composite(img, alert_bar)

        draw = ImageDraw.Draw(img)
        text_w = W - M * 2

        # ── 폰트 ──
        f_brand = _load_font(_FONT_BOLD, 22)
        f_tag = _load_font(_FONT_REGULAR, 11)
        f_badge_label = _load_font(_FONT_BOLD, 12)
        f_date = _load_font(_FONT_BOLD, 14)
        f_cc = _load_font(_FONT_BOLD, 12)
        f_cn = _load_font(_FONT_REGULAR, 12)
        f_sev = _load_font(_FONT_REGULAR, 11)
        f_tiny = _load_font(_FONT_REGULAR, 11)
        f_cred = _load_font(_FONT_REGULAR, 11)

        # spike_alert 이슈 폰트: 더 크고 볼드
        if is_spike:
            f_issue_en = _load_font(_FONT_BOLD, 22)
            f_issue_ko = _load_font(_FONT_BOLD, 20)
            line_h_en = 28
            line_h_ko = 26
        else:
            f_issue_en = _load_font(_FONT_REGULAR, 16)
            f_issue_ko = _load_font(_FONT_REGULAR, 16)
            line_h_en = 22
            line_h_ko = 22

        if not date_str:
            if is_spike:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            else:
                date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # ── 헤더 (상단 고정) ──
        y = M
        draw.text((M, y), "WeWantPeace", fill=_ACCENT, font=f_brand)
        y += 24
        draw.text((M, y), "Real-time Global Conflict Monitor", fill=_MUTED, font=f_tag)

        # 타입 뱃지 (오른쪽)
        type_label, type_color = _TYPE_CONFIG.get(content_type, ("POST", _ACCENT))
        if is_spike:
            f_badge_big = _load_font(_FONT_BOLD, 16)
            tw_badge = _tw(draw, type_label, f_badge_big)
            bx = W - M - tw_badge - 16
            draw.rounded_rectangle(
                [(bx, y - 22), (bx + tw_badge + 16, y + 2)],
                radius=5, fill=type_color,
            )
            draw.text((bx + 8, y - 20), type_label, fill=_WHITE, font=f_badge_big)
        else:
            tw_badge = _tw(draw, type_label, f_badge_label)
            bx = W - M - tw_badge - 12
            draw.rounded_rectangle(
                [(bx, y - 18), (bx + tw_badge + 12, y)],
                radius=4, fill=type_color,
            )
            draw.text((bx + 6, y - 17), type_label, fill=_WHITE, font=f_badge_label)
        y += 16

        hdr_line_color = (239, 68, 68) if is_spike else _DIVIDER
        draw.line([(M, y), (W - M, y)], fill=hdr_line_color, width=2 if is_spike else 1)
        y += 12

        # ── 날짜 (상단 고정) ──
        draw.text((M, y), date_str, fill=_LIGHT, font=f_date)
        y += 28

        header_bottom = y

        # ── 이슈 높이 계산 (중앙 정렬용) ──
        footer_h = 44
        issue_h_total = 0

        # 이슈 수에 따른 줄 수 제한 (spike_alert=1이슈→충분한 공간)
        n_issues = len(issues[:3]) if issues else 0
        max_lines = 8 if n_issues <= 1 else (5 if n_issues == 2 else 3)

        if issues:
            for idx, iss in enumerate(issues[:3]):
                en_lines = _wrap(iss.get("title_en", ""), f_issue_en, text_w - 24, draw)
                ko_lines = _wrap(iss.get("title_ko", ""), f_issue_ko, text_w - 24, draw)
                issue_h_total += 24  # 국가 뱃지 줄
                issue_h_total += min(len(en_lines), max_lines) * line_h_en
                issue_h_total += min(len(ko_lines), max_lines) * line_h_ko
                # 신뢰도 라인
                cred = _build_credibility_text(iss)
                if cred:
                    issue_h_total += 20
                issue_h_total += 6 + 14  # severity bar
                if idx < len(issues[:3]) - 1:
                    issue_h_total += 14
        else:
            issue_h_total = 200

        # 이슈 영역: header_bottom ~ (H - M - footer_h)
        avail_h = H - M - footer_h - header_bottom
        issue_y_start = max(header_bottom, header_bottom + (avail_h - issue_h_total) // 2)
        y = issue_y_start

        # ── 이슈 목록 ──
        max_y = H - M - footer_h - 6

        if issues:
            # 이슈 영역 반투명 패널 (가독성)
            panel_top = max(y - 8, header_bottom)
            panel_bot = min(y + issue_h_total + 8, max_y + 10)
            panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                [(M - 10, panel_top), (W - M + 10, panel_bot)],
                radius=12, fill=(10, 10, 18, 120),
            )
            img = Image.alpha_composite(img, panel)
            draw = ImageDraw.Draw(img)

            for idx, iss in enumerate(issues[:3]):
                if y >= max_y:
                    break

                cc = iss.get("country_code", "")
                cn = _COUNTRY_NAMES.get(cc, cc)
                sev = iss.get("severity", 0)
                title_en = _strip_emoji(iss.get("title_en", ""))
                title_ko = _strip_emoji(iss.get("title_ko", title_en))
                sc = _sev_color(sev)

                # 국가 뱃지 + severity 수치
                if cc:
                    ccw = _tw(draw, f" {cc} ", f_cc)
                    draw.rounded_rectangle(
                        [(M, y), (M + ccw + 2, y + 19)],
                        radius=4, fill=(*sc, 80),
                        outline=sc, width=1,
                    )
                    draw.text((M + 2, y + 2), f" {cc} ", fill=_WHITE, font=f_cc)
                    draw.text((M + ccw + 8, y + 3), cn, fill=_MUTED, font=f_cn)
                    sev_txt = f"Severity {sev}/100"
                    sw = _tw(draw, sev_txt, f_sev)
                    draw.text((W - M - sw, y + 4), sev_txt, fill=sc, font=f_sev)
                    y += 24

                # EN 라인
                en_lines = _wrap(title_en, f_issue_en, text_w - 24, draw)
                for li, line in enumerate(en_lines[:max_lines]):
                    if y >= max_y:
                        break
                    if is_spike:
                        draw.text((M + 8, y), line, fill=_WHITE, font=f_issue_en)
                    else:
                        prefix = "- " if li == 0 else "  "
                        draw.text((M + 8, y), prefix + line, fill=_LIGHT, font=f_issue_en)
                    y += line_h_en

                # KO 라인
                ko_lines = _wrap(title_ko, f_issue_ko, text_w - 24, draw)
                for li, line in enumerate(ko_lines[:max_lines]):
                    if y >= max_y:
                        break
                    if is_spike:
                        draw.text((M + 8, y), line, fill=_LIGHT, font=f_issue_ko)
                    else:
                        prefix = "- " if li == 0 else "  "
                        draw.text((M + 8, y), prefix + line, fill=_WHITE, font=f_issue_ko)
                    y += line_h_ko

                # 신뢰도 라인
                cred = _build_credibility_text(iss)
                if cred:
                    y += 4
                    # 방패 아이콘 대신 텍스트 뱃지
                    cred_display = f"\u2713 {cred}" if iss.get("is_verified") else cred
                    draw.text((M + 8, y), cred_display, fill=_MUTED, font=f_cred)
                    y += 16

                # 글자-바 간격
                y += 6

                # 개별 severity 바
                bar_w = text_w - 16
                draw.rounded_rectangle(
                    [(M + 8, y), (M + 8 + bar_w, y + 5)],
                    radius=2, fill=(35, 38, 50),
                )
                fill_w = int(bar_w * min(sev, 100) / 100)
                if fill_w > 0:
                    draw.rounded_rectangle(
                        [(M + 8, y), (M + 8 + fill_w, y + 5)],
                        radius=2, fill=sc,
                    )
                y += 14

                # 이슈 간 구분선
                if idx < len(issues) - 1 and y < max_y:
                    draw.line(
                        [(M, y), (W - M, y)],
                        fill=_DIVIDER, width=1,
                    )
                    y += 14

        elif body_text:
            f_fallback = _load_font(_FONT_REGULAR, 16)
            lines = _wrap(_strip_emoji(body_text), f_fallback, text_w, draw)
            for line in lines[:14]:
                if y >= max_y:
                    break
                draw.text((M, y), line, fill=_LIGHT, font=f_fallback)
                y += 22

        # ── 하단 ──
        bottom = H - M - 34
        draw.line([(M, bottom - 6), (W - M, bottom - 6)], fill=_DIVIDER, width=1)

        if hashtags:
            draw.text((M, bottom), " ".join(hashtags[:4]), fill=_ACCENT, font=f_tiny)

        bottom += 16
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        draw.text((M, bottom), ts, fill=_MUTED, font=f_tiny)
        url = "www.wewantpeace.live"
        uw = _tw(draw, url, f_tiny)
        draw.text((W - M - uw, bottom), url, fill=_ACCENT, font=f_tiny)

        final = img.convert("RGB")
        buf = io.BytesIO()
        final.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    except Exception:
        logger.exception("카드 이미지 생성 실패")
        return None


def save_card_temp(image_bytes: bytes, post_id: str) -> str | None:
    try:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", prefix=f"social-card-{post_id}-",
            delete=False,
        )
        tmp.write(image_bytes)
        tmp.close()
        return tmp.name
    except Exception:
        logger.exception("카드 이미지 임시 저장 실패")
        return None


async def generate_card_for_post(post, clusters=None) -> str | None:
    """카드 이미지 생성 + post.image_url에 경로 저장.

    clusters: list[IssueCluster] — 구조화된 이슈 데이터
    """
    issues = None
    bg_image_url = None

    if clusters:
        issues = []
        for c in clusters[:3]:
            issues.append({
                "title_en": c.title or "",
                "title_ko": c.title_ko or c.title or "",
                "country_code": c.country_code or "",
                "severity": c.severity or 0,
                "independent_sources": getattr(c, "independent_sources", 0),
                "source_tiers": getattr(c, "source_tiers", []),
                "is_verified": getattr(c, "is_verified", False),
                "event_count": getattr(c, "event_count", 0),
            })
        bg_image_url = getattr(clusters[0], "image_url", None)

    # spike_alert: 첫 클러스터의 last_event_at을 시간 포함 date_str로
    date_str = None
    if post.content_type == "spike_alert" and clusters:
        evt_time = getattr(clusters[0], "last_event_at", None)
        if evt_time:
            date_str = evt_time.strftime("%Y-%m-%d %H:%M UTC")

    # ── HTML/Playwright 카드 우선 시도 ──────────────────────────────────────
    # sync_playwright()는 asyncio 이벤트 루프가 활성화된 상태에서 호출 불가.
    # async def인 generate_card_for_post 내부에서 직접 호출하면
    # "Playwright Sync API inside the asyncio loop" 에러 발생.
    # → run_in_executor로 별도 스레드에서 실행 (이벤트 루프 없는 환경).
    image_bytes: bytes | None = None
    try:
        import asyncio
        import functools
        from worker.social.card_html_generator import generate_html_card
        fn = functools.partial(
            generate_html_card,
            content_type=post.content_type,
            issues=issues,
            hashtags=post.hashtags,
            date=date_str,
            image_url=bg_image_url,
        )
        loop = asyncio.get_event_loop()
        image_bytes = await loop.run_in_executor(None, fn)
    except Exception as e:
        logger.warning("HTML 카드 생성 불가, PIL 폴백으로 전환: %s", e)

    # ── PIL 폴백 ─────────────────────────────────────────────────────────────
    if not image_bytes:
        image_bytes = generate_card(
            content_type=post.content_type,
            issues=issues,
            body_text=post.body_text if not issues else None,
            hashtags=post.hashtags,
            bg_image_url=bg_image_url,
            date_str=date_str,
        )
    if not image_bytes:
        return None

    tmp_path = save_card_temp(image_bytes, str(post.id))
    if not tmp_path:
        return None

    # 즉시 Supabase Storage에 업로드 → public URL로 저장
    try:
        from worker.social.image_uploader import upload_image, is_configured
        if is_configured():
            public_url = upload_image(tmp_path, str(post.id))
            if public_url:
                post.image_url = public_url
                return public_url
    except Exception:
        logger.warning("Supabase 업로드 실패, 로컬 경로 유지: %s", tmp_path)

    # Supabase 미설정/실패 시 로컬 경로 폴백
    post.image_url = tmp_path
    return tmp_path

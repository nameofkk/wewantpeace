"""SNS 카드 이미지 생성기 — 720x720.

각 이슈를 국가 + EN/KO 제목 + 개별 severity로 표시.
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
    "spike_alert": ("BREAKING", (239, 68, 68)),
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


def generate_card(
    content_type: str,
    issues: list[dict] | None = None,
    body_text: str | None = None,
    hashtags: list[str] | None = None,
    bg_image_url: str | None = None,
    date_str: str | None = None,
) -> bytes | None:
    """720x720 SNS 카드.

    issues: [{"title_en", "title_ko", "country_code", "severity"}, ...]
    body_text: issues 없을 때 폴백용 flat 텍스트
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.error("Pillow 미설치")
        return None

    try:
        W, H = 720, 720
        M = 40

        # ── 배경 ──
        is_spike = content_type == "spike_alert"
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
                    if content_type == "spike_alert":
                        # 긴박한 빨간 틴트 오버레이
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
            # 상하단 빨간 경고 바
            alert_bar = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ab_draw = ImageDraw.Draw(alert_bar)
            ab_draw.rectangle([(0, 0), (W, 6)], fill=(239, 68, 68, 220))
            ab_draw.rectangle([(0, H - 6), (W, H)], fill=(239, 68, 68, 220))
            # 좌우 빨간 비네팅
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
        f_issue = _load_font(_FONT_REGULAR, 16)
        f_sev = _load_font(_FONT_REGULAR, 11)
        f_tiny = _load_font(_FONT_REGULAR, 11)

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
            # BREAKING: 더 크고 강렬한 뱃지
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

        header_bottom = y  # 헤더 아래 끝

        # ── 이슈 높이 계산 (중앙 정렬용) ──
        footer_h = 44
        issue_h_total = 0

        if issues:
            for idx, iss in enumerate(issues[:3]):
                en_lines = _wrap(iss.get("title_en", ""), f_issue, text_w - 24, draw)
                ko_lines = _wrap(iss.get("title_ko", ""), f_issue, text_w - 24, draw)
                issue_h_total += 24 + min(len(en_lines), 2) * 22 + min(len(ko_lines), 2) * 22 + 6 + 14
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
                    # 국가코드 뱃지
                    ccw = _tw(draw, f" {cc} ", f_cc)
                    draw.rounded_rectangle(
                        [(M, y), (M + ccw + 2, y + 19)],
                        radius=4, fill=(*sc, 80),
                        outline=sc, width=1,
                    )
                    draw.text((M + 2, y + 2), f" {cc} ", fill=_WHITE, font=f_cc)
                    # 국가명
                    draw.text((M + ccw + 8, y + 3), cn, fill=_MUTED, font=f_cn)
                    # severity 오른쪽 (라벨 포함)
                    sev_txt = f"Severity {sev}/100"
                    sw = _tw(draw, sev_txt, f_sev)
                    draw.text((W - M - sw, y + 4), sev_txt, fill=sc, font=f_sev)
                    y += 24

                # EN 라인 (- 접두사)
                en_lines = _wrap(title_en, f_issue, text_w - 24, draw)
                for li, line in enumerate(en_lines[:2]):
                    if y >= max_y:
                        break
                    prefix = "- " if li == 0 else "  "
                    draw.text((M + 8, y), prefix + line, fill=_LIGHT, font=f_issue)
                    y += 22

                # KO 라인 (- 접두사)
                ko_lines = _wrap(title_ko, f_issue, text_w - 24, draw)
                for li, line in enumerate(ko_lines[:2]):
                    if y >= max_y:
                        break
                    prefix = "- " if li == 0 else "  "
                    draw.text((M + 8, y), prefix + line, fill=_WHITE, font=f_issue)
                    y += 22

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
            # 폴백: flat 텍스트
            lines = _wrap(_strip_emoji(body_text), f_issue, text_w, draw)
            for line in lines[:12]:
                if y >= max_y:
                    break
                draw.text((M, y), line, fill=_LIGHT, font=f_issue)
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
            })
        # 첫 클러스터의 이미지를 배경으로
        bg_image_url = getattr(clusters[0], "image_url", None)

    # spike_alert: 첫 클러스터의 last_event_at을 시간 포함 date_str로
    date_str = None
    if post.content_type == "spike_alert" and clusters:
        evt_time = getattr(clusters[0], "last_event_at", None)
        if evt_time:
            date_str = evt_time.strftime("%Y-%m-%d %H:%M UTC")

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
    if tmp_path:
        post.image_url = tmp_path
    return tmp_path

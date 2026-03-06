"""SNS 카드 이미지 생성기 — Pillow 기반 720x720 다크 카드."""
import io
import logging
import os
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# 폰트 경로 (Railway Docker에서도 사용 가능한 범용 경로)
_FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# 색상 팔레트 (다크 테마)
_BG_COLOR = (15, 15, 25)       # 짙은 남색 배경
_TEXT_COLOR = (240, 240, 245)   # 밝은 흰색
_ACCENT_COLOR = (59, 130, 246) # 파란색 (primary)
_MUTED_COLOR = (148, 163, 184) # 회색 텍스트
_SEVERITY_COLORS = {
    "low": (34, 197, 94),       # 녹색
    "medium": (234, 179, 8),    # 노란색
    "high": (239, 68, 68),      # 빨간색
}

# 국가 플래그 이모지 → 텍스트 대체
_COUNTRY_NAMES = {
    "UA": "Ukraine", "RU": "Russia", "IL": "Israel", "PS": "Palestine",
    "IR": "Iran", "CN": "China", "TW": "Taiwan", "KP": "N.Korea",
    "KR": "S.Korea", "US": "USA", "SY": "Syria", "YE": "Yemen",
    "MM": "Myanmar", "SD": "Sudan", "ET": "Ethiopia", "AF": "Afghanistan",
    "IQ": "Iraq", "LB": "Lebanon", "PK": "Pakistan", "IN": "India",
    "JP": "Japan", "TR": "Turkey", "EG": "Egypt", "SA": "Saudi Arabia",
}


def _find_font(size: int):
    """사용 가능한 폰트를 찾아 반환."""
    from PIL import ImageFont
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    # 폴백: 기본 폰트
    return ImageFont.load_default()


def _wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    """텍스트를 max_width에 맞게 줄바꿈."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines or [text]


def generate_card(
    body_text: str,
    content_type: str,
    risk_level: str,
    country_code: str | None = None,
    severity: int | None = None,
    hashtags: list[str] | None = None,
) -> bytes | None:
    """720x720 SNS 카드 이미지 생성.

    Returns:
        PNG 이미지 바이트 또는 실패 시 None
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.error("Pillow 미설치, 카드 생성 불가")
        return None

    try:
        W, H = 720, 720
        img = Image.new("RGB", (W, H), _BG_COLOR)
        draw = ImageDraw.Draw(img)

        # 폰트
        font_title = _find_font(28)
        font_body = _find_font(22)
        font_small = _find_font(16)
        font_label = _find_font(14)

        y = 40

        # ── 상단: WeWantPeace 브랜딩 ──
        draw.text((40, y), "WeWantPeace", fill=_ACCENT_COLOR, font=font_title)
        y += 45

        # 구분선
        draw.line([(40, y), (W - 40, y)], fill=(50, 50, 70), width=2)
        y += 20

        # ── 콘텐츠 타입 라벨 ──
        type_labels = {
            "daily_movers": "DAILY MOVERS",
            "spike_alert": "⚡ SPIKE ALERT",
            "weekly_recap": "WEEKLY RECAP",
        }
        type_label = type_labels.get(content_type, content_type.upper())
        draw.text((40, y), type_label, fill=_ACCENT_COLOR, font=font_small)

        # 국가 표시 (오른쪽)
        if country_code:
            country_name = _COUNTRY_NAMES.get(country_code, country_code)
            bbox = draw.textbbox((0, 0), country_name, font=font_small)
            cw = bbox[2] - bbox[0]
            draw.text((W - 40 - cw, y), country_name, fill=_MUTED_COLOR, font=font_small)
        y += 35

        # ── 본문 텍스트 ──
        max_text_width = W - 80
        lines = _wrap_text(body_text, font_body, max_text_width, draw)
        max_lines = 10
        for i, line in enumerate(lines[:max_lines]):
            draw.text((40, y), line, fill=_TEXT_COLOR, font=font_body)
            y += 32
            if i >= max_lines - 1 and len(lines) > max_lines:
                draw.text((40, y), "...", fill=_MUTED_COLOR, font=font_body)
                y += 32
                break
        y += 15

        # ── Severity 바 ──
        if severity is not None:
            bar_y = y
            bar_width = W - 80
            bar_height = 8

            # 배경 바
            draw.rounded_rectangle(
                [(40, bar_y), (40 + bar_width, bar_y + bar_height)],
                radius=4, fill=(40, 40, 55),
            )

            # 채운 바
            sev_color = _SEVERITY_COLORS.get(risk_level, _SEVERITY_COLORS["medium"])
            fill_width = int(bar_width * min(severity, 100) / 100)
            if fill_width > 0:
                draw.rounded_rectangle(
                    [(40, bar_y), (40 + fill_width, bar_y + bar_height)],
                    radius=4, fill=sev_color,
                )

            # Severity 라벨
            y = bar_y + bar_height + 8
            sev_text = f"Severity: {severity}/100"
            draw.text((40, y), sev_text, fill=_MUTED_COLOR, font=font_label)

            risk_text = risk_level.upper()
            bbox = draw.textbbox((0, 0), risk_text, font=font_label)
            rw = bbox[2] - bbox[0]
            draw.text((W - 40 - rw, y), risk_text, fill=sev_color, font=font_label)
            y += 30

        # ── 해시태그 ──
        if hashtags:
            hashtag_str = " ".join(hashtags[:5])
            ht_lines = _wrap_text(hashtag_str, font_label, max_text_width, draw)
            for line in ht_lines[:2]:
                draw.text((40, y), line, fill=_ACCENT_COLOR, font=font_label)
                y += 22

        # ── 하단: 날짜 + 워터마크 ──
        bottom_y = H - 50
        draw.line([(40, bottom_y - 15), (W - 40, bottom_y - 15)], fill=(50, 50, 70), width=1)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        draw.text((40, bottom_y), now_str, fill=_MUTED_COLOR, font=font_label)

        watermark = "www.wewantpeace.live"
        bbox = draw.textbbox((0, 0), watermark, font=font_label)
        ww = bbox[2] - bbox[0]
        draw.text((W - 40 - ww, bottom_y), watermark, fill=_MUTED_COLOR, font=font_label)

        # PNG로 인코딩
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    except Exception:
        logger.exception("카드 이미지 생성 실패")
        return None


def save_card_temp(image_bytes: bytes, post_id: str) -> str | None:
    """이미지 바이트를 임시 파일로 저장. X 어댑터에서 직접 업로드용."""
    import tempfile
    try:
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", prefix=f"social-card-{post_id}-",
            delete=False,
        )
        tmp.write(image_bytes)
        tmp.close()
        logger.info("카드 이미지 임시 저장: %s", tmp.name)
        return tmp.name
    except Exception:
        logger.exception("카드 이미지 임시 저장 실패")
        return None


async def generate_card_for_post(
    post,
    cluster=None,
) -> str | None:
    """카드 이미지 생성 + 임시 파일 저장 + post.image_url에 경로 저장.

    Returns:
        임시 파일 경로 또는 None
    """
    severity = None
    country_code = None
    if cluster:
        severity = cluster.severity
        country_code = cluster.country_code

    image_bytes = generate_card(
        body_text=post.body_text,
        content_type=post.content_type,
        risk_level=post.risk_level,
        country_code=country_code,
        severity=severity,
        hashtags=post.hashtags,
    )
    if not image_bytes:
        return None

    tmp_path = save_card_temp(image_bytes, str(post.id))
    if tmp_path:
        # image_url에 로컬 파일 경로 저장 (X 어댑터에서 사용)
        post.image_url = tmp_path
        logger.info("카드 이미지 생성 완료: %s → %s", post.id, tmp_path)
    return tmp_path

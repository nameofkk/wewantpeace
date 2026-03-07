"""
OG 이미지 생성 스크립트.
출력: frontend/public/og-image.png (1200x630)
      frontend/public/og-image-twitter.png (1200x630)
"""
from PIL import Image, ImageDraw, ImageFont
import math
import os

W, H = 1200, 630
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")

# 색상
BG_DARK = (10, 15, 30)
GRID_COLOR = (59, 130, 246, 12)  # 파란 그리드
GLOW_CENTER = (59, 130, 246)
WHITE = (241, 245, 249)
MUTED = (148, 163, 184)
RED = (239, 68, 68)
GREEN = (16, 185, 129)
AMBER = (245, 158, 11)


def draw_gradient_bg(draw: ImageDraw.ImageDraw, img: Image.Image):
    """다크 그라데이션 배경"""
    for y in range(H):
        r = int(10 + (y / H) * 8)
        g = int(15 + (y / H) * 12)
        b = int(30 + (y / H) * 18)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def draw_grid(draw: ImageDraw.ImageDraw):
    """배경 그리드 패턴"""
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=(30, 45, 75, 20), width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=(30, 45, 75, 20), width=1)


def draw_radar_glow(img: Image.Image):
    """중앙 레이더 글로우"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx, cy = W // 2, H // 2 - 30
    for r in range(200, 0, -2):
        alpha = int(15 * (1 - r / 200))
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(GLOW_CENTER[0], GLOW_CENTER[1], GLOW_CENTER[2], alpha),
        )
    img.paste(Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 0)), overlay), mask=overlay)


def draw_radar_rings(draw: ImageDraw.ImageDraw):
    """레이더 동심원"""
    cx, cy = W // 2, H // 2 - 30
    for r in [60, 110, 160]:
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(59, 130, 246, 30),
            width=1,
        )


def get_font(size: int, bold: bool = False):
    """시스템 폰트 fallback"""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_text_center(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=fill)


def draw_feature_tags(draw: ImageDraw.ImageDraw, y: int):
    """피처 태그: 3개 원형 배지"""
    tags = [
        ("40+ Countries", GREEN),
        ("AI Analysis", (59, 130, 246)),
        ("Spike Alert", RED),
    ]
    font = get_font(14, bold=True)
    total_w = 0
    tag_sizes = []
    pad_x, pad_y = 16, 8
    gap = 12
    for label, _ in tags:
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        tag_sizes.append(tw)
        total_w += tw + pad_x * 2
    total_w += gap * (len(tags) - 1)
    sx = (W - total_w) // 2
    for i, (label, color) in enumerate(tags):
        tw = tag_sizes[i]
        bw = tw + pad_x * 2
        bh = 30
        r = bh // 2
        draw.rounded_rectangle(
            [sx, y, sx + bw, y + bh],
            radius=r,
            fill=(color[0], color[1], color[2], 30),
            outline=(color[0], color[1], color[2], 80),
        )
        draw.text((sx + pad_x, y + (bh - 16) // 2), label, font=font, fill=color)
        sx += bw + gap


def draw_live_indicator(draw: ImageDraw.ImageDraw, x: int, y: int):
    """LIVE 인디케이터"""
    font = get_font(12, bold=True)
    draw.ellipse([x, y + 4, x + 8, y + 12], fill=RED)
    draw.text((x + 14, y), "LIVE", font=font, fill=RED)


def generate():
    img = Image.new("RGBA", (W, H), BG_DARK + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    draw_gradient_bg(draw, img)
    draw_grid(draw)
    draw_radar_glow(img)
    draw = ImageDraw.Draw(img, "RGBA")  # re-get draw after composite
    draw_radar_rings(draw)

    # LIVE 인디케이터
    draw_live_indicator(draw, W // 2 - 24, 180)

    # 타이틀
    title_font = get_font(42, bold=True)
    draw_text_center(draw, 210, "WeWantPeace", title_font, WHITE)

    # 서브타이틀
    sub_font = get_font(18)
    draw_text_center(draw, 270, "Real-time Global Conflict Monitor", sub_font, MUTED)

    # 구분선
    line_y = 310
    line_w = 200
    draw.line(
        [(W // 2 - line_w, line_y), (W // 2 + line_w, line_y)],
        fill=(59, 130, 246, 60),
        width=1,
    )

    # 피처 태그
    draw_feature_tags(draw, 340)

    # 하단 URL
    url_font = get_font(13)
    draw_text_center(draw, H - 50, "www.wewantpeace.live", url_font, (100, 116, 139))

    # 데이터 요소 — 좌우에 KScore 같은 숫자
    stat_font = get_font(28, bold=True)
    stat_label_font = get_font(11)

    # 왼쪽 — Tension Index
    draw.text((80, 420), "7.2", font=stat_font, fill=RED)
    draw.text((80, 455), "Tension Index", font=stat_label_font, fill=MUTED)

    # 오른쪽 — Active Issues
    draw.text((W - 200, 420), "142", font=stat_font, fill=AMBER)
    draw.text((W - 200, 455), "Active Issues", font=stat_label_font, fill=MUTED)

    # 저장
    os.makedirs(OUT_DIR, exist_ok=True)
    rgb_img = Image.new("RGB", (W, H), BG_DARK)
    rgb_img.paste(img, mask=img.split()[3])

    og_path = os.path.join(OUT_DIR, "og-image.png")
    twitter_path = os.path.join(OUT_DIR, "og-image-twitter.png")
    rgb_img.save(og_path, "PNG", optimize=True)
    rgb_img.save(twitter_path, "PNG", optimize=True)
    print(f"Generated: {og_path}")
    print(f"Generated: {twitter_path}")


if __name__ == "__main__":
    generate()

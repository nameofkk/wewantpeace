"""
OG 이미지 생성 스크립트.
출력: frontend/public/og-image.png (1200x630)
      frontend/public/og-image-twitter.png (1200x630)
"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 1200, 630
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")
LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "logo-eye.png")

# 색상
BG_DARK = (15, 23, 42)
GLOW_CENTER = (59, 130, 246)
WHITE = (241, 245, 249)
MUTED = (148, 163, 184)
GREEN = (16, 185, 129)
RED = (239, 68, 68)


def draw_gradient_bg(draw: ImageDraw.ImageDraw):
    """다크 그라데이션 배경 — 기존보다 밝게"""
    for y in range(H):
        t = y / H
        r = int(15 + t * 12)
        g = int(23 + t * 16)
        b = int(42 + t * 22)
        draw.line([(0, y), (W, y)], fill=(r, g, b))


def draw_grid(draw: ImageDraw.ImageDraw):
    """배경 그리드 패턴 — 잘 보이게 opacity 높임"""
    grid_color = (59, 130, 246, 30)
    for x in range(0, W, 50):
        draw.line([(x, 0), (x, H)], fill=grid_color, width=1)
    for y in range(0, H, 50):
        draw.line([(0, y), (W, y)], fill=grid_color, width=1)


def draw_radar_glow(img: Image.Image):
    """중앙 레이더 글로우 — 더 밝게"""
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    cx, cy = W // 2, H // 2
    for r in range(300, 0, -2):
        alpha = int(28 * (1 - r / 300))
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(GLOW_CENTER[0], GLOW_CENTER[1], GLOW_CENTER[2], alpha),
        )
    img.paste(Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 0)), overlay), mask=overlay)


def draw_radar_rings(draw: ImageDraw.ImageDraw):
    """레이더 동심원 — 더 밝게, 더 크게"""
    cx, cy = W // 2, H // 2
    ring_color = (59, 130, 246, 50)
    for r in [100, 180, 260]:
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=ring_color,
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
    """피처 태그 — 크게"""
    tags = [
        ("195 Countries", GREEN),
        ("Spike Alert", RED),
    ]
    font = get_font(28, bold=True)
    total_w = 0
    tag_sizes = []
    pad_x, pad_y = 32, 16
    gap = 28
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
        bh = 56
        r = bh // 2
        draw.rounded_rectangle(
            [sx, y, sx + bw, y + bh],
            radius=r,
            fill=(color[0], color[1], color[2], 45),
            outline=(color[0], color[1], color[2], 140),
            width=2,
        )
        bbox = draw.textbbox((0, 0), label, font=font)
        th = bbox[3] - bbox[1]
        draw.text((sx + pad_x, y + (bh - th) // 2), label, font=font, fill=color)
        sx += bw + gap


def draw_live_indicator(draw: ImageDraw.ImageDraw, cx: int, y: int):
    """LIVE 인디케이터 — 크게"""
    font = get_font(22, bold=True)
    label = "LIVE"
    dot_r = 8
    gap = 10
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    total_w = dot_r * 2 + gap + tw
    sx = cx - total_w // 2
    dot_cy = y + th // 2 + 2
    draw.ellipse([sx, dot_cy - dot_r, sx + dot_r * 2, dot_cy + dot_r], fill=RED)
    draw.text((sx + dot_r * 2 + gap, y), label, font=font, fill=RED)


def generate():
    img = Image.new("RGBA", (W, H), BG_DARK + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    draw_gradient_bg(draw)
    draw_grid(draw)
    draw_radar_glow(img)
    draw = ImageDraw.Draw(img, "RGBA")
    draw_radar_rings(draw)

    # --- 콘텐츠 수직 정중앙 배치 (하단 URL 제거) ---
    # 로고(150) + gap(24) + 타이틀(72) + gap(12) + LIVE(22) + gap(20) + 서브(32) + gap(32) + 구분선(1) + gap(28) + 태그(56)
    # = 449px → 시작 Y = (630 - 449) / 2 ≈ 90
    content_h = 150 + 24 + 72 + 12 + 22 + 20 + 32 + 32 + 1 + 28 + 56
    start_y = (H - content_h) // 2

    # 로고 이미지 — 크게 (150px)
    logo_y = start_y
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo_h = 150
        ratio = logo_h / logo.height
        logo_w = int(logo.width * ratio)
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        logo_x = (W - logo_w) // 2
        img.paste(logo, (logo_x, logo_y), logo)
        draw = ImageDraw.Draw(img, "RGBA")

    # 타이틀 — 크게 (72pt)
    title_y = logo_y + 150 + 24
    title_font = get_font(72, bold=True)
    draw_text_center(draw, title_y, "WeWantPeace", title_font, WHITE)

    # LIVE 인디케이터 — 크게 (22pt)
    live_y = title_y + 72 + 12
    draw_live_indicator(draw, W // 2, live_y)

    # 서브타이틀 — 크게 (32pt)
    sub_y = live_y + 22 + 20
    sub_font = get_font(32)
    draw_text_center(draw, sub_y, "Real-time Global Conflict Monitor", sub_font, MUTED)

    # 구분선
    line_y = sub_y + 32 + 32
    line_w = 300
    draw.line(
        [(W // 2 - line_w, line_y), (W // 2 + line_w, line_y)],
        fill=(59, 130, 246, 90),
        width=2,
    )

    # 피처 태그 — 크게 (28pt, 56px tall)
    tag_y = line_y + 28
    draw_feature_tags(draw, tag_y)

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

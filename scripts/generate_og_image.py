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
BG_DARK = (10, 15, 30)
GLOW_CENTER = (59, 130, 246)
WHITE = (241, 245, 249)
MUTED = (148, 163, 184)
GREEN = (16, 185, 129)
RED = (239, 68, 68)


def draw_gradient_bg(draw: ImageDraw.ImageDraw):
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
    cx, cy = W // 2, H // 2 - 20
    for r in range(250, 0, -2):
        alpha = int(18 * (1 - r / 250))
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(GLOW_CENTER[0], GLOW_CENTER[1], GLOW_CENTER[2], alpha),
        )
    img.paste(Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 0)), overlay), mask=overlay)


def draw_radar_rings(draw: ImageDraw.ImageDraw):
    """레이더 동심원"""
    cx, cy = W // 2, H // 2 - 20
    for r in [80, 140, 200]:
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(59, 130, 246, 25),
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
    """피처 태그: 2개 배지 (AI 제거)"""
    tags = [
        ("195 Countries", GREEN),
        ("Spike Alert", RED),
    ]
    font = get_font(20, bold=True)
    total_w = 0
    tag_sizes = []
    pad_x, pad_y = 24, 12
    gap = 20
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
        bh = 42
        r = bh // 2
        draw.rounded_rectangle(
            [sx, y, sx + bw, y + bh],
            radius=r,
            fill=(color[0], color[1], color[2], 35),
            outline=(color[0], color[1], color[2], 100),
        )
        bbox = draw.textbbox((0, 0), label, font=font)
        th = bbox[3] - bbox[1]
        draw.text((sx + pad_x, y + (bh - th) // 2), label, font=font, fill=color)
        sx += bw + gap


def draw_live_indicator(draw: ImageDraw.ImageDraw, cx: int, y: int):
    """LIVE 인디케이터 (중앙 정렬)"""
    font = get_font(16, bold=True)
    label = "LIVE"
    dot_r = 6
    gap = 8
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    total_w = dot_r * 2 + gap + tw
    sx = cx - total_w // 2
    draw.ellipse([sx, y + (th - dot_r * 2) // 2 + 2, sx + dot_r * 2, y + (th - dot_r * 2) // 2 + 2 + dot_r * 2], fill=RED)
    draw.text((sx + dot_r * 2 + gap, y), label, font=font, fill=RED)


def generate():
    img = Image.new("RGBA", (W, H), BG_DARK + (255,))
    draw = ImageDraw.Draw(img, "RGBA")

    draw_gradient_bg(draw)
    draw_grid(draw)
    draw_radar_glow(img)
    draw = ImageDraw.Draw(img, "RGBA")  # re-get draw after composite
    draw_radar_rings(draw)

    # --- 모든 요소 수직 중앙 정렬 ---
    # 총 높이 계산: 로고(100) + gap(20) + title(56) + gap(10) + LIVE(16) + gap(16) + subtitle(24) + gap(24) + divider(1) + gap(24) + tags(42) + gap(24) + url(16)
    # ≈ 310px → 시작 Y = (630 - 310) / 2 ≈ 120

    # 로고 이미지
    logo_y = 105
    if os.path.exists(LOGO_PATH):
        logo = Image.open(LOGO_PATH).convert("RGBA")
        # 로고 크기 조정 (높이 100px 기준)
        logo_h = 100
        ratio = logo_h / logo.height
        logo_w = int(logo.width * ratio)
        logo = logo.resize((logo_w, logo_h), Image.LANCZOS)
        logo_x = (W - logo_w) // 2
        img.paste(logo, (logo_x, logo_y), logo)
        draw = ImageDraw.Draw(img, "RGBA")  # re-get after paste

    # 타이틀
    title_y = logo_y + 115
    title_font = get_font(56, bold=True)
    draw_text_center(draw, title_y, "WeWantPeace", title_font, WHITE)

    # LIVE 인디케이터
    live_y = title_y + 70
    draw_live_indicator(draw, W // 2, live_y)

    # 서브타이틀
    sub_y = live_y + 32
    sub_font = get_font(24)
    draw_text_center(draw, sub_y, "Real-time Global Conflict Monitor", sub_font, MUTED)

    # 구분선
    line_y = sub_y + 44
    line_w = 240
    draw.line(
        [(W // 2 - line_w, line_y), (W // 2 + line_w, line_y)],
        fill=(59, 130, 246, 60),
        width=1,
    )

    # 피처 태그
    tag_y = line_y + 20
    draw_feature_tags(draw, tag_y)

    # 하단 URL
    url_font = get_font(16)
    draw_text_center(draw, H - 48, "wewantpeace.live", url_font, (100, 116, 139))

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

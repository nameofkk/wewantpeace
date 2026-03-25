"""온보딩 히어로 개선안 목업 이미지 생성"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math, random

W, H = 390, 844  # iPhone 14 사이즈
BG = (15, 23, 42)  # slate-900
PRIMARY = (99, 102, 241)  # indigo-500
EMERALD = (16, 185, 129)
RED = (239, 68, 68)
ORANGE = (249, 115, 22)
AMBER = (234, 179, 8)
WHITE = (255, 255, 255)
MUTED = (148, 163, 184)  # slate-400
CARD_BG = (30, 41, 59)  # slate-800
CARD_BORDER = (51, 65, 85)  # slate-700

# 폰트 로드
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
FONT_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

def font(size, bold=False):
    path = FONT_BOLD if bold else FONT_REG
    return ImageFont.truetype(path, size, index=1)  # index=1 = KR

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# ── 배경: 점 패턴 (세계지도 느낌) ──
random.seed(42)
for _ in range(200):
    x = random.randint(20, W - 20)
    y = random.randint(60, 320)
    opacity = random.randint(15, 40)
    draw.ellipse([x, y, x + 2, y + 2], fill=(*PRIMARY, opacity))

# ── 배경: 이슈 핑 표시 ──
pings = [(180, 140, RED), (280, 180, ORANGE), (120, 200, RED), (310, 130, AMBER), (90, 160, ORANGE), (250, 220, RED)]
for px, py, color in pings:
    for r in range(12, 2, -2):
        alpha = max(10, 60 - r * 5)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(*color[:3], alpha))
    draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=color)

# ── 상단: 스킵 버튼 ──
draw.text((W - 60, 54), "건너뛰기", fill=MUTED, font=font(12))

# ── 히어로 비주얼: 가상 지도 프레임 ──
map_top = 80
map_h = 200
map_rect = [20, map_top, W - 20, map_top + map_h]

# 지도 영역 배경 (그라데이션)
for y in range(map_top, map_top + map_h):
    progress = (y - map_top) / map_h
    r = int(20 + 10 * progress)
    g = int(30 + 15 * progress)
    b = int(50 + 10 * progress)
    draw.line([(20, y), (W - 20, y)], fill=(r, g, b))

# 지도 프레임 라운드 코너
draw.rounded_rectangle(map_rect, radius=16, outline=CARD_BORDER, width=1)

# 지도 안에 점들 (대륙 표현)
# 유럽/중동
for _ in range(40):
    x = random.randint(180, 280)
    y = random.randint(map_top + 40, map_top + 100)
    draw.ellipse([x, y, x + 2, y + 2], fill=(99, 102, 241, 40))

# 아시아
for _ in range(35):
    x = random.randint(260, 350)
    y = random.randint(map_top + 50, map_top + 130)
    draw.ellipse([x, y, x + 2, y + 2], fill=(99, 102, 241, 40))

# 아프리카
for _ in range(25):
    x = random.randint(180, 240)
    y = random.randint(map_top + 90, map_top + 170)
    draw.ellipse([x, y, x + 2, y + 2], fill=(99, 102, 241, 40))

# 남미
for _ in range(20):
    x = random.randint(80, 140)
    y = random.randint(map_top + 100, map_top + 180)
    draw.ellipse([x, y, x + 2, y + 2], fill=(99, 102, 241, 40))

# 북미
for _ in range(20):
    x = random.randint(40, 130)
    y = random.randint(map_top + 40, map_top + 100)
    draw.ellipse([x, y, x + 2, y + 2], fill=(99, 102, 241, 40))

# 지도 위에 이슈 핑 (빨간 점 + 글로우)
map_pings = [
    (220, map_top + 60, RED, "우크라이나"),
    (240, map_top + 85, ORANGE, "이란"),
    (300, map_top + 95, RED, "미얀마"),
    (200, map_top + 130, AMBER, "수단"),
    (260, map_top + 75, ORANGE, "이스라엘"),
]
for px, py, color, label in map_pings:
    # 글로우
    for r in range(10, 3, -1):
        alpha = max(5, 40 - r * 4)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(*color[:3], alpha))
    draw.ellipse([px - 3, py - 3, px + 3, py + 3], fill=color)

# 지도 왼쪽 상단에 "LIVE" 배지
live_x, live_y = 32, map_top + 12
draw.rounded_rectangle([live_x, live_y, live_x + 52, live_y + 20], radius=10, fill=(16, 185, 129, 40))
draw.ellipse([live_x + 8, live_y + 7, live_x + 14, live_y + 13], fill=EMERALD)
draw.text((live_x + 18, live_y + 3), "LIVE", fill=EMERALD, font=font(11, bold=True))

# 지도 오른쪽 상단에 숫자
draw.text((W - 100, map_top + 12), "12,847건 수집", fill=(*MUTED, 180), font=font(10))

# ── 메인 헤드라인 ──
headline_y = map_top + map_h + 28
draw.text((W // 2, headline_y), "세계가 위험해지기 전에", fill=WHITE, font=font(24, bold=True), anchor="mt")
draw.text((W // 2, headline_y + 34), "먼저 알 수 있습니다", fill=WHITE, font=font(24, bold=True), anchor="mt")

# ── 서브 헤드라인 ──
sub_y = headline_y + 76
draw.text((W // 2, sub_y), "195개국 · 66개 소스 · 5분마다 업데이트", fill=MUTED, font=font(13), anchor="mt")

# ── 플레이스토어 1위 배지 ──
badge_y = sub_y + 28
badge_w = 200
badge_x = (W - badge_w) // 2
draw.rounded_rectangle(
    [badge_x, badge_y, badge_x + badge_w, badge_y + 28],
    radius=14, fill=(234, 179, 8, 25), outline=(234, 179, 8, 80)
)
draw.text((W // 2, badge_y + 6), "🏆 플레이스토어 뉴스 앱 1위", fill=(250, 204, 21), font=font(12, bold=True), anchor="mt")

# ── 숫자 카드 3개 ──
card_y = badge_y + 48
card_w = (W - 20 * 2 - 10 * 2) // 3  # 3열, 간격 10
cards = [
    ("12,847", "오늘 수집", PRIMARY),
    ("195", "개국 커버", EMERALD),
    ("5min", "업데이트 간격", ORANGE),
]

for i, (num, label, color) in enumerate(cards):
    cx = 20 + i * (card_w + 10)
    # 카드 배경
    draw.rounded_rectangle(
        [cx, card_y, cx + card_w, card_y + 72],
        radius=12, fill=CARD_BG, outline=CARD_BORDER
    )
    # 상단 색 라인
    draw.line([(cx + 12, card_y + 8), (cx + 32, card_y + 8)], fill=color, width=2)
    # 숫자
    draw.text((cx + card_w // 2, card_y + 24), num, fill=WHITE, font=font(20, bold=True), anchor="mt")
    # 라벨
    draw.text((cx + card_w // 2, card_y + 50), label, fill=MUTED, font=font(10), anchor="mt")

# ── 핵심 가치 3개 (아이콘 없이 간결하게) ──
val_y = card_y + 92
values = [
    ("전쟁·분쟁 뉴스를 로이터보다 빠르게", "텔레그램 OSINT 채널 포함 66개 소스 실시간 수집"),
    ("내 나라에 미치는 영향을 숫자로", "KScore로 분쟁의 한국 영향도 0~10점 수치화"),
    ("위험이 감지되면 즉시 알림", "관심 국가 설정 → 긴장도 급상승 시 푸시 알림"),
]

for i, (title, desc) in enumerate(values):
    vy = val_y + i * 52
    # 번호 원
    draw.ellipse([28, vy, 44, vy + 16], fill=PRIMARY)
    draw.text((36, vy + 1), str(i + 1), fill=WHITE, font=font(10, bold=True), anchor="mt")
    # 제목
    draw.text((54, vy - 1), title, fill=WHITE, font=font(13, bold=True))
    # 설명
    draw.text((54, vy + 18), desc, fill=(*MUTED, 160), font=font(10))

# ── CTA 버튼 ──
cta_y = H - 110
cta_rect = [24, cta_y, W - 24, cta_y + 50]

# 버튼 그라데이션 (단색으로 대체)
draw.rounded_rectangle(cta_rect, radius=16, fill=PRIMARY)
# 버튼 글로우
for r in range(3):
    draw.rounded_rectangle(
        [24 - r, cta_y - r, W - 24 + r, cta_y + 50 + r],
        radius=16 + r, outline=(*PRIMARY, 30)
    )
draw.text((W // 2, cta_y + 17), "지금 확인하기 →", fill=WHITE, font=font(16, bold=True), anchor="mt")

# ── 수집처 마퀴 ──
marquee_y = cta_y + 64
sources = "Reuters · AP · BBC · ACLED · GDELT · NASA FIRMS · UCDP · OCHA · Al Jazeera"
draw.text((W // 2, marquee_y), sources, fill=(*MUTED, 80), font=font(9), anchor="mt")

# ── 저장 ──
OUTPUT = "/mnt/c/Users/krshi/OneDrive/바탕 화면/온보딩_히어로_개선안.png"
img.save(OUTPUT, "PNG", quality=95)
print(f"목업 이미지 생성 완료: {OUTPUT}")
print(f"사이즈: {W}x{H}px (iPhone 14 기준)")

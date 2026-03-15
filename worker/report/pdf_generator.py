"""주간 리포트 PDF 생성기 — ReportLab + matplotlib (CrowdStrike/ACLED 스타일).

8-10 페이지 구성:
  1. Cover Page
  2. Executive Summary (BLUF)
  3. Key Metrics Dashboard
  4. TOP 5 Issues
  5. Country Risk Table
  6. Intelligence Summary
  7. Weekly Trend (tension chart)
  8. Outlook & Watch List
  9. Methodology & Disclaimer
"""
import io
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # GUI 없는 서버 환경
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak, KeepTogether, HRFlowable,
)
from reportlab.platypus.flowables import Flowable

logger = logging.getLogger(__name__)

# ── 폰트 등록 ────────────────────────────────────────────────────────────
_FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJKkr-Regular.otf",
    os.path.expanduser("~/.fonts/NanumGothic-Regular.ttf"),
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]
_FONT_BOLD_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJKkr-Bold.otf",
    os.path.expanduser("~/.fonts/NanumGothic-Bold.ttf"),
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]

_fonts_registered = False


def _register_fonts():
    """CJK 폰트 등록 (한 번만 실행)."""
    global _fonts_registered
    if _fonts_registered:
        return
    _fonts_registered = True

    # Regular
    for path in _FONT_PATHS:
        if os.path.exists(path):
            try:
                kwargs = {"subfontIndex": 1} if path.endswith(".ttc") else {}
                pdfmetrics.registerFont(TTFont("NotoSansKR", path, **kwargs))
                break
            except Exception as e:
                logger.warning("폰트 등록 실패 %s: %s", path, e)
    else:
        logger.warning("CJK 폰트 미발견, 기본 폰트 사용")
        return

    # Bold
    for path in _FONT_BOLD_PATHS:
        if os.path.exists(path):
            try:
                kwargs = {"subfontIndex": 1} if path.endswith(".ttc") else {}
                pdfmetrics.registerFont(TTFont("NotoSansKR-Bold", path, **kwargs))
                break
            except Exception as e:
                logger.warning("Bold 폰트 등록 실패 %s: %s", path, e)


# ── 색상 팔레트 (CrowdStrike/ACLED 스타일) ──────────────────────────────
COLORS = {
    "primary": HexColor("#0F172A"),       # Slate 900 - dark navy
    "secondary": HexColor("#1E3A5F"),     # Navy Blue
    "accent": HexColor("#3B82F6"),        # Blue 500
    "danger": HexColor("#DC2626"),        # Red 600 - Critical
    "warning": HexColor("#F59E0B"),       # Amber 500 - Elevated
    "success": HexColor("#10B981"),       # Emerald 500 - Stable
    "bg": HexColor("#FFFFFF"),            # White
    "bg_alt": HexColor("#F8FAFC"),        # Slate 50
    "text": HexColor("#0F172A"),          # Slate 900
    "text_muted": HexColor("#64748B"),    # Slate 500
}

# Severity 색상 매핑
_SEVERITY_COLORS = {
    "critical": HexColor("#DC2626"),   # Red
    "high": HexColor("#EA580C"),       # Orange
    "medium": HexColor("#F59E0B"),     # Amber
    "low": HexColor("#10B981"),        # Green
}

# 이전 BRAND dict 호환 (다른 모듈에서 import 하는 경우 대비)
BRAND = {
    "bg_dark": COLORS["primary"],
    "bg_card": COLORS["bg_alt"],
    "bg_header": COLORS["secondary"],
    "border": HexColor("#E2E8F0"),
    "text_primary": COLORS["text"],
    "text_secondary": COLORS["text_muted"],
    "accent_blue": COLORS["accent"],
    "accent_green": COLORS["success"],
    "accent_red": COLORS["danger"],
    "accent_yellow": COLORS["warning"],
}


def _severity_label(sev: int, lang: str = "ko") -> str:
    """심각도 숫자를 라벨로 변환."""
    if sev >= 80:
        return "Critical" if lang == "en" else "심각"
    elif sev >= 60:
        return "High" if lang == "en" else "높음"
    elif sev >= 40:
        return "Medium" if lang == "en" else "보통"
    else:
        return "Low" if lang == "en" else "낮음"


def _severity_color(sev: int) -> HexColor:
    """심각도 숫자에 따른 색상 반환."""
    if sev >= 80:
        return _SEVERITY_COLORS["critical"]
    elif sev >= 60:
        return _SEVERITY_COLORS["high"]
    elif sev >= 40:
        return _SEVERITY_COLORS["medium"]
    else:
        return _SEVERITY_COLORS["low"]


def _trend_arrow(delta) -> str:
    """delta 값에 따른 추세 화살표."""
    try:
        d = float(delta)
    except (TypeError, ValueError):
        return "-"
    if d > 2:
        return "^^"
    elif d > 0:
        return "^"
    elif d < -2:
        return "vv"
    elif d < 0:
        return "v"
    return "-"


def _setup_matplotlib(lang: str = "ko"):
    """matplotlib 다크 테마 + CJK 폰트 설정."""
    plt.style.use("dark_background")
    # CJK 폰트 탐색 (없으면 sans-serif 폴백)
    font_family = "sans-serif"
    if lang == "ko":
        from matplotlib.font_manager import fontManager
        # ~/.fonts 에 수동 설치된 폰트 추가 시도
        for fpath in [
            os.path.expanduser("~/.fonts/NanumGothic-Regular.ttf"),
            os.path.expanduser("~/.fonts/NanumGothic-Bold.ttf"),
        ]:
            if os.path.exists(fpath):
                try:
                    fontManager.addfont(fpath)
                except Exception:
                    pass
        for name in ["Noto Sans CJK KR", "NanumGothic", "Malgun Gothic"]:
            if any(f.name == name for f in fontManager.ttflist):
                font_family = name
                break
    plt.rcParams.update({
        "font.family": font_family,
        "axes.facecolor": "#0F172A",
        "figure.facecolor": "#0F172A",
        "axes.edgecolor": "#334155",
        "axes.labelcolor": "#94A3B8",
        "xtick.color": "#94A3B8",
        "ytick.color": "#94A3B8",
        "grid.color": "#1E293B",
    })


# ── 데이터 모델 ──────────────────────────────────────────────────────────

@dataclass
class WeeklyReportData:
    """PDF에 필요한 데이터 컨테이너."""
    week_start: datetime
    week_end: datetime
    total_events: int = 0
    new_clusters: int = 0
    crisis_countries: int = 0
    top_issues: list = field(default_factory=list)
    tension_series: list = field(default_factory=list)
    topic_distribution: dict = field(default_factory=dict)
    lang: str = "ko"
    # ── 신규 필드 (기본값 있어 기존 caller 호환) ──
    highlight_text: str = ""                                # BLUF summary
    country_risks: list = field(default_factory=list)       # [{cc, tension, delta, trend}]
    intel_summary: dict = field(default_factory=dict)       # {firms: N, ioda: N, gps: N, cross_hits: N}
    top_kscore: list = field(default_factory=list)           # [{title, kscore, cc}]
    outlook_items: list = field(default_factory=list)        # [{text, risk_level}]
    issue_number: int = 0                                    # Issue number
    wow_change: float = 0.0                                  # Week-over-week % change


# ── BLUF 생성 ────────────────────────────────────────────────────────────

def _generate_bluf(data: WeeklyReportData, lang: str) -> str:
    """핵심 요약(BLUF) 텍스트 생성."""
    if data.highlight_text:
        return data.highlight_text

    bullets = []
    for issue in (data.top_issues or [])[:3]:
        title = issue.get("title_ko", issue.get("title", "")) if lang == "ko" else issue.get("title", "")
        bullets.append(f"- {title} (Severity {issue.get('severity', 0)})")
    count_text = (
        f"이번 주 {data.total_events}건의 이벤트가 수집되었으며, "
        f"{data.new_clusters}개의 신규 이슈 클러스터가 생성되었습니다."
        if lang == "ko"
        else f"This week {data.total_events} events were collected, "
             f"with {data.new_clusters} new issue clusters identified."
    )
    return "\n".join(bullets) + "\n\n" + count_text


# ── 차트 생성 ────────────────────────────────────────────────────────────

def _generate_tension_chart(data: WeeklyReportData) -> io.BytesIO:
    """긴장도 추이 라인 차트 생성 (다크 네이비 테마)."""
    _setup_matplotlib(data.lang)
    fig, ax = plt.subplots(figsize=(7, 3.2), dpi=150)

    countries: dict[str, dict] = {}
    for row in data.tension_series:
        cc = row["country_code"]
        if cc not in countries:
            countries[cc] = {"times": [], "scores": []}
        countries[cc]["times"].append(row["time"])
        countries[cc]["scores"].append(row["raw_score"])

    color_cycle = ["#3B82F6", "#DC2626", "#10B981", "#F59E0B", "#8B5CF6"]
    for i, (cc, series) in enumerate(list(countries.items())[:5]):
        ax.plot(
            series["times"], series["scores"],
            label=cc, color=color_cycle[i % len(color_cycle)],
            linewidth=2, marker="o", markersize=4,
        )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    title_text = "국가별 긴장도 추이" if data.lang == "ko" else "Tension Score by Country"
    ax.set_title(title_text, color="#E2E8F0", fontsize=12, pad=10)
    ax.set_ylabel("긴장도 점수" if data.lang == "ko" else "Tension Score",
                   color="#94A3B8", fontsize=9)
    ax.legend(loc="upper left", fontsize=8, framealpha=0.3)
    ax.grid(True, alpha=0.2)

    # 영역 채우기 (subtle)
    for i, (cc, series) in enumerate(list(countries.items())[:5]):
        ax.fill_between(
            series["times"], series["scores"], alpha=0.08,
            color=color_cycle[i % len(color_cycle)],
        )

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _generate_topic_chart(data: WeeklyReportData) -> io.BytesIO:
    """토픽별 이슈 분포 도넛 차트."""
    _setup_matplotlib(data.lang)
    fig, ax = plt.subplots(figsize=(4.5, 4.5), dpi=150)

    labels = list(data.topic_distribution.keys())[:8]
    sizes = [data.topic_distribution[lb] for lb in labels]
    pie_colors = ["#3B82F6", "#DC2626", "#10B981", "#F59E0B",
                  "#8B5CF6", "#EC4899", "#06B6D4", "#84CC16"]

    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, autopct="%1.0f%%",
        colors=pie_colors[:len(labels)],
        textprops={"fontsize": 8, "color": "#E2E8F0"},
        pctdistance=0.8, wedgeprops={"width": 0.4, "edgecolor": "#0F172A"},
    )
    ax.set_title(
        "토픽별 분포" if data.lang == "ko" else "Distribution by Topic",
        color="#E2E8F0", fontsize=11, pad=10,
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ── 페이지 헤더/푸터 ────────────────────────────────────────────────────

class _PageNumCanvas:
    """페이지 번호 + 헤더/푸터를 각 페이지에 그리는 콜백."""

    def __init__(self, data: WeeklyReportData, font_name: str, font_bold: str):
        self.data = data
        self.font_name = font_name
        self.font_bold = font_bold
        self._pages = []

    def on_page(self, canvas, doc):
        """각 페이지마다 호출."""
        canvas.saveState()
        page_num = doc.page
        width, height = A4

        # ── 상단 헤더 바 ──
        canvas.setFillColor(COLORS["primary"])
        canvas.rect(0, height - 12 * mm, width, 12 * mm, fill=True, stroke=False)

        # 헤더 텍스트 (좌측)
        canvas.setFillColor(HexColor("#FFFFFF"))
        canvas.setFont(self.font_bold, 8)
        canvas.drawString(20 * mm, height - 8 * mm, "WeWantPeace")

        # 헤더 텍스트 (중앙 - 날짜 범위)
        lang = self.data.lang
        if lang == "ko":
            date_str = (
                f"{self.data.week_start.strftime('%Y.%m.%d')} ~ "
                f"{self.data.week_end.strftime('%Y.%m.%d')}"
            )
        else:
            date_str = (
                f"{self.data.week_start.strftime('%b %d, %Y')} - "
                f"{self.data.week_end.strftime('%b %d, %Y')}"
            )
        canvas.setFont(self.font_name, 7)
        canvas.setFillColor(HexColor("#94A3B8"))
        canvas.drawCentredString(width / 2, height - 8 * mm, date_str)

        # 헤더 텍스트 (우측 - 페이지)
        canvas.setFont(self.font_name, 7)
        canvas.setFillColor(HexColor("#94A3B8"))
        canvas.drawRightString(
            width - 20 * mm, height - 8 * mm,
            f"p. {page_num}"
        )

        # ── 하단 푸터 바 ──
        canvas.setFillColor(COLORS["primary"])
        canvas.rect(0, 0, width, 8 * mm, fill=True, stroke=False)

        canvas.setFillColor(HexColor("#64748B"))
        canvas.setFont(self.font_name, 6)
        footer_text = "https://www.wewantpeace.live"
        canvas.drawString(20 * mm, 3 * mm, footer_text)

        label = "CONFIDENTIAL" if lang == "en" else "CONFIDENTIAL"
        canvas.setFillColor(HexColor("#475569"))
        canvas.drawRightString(width - 20 * mm, 3 * mm, label)

        canvas.restoreState()

    def on_first_page(self, canvas, doc):
        """첫 페이지(표지)에는 헤더/푸터 표시하지 않음."""
        pass


# ── 커스텀 Flowable: 수평 줄 ──────────────────────────────────────────

class SectionDivider(Flowable):
    """얇은 구분선."""
    def __init__(self, width, color=COLORS["accent"], thickness=1):
        super().__init__()
        self.width = width
        self.color = color
        self.thickness = thickness
        self.height = thickness + 2 * mm

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 1 * mm, self.width, 1 * mm)


# ── 메인 PDF 빌드 ────────────────────────────────────────────────────────

def build_pdf(data: WeeklyReportData) -> io.BytesIO:
    """주간 리포트 PDF 생성 (8-10 pages, CrowdStrike/ACLED 스타일). BytesIO 반환."""
    _register_fonts()

    # 폰트 이름 결정 (등록 실패 시 Helvetica 폴백)
    try:
        pdfmetrics.getFont("NotoSansKR")
        font_name = "NotoSansKR"
        font_bold = "NotoSansKR-Bold"
    except KeyError:
        font_name = "Helvetica"
        font_bold = "Helvetica-Bold"

    lang = data.lang
    page_w, page_h = A4
    content_w = page_w - 40 * mm  # 좌우 마진 20mm

    buffer = io.BytesIO()
    page_handler = _PageNumCanvas(data, font_name, font_bold)

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=18 * mm, bottomMargin=14 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
        title="WeWantPeace Weekly Conflict Monitor",
        author="WeWantPeace",
    )

    styles = getSampleStyleSheet()

    # ── 스타일 정의 ───────────────────────────────────────────────
    s_cover_title = ParagraphStyle(
        "CoverTitle", parent=styles["Title"],
        fontName=font_bold, fontSize=32,
        textColor=HexColor("#FFFFFF"),
        alignment=TA_CENTER, spaceAfter=4 * mm,
    )
    s_cover_sub = ParagraphStyle(
        "CoverSub", parent=styles["Normal"],
        fontName=font_name, fontSize=16,
        textColor=HexColor("#94A3B8"),
        alignment=TA_CENTER, spaceAfter=6 * mm,
    )
    s_cover_date = ParagraphStyle(
        "CoverDate", parent=styles["Normal"],
        fontName=font_name, fontSize=12,
        textColor=HexColor("#64748B"),
        alignment=TA_CENTER,
    )
    s_section = ParagraphStyle(
        "SectionTitle", parent=styles["Heading1"],
        fontName=font_bold, fontSize=16,
        textColor=COLORS["primary"],
        spaceBefore=6 * mm, spaceAfter=3 * mm,
    )
    s_h2 = ParagraphStyle(
        "WH2", parent=styles["Heading2"],
        fontName=font_bold, fontSize=13,
        textColor=COLORS["secondary"],
        spaceBefore=5 * mm, spaceAfter=3 * mm,
    )
    s_body = ParagraphStyle(
        "WBody", parent=styles["Normal"],
        fontName=font_name, fontSize=10,
        textColor=COLORS["text"],
        leading=15, spaceAfter=2 * mm,
    )
    s_body_bold = ParagraphStyle(
        "WBodyBold", parent=s_body,
        fontName=font_bold,
    )
    s_bullet = ParagraphStyle(
        "WBullet", parent=s_body,
        leftIndent=8 * mm, bulletIndent=3 * mm,
        spaceBefore=1 * mm, spaceAfter=1 * mm,
    )
    s_small = ParagraphStyle(
        "WSmall", parent=styles["Normal"],
        fontName=font_name, fontSize=8,
        textColor=COLORS["text_muted"],
        leading=11,
    )
    s_small_center = ParagraphStyle(
        "WSmallCenter", parent=s_small,
        alignment=TA_CENTER,
    )
    s_kpi_label = ParagraphStyle(
        "KPILabel", parent=styles["Normal"],
        fontName=font_name, fontSize=8,
        textColor=HexColor("#94A3B8"),
        alignment=TA_CENTER,
    )
    s_kpi_value = ParagraphStyle(
        "KPIValue", parent=styles["Normal"],
        fontName=font_bold, fontSize=22,
        textColor=HexColor("#FFFFFF"),
        alignment=TA_CENTER,
    )
    s_table_header = ParagraphStyle(
        "TblHeader", parent=styles["Normal"],
        fontName=font_bold, fontSize=9,
        textColor=HexColor("#FFFFFF"),
    )
    s_table_cell = ParagraphStyle(
        "TblCell", parent=styles["Normal"],
        fontName=font_name, fontSize=9,
        textColor=COLORS["text"],
        leading=12,
    )
    s_table_cell_bold = ParagraphStyle(
        "TblCellBold", parent=s_table_cell,
        fontName=font_bold,
    )

    story = []

    # ═══════════════════════════════════════════════════════════════
    # PAGE 1: COVER
    # ═══════════════════════════════════════════════════════════════

    # 표지 배경 (네이비 블록)
    cover_bg_data = [[""],]
    cover_bg = Table(cover_bg_data, colWidths=[content_w], rowHeights=[220 * mm])
    cover_bg.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["primary"]),
        ("BOX", (0, 0), (-1, -1), 0, COLORS["primary"]),
    ]))

    # 표지 콘텐츠를 테이블 안에 구성
    cover_content = []
    cover_content.append(Spacer(1, 50 * mm))

    # 악센트 라인
    cover_content.append(
        HRFlowable(
            width="30%", thickness=3, color=COLORS["accent"],
            spaceBefore=0, spaceAfter=8 * mm,
        )
    )

    cover_content.append(Paragraph("WEEKLY CONFLICT MONITOR", s_cover_title))
    cover_content.append(Spacer(1, 4 * mm))

    subtitle = (
        "주간 분쟁 모니터링 리포트" if lang == "ko"
        else "Conflict Intelligence Report"
    )
    cover_content.append(Paragraph(subtitle, s_cover_sub))
    cover_content.append(Spacer(1, 8 * mm))

    # 날짜 범위
    if lang == "ko":
        date_range = (
            f"{data.week_start.strftime('%Y년 %m월 %d일')} ~ "
            f"{data.week_end.strftime('%Y년 %m월 %d일')}"
        )
    else:
        date_range = (
            f"{data.week_start.strftime('%B %d, %Y')} - "
            f"{data.week_end.strftime('%B %d, %Y')}"
        )
    cover_content.append(Paragraph(date_range, s_cover_date))
    cover_content.append(Spacer(1, 4 * mm))

    # Week N + Issue #
    week_num = data.week_start.isocalendar()[1]
    issue_num = data.issue_number if data.issue_number else week_num
    week_label = f"Week {week_num} | Issue #{issue_num:02d}"
    cover_content.append(Paragraph(week_label, s_cover_date))

    cover_content.append(Spacer(1, 30 * mm))

    # 악센트 라인 (하단)
    cover_content.append(
        HRFlowable(
            width="30%", thickness=3, color=COLORS["accent"],
            spaceBefore=0, spaceAfter=6 * mm,
        )
    )

    # 웹사이트
    s_cover_url = ParagraphStyle(
        "CoverURL", parent=s_cover_date,
        fontSize=9, textColor=COLORS["accent"],
    )
    cover_content.append(Paragraph("www.wewantpeace.live", s_cover_url))

    # 표지 전체를 네이비 배경 테이블로 감싸기
    cover_inner = Table(
        [[cover_content]],
        colWidths=[content_w],
    )
    cover_inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["primary"]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # 표지는 네이비 배경 테이블로 추가
    story.append(cover_inner)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 2: EXECUTIVE SUMMARY (BLUF)
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "EXECUTIVE SUMMARY" if lang == "en" else "핵심 요약 (BLUF)",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 3 * mm))

    # BLUF 박스
    bluf_text = _generate_bluf(data, lang)
    bluf_lines = bluf_text.split("\n")

    bluf_paras = []
    for line in bluf_lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("- ") or line.startswith("* "):
            bluf_paras.append(Paragraph(line, s_bullet))
        else:
            bluf_paras.append(Paragraph(line, s_body))

    # BLUF를 박스에 넣기
    bluf_table = Table(
        [[bluf_paras]],
        colWidths=[content_w - 6 * mm],
    )
    bluf_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["bg_alt"]),
        ("BOX", (0, 0), (-1, -1), 1, COLORS["accent"]),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(bluf_table)
    story.append(Spacer(1, 6 * mm))

    # 추가 컨텍스트
    ctx_label = "주요 발견사항" if lang == "ko" else "Key Findings"
    story.append(Paragraph(ctx_label, s_h2))

    findings = []
    if data.total_events:
        findings.append(
            f"총 {data.total_events:,}건의 이벤트 수집, {data.new_clusters}개 신규 클러스터 식별"
            if lang == "ko"
            else f"Total {data.total_events:,} events collected, {data.new_clusters} new clusters identified"
        )
    if data.crisis_countries:
        findings.append(
            f"{data.crisis_countries}개 국가에서 고위험 분쟁 상황 감지"
            if lang == "ko"
            else f"High-risk conflict situations detected in {data.crisis_countries} countries"
        )
    if data.wow_change:
        direction = "증가" if data.wow_change > 0 else "감소"
        direction_en = "increase" if data.wow_change > 0 else "decrease"
        findings.append(
            f"전주 대비 이벤트 {abs(data.wow_change):.1f}% {direction}"
            if lang == "ko"
            else f"{abs(data.wow_change):.1f}% {direction_en} week-over-week"
        )
    if not findings:
        findings.append(
            "데이터 수집 정상 진행 중" if lang == "ko" else "Data collection proceeding normally"
        )

    for f in findings:
        story.append(Paragraph(f"- {f}", s_bullet))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 3: KEY METRICS DASHBOARD
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "KEY METRICS" if lang == "en" else "주요 지표",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 4 * mm))

    # 4 KPI 카드
    wow_sign = "+" if data.wow_change >= 0 else ""
    wow_str = f"{wow_sign}{data.wow_change:.1f}%"

    kpi_labels = [
        ("총 이벤트" if lang == "ko" else "Total Events", str(f"{data.total_events:,}")),
        ("신규 클러스터" if lang == "ko" else "New Clusters", str(data.new_clusters)),
        ("위기 국가" if lang == "ko" else "Active Countries", str(data.crisis_countries)),
        ("전주 대비" if lang == "ko" else "WoW Change", wow_str),
    ]

    kpi_cells = []
    for label, value in kpi_labels:
        cell_content = [
            Paragraph(value, s_kpi_value),
            Spacer(1, 2 * mm),
            Paragraph(label, s_kpi_label),
        ]
        kpi_cells.append(cell_content)

    card_w = (content_w - 9 * mm) / 4  # 4카드 + 간격
    kpi_table = Table(
        [kpi_cells],
        colWidths=[card_w, card_w, card_w, card_w],
        rowHeights=[32 * mm],
    )
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["primary"]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (0, 0), 1, COLORS["accent"]),
        ("BOX", (1, 0), (1, 0), 1, COLORS["success"]),
        ("BOX", (2, 0), (2, 0), 1, COLORS["danger"]),
        ("BOX", (3, 0), (3, 0), 1, COLORS["warning"]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8 * mm))

    # 토픽 분포 차트 (있으면)
    if data.topic_distribution:
        story.append(Paragraph(
            "토픽별 이슈 분포" if lang == "ko" else "Issue Distribution by Topic", s_h2
        ))
        pie_buf = _generate_topic_chart(data)
        story.append(Image(pie_buf, width=90 * mm, height=90 * mm))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 4: TOP 5 ISSUES
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "TOP 5 ISSUES" if lang == "en" else "TOP 5 주요 이슈",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 3 * mm))

    if data.top_issues:
        header = [
            Paragraph("#", s_table_header),
            Paragraph("국가" if lang == "ko" else "Country", s_table_header),
            Paragraph("이슈" if lang == "ko" else "Issue", s_table_header),
            Paragraph("심각도" if lang == "ko" else "Severity", s_table_header),
            Paragraph("KScore", s_table_header),
        ]
        rows = [header]
        for i, issue in enumerate(data.top_issues[:5], 1):
            title = issue.get("title_ko") or issue.get("title", "") if lang == "ko" else issue.get("title", "")
            if len(title) > 50:
                title = title[:50] + "..."

            sev = issue.get("severity", 0)
            sev_label = _severity_label(sev, lang)
            sev_color = _severity_color(sev)

            kscore = issue.get("kscore", "-")
            if isinstance(kscore, (int, float)):
                kscore_str = f"{kscore:.1f}" if isinstance(kscore, float) else str(kscore)
            else:
                kscore_str = str(kscore)

            s_sev_badge = ParagraphStyle(
                f"SevBadge{i}", parent=s_table_cell,
                fontName=font_bold, fontSize=8,
                textColor=HexColor("#FFFFFF"),
            )

            rows.append([
                Paragraph(str(i), s_table_cell),
                Paragraph(issue.get("country_code", "-"), s_table_cell_bold),
                Paragraph(title, s_table_cell),
                Paragraph(f"<font color='#{sev_color.hexval()[2:]}'>{sev_label} ({sev})</font>", s_table_cell),
                Paragraph(kscore_str, s_table_cell),
            ])

        col_widths = [10 * mm, 18 * mm, 85 * mm, 32 * mm, 20 * mm]
        t = Table(rows, colWidths=col_widths)
        table_style_cmds = [
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), COLORS["secondary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("BACKGROUND", (0, 1), (-1, -1), COLORS["bg"]),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (4, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
            ("LINEBELOW", (0, 0), (-1, 0), 1.5, COLORS["accent"]),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        # 교대 행 배경색
        for row_idx in range(1, len(rows)):
            if row_idx % 2 == 0:
                table_style_cmds.append(
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), COLORS["bg_alt"])
                )
        t.setStyle(TableStyle(table_style_cmds))
        story.append(t)
    else:
        story.append(Paragraph(
            "이번 주 보고할 이슈가 없습니다." if lang == "ko" else "No issues to report this week.",
            s_body,
        ))

    # Top KScore 이슈 (있으면)
    if data.top_kscore:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(
            "KScore 상위 이슈" if lang == "ko" else "Top KScore Issues", s_h2
        ))
        ks_header = [
            Paragraph("이슈" if lang == "ko" else "Issue", s_table_header),
            Paragraph("KScore", s_table_header),
            Paragraph("국가" if lang == "ko" else "Country", s_table_header),
        ]
        ks_rows = [ks_header]
        for item in data.top_kscore[:5]:
            ks_rows.append([
                Paragraph(str(item.get("title", "")), s_table_cell),
                Paragraph(str(item.get("kscore", "-")), s_table_cell),
                Paragraph(str(item.get("cc", "-")), s_table_cell),
            ])
        ks_t = Table(ks_rows, colWidths=[100 * mm, 25 * mm, 25 * mm])
        ks_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), COLORS["secondary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("BACKGROUND", (0, 1), (-1, -1), COLORS["bg"]),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#E2E8F0")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(ks_t)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 5: COUNTRY RISK TABLE
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "COUNTRY RISK ASSESSMENT" if lang == "en" else "국가별 위험도 평가",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 3 * mm))

    # country_risks 데이터가 있으면 사용, 없으면 tension_series에서 추출
    country_risk_data = data.country_risks
    if not country_risk_data and data.tension_series:
        # tension_series에서 국가별 최신 값 추출
        _latest: dict[str, dict] = {}
        for row in data.tension_series:
            cc = row["country_code"]
            if cc not in _latest or row["time"] > _latest[cc]["time"]:
                _latest[cc] = row
        country_risk_data = [
            {"cc": cc, "tension": r.get("raw_score", 0), "delta": 0, "trend": "-"}
            for cc, r in sorted(_latest.items(), key=lambda x: x[1].get("raw_score", 0), reverse=True)
        ]

    if country_risk_data:
        cr_header = [
            Paragraph("#", s_table_header),
            Paragraph("국가" if lang == "ko" else "Country", s_table_header),
            Paragraph("긴장도" if lang == "ko" else "Tension", s_table_header),
            Paragraph("변화" if lang == "ko" else "Delta", s_table_header),
            Paragraph("추세" if lang == "ko" else "Trend", s_table_header),
            Paragraph("등급" if lang == "ko" else "Level", s_table_header),
        ]
        cr_rows = [cr_header]
        for i, cr in enumerate(country_risk_data[:10], 1):
            tension = cr.get("tension", 0)
            delta = cr.get("delta", 0)
            trend = cr.get("trend", _trend_arrow(delta))
            sev_color = _severity_color(int(tension)) if tension else COLORS["text_muted"]
            sev_text = _severity_label(int(tension), lang) if tension else "-"

            delta_str = f"{delta:+.1f}" if isinstance(delta, (int, float)) else str(delta)

            cr_rows.append([
                Paragraph(str(i), s_table_cell),
                Paragraph(str(cr.get("cc", "-")), s_table_cell_bold),
                Paragraph(f"{tension:.0f}" if isinstance(tension, (int, float)) else str(tension), s_table_cell),
                Paragraph(delta_str, s_table_cell),
                Paragraph(str(trend), s_table_cell_bold),
                Paragraph(f"<font color='#{sev_color.hexval()[2:]}'>{sev_text}</font>", s_table_cell),
            ])

        cr_t = Table(cr_rows, colWidths=[10 * mm, 25 * mm, 28 * mm, 25 * mm, 20 * mm, 30 * mm])
        cr_style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), COLORS["secondary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
            ("BACKGROUND", (0, 1), (-1, -1), COLORS["bg"]),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
            ("LINEBELOW", (0, 0), (-1, 0), 1.5, COLORS["accent"]),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ]
        for row_idx in range(1, len(cr_rows)):
            if row_idx % 2 == 0:
                cr_style_cmds.append(
                    ("BACKGROUND", (0, row_idx), (-1, row_idx), COLORS["bg_alt"])
                )
        cr_t.setStyle(TableStyle(cr_style_cmds))
        story.append(cr_t)
    else:
        story.append(Paragraph(
            "국가별 위험도 데이터가 없습니다." if lang == "ko" else "No country risk data available.",
            s_body,
        ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 6: INTELLIGENCE SUMMARY
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "INTELLIGENCE SUMMARY" if lang == "en" else "인텔리전스 요약",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 3 * mm))

    intel = data.intel_summary or {}
    firms_count = intel.get("firms", 0)
    ioda_count = intel.get("ioda", 0)
    gps_count = intel.get("gps", 0)
    cross_hits = intel.get("cross_hits", 0)

    # 인텔 KPI 카드
    intel_labels = [
        ("FIRMS", str(firms_count), "화재/열점 감지" if lang == "ko" else "Fire/Hotspot Detections"),
        ("IODA", str(ioda_count), "인터넷 장애 감지" if lang == "ko" else "Internet Outage Detections"),
        ("GPS", str(gps_count), "GPS 교란 감지" if lang == "ko" else "GPS Jamming Detections"),
        ("Cross-Verify", str(cross_hits), "교차 검증 히트" if lang == "ko" else "Cross-Verification Hits"),
    ]

    intel_cells = []
    for source, count, desc in intel_labels:
        cell_content = [
            Paragraph(source, ParagraphStyle(
                f"IntelSrc_{source}", parent=s_kpi_label,
                fontName=font_bold, fontSize=9,
                textColor=COLORS["accent"],
            )),
            Paragraph(count, ParagraphStyle(
                f"IntelVal_{source}", parent=s_kpi_value,
                fontSize=18,
            )),
            Spacer(1, 1 * mm),
            Paragraph(desc, s_kpi_label),
        ]
        intel_cells.append(cell_content)

    intel_card_w = (content_w - 9 * mm) / 4
    intel_table = Table(
        [intel_cells],
        colWidths=[intel_card_w] * 4,
        rowHeights=[36 * mm],
    )
    intel_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["primary"]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#334155")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#334155")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(intel_table)
    story.append(Spacer(1, 8 * mm))

    # 주요 감지 사항
    story.append(Paragraph(
        "주요 감지 사항" if lang == "ko" else "Notable Detections", s_h2
    ))

    top_detections = intel.get("top_detections", [])
    if top_detections:
        for det in top_detections[:3]:
            story.append(Paragraph(f"- {det}", s_bullet))
    else:
        # 기본 텍스트
        if firms_count or ioda_count or gps_count:
            summary_text = (
                f"FIRMS {firms_count}건, IODA {ioda_count}건, GPS {gps_count}건 감지. "
                f"교차 검증 {cross_hits}건 확인."
                if lang == "ko"
                else f"FIRMS {firms_count}, IODA {ioda_count}, GPS {gps_count} detections. "
                     f"{cross_hits} cross-verification hits confirmed."
            )
            story.append(Paragraph(summary_text, s_body))
        else:
            story.append(Paragraph(
                "인텔리전스 데이터가 수집 중입니다." if lang == "ko"
                else "Intelligence data collection in progress.",
                s_body,
            ))

    # 데이터 소스 개요
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "데이터 소스 현황" if lang == "ko" else "Data Source Status", s_h2
    ))
    source_items = [
        ("FIRMS (NASA)", "화재/열점 감지 위성 데이터" if lang == "ko" else "Satellite fire/thermal anomaly data"),
        ("IODA (CAIDA)", "인터넷 장애 모니터링" if lang == "ko" else "Internet outage monitoring"),
        ("GPS Jamming", "GPS 교란 모니터링" if lang == "ko" else "GPS interference monitoring"),
        ("GDELT/ACLED", "분쟁 이벤트 데이터" if lang == "ko" else "Conflict event data"),
    ]
    for src, desc in source_items:
        story.append(Paragraph(f"<b>{src}</b>: {desc}", s_body))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 7: WEEKLY TREND (TENSION CHART)
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "WEEKLY TREND" if lang == "en" else "주간 긴장도 추이",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 3 * mm))

    if data.tension_series:
        chart_buf = _generate_tension_chart(data)
        story.append(Image(chart_buf, width=165 * mm, height=75 * mm))
        story.append(Spacer(1, 4 * mm))

        # 차트 해석 텍스트
        story.append(Paragraph(
            "위 차트는 상위 5개 국가의 주간 긴장도 추이를 나타냅니다. "
            "점수가 높을수록 분쟁 위험도가 높음을 의미합니다."
            if lang == "ko"
            else "The chart above shows weekly tension trends for the top 5 countries. "
                 "Higher scores indicate greater conflict risk.",
            s_small,
        ))
    else:
        story.append(Paragraph(
            "이번 주 긴장도 데이터가 없습니다." if lang == "ko"
            else "No tension data available for this week.",
            s_body,
        ))

    # 분류 기준 설명 (차트 아래)
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        "긴장도 등급 기준" if lang == "ko" else "Tension Level Criteria", s_h2
    ))

    level_data = [
        [
            Paragraph("등급" if lang == "ko" else "Level", s_table_header),
            Paragraph("점수" if lang == "ko" else "Score", s_table_header),
            Paragraph("설명" if lang == "ko" else "Description", s_table_header),
        ],
        [
            Paragraph(f"<font color='#DC2626'>{'심각' if lang == 'ko' else 'Critical'}</font>", s_table_cell_bold),
            Paragraph("80-100", s_table_cell),
            Paragraph(
                "즉각적 위기 상황, 대규모 충돌 진행 중" if lang == "ko"
                else "Immediate crisis, large-scale conflict underway",
                s_table_cell,
            ),
        ],
        [
            Paragraph(f"<font color='#EA580C'>{'높음' if lang == 'ko' else 'High'}</font>", s_table_cell_bold),
            Paragraph("60-79", s_table_cell),
            Paragraph(
                "긴장 고조, 무력 충돌 가능성 높음" if lang == "ko"
                else "Elevated tensions, high probability of armed conflict",
                s_table_cell,
            ),
        ],
        [
            Paragraph(f"<font color='#F59E0B'>{'보통' if lang == 'ko' else 'Medium'}</font>", s_table_cell_bold),
            Paragraph("40-59", s_table_cell),
            Paragraph(
                "긴장 존재, 상황 모니터링 필요" if lang == "ko"
                else "Tensions present, situation requires monitoring",
                s_table_cell,
            ),
        ],
        [
            Paragraph(f"<font color='#10B981'>{'낮음' if lang == 'ko' else 'Low'}</font>", s_table_cell_bold),
            Paragraph("0-39", s_table_cell),
            Paragraph(
                "안정적, 일상적 수준의 사건" if lang == "ko"
                else "Stable, routine-level incidents",
                s_table_cell,
            ),
        ],
    ]
    level_t = Table(level_data, colWidths=[30 * mm, 25 * mm, 100 * mm])
    level_style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), COLORS["secondary"]),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("BACKGROUND", (0, 1), (-1, -1), COLORS["bg"]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    for row_idx in range(1, len(level_data)):
        if row_idx % 2 == 0:
            level_style_cmds.append(
                ("BACKGROUND", (0, row_idx), (-1, row_idx), COLORS["bg_alt"])
            )
    level_t.setStyle(TableStyle(level_style_cmds))
    story.append(level_t)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 8: OUTLOOK & WATCH LIST
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "OUTLOOK & WATCH LIST" if lang == "en" else "전망 및 주시 항목",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 3 * mm))

    outlook_items = data.outlook_items
    if not outlook_items:
        # 데이터가 없을 때 기본 outlook 생성
        outlook_items = []
        if data.top_issues:
            for issue in data.top_issues[:3]:
                title = issue.get("title_ko") or issue.get("title", "") if lang == "ko" else issue.get("title", "")
                sev = issue.get("severity", 0)
                risk = "critical" if sev >= 80 else ("high" if sev >= 60 else "medium")
                text = (
                    f"{title} - 향후 동향 주시 필요" if lang == "ko"
                    else f"{title} - Requires continued monitoring"
                )
                outlook_items.append({"text": text, "risk_level": risk})

    if outlook_items:
        story.append(Paragraph(
            "다음 주 주시해야 할 주요 항목입니다." if lang == "ko"
            else "Key items to watch in the coming week.",
            s_body,
        ))
        story.append(Spacer(1, 4 * mm))

        for i, item in enumerate(outlook_items[:5], 1):
            risk = item.get("risk_level", "medium")
            text = item.get("text", "")

            # 리스크 레벨별 색상
            risk_colors = {
                "critical": COLORS["danger"],
                "high": HexColor("#EA580C"),
                "medium": COLORS["warning"],
                "low": COLORS["success"],
            }
            rc = risk_colors.get(risk, COLORS["text_muted"])
            risk_label = risk.upper()

            # Outlook 아이템을 테이블 카드로 표시
            outlook_row = Table(
                [[
                    Paragraph(f"<font color='#{rc.hexval()[2:]}'><b>{risk_label}</b></font>", s_table_cell),
                    Paragraph(text, s_table_cell),
                ]],
                colWidths=[25 * mm, content_w - 30 * mm],
                rowHeights=[None],
            )
            outlook_row.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), COLORS["bg_alt"]),
                ("BACKGROUND", (1, 0), (1, 0), COLORS["bg"]),
                ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
                ("LINEBELOW", (0, 0), (-1, -1), 0, HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(outlook_row)
            story.append(Spacer(1, 2 * mm))
    else:
        story.append(Paragraph(
            "현재 특별히 주시할 항목이 없습니다." if lang == "ko"
            else "No specific items to watch at this time.",
            s_body,
        ))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════
    # PAGE 9: METHODOLOGY & DISCLAIMER
    # ═══════════════════════════════════════════════════════════════

    story.append(Paragraph(
        "METHODOLOGY & DISCLAIMER" if lang == "en" else "분석 방법론 및 면책 조항",
        s_section,
    ))
    story.append(SectionDivider(content_w))
    story.append(Spacer(1, 4 * mm))

    # 데이터 소스
    story.append(Paragraph(
        "데이터 소스" if lang == "ko" else "Data Sources", s_h2
    ))
    if lang == "ko":
        sources_text = (
            "본 리포트는 다음 공개 데이터 소스를 기반으로 AI가 자동 분석한 결과입니다:"
        )
    else:
        sources_text = (
            "This report is based on AI-automated analysis of the following public data sources:"
        )
    story.append(Paragraph(sources_text, s_body))
    story.append(Spacer(1, 2 * mm))

    source_list = [
        ("GDELT Project", "글로벌 이벤트/분쟁 뉴스 데이터" if lang == "ko" else "Global event/conflict news data"),
        ("ACLED", "무력 분쟁 위치 및 이벤트 데이터" if lang == "ko" else "Armed Conflict Location & Event Data"),
        ("NASA FIRMS", "위성 기반 화재/열점 감지" if lang == "ko" else "Satellite-based fire/thermal anomaly detection"),
        ("CAIDA IODA", "인터넷 장애/차단 모니터링" if lang == "ko" else "Internet outage/disruption monitoring"),
        ("GPSJam", "GPS 교란/재밍 모니터링" if lang == "ko" else "GPS jamming/interference monitoring"),
    ]
    for src, desc in source_list:
        story.append(Paragraph(f"- <b>{src}</b>: {desc}", s_bullet))

    story.append(Spacer(1, 6 * mm))

    # 분류 기준
    story.append(Paragraph(
        "분류 기준" if lang == "ko" else "Classification Criteria", s_h2
    ))
    if lang == "ko":
        criteria = [
            "심각도(Severity): AI 기반 0-100 점수. 이벤트 빈도, 사상자 추정, 미디어 관심도 반영",
            "KScore: 이슈 클러스터의 핵심 지표. 이벤트 수, 국가 수, 최근성 등 복합 평가",
            "긴장도(Tension Index): 국가별 종합 분쟁 위험 지수. 다중 소스 교차 검증",
        ]
    else:
        criteria = [
            "Severity: AI-based 0-100 score reflecting event frequency, casualty estimates, and media attention",
            "KScore: Key metric for issue clusters combining event count, country count, and recency",
            "Tension Index: Composite conflict risk index per country with multi-source cross-verification",
        ]
    for c in criteria:
        story.append(Paragraph(f"- {c}", s_bullet))

    story.append(Spacer(1, 8 * mm))

    # 면책 조항
    story.append(Paragraph(
        "면책 조항" if lang == "ko" else "Disclaimer", s_h2
    ))

    disclaimer_box_content = []
    if lang == "ko":
        disclaimers = [
            "본 리포트는 공개 데이터를 기반으로 AI가 자동 생성한 분석 결과이며, "
            "투자 자문, 군사 정보, 또는 정부 공식 입장을 대변하지 않습니다.",
            "모든 데이터는 발행 시점 기준이며, 실시간 상황과 차이가 있을 수 있습니다.",
            "WeWantPeace는 본 리포트의 정확성, 완전성, 적시성을 보장하지 않으며, "
            "이를 근거로 한 의사결정에 대해 책임을 지지 않습니다.",
            "본 리포트의 무단 복제 및 상업적 이용을 금합니다.",
        ]
    else:
        disclaimers = [
            "This report is AI-generated analysis based on publicly available data and does not "
            "constitute investment advice, military intelligence, or official government positions.",
            "All data is current as of the publication date and may differ from real-time conditions.",
            "WeWantPeace does not guarantee the accuracy, completeness, or timeliness of this report "
            "and assumes no liability for decisions made based on its content.",
            "Unauthorized reproduction or commercial use of this report is prohibited.",
        ]

    for d in disclaimers:
        disclaimer_box_content.append(Paragraph(f"- {d}", ParagraphStyle(
            "DisclaimerItem", parent=s_small,
            leftIndent=4 * mm, spaceBefore=1 * mm, spaceAfter=1 * mm,
            leading=11,
        )))

    disc_table = Table(
        [[disclaimer_box_content]],
        colWidths=[content_w - 6 * mm],
    )
    disc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COLORS["bg_alt"]),
        ("BOX", (0, 0), (-1, -1), 0.5, HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(disc_table)

    story.append(Spacer(1, 10 * mm))

    # 최종 푸터
    story.append(
        HRFlowable(width="100%", thickness=0.5, color=HexColor("#E2E8F0"),
                    spaceBefore=2 * mm, spaceAfter=4 * mm)
    )
    story.append(Paragraph(
        "WeWantPeace Weekly Conflict Monitor | www.wewantpeace.live",
        s_small_center,
    ))
    copyright_year = data.week_end.strftime("%Y")
    story.append(Paragraph(
        f"Copyright {copyright_year} WeWantPeace. All rights reserved.",
        s_small_center,
    ))

    # ── 빌드 ──────────────────────────────────────────────────────
    doc.build(
        story,
        onFirstPage=page_handler.on_first_page,
        onLaterPages=page_handler.on_page,
    )
    buffer.seek(0)
    return buffer

"""주간 리포트 PDF 생성기 — ReportLab + matplotlib."""
import io
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # GUI 없는 서버 환경
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak,
)

logger = logging.getLogger(__name__)

# ── 폰트 등록 ────────────────────────────────────────────────────────────
_FONT_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJKkr-Regular.otf",
]
_FONT_BOLD_PATHS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJKkr-Bold.otf",
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


# ── 브랜딩 색상 ──────────────────────────────────────────────────────────
BRAND = {
    "bg_dark": colors.HexColor("#0d1117"),
    "bg_card": colors.HexColor("#161b22"),
    "bg_header": colors.HexColor("#21262d"),
    "border": colors.HexColor("#30363d"),
    "text_primary": colors.HexColor("#e6edf3"),
    "text_secondary": colors.HexColor("#8b949e"),
    "accent_blue": colors.HexColor("#58a6ff"),
    "accent_green": colors.HexColor("#3fb950"),
    "accent_red": colors.HexColor("#f85149"),
    "accent_yellow": colors.HexColor("#e3b341"),
}


def _setup_matplotlib(lang: str = "ko"):
    """matplotlib 다크 테마 + CJK 폰트 설정."""
    plt.style.use("dark_background")
    # CJK 폰트 탐색 (없으면 sans-serif 폴백)
    font_family = "sans-serif"
    if lang == "ko":
        from matplotlib.font_manager import fontManager
        for name in ["Noto Sans CJK KR", "NanumGothic", "Malgun Gothic"]:
            if any(f.name == name for f in fontManager.ttflist):
                font_family = name
                break
    plt.rcParams.update({
        "font.family": font_family,
        "axes.facecolor": "#161b22",
        "figure.facecolor": "#0d1117",
        "axes.edgecolor": "#30363d",
        "axes.labelcolor": "#8b949e",
        "xtick.color": "#8b949e",
        "ytick.color": "#8b949e",
        "grid.color": "#21262d",
    })


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


def _generate_tension_chart(data: WeeklyReportData) -> io.BytesIO:
    """긴장도 추이 라인 차트 생성."""
    _setup_matplotlib(data.lang)
    fig, ax = plt.subplots(figsize=(7, 3), dpi=150)

    countries: dict[str, dict] = {}
    for row in data.tension_series:
        cc = row["country_code"]
        if cc not in countries:
            countries[cc] = {"times": [], "scores": []}
        countries[cc]["times"].append(row["time"])
        countries[cc]["scores"].append(row["raw_score"])

    color_cycle = ["#58a6ff", "#f85149", "#3fb950", "#e3b341", "#bc8cff"]
    for i, (cc, series) in enumerate(list(countries.items())[:5]):
        ax.plot(
            series["times"], series["scores"],
            label=cc, color=color_cycle[i % len(color_cycle)],
            linewidth=1.5, marker="o", markersize=3,
        )

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.set_ylabel("긴장도 점수" if data.lang == "ko" else "Tension Score")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def _generate_topic_chart(data: WeeklyReportData) -> io.BytesIO:
    """토픽별 이슈 분포 파이 차트."""
    _setup_matplotlib(data.lang)
    fig, ax = plt.subplots(figsize=(4, 4), dpi=150)

    labels = list(data.topic_distribution.keys())[:8]
    sizes = [data.topic_distribution[l] for l in labels]
    pie_colors = ["#58a6ff", "#f85149", "#3fb950", "#e3b341",
                  "#bc8cff", "#f778ba", "#79c0ff", "#a5d6ff"]

    ax.pie(
        sizes, labels=labels, autopct="%1.0f%%",
        colors=pie_colors[:len(labels)],
        textprops={"fontsize": 8, "color": "#e6edf3"},
    )
    ax.set_title(
        "토픽별 분포" if data.lang == "ko" else "Distribution by Topic",
        color="#e6edf3", fontsize=11, pad=10,
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def build_pdf(data: WeeklyReportData) -> io.BytesIO:
    """주간 리포트 PDF 생성. BytesIO 반환."""
    _register_fonts()

    # 폰트 이름 결정 (등록 실패 시 Helvetica 폴백)
    try:
        pdfmetrics.getFont("NotoSansKR")
        font_name = "NotoSansKR"
        font_bold = "NotoSansKR-Bold"
    except KeyError:
        font_name = "Helvetica"
        font_bold = "Helvetica-Bold"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
        title="WeWantPeace Weekly Report",
        author="WeWantPeace",
    )

    styles = getSampleStyleSheet()
    s_title = ParagraphStyle(
        "WTitle", parent=styles["Title"],
        fontName=font_bold, fontSize=22,
        textColor=BRAND["text_primary"],
        spaceAfter=4 * mm,
    )
    s_h2 = ParagraphStyle(
        "WH2", parent=styles["Heading2"],
        fontName=font_bold, fontSize=14,
        textColor=BRAND["accent_blue"],
        spaceBefore=8 * mm, spaceAfter=4 * mm,
    )
    s_body = ParagraphStyle(
        "WBody", parent=styles["Normal"],
        fontName=font_name, fontSize=10,
        textColor=BRAND["text_primary"],
        leading=14,
    )
    s_small = ParagraphStyle(
        "WSmall", parent=styles["Normal"],
        fontName=font_name, fontSize=8,
        textColor=BRAND["text_secondary"],
    )

    story = []

    # ── 표지 ──────────────────────────────────────────────────────
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("WeWantPeace", s_title))
    if data.lang == "ko":
        story.append(Paragraph("주간 분쟁 모니터링 리포트", s_h2))
        story.append(Paragraph(
            f"{data.week_start.strftime('%Y.%m.%d')} ~ "
            f"{data.week_end.strftime('%Y.%m.%d')}", s_body,
        ))
    else:
        story.append(Paragraph("Weekly Conflict Monitoring Report", s_h2))
        story.append(Paragraph(
            f"{data.week_start.strftime('%b %d, %Y')} - "
            f"{data.week_end.strftime('%b %d, %Y')}", s_body,
        ))
    story.append(PageBreak())

    # ── 주간 요약 ─────────────────────────────────────────────────
    story.append(Paragraph(
        "이번 주 요약" if data.lang == "ko" else "Weekly Summary", s_h2
    ))
    summary_data = [
        [
            "수집된 이벤트" if data.lang == "ko" else "Events",
            "신규 이슈 클러스터" if data.lang == "ko" else "New Clusters",
            "위기 국가" if data.lang == "ko" else "Crisis Countries",
        ],
        [
            str(data.total_events),
            str(data.new_clusters),
            str(data.crisis_countries),
        ],
    ]
    t = Table(summary_data, colWidths=[55 * mm, 55 * mm, 55 * mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), font_name),
        ("FONTNAME", (0, 1), (-1, 1), font_bold),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, 1), 18),
        ("TEXTCOLOR", (0, 0), (-1, 0), BRAND["text_secondary"]),
        ("TEXTCOLOR", (0, 1), (0, 1), BRAND["accent_blue"]),
        ("TEXTCOLOR", (1, 1), (1, 1), BRAND["accent_green"]),
        ("TEXTCOLOR", (2, 1), (2, 1), BRAND["accent_red"]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, -1), BRAND["bg_card"]),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND["border"]),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, BRAND["border"]),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 8 * mm))

    # ── TOP 10 이슈 ──────────────────────────────────────────────
    if data.top_issues:
        story.append(Paragraph(
            "TOP 10 이슈" if data.lang == "ko" else "Top 10 Issues", s_h2
        ))
        header = [
            "#",
            "국가" if data.lang == "ko" else "Country",
            "이슈" if data.lang == "ko" else "Issue",
            "심각도" if data.lang == "ko" else "Severity",
        ]
        rows = [header]
        for i, issue in enumerate(data.top_issues[:10], 1):
            title = issue.get("title_ko") or issue.get("title", "")
            if len(title) > 40:
                title = title[:40] + "..."
            rows.append([
                str(i),
                issue.get("country_code", "-"),
                Paragraph(title, s_body),
                str(issue.get("severity", "-")),
            ])

        t = Table(rows, colWidths=[10 * mm, 18 * mm, 110 * mm, 20 * mm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), font_bold),
            ("FONTNAME", (0, 1), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), BRAND["accent_blue"]),
            ("TEXTCOLOR", (0, 1), (-1, -1), BRAND["text_primary"]),
            ("BACKGROUND", (0, 0), (-1, 0), BRAND["bg_header"]),
            ("BACKGROUND", (0, 1), (-1, -1), BRAND["bg_card"]),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, BRAND["border"]),
            ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND["border"]),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, BRAND["border"]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 8 * mm))

    # ── 긴장도 추이 차트 ─────────────────────────────────────────
    if data.tension_series:
        story.append(Paragraph(
            "긴장도 추이" if data.lang == "ko" else "Tension Trends", s_h2
        ))
        chart_buf = _generate_tension_chart(data)
        story.append(Image(chart_buf, width=165 * mm, height=70 * mm))
        story.append(Spacer(1, 8 * mm))

    # ── 토픽별 분포 ──────────────────────────────────────────────
    if data.topic_distribution:
        story.append(Paragraph(
            "토픽별 이슈 분포" if data.lang == "ko" else "Issue Distribution by Topic", s_h2
        ))
        pie_buf = _generate_topic_chart(data)
        story.append(Image(pie_buf, width=90 * mm, height=90 * mm))

    # ── 면책/푸터 ────────────────────────────────────────────────
    story.append(Spacer(1, 15 * mm))
    disclaimer = (
        "본 리포트는 공개 데이터 기반 AI 분석 결과이며, 투자 자문이 아닙니다."
        if data.lang == "ko"
        else "This report is AI-powered analysis based on public data and is not investment advice."
    )
    story.append(Paragraph(disclaimer, s_small))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "https://www.wewantpeace.live | WeWantPeace Weekly Report",
        ParagraphStyle(
            "WFooter", parent=s_small,
            alignment=TA_CENTER,
            textColor=BRAND["text_secondary"],
        ),
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer

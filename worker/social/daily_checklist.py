"""Phase 1 마케팅 일일 체크리스트 -- 매일 KST 09:00 텔레그램 전송."""

import logging
from datetime import date, datetime, timezone, timedelta

import os

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("SOCIAL_TG_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("SOCIAL_TG_CHAT_ID", "")

# X Thread 시작일: 2026-03-09 = Day 1
THREAD_START_DATE = date(2026, 3, 9)
THREAD_TOTAL_DAYS = 7

# GeekNews 가입일: 2026-03-09, 글 작성 가능일: 7일 후
GEEKNEWS_SIGNUP_DATE = date(2026, 3, 9)
GEEKNEWS_WAIT_DAYS = 7


def _thread_day(today: date) -> int:
    """오늘이 Thread Day 몇인지 계산. Day 1~7, 이후 8+."""
    delta = (today - THREAD_START_DATE).days + 1  # 3/9 = Day 1
    return max(delta, 1)


def _build_message(today: date) -> str:
    """체크리스트 HTML 메시지를 생성한다."""
    day_n = _thread_day(today)
    date_str = today.strftime("%Y-%m-%d")

    # X Thread 섹션
    if day_n <= THREAD_TOTAL_DAYS:
        x_section = (
            "<b>\U0001f426 X #BuildInPublic</b>\n"
            "\u2502 \U0001f3af 인디해커 커뮤니티에 존재감 + 팔로워 확보\n"
            "\u25a1 Thread {day}/7 올리기 (밤 11시 KST)\n"
            "\u25a1 답글 확인 + 1시간 내 답장\n"
            "\u25a1 @WeWantPeaceNews 인용RT"
        ).format(day=day_n)
        footer = "\U0001f4a1 X Thread는 매일 1개씩, 총 7일. 오늘은 Day {day}.".format(day=day_n)
    else:
        x_section = (
            "<b>\U0001f426 X #BuildInPublic</b>\n"
            "\u2502 \u2705 7개 스레드 완료!"
        )
        footer = "\U0001f4a1 X Thread 7개 완료! 다음 단계를 계획하세요."

    # GeekNews 섹션
    gn_available_date = GEEKNEWS_SIGNUP_DATE + timedelta(days=GEEKNEWS_WAIT_DAYS)
    days_until_gn = (gn_available_date - today).days
    if days_until_gn > 0:
        geeknews_section = (
            "<b>\U0001f4e2 GeekNews Show GN</b>\n"
            "\u2502 \u23f3 글 작성까지 {d}일 남음 ({avail}부터 가능)\n"
            "\n"
        ).format(d=days_until_gn, avail=gn_available_date.strftime("%m/%d"))
    elif days_until_gn == 0:
        geeknews_section = (
            "<b>\U0001f6a8 GeekNews Show GN</b>\n"
            "\u2502 \u2757 오늘부터 글 작성 가능!\n"
            "\u25a1 https://news.hada.io/show 에서 Show GN 글 올리기\n"
            "\n"
        )
    else:
        geeknews_section = (
            "<b>\U0001f4e2 GeekNews Show GN</b>\n"
            "\u25a1 Show GN 글 올리기 (가입 대기 완료)\n"
            "\n"
        )

    msg = (
        "\U0001f4cb <b>Phase 1 Daily Checklist</b> \u2014 {date}\n"
        "\n"
        "{x_section}\n"
        "\n"
        "<b>\U0001f4ac Reddit 카르마</b>\n"
        "\u2502 \U0001f3af 포스팅 권한 확보 (카르마 50+ 목표)\n"
        "\u25a1 r/SideProject 또는 r/OSINT에 댓글 3개+\n"
        "\u25a1 진심 어린 피드백/답변 (홍보 금지)\n"
        "\n"
        "<b>\U0001f4e7 이메일 회신 확인</b>\n"
        "\u2502 \U0001f3af OSINT 커뮤니티 전문가 유저 확보\n"
        "\u25a1 Bellingcat 회신 확인\n"
        "\u25a1 GIJN 회신 확인\n"
        "\u25a1 OCCRP 회신 확인\n"
        "\n"
        "<b>\U0001f4cc PR 상태 확인</b>\n"
        "\u2502 \U0001f3af 영구 백링크 확보 (merged되면 월 50-200클릭)\n"
        "\u25a1 awesome-osint PR #826 확인\n"
        "\u25a1 awesome-disastertech PR #2 확인\n"
        "\u25a1 awesome-humanitarian-foss PR #6 확인\n"
        "\u25a1 ALL-about-RSS PR #128 확인\n"
        "\n"
        "<b>\U0001f4f0 Show HN</b>\n"
        "\u2502 \u2705 포스팅 완료 (item?id=47303606)\n"
        "\u25a1 새 댓글 확인 + 답변\n"
        "\n"
        "{geeknews_section}"
        "<b>\U0001f514 기타</b>\n"
        "\u25a1 Product Hunt 런칭일 결정\n"
        "\n"
        "{footer}"
    ).format(date=date_str, x_section=x_section, geeknews_section=geeknews_section, footer=footer)

    return msg


def send_daily_checklist(target_date: date | None = None) -> dict:
    """텔레그램으로 일일 체크리스트를 전송한다.

    Args:
        target_date: 체크리스트 날짜. None이면 KST 기준 오늘.

    Returns:
        Telegram API 응답 dict.
    """
    if target_date is None:
        kst = timezone(timedelta(hours=9))
        target_date = datetime.now(kst).date()

    message = _build_message(target_date)

    url = "https://api.telegram.org/bot{token}/sendMessage".format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload)
        result = resp.json()

    if result.get("ok"):
        logger.info("일일 체크리스트 전송 성공 (date=%s)", target_date)
    else:
        logger.error(
            "일일 체크리스트 전송 실패: %s (hint: 봇에 /start를 보냈는지 확인)",
            result,
        )

    return result

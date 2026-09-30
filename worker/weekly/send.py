"""주간 브리핑 발송 — 받는 사람 모으기 · 언어 정하기 · Resend 로 보내기.

받는 사람 = 마케팅 수신 동의 회원 ∪ 확인 완료한 무료 브리프 구독자 (이메일로 중복 제거).

언어 (2026-09-30 실측): 회원 설정은 language='ko', timezone='Asia/Seoul', 가입 국가 'KR'이
전부 기본값이라(온보딩 기본 국가도 KR) 74명 중 71명이 한국어판을 받았지만, 구글 표시 이름이
서양식(First Last)인 사람이 16명, 한글 이름은 29명뿐이었다. 설정만 믿지 않는다:
  - 브리프 구독자: 본인이 고른 lang
  - 회원: 이름(닉네임·표시 이름)에 한글이 있으면 ko, 그 밖은 WEEKLY_AMBIGUOUS_LANG(기본 en).
          로마자 한국 이름("Minsoo Kim")도 서양식처럼 보여 이름만으로는 가를 수 없다(글을 남긴 사람도
          28명 중 2명뿐). 잘못 보냈을 때 한국인이 영어판을 받는 쪽이 덜 나쁘다 — 외국인이 한국어판을
          받으면 읽지 못하고 끊는다. 메일 맨 위에 한 번 누르면 바뀌는 언어 링크를 둔다.
발송 시각: 한국어판은 월 07:00 KST(일 22:00 UTC), 영어판은 월 11:00 UTC.
"""
from __future__ import annotations

import hmac
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)



@dataclass
class Recipient:
    email: str
    lang: str
    kind: str                       # "user" | "subscriber"
    token: str                      # 수신거부·언어 바꾸기 토큰
    follow: list[str] = field(default_factory=list)


def user_token(user_id) -> str:
    """backend/app/routers/newsletter.py _generate_token 과 같은 값 (수신거부 페이지가 이걸로 찾는다)."""
    from backend.app.core.config import settings
    return hmac.new(settings.secret_key.encode(), str(user_id).encode(), sha256).hexdigest()[:32]


def decide_user_lang(nickname: str | None, display_name: str | None, pref_lang: str | None,
                     explicit: bool = False) -> str:
    """explicit=True 는 사용자가 메일의 언어 링크로 직접 고른 경우 (그대로 따른다)."""
    import os
    if explicit and pref_lang in ("ko", "en"):
        return pref_lang
    names = f"{nickname or ''} {display_name or ''}"
    if re.search(r"[가-힣]", names):
        return "ko"
    if pref_lang == "en":
        return "en"
    return "ko" if os.getenv("WEEKLY_AMBIGUOUS_LANG", "en") == "ko" else "en"


async def collect_recipients(db: AsyncSession) -> list[Recipient]:
    from backend.app.models.brief_subscriber import BriefSubscriber
    from backend.app.models.user import User, UserArea, UserPreference

    out: dict[str, Recipient] = {}
    rows = (await db.execute(
        select(User, UserPreference).join(UserPreference, User.id == UserPreference.user_id, isouter=True)
        .where(User.marketing_agreed_at.isnot(None), User.status != "deleted", User.email.isnot(None))
    )).all()
    areas: dict = {}
    chosen = _explicit_lang_users()
    if rows:
        for uid, cc in (await db.execute(
            select(UserArea.user_id, UserArea.country_code)
            .where(UserArea.is_active.is_(True), UserArea.country_code.isnot(None))
        )).all():
            areas.setdefault(uid, []).append(cc)
    for user, pref in rows:
        email = user.email.strip().lower()
        out[email] = Recipient(
            email=email, kind="user", token=user_token(user.id),
            lang=decide_user_lang(user.nickname, user.display_name, pref.language if pref else None,
                                  explicit=str(user.id) in chosen),
            follow=areas.get(user.id, [])[:3],
        )
    for sub in (await db.execute(select(BriefSubscriber).where(BriefSubscriber.status == "active"))).scalars():
        email = sub.email.strip().lower()
        if email in out:
            # 회원이면서 브리프도 신청 — 고른 나라를 앞에 두고 한 통만
            r = out[email]
            r.follow = list(dict.fromkeys((sub.countries or []) + r.follow))[:3]
            continue
        out[email] = Recipient(email=email, kind="subscriber", token=sub.token,
                               lang="ko" if sub.lang == "ko" else "en", follow=(sub.countries or [])[:3])
    return list(out.values())


def _explicit_lang_users() -> set[str]:
    """메일의 언어 링크를 누른 회원 id (Redis 집합 weekly:lang_chosen)."""
    try:
        from worker.ai_config import _get_redis_sync
        return {m if isinstance(m, str) else m.decode() for m in _get_redis_sync().smembers("weekly:lang_chosen")}
    except Exception:
        return set()


def links_for(r: Recipient) -> dict:
    from worker.weekly.render import API, SITE
    if r.kind == "subscriber":
        unsub = f"{SITE}/brief/unsubscribe?token={r.token}"
    else:
        unsub = f"{SITE}/unsubscribe?token={r.token}"
    other = "en" if r.lang == "ko" else "ko"
    return {"unsubscribe_url": unsub,
            "switch_url": f"{API}/newsletter/lang?t={r.token}&k={r.kind}&lang={other}"}


def send_edition(data: dict, recipients: list[Recipient], lang: str, *, dry_run: bool = False,
                 only: str | None = None) -> dict:
    """lang 판을 받을 사람에게 보낸다. only=이메일 하나만 (테스트)."""
    from backend.app.core.mailer import send_email
    from worker.weekly.render import render_email

    targets = [r for r in recipients if r.lang == lang and (only is None or r.email == only.lower())]
    sent = failed = 0
    subject = ""
    for r in targets:
        links = links_for(r)
        mail = render_email(data, lang, follow=r.follow or None, subscriber=r.kind == "subscriber",
                            feedback_token=r.token[:12], **links)
        subject = mail["subject"]
        if dry_run:
            sent += 1
            continue
        ok = send_email(r.email, mail["subject"], mail["html"], text=mail["text"], headers={
            "List-Unsubscribe": f"<{links['unsubscribe_url']}>",
        })
        sent += int(ok)
        failed += int(not ok)
        time.sleep(0.6)  # Resend 초당 2건
    return {"lang": lang, "targets": len(targets), "sent": sent, "failed": failed, "subject": subject}


async def log_send(db: AsyncSession, data: dict, result: dict) -> None:
    from backend.app.models.community import MarketingEmailLog
    db.add(MarketingEmailLog(
        admin_id=None,
        subject=f"WeWantPeace Weekly {data['week_key']} ({result['lang']}) — {result['subject'][:120]}",
        body=f"weekly edition: targets={result['targets']} sent={result['sent']} failed={result['failed']}",
        sent_count=result["sent"], failed_count=result["failed"],
        status="completed" if result["sent"] else "failed",
    ))
    await db.flush()

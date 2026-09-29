"""나라별 주간 브리프 구독 — 로그인 없이, 이중 확인 (2026-09-30).

POST /briefs/subscribe     이메일 + 나라(최대 3) + 동의 → 확인 메일
GET  /briefs/confirm       확인 링크 → active
GET  /briefs/unsubscribe   수신거부 화면용 정보(마스킹 이메일)
POST /briefs/unsubscribe   수신거부

응답은 이미 구독 중이든 아니든 똑같이 돌려준다 — 이메일 가입 여부를 캐낼 수 없게.
"""
import html
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_db
from backend.app.core.limiter import limiter
from backend.app.core.mailer import send_email
from backend.app.models.brief_subscriber import BriefSubscriber

router = APIRouter(prefix="/briefs", tags=["briefs"])

SITE = "https://www.wewantpeace.live"
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$")
_CC_RE = re.compile(r"^[A-Z]{2}$")
MAX_COUNTRIES = 3


class SubscribeBody(BaseModel):
    email: str
    countries: list[str]
    lang: str = "en"
    consent: bool = False
    source: str | None = None


class TokenBody(BaseModel):
    token: str


def _mask(email: str) -> str:
    local, _, domain = email.partition("@")
    return (local[:2] + "***@" + domain) if local else email


def _confirm_mail(sub: BriefSubscriber) -> tuple[str, str, str]:
    link = f"{SITE}/brief/confirm?token={sub.token}"
    names = ", ".join(sub.countries)
    if sub.lang == "ko":
        subject = "WeWantPeace 주간 브리프 구독 확인"
        body = (
            f"<p>{html.escape(names)} 주간 브리프 구독을 요청하셨습니다.</p>"
            f"<p><a href='{link}'>구독 확인하기</a></p>"
            "<p>요청하지 않으셨다면 이 메일을 무시하세요. 확인 전에는 아무것도 보내지 않습니다.</p>"
        )
        text = f"{names} 주간 브리프 구독 확인: {link}\n요청하지 않으셨다면 무시하세요."
    else:
        subject = "Confirm your WeWantPeace weekly brief"
        body = (
            f"<p>You asked for a weekly brief on {html.escape(names)}.</p>"
            f"<p><a href='{link}'>Confirm subscription</a></p>"
            "<p>If this wasn't you, ignore this email. Nothing is sent until you confirm.</p>"
        )
        text = f"Confirm your weekly brief on {names}: {link}\nIf this wasn't you, ignore this email."
    return subject, body, text


@router.post("/subscribe")
@limiter.limit("5/minute")
async def subscribe(request: Request, response: Response, body: SubscribeBody, db: AsyncSession = Depends(get_db)):
    email = body.email.strip().lower()
    if not _EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(422, detail="invalid_email")
    if not body.consent:
        raise HTTPException(422, detail="consent_required")
    countries = []
    for cc in body.countries:
        cc = (cc or "").strip().upper()
        if _CC_RE.match(cc) and cc not in countries:
            countries.append(cc)
    if not countries:
        raise HTTPException(422, detail="countries_required")
    countries = countries[:MAX_COUNTRIES]
    lang = "ko" if body.lang == "ko" else "en"
    now = datetime.now(timezone.utc)

    sub = (await db.execute(select(BriefSubscriber).where(BriefSubscriber.email == email))).scalar_one_or_none()
    if sub is None:
        sub = BriefSubscriber(
            email=email, countries=countries, lang=lang, status="pending",
            token=secrets.token_urlsafe(24), consent_at=now, source=(body.source or "")[:32] or None,
        )
        db.add(sub)
    elif sub.status == "active":
        # 이미 구독 중 — 나라만 갱신하고 같은 응답
        sub.countries = countries
        sub.lang = lang
        await db.flush()
        return {"status": "check_email"}
    else:
        sub.countries = countries
        sub.lang = lang
        sub.status = "pending"
        sub.consent_at = now
        sub.unsubscribed_at = None
    await db.flush()

    subject, html_body, text = _confirm_mail(sub)
    send_email(email, subject, html_body, text=text)
    return {"status": "check_email"}


async def _by_token(db: AsyncSession, token: str) -> BriefSubscriber:
    sub = (await db.execute(select(BriefSubscriber).where(BriefSubscriber.token == token))).scalar_one_or_none()
    if not sub:
        raise HTTPException(404, detail="invalid_token")
    return sub


@router.get("/confirm")
@limiter.limit("20/minute")
async def confirm(request: Request, response: Response, token: str = Query(..., min_length=10, max_length=64),
                  db: AsyncSession = Depends(get_db)):
    sub = await _by_token(db, token)
    if sub.status != "active":
        sub.status = "active"
        sub.confirmed_at = datetime.now(timezone.utc)
        sub.unsubscribed_at = None
        await db.flush()
    return {"status": "active", "countries": sub.countries, "email": _mask(sub.email)}


@router.get("/unsubscribe")
@limiter.limit("20/minute")
async def unsubscribe_info(request: Request, response: Response, token: str = Query(..., min_length=10, max_length=64),
                           db: AsyncSession = Depends(get_db)):
    sub = await _by_token(db, token)
    return {"status": sub.status, "countries": sub.countries, "email": _mask(sub.email)}


@router.post("/unsubscribe")
@limiter.limit("20/minute")
async def unsubscribe(request: Request, response: Response, body: TokenBody, db: AsyncSession = Depends(get_db)):
    sub = await _by_token(db, body.token)
    if sub.status != "unsubscribed":
        sub.status = "unsubscribed"
        sub.unsubscribed_at = datetime.now(timezone.utc)
        await db.flush()
    return {"status": "unsubscribed"}

"""
/newsletter/* 뉴스레터 수신거부 + 아카이브 + 통계 + 샘플 API (인증 불필요)

GET  /newsletter/unsubscribe?token=xxx  -- 마스킹된 이메일 + 확인 UI 데이터
POST /newsletter/unsubscribe            -- 수신거부 실행
GET  /newsletter/archive                -- 발송된 뉴스레터 목록 (public)
GET  /newsletter/archive/{log_id}       -- 특정 뉴스레터 HTML (public)
GET  /newsletter/stats                  -- 구독자 수 (public)
GET  /newsletter/sample?lang=kr|us      -- 샘플 뉴스레터 HTML (public)
"""
from __future__ import annotations

import hmac
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_db
from backend.app.core.config import settings
from backend.app.core.redis import get_redis
from backend.app.models.user import User
from backend.app.models.terms import UserConsent
from backend.app.models.community import MarketingEmailLog

router = APIRouter(prefix="/newsletter", tags=["newsletter"])


def _generate_token(user_id: str) -> str:
    """HMAC-SHA256 기반 수신거부 토큰 생성."""
    return hmac.new(
        settings.secret_key.encode(),
        str(user_id).encode(),
        sha256,
    ).hexdigest()[:32]


def _mask_email(email: str) -> str:
    """이메일 마스킹: k***@gmail.com 형식."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 1:
        masked_local = local + "***"
    else:
        masked_local = local[0] + "***"
    return f"{masked_local}@{domain}"


async def _find_user_by_token(
    token: str, db: AsyncSession
) -> User | None:
    """토큰으로 유저 조회 (모든 유저 순회하며 HMAC 비교)."""
    result = await db.execute(
        select(User).where(User.status != "deleted", User.email != None)
    )
    users = result.scalars().all()
    for u in users:
        expected = _generate_token(u.id)
        if hmac.compare_digest(expected, token):
            return u
    return None


# ── GET /newsletter/unsubscribe ──────────────────────────────────────────────

@router.get("/unsubscribe")
async def unsubscribe_info(
    token: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """수신거부 확인 페이지 데이터: 마스킹된 이메일 반환."""
    user = await _find_user_by_token(token, db)
    if not user:
        raise HTTPException(404, detail="Invalid or expired token")

    already_unsubscribed = user.marketing_agreed_at is None

    return {
        "masked_email": _mask_email(user.email),
        "already_unsubscribed": already_unsubscribed,
    }


# ── POST /newsletter/unsubscribe ─────────────────────────────────────────────

class UnsubscribeBody(BaseModel):
    token: str


@router.post("/unsubscribe")
async def unsubscribe_execute(
    body: UnsubscribeBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """수신거부 실행: marketing_agreed_at = None + UserConsent 기록."""
    user = await _find_user_by_token(body.token, db)
    if not user:
        raise HTTPException(404, detail="Invalid or expired token")

    if user.marketing_agreed_at is None:
        return {"status": "already_unsubscribed", "masked_email": _mask_email(user.email)}

    # 마케팅 동의 해제
    user.marketing_agreed_at = None

    # UserConsent 기록
    db.add(UserConsent(
        user_id=user.id,
        term_type="marketing_revoke",
        term_version="1.0",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500] if request else None,
    ))

    await db.flush()

    return {"status": "ok", "masked_email": _mask_email(user.email)}


# ── GET /newsletter/stats ───────────────────────────────────────────────────

@router.get("/stats")
async def newsletter_stats(db: AsyncSession = Depends(get_db)):
    """구독자 수 반환 (Redis 1시간 캐싱)."""
    redis = get_redis()
    cached = await redis.get("newsletter:stats:subscriber_count")
    if cached is not None:
        return {"subscriber_count": int(cached)}

    result = await db.execute(
        select(func.count()).select_from(User).where(
            User.marketing_agreed_at != None,
            User.status != "deleted",
            User.email != None,
        )
    )
    count = result.scalar() or 0
    await redis.set("newsletter:stats:subscriber_count", str(count), ex=3600)
    return {"subscriber_count": count}


# ── GET /newsletter/archive ─────────────────────────────────────────────────

@router.get("/archive")
async def newsletter_archive_list(db: AsyncSession = Depends(get_db)):
    """발송 완료된 뉴스레터 목록 (최근 20건)."""
    result = await db.execute(
        select(MarketingEmailLog)
        .where(MarketingEmailLog.status == "completed")
        .order_by(MarketingEmailLog.created_at.desc())
        .limit(20)
    )
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "subject": l.subject,
            "sent_count": l.sent_count,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


# ── GET /newsletter/archive/{log_id} ────────────────────────────────────────

@router.get("/archive/{log_id}")
async def newsletter_archive_detail(log_id: int):
    """특정 뉴스레터 HTML 반환."""
    redis = get_redis()
    html = await redis.get(f"newsletter:archive:{log_id}")
    if not html:
        raise HTTPException(404, detail="Newsletter not found")
    return HTMLResponse(content=html)


# ── GET /newsletter/sample ─────────────────────────────────────────────────

@router.get("/sample")
async def newsletter_sample(lang: str = Query("kr", regex="^(kr|us)$")):
    """샘플 뉴스레터 HTML 반환 (공개, Redis 24h 캐시)."""
    import chevron
    import json as _json
    import os

    redis = get_redis()
    cache_key = f"newsletter:sample:{lang}"
    cached = await redis.get(cache_key)
    if cached:
        return HTMLResponse(content=cached)

    tpl_dir = Path(os.path.dirname(__file__)).parent / "templates" / "newsletter"
    tpl_name = "newsletter-v1-final-ko.html" if lang == "kr" else "newsletter-v1-final-en.html"
    tpl_path = tpl_dir / tpl_name
    if not tpl_path.exists():
        raise HTTPException(404, detail="Template not found")

    with open(tpl_path, "r", encoding="utf-8") as f:
        template = f.read()

    # 샘플 데이터 로드
    sample_name = "vol1-kr-sample.json" if lang == "kr" else "vol1-us-sample.json"
    sample_path = tpl_dir / sample_name
    data: dict = {}
    if sample_path.exists():
        with open(sample_path, "r", encoding="utf-8") as f:
            data = _json.load(f)
        # @file: 참조 해소
        for key, value in list(data.items()):
            if isinstance(value, str) and value.startswith("@file:"):
                ref_path = tpl_dir.parent.parent.parent.parent / "docs" / "marketing" / value[6:]
                if not ref_path.exists():
                    ref_path = tpl_dir / value[6:]
                if ref_path.exists():
                    with open(ref_path, "r", encoding="utf-8") as f:
                        data[key] = f.read()
        data.pop("_comment", None)
        data.pop("_template", None)

    html = chevron.render(template, data)
    await redis.set(cache_key, html, ex=86400)  # 24h
    return HTMLResponse(content=html)

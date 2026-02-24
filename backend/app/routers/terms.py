"""
/terms/* 약관 API
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db
from backend.app.models.user import User
from backend.app.models.terms import TermVersion, UserConsent

router = APIRouter(prefix="/terms", tags=["terms"])


class ConsentBody(BaseModel):
    term_type: str
    term_version: str


@router.get("/current")
async def get_current_terms(db: AsyncSession = Depends(get_db)):
    """현재 최신 약관 버전 목록 반환."""
    result = await db.execute(
        select(TermVersion).order_by(TermVersion.effective_at.desc())
    )
    versions = result.scalars().all()

    # type별 최신 1개만
    seen = {}
    for v in versions:
        if v.type not in seen:
            seen[v.type] = {"type": v.type, "version": v.version, "effective_at": v.effective_at.isoformat()}

    return list(seen.values())


@router.get("/{term_type}/{version}")
async def get_term_content(term_type: str, version: str, db: AsyncSession = Depends(get_db)):
    if term_type not in ("terms", "privacy"):
        raise HTTPException(404)
    result = await db.execute(
        select(TermVersion).where(TermVersion.type == term_type, TermVersion.version == version)
    )
    tv = result.scalar_one_or_none()
    if not tv:
        raise HTTPException(404, detail="해당 약관을 찾을 수 없습니다.")
    return {"type": tv.type, "version": tv.version, "content": tv.content, "effective_at": tv.effective_at.isoformat()}


@router.post("/consent", status_code=201)
async def record_consent(
    body: ConsentBody,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:500]

    consent = UserConsent(
        user_id=current_user.id,
        term_type=body.term_type,
        term_version=body.term_version,
        ip_address=ip,
        user_agent=ua,
    )
    db.add(consent)
    await db.flush()
    return {"status": "ok"}

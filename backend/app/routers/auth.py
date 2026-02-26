"""
/auth/* 인증·프로필 API

POST /auth/register      — Firebase 가입 후 서버 등록 (닉네임, 약관 동의)
GET  /auth/check-nickname — 닉네임 중복 확인
PATCH /auth/profile       — 프로필 수정
DELETE /auth/account      — 회원 탈퇴
"""
from __future__ import annotations
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db, _verify_firebase_token, _get_or_create_user
from backend.app.models.user import User, UserPreference
from backend.app.models.terms import UserConsent

router = APIRouter(prefix="/auth", tags=["auth"])

CURRENT_TERMS_VERSION = "2.0"
CURRENT_PRIVACY_VERSION = "2.0"
CURRENT_YEAR = 2026


# ── 스키마 ──────────────────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    firebase_token: str
    nickname: str
    birth_year: int
    agreed_terms: bool
    agreed_privacy: bool
    marketing_agreed: bool = False
    display_name: Optional[str] = None
    email: Optional[str] = None

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2 or len(v) > 20:
            raise ValueError("닉네임은 2~20자여야 합니다.")
        if not re.match(r"^[가-힣a-zA-Z0-9_]+$", v):
            raise ValueError("닉네임은 한글, 영문, 숫자, 언더스코어만 가능합니다.")
        forbidden = ["admin", "관리자", "운영자", "support", "system"]
        if v.lower() in forbidden:
            raise ValueError("사용할 수 없는 닉네임입니다.")
        return v


class ProfilePatch(BaseModel):
    nickname: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_image_url: Optional[str] = None


class UserOut(BaseModel):
    id: str
    firebase_uid: str
    email: Optional[str]
    nickname: Optional[str]
    display_name: Optional[str]
    bio: Optional[str]
    profile_image_url: Optional[str]
    plan: str
    role: str
    status: str
    birth_year: Optional[int]
    agreed_terms_at: Optional[str]
    agreed_privacy_at: Optional[str]
    marketing_agreed_at: Optional[str]


def _user_to_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        firebase_uid=u.firebase_uid,
        email=u.email,
        nickname=u.nickname,
        display_name=u.display_name,
        bio=u.bio,
        profile_image_url=u.profile_image_url,
        plan=u.plan,
        role=u.role,
        status=u.status,
        birth_year=u.birth_year,
        agreed_terms_at=u.agreed_terms_at.isoformat() if u.agreed_terms_at else None,
        agreed_privacy_at=u.agreed_privacy_at.isoformat() if u.agreed_privacy_at else None,
        marketing_agreed_at=u.marketing_agreed_at.isoformat() if u.marketing_agreed_at else None,
    )


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserOut, status_code=201)
async def register(
    body: RegisterBody,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Firebase 가입 후 서버 등록. 닉네임 설정 + 약관 동의 기록."""
    # 약관 필수 동의 확인
    if not body.agreed_terms:
        raise HTTPException(422, detail="이용약관에 동의해야 합니다.")
    if not body.agreed_privacy:
        raise HTTPException(422, detail="개인정보처리방침에 동의해야 합니다.")

    # 만 14세 미만 거부
    if CURRENT_YEAR - body.birth_year < 14:
        raise HTTPException(400, detail="만 14세 미만은 가입이 불가능합니다.")

    # Firebase 토큰 검증
    token_info = _verify_firebase_token(body.firebase_token)
    if not token_info:
        raise HTTPException(401, detail="유효하지 않은 Firebase 토큰입니다.")
    firebase_uid = token_info["uid"]
    token_email = token_info.get("email")

    # 닉네임 중복 확인
    existing = await db.execute(select(User).where(User.nickname == body.nickname))
    if existing.scalar_one_or_none():
        raise HTTPException(409, detail="이미 사용 중인 닉네임입니다.")

    # 이메일: body에서 명시적으로 전달된 값 > 토큰에서 추출된 값
    user_email = body.email or token_email

    # 사용자 생성 또는 조회
    user = await _get_or_create_user(firebase_uid, db, email=user_email)

    # 프로필 업데이트
    now = datetime.now(timezone.utc)
    user.nickname = body.nickname
    user.birth_year = body.birth_year
    user.display_name = body.display_name or body.nickname
    if user_email:
        user.email = user_email
    user.agreed_terms_at = now
    user.agreed_privacy_at = now
    if body.marketing_agreed:
        user.marketing_agreed_at = now

    # 어드민 이메일 자동 승격
    import os
    admin_email = os.getenv("ADMIN_EMAIL", "")
    if admin_email and user.email and user.email.lower() == admin_email.lower():
        user.role = "admin"

    await db.flush()

    # 약관 동의 기록
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:500]

    for term_type, term_ver in [("terms", CURRENT_TERMS_VERSION), ("privacy", CURRENT_PRIVACY_VERSION)]:
        consent = UserConsent(
            user_id=user.id,
            term_type=term_type,
            term_version=term_ver,
            ip_address=ip,
            user_agent=ua,
        )
        db.add(consent)

    if body.marketing_agreed:
        db.add(UserConsent(
            user_id=user.id,
            term_type="marketing",
            term_version="1.0",
            ip_address=ip,
            user_agent=ua,
        ))

    await db.flush()
    return _user_to_out(user)


@router.get("/check-nickname")
async def check_nickname(nickname: str, db: AsyncSession = Depends(get_db)):
    """닉네임 중복 확인."""
    result = await db.execute(select(User).where(User.nickname == nickname.strip()))
    exists = result.scalar_one_or_none() is not None
    return {"available": not exists, "nickname": nickname.strip()}


@router.patch("/profile", response_model=UserOut)
async def update_profile(
    body: ProfilePatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로필 수정."""
    if body.nickname is not None:
        body.nickname = body.nickname.strip()
        if body.nickname != current_user.nickname:
            existing = await db.execute(select(User).where(User.nickname == body.nickname))
            if existing.scalar_one_or_none():
                raise HTTPException(409, detail="이미 사용 중인 닉네임입니다.")
        current_user.nickname = body.nickname
    if body.display_name is not None:
        current_user.display_name = body.display_name
    if body.bio is not None:
        if len(body.bio) > 200:
            raise HTTPException(422, detail="자기소개는 200자 이내로 입력해주세요.")
        current_user.bio = body.bio
    if body.profile_image_url is not None:
        current_user.profile_image_url = body.profile_image_url
    await db.flush()
    return _user_to_out(current_user)


@router.delete("/account", status_code=204)
async def delete_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """회원 탈퇴: 개인정보 익명화 + Firebase 사용자 삭제."""
    uid_prefix = str(current_user.id)[:8]
    firebase_uid = current_user.firebase_uid

    current_user.email = f"deleted_{uid_prefix}@deleted.invalid"
    current_user.nickname = None
    current_user.display_name = None
    current_user.bio = None
    current_user.profile_image_url = None
    current_user.birth_year = None
    current_user.marketing_agreed_at = None
    current_user.agreed_terms_at = None
    current_user.agreed_privacy_at = None
    current_user.status = "deleted"
    await db.flush()

    # Firebase에서도 사용자 삭제 시도 (실패해도 무시)
    try:
        import firebase_admin.auth as fb_auth
        fb_auth.delete_user(firebase_uid)
    except Exception:
        pass

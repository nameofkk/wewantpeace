"""
/auth/* 인증·프로필 API

POST /auth/register      — Firebase 가입 후 서버 등록 (닉네임, 약관 동의)
POST /auth/toss-login    — 토스 앱인토스 로그인 (authorizationCode → Firebase Custom Token)
GET  /auth/check-nickname — 닉네임 중복 확인
PATCH /auth/profile       — 프로필 수정
DELETE /auth/account      — 회원 탈퇴
"""
from __future__ import annotations
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_current_user, get_db, _verify_firebase_token, _get_or_create_user
from backend.app.core.config import settings
from backend.app.models.user import User, UserPreference
from backend.app.models.terms import UserConsent

logger = logging.getLogger(__name__)

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


# ── 토스 로그인 ─────────────────────────────────────────────────────────────

class TossLoginBody(BaseModel):
    authorization_code: str


class TossLoginOut(BaseModel):
    firebase_custom_token: str
    is_new_user: bool
    user_id: Optional[str] = None


TOSS_API_BASE = "https://apps-in-toss-api.toss.im"


async def _exchange_toss_code(authorization_code: str) -> dict:
    """Toss authorizationCode → accessToken 교환."""
    import httpx

    if not settings.toss_app_secret:
        raise HTTPException(503, detail="토스 로그인이 설정되지 않았습니다. (TOSS_APP_SECRET 필요)")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{TOSS_API_BASE}/api-partner/v1/apps-in-toss/user/oauth2/generate-token",
            json={"authorizationCode": authorization_code},
            headers={
                "Authorization": f"Bearer {settings.toss_app_secret}",
                "Content-Type": "application/json",
            },
        )
    if resp.status_code != 200:
        logger.error("토스 토큰 교환 실패: %s %s", resp.status_code, resp.text)
        raise HTTPException(401, detail="토스 인증에 실패했습니다.")
    return resp.json()


async def _get_toss_user_key(access_token: str) -> str:
    """Toss accessToken → userKey 조회."""
    import httpx

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{TOSS_API_BASE}/api-partner/v1/apps-in-toss/user/login-me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        logger.error("토스 유저 정보 조회 실패: %s %s", resp.status_code, resp.text)
        raise HTTPException(401, detail="토스 유저 정보를 가져올 수 없습니다.")

    data = resp.json()

    # 응답이 암호화된 경우 복호화 시도
    if "encryptedData" in data and settings.toss_decryption_key:
        data = _decrypt_toss_user_data(data["encryptedData"])

    user_key = data.get("userKey") or data.get("user_key")
    if not user_key:
        logger.error("토스 응답에 userKey 없음: %s", list(data.keys()))
        raise HTTPException(500, detail="토스 유저 식별 실패")
    return user_key


def _decrypt_toss_user_data(encrypted_data: str) -> dict:
    """AES-256-GCM으로 암호화된 토스 유저 데이터 복호화."""
    import base64
    import json
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = base64.b64decode(settings.toss_decryption_key)
    aad = settings.toss_decryption_aad.encode() if settings.toss_decryption_aad else None

    raw = base64.b64decode(encrypted_data)
    # 첫 12바이트: nonce(IV), 나머지: ciphertext + tag
    nonce, ciphertext = raw[:12], raw[12:]

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
    return json.loads(plaintext)


@router.post("/toss-login", response_model=TossLoginOut)
async def toss_login(
    body: TossLoginBody,
    db: AsyncSession = Depends(get_db),
):
    """토스 앱인토스 로그인.

    1. authorizationCode → Toss API에서 accessToken 교환
    2. accessToken으로 userKey 조회
    3. firebase_uid = "toss:{userKey}" 로 유저 조회/생성
    4. Firebase Custom Token 발급 → 프론트에서 signInWithCustomToken()
    """
    # 1. 코드 → 토큰 교환
    token_data = await _exchange_toss_code(body.authorization_code)
    access_token = token_data.get("accessToken") or token_data.get("access_token")
    if not access_token:
        raise HTTPException(500, detail="토스 토큰 응답에 accessToken 없음")

    # 2. userKey 조회
    user_key = await _get_toss_user_key(access_token)
    firebase_uid = f"toss:{user_key}"

    # 3. 유저 조회 (기존 유저인지 확인)
    result = await db.execute(select(User).where(User.firebase_uid == firebase_uid))
    existing_user = result.scalar_one_or_none()
    is_new = existing_user is None

    if not is_new:
        # 기존 유저 — 활동 시간 갱신
        existing_user.last_active = datetime.now(timezone.utc)
        await db.flush()

    # 4. Firebase Custom Token 발급
    try:
        import firebase_admin.auth as fb_auth
        custom_token = fb_auth.create_custom_token(firebase_uid)
        if isinstance(custom_token, bytes):
            custom_token = custom_token.decode("utf-8")
    except Exception as e:
        logger.error("Firebase Custom Token 생성 실패: %s", e)
        raise HTTPException(500, detail="인증 토큰 생성에 실패했습니다.")

    return TossLoginOut(
        firebase_custom_token=custom_token,
        is_new_user=is_new,
        user_id=str(existing_user.id) if existing_user else None,
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

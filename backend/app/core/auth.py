"""
Firebase JWT 인증 미들웨어.

프로덕션: firebase_admin.auth.verify_id_token() 사용
개발/테스트: DISABLE_AUTH=true 환경변수 또는 X-Dev-UID 헤더로 바이패스 가능
"""
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.models.user import User, UserPreference
from backend.app.core.database import AsyncSessionLocal, get_db
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# DAU 등 '하루' 경계는 한국시간 자정 기준 (admin.py / funnel.py와 동일)
KST = timezone(timedelta(hours=9))

# .env의 DISABLE_AUTH=true를 pydantic_settings를 통해 읽음 (os.getenv는 shell 환경변수만 봄)
_disable_auth_raw = settings.disable_auth or os.getenv("DISABLE_AUTH", "false").lower() == "true"

# ENVIRONMENT=production 이면 DISABLE_AUTH를 강제로 false
_environment = os.getenv("ENVIRONMENT", "development").lower()
if _disable_auth_raw and _environment == "production":
    logger.critical(
        "🚨 DISABLE_AUTH=true detected in PRODUCTION environment — "
        "forcing auth back on. Set DISABLE_AUTH=false in production!"
    )
    raise RuntimeError("DISABLE_AUTH=true is not allowed in production")
else:
    DISABLE_AUTH = _disable_auth_raw

if DISABLE_AUTH:
    logger.warning("⚠️  DISABLE_AUTH=true: Firebase 토큰 검증이 비활성화됩니다. 개발 환경에서만 사용하세요.")


def _verify_firebase_token(token: str) -> Optional[dict]:
    """
    Firebase ID Token 검증 → {"uid": str, "email": str|None} 반환.

    DISABLE_AUTH=true: 서명 검증 없이 JWT 페이로드만 디코딩 (개발용)
    프로덕션: firebase_admin.auth.verify_id_token() 사용
    """
    if DISABLE_AUTH:
        # 개발 모드: 서명 검증 없이 JWT payload에서 UID 추출
        try:
            import base64, json
            parts = token.split('.')
            if len(parts) < 2:
                return None
            payload_b64 = parts[1]
            # Base64 패딩 보정
            payload_b64 += '=' * (4 - len(payload_b64) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            # Firebase ID Token: 'user_id' 또는 'sub' 필드에 UID
            uid = payload.get('user_id') or payload.get('sub')
            return {"uid": uid, "email": payload.get("email")} if uid else None
        except Exception as e:
            logger.warning("DISABLE_AUTH JWT 디코드 실패: %s", e)
            return None

    # 프로덕션: 실제 Firebase Admin SDK 검증
    try:
        import firebase_admin.auth as fb_auth
        decoded = fb_auth.verify_id_token(token)
        return {"uid": decoded["uid"], "email": decoded.get("email")}
    except ImportError:
        logger.warning("firebase_admin SDK 없음 - auth 비활성")
        return None
    except Exception as e:
        logger.warning("Firebase 토큰 검증 실패: %s", e)
        return None


async def _get_or_create_user(firebase_uid: str, db: AsyncSession, email: Optional[str] = None) -> User:
    """firebase_uid로 User 조회, 없으면 생성."""
    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    user = result.scalar_one_or_none()

    if not user:
        # DISABLE_AUTH 개발 환경에서 "dev-admin" UID는 자동으로 admin 역할 부여
        role = "admin" if (DISABLE_AUTH and firebase_uid == "dev-admin") else "user"
        nickname = "개발자어드민" if firebase_uid == "dev-admin" else None
        # display_name 자동 설정: email 앞부분 또는 토스 사용자
        if nickname:
            default_display = nickname
        elif email:
            default_display = email.split("@")[0]
        elif firebase_uid.startswith("toss:"):
            default_display = "토스 사용자"
        else:
            default_display = None
        user = User(firebase_uid=firebase_uid, plan="free", role=role, nickname=nickname, email=email, display_name=default_display)
        db.add(user)
        await db.flush()

        # 기본 preferences 생성
        pref = UserPreference(user_id=user.id)
        db.add(pref)
        await db.flush()

        # 퍼널 계측: 가입 이벤트 (모든 인증 경로의 신규 유저 생성 지점)
        # 신규 유저는 생성 즉시 last_active가 '오늘'로 박혀서 get_current_user의 first_visit_today
        # 게이트를 통과 못 하므로, 오늘 활동(daily_active)도 여기서 함께 적재한다(오늘 DAU에 잡히게).
        from backend.app.services.funnel import log_funnel_event, EV_SIGNUP, EV_DAILY_ACTIVE
        await log_funnel_event(db, EV_SIGNUP, user.id, props={"role": role})
        await log_funnel_event(db, EV_DAILY_ACTIVE, user.id, once_per_day=True)
        await db.flush()
    elif email and not user.email:
        # 기존 사용자인데 email이 없으면 업데이트
        user.email = email
        await db.flush()

    return user


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_dev_uid: Optional[str] = Header(None, alias="X-Dev-UID"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI Dependency: 현재 인증된 User 반환.

    우선순위:
    1. DISABLE_AUTH=true → X-Dev-UID 헤더 사용 (개발용)
    2. Authorization: Bearer <token> → Firebase 검증
    """
    firebase_uid: Optional[str] = None
    firebase_email: Optional[str] = None

    if DISABLE_AUTH and x_dev_uid:
        firebase_uid = x_dev_uid
    elif authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        token_info = _verify_firebase_token(token)
        if token_info:
            firebase_uid = token_info["uid"]
            firebase_email = token_info.get("email")

    if not firebase_uid:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    user = await _get_or_create_user(firebase_uid, db, email=firebase_email)

    # last_active 갱신 (1시간 이상 경과 시만 업데이트 — DB 부하 최소화)
    # sqlite 등 일부 백엔드는 timezone-naive datetime을 돌려주므로, aware now와 빼기 전에 UTC aware로 보정(naive-aware 혼합 TypeError 방지).
    now = datetime.now(timezone.utc)
    last_active = user.last_active
    if last_active is not None and last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    # DAU는 last_active(1시간 스로틀)가 아니라 일자별 활동 로그로 센다.
    # 1시간 스로틀 때문에 자정 직후 재방문이 전날 last_active로 남아 DAU에서 새던 문제가 있었다.
    # 그래서 '오늘(KST) 첫 인증요청'에 daily_active 이벤트를 하루 1건만 적재하고, admin DAU는 그걸 센다.
    # 첫 접속 판정은 last_active를 갱신하기 '전' 값으로 한다(갱신하면 항상 오늘이라 판정 불가).
    today_kst = now.astimezone(KST).date()
    first_visit_today = last_active is None or last_active.astimezone(KST).date() < today_kst

    if not last_active or (now - last_active) > timedelta(hours=1):
        user.last_active = now
        await db.flush()

    if first_visit_today:
        # once_per_day=True로 한 번 더 가드 — 동시요청 경쟁이나 판정 오차로 인한 중복 적재 방지.
        # 계측 실패가 인증 자체를 깨뜨리면 안 되므로 log_funnel_event가 예외를 삼킨다.
        from backend.app.services.funnel import log_funnel_event, EV_DAILY_ACTIVE
        await log_funnel_event(db, EV_DAILY_ACTIVE, user.id, once_per_day=True)
        await db.flush()

    return user


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_dev_uid: Optional[str] = Header(None, alias="X-Dev-UID"),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """인증 선택적 - 없으면 None 반환."""
    try:
        return await get_current_user(authorization, x_dev_uid, db)
    except HTTPException:
        return None


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """관리자 권한 확인 dependency."""
    if current_user.role != "admin":
        raise HTTPException(403, detail="관리자만 접근 가능합니다.")
    return current_user


_PLAN_ORDER = {"free": 0, "pro": 1, "pro_plus": 2}


def plan_required(min_plan: str):
    """
    FastAPI Dependency factory: 최소 플랜 요구.

    예시:
        @router.get("/history")
        async def history(user: User = Depends(plan_required("pro"))):
    """
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        user_level = _PLAN_ORDER.get(current_user.plan.lower(), 0)
        required_level = _PLAN_ORDER.get(min_plan.lower(), 0)
        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PLAN_REQUIRED",
                    "required": min_plan,
                    "current": current_user.plan,
                    "message": f"이 기능은 {min_plan.upper()} 이상 플랜이 필요합니다.",
                    "upgrade_url": "/upgrade",
                },
            )
        return current_user
    return _check

"""
/r/{code} 공개 리다이렉트 라우터 (인증 불필요)
"""
import hashlib
from fastapi import APIRouter, Depends, BackgroundTasks, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.auth import get_db

router = APIRouter(tags=["links"])


async def _log_click(
    link_id,
    ip_hash: str,
    user_agent: str | None,
    referer: str | None,
):
    """Fire-and-forget: 클릭 로그 저장."""
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.models.short_link import LinkClick

    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                click = LinkClick(
                    link_id=link_id,
                    ip_hash=ip_hash,
                    user_agent=user_agent,
                    referer=referer,
                )
                db.add(click)
    except Exception:
        pass


@router.get("/r/{code}")
async def redirect_short_link(
    code: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Short link redirect with click logging."""
    from backend.app.models.short_link import ShortLink
    from datetime import datetime, timezone

    # Redis cache check first
    try:
        import json as _json
        from backend.app.core.redis import get_redis
        redis = get_redis()
        cached = await redis.get(f"sl:{code}")
        if cached:
            raw = cached.decode() if isinstance(cached, bytes) else cached
            try:
                data = _json.loads(raw)
                target_url = data["url"]
                link_id = data.get("link_id")
            except (ValueError, KeyError):
                # 이전 형식 (URL 문자열만 저장) 호환
                target_url = raw
                link_id = None
            # 캐시 히트에서도 클릭 로그 기록
            if link_id:
                ip = request.client.host if request.client else ""
                ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
                background_tasks.add_task(
                    _log_click,
                    link_id=link_id,
                    ip_hash=ip_hash,
                    user_agent=request.headers.get("user-agent"),
                    referer=request.headers.get("referer"),
                )
            return RedirectResponse(url=target_url, status_code=302)
    except Exception:
        pass

    # DB lookup
    result = await db.execute(
        select(ShortLink).where(ShortLink.code == code, ShortLink.is_active == True)
    )
    link = result.scalar_one_or_none()
    if not link:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Link not found")

    # Check expiry
    if link.expires_at and link.expires_at < datetime.now(timezone.utc):
        from fastapi import HTTPException
        raise HTTPException(status_code=410, detail="Link expired")

    # Build final URL with UTM params
    target = link.target_url
    utm_params = []
    if link.utm_source:
        utm_params.append(f"utm_source={link.utm_source}")
    if link.utm_medium:
        utm_params.append(f"utm_medium={link.utm_medium}")
    if link.utm_campaign:
        utm_params.append(f"utm_campaign={link.utm_campaign}")
    if utm_params:
        separator = "&" if "?" in target else "?"
        target = f"{target}{separator}{'&'.join(utm_params)}"

    # Cache in Redis (5 min TTL) — link_id 포함하여 캐시 히트에서도 클릭 로그 가능
    try:
        import json as _json
        from backend.app.core.redis import get_redis
        redis = get_redis()
        await redis.set(f"sl:{code}", _json.dumps({"url": target, "link_id": str(link.id)}), ex=300)
    except Exception:
        pass

    # Log click in background
    ip = request.client.host if request.client else ""
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
    background_tasks.add_task(
        _log_click,
        link_id=link.id,
        ip_hash=ip_hash,
        user_agent=request.headers.get("user-agent"),
        referer=request.headers.get("referer"),
    )

    return RedirectResponse(url=target, status_code=302)

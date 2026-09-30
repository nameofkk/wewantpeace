"""
/newsletter/* 뉴스레터 수신거부 + 아카이브 + 통계 + 샘플 API (인증 불필요)

GET  /newsletter/unsubscribe?token=xxx  -- 마스킹된 이메일 + 확인 UI 데이터
POST /newsletter/unsubscribe            -- 수신거부 실행
GET  /newsletter/archive                -- 발송된 뉴스레터 목록 (public)
GET  /newsletter/archive/{log_id}       -- 특정 뉴스레터 HTML (public)
GET  /newsletter/stats                  -- 구독자 수 (public)
GET  /newsletter/sample?lang=kr|us      -- 샘플 뉴스레터 HTML (public)
GET  /newsletter/weekly/{week}?lang=     -- 주간 브리핑 웹판 (public, 개인 칸 없음)
GET  /newsletter/weekly/{week}/feedback  -- 메일의 "유용했어요/별로예요" 기록
GET/POST /newsletter/lang?t=&k=&lang=    -- 메일의 언어 바꾸기 (GET 은 확인 화면, POST 가 저장)
"""

import hmac
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.auth import get_db
from backend.app.core.config import settings
from backend.app.core.limiter import limiter
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
@limiter.limit("10/minute")
async def unsubscribe_info(
    request: Request,
    response: Response,
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
@limiter.limit("10/minute")
async def unsubscribe_execute(
    response: Response,
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
async def newsletter_sample(
    lang: str = Query("kr", regex="^(kr|us)$"),
    refresh: int = Query(0),
):
    """샘플 뉴스레터 HTML 반환 (공개, Redis 24h 캐시). ?refresh=1 로 캐시 갱신."""
    import chevron
    import json as _json
    import os

    redis = get_redis()
    cache_key = f"newsletter:sample:{lang}"
    if not refresh:
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


# ── 주간 브리핑 (2026-09-30) ───────────────────────────────────────────────

_WEEK_RE = r"^\d{4}-W\d{2}$"


def _simple_page(title: str, body: str, lang: str = "en") -> HTMLResponse:
    html = (
        f"<!doctype html><html lang='{lang}'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title></head>"
        "<body style=\"margin:0;background:#EEF0F3;font-family:-apple-system,'Apple SD Gothic Neo','Malgun Gothic',"
        "Segoe UI,Arial,sans-serif;color:#0F172A;\"><div style='max-width:480px;margin:60px auto;background:#fff;"
        f"border-radius:14px;padding:28px 24px;'>{body}</div></body></html>"
    )
    return HTMLResponse(content=html)


@router.get("/weekly/{week_key}")
@limiter.limit("60/minute")
async def weekly_web(request: Request, response: Response, week_key: str,
                     lang: str = Query("en", pattern="^(en|ko)$"), db: AsyncSession = Depends(get_db)):
    """주간 브리핑 웹판 — 메일의 '브라우저로 보기'·다른 언어판 링크가 여기로 온다."""
    import re as _re
    from backend.app.models.weekly_edition import WeeklyEdition
    from worker.weekly.render import render_email

    if week_key == "latest":
        row = (await db.execute(select(WeeklyEdition).order_by(WeeklyEdition.created_at.desc()).limit(1))).scalar_one_or_none()
    elif _re.match(_WEEK_RE, week_key):
        row = (await db.execute(select(WeeklyEdition).where(WeeklyEdition.week_key == week_key))).scalar_one_or_none()
    else:
        row = None
    if row is None:
        raise HTTPException(404, detail="Edition not found")
    mail = render_email(row.data, lang)
    return HTMLResponse(content=mail["html"])


@router.get("/weekly/{week_key}/feedback")
@limiter.limit("30/minute")
async def weekly_feedback(request: Request, response: Response, week_key: str,
                          v: str = Query(..., pattern="^(good|bad)$"),
                          lang: str = Query("en", pattern="^(en|ko)$"),
                          t: str = Query("", max_length=40), db: AsyncSession = Depends(get_db)):
    """메일의 '유용했어요/별로예요'. 받는 사람 토큰 앞 12자로 한 표만 (마지막 표가 남는다).

    메일 보안 스캐너가 링크를 전부 열어 보는 경우가 있어 같은 토큰의 두 표가 몇 초 안에 들어오면
    분석할 때 걸러야 한다 — 그래서 시각과 함께 AppEvent 로도 남긴다.
    """
    import re as _re
    from backend.app.models.app_event import AppEvent

    if not _re.match(_WEEK_RE, week_key):
        raise HTTPException(404)
    rid = _re.sub(r"[^0-9a-zA-Z]", "", t)[:12]
    db.add(AppEvent(name="weekly_feedback", props={"week": week_key, "v": v, "lang": lang, "rid": rid}, platform="email"))
    try:
        if rid:
            await get_redis().hset(f"weekly:fb:{week_key}", rid, v)
    except Exception:
        pass
    await db.flush()
    if lang == "ko":
        return _simple_page("고마워요", "<h2 style='margin:0 0 8px;'>의견 고마워요</h2><p style='color:#5B6472;line-height:1.6;'>"
                            "다음 호를 만들 때 참고할게요.</p><p><a href='https://www.wewantpeace.live/?ref=weekly'>WeWantPeace 열기</a></p>", "ko")
    return _simple_page("Thanks", "<h2 style='margin:0 0 8px;'>Thanks for the feedback</h2><p style='color:#5B6472;line-height:1.6;'>"
                        "It helps us shape the next issue.</p><p><a href='https://www.wewantpeace.live/?ref=weekly'>Open WeWantPeace</a></p>")


async def _set_lang(db: AsyncSession, t: str, k: str, lang: str) -> bool:
    from backend.app.models.brief_subscriber import BriefSubscriber
    from backend.app.models.user import UserPreference

    if k == "subscriber":
        sub = (await db.execute(select(BriefSubscriber).where(BriefSubscriber.token == t))).scalar_one_or_none()
        if not sub:
            return False
        sub.lang = lang
        return True
    user = await _find_user_by_token(t, db)
    if not user:
        return False
    pref = (await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))).scalar_one_or_none()
    if pref is None:
        db.add(UserPreference(user_id=user.id, language=lang))
    else:
        pref.language = lang
    try:
        # 회원 설정의 언어는 기본값(ko)이라 믿을 수 없어서, 직접 고른 사람을 따로 기억한다 (worker/weekly/send.py)
        await get_redis().sadd("weekly:lang_chosen", str(user.id))
    except Exception:
        pass
    return True


@router.get("/lang")
@limiter.limit("20/minute")
async def weekly_lang_confirm(request: Request, response: Response,
                              t: str = Query(..., min_length=10, max_length=64),
                              k: str = Query("user", pattern="^(user|subscriber)$"),
                              lang: str = Query(..., pattern="^(en|ko)$")):
    """확인 화면만 — 메일 보안 스캐너가 링크를 미리 열어도 설정이 바뀌지 않게 저장은 POST 로."""
    import html as _h
    label = "앞으로 한국어판으로 받기" if lang == "ko" else "Send me the English edition from now on"
    head = "한국어판으로 바꿀까요?" if lang == "ko" else "Switch to the English edition?"
    body = (f"<h2 style='margin:0 0 16px;'>{head}</h2>"
            f"<form method='post' action='/newsletter/lang?t={_h.escape(t)}&k={_h.escape(k)}&lang={lang}'>"
            "<button type='submit' style='width:100%;padding:14px;border:0;border-radius:10px;background:#0B1220;"
            f"color:#fff;font-size:16px;font-weight:700;cursor:pointer;'>{label}</button></form>")
    return _simple_page(head, body, lang)


@router.post("/lang")
@limiter.limit("10/minute")
async def weekly_lang_set(request: Request, response: Response,
                          t: str = Query(..., min_length=10, max_length=64),
                          k: str = Query("user", pattern="^(user|subscriber)$"),
                          lang: str = Query(..., pattern="^(en|ko)$"),
                          db: AsyncSession = Depends(get_db)):
    ok = await _set_lang(db, t, k, lang)
    if not ok:
        raise HTTPException(404, detail="Invalid or expired link")
    await db.flush()
    if lang == "ko":
        return _simple_page("바꿨어요", "<h2 style='margin:0 0 8px;'>다음 호부터 한국어로 보내드려요</h2>", "ko")
    return _simple_page("Done", "<h2 style='margin:0 0 8px;'>You'll get the English edition from the next issue</h2>")

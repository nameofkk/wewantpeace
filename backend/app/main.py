import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from backend.app.core.limiter import limiter
from backend.app.core.config import settings
from backend.app.core.redis import close_redis
from backend.app.core.sentry import init_sentry
from backend.app.core.firebase_init import init_firebase
from backend.app.routers import issues, trending, tension, me
from backend.app.routers import auth as auth_router, community, admin as admin_router, subscriptions, terms as terms_router
from backend.app.routers import store_subscriptions
from backend.app.routers import dodopayments as dodopayments_router
from backend.app.routers import links as links_router
from backend.app.routers import public as public_router
import structlog

logger = structlog.get_logger()

# Sentry 초기화 (앱 시작 전)
init_sentry()

# Rate limiter (IP 기반, 기본 200req/분 전체 적용) (H-1)
# limiter instance imported from backend.app.core.limiter


async def _bootstrap_admin():
    """어드민 자동 부트스트랩.

    1) ADMIN_EMAILS 환경변수가 있으면 해당 이메일을 admin 승격
    2) DB에 admin이 한 명도 없으면 가장 먼저 가입한 유저를 admin 승격
    """
    from backend.app.core.database import AsyncSessionLocal
    from sqlalchemy import select, func
    from backend.app.models.user import User

    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                # 1) ADMIN_EMAILS 환경변수 처리
                admin_emails_str = os.environ.get("ADMIN_EMAILS", "")
                if admin_emails_str:
                    emails = [e.strip() for e in admin_emails_str.split(",") if e.strip()]
                    if emails:
                        result = await db.execute(
                            select(User).where(User.email.in_(emails), User.role != "admin")
                        )
                        for u in result.scalars().all():
                            u.role = "admin"
                            logger.info("admin 승격 (env): %s", u.email)

                # 2) admin이 아무도 없으면 첫 번째 유저 자동 승격
                admin_count = (await db.execute(
                    select(func.count()).select_from(User).where(User.role == "admin")
                )).scalar() or 0

                if admin_count == 0:
                    first_user = (await db.execute(
                        select(User).where(User.status == "active").order_by(User.created_at.asc()).limit(1)
                    )).scalar_one_or_none()
                    if first_user:
                        first_user.role = "admin"
                        logger.info("admin 자동 부트스트랩: %s (첫 번째 유저)", first_user.email)
    except Exception as e:
        logger.error("bootstrap_admin 실패: %s", e)


async def _cleanup_stale_data():
    """기존 데이터 정리: kscore=0 재계산 + 오래된 데이터 삭제."""
    import traceback
    from datetime import datetime, timezone, timedelta
    from backend.app.core.database import AsyncSessionLocal
    from sqlalchemy import select, text

    logger.info("cleanup_stale_data 시작...")
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                from backend.app.models.issue_cluster import IssueCluster
                from worker.processor.trending_engine import _calc_kscore

                # 1. kscore=0.0인 클러스터 재계산
                result = await db.execute(
                    select(IssueCluster).where(IssueCluster.kscore == 0.0)
                )
                zero_clusters = result.scalars().all()
                for c in zero_clusters:
                    c.kscore, _ = _calc_kscore(
                        event_count=c.event_count,
                        is_spike=False,  # v7: spike 비활성화
                        confidence=c.confidence,
                        severity=c.severity,
                        independent_sources=c.independent_sources or 1,
                        source_tiers=c.source_tiers or [],
                    )
                logger.info("kscore=0 재계산: %d개", len(zero_clusters))

                # 2. 7일 초과 클러스터 + 연관 데이터 삭제
                old_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                r1 = await db.execute(text(
                    "DELETE FROM cluster_events WHERE cluster_id IN "
                    "(SELECT id FROM issue_clusters WHERE last_event_at < :cutoff)"
                ), {"cutoff": old_cutoff})
                r2 = await db.execute(text(
                    "DELETE FROM issue_clusters WHERE last_event_at < :cutoff"
                ), {"cutoff": old_cutoff})
                logger.info("오래된 데이터 삭제: cluster_events %d건, issue_clusters %d건",
                            r1.rowcount, r2.rowcount)
    except Exception as e:
        logger.error("cleanup_stale_data 실패: %s\n%s", e, traceback.format_exc())


async def _startup_tension_calculation():
    """백엔드 기동 시 긴장도·트렌딩 즉시 계산 (백그라운드).

    Celery beat 스케줄 대기 없이 배포 직후 데이터가 비어있는 구간을 방지.
    FastAPI 프로세스 안에서 실행되므로 이벤트 루프 문제가 없다.
    """
    import traceback

    from backend.app.core.database import AsyncSessionLocal

    # 데이터 정리 먼저 실행
    await _cleanup_stale_data()

    logger.info("startup_tension_calculation 시작...")
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                from worker.processor.tension_calculator import calculate_all_tensions
                results = await calculate_all_tensions(db)
                logger.info("startup_tension_calculation 완료: %d개국", len(results))
    except Exception as e:
        logger.error("startup_tension_calculation 실패: %s\n%s", e, traceback.format_exc())

    logger.info("startup_trending_calculation 시작...")
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                from worker.processor.trending_engine import calculate_global_trending
                results = await calculate_global_trending(db)
                logger.info("startup_trending_calculation 완료: %d개", len(results))
    except Exception as e:
        logger.error("startup_trending_calculation 실패: %s\n%s", e, traceback.format_exc())


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    os.makedirs(settings.upload_dir, exist_ok=True)
    init_firebase()
    logger.info("WeWantPeace API starting up", env=settings.debug)

    # 어드민 이메일 자동 승격 (ADMIN_EMAILS 환경변수)
    await _bootstrap_admin()

    # 누락 인덱스 자동 생성
    try:
        from backend.app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as db:
            await db.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_trending_kw_scope_nkw_calcat "
                "ON trending_keywords (scope, normalized_kw, calculated_at)"
            ))
            await db.commit()
            logger.info("인덱스 ix_trending_kw_scope_nkw_calcat 확인/생성 완료")
    except Exception as e:
        logger.warning("인덱스 생성 실패 (무시): %s", e)

    # 긴장도·트렌딩 계산을 백그라운드로 실행 (서버 즉시 시작, 완료 추적)
    app.state.tension_ready = False

    async def _bg_tension():
        try:
            await asyncio.wait_for(_startup_tension_calculation(), timeout=120)
        except asyncio.TimeoutError:
            logger.warning("startup_tension_calculation 타임아웃(120초)")
        finally:
            app.state.tension_ready = True
            logger.info("tension_ready = True")

    asyncio.create_task(_bg_tension())

    yield
    await close_redis()
    logger.info("WeWantPeace API shut down")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="세계정세 알림·지도·긴장도 지수 API",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# Rate limit 설정 (SlowAPIMiddleware: 모든 라우트에 default_limits 자동 적용)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

logger.info("CORS allowed_origins: %s", settings.allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.toss\.im",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Dev-UID", "X-Requested-With"],
)


import os as _os
if _os.path.isdir("media"):
    app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(issues.router)
app.include_router(trending.router)
app.include_router(tension.router)
app.include_router(me.router)
app.include_router(auth_router.router)
app.include_router(community.router)
app.include_router(admin_router.router)
app.include_router(subscriptions.router)
app.include_router(store_subscriptions.router)
app.include_router(dodopayments_router.router)
app.include_router(terms_router.router)
app.include_router(links_router.router)
app.include_router(public_router.router)


@app.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request):
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    return {"message": "WeWantPeace API", "docs": "/docs"}

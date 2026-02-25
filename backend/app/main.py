import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from backend.app.core.config import settings
from backend.app.core.redis import close_redis
from backend.app.core.sentry import init_sentry
from backend.app.core.firebase_init import init_firebase
from backend.app.routers import issues, trending, tension, me
from backend.app.routers import auth as auth_router, community, admin as admin_router, subscriptions, terms as terms_router
import structlog

logger = structlog.get_logger()

# Sentry 초기화 (앱 시작 전)
init_sentry()

# Rate limiter (IP 기반, 기본 200req/분 전체 적용) (H-1)
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


async def _startup_tension_calculation():
    """백엔드 기동 시 긴장도·트렌딩 즉시 계산 (백그라운드).

    Celery beat 스케줄 대기 없이 배포 직후 데이터가 비어있는 구간을 방지.
    FastAPI 프로세스 안에서 실행되므로 이벤트 루프 문제가 없다.
    """
    import asyncio
    await asyncio.sleep(5)  # DB 연결 안정화 대기

    from backend.app.core.database import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                from worker.processor.tension_calculator import calculate_all_tensions
                results = await calculate_all_tensions(db)
                logger.info("startup_tension_calculation 완료: %d개국", len(results))
    except Exception as e:
        logger.error("startup_tension_calculation 실패: %s", e)

    try:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                from worker.processor.trending_engine import calculate_global_trending
                results = await calculate_global_trending(db)
                logger.info("startup_trending_calculation 완료: %d개", len(results))
    except Exception as e:
        logger.error("startup_trending_calculation 실패: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    os.makedirs(settings.upload_dir, exist_ok=True)
    init_firebase()
    logger.info("WeWantPeace API starting up", env=settings.debug)

    # 백그라운드로 긴장도·트렌딩 즉시 계산 (배포 후 빈 데이터 방지)
    task = asyncio.create_task(_startup_tension_calculation())

    yield

    task.cancel()
    await close_redis()
    logger.info("WeWantPeace API shut down")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="세계정세 알림·지도·긴장도 지수 API",
    lifespan=lifespan,
)

# Rate limit 설정 (SlowAPIMiddleware: 모든 라우트에 default_limits 자동 적용)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/media", StaticFiles(directory="media"), name="media")

app.include_router(issues.router)
app.include_router(trending.router)
app.include_router(tension.router)
app.include_router(me.router)
app.include_router(auth_router.router)
app.include_router(community.router)
app.include_router(admin_router.router)
app.include_router(subscriptions.router)
app.include_router(terms_router.router)


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

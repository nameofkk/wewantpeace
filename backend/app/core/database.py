import json
import uuid as _uuid
from sqlalchemy import TypeDecorator, Text, String
from sqlalchemy.dialects.postgresql import ARRAY as PgArray, UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.config import settings


class StringArray(TypeDecorator):
    """Cross-database string array: native ARRAY on PostgreSQL, JSON text on SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgArray(String))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return "[]"
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return json.loads(value)


class UUIDArray(TypeDecorator):
    """Cross-database UUID array: native ARRAY(UUID) on PostgreSQL, JSON text on SQLite."""
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgArray(PgUUID(as_uuid=True)))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return "[]"
        return json.dumps([str(v) for v in value])

    def process_result_value(self, value, dialect):
        if dialect.name == "postgresql":
            return value
        if value is None:
            return []
        if isinstance(value, list):
            return [v if isinstance(v, _uuid.UUID) else _uuid.UUID(v) for v in value]
        return [_uuid.UUID(v) for v in json.loads(value)]


import os as _os

_is_sqlite = settings.database_url.startswith("sqlite")
_is_worker = bool(_os.environ.get("CELERY_WORKER"))

# ── DB 연결 전략 ──────────────────────────────────────────────────────────────
# Supabase session mode(5432) 사용.
# asyncpg + Supavisor transaction mode(6543)는 DEALLOCATE ALL 미실행으로
# DuplicatePreparedStatementError 발생 → session mode가 유일하게 안정적인 선택.
#
# 연결 수 설계 (Supabase 한도 15개):
#   backend:  uvicorn 1worker × (pool_size=1 + overflow=3) = 최대 4개
#   worker:   celery -c 4 × pool_size=1                   = 4개
#   일반 idle: 1 + 4 = 5개  /  최대 burst: 4+4=8개
#   배포 오버랩: old(4) + new(4) + worker(4) = 12개 << 15 ✓

if _is_sqlite:
    _engine_kwargs: dict = {}
elif _is_worker:
    # Worker: child당 1개 연결 (concurrency=4 → 총 4개)
    _engine_kwargs = {
        "pool_size": 1,
        "max_overflow": 0,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_timeout": 30,
    }
else:
    # Backend: uvicorn 1 worker, 최대 4개 연결 (burst 허용)
    _engine_kwargs = {
        "pool_size": 1,
        "max_overflow": 3,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_timeout": 30,
    }

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    **_engine_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Canonical DB session dependency — 모든 라우터에서 이 함수를 사용할 것."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

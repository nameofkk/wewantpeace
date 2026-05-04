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
# Supabase transaction mode(6543) + PgBouncer 사용.
# - prepared_statement_cache_size=0: DuplicatePreparedStatementError 방지
#   (transaction mode에서 connection이 재사용되면 prepared statement 충돌 발생)
# - PgBouncer가 connection을 효율적으로 풀링 → session mode 20개 한도 문제 해소
#
# 연결 수 설계:
#   backend + worker가 N개 연결을 요청해도 PgBouncer가 소수의 실제 PG 연결로 처리
#   → Supabase 내부 18개 + 앱 코드 수십 개 요청 모두 문제없음

_txn_mode_connect_args: dict = {}
if not _is_sqlite:
    # asyncpg: prepared statement 캐시 비활성화 (transaction mode pooler 필수)
    # statement_cache_size=0 → asyncpg 클라이언트 측 캐시 비활성화
    # (server_settings가 아닌 asyncpg connect() 파라미터)
    _txn_mode_connect_args = {"statement_cache_size": 0}

if _is_sqlite:
    _engine_kwargs: dict = {}
elif _is_worker:
    # Worker: child당 1개 연결 (concurrency=4)
    _engine_kwargs = {
        "pool_size": 1,
        "max_overflow": 2,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_timeout": 30,
        "connect_args": _txn_mode_connect_args,
    }
else:
    # Backend: uvicorn 1 worker
    _engine_kwargs = {
        "pool_size": 2,
        "max_overflow": 4,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "pool_timeout": 30,
        "connect_args": _txn_mode_connect_args,
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

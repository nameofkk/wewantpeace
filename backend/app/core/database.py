import json
import uuid as _uuid
from sqlalchemy import TypeDecorator, Text, String
from sqlalchemy.dialects.postgresql import ARRAY as PgArray, UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
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


def _to_transaction_mode_url(raw: str) -> str:
    """URL을 Supabase transaction mode(6543, Supavisor)로 강제 변환."""
    url = raw
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    url = url.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543")
    return url


# ── DB 연결 전략 ──────────────────────────────────────────────────────────────
# Supabase transaction mode(6543 / Supavisor):
#   - 연결 수 제한 없음 (Supavisor가 DB 연결 풀링 전담)
#   - backend: NullPool → 요청마다 Supavisor에 연결·해제 (prepared stmt 충돌 원천 차단)
#   - worker:  pool_size=1 per child + statement_cache_size=0
#
# NullPool + transaction mode 조합으로:
#   - EMAXCONNSESSION (15개 한도) 영구 해소
#   - DuplicatePreparedStatementError 영구 해소
#   - QueuePool timeout 영구 해소
_raw_url = _os.environ.get("DATABASE_URL", "") or settings.database_url
if not _is_sqlite and "pooler.supabase.com" in _raw_url:
    _db_url = _to_transaction_mode_url(_raw_url)
else:
    _db_url = settings.database_url

# PgBouncer/Supavisor transaction mode: prepared statement 캐시 비활성화 필수
# json_serializer/deserializer: setup_asyncpg_json_codec 건너뜀 (prepared stmt 사용 방지)
_pgbouncer_kwargs: dict = {
    "json_serializer": json.dumps,
    "json_deserializer": json.loads,
    "connect_args": {"statement_cache_size": 0},
}

if _is_sqlite:
    _engine_kwargs: dict = {}
elif _is_worker:
    # Worker: pool_size=1 per child (concurrency=4 → 총 4개 연결)
    _engine_kwargs = {
        "pool_size": 1,
        "max_overflow": 0,
        "pool_pre_ping": False,
        "pool_recycle": 1800,
        "pool_timeout": 30,
        **_pgbouncer_kwargs,
    }
else:
    # Backend: NullPool → SQLAlchemy 로컬 풀 없음, Supavisor가 전담
    # 요청마다 새 연결 → prepared stmt 충돌 원천 차단
    _engine_kwargs = {
        "poolclass": NullPool,
        **_pgbouncer_kwargs,
    }

engine = create_async_engine(
    _db_url,
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

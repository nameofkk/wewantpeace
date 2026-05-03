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

_is_sqlite = settings.database_url.startswith("sqlite")
# Worker는 transaction mode(포트 6543)를 사용 — PgBouncer 연결 제한 없음.
# config.py의 fix_db_url_scheme이 6543→5432 자동 전환하므로,
# worker에서는 원본 DATABASE_URL 환경변수를 직접 읽어 6543 포트로 전환.
# prepared_statement_cache_size=0 필수 (PgBouncer transaction mode는 prepared statements 미지원)
import os as _os
_is_worker = bool(_os.environ.get("CELERY_WORKER"))
_pool_size = 1 if _is_worker else 5
_max_overflow = 0 if _is_worker else 5

def _build_worker_db_url() -> str:
    """Worker용 transaction mode URL 생성 (포트 6543).
    WORKER_DATABASE_URL 환경변수 → 없으면 DATABASE_URL의 5432 → 6543 자동 전환."""
    explicit = _os.environ.get("WORKER_DATABASE_URL", "")
    if explicit:
        url = explicit
    else:
        # 원본 DATABASE_URL에서 session mode(5432) → transaction mode(6543) 전환
        url = _os.environ.get("DATABASE_URL", settings.database_url)
        url = url.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543")
    # postgres:// → postgresql+asyncpg:// 변환 (6543 포트 유지)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

if _is_worker:
    _db_url = _build_worker_db_url()
else:
    _db_url = settings.database_url

_is_transaction_mode = "pooler.supabase.com:6543" in _db_url

_connect_args: dict = {}
if not _is_sqlite:
    _connect_args["server_settings"] = {"statement_timeout": "120000"}
    if _is_transaction_mode:
        # PgBouncer transaction mode: prepared statements 비활성화 필수
        _connect_args["prepared_statement_cache_size"] = 0
        _connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    _db_url,
    echo=settings.debug,
    **({} if _is_sqlite else {
        "pool_size": _pool_size, "max_overflow": _max_overflow,
        "pool_pre_ping": True, "pool_recycle": 1800, "pool_timeout": 30,
        "connect_args": _connect_args,
    }),
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

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
# ── DB 연결 전략 ──────────────────────────────────────────────────────────────
# Supabase session mode(5432): 전체 15개 연결 한도 → backend+worker 합산 초과 위험
# Supabase transaction mode(6543): PgBouncer 경유, 연결 한도 없음 → backend+worker 모두 사용
#
# 따라서 backend와 worker 모두 transaction mode를 사용한다.
# config.py의 fix_db_url_scheme이 6543→5432로 강제 변환하므로,
# 여기서는 환경변수 원본을 직접 읽어 6543으로 전환한다.
# prepared_statement_cache_size=0 필수 (PgBouncer는 prepared statements 미지원)
import os as _os
_is_worker = bool(_os.environ.get("CELERY_WORKER"))
_pool_size = 1 if _is_worker else 5
_max_overflow = 0 if _is_worker else 5


def _to_transaction_mode_url(raw: str) -> str:
    """URL을 Supabase transaction mode(6543, PgBouncer)로 강제 변환."""
    url = raw
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    # session mode → transaction mode
    url = url.replace("pooler.supabase.com:5432", "pooler.supabase.com:6543")
    return url


# 원본 DATABASE_URL에서 직접 변환 (config.py의 5432 강제변환 우회)
_raw_url = _os.environ.get("DATABASE_URL", "") or settings.database_url
if not _is_sqlite and "pooler.supabase.com" in _raw_url:
    _db_url = _to_transaction_mode_url(_raw_url)
else:
    _db_url = settings.database_url

_is_transaction_mode = "pooler.supabase.com:6543" in _db_url

_connect_args: dict = {}
if not _is_sqlite:
    if _is_transaction_mode:
        # PgBouncer transaction mode: prepared statements 비활성화 필수
        _connect_args["prepared_statement_cache_size"] = 0
        _connect_args["statement_cache_size"] = 0
    # statement_timeout 제거: transaction mode에서 prepared stmt cache 없어 쿼리 느려짐
    # /tension/mine 같은 복잡한 쿼리가 120s 초과 → 쿼리 최적화 전까지 timeout 없음

_engine_kwargs: dict = {}
if not _is_sqlite:
    _engine_kwargs = {
        "pool_size": _pool_size, "max_overflow": _max_overflow,
        "pool_pre_ping": not _is_transaction_mode,  # transaction mode에서 pre_ping 비활성화
        "pool_recycle": 1800, "pool_timeout": 30,
        "connect_args": _connect_args,
    }
    if _is_transaction_mode:
        # PgBouncer transaction mode: JSON codec 초기화 시 prepared statement 사용 방지
        # json_serializer/deserializer 명시 → setup_asyncpg_json_codec 건너뜀
        _engine_kwargs["json_serializer"] = json.dumps
        _engine_kwargs["json_deserializer"] = json.loads

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

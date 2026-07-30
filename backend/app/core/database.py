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
    # ── Supavisor transaction mode에서 prepared statement 끄기 ────────────────
    # 프로덕션 로그에서 실제로 터지던 예외:
    #   asyncpg.exceptions.InvalidSQLStatementNameError:
    #   prepared statement "__asyncpg_stmt_17d__" does not exist
    #
    # 원인: statement_cache_size는 asyncpg 자체 캐시만 끈다. SQLAlchemy asyncpg
    # 다이얼렉트는 그와 별개로 DBAPI 커넥션마다 prepared statement를 100개까지
    # 캐시한다(기본값). transaction mode 풀러에서는 트랜잭션마다 뒤쪽 PG 백엔드가
    # 바뀔 수 있어, 앞 트랜잭션에서 prepare한 statement가 다음 트랜잭션에는 없다.
    #   → prepared_statement_cache_size=0 으로 다이얼렉트 캐시까지 꺼야 한다.
    #     (SQLAlchemy 문서상 dialect 인자가 아니라 DBAPI 인자라 connect_args로 넘긴다)
    #   → prepared_statement_name_func: 이름을 매번 유일하게 만들어, 재사용된 PG
    #     백엔드에 같은 이름이 남아 있을 때의 DuplicatePreparedStatementError도 막는다.
    #
    # 워커는 NullPool이라 매번 새 커넥션을 열어 이 문제를 우연히 피해 왔고,
    # 커넥션을 재사용하는 백엔드(QueuePool)만 계속 터지고 있었다.
    _txn_mode_connect_args = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{_uuid.uuid4()}__",
    }

if _is_sqlite:
    _engine_kwargs: dict = {}
elif _is_worker:
    # ── Worker: NullPool + pgbouncer transaction mode ──────────────────────
    # pgbouncer transaction mode에서 SQLAlchemy 레벨 connection pool을 사용하면
    # fork된 자식 프로세스가 부모의 asyncpg 연결을 상속 → 이벤트 루프 불일치 +
    # DuplicatePreparedStatementError 발생.
    #
    # NullPool: 각 AsyncSessionLocal() 호출마다 새 연결, 세션 종료 시 즉시 close.
    # pgbouncer가 실제 PG 연결을 풀링하므로 연결 오버헤드 없음.
    # (Celery 워커 concurrency=4 → 최대 동시 4개 연결, pgbouncer가 관리)
    from sqlalchemy.pool import NullPool
    _engine_kwargs = {
        "poolclass": NullPool,
        "connect_args": _txn_mode_connect_args,
    }
else:
    # Backend: uvicorn 1 worker — 연결 풀 사용 (일반적인 웹 서버 패턴)
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

# ── pgbouncer transaction mode: stale prepared statement 정리 ─────────────────
# asyncpg는 statement_cache_size=0 이어도 named prepared statement를 서버 측에 생성함
# (__asyncpg_stmt_1__, __asyncpg_stmt_2__, ...).
# pgbouncer가 backend PG connection을 재사용할 때 stale statement가 남아 있으면
# DuplicatePreparedStatementError 발생.
#
# 해결: 새 연결 체크아웃 시 DEALLOCATE ALL을 simple query protocol(파라미터 없음)로 실행.
# simple query는 prepared statement를 사용하지 않으므로 stale statement에 영향받지 않음.
if not _is_sqlite:
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection, connection_record):
        """새 asyncpg 연결 시 pgbouncer backend의 stale prepared statement 정리."""
        try:
            raw_conn = dbapi_connection._connection
            # simple query protocol (파라미터 없음) → named prepared statement 생성 안 함
            dbapi_connection.await_(raw_conn.execute("DEALLOCATE ALL"))
        except Exception:
            pass  # 첫 연결이거나 DEALLOCATE 불필요한 경우 무시

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

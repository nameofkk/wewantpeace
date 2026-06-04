"""
프로덕션 스모크 테스트.
핵심 엔드포인트가 올바른 스키마로 응답하는지 확인.
실제 데이터 없이도 통과해야 함 (빈 리스트/404 허용).
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

_is_sqlite = "sqlite" in os.environ.get("DATABASE_URL", "sqlite")

from backend.app.main import app
from backend.app.core.database import Base

# 모든 모델 등록 (create_all 전에 import)
import backend.app.models  # noqa: F401
import backend.app.routers.issues as issues_router
import backend.app.routers.trending as trending_router
import backend.app.routers.tension as tension_router
import backend.app.routers.me as me_router


# ── 테스트 DB 픽스처 ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db(test_engine) -> AsyncSession:
    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest.fixture
async def client(test_db: AsyncSession):
    """스모크 테스트용 클라이언트 (비인증)."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[issues_router.get_db] = override_get_db
    app.dependency_overrides[trending_router.get_db] = override_get_db
    app.dependency_overrides[tension_router.get_db] = override_get_db
    app.dependency_overrides[me_router.get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ── /health ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_smoke_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "app" in data
    assert "version" in data


@pytest.mark.asyncio
async def test_smoke_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "WeWantPeace" in resp.json().get("message", "")


# ── /trending ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.skipif(_is_sqlite, reason="DISTINCT ON은 PostgreSQL 전용 문법")
async def test_smoke_trending_global(client):
    """/trending/global → 200, list 반환."""
    resp = await client.get("/trending/global")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
@pytest.mark.skipif(_is_sqlite, reason="DISTINCT ON은 PostgreSQL 전용 문법")
async def test_smoke_trending_global_schema(client):
    """트렌딩 아이템 스키마 검증 (데이터 있을 때)."""
    resp = await client.get("/trending/global")
    items = resp.json()
    if items:
        item = items[0]
        assert "id" in item
        assert "title" in item
        assert "severity" in item


# ── /issues ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_smoke_issues_list(client):
    """/issues → 200, list 반환."""
    resp = await client.get("/issues")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_smoke_issues_with_filters(client):
    """/issues?topic=conflict&severity_min=30 → 200."""
    resp = await client.get("/issues?topic=conflict&severity_min=30")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_smoke_issue_not_found(client):
    """/issues/{invalid_id} → 404."""
    resp = await client.get("/issues/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


# ── /tension ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_smoke_tension_history_unauthenticated(client):
    """/tension/country/UA/history → 200 (비로그인, 7d 허용)."""
    resp = await client.get("/tension/country/UA/history?range=7d")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_smoke_tension_history_30d_requires_auth(client):
    """/tension/country/UA/history?range=30d → 403 (비로그인)."""
    resp = await client.get("/tension/country/UA/history?range=30d")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "PLAN_REQUIRED"


# ── API 메타데이터 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_smoke_openapi_available(client):
    """/openapi.json → 200 (Swagger UI 기반)."""
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert "openapi" in spec
    assert "paths" in spec


@pytest.mark.asyncio
async def test_smoke_docs_available(client):
    """/docs → 200."""
    resp = await client.get("/docs")
    assert resp.status_code == 200

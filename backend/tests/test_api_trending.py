"""
/trending/* /issues/* /tension/* API 통합 테스트.
FastAPI dependency_overrides로 테스트 DB 주입.
"""
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import app
from backend.app.core.database import Base
from backend.app.models.trending_keyword import TrendingKeyword
import backend.app.routers.issues as issues_router
import backend.app.routers.trending as trending_router
import backend.app.routers.tension as tension_router


# ── 테스트 DB 세션 픽스처 ─────────────────────────────────────────────────────

@pytest.fixture(scope="module")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("PRAGMA foreign_keys=ON"))
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
async def client(test_db):
    """FastAPI 앱에 테스트 DB 주입."""
    async def override_get_db():
        yield test_db

    app.dependency_overrides[issues_router.get_db] = override_get_db
    app.dependency_overrides[trending_router.get_db] = override_get_db
    app.dependency_overrides[tension_router.get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ── /trending/global ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_global_trending_empty_returns_list(client):
    """트렌딩 데이터 없어도 200 + 빈 배열."""
    resp = await client.get("/trending/global")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_global_trending_returns_cached(client, test_db):
    """캐시된 trending_keyword 반환."""
    now = datetime.now(timezone.utc)
    kw = TrendingKeyword(
        keyword="Kyiv attack",
        normalized_kw="kyiv attack",
        kscore=3.5,
        topic="conflict",
        country_codes=["UA"],
        cluster_ids=[],
        scope="global",
        calculated_at=now,
        valid_until=now + timedelta(minutes=15),
    )
    test_db.add(kw)
    await test_db.flush()

    resp = await client.get("/trending/global")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any(item["keyword"] == "Kyiv attack" for item in data)


@pytest.mark.asyncio
async def test_trending_item_schema(client, test_db):
    """응답 필드 확인."""
    now = datetime.now(timezone.utc)
    kw = TrendingKeyword(
        keyword="Schema test",
        normalized_kw="schema test",
        kscore=2.0,
        topic="conflict",
        country_codes=["UA"],
        cluster_ids=[],
        scope="global",
        calculated_at=now,
        valid_until=now + timedelta(minutes=15),
    )
    test_db.add(kw)
    await test_db.flush()

    resp = await client.get("/trending/global")
    assert resp.status_code == 200
    items = resp.json()
    if items:
        item = items[0]
        assert "keyword" in item
        assert "kscore" in item
        assert "topic" in item
        assert "country_codes" in item
        assert "calculated_at" in item


# ── /trending/mine ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mine_trending_returns_list(client):
    resp = await client.get("/trending/mine")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ── /issues ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_issues_returns_list(client):
    resp = await client.get("/issues")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_issues_invalid_cluster_id(client):
    resp = await client.get("/issues/not-a-uuid")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_issues_not_found(client):
    resp = await client.get("/issues/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_issues_filter_by_severity(client):
    resp = await client.get("/issues?severity_min=50")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["severity"] >= 50 for item in data)


# ── /tension ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_tension_mine_returns_list(client):
    resp = await client.get("/tension/mine")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_tension_country_ua_no_data(client):
    """데이터 없으면 404."""
    resp = await client.get("/tension/country/UA")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_tension_history_returns_list(client):
    resp = await client.get("/tension/country/UA/history?range=7d")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_tension_history_invalid_range(client):
    """잘못된 range는 기본값(7d)으로 처리."""
    resp = await client.get("/tension/country/UA/history?range=invalid")
    assert resp.status_code == 200

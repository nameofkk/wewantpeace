"""
인증 미들웨어 테스트.
- 인증 없으면 401
- DISABLE_AUTH + X-Dev-UID로 우회
- get_or_create_user 동작
"""
import pytest
import os
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import app
from backend.app.core.database import Base
from backend.app.models.user import User, UserPreference
import backend.app.core.auth as auth_module
import backend.app.routers.me as me_router


# ── 테스트 DB ─────────────────────────────────────────────────────────────────

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
async def client_no_auth(test_db):
    """인증 없는 기본 클라이언트 (DISABLE_AUTH=false)."""
    original = auth_module.DISABLE_AUTH

    async def override_db():
        yield test_db

    app.dependency_overrides[me_router.get_db] = override_db
    app.dependency_overrides[auth_module.get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
    auth_module.DISABLE_AUTH = original


@pytest.fixture
async def client_dev_auth(test_db, monkeypatch):
    """DISABLE_AUTH=true + X-Dev-UID 클라이언트."""
    monkeypatch.setattr(auth_module, "DISABLE_AUTH", True)

    async def override_db():
        yield test_db

    app.dependency_overrides[me_router.get_db] = override_db
    app.dependency_overrides[auth_module.get_db] = override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


# ── 인증 없음 → 401 ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_requires_auth(client_no_auth):
    resp = await client_no_auth.get("/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_areas_requires_auth(client_no_auth):
    resp = await client_no_auth.get("/me/areas")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_preferences_requires_auth(client_no_auth):
    resp = await client_no_auth.get("/me/preferences")
    assert resp.status_code == 401


# ── 개발 모드 우회 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dev_auth_bypass_works(client_dev_auth):
    """X-Dev-UID 헤더로 인증 우회."""
    uid = f"dev-{uuid.uuid4()}"
    resp = await client_dev_auth.get("/me", headers={"X-Dev-UID": uid})
    assert resp.status_code == 200
    data = resp.json()
    assert data["firebase_uid"] == uid
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_dev_auth_creates_user_on_first_call(client_dev_auth):
    """첫 요청 시 User 자동 생성."""
    uid = f"new-{uuid.uuid4()}"
    resp = await client_dev_auth.get("/me", headers={"X-Dev-UID": uid})
    assert resp.status_code == 200
    assert resp.json()["firebase_uid"] == uid


@pytest.mark.asyncio
async def test_dev_auth_same_user_on_second_call(client_dev_auth):
    """같은 UID는 같은 User 반환."""
    uid = f"same-{uuid.uuid4()}"
    r1 = await client_dev_auth.get("/me", headers={"X-Dev-UID": uid})
    r2 = await client_dev_auth.get("/me", headers={"X-Dev-UID": uid})
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_dev_auth_without_uid_returns_401(client_dev_auth):
    """X-Dev-UID 없으면 401."""
    resp = await client_dev_auth.get("/me")
    assert resp.status_code == 401


# ── 관심지역 + 인증 통합 ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_areas_accessible_with_dev_auth(client_dev_auth):
    uid = f"area-{uuid.uuid4()}"
    resp = await client_dev_auth.get("/me/areas", headers={"X-Dev-UID": uid})
    assert resp.status_code == 200
    assert resp.json() == []

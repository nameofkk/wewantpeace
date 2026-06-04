"""
/me/areas 관심지역 API 테스트.
- Free 2개 제한
- CRUD 동작
- notify_fast/verified 플래그
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import app
from backend.app.core.database import Base
from backend.app.models.user import User, UserArea, UserPreference
import backend.app.routers.me as me_router
from backend.app.core.auth import get_current_user


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
async def free_user(test_db) -> User:
    """Free 플랜 테스트 유저."""
    user = User(firebase_uid=f"test-{uuid.uuid4()}", plan="free")
    test_db.add(user)
    await test_db.flush()  # user.id 확보
    pref = UserPreference(user_id=user.id)
    test_db.add(pref)
    await test_db.flush()
    return user


@pytest.fixture
async def pro_user(test_db) -> User:
    """Pro 플랜 테스트 유저."""
    user = User(firebase_uid=f"pro-{uuid.uuid4()}", plan="pro")
    test_db.add(user)
    await test_db.flush()  # user.id 확보
    pref = UserPreference(user_id=user.id)
    test_db.add(pref)
    await test_db.flush()
    return user


@pytest.fixture
def client_with_user(test_db, free_user):
    """free_user로 인증된 FastAPI 테스트 클라이언트."""
    async def override_db():
        yield test_db

    async def override_user():
        return free_user

    app.dependency_overrides[me_router.get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)

    class ClientCtx:
        async def __aenter__(self):
            self.client = AsyncClient(transport=transport, base_url="http://test")
            return await self.client.__aenter__()

        async def __aexit__(self, *args):
            await self.client.__aexit__(*args)
            app.dependency_overrides.clear()

    return ClientCtx()


@pytest.fixture
def pro_client(test_db, pro_user):
    """pro_user로 인증된 클라이언트."""
    async def override_db():
        yield test_db

    async def override_user():
        return pro_user

    app.dependency_overrides[me_router.get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    transport = ASGITransport(app=app)

    class ClientCtx:
        async def __aenter__(self):
            self.client = AsyncClient(transport=transport, base_url="http://test")
            return await self.client.__aenter__()

        async def __aexit__(self, *args):
            await self.client.__aexit__(*args)
            app.dependency_overrides.clear()

    return ClientCtx()


# ── 기본 CRUD ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_areas_empty(client_with_user):
    async with client_with_user as c:
        resp = await c.get("/me/areas")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_create_area(client_with_user):
    async with client_with_user as c:
        resp = await c.post("/me/areas", json={
            "area_type": "country",
            "country_code": "KR",
            "label": "대한민국",
            "notify_verified": True,
            "notify_fast": False,
        })
    assert resp.status_code == 201
    data = resp.json()
    assert data["country_code"] == "KR"
    assert data["notify_verified"] is True
    assert data["notify_fast"] is False


@pytest.mark.asyncio
async def test_create_two_areas_free(client_with_user):
    """Free 유저 2개까지 가능."""
    async with client_with_user as c:
        r1 = await c.post("/me/areas", json={"country_code": "UA", "label": "우크라이나"})
        r2 = await c.post("/me/areas", json={"country_code": "PS", "label": "팔레스타인"})
    assert r1.status_code == 201
    assert r2.status_code == 201


@pytest.mark.asyncio
async def test_free_area_limit_enforced(client_with_user):
    """Free 유저 3번째 추가 시 403."""
    async with client_with_user as c:
        await c.post("/me/areas", json={"country_code": "UA"})
        await c.post("/me/areas", json={"country_code": "PS"})
        r3 = await c.post("/me/areas", json={"country_code": "IL"})

    assert r3.status_code == 403
    error = r3.json()
    assert error["detail"]["code"] == "FREE_AREA_LIMIT"


@pytest.mark.asyncio
async def test_pro_user_no_area_limit(pro_client):
    """Pro 유저는 2개 초과 가능."""
    async with pro_client as c:
        for code in ["UA", "PS", "IL"]:
            r = await c.post("/me/areas", json={"country_code": code})
            assert r.status_code == 201


@pytest.mark.asyncio
async def test_delete_area(client_with_user):
    async with client_with_user as c:
        create = await c.post("/me/areas", json={"country_code": "KR"})
        area_id = create.json()["id"]
        delete_r = await c.delete(f"/me/areas/{area_id}")
        list_r = await c.get("/me/areas")

    assert delete_r.status_code == 204
    assert not any(a["id"] == area_id for a in list_r.json())


@pytest.mark.asyncio
async def test_delete_nonexistent_area_404(client_with_user):
    async with client_with_user as c:
        resp = await c.delete("/me/areas/99999")
    assert resp.status_code == 404


# ── notify 플래그 ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notify_verified_default_true(client_with_user):
    async with client_with_user as c:
        resp = await c.post("/me/areas", json={"country_code": "KR"})
    assert resp.json()["notify_verified"] is True


@pytest.mark.asyncio
async def test_notify_fast_default_false(client_with_user):
    async with client_with_user as c:
        resp = await c.post("/me/areas", json={"country_code": "KR"})
    assert resp.json()["notify_fast"] is False

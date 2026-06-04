"""
plan_required 의존성 테스트.
- Free 유저 → Pro 전용 엔드포인트 403
- Pro 유저 → 200
- Pro+ 필요 → Pro는 403, Pro+는 200
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from backend.app.main import app
from backend.app.core.database import Base
from backend.app.models.user import User, UserPreference
from backend.app.models.tension_index import TensionIndex  # noqa: F401 — Base에 등록
from backend.app.core.auth import get_current_user, get_optional_user, get_db, _PLAN_ORDER, plan_required


# ── 테스트 DB ─────────────────────────────────────────────────────────────────

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


async def _make_user(db, plan: str) -> User:
    user = User(firebase_uid=f"uid-{uuid.uuid4()}", plan=plan)
    db.add(user)
    await db.flush()
    pref = UserPreference(user_id=user.id)
    db.add(pref)
    await db.flush()
    return user


def _client_with_user(test_db: AsyncSession, user: User):
    async def override_db():
        yield test_db

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_optional_user] = override_user

    class Ctx:
        async def __aenter__(self):
            self._c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
            return await self._c.__aenter__()
        async def __aexit__(self, *a):
            await self._c.__aexit__(*a)
            app.dependency_overrides.clear()

    return Ctx()


# ── plan_required 단위 테스트 ─────────────────────────────────────────────────

def test_plan_order():
    assert _PLAN_ORDER["free"] < _PLAN_ORDER["pro"]
    assert _PLAN_ORDER["pro"] < _PLAN_ORDER["pro_plus"]


@pytest.mark.asyncio
async def test_free_user_blocked_from_pro_endpoint(test_db):
    """Free 유저 → /tension/country/UA/history?range=30d → 403."""
    user = await _make_user(test_db, "free")
    async with _client_with_user(test_db, user) as c:
        resp = await c.get("/tension/country/UA/history?range=30d")
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "PLAN_REQUIRED"


@pytest.mark.asyncio
async def test_free_user_allowed_7d(test_db):
    """Free 유저 → /tension/country/UA/history?range=7d → 200 (빈 리스트)."""
    user = await _make_user(test_db, "free")
    async with _client_with_user(test_db, user) as c:
        resp = await c.get("/tension/country/UA/history?range=7d")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_pro_user_allowed_30d(test_db):
    """Pro 유저 → /tension/country/UA/history?range=30d → 200."""
    user = await _make_user(test_db, "pro")
    async with _client_with_user(test_db, user) as c:
        resp = await c.get("/tension/country/UA/history?range=30d")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_pro_user_blocked_from_90d(test_db):
    """Pro 유저 → /tension/country/UA/history?range=90d → 403 (Pro+ 필요)."""
    user = await _make_user(test_db, "pro")
    async with _client_with_user(test_db, user) as c:
        resp = await c.get("/tension/country/UA/history?range=90d")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_pro_plus_allowed_90d(test_db):
    """Pro+ 유저 → /tension/country/UA/history?range=90d → 200."""
    user = await _make_user(test_db, "pro_plus")
    async with _client_with_user(test_db, user) as c:
        resp = await c.get("/tension/country/UA/history?range=90d")
    assert resp.status_code == 200

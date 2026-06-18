"""
/livez 라이브니스 프로브 테스트.

라이브니스는 "프로세스가 살아있냐"만 본다:
  - 항상 200 + {"status": "alive"}
  - 의존성(DB·Redis)을 전혀 건드리지 않는다 (그게 흔들려도 프로세스는 안 죽임)
  - 레이트리밋에서 제외된다 (@limiter.exempt) — 트래픽 폭주 중에도 프로브가 막히면 안 됨
"""
import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.core.limiter import limiter


@pytest.mark.asyncio
async def test_livez_returns_200_alive():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/livez")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_livez_not_rate_limited():
    """디폴트 리밋(200/분)을 훌쩍 넘겨 때려도 429가 절대 안 나와야 한다."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        codes = set()
        for _ in range(250):  # 디폴트 200/분을 초과
            resp = await c.get("/livez")
            codes.add(resp.status_code)
    assert codes == {200}, f"라이브니스에 레이트리밋이 걸렸다: {codes}"


@pytest.mark.asyncio
async def test_livez_carries_no_ratelimit_headers():
    """exempt 라우트라 slowapi의 X-RateLimit-* 헤더가 붙지 않는다."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/livez")
    rl_headers = [h for h in resp.headers if h.lower().startswith("x-ratelimit")]
    assert rl_headers == [], f"exempt인데 리밋 헤더가 붙었다: {rl_headers}"


@pytest.mark.asyncio
async def test_livez_independent_of_db_and_redis(monkeypatch):
    """DB·Redis가 죽어도(연결이 터져도) 라이브니스는 200을 준다."""
    import backend.app.core.database as db_mod
    import backend.app.core.redis as redis_mod

    def _boom(*a, **k):
        raise RuntimeError("dependency down")

    # 의존성을 일부러 터뜨려도 /livez는 영향받지 않아야 함
    monkeypatch.setattr(db_mod, "AsyncSessionLocal", _boom)
    monkeypatch.setattr(redis_mod, "get_redis", _boom)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/livez")
    assert resp.status_code == 200
    assert resp.json() == {"status": "alive"}


def test_livez_registered_as_exempt():
    """slowapi 리미터의 exempt 목록에 라이브니스 핸들러가 등록돼 있다."""
    assert "liveness" in {name.split(".")[-1] for name in limiter._exempt_routes}

"""
/status 읽기전용 엔드포인트 테스트.

- Redis에 저장된 beat 심장박동 / 태스크 마지막 실행 / 19종 헬스 스냅샷을
  그대로 읽어서 반환하는지
- 관리자 권한 게이트가 동작하는지
- checker._persist_results가 스냅샷을 올바르게 저장하는지
"""
import json
from datetime import datetime, timezone, timedelta

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.routers import status as status_router
from backend.app.core.auth import require_admin


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@pytest_asyncio.fixture
async def client_and_redis(monkeypatch):
    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

    # status 라우터와 checker가 같은 fakeredis를 보도록 패치
    monkeypatch.setattr(status_router, "get_redis", lambda: fake)

    # 관리자 인증 통과 (실제 유저 객체 불필요 — 라우터는 admin 객체를 안 씀)
    app.dependency_overrides[require_admin] = lambda: object()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c, fake

    app.dependency_overrides.clear()
    await fake.aclose()


@pytest.mark.asyncio
async def test_status_all_healthy(client_and_redis):
    c, fake = client_and_redis
    now = datetime.now(timezone.utc)

    # beat 심장박동: 1분 전 (TTL 살아있음)
    await fake.set("beat:heartbeat", _iso(now - timedelta(minutes=1)), ex=600)
    # 태스크 마지막 실행
    await fake.set("celery:last_run:collect_rss", _iso(now - timedelta(minutes=3)), ex=3600)
    await fake.set("celery:last_run:calculate_tension", _iso(now - timedelta(minutes=2)), ex=3600)
    # 19종 헬스 스냅샷 (전부 ok)
    snapshot = {
        "generated_at": _iso(now - timedelta(minutes=10)),
        "overall": "ok",
        "total": 19, "ok": 19, "warning": 0, "critical": 0,
        "checks": [{"check_name": "redis_health", "status": "ok", "message": "Redis OK", "issues": []}],
    }
    await fake.set("health:last_results", json.dumps(snapshot))

    resp = await c.get("/status")
    assert resp.status_code == 200
    data = resp.json()

    assert data["overall"] == "ok"
    assert data["beat"]["alive"] is True
    assert data["beat"]["age_seconds"] is not None and data["beat"]["age_seconds"] < 120
    assert data["beat"]["ttl_seconds"] is not None

    assert set(data["tasks"]) == {"collect_rss", "calculate_tension"}
    assert data["tasks"]["collect_rss"]["stale"] is False
    assert data["tasks"]["collect_rss"]["age_seconds"] is not None

    assert data["health"]["overall"] == "ok"
    assert data["health"]["age_seconds"] is not None
    assert data["health"]["checks"][0]["check_name"] == "redis_health"


@pytest.mark.asyncio
async def test_status_beat_dead_is_down(client_and_redis):
    c, fake = client_and_redis
    # beat 키 자체가 없음 → Beat 멈춤 → overall down
    await fake.set("health:last_results", json.dumps({"overall": "ok", "generated_at": None, "checks": []}))

    resp = await c.get("/status")
    data = resp.json()
    assert resp.status_code == 200
    assert data["beat"]["alive"] is False
    assert data["beat"]["last_heartbeat"] is None
    assert data["overall"] == "down"


@pytest.mark.asyncio
async def test_status_critical_health_is_down(client_and_redis):
    c, fake = client_and_redis
    now = datetime.now(timezone.utc)
    await fake.set("beat:heartbeat", _iso(now), ex=600)
    snapshot = {
        "generated_at": _iso(now),
        "overall": "critical", "total": 19, "ok": 17, "warning": 1, "critical": 1,
        "checks": [{"check_name": "openai_status", "status": "critical", "message": "API 다운",
                    "issues": [{"severity": "critical", "message": "rate limited",
                                "auto_fix_available": True, "fix_action": "reset_openai_rate_limit"}]}],
    }
    await fake.set("health:last_results", json.dumps(snapshot))

    resp = await c.get("/status")
    data = resp.json()
    assert data["overall"] == "down"
    assert data["health"]["critical"] == 1
    assert data["health"]["checks"][0]["issues"][0]["fix_action"] == "reset_openai_rate_limit"


@pytest.mark.asyncio
async def test_status_missing_snapshot_is_degraded(client_and_redis):
    c, fake = client_and_redis
    now = datetime.now(timezone.utc)
    await fake.set("beat:heartbeat", _iso(now), ex=600)
    # health 스냅샷 없음 → health=None → degraded
    resp = await c.get("/status")
    data = resp.json()
    assert data["health"] is None
    assert data["overall"] == "degraded"


@pytest.mark.asyncio
async def test_status_requires_admin():
    # 인증 오버라이드 없이 호출 → 401/403
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/status")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_persist_results_writes_snapshot(monkeypatch):
    """checker.run_all_checks가 호출하는 _persist_results 단위 검증."""
    from worker.health import checker

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(checker, "get_redis", lambda: fake)

    results = [
        checker.HealthCheckResult(check_name="redis_health", status="ok", message="ok"),
        checker.HealthCheckResult(
            check_name="openai_status", status="critical", message="down",
            issues=[checker.HealthIssue(check_name="openai_status", severity="critical",
                                        message="rate limited", auto_fix_available=True,
                                        fix_action="reset_openai_rate_limit")],
        ),
        checker.HealthCheckResult(check_name="rss_freshness", status="warning", message="지연"),
    ]
    await checker._persist_results(results)

    raw = await fake.get(checker.HEALTH_SNAPSHOT_KEY)
    assert raw is not None
    payload = json.loads(raw)
    assert payload["total"] == 3
    assert payload["ok"] == 1 and payload["warning"] == 1 and payload["critical"] == 1
    assert payload["overall"] == "critical"
    assert payload["checks"][1]["issues"][0]["fix_action"] == "reset_openai_rate_limit"
    # 스냅샷 TTL이 설정돼 있어야 함 (영구 키 방지)
    assert await fake.ttl(checker.HEALTH_SNAPSHOT_KEY) > 0

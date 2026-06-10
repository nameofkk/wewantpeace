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

    # 가용성 = 마지막 수집(collect_rss, 3분 전)이 임계값 안 → available True
    assert data["available"] is True
    assert data["collection"]["available"] is True
    assert data["collection"]["source_task"] == "collect_rss"
    assert data["collection"]["age_seconds"] < 15 * 60
    # 배포 커밋 SHA 블록 존재 (값은 환경변수 유무에 따라 None일 수 있음)
    assert "version" in data
    assert "commit" in data["version"] and "commit_short" in data["version"]


@pytest.mark.asyncio
async def test_status_beat_dead_is_down(client_and_redis):
    c, fake = client_and_redis
    now = datetime.now(timezone.utc)
    # 수집은 살아있게(2분 전) 두고 beat 키만 없앤다 → down 원인을 beat로 고립
    await fake.set("celery:last_run:collect_rss", _iso(now - timedelta(minutes=2)), ex=3600)
    # beat 키 자체가 없음 → Beat 멈춤 → overall down
    await fake.set("health:last_results", json.dumps({"overall": "ok", "generated_at": None, "checks": []}))

    resp = await c.get("/status")
    data = resp.json()
    assert resp.status_code == 200
    assert data["beat"]["alive"] is False
    assert data["beat"]["last_heartbeat"] is None
    assert data["available"] is True  # 수집은 살아있음
    assert data["overall"] == "down"  # 그래도 beat 죽어서 down


@pytest.mark.asyncio
async def test_status_critical_health_is_down(client_and_redis):
    c, fake = client_and_redis
    now = datetime.now(timezone.utc)
    await fake.set("beat:heartbeat", _iso(now), ex=600)
    await fake.set("celery:last_run:collect_rss", _iso(now - timedelta(minutes=2)), ex=3600)
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
    await fake.set("celery:last_run:collect_rss", _iso(now - timedelta(minutes=2)), ex=3600)
    # health 스냅샷 없음 → health=None → degraded (단, 수집·beat는 살아있음)
    resp = await c.get("/status")
    data = resp.json()
    assert data["available"] is True
    assert data["health"] is None
    assert data["overall"] == "degraded"


@pytest.mark.asyncio
async def test_status_stale_collection_is_down(client_and_redis):
    """beat·health가 멀쩡해도 마지막 수집이 N분 넘게 끊기면 down (가용성 재정의 핵심)."""
    c, fake = client_and_redis
    now = datetime.now(timezone.utc)
    # beat 살아있고
    await fake.set("beat:heartbeat", _iso(now), ex=600)
    # 수집 태스크는 20분 전이 마지막 (임계값 15분 초과) → 수집 끊김
    await fake.set("celery:last_run:collect_rss", _iso(now - timedelta(minutes=20)), ex=3600)
    await fake.set("celery:last_run:collect_telegram_channels", _iso(now - timedelta(minutes=22)), ex=3600)
    # 헬스 스냅샷은 전부 ok
    await fake.set("health:last_results", json.dumps({
        "overall": "ok", "generated_at": _iso(now), "total": 19, "ok": 19,
        "warning": 0, "critical": 0, "checks": [],
    }))

    resp = await c.get("/status")
    data = resp.json()
    assert resp.status_code == 200
    assert data["beat"]["alive"] is True       # beat는 살아있는데
    assert data["available"] is False           # 수집이 끊겨서 available False
    assert data["collection"]["age_seconds"] >= 15 * 60
    assert data["collection"]["source_task"] == "collect_rss"  # 둘 중 더 최근(20분) 게 기준
    assert data["overall"] == "down"            # 응답은 200이어도 down


@pytest.mark.asyncio
async def test_status_no_collection_record_is_down(client_and_redis):
    """수집 기록 자체가 없으면 available False, collection 필드는 None으로."""
    c, fake = client_and_redis
    now = datetime.now(timezone.utc)
    await fake.set("beat:heartbeat", _iso(now), ex=600)
    # collect_* 키 전혀 없음, tension 같은 비수집 태스크만 있음
    await fake.set("celery:last_run:calculate_tension", _iso(now - timedelta(minutes=1)), ex=3600)

    resp = await c.get("/status")
    data = resp.json()
    assert data["available"] is False
    assert data["collection"]["last_collection"] is None
    assert data["collection"]["source_task"] is None
    assert data["overall"] == "down"


@pytest.mark.asyncio
async def test_status_reports_commit_sha(client_and_redis, monkeypatch):
    """배포 커밋 SHA가 설정돼 있으면 version 블록에 그대로 노출된다."""
    from backend.app.routers import status as status_router

    monkeypatch.setattr(status_router.settings, "railway_git_commit_sha", "abcdef1234567890", raising=False)
    monkeypatch.setattr(status_router.settings, "git_commit_sha", "", raising=False)

    now = datetime.now(timezone.utc)
    await fake_set_healthy(fake=client_and_redis[1], now=now)

    resp = await client_and_redis[0].get("/status")
    data = resp.json()
    assert data["version"]["commit"] == "abcdef1234567890"
    assert data["version"]["commit_short"] == "abcdef1"


async def fake_set_healthy(fake, now):
    """건강한 기본 상태(beat·수집·헬스 ok)를 fakeredis에 깔아주는 헬퍼."""
    await fake.set("beat:heartbeat", _iso(now), ex=600)
    await fake.set("celery:last_run:collect_rss", _iso(now - timedelta(minutes=2)), ex=3600)
    await fake.set("health:last_results", json.dumps({
        "overall": "ok", "generated_at": _iso(now), "total": 19, "ok": 19,
        "warning": 0, "critical": 0, "checks": [],
    }))


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

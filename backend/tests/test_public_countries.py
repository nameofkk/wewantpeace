"""/public/countries — country_code 가 NULL 인 클러스터가 있어도 500 이 나지 않는다.

프로덕션에서 NULL 이 섞여 sorted() 가 TypeError 를 내며 매 요청 500 이었다.
"""
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient, ASGITransport

from backend.app.main import app
from backend.app.models.issue_cluster import IssueCluster
import backend.app.routers.public as public_router


def _cluster(cc):
    now = datetime.now(timezone.utc)
    return IssueCluster(
        cluster_key=f"{cc or '0000'}:conflict", geohash5="00000", topic="conflict", country_code=cc,
        title=f"t {cc}", event_count=1, severity=50, confidence=0.7, kscore=1.0, source_tiers=["B"],
        independent_sources=1, first_event_at=now, last_event_at=now, window_start=now, window_end=now,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_countries_ignores_null_country(db):
    db.add_all([_cluster("UA"), _cluster(None), _cluster("IR")])
    await db.flush()

    async def override_get_db():
        yield db

    app.dependency_overrides[public_router.get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get("/public/countries")
    finally:
        app.dependency_overrides.clear()

    assert res.status_code == 200
    assert res.json()["data"] == ["IR", "UA"]

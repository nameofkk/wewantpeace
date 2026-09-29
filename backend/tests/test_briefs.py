"""나라별 주간 브리프 구독 — 이중 확인·동의·수신거부·가입 여부 비노출."""
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend.app.main import app
from backend.app.models.brief_subscriber import BriefSubscriber
import backend.app.routers.briefs as briefs_router


@pytest.fixture
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[briefs_router.get_db] = override_get_db
    # 레이트리밋은 테스트 사이에서 공유되므로 끈다
    briefs_router.limiter.enabled = False
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        briefs_router.limiter.enabled = True
        app.dependency_overrides.clear()


async def _sub(db, email):
    return (await db.execute(select(BriefSubscriber).where(BriefSubscriber.email == email))).scalar_one_or_none()


@pytest.mark.asyncio
async def test_subscribe_confirm_unsubscribe(client, db):
    with patch.object(briefs_router, "send_email", return_value=True) as mail:
        r = await client.post("/briefs/subscribe", json={
            "email": " Reader@Example.com ", "countries": ["ua", "IR", "UA", "xx1"], "lang": "en", "consent": True,
            "source": "threads",
        })
    assert r.status_code == 200 and r.json() == {"status": "check_email"}
    sub = await _sub(db, "reader@example.com")
    assert sub.status == "pending"
    assert sub.countries == ["UA", "IR"]
    assert sub.consent_at is not None
    to, subject, html = mail.call_args.args[:3]
    assert to == "reader@example.com"
    assert f"/brief/confirm?token={sub.token}" in html

    r = await client.get("/briefs/confirm", params={"token": sub.token})
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert r.json()["email"] == "re***@example.com"

    r = await client.post("/briefs/unsubscribe", json={"token": sub.token})
    assert r.json() == {"status": "unsubscribed"}
    assert (await _sub(db, "reader@example.com")).status == "unsubscribed"


@pytest.mark.asyncio
async def test_consent_and_validation(client):
    with patch.object(briefs_router, "send_email", return_value=True) as mail:
        r = await client.post("/briefs/subscribe", json={"email": "a@b.co", "countries": ["UA"], "consent": False})
        assert r.status_code == 422
        r = await client.post("/briefs/subscribe", json={"email": "not-an-email", "countries": ["UA"], "consent": True})
        assert r.status_code == 422
        r = await client.post("/briefs/subscribe", json={"email": "a@b.co", "countries": ["123"], "consent": True})
        assert r.status_code == 422
    mail.assert_not_called()


@pytest.mark.asyncio
async def test_existing_active_gets_same_response_without_mail(client, db):
    with patch.object(briefs_router, "send_email", return_value=True):
        await client.post("/briefs/subscribe", json={"email": "x@y.org", "countries": ["IL"], "consent": True})
    sub = await _sub(db, "x@y.org")
    await client.get("/briefs/confirm", params={"token": sub.token})

    with patch.object(briefs_router, "send_email", return_value=True) as mail:
        r = await client.post("/briefs/subscribe", json={"email": "x@y.org", "countries": ["IL", "PS"], "consent": True})
    assert r.json() == {"status": "check_email"}
    mail.assert_not_called()
    assert (await _sub(db, "x@y.org")).countries == ["IL", "PS"]


@pytest.mark.asyncio
async def test_bad_token(client):
    r = await client.get("/briefs/confirm", params={"token": "nope-nope-nope"})
    assert r.status_code == 404

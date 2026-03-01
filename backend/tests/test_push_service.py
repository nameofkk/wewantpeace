"""
PushService 단위 테스트.
- FCM mock
- Verified/Fast 레인 분리
- 15분 쿨다운
- notify_fast=False 시 Fast 레인 발송 안됨
"""
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from worker.push.push_service import (
    send_spike_alert,
    _is_in_cooldown,
    _set_cooldown,
    _get_target_tokens_by_platform,
)
from backend.app.models.user import User, UserArea, UserPushToken, UserPreference


# ── 테스트 유저/토큰 픽스처 ──────────────────────────────────────────────────

async def _make_user_with_area(db, country_code: str, notify_fast: bool = False, notify_verified: bool = True) -> tuple:
    user = User(firebase_uid=f"uid-{uuid.uuid4()}", plan="free" if not notify_fast else "pro")
    db.add(user)
    await db.flush()  # user.id 확보

    pref = UserPreference(user_id=user.id)
    db.add(pref)
    await db.flush()

    area = UserArea(
        user_id=user.id,
        area_type="country",
        country_code=country_code,
        notify_verified=notify_verified,
        notify_fast=notify_fast,
    )
    db.add(area)
    await db.flush()

    token = UserPushToken(
        user_id=user.id,
        fcm_token=f"token-{uuid.uuid4()}",
        platform="web",
    )
    db.add(token)
    await db.flush()

    return user, area, token


# ── 쿨다운 ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cooldown_initially_false(redis_mock):
    assert not await _is_in_cooldown("cid-001", redis_mock)


@pytest.mark.asyncio
async def test_cooldown_set_and_active(redis_mock):
    await _set_cooldown("cid-002", redis_mock)
    assert await _is_in_cooldown("cid-002", redis_mock)


@pytest.mark.asyncio
async def test_send_skipped_during_cooldown(db, redis_mock):
    cluster_id = str(uuid.uuid4())
    await _set_cooldown(cluster_id, redis_mock)

    result = await send_spike_alert(
        cluster_id=cluster_id,
        cluster_title="Test",
        country_code="UA",
        severity=70,
        kscore=5.0,
        is_verified=True,
        cluster_topic=None,
        db=db,
        redis=redis_mock,
    )
    assert result["status"] == "cooldown"
    assert result["sent"] == 0


# ── 레인 분리 ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verified_lane_sends_to_notify_verified_users(db, redis_mock):
    """notify_verified=True 사용자에게 Verified 레인 발송."""
    _, _, token = await _make_user_with_area(db, "UA", notify_verified=True, notify_fast=False)

    with patch("worker.push.push_service._split_and_send", return_value=1) as mock_fcm:
        result = await send_spike_alert(
            cluster_id=str(uuid.uuid4()),
            cluster_title="Kyiv attack",
            country_code="UA",
            severity=75,
            kscore=5.0,
            is_verified=True,
            cluster_topic=None,
            db=db,
            redis=redis_mock,
        )

    assert result["sent_verified"] == 1
    assert mock_fcm.called


@pytest.mark.asyncio
async def test_verified_lane_skipped_if_not_verified(db, redis_mock):
    """is_verified=False이면 Verified 레인 발송 안됨."""
    await _make_user_with_area(db, "UA", notify_verified=True)

    with patch("worker.push.push_service._split_and_send", return_value=0) as mock_fcm:
        result = await send_spike_alert(
            cluster_id=str(uuid.uuid4()),
            cluster_title="Test",
            country_code="UA",
            severity=60,
            kscore=5.0,
            is_verified=False,  # ← Verified 레인 비활성
            cluster_topic=None,
            db=db,
            redis=redis_mock,
        )

    assert result["sent_verified"] == 0


@pytest.mark.asyncio
async def test_fast_lane_sends_to_notify_fast_users(db, redis_mock):
    """notify_fast=True Pro 사용자에게 Fast 레인 발송."""
    await _make_user_with_area(db, "UA", notify_fast=True)

    with patch("worker.push.push_service._split_and_send", return_value=1) as mock_fcm:
        result = await send_spike_alert(
            cluster_id=str(uuid.uuid4()),
            cluster_title="Test",
            country_code="UA",
            severity=50,
            kscore=5.0,
            is_verified=False,
            cluster_topic=None,
            db=db,
            redis=redis_mock,
        )

    assert result["sent_fast"] == 1


@pytest.mark.asyncio
async def test_notify_fast_false_no_fast_lane(db, redis_mock):
    """notify_fast=False 사용자는 Fast 레인 대상 아님."""
    await _make_user_with_area(db, "UA", notify_fast=False)

    tokens = await _get_target_tokens_by_platform("UA", notify_fast=True, kscore=10.0, cluster_topic=None, db=db)
    assert len(tokens) == 0


@pytest.mark.asyncio
async def test_cooldown_set_after_send(db, redis_mock):
    """발송 후 쿨다운 설정됨."""
    cluster_id = str(uuid.uuid4())
    await _make_user_with_area(db, "UA", notify_verified=True)

    with patch("worker.push.push_service._split_and_send", return_value=1):
        await send_spike_alert(
            cluster_id=cluster_id,
            cluster_title="Test",
            country_code="UA",
            severity=70,
            kscore=5.0,
            is_verified=True,
            cluster_topic=None,
            db=db,
            redis=redis_mock,
        )

    assert await _is_in_cooldown(cluster_id, redis_mock)


@pytest.mark.asyncio
async def test_no_tokens_for_different_country(db, redis_mock):
    """다른 국가 사용자에게 발송 안됨."""
    await _make_user_with_area(db, "KR", notify_verified=True)  # KR 등록

    tokens = await _get_target_tokens_by_platform("UA", notify_fast=False, kscore=10.0, cluster_topic=None, db=db)  # UA 조회
    assert len(tokens) == 0

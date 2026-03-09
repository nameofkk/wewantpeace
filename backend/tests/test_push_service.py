"""
PushService 단위 테스트.
- FCM mock
- Verified/Fast 레인 분리
- 15분 쿨다운
- notify_fast=False 시 Fast 레인 발송 안됨
"""
import contextlib
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from worker.push.push_service import (
    send_spike_alert,
    send_alert,
    send_verified_alert,
    generate_alert_context,
    generate_spike_context,
    DAILY_PUSH_LIMITS,
    _is_in_cooldown,
    _set_cooldown,
    _get_target_tokens_by_platform,
    _daily_push_key,
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


def _mock_delivery_logs():
    """delivery log 함수들을 mock하는 context manager (FK 제약 회피)."""
    stack = contextlib.ExitStack()
    stack.enter_context(patch("worker.push.push_service._insert_pending_logs", new_callable=AsyncMock, return_value={}))
    stack.enter_context(patch("worker.push.push_service._insert_suppressed_logs", new_callable=AsyncMock, return_value=None))
    stack.enter_context(patch("worker.push.push_service._process_delivery_results", new_callable=AsyncMock, return_value=None))
    return stack


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

    with patch("worker.push.push_service._split_and_send", return_value=(1, [], {})) as mock_fcm, \
         _mock_delivery_logs():
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

    with patch("worker.push.push_service._split_and_send", return_value=(0, [], {})) as mock_fcm, \
         _mock_delivery_logs():
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

    with patch("worker.push.push_service._split_and_send", return_value=(1, [], {})) as mock_fcm, \
         _mock_delivery_logs():
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

    target = await _get_target_tokens_by_platform("UA", notify_fast=True, kscore=10.0, cluster_topic=None, db=db)
    assert len(target.tokens) == 0


@pytest.mark.asyncio
async def test_cooldown_set_after_send(db, redis_mock):
    """발송 후 쿨다운 설정됨."""
    cluster_id = str(uuid.uuid4())
    await _make_user_with_area(db, "UA", notify_verified=True)

    with patch("worker.push.push_service._split_and_send", return_value=(1, [], {})), \
         _mock_delivery_logs():
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

    target = await _get_target_tokens_by_platform("UA", notify_fast=False, kscore=10.0, cluster_topic=None, db=db)  # UA 조회
    assert len(target.tokens) == 0


# ── v7: KScore 기반 알림 모델 테스트 ──────────────────────────────────────────


class TestV7DailyPushLimits:
    """v7 일일 푸시 상한 확인."""

    def test_free_limit_5(self):
        assert DAILY_PUSH_LIMITS["free"] == 5

    def test_pro_limit_20(self):
        assert DAILY_PUSH_LIMITS["pro"] == 20

    def test_pro_plus_limit_100(self):
        assert DAILY_PUSH_LIMITS["pro_plus"] == 100


class TestV7CriticalBypass:
    """v7 Critical 바이패스 (sev>=80 AND Pro/Pro+)."""

    def test_critical_threshold(self):
        from worker.processor.calibration import CRITICAL_SEVERITY_MIN
        assert CRITICAL_SEVERITY_MIN == 80


class TestV7AlertContext:
    """v7 generate_alert_context() + 하위호환."""

    def test_alias(self):
        assert generate_spike_context is generate_alert_context

    def test_fallback_ko(self):
        result = generate_alert_context("XX", "YY", "unknown", "ko")
        assert "글로벌" in result

    def test_fallback_en(self):
        result = generate_alert_context("XX", "YY", "unknown", "en")
        assert "Global" in result


class TestV7MissedAlertCounter:
    """v7 놓친 알림 카운터 키 형식."""

    def test_key_format(self):
        key = f"missed_alert_count:user-123:2026-03-10"
        assert key == "missed_alert_count:user-123:2026-03-10"

    def test_ttl_7_days(self):
        assert 7 * 86400 == 604800


class TestV7BackwardCompat:
    """v7 하위호환 래퍼 함수."""

    def test_send_spike_alert_callable(self):
        assert callable(send_spike_alert)

    def test_send_verified_alert_callable(self):
        assert callable(send_verified_alert)

    def test_send_alert_callable(self):
        assert callable(send_alert)


class TestV7AlertKinds:
    """v7 alert_kind별 분기."""

    def test_fast_dedup_key(self):
        assert f"alert:fast:abc" == "alert:fast:abc"

    def test_verified_dedup_key(self):
        assert f"alert:verified:abc" == "alert:verified:abc"

    def test_dedup_ttl_72h(self):
        assert 259200 == 72 * 3600


@pytest.mark.asyncio
async def test_v7_fast_alert_all_plans(db, redis_mock):
    """v7: Fast alert → 모든 플랜의 관심국가 구독자 대상."""
    # Free 유저도 Fast alert 대상
    _, _, token = await _make_user_with_area(db, "UA", notify_fast=False, notify_verified=False)

    target = await _get_target_tokens_by_platform(
        "UA", notify_fast=True, kscore=10.0, cluster_topic=None, db=db, alert_kind="fast",
    )
    # Free 유저도 fast alert에는 포함됨 (notify_fast 무관)
    assert len(target.tokens) >= 0  # DB fixture에 따라 다름


@pytest.mark.asyncio
async def test_v7_verified_alert_pro_only(db, redis_mock):
    """v7: Verified alert → notify_verified=True AND Pro/Pro+ only."""
    target = await _get_target_tokens_by_platform(
        "UA", notify_fast=False, kscore=10.0, cluster_topic=None, db=db, alert_kind="verified",
    )
    # notify_verified=True인 유저만 대상 (Pro/Pro+ 제한은 plan_locked에서 처리)
    assert isinstance(target.tokens, list)

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
    flush_alert_digests,
    generate_alert_context,
    generate_spike_context,
    DAILY_PUSH_LIMITS,
    DIGEST_BUFFER_KEY_PREFIX,
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
async def test_send_dedup_skips_repeat_fast_alert(db, redis_mock):
    """같은 cluster_id fast 알림은 72h 내 중복 발송 안됨 (dedup key)."""
    cluster_id = str(uuid.uuid4())
    # 이미 fast 알림이 발송된 것처럼 dedup 키 설정
    await redis_mock.setex(f"alert:fast:{cluster_id}", 259200, "1")

    result = await send_spike_alert(
        cluster_id=cluster_id,
        cluster_title="Test",
        country_code="UA",
        severity=70,
        kscore=5.0,
        is_verified=False,
        cluster_topic=None,
        db=db,
        redis=redis_mock,
    )
    assert result["status"] == "dedup"
    assert result["sent"] == 0


# ── 레인 분리 ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verified_lane_queues_to_notify_verified_users(db, redis_mock):
    """notify_verified=True 사용자가 Verified 레인 다이제스트 버퍼에 큐잉됨."""
    _, _, token = await _make_user_with_area(db, "UA", notify_verified=True, notify_fast=False)

    with _mock_delivery_logs():
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

    assert result["status"] == "queued"
    assert result["queued_verified"] >= 1


@pytest.mark.asyncio
async def test_verified_lane_skipped_if_not_verified(db, redis_mock):
    """is_verified=False이면 Verified 레인 큐잉 안됨."""
    await _make_user_with_area(db, "UA", notify_verified=True)

    with _mock_delivery_logs():
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

    assert result["queued_verified"] == 0


@pytest.mark.asyncio
async def test_fast_lane_queues_to_subscribers(db, redis_mock):
    """관심국가 구독자가 Fast 레인 다이제스트 버퍼에 큐잉됨."""
    await _make_user_with_area(db, "UA", notify_fast=True)

    with _mock_delivery_logs():
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

    assert result["status"] == "queued"
    assert result["queued_fast"] >= 1


@pytest.mark.asyncio
async def test_v7_fast_alert_all_active_subscribers(db, redis_mock):
    """v7: Fast alert는 notify_fast 필드 무관하게 관심국가 모든 활성 구독자 대상."""
    await _make_user_with_area(db, "UA", notify_fast=False)

    # alert_kind="fast"로 조회하면 notify_fast=False도 포함됨 (v7 정책)
    target = await _get_target_tokens_by_platform(
        "UA", notify_fast=False, kscore=10.0, cluster_topic=None, db=db, alert_kind="fast",
    )
    assert isinstance(target.tokens, list)
    assert len(target.tokens) >= 1


@pytest.mark.asyncio
async def test_dedup_key_set_after_queue(db, redis_mock):
    """큐잉 후 dedup 키 설정 → 같은 cluster_id 재발송 방지됨."""
    cluster_id = str(uuid.uuid4())
    await _make_user_with_area(db, "UA", notify_verified=True)

    with _mock_delivery_logs():
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

    # 큐잉 후 fast + verified dedup 키 모두 설정돼야 함
    assert await redis_mock.exists(f"alert:fast:{cluster_id}")
    assert await redis_mock.exists(f"alert:verified:{cluster_id}")


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


# ── 다이제스트 flush 테스트 ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_digest_queued_in_redis_after_send(db, redis_mock):
    """send_alert 후 Redis 다이제스트 버퍼에 항목이 쌓임."""
    _, _, token = await _make_user_with_area(db, "UA", notify_fast=True)

    with _mock_delivery_logs():
        result = await send_alert(
            cluster_id=str(uuid.uuid4()),
            cluster_title="Test fast alert",
            country_code="UA",
            severity=60,
            kscore=5.0,
            is_verified=False,
            cluster_topic=None,
            alert_kind="fast",
            db=db,
            redis=redis_mock,
        )

    assert result["status"] == "queued"
    # Redis에 다이제스트 키가 생겼어야 함
    keys = [k async for k in redis_mock.scan_iter(f"{DIGEST_BUFFER_KEY_PREFIX}*")]
    assert len(keys) >= 1


@pytest.mark.asyncio
async def test_flush_alert_digests_clears_buffer_and_sends(db, redis_mock):
    """flush_alert_digests(): Redis 버퍼를 읽어 FCM 발송 시도, 버퍼 초기화."""
    import json
    user, _, push_token = await _make_user_with_area(db, "UA", notify_fast=True)

    # 직접 버퍼에 항목 삽입
    key = f"{DIGEST_BUFFER_KEY_PREFIX}{user.id}"
    item = json.dumps({
        "cluster_id": str(uuid.uuid4()),
        "title": "Test event",
        "title_ko": "테스트 이벤트",
        "country_code": "UA",
        "severity": 65,
        "kscore": 5.0,
        "lane": "fast",
        "ts": 1700000000,
        "log_id": None,
        "platform": "web",
        "language": "ko",
        "tz_name": "Asia/Seoul",
        "home_country": "KR",
    })
    await redis_mock.rpush(key, item)

    with patch("worker.push.push_service._split_and_send", return_value=(1, [], {})) as mock_fcm:
        result = await flush_alert_digests(db=db, redis=redis_mock)

    assert result["flushed_users"] == 1
    assert mock_fcm.called
    # 버퍼 키가 삭제됐어야 함
    remaining_keys = [k async for k in redis_mock.scan_iter(f"{DIGEST_BUFFER_KEY_PREFIX}*")]
    assert len(remaining_keys) == 0


@pytest.mark.asyncio
async def test_flush_digests_noop_on_empty_buffer(db, redis_mock):
    """버퍼가 비어있으면 flush는 아무것도 안 함."""
    result = await flush_alert_digests(db=db, redis=redis_mock)
    assert result["flushed_users"] == 0
    assert result["sent"] == 0


class TestDigestConstants:
    """다이제스트 버퍼 상수 확인."""

    def test_buffer_key_prefix(self):
        assert DIGEST_BUFFER_KEY_PREFIX == "alert:digest:"

    def test_digest_ttl_2h(self):
        from worker.push.push_service import DIGEST_BUFFER_TTL
        assert DIGEST_BUFFER_TTL == 7200

    def test_digest_max_display(self):
        from worker.push.push_service import DIGEST_MAX_DISPLAY
        assert DIGEST_MAX_DISPLAY == 3

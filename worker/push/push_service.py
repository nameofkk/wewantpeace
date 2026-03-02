"""
PushService: FCM Multicast 푸시 발송.

레인 분리:
  Verified 레인: is_verified=True AND notify_verified=True 사용자
  Fast    레인: notify_fast=True 사용자 (Pro만 해당, 미확인 포함)

쿨다운: severity >= 90 → 30분, 그 외 → 1시간 (Redis key)
필터:
  - topics: 사용자가 선택한 토픽에 해당 이슈 topic이 포함된 경우만 발송
  - quiet_hours: 사용자 현지 시각이 조용한 시간 범위이면 발송 제외

플랫폼별 분리:
  - web: data-only 메시지 (SW onBackgroundMessage에서 표시)
  - android/ios: notification + data 메시지 (시스템 트레이 자동 표시, 상단 배너)

Delivery Integrity (Sprint 2):
  - 전송 전 AlertDeliveryLog(decision='pending') INSERT
  - FCM ACK 후 decision → 'sent'
  - FCM 실패 후 decision → 'failed' + failure_reason
  - 억제 시 decision → 'suppressed' + suppression_reason
  - 멀티디바이스: 유저당 last_seen_at 최신 1개 토큰만 발송
  - collapse_key: spike_event_id 기반 중복 알림 완화
"""
import logging
import uuid as _uuid
from collections import defaultdict
from datetime import datetime, timezone, time as dt_time
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User, UserArea, UserPreference, UserPushToken
from backend.app.models.notification import Notification
from backend.app.models.alert_delivery_log import AlertDeliveryLog
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# FCM 에러 중 토큰 무효를 나타내는 에러 코드들
_INVALID_TOKEN_ERRORS = {
    "UNREGISTERED",
    "INVALID_ARGUMENT",
    "SENDER_ID_MISMATCH",
    "NOT_FOUND",
}

COOLDOWN_SECONDS = 3600  # 1시간 (기본)
COOLDOWN_SECONDS_CRITICAL = 1800  # 30분 (severity >= 90)
_COOLDOWN_KEY_PREFIX = "push:cooldown:"


def _cooldown_key(cluster_id: str) -> str:
    return f"{_COOLDOWN_KEY_PREFIX}{cluster_id}"


async def _is_in_cooldown(cluster_id: str, redis) -> bool:
    return bool(await redis.exists(_cooldown_key(cluster_id)))


async def _set_cooldown(cluster_id: str, redis, severity: int = 0):
    """쿨다운 설정. severity >= 90이면 30분, 그 외 1시간."""
    ttl = COOLDOWN_SECONDS_CRITICAL if severity >= 90 else COOLDOWN_SECONDS
    await redis.setex(_cooldown_key(cluster_id), ttl, "1")


def _is_in_quiet_hours(current: dt_time, start: dt_time, end: dt_time) -> bool:
    """현재 시각이 quiet_hours(start~end) 범위인지 확인. 자정 걸침 처리."""
    if start <= end:
        # 같은 날 범위: e.g., 09:00~18:00
        return start <= current <= end
    else:
        # 자정 걸침: e.g., 22:00~07:00
        return current >= start or current <= end


# ── 토큰 타입 (플랫폼 + user_id 포함) ──
class _TokenInfo:
    __slots__ = ("fcm_token", "platform", "user_id")

    def __init__(self, fcm_token: str, platform: str, user_id: _uuid.UUID):
        self.fcm_token = fcm_token
        self.platform = platform  # "web" | "android" | "ios"
        self.user_id = user_id


# ── 억제된 사용자 정보 ──
class _SuppressedInfo:
    __slots__ = ("user_id", "platform", "reason")

    def __init__(self, user_id: _uuid.UUID, platform: str, reason: str):
        self.user_id = user_id
        self.platform = platform
        self.reason = reason


class _TargetResult:
    """_get_target_tokens_by_platform 반환값: 발송 대상 + 억제된 유저."""
    __slots__ = ("tokens", "suppressed")

    def __init__(self, tokens: list[_TokenInfo], suppressed: list[_SuppressedInfo]):
        self.tokens = tokens
        self.suppressed = suppressed


async def _get_target_tokens_by_platform(
    country_code: Optional[str],
    notify_fast: bool,
    kscore: float,
    cluster_topic: Optional[str],
    db: AsyncSession,
) -> _TargetResult:
    """
    해당 국가에 관심 설정한 사용자의 FCM 토큰 + 플랫폼 수집.
    notify_fast=True: fast 레인 (notify_fast=True 사용자)
    notify_fast=False: verified 레인 (notify_verified=True 사용자)
    kscore: 사용자 min_kscore 이하인 경우만 발송
    cluster_topic: 사용자 topics 목록에 포함된 경우만 발송
    quiet_hours: 사용자 현지 시각이 조용한 시간이면 제외

    PRD 8.5 멀티디바이스: 유저당 last_seen_at 최신 1개 토큰만 반환.
    """
    if not country_code:
        return _TargetResult([], [])

    if notify_fast:
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
            UserArea.notify_fast == True,
        )
    else:
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
            UserArea.notify_verified == True,
        )

    result = await db.execute(
        select(
            UserPushToken.user_id,
            UserPushToken.fcm_token,
            UserPushToken.platform,
            UserPushToken.last_seen_at,
            UserPreference.topics,
            UserPreference.quiet_hours_start,
            UserPreference.quiet_hours_end,
            UserPreference.timezone,
        )
        .join(UserArea, UserArea.user_id == UserPushToken.user_id)
        .join(UserPreference, UserPreference.user_id == UserPushToken.user_id)
        .where(*area_filter, UserPreference.min_kscore <= kscore, UserPushToken.status == "active")
    )
    rows = result.fetchall()

    now_utc = datetime.now(timezone.utc)

    # 1차: 유저별로 모든 토큰 수집 + 필터링 사유 판별
    # user_id -> list of (fcm_token, platform, last_seen_at, suppression_reason|None)
    user_rows: dict[_uuid.UUID, list[tuple]] = defaultdict(list)
    for user_id, fcm_token, platform, last_seen_at, topics, qh_start, qh_end, tz_name in rows:
        suppression_reason = None

        # topics 필터: cluster_topic이 사용자가 구독한 topic 목록에 없으면 스킵
        if cluster_topic and topics and cluster_topic not in topics:
            # topics 미구독은 발송 대상이 아님 (delivery log 기록 안 함)
            continue

        # quiet_hours 필터: 현재 사용자 로컬 시각이 조용한 시간 범위이면 억제
        if qh_start is not None and qh_end is not None:
            try:
                user_tz = ZoneInfo(tz_name or "Asia/Seoul")
                now_local = now_utc.astimezone(user_tz).time()
                if _is_in_quiet_hours(now_local, qh_start, qh_end):
                    suppression_reason = "dnd"
            except (ZoneInfoNotFoundError, Exception):
                pass  # timezone 파싱 실패 시 조용한 시간 무시

        user_rows[user_id].append((fcm_token, platform or "web", last_seen_at, suppression_reason))

    # 2차: 유저당 last_seen_at 최신 1개 토큰만 선택 (PRD 8.5)
    tokens: list[_TokenInfo] = []
    suppressed: list[_SuppressedInfo] = []

    for user_id, token_list in user_rows.items():
        # 억제 사유가 있는 토큰이 하나라도 있으면 유저 전체 억제
        # (같은 유저의 모든 토큰은 동일한 suppression_reason을 가짐)
        first_suppression = None
        for _, _, _, reason in token_list:
            if reason is not None:
                first_suppression = reason
                break

        if first_suppression:
            # 유저 억제: 가장 최신 토큰의 platform으로 기록
            sorted_by_seen = sorted(
                token_list,
                key=lambda x: x[2] or datetime.min.replace(tzinfo=timezone.utc),
                reverse=True,
            )
            best = sorted_by_seen[0]
            suppressed.append(_SuppressedInfo(user_id, best[1], first_suppression))
            continue

        # 억제 아닌 경우: last_seen_at 최신 1개만 선택
        sorted_by_seen = sorted(
            token_list,
            key=lambda x: x[2] or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        best = sorted_by_seen[0]
        tokens.append(_TokenInfo(best[0], best[1], user_id))

    return _TargetResult(tokens, suppressed)


async def _get_plan_locked_users(
    country_code: Optional[str],
    db: AsyncSession,
) -> list[_SuppressedInfo]:
    """Free 유저 중 해당 국가를 관심 등록했지만 Fast 알림을 받을 수 없는 유저 조회.
    → 'plan_locked' suppression 사유로 delivery log에 기록."""
    if not country_code:
        return []
    result = await db.execute(
        select(User.id, UserPushToken.platform, UserPushToken.last_seen_at)
        .join(UserArea, UserArea.user_id == User.id)
        .join(UserPushToken, UserPushToken.user_id == User.id)
        .where(
            UserArea.country_code == country_code,
            UserArea.is_active == True,
            UserArea.notify_fast == False,
            User.plan == "free",
            UserPushToken.status == "active",
        )
        .distinct(User.id)
    )
    # 유저당 1 레코드만 (DISTINCT)
    return [
        _SuppressedInfo(row.id, row.platform or "web", "plan_locked")
        for row in result.fetchall()
    ]


FCM_BATCH_SIZE = 500  # FCM MulticastMessage 최대 토큰 수


def _collect_invalid_tokens(batch: list[str], response) -> list[str]:
    """FCM 응답에서 만료/무효 토큰을 수집."""
    invalid = []
    for token, send_response in zip(batch, response.responses):
        if send_response.success:
            continue
        exc = send_response.exception
        if exc is None:
            continue
        # firebase_admin.messaging 에러 코드 확인
        error_code = getattr(exc, "code", "") or ""
        error_class = type(exc).__name__
        if (
            error_class in ("UnregisteredError", "InvalidArgumentError", "SenderIdMismatchError", "NotFoundError")
            or any(code in error_code.upper() for code in _INVALID_TOKEN_ERRORS)
        ):
            invalid.append(token)
    return invalid


def _classify_fcm_failure(batch: list[str], response) -> dict[str, str]:
    """FCM 응답에서 토큰별 failure_reason 분류. 성공한 토큰은 포함 안 함."""
    failures: dict[str, str] = {}
    for token, send_response in zip(batch, response.responses):
        if send_response.success:
            continue
        exc = send_response.exception
        if exc is None:
            failures[token] = "gateway_error"
            continue
        error_code = getattr(exc, "code", "") or ""
        error_class = type(exc).__name__
        if (
            error_class in ("UnregisteredError", "InvalidArgumentError", "SenderIdMismatchError", "NotFoundError")
            or any(code in error_code.upper() for code in _INVALID_TOKEN_ERRORS)
        ):
            failures[token] = "token_expired"
        elif "QUOTA" in error_code.upper() or "RATE" in error_code.upper():
            failures[token] = "throttled"
        else:
            failures[token] = "gateway_error"
    return failures


def _send_fcm_for_web(
    tokens: list[str],
    title: str,
    body: str,
    data: dict,
    collapse_key: Optional[str] = None,
) -> tuple[int, list[str], dict[str, str]]:
    """
    웹 토큰용 FCM 발송: data-only 메시지 (SW onBackgroundMessage에서 표시).
    notification 필드 없음 -> 중복 알림 방지.
    Returns: (성공 수, 만료/무효 토큰 리스트, 토큰별 failure_reason)
    """
    if not tokens:
        return 0, [], {}
    total_success = 0
    all_invalid: list[str] = []
    all_failures: dict[str, str] = {}
    for i in range(0, len(tokens), FCM_BATCH_SIZE):
        batch = tokens[i:i + FCM_BATCH_SIZE]
        try:
            import firebase_admin.messaging as messaging
            msg_data = {k: str(v) for k, v in data.items()}
            msg_data["title"] = title
            msg_data["body"] = body

            webpush_headers = {"Urgency": "high"}
            if collapse_key:
                webpush_headers["Topic"] = collapse_key

            message = messaging.MulticastMessage(
                tokens=batch,
                data=msg_data,
                android=messaging.AndroidConfig(priority="high"),
                webpush=messaging.WebpushConfig(headers=webpush_headers),
            )
            response = messaging.send_each_for_multicast(message)
            total_success += response.success_count
            all_invalid.extend(_collect_invalid_tokens(batch, response))
            all_failures.update(_classify_fcm_failure(batch, response))
            logger.info("FCM 웹 배치[%d~%d]: %d/%d 성공", i, i + len(batch), response.success_count, len(batch))
        except ImportError:
            logger.warning(
                "FCM 미설치 (firebase_admin 없음): tokens=%d 미발송 title=%r",
                len(batch), title,
            )
            for t in batch:
                all_failures[t] = "gateway_error"
        except Exception as e:
            logger.error("FCM 웹 발송 오류 (배치 %d): %s", i // FCM_BATCH_SIZE, e)
            for t in batch:
                all_failures[t] = "gateway_error"
    return total_success, all_invalid, all_failures


def _send_fcm_for_native(
    tokens: list[str],
    title: str,
    body: str,
    data: dict,
    severity: int = 0,
    collapse_key: Optional[str] = None,
) -> tuple[int, list[str], dict[str, str]]:
    """
    Android/iOS 네이티브 토큰용 FCM 발송: notification + data 메시지.
    시스템 트레이에 자동 표시 + 상단 배너 (HIGH importance 채널).
    Returns: (성공 수, 만료/무효 토큰 리스트, 토큰별 failure_reason)
    """
    if not tokens:
        return 0, [], {}
    total_success = 0
    all_invalid: list[str] = []
    all_failures: dict[str, str] = {}
    channel_id = "wwp_critical" if severity >= 90 else "wwp_alerts"
    for i in range(0, len(tokens), FCM_BATCH_SIZE):
        batch = tokens[i:i + FCM_BATCH_SIZE]
        try:
            import firebase_admin.messaging as messaging
            msg_data = {k: str(v) for k, v in data.items()}

            # collapse_key for Android (PRD 8.4)
            android_config = messaging.AndroidConfig(
                priority="high",
                collapse_key=collapse_key if collapse_key else None,
                notification=messaging.AndroidNotification(
                    channel_id=channel_id,
                    priority="high" if severity < 90 else "max",
                    icon="notification_icon",
                ),
            )

            # apns-collapse-id for iOS (PRD 8.4)
            apns_headers = {}
            if collapse_key:
                apns_headers["apns-collapse-id"] = collapse_key

            apns_config = messaging.APNSConfig(
                headers=apns_headers if apns_headers else None,
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                    ),
                ),
            )

            message = messaging.MulticastMessage(
                tokens=batch,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=msg_data,
                android=android_config,
                apns=apns_config,
            )
            response = messaging.send_each_for_multicast(message)
            total_success += response.success_count
            all_invalid.extend(_collect_invalid_tokens(batch, response))
            all_failures.update(_classify_fcm_failure(batch, response))
            logger.info("FCM 네이티브 배치[%d~%d]: %d/%d 성공", i, i + len(batch), response.success_count, len(batch))
        except ImportError:
            logger.warning(
                "FCM 미설치 (firebase_admin 없음): tokens=%d 미발송 title=%r",
                len(batch), title,
            )
            for t in batch:
                all_failures[t] = "gateway_error"
        except Exception as e:
            logger.error("FCM 네이티브 발송 오류 (배치 %d): %s", i // FCM_BATCH_SIZE, e)
            for t in batch:
                all_failures[t] = "gateway_error"
    return total_success, all_invalid, all_failures


def _split_and_send(
    token_infos: list[_TokenInfo],
    title: str,
    body: str,
    data: dict,
    severity: int = 0,
    collapse_key: Optional[str] = None,
) -> tuple[int, list[str], dict[str, str]]:
    """토큰을 웹/네이티브로 분리하여 각각 발송. Returns: (성공 수, 무효 토큰 리스트, 토큰별 failure_reason)"""
    web_tokens = [t.fcm_token for t in token_infos if t.platform == "web"]
    native_tokens = [t.fcm_token for t in token_infos if t.platform in ("android", "ios")]

    sent_web, invalid_web, failures_web = _send_fcm_for_web(
        web_tokens, title, body, data, collapse_key=collapse_key,
    )
    sent_native, invalid_native, failures_native = _send_fcm_for_native(
        native_tokens, title, body, data, severity=severity, collapse_key=collapse_key,
    )

    all_failures = {**failures_web, **failures_native}
    return sent_web + sent_native, invalid_web + invalid_native, all_failures


async def cleanup_invalid_tokens(invalid_tokens: list[str], db: AsyncSession):
    """무효/만료 FCM 토큰을 status='expired'로 소프트 삭제."""
    if not invalid_tokens:
        return
    result = await db.execute(
        update(UserPushToken)
        .where(UserPushToken.fcm_token.in_(invalid_tokens))
        .values(status="expired")
    )
    updated = result.rowcount
    if updated:
        logger.info("만료/무효 FCM 토큰 %d개 expired 처리: %s", updated, invalid_tokens[:5])


# ── Delivery Log 헬퍼 ──────────────────────────────────────────────────────


async def _insert_pending_logs(
    token_infos: list[_TokenInfo],
    cluster_id: str,
    spike_event_id: Optional[str],
    alert_type: str,
    collapse_key: Optional[str],
    db: AsyncSession,
) -> dict[str, _uuid.UUID]:
    """발송 대상 토큰에 대해 pending delivery log를 배치 INSERT.
    Returns: {fcm_token -> log.id} 매핑
    """
    pipeline_mode = settings.alert_pipeline_mode
    cluster_uuid = _uuid.UUID(cluster_id)
    spike_uuid = _uuid.UUID(spike_event_id) if spike_event_id else None
    token_to_log_id: dict[str, _uuid.UUID] = {}

    logs = []
    for ti in token_infos:
        log = AlertDeliveryLog(
            user_id=ti.user_id,
            cluster_id=cluster_uuid,
            spike_event_id=spike_uuid,
            alert_type=alert_type,
            decision="pending",
            platform=ti.platform,
            pipeline_mode=pipeline_mode,
            collapse_key=collapse_key,
        )
        logs.append(log)

    if logs:
        db.add_all(logs)
        await db.flush()  # ID 할당
        for log, ti in zip(logs, token_infos):
            token_to_log_id[ti.fcm_token] = log.id

    return token_to_log_id


async def _update_logs_sent(log_ids: list[_uuid.UUID], db: AsyncSession):
    """발송 성공한 log들을 sent로 업데이트."""
    if not log_ids:
        return
    await db.execute(
        update(AlertDeliveryLog)
        .where(AlertDeliveryLog.id.in_(log_ids))
        .values(decision="sent", updated_at=datetime.now(timezone.utc))
    )


async def _update_logs_failed(
    log_ids_with_reason: list[tuple[_uuid.UUID, str]], db: AsyncSession,
):
    """발송 실패한 log들을 failed + failure_reason으로 업데이트."""
    if not log_ids_with_reason:
        return
    # 같은 failure_reason별로 묶어서 배치 업데이트
    reason_groups: dict[str, list[_uuid.UUID]] = defaultdict(list)
    for log_id, reason in log_ids_with_reason:
        reason_groups[reason].append(log_id)

    for reason, ids in reason_groups.items():
        await db.execute(
            update(AlertDeliveryLog)
            .where(AlertDeliveryLog.id.in_(ids))
            .values(
                decision="failed",
                failure_reason=reason,
                updated_at=datetime.now(timezone.utc),
            )
        )


async def _insert_suppressed_logs(
    suppressed: list[_SuppressedInfo],
    cluster_id: str,
    spike_event_id: Optional[str],
    alert_type: str,
    db: AsyncSession,
):
    """억제된 유저에 대해 suppressed delivery log INSERT."""
    if not suppressed:
        return
    pipeline_mode = settings.alert_pipeline_mode
    cluster_uuid = _uuid.UUID(cluster_id)
    spike_uuid = _uuid.UUID(spike_event_id) if spike_event_id else None

    logs = []
    for si in suppressed:
        log = AlertDeliveryLog(
            user_id=si.user_id,
            cluster_id=cluster_uuid,
            spike_event_id=spike_uuid,
            alert_type=alert_type,
            decision="suppressed",
            suppression_reason=si.reason,
            platform=si.platform,
            pipeline_mode=pipeline_mode,
        )
        logs.append(log)

    if logs:
        db.add_all(logs)
        await db.flush()


async def _process_delivery_results(
    token_infos: list[_TokenInfo],
    token_to_log_id: dict[str, _uuid.UUID],
    fcm_failures: dict[str, str],
    db: AsyncSession,
):
    """FCM 발송 결과에 따라 delivery log를 sent/failed로 업데이트."""
    sent_ids: list[_uuid.UUID] = []
    failed_ids: list[tuple[_uuid.UUID, str]] = []

    for ti in token_infos:
        log_id = token_to_log_id.get(ti.fcm_token)
        if not log_id:
            continue
        if ti.fcm_token in fcm_failures:
            failed_ids.append((log_id, fcm_failures[ti.fcm_token]))
        else:
            sent_ids.append(log_id)

    await _update_logs_sent(sent_ids, db)
    await _update_logs_failed(failed_ids, db)


# ── 메인 발송 함수 ──────────────────────────────────────────────────────


async def send_spike_alert(
    cluster_id: str,
    cluster_title: str,
    country_code: Optional[str],
    severity: int,
    kscore: float,
    is_verified: bool,
    cluster_topic: Optional[str],
    db: AsyncSession,
    redis,
    spike_event_id: Optional[str] = None,
) -> dict:
    """
    스파이크 알림 발송.
    1. 쿨다운 확인
    2. Verified 레인: is_verified이면 발송
    3. Fast 레인: 항상 발송 (Pro 사용자, notify_fast=True)
    topics/quiet_hours 필터는 _get_target_tokens_by_platform 내부에서 적용됨.

    Delivery Integrity: pending -> sent/failed 로깅, suppressed 로깅.
    """
    if await _is_in_cooldown(cluster_id, redis):
        logger.info("쿨다운 중 - 발송 스킵: cluster_id=%s", cluster_id)
        return {"status": "cooldown", "sent": 0}

    collapse_key = str(spike_event_id) if spike_event_id else cluster_id
    sent_verified = 0
    sent_fast = 0
    all_invalid: list[str] = []

    # Verified 레인
    if is_verified:
        target_v = await _get_target_tokens_by_platform(
            country_code, notify_fast=False, kscore=kscore, cluster_topic=cluster_topic, db=db
        )

        # 1. suppressed 로그
        await _insert_suppressed_logs(
            target_v.suppressed, cluster_id, spike_event_id, "verified", db,
        )

        # 2. pending 로그
        token_to_log_v = await _insert_pending_logs(
            target_v.tokens, cluster_id, spike_event_id, "verified", collapse_key, db,
        )

        # 3. FCM 발송
        sent_verified, invalid_v, failures_v = _split_and_send(
            token_infos=target_v.tokens,
            title=f"⚠️ {cluster_title}",
            body=f"Severity {severity} · KScore {kscore:.1f} · Verified / 심각도 {severity} · 확인된 이슈",
            data={"cluster_id": cluster_id, "lane": "verified", "severity": str(severity), "kscore": str(kscore)},
            severity=severity,
            collapse_key=collapse_key,
        )

        # 4. 결과 반영 (sent/failed)
        await _process_delivery_results(target_v.tokens, token_to_log_v, failures_v, db)
        all_invalid.extend(invalid_v)

    # Fast 레인 (항상)
    target_f = await _get_target_tokens_by_platform(
        country_code, notify_fast=True, kscore=kscore, cluster_topic=cluster_topic, db=db
    )

    # plan_locked 억제: Free 유저 중 해당 국가를 관심 등록했지만 Fast 알림 불가한 유저
    plan_locked = await _get_plan_locked_users(country_code, db)
    all_suppressed_fast = list(target_f.suppressed) + plan_locked

    # 1. suppressed 로그
    await _insert_suppressed_logs(
        all_suppressed_fast, cluster_id, spike_event_id, "fast", db,
    )

    # 2. pending 로그
    token_to_log_f = await _insert_pending_logs(
        target_f.tokens, cluster_id, spike_event_id, "fast", collapse_key, db,
    )

    # 3. FCM 발송
    sent_fast, invalid_f, failures_f = _split_and_send(
        token_infos=target_f.tokens,
        title=f"🚨 {cluster_title}",
        body=f"Severity {severity} · Fast Alert / 심각도 {severity} · 빠른 알림",
        data={"cluster_id": cluster_id, "lane": "fast", "severity": str(severity)},
        severity=severity,
        collapse_key=collapse_key,
    )

    # 4. 결과 반영
    await _process_delivery_results(target_f.tokens, token_to_log_f, failures_f, db)
    all_invalid.extend(invalid_f)

    # 만료/무효 토큰 자동 정리
    await cleanup_invalid_tokens(all_invalid, db)

    await _set_cooldown(cluster_id, redis, severity=severity)

    return {
        "status": "sent",
        "sent_verified": sent_verified,
        "sent_fast": sent_fast,
        "total": sent_verified + sent_fast,
        "cleaned_tokens": len(all_invalid),
    }


_VERIFIED_COOLDOWN_KEY_PREFIX = "push:verified_cooldown:"


async def send_verified_alert(
    cluster_id: str,
    cluster_title: str,
    country_code: Optional[str],
    severity: int,
    kscore: float,
    cluster_topic: Optional[str],
    db: AsyncSession,
    redis,
    spike_event_id: Optional[str] = None,
) -> dict:
    """
    공식확인(verified) 전환 시 알림 발송.
    Verified 레인만 발송. 별도 쿨다운 키 사용.

    Delivery Integrity: pending -> sent/failed 로깅, suppressed 로깅.
    """
    cooldown_key = f"{_VERIFIED_COOLDOWN_KEY_PREFIX}{cluster_id}"
    if await redis.exists(cooldown_key):
        logger.info("Verified 쿨다운 중 - 발송 스킵: cluster_id=%s", cluster_id)
        return {"status": "cooldown", "sent": 0}

    collapse_key = str(spike_event_id) if spike_event_id else cluster_id

    target_v = await _get_target_tokens_by_platform(
        country_code, notify_fast=False, kscore=kscore, cluster_topic=cluster_topic, db=db
    )

    # 1. suppressed 로그
    await _insert_suppressed_logs(
        target_v.suppressed, cluster_id, spike_event_id, "verified", db,
    )

    # 2. pending 로그
    token_to_log_v = await _insert_pending_logs(
        target_v.tokens, cluster_id, spike_event_id, "verified", collapse_key, db,
    )

    # 3. FCM 발송
    sent_verified, invalid_v, failures_v = _split_and_send(
        token_infos=target_v.tokens,
        title=f"⚠️ {cluster_title}",
        body=f"Severity {severity} · KScore {kscore:.1f} · Verified / 심각도 {severity} · 확인된 이슈",
        data={"cluster_id": cluster_id, "lane": "verified", "severity": str(severity), "kscore": str(kscore)},
        severity=severity,
        collapse_key=collapse_key,
    )

    # 4. 결과 반영
    await _process_delivery_results(target_v.tokens, token_to_log_v, failures_v, db)

    # 만료/무효 토큰 자동 정리
    await cleanup_invalid_tokens(invalid_v, db)

    ttl = COOLDOWN_SECONDS_CRITICAL if severity >= 90 else COOLDOWN_SECONDS
    await redis.setex(cooldown_key, ttl, "1")

    return {
        "status": "sent",
        "sent_verified": sent_verified,
        "total": sent_verified,
        "cleaned_tokens": len(invalid_v),
    }


async def save_in_app_notifications(
    cluster_id: str,
    cluster_title: str,
    country_code: Optional[str],
    notif_type: str,
    db: AsyncSession,
) -> int:
    """
    해당 국가 관심지역 사용자에게 인앱 Notification 레코드 배치 INSERT.
    notif_type: "verified" | "spike"
    Returns: 생성된 알림 수
    """
    if not country_code:
        return 0

    if notif_type == "verified":
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
            UserArea.notify_verified == True,
        )
        title = f"⚠️ {cluster_title}"
        body = "공식 확인된 이슈입니다 / Verified issue"
    else:
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
            UserArea.notify_fast == True,
        )
        title = f"🚨 {cluster_title}"
        body = "속보 알림 / Breaking alert"

    # 대상 사용자 user_id 수집 (중복 제거)
    result = await db.execute(
        select(UserArea.user_id)
        .where(*area_filter)
        .distinct()
    )
    user_ids = [row[0] for row in result.fetchall()]

    if not user_ids:
        return 0

    cluster_uuid = _uuid.UUID(cluster_id)

    notifications = [
        Notification(
            user_id=uid,
            type=notif_type,
            cluster_id=cluster_uuid,
            title=title,
            body=body,
        )
        for uid in user_ids
    ]
    db.add_all(notifications)
    await db.flush()

    logger.info(
        "인앱 알림 %d건 저장: type=%s, cluster_id=%s",
        len(notifications), notif_type, cluster_id,
    )
    return len(notifications)

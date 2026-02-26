"""
PushService: FCM Multicast 푸시 발송.

레인 분리:
  Verified 레인: is_verified=True AND notify_verified=True 사용자
  Fast    레인: notify_fast=True 사용자 (Pro만 해당, 미확인 포함)

쿨다운: 동일 cluster_id 1시간 (Redis key)
필터:
  - topics: 사용자가 선택한 토픽에 해당 이슈 topic이 포함된 경우만 발송
  - quiet_hours: 사용자 현지 시각이 조용한 시간 범위이면 발송 제외
"""
import logging
from datetime import datetime, timezone, time as dt_time
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.user import User, UserArea, UserPreference, UserPushToken
from backend.app.models.notification import Notification

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = 3600  # 1시간
_COOLDOWN_KEY_PREFIX = "push:cooldown:"


def _cooldown_key(cluster_id: str) -> str:
    return f"{_COOLDOWN_KEY_PREFIX}{cluster_id}"


async def _is_in_cooldown(cluster_id: str, redis) -> bool:
    return bool(await redis.exists(_cooldown_key(cluster_id)))


async def _set_cooldown(cluster_id: str, redis):
    await redis.setex(_cooldown_key(cluster_id), COOLDOWN_SECONDS, "1")


def _is_in_quiet_hours(current: dt_time, start: dt_time, end: dt_time) -> bool:
    """현재 시각이 quiet_hours(start~end) 범위인지 확인. 자정 걸침 처리."""
    if start <= end:
        # 같은 날 범위: e.g., 09:00~18:00
        return start <= current <= end
    else:
        # 자정 걸침: e.g., 22:00~07:00
        return current >= start or current <= end


async def _get_target_tokens(
    country_code: Optional[str],
    notify_fast: bool,
    kscore: float,
    cluster_topic: Optional[str],
    db: AsyncSession,
) -> list[str]:
    """
    해당 국가에 관심 설정한 사용자의 FCM 토큰 수집.
    notify_fast=True: fast 레인 (notify_fast=True 사용자)
    notify_fast=False: verified 레인 (notify_verified=True 사용자)
    kscore: 사용자 min_kscore 이하인 경우만 발송
    cluster_topic: 사용자 topics 목록에 포함된 경우만 발송
    quiet_hours: 사용자 현지 시각이 조용한 시간이면 제외
    """
    if not country_code:
        return []

    if notify_fast:
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.notify_fast == True,
        )
    else:
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.notify_verified == True,
        )

    result = await db.execute(
        select(
            UserPushToken.fcm_token,
            UserPreference.topics,
            UserPreference.quiet_hours_start,
            UserPreference.quiet_hours_end,
            UserPreference.timezone,
        )
        .join(UserArea, UserArea.user_id == UserPushToken.user_id)
        .join(UserPreference, UserPreference.user_id == UserPushToken.user_id)
        .where(*area_filter, UserPreference.min_kscore <= kscore)
    )
    rows = result.fetchall()

    now_utc = datetime.now(timezone.utc)
    tokens = []
    for fcm_token, topics, qh_start, qh_end, tz_name in rows:
        # topics 필터: cluster_topic이 사용자가 구독한 topic 목록에 없으면 스킵
        if cluster_topic and topics and cluster_topic not in topics:
            continue

        # quiet_hours 필터: 현재 사용자 로컬 시각이 조용한 시간 범위이면 스킵
        if qh_start is not None and qh_end is not None:
            try:
                user_tz = ZoneInfo(tz_name or "Asia/Seoul")
                now_local = now_utc.astimezone(user_tz).time()
                if _is_in_quiet_hours(now_local, qh_start, qh_end):
                    continue
            except (ZoneInfoNotFoundError, Exception):
                pass  # timezone 파싱 실패 시 조용한 시간 무시

        tokens.append(fcm_token)

    return tokens


FCM_BATCH_SIZE = 500  # FCM MulticastMessage 최대 토큰 수


def _send_fcm_multicast(tokens: list[str], title: str, body: str, data: dict) -> int:
    """
    Firebase FCM Multicast 발송 (500개 배치).
    firebase_admin SDK 없으면 로깅만.
    Returns: 성공 수
    """
    if not tokens:
        return 0
    total_success = 0
    # FCM API 제한: 한 번에 최대 500개 토큰
    for i in range(0, len(tokens), FCM_BATCH_SIZE):
        batch = tokens[i:i + FCM_BATCH_SIZE]
        try:
            import firebase_admin.messaging as messaging
            message = messaging.MulticastMessage(
                tokens=batch,
                notification=messaging.Notification(title=title, body=body),
                data={k: str(v) for k, v in data.items()},
            )
            response = messaging.send_each_for_multicast(message)
            total_success += response.success_count
            logger.info("FCM 배치[%d~%d]: %d/%d 성공", i, i + len(batch), response.success_count, len(batch))
        except ImportError:
            logger.warning(
                "FCM 미설치 (firebase_admin 없음): tokens=%d 미발송 title=%r",
                len(batch), title,
            )
        except Exception as e:
            logger.error("FCM 발송 오류 (배치 %d): %s", i // FCM_BATCH_SIZE, e)
    return total_success


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
) -> dict:
    """
    스파이크 알림 발송.
    1. 쿨다운 확인
    2. Verified 레인: is_verified이면 발송
    3. Fast 레인: 항상 발송 (Pro 사용자, notify_fast=True)
    topics/quiet_hours 필터는 _get_target_tokens 내부에서 적용됨.
    """
    if await _is_in_cooldown(cluster_id, redis):
        logger.info("쿨다운 중 - 발송 스킵: cluster_id=%s", cluster_id)
        return {"status": "cooldown", "sent": 0}

    sent_verified = 0
    sent_fast = 0

    # Verified 레인
    if is_verified:
        tokens_v = await _get_target_tokens(
            country_code, notify_fast=False, kscore=kscore, cluster_topic=cluster_topic, db=db
        )
        sent_verified = _send_fcm_multicast(
            tokens=tokens_v,
            title=f"⚠️ {cluster_title}",
            body=f"Severity {severity} · KScore {kscore:.1f} · Verified / 심각도 {severity} · 확인된 이슈",
            data={"cluster_id": cluster_id, "lane": "verified", "severity": str(severity), "kscore": str(kscore)},
        )

    # Fast 레인 (항상)
    tokens_f = await _get_target_tokens(
        country_code, notify_fast=True, kscore=kscore, cluster_topic=cluster_topic, db=db
    )
    sent_fast = _send_fcm_multicast(
        tokens=tokens_f,
        title=f"🚨 {cluster_title}",
        body=f"Severity {severity} · Fast Alert / 심각도 {severity} · 빠른 알림",
        data={"cluster_id": cluster_id, "lane": "fast", "severity": str(severity)},
    )

    await _set_cooldown(cluster_id, redis)

    return {
        "status": "sent",
        "sent_verified": sent_verified,
        "sent_fast": sent_fast,
        "total": sent_verified + sent_fast,
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
) -> dict:
    """
    공식확인(verified) 전환 시 알림 발송.
    Verified 레인만 발송. 별도 쿨다운 키 사용.
    """
    cooldown_key = f"{_VERIFIED_COOLDOWN_KEY_PREFIX}{cluster_id}"
    if await redis.exists(cooldown_key):
        logger.info("Verified 쿨다운 중 - 발송 스킵: cluster_id=%s", cluster_id)
        return {"status": "cooldown", "sent": 0}

    tokens_v = await _get_target_tokens(
        country_code, notify_fast=False, kscore=kscore, cluster_topic=cluster_topic, db=db
    )
    sent_verified = _send_fcm_multicast(
        tokens=tokens_v,
        title=f"⚠️ {cluster_title}",
        body=f"Severity {severity} · KScore {kscore:.1f} · Verified / 심각도 {severity} · 확인된 이슈",
        data={"cluster_id": cluster_id, "lane": "verified", "severity": str(severity), "kscore": str(kscore)},
    )

    await redis.setex(cooldown_key, COOLDOWN_SECONDS, "1")

    return {
        "status": "sent",
        "sent_verified": sent_verified,
        "total": sent_verified,
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
            UserArea.notify_verified == True,
        )
        title = f"⚠️ {cluster_title}"
        body = f"공식 확인된 이슈입니다 / Verified issue"
    else:
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.notify_fast == True,
        )
        title = f"🚨 {cluster_title}"
        body = f"속보 알림 / Breaking alert"

    # 대상 사용자 user_id 수집 (중복 제거)
    result = await db.execute(
        select(UserArea.user_id)
        .where(*area_filter)
        .distinct()
    )
    user_ids = [row[0] for row in result.fetchall()]

    if not user_ids:
        return 0

    import uuid as _uuid
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

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
from datetime import datetime, timedelta, timezone, time as dt_time
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

# ── Spike Push Count: FREE 유저 spike 알림 횟수 추적 (Pro 전환 프롬프트) ──
_SPIKE_PUSH_COUNT_PREFIX = "spike_push_count:"
_SPIKE_PUSH_COUNT_TTL = 30 * 86400  # 30일

# T12: 일일 푸시 상한
DAILY_PUSH_LIMITS = {
    "free": 5,
    "pro": 20,
    "pro_plus": 100,
}
_DAILY_PUSH_KEY_PREFIX = "push:daily:"


def _cooldown_key(cluster_id: str) -> str:
    return f"{_COOLDOWN_KEY_PREFIX}{cluster_id}"


async def _is_in_cooldown(cluster_id: str, redis) -> bool:
    return bool(await redis.exists(_cooldown_key(cluster_id)))


async def _set_cooldown(cluster_id: str, redis, severity: int = 0):
    """쿨다운 설정. severity >= 90이면 30분, 그 외 1시간."""
    ttl = COOLDOWN_SECONDS_CRITICAL if severity >= 90 else COOLDOWN_SECONDS
    await redis.setex(_cooldown_key(cluster_id), ttl, "1")


def _daily_push_key(user_id: str, tz_name: str = "") -> str:
    if tz_name:
        try:
            today = datetime.now(ZoneInfo(tz_name)).strftime("%Y-%m-%d")
        except (ZoneInfoNotFoundError, Exception):
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{_DAILY_PUSH_KEY_PREFIX}{user_id}:{today}"


async def _check_daily_limit(user_id: str, plan: str, redis, tz_name: str = "") -> bool:
    """일일 푸시 상한 확인. 초과 시 True 반환."""
    limit = DAILY_PUSH_LIMITS.get(plan, DAILY_PUSH_LIMITS["free"])
    key = _daily_push_key(user_id, tz_name=tz_name)
    current = await redis.get(key)
    return int(current or 0) >= limit


async def _increment_daily_push(user_id: str, redis, tz_name: str = ""):
    """일일 푸시 카운터 증가."""
    key = _daily_push_key(user_id, tz_name=tz_name)
    pipe = redis.pipeline()
    pipe.incr(key)
    pipe.expire(key, 86400)  # 24시간 TTL
    await pipe.execute()


def _is_in_quiet_hours(current: dt_time, start: dt_time, end: dt_time) -> bool:
    """현재 시각이 quiet_hours(start~end) 범위인지 확인. 자정 걸침 처리."""
    if start <= end:
        # 같은 날 범위: e.g., 09:00~18:00
        return start <= current <= end
    else:
        # 자정 걸침: e.g., 22:00~07:00
        return current >= start or current <= end


# ── 토큰 타입 (플랫폼 + user_id + 개인화 정보 포함) ──
class _TokenInfo:
    __slots__ = ("fcm_token", "platform", "user_id", "home_country", "language", "tz_name")

    def __init__(
        self,
        fcm_token: str,
        platform: str,
        user_id: _uuid.UUID,
        home_country: str = "",
        language: str = "ko",
        tz_name: str = "",
    ):
        self.fcm_token = fcm_token
        self.platform = platform  # "web" | "android" | "ios"
        self.user_id = user_id
        self.home_country = home_country
        self.language = language
        self.tz_name = tz_name


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
    alert_kind: str = "",
) -> _TargetResult:
    """
    해당 국가에 관심 설정한 사용자의 FCM 토큰 + 플랫폼 수집.

    v7 변경:
      Fast alert → 모든 플랜의 관심국가 구독자 대상 (notify_fast 체크 불필요, is_active만)
      Verified alert → notify_verified=True AND plan in ("pro","pro_plus") 조건

    kscore: 사용자 min_kscore 이하인 경우만 발송
    cluster_topic: 사용자 topics 목록에 포함된 경우만 발송
    quiet_hours: 사용자 현지 시각이 조용한 시간이면 제외

    PRD 8.5 멀티디바이스: 유저당 last_seen_at 최신 1개 토큰만 반환.
    """
    if not country_code:
        return _TargetResult([], [])

    if alert_kind == "verified":
        # v7: Verified alert → notify_verified=True AND Pro/Pro+ only
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
            UserArea.notify_verified == True,
        )
    elif alert_kind == "fast" or notify_fast:
        # v7: Fast alert → 모든 관심국가 구독자 (notify_fast 무관)
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
        )
    else:
        # legacy: verified lane
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
            UserPreference.home_country,
            UserPreference.language,
        )
        .join(UserArea, UserArea.user_id == UserPushToken.user_id)
        .join(UserPreference, UserPreference.user_id == UserPushToken.user_id)
        .where(*area_filter, UserPreference.min_kscore <= kscore, UserPushToken.status == "active")
    )
    rows = result.fetchall()

    now_utc = datetime.now(timezone.utc)

    # 1차: 유저별로 모든 토큰 수집 + 필터링 사유 판별
    # user_id -> list of (fcm_token, platform, last_seen_at, suppression_reason|None, home_country, language)
    user_rows: dict[_uuid.UUID, list[tuple]] = defaultdict(list)
    for user_id, fcm_token, platform, last_seen_at, topics, qh_start, qh_end, tz_name, home_country, language in rows:
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

        user_rows[user_id].append((fcm_token, platform or "web", last_seen_at, suppression_reason, home_country or "", language or "ko", tz_name or ""))

    # 2차: 유저당 last_seen_at 최신 1개 토큰만 선택 (PRD 8.5)
    tokens: list[_TokenInfo] = []
    suppressed: list[_SuppressedInfo] = []

    for user_id, token_list in user_rows.items():
        # 억제 사유가 있는 토큰이 하나라도 있으면 유저 전체 억제
        # (같은 유저의 모든 토큰은 동일한 suppression_reason을 가짐)
        first_suppression = None
        for _, _, _, reason, _, _, _ in token_list:
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
        tokens.append(_TokenInfo(best[0], best[1], user_id, home_country=best[4], language=best[5], tz_name=best[6]))

    return _TargetResult(tokens, suppressed)


async def _apply_daily_limits(
    target: _TargetResult, db: AsyncSession, redis,
    severity: int = 0,
) -> _TargetResult:
    """T12: 일일 푸시 상한 초과 유저를 tokens에서 제거하고 suppressed로 이동.

    v7 Critical 바이패스: severity >= CRITICAL_SEVERITY_MIN(80) AND plan in ("pro","pro_plus")
    → 일일 상한 무시.
    """
    from worker.processor.calibration import CRITICAL_SEVERITY_MIN
    if not target.tokens:
        return target

    # 유저 ID 수집
    user_ids = list({t.user_id for t in target.tokens})

    # 유저별 plan 조회
    plan_result = await db.execute(
        select(User.id, User.plan).where(User.id.in_(user_ids))
    )
    user_plans = {row[0]: row[1] for row in plan_result.fetchall()}

    allowed_tokens: list[_TokenInfo] = []
    extra_suppressed: list[_SuppressedInfo] = []

    for t in target.tokens:
        plan = user_plans.get(t.user_id, "free")
        # v7: Critical 바이패스 — Pro/Pro+ 사용자는 sev>=80 시 상한 무시
        if severity >= CRITICAL_SEVERITY_MIN and plan in ("pro", "pro_plus"):
            allowed_tokens.append(t)
            continue
        exceeded = await _check_daily_limit(str(t.user_id), plan, redis, tz_name=t.tz_name)
        if exceeded:
            extra_suppressed.append(_SuppressedInfo(t.user_id, t.platform, "daily_limit"))
            # v7: Free 유저 놓친 알림 카운터 추적
            if plan == "free":
                try:
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    missed_key = f"missed_alert_count:{t.user_id}:{today}"
                    await redis.incr(missed_key)
                    await redis.expire(missed_key, 7 * 86400)  # 7일 TTL
                except Exception:
                    pass
        else:
            allowed_tokens.append(t)

    return _TargetResult(allowed_tokens, target.suppressed + extra_suppressed)


async def _increment_daily_push_for_tokens(tokens: list[_TokenInfo], redis):
    """발송 성공한 토큰들의 유저에 대해 일일 카운터 증가."""
    seen_users = set()
    for t in tokens:
        uid = str(t.user_id)
        if uid not in seen_users:
            seen_users.add(uid)
            await _increment_daily_push(uid, redis, tz_name=t.tz_name)


async def _get_plan_locked_users(
    country_code: Optional[str],
    db: AsyncSession,
    alert_kind: str = "verified",
) -> list[_SuppressedInfo]:
    """v7: Free 유저 중 해당 국가를 관심 등록했지만 Verified 알림을 받을 수 없는 유저 조회.
    → 'plan_locked' suppression 사유로 delivery log에 기록.

    변경: 기존 Fast 잠금 → Verified 잠금 (Fast는 모든 플랜에서 가능)
    """
    if not country_code:
        return []
    if alert_kind != "verified":
        return []  # Fast alert는 plan 제한 없음
    result = await db.execute(
        select(User.id, UserPushToken.platform, UserPushToken.last_seen_at)
        .join(UserArea, UserArea.user_id == User.id)
        .join(UserPushToken, UserPushToken.user_id == User.id)
        .where(
            UserArea.country_code == country_code,
            UserArea.is_active == True,
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


# ── "Why this matters" 컨텍스트 생성 ─────────────────────────────────────────

# 국가명 (컨텍스트 표시용, 짧은 이름)
_HOME_COUNTRY_NAMES_KO: dict[str, str] = {
    "KR": "한국", "US": "미국", "JP": "일본", "CN": "중국", "TW": "대만",
    "DE": "독일", "GB": "영국", "AU": "호주", "IN": "인도", "BR": "브라질",
}
_HOME_COUNTRY_NAMES_EN: dict[str, str] = {
    "KR": "Korea", "US": "US", "JP": "Japan", "CN": "China", "TW": "Taiwan",
    "DE": "Germany", "GB": "UK", "AU": "Australia", "IN": "India", "BR": "Brazil",
}

# 관계 설명 템플릿 (geo/sec/eco 최대 요인 기반)
# (factor_key, min_threshold) -> (ko_template, en_template)
# 50자 이내를 목표로 함
_RELATION_TEMPLATES_KO: dict[str, list[tuple[float, str]]] = {
    "geo": [
        (0.9, "직접 안보 위협 — 최고 경계"),
        (0.7, "인접국 긴장 — 주시 필요"),
        (0.4, "주변국 동향 — 영향 가능"),
    ],
    "sec": [
        (0.9, "핵심 안보 이해관계 — 경계"),
        (0.7, "안보 동맹/관련국 — 주시 필요"),
        (0.4, "안보 연관 — 동향 주시"),
    ],
    "eco": [
        (0.9, "핵심 경제 파트너 — 직접 영향"),
        (0.7, "주요 교역국 — 경제 영향 가능"),
        (0.4, "경제 연관 — 간접 영향 가능"),
    ],
}

_RELATION_TEMPLATES_EN: dict[str, list[tuple[float, str]]] = {
    "geo": [
        (0.9, "Direct threat — highest alert"),
        (0.7, "Neighboring tension — monitor"),
        (0.4, "Regional development — watch"),
    ],
    "sec": [
        (0.9, "Core security interest — alert"),
        (0.7, "Security ally/partner — monitor"),
        (0.4, "Security link — watch"),
    ],
    "eco": [
        (0.9, "Key economic partner — direct impact"),
        (0.7, "Major trade partner — potential impact"),
        (0.4, "Economic link — indirect impact"),
    ],
}


def generate_alert_context(
    home_country: str,
    event_country: str,
    topic: str,
    lang: str = "ko",
) -> str:
    """
    사용자 기준국과 이벤트 발생국의 관계를 1줄로 설명.
    IMPACT_FACTORS와 TOPIC_IMPACT_WEIGHTS를 기반으로 가장 두드러진 요인을 선택.
    50자 이내 목표.

    Returns: "한국: 직접 안보 위협 — 최고 경계" 형태의 문자열
    """
    from worker.processor.calibration import IMPACT_FACTORS, TOPIC_IMPACT_WEIGHTS

    # BASIC(빈 문자열) 기준국가 → 글로벌 알림
    if not home_country:
        if lang == "ko":
            return "📍 글로벌 긴장도 상승 — 주시 필요"
        return "📍 Global tension rising — monitor"

    factors = IMPACT_FACTORS.get(home_country, {}).get(event_country)
    if not factors:
        # 등록되지 않은 국가쌍: 글로벌 폴백
        if lang == "ko":
            return "📍 글로벌 긴장도 상승 — 주시 필요"
        return "📍 Global tension rising — monitor"

    # TOPIC_IMPACT_WEIGHTS로 가중 점수 계산, 가장 높은 요인 선택
    weights = TOPIC_IMPACT_WEIGHTS.get(topic, TOPIC_IMPACT_WEIGHTS["unknown"])
    weighted = {
        k: factors[k] * weights[k]
        for k in ("geo", "sec", "eco")
    }
    # 가중 점수가 가장 높은 요인 선택
    dominant_key = max(weighted, key=weighted.get)  # type: ignore[arg-type]
    dominant_val = factors[dominant_key]

    templates = _RELATION_TEMPLATES_KO if lang == "ko" else _RELATION_TEMPLATES_EN
    country_names = _HOME_COUNTRY_NAMES_KO if lang == "ko" else _HOME_COUNTRY_NAMES_EN

    home_label = country_names.get(home_country, home_country)

    # 임계값 내림차순으로 매칭
    desc = None
    for threshold, tmpl in templates[dominant_key]:
        if dominant_val >= threshold:
            desc = tmpl
            break

    if not desc:
        # 모든 요인이 낮은 경우 (< 0.4)
        if lang == "ko":
            desc = "글로벌 동향 — 참고"
        else:
            desc = "Global development — FYI"

    return f"📍 {home_label} 관점: {desc}"


# 하위호환 alias
generate_spike_context = generate_alert_context

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


def _split_and_send_with_context(
    token_infos: list[_TokenInfo],
    title: str,
    base_body: str,
    data: dict,
    event_country: Optional[str],
    topic: Optional[str],
    severity: int = 0,
    collapse_key: Optional[str] = None,
    title_ko: Optional[str] = None,
    body_ko: Optional[str] = None,
    body_en: Optional[str] = None,
) -> tuple[int, list[str], dict[str, str]]:
    """
    토큰을 (home_country, language)별로 그룹화하여 개인화된 컨텍스트를 body에 추가 발송.
    각 그룹마다 generate_alert_context()로 "why this matters" 1줄 생성.
    lang에 따라 title/body를 분기 (ko/en).
    Returns: (성공 수, 무효 토큰 리스트, 토큰별 failure_reason)
    """
    if not token_infos:
        return 0, [], {}

    # (home_country, language)별로 토큰 그룹화
    groups: dict[tuple[str, str], list[_TokenInfo]] = defaultdict(list)
    for ti in token_infos:
        groups[(ti.home_country, ti.language)].append(ti)

    total_sent = 0
    all_invalid: list[str] = []
    all_failures: dict[str, str] = {}

    for (home_country, lang), group_tokens in groups.items():
        # 언어별 title 선택
        group_title = (title_ko if lang == "ko" and title_ko else title)
        # 언어별 body 선택
        group_body = (body_ko if lang == "ko" and body_ko else body_en if lang != "ko" and body_en else base_body)

        # 컨텍스트 생성
        if event_country:
            context = generate_alert_context(home_country, event_country, topic or "unknown", lang)
        else:
            context = "글로벌 긴장도 상승 — 주시 필요" if lang == "ko" else "Global tension rising — monitor"

        # body에 컨텍스트 추가 (줄바꿈 구분)
        personalized_body = f"{group_body}\n{context}"

        # data에도 context 추가 (웹 SW에서 활용 가능)
        personalized_data = {**data, "context": context}

        sent, invalid, failures = _split_and_send(
            token_infos=group_tokens,
            title=group_title,
            body=personalized_body,
            data=personalized_data,
            severity=severity,
            collapse_key=collapse_key,
        )
        total_sent += sent
        all_invalid.extend(invalid)
        all_failures.update(failures)

    return total_sent, all_invalid, all_failures


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


# ── Spike Push Count 추적 (Pro 전환 프롬프트용) ────────────────────────────


async def _increment_spike_push_counts(
    target_verified: _TargetResult,
    target_fast: _TargetResult,
    db: AsyncSession,
    redis,
):
    """
    Spike 알림이 실제 발송된 FREE 유저의 spike_push_count를 Redis에서 증가.
    Verified + Fast 레인 모두의 발송 대상 유저에서 FREE 유저만 카운트.
    """
    # 발송 대상 유저 ID 수집 (중복 제거)
    sent_user_ids = set()
    for ti in target_verified.tokens:
        sent_user_ids.add(ti.user_id)
    for ti in target_fast.tokens:
        sent_user_ids.add(ti.user_id)

    if not sent_user_ids:
        return

    # FREE 유저만 필터
    user_ids_list = list(sent_user_ids)
    plan_result = await db.execute(
        select(User.id, User.plan).where(User.id.in_(user_ids_list))
    )
    free_user_ids = [row[0] for row in plan_result.fetchall() if row[1] == "free"]

    for uid in free_user_ids:
        key = f"{_SPIKE_PUSH_COUNT_PREFIX}{uid}"
        try:
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, _SPIKE_PUSH_COUNT_TTL)
        except Exception:
            logger.debug("spike_push_count incr 실패: user_id=%s", uid)


# ── 메인 발송 함수 (v7: KScore 기반 알림 모델) ────────────────────────────

_VERIFIED_COOLDOWN_KEY_PREFIX = "push:verified_cooldown:"


async def send_alert(
    cluster_id: str,
    cluster_title: str,
    country_code: Optional[str],
    severity: int,
    kscore: float,
    is_verified: bool,
    cluster_topic: Optional[str],
    alert_kind: str,
    db: AsyncSession,
    redis,
    spike_event_id: Optional[str] = None,
    cluster_title_ko: Optional[str] = None,
) -> dict:
    """
    v7 통합 알림 발송.
    alert_kind: "fast" | "verified" | "combined"
      - fast: 모든 플랜의 관심국가 구독자에게 신속 알림
      - verified: Pro/Pro+ 구독자에게 신뢰 알림
      - combined: fast+verified 동시 충족 → 1건만 발송

    1. Redis 중복방지 (클러스터 단위, 72h TTL)
    2. Critical 바이패스 (sev>=80 AND Pro/Pro+)
    3. 놓친 알림 카운터 (Free 상한 초과 시)
    """
    # Redis 중복방지 (같은 cluster_id)
    if alert_kind in ("fast", "combined"):
        dedup_key = f"alert:fast:{cluster_id}"
        if await redis.exists(dedup_key):
            logger.info("Fast alert 중복 스킵: cluster_id=%s", cluster_id)
            if alert_kind == "fast":
                return {"status": "dedup", "sent": 0}
    if alert_kind in ("verified", "combined"):
        dedup_key_v = f"alert:verified:{cluster_id}"
        if await redis.exists(dedup_key_v):
            logger.info("Verified alert 중복 스킵: cluster_id=%s", cluster_id)
            if alert_kind == "verified":
                return {"status": "dedup", "sent": 0}

    # Cross-cluster 유사도 중복방지: 같은 국가 + 유사 제목의 다른 클러스터에
    # 이미 알림 보냈으면 스킵 (6시간 내)
    if country_code and cluster_title:
        try:
            from backend.app.models.issue_cluster import IssueCluster
            from worker.processor.clusterer import _title_similarity
            _cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
            _recent = await db.execute(
                select(IssueCluster.id, IssueCluster.title, IssueCluster.title_ko).where(
                    IssueCluster.country_code == country_code,
                    IssueCluster.severity > 0,
                    IssueCluster.id != _uuid.UUID(cluster_id),
                    IssueCluster.last_event_at >= _cutoff,
                )
            )
            for _row in _recent:
                _sim = _title_similarity(
                    cluster_title, _row.title or "",
                    ko_a=cluster_title_ko, ko_b=_row.title_ko,
                )
                if _sim >= 0.20:
                    _other_key = f"alert:fast:{_row.id}"
                    if await redis.exists(_other_key):
                        logger.info(
                            "Cross-cluster 중복 스킵: %s (sim=%.3f with %s)",
                            cluster_id, _sim, _row.id,
                        )
                        return {"status": "cross_dedup", "sent": 0, "similar_cluster": str(_row.id)}
        except Exception:
            logger.debug("Cross-cluster dedup check 실패 (무시)", exc_info=True)

    collapse_key = cluster_id
    sent_verified = 0
    sent_fast = 0
    all_invalid: list[str] = []
    verified_user_ids: set[_uuid.UUID] = set()  # combined 모드에서 fast 레인 중복 제거용

    # ── Verified 레인 (combined 또는 verified) ──
    if alert_kind in ("verified", "combined") and is_verified:
        target_v = await _get_target_tokens_by_platform(
            country_code, notify_fast=False, kscore=kscore,
            cluster_topic=cluster_topic, db=db, alert_kind="verified",
        )
        target_v = await _apply_daily_limits(target_v, db, redis, severity=severity)

        # plan_locked: Free 유저가 Verified를 받으려 하는 경우
        plan_locked_v = await _get_plan_locked_users(country_code, db, alert_kind="verified")
        await _insert_suppressed_logs(
            target_v.suppressed + plan_locked_v, cluster_id, spike_event_id, "verified", db,
        )

        token_to_log_v = await _insert_pending_logs(
            target_v.tokens, cluster_id, spike_event_id, "verified", collapse_key, db,
        )

        _title_en = f"⚠️ {cluster_title}"
        _title_ko = f"⚠️ {cluster_title_ko or cluster_title}"
        # combined 모드: 속보 + 신뢰 동시 충족 표시
        if alert_kind == "combined":
            _vbody_ko = f"심각도 {severity} · KScore {kscore:.1f} · 속보 + 신뢰 알림"
            _vbody_en = f"Severity {severity} · KScore {kscore:.1f} · Fast + Verified"
        else:
            _vbody_ko = f"심각도 {severity} · KScore {kscore:.1f} · 신뢰 알림"
            _vbody_en = f"Severity {severity} · KScore {kscore:.1f} · Verified Alert"
        sent_verified, invalid_v, failures_v = _split_and_send_with_context(
            token_infos=target_v.tokens,
            title=_title_en,
            base_body=_vbody_en,
            data={"cluster_id": cluster_id, "lane": "verified", "severity": str(severity), "kscore": str(kscore)},
            event_country=country_code,
            topic=cluster_topic,
            severity=severity,
            collapse_key=collapse_key,
            title_ko=_title_ko,
            body_ko=_vbody_ko,
            body_en=_vbody_en,
        )
        await _process_delivery_results(target_v.tokens, token_to_log_v, failures_v, db)
        all_invalid.extend(invalid_v)
        await _increment_daily_push_for_tokens(target_v.tokens, redis)
        verified_user_ids = {t.user_id for t in target_v.tokens}

        # Redis 중복방지 설정
        await redis.setex(f"alert:verified:{cluster_id}", 259200, "1")  # 72h

    # ── Fast 레인 (combined 또는 fast) ──
    if alert_kind in ("fast", "combined"):
        target_f = await _get_target_tokens_by_platform(
            country_code, notify_fast=True, kscore=kscore,
            cluster_topic=cluster_topic, db=db, alert_kind="fast",
        )

        # combined 모드: verified 레인에서 이미 발송한 유저 제외 (중복 알림 방지)
        if alert_kind == "combined" and verified_user_ids:
            target_f = _TargetResult(
                tokens=[t for t in target_f.tokens if t.user_id not in verified_user_ids],
                suppressed=target_f.suppressed,
            )

        target_f = await _apply_daily_limits(target_f, db, redis, severity=severity)

        await _insert_suppressed_logs(
            target_f.suppressed, cluster_id, spike_event_id, "fast", db,
        )

        token_to_log_f = await _insert_pending_logs(
            target_f.tokens, cluster_id, spike_event_id, "fast", collapse_key, db,
        )

        _title_en_f = f"🚨 {cluster_title}"
        _title_ko_f = f"🚨 {cluster_title_ko or cluster_title}"
        if alert_kind == "fast" and not is_verified:
            _body_ko_f = f"심각도 {severity} · 속보 알림\n⏳ 추후 신뢰 인증 가능"
            _body_en_f = f"Severity {severity} · Fast Alert\n⏳ May be verified later"
        else:
            _body_ko_f = f"심각도 {severity} · 속보 알림"
            _body_en_f = f"Severity {severity} · Fast Alert"

        sent_fast, invalid_f, failures_f = _split_and_send_with_context(
            token_infos=target_f.tokens,
            title=_title_en_f,
            base_body=_body_en_f,
            data={"cluster_id": cluster_id, "lane": "fast", "severity": str(severity)},
            event_country=country_code,
            topic=cluster_topic,
            severity=severity,
            collapse_key=collapse_key,
            title_ko=_title_ko_f,
            body_ko=_body_ko_f,
            body_en=_body_en_f,
        )
        await _process_delivery_results(target_f.tokens, token_to_log_f, failures_f, db)
        all_invalid.extend(invalid_f)
        await _increment_daily_push_for_tokens(target_f.tokens, redis)

        # Redis 중복방지 설정
        await redis.setex(f"alert:fast:{cluster_id}", 259200, "1")  # 72h

    # 만료/무효 토큰 자동 정리
    await cleanup_invalid_tokens(all_invalid, db)

    return {
        "status": "sent",
        "alert_kind": alert_kind,
        "sent_verified": sent_verified,
        "sent_fast": sent_fast,
        "total": sent_verified + sent_fast,
        "cleaned_tokens": len(all_invalid),
    }


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
    """하위호환 wrapper: send_alert()로 위임."""
    alert_kind = "combined" if is_verified else "fast"
    return await send_alert(
        cluster_id=cluster_id,
        cluster_title=cluster_title,
        country_code=country_code,
        severity=severity,
        kscore=kscore,
        is_verified=is_verified,
        cluster_topic=cluster_topic,
        alert_kind=alert_kind,
        db=db,
        redis=redis,
        spike_event_id=spike_event_id,
    )


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
    """하위호환 wrapper: send_alert(alert_kind="verified")로 위임."""
    return await send_alert(
        cluster_id=cluster_id,
        cluster_title=cluster_title,
        country_code=country_code,
        severity=severity,
        kscore=kscore,
        is_verified=True,
        cluster_topic=cluster_topic,
        alert_kind="verified",
        db=db,
        redis=redis,
        spike_event_id=spike_event_id,
    )


async def save_in_app_notifications(
    cluster_id: str,
    cluster_title: str,
    country_code: Optional[str],
    notif_type: str,
    db: AsyncSession,
    cluster_topic: Optional[str] = None,
) -> int:
    """
    해당 국가 관심지역 사용자에게 인앱 Notification 레코드 배치 INSERT.
    notif_type: "verified" | "fast" (v7: "spike" → "fast")
    cluster_topic: 이벤트 토픽 (컨텍스트 생성용)
    Returns: 생성된 알림 수
    """
    if not country_code:
        return 0

    # 같은 cluster_id로 6시간 내 인앱 알림이 이미 있으면 스킵
    cluster_uuid = _uuid.UUID(cluster_id)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
    dup_check = await db.execute(
        select(Notification.id)
        .where(
            Notification.cluster_id == cluster_uuid,
            Notification.type == notif_type,
            Notification.created_at >= cutoff,
        )
        .limit(1)
    )
    if dup_check.scalar_one_or_none():
        logger.info("인앱 알림 중복 스킵: cluster=%s type=%s (6시간 내 기존 존재)", cluster_id, notif_type)
        return 0

    if notif_type == "verified":
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
            UserArea.notify_verified == True,
        )
        title = f"⚠️ {cluster_title}"
        base_body = "공식 확인된 이슈입니다 / Verified issue"
    else:
        # v7: Fast alert → 모든 관심국가 구독자 (notify_fast 무관)
        area_filter = (
            UserArea.country_code == country_code,
            UserArea.is_active == True,
        )
        title = f"🚨 {cluster_title}"
        base_body = "속보 알림 / Breaking alert"

    # 대상 사용자 user_id + home_country + language 수집 (중복 제거)
    result = await db.execute(
        select(
            UserArea.user_id,
            UserPreference.home_country,
            UserPreference.language,
        )
        .join(UserPreference, UserPreference.user_id == UserArea.user_id)
        .where(*area_filter)
        .distinct(UserArea.user_id)
    )
    rows = result.fetchall()

    if not rows:
        return 0

    notifications = []
    for uid, home_country, language in rows:
        # 유저별 개인화된 컨텍스트 생성
        context = generate_alert_context(
            home_country=home_country or "KR",
            event_country=country_code,
            topic=cluster_topic or "unknown",
            lang=language or "ko",
        )
        body = f"{base_body}\n{context}"

        notifications.append(
            Notification(
                user_id=uid,
                type=notif_type,
                cluster_id=cluster_uuid,
                title=title,
                body=body,
            )
        )

    db.add_all(notifications)
    await db.flush()

    logger.info(
        "인앱 알림 %d건 저장: type=%s, cluster_id=%s",
        len(notifications), notif_type, cluster_id,
    )
    return len(notifications)

"""
Groq / Gemini / OpenAI AI 클라이언트 설정.

우선순위: Groq (무료) → Gemini (무료) → OpenAI (유료 폴백, 현재 401 키 이슈로 사실상 죽어있음)
- 각 단계 429/오류 시 Redis에 차단 상태 저장 → 모든 worker 프로세스가 공유
- 차단 중에는 다음 단계로 자동 폴백 (해당 API 키가 있을 때)

Groq 무료 티어 (openai/gpt-oss-120b, 2026-09 실측): RPD 14,400 / RPM 30 / TPM 8,000
- 이 모델은 reasoning 모델이라 프롬프트 자체가 길면(분류 프롬프트 ~2,000 토큰)
  응답 전 reasoning 토큰을 크게 먹어(실측 200~730 변동) 분당 3콜 정도면 TPM 소진.
  → Gemini를 2차 폴백으로 추가한 이유 (TPM 여유가 훨씬 크고 reasoning 끌 수 있음).
Gemini 무료 티어 (gemini-3.5-flash-lite, OpenAI 호환 레이어):
  base_url=https://generativelanguage.googleapis.com/v1beta/openai/
  2026-09-15 실측: gemini-2.5-flash-lite/gemini-2.5-flash 전부 신규 계정에
  404("no longer available to new users") — 2.5 세대는 이미 신규 발급 종료됨.
  gemini-3.5-flash-lite로 교체. reasoning_effort="none"은 3.x에서 400
  에러(3.x는 완전 비활성 불가, "none"이 유효값이 아님) — 대신
  reasoning_effort="minimal"이 실측 completion 45~108 토큰(Groq 200~730
  대비 훨씬 안정적)으로 사실상 동일한 효과를 냄.
  정확한 RPM/TPM/RPD는 계정마다 달라 Google AI Studio 대시보드에서 확인 필요.
"""
import logging
import os
import time

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "openai/gpt-oss-120b"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_GEMINI_MODEL = "gemini-3.5-flash-lite"
_OPENAI_MODEL = "gpt-4o-mini"

USE_GROQ = bool(GROQ_API_KEY)
USE_GEMINI = bool(GEMINI_API_KEY)
USE_OPENAI = bool(OPENAI_API_KEY)

_active = [name for name, on in (("Groq", USE_GROQ), ("Gemini", USE_GEMINI), ("OpenAI", USE_OPENAI)) if on]
if _active:
    logger.info("AI 클라이언트 우선순위: %s", " → ".join(_active))
else:
    logger.warning("AI API 키 미설정 — AI 기능 비활성")

# ── Redis 서킷 브레이커 ────────────────────────────────────────────────────────
# 프로세스 메모리 변수 대신 Redis를 사용해 모든 celery worker 프로세스가 공유.
# Groq 429 → Redis에 "ai:groq_blocked" 키 TTL 저장 → 전 프로세스가 확인.
# Redis 장애 시 False 반환 (fail-open) — Redis 없으면 celery 자체가 안 돌아가므로 실질 위험 없음.

_REDIS_BLOCK_KEY = "ai:groq_blocked"
_redis_sync_client = None

# 배포/재시작 시 이전 차단 키 정리 (24시간 차단이 남아있을 수 있음)
def _is_stale_block_ttl(ttl: int | None) -> bool:
    """차단 키의 TTL이 비정상인지 판정.

    Redis TTL 규약: -2 = 키 없음, -1 = 키는 있으나 만료 시간 없음, n>0 = 남은 초.
    정상 차단은 mark_rate_limited가 최대 930초(=900+30)로 걸므로 그보다 크면 비정상이고,
    **-1(만료 없음)은 영구 차단이라 가장 위험하다**.

    예전 코드는 `if ttl and ttl > 900` 이라 -1을 걸러내지 못했다.
    그 결과 만료 없는 차단 키가 남으면 Groq가 영구 차단되고, 폴백인 OpenAI가
    크레딧 소진 상태라 AI 분류가 전부 실패 → 키워드 폴백 → topic=unknown 이 26%까지 치솟았다.
    """
    if ttl is None:
        return False
    return ttl == -1 or ttl > 930


def _clear_stale_block():
    """기존 차단 키가 비정상이면 삭제 (배포 직후 AI 복구용)."""
    try:
        r = _get_redis_sync()
        ttl = r.ttl(_REDIS_BLOCK_KEY)
        if _is_stale_block_ttl(ttl):
            r.delete(_REDIS_BLOCK_KEY)
            logger.warning("비정상 Groq 차단 키 삭제 (TTL=%s) — AI 분류 복구", ttl)
    except Exception as e:
        logger.debug("차단 키 정리 실패 (무시): %s", e)


def _get_redis_sync():
    """동기 Redis 클라이언트 반환 (celery sync 컨텍스트용)."""
    global _redis_sync_client
    if _redis_sync_client is None:
        import redis as _redis_lib
        redis_url = os.getenv("REDIS_URL", os.getenv("REDIS_PRIVATE_URL", "redis://localhost:6379"))
        _redis_sync_client = _redis_lib.from_url(redis_url, decode_responses=True, socket_timeout=2)
    return _redis_sync_client


def mark_rate_limited(retry_after_seconds: float) -> None:
    """Groq 429 발생 시 호출 — Redis에 차단 상태 저장 (모든 worker 공유)."""
    ttl = int(retry_after_seconds) + 30  # 여유 30초 추가
    try:
        _get_redis_sync().set(_REDIS_BLOCK_KEY, "1", ex=ttl)
        logger.warning(
            "Groq rate limit — Redis 차단 키 설정 (TTL=%.0f초/%.1f분). OpenAI 폴백 활성.",
            retry_after_seconds,
            retry_after_seconds / 60,
        )
    except Exception as _e:
        logger.warning("Redis 서킷 브레이커 저장 실패 (%s) — 프로세스 메모리로 폴백", _e)
        # 프로세스 메모리 폴백
        global _mem_blocked_until
        _mem_blocked_until = time.monotonic() + retry_after_seconds


# 메모리 폴백용 (Redis 장애 시)
_mem_blocked_until: float = 0.0


def is_groq_rate_limited() -> bool:
    """Groq 차단 상태인지 확인 (Redis 우선, 메모리 폴백).

    임포트 시점의 _clear_stale_block만으로는 부족하다 — 워커가 뜬 뒤에 비정상 키가
    생기면 재배포 전까지 영구 차단된다. 그래서 조회할 때마다 TTL을 같이 보고
    비정상이면 그 자리에서 지우고 해제로 판정한다 (런타임 자가치유).
    """
    # 메모리 먼저 확인 (Redis 오류 시 사용)
    if time.monotonic() < _mem_blocked_until:
        return True
    try:
        r = _get_redis_sync()
        ttl = r.ttl(_REDIS_BLOCK_KEY)
        if ttl == -2:  # 키 없음 = 차단 아님
            return False
        if _is_stale_block_ttl(ttl):
            r.delete(_REDIS_BLOCK_KEY)
            logger.warning("비정상 Groq 차단 키 감지·삭제 (TTL=%s) — 차단 해제", ttl)
            return False
        return True
    except Exception:
        return False  # Redis 장애 시 차단 해제 (fail-open)


# 하위 호환: 기존 코드에서 is_rate_limited() 호출하는 곳들
def is_rate_limited() -> bool:
    return is_groq_rate_limited()


# ── OpenAI 사용 불가 표시 ──────────────────────────────────────────────────────
# insufficient_quota(크레딧 소진)는 재시도로 풀리지 않는다. 그런데도 폴백 대상이라는
# 이유로 매 기사마다 호출해 429를 받고 있었다(실측 213연속 실패). 죽은 제공자를
# 일정 시간 배제해 낭비를 막고, 그동안은 Groq를 쓴다.
_OPENAI_BLOCK_KEY = "ai:openai_unavailable"
_mem_openai_blocked_until: float = 0.0


def mark_openai_unavailable(seconds: float = 3600.0) -> None:
    """OpenAI를 일정 시간 사용 불가로 표시 (크레딧 소진 등 재시도 무의미한 상태)."""
    global _mem_openai_blocked_until
    _mem_openai_blocked_until = time.monotonic() + seconds
    try:
        _get_redis_sync().set(_OPENAI_BLOCK_KEY, "1", ex=int(seconds))
    except Exception:
        pass
    logger.warning(
        "OpenAI 사용 불가로 표시 (%.0f분) — 크레딧/쿼터 확인 필요. 그동안 Groq만 사용.",
        seconds / 60,
    )


def is_openai_unavailable() -> bool:
    if time.monotonic() < _mem_openai_blocked_until:
        return True
    try:
        return bool(_get_redis_sync().exists(_OPENAI_BLOCK_KEY))
    except Exception:
        return False


# ── Gemini 서킷 브레이커 ───────────────────────────────────────────────────────
# Groq와 같은 이유(429 발생 시 일시 차단)와 OpenAI와 같은 이유(인증/쿼터 소진 시
# 영구에 가깝게 배제)를 둘 다 가질 수 있어 두 종류 브레이커를 모두 둔다.

_GEMINI_RATE_BLOCK_KEY = "ai:gemini_blocked"
_mem_gemini_rate_blocked_until: float = 0.0
_GEMINI_UNAVAILABLE_KEY = "ai:gemini_unavailable"
_mem_gemini_unavailable_until: float = 0.0


def mark_gemini_rate_limited(retry_after_seconds: float = 60.0) -> None:
    """Gemini 429 발생 시 호출 — 일시 차단 (Groq 서킷 브레이커와 동일 패턴)."""
    ttl = int(retry_after_seconds) + 15
    global _mem_gemini_rate_blocked_until
    _mem_gemini_rate_blocked_until = time.monotonic() + retry_after_seconds
    try:
        _get_redis_sync().set(_GEMINI_RATE_BLOCK_KEY, "1", ex=ttl)
    except Exception:
        pass
    logger.warning("Gemini rate limit — %.0f초 차단, 다음 폴백 사용.", retry_after_seconds)


def is_gemini_rate_limited() -> bool:
    if time.monotonic() < _mem_gemini_rate_blocked_until:
        return True
    try:
        return bool(_get_redis_sync().exists(_GEMINI_RATE_BLOCK_KEY))
    except Exception:
        return False


def mark_gemini_unavailable(seconds: float = 3600.0) -> None:
    """Gemini를 일정 시간 사용 불가로 표시 (인증 실패·쿼터 소진 등 재시도 무의미한 상태)."""
    global _mem_gemini_unavailable_until
    _mem_gemini_unavailable_until = time.monotonic() + seconds
    try:
        _get_redis_sync().set(_GEMINI_UNAVAILABLE_KEY, "1", ex=int(seconds))
    except Exception:
        pass
    logger.warning("Gemini 사용 불가로 표시 (%.0f분) — 키/쿼터 확인 필요.", seconds / 60)


def is_gemini_unavailable() -> bool:
    if time.monotonic() < _mem_gemini_unavailable_until:
        return True
    try:
        return bool(_get_redis_sync().exists(_GEMINI_UNAVAILABLE_KEY))
    except Exception:
        return False


# ── 3단계 폴백 선택 (Groq → Gemini → OpenAI) ──────────────────────────────────
# get_client()/get_model()/is_available()이 각자 같은 우선순위 로직을 중복 구현하면
# 나중에 티어를 추가/변경할 때 한쪽만 고치는 실수가 나기 쉬워 한 곳(_select_provider)
# 으로 모았다. get_current_provider()는 예외 처리에서 "방금 어느 제공자를 불렀는지"를
# 문자열 추측(에러 메시지에 "groq" 포함 여부 등) 없이 정확히 알기 위해 노출한다.

_PROVIDER_PRIORITY = ("groq", "gemini", "openai")

_PROVIDER_CONFIGURED = {
    "groq": lambda: USE_GROQ,
    "gemini": lambda: USE_GEMINI,
    "openai": lambda: USE_OPENAI,
}

_PROVIDER_BLOCKED = {
    "groq": is_groq_rate_limited,
    "gemini": lambda: is_gemini_rate_limited() or is_gemini_unavailable(),
    "openai": is_openai_unavailable,
}

_PROVIDER_CLIENT_ARGS = {
    "groq": (GROQ_API_KEY, _GROQ_BASE_URL),
    "gemini": (GEMINI_API_KEY, _GEMINI_BASE_URL),
    "openai": (OPENAI_API_KEY, None),
}

_PROVIDER_MODEL = {
    "groq": _GROQ_MODEL,
    "gemini": _GEMINI_MODEL,
    "openai": _OPENAI_MODEL,
}


def get_current_provider():
    """다음 호출에 실제로 쓰일 제공자("groq"/"gemini"/"openai") 반환, 키가 하나도
    없으면 None. 차단되지 않은 첫 제공자를 우선하고, 전부 차단이면 그래도 우선순위
    최상단(설정된 것 중)을 마지막 수단으로 한 번 더 시도한다 — 죽은 유료 API를
    두드리는 것보다 일시 차단된 무료 API를 재시도하는 게 낫다는 기존 원칙 유지.
    """
    configured = [p for p in _PROVIDER_PRIORITY if _PROVIDER_CONFIGURED[p]()]
    if not configured:
        return None
    for p in configured:
        if not _PROVIDER_BLOCKED[p]():
            return p
    return configured[0]


def get_client(timeout: float = 30.0):
    """Groq → Gemini → OpenAI 순으로 사용 가능한 첫 제공자의 클라이언트 반환."""
    from openai import OpenAI

    provider = get_current_provider()
    if provider is None:
        raise RuntimeError("AI API 키 미설정 — Groq, Gemini, OpenAI 모두 없음")
    api_key, base_url = _PROVIDER_CLIENT_ARGS[provider]
    if base_url:
        return OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
    return OpenAI(api_key=api_key, timeout=timeout)


def get_model() -> str:
    """현재 사용할 모델명 반환 (get_client와 같은 판정 순서를 따른다)."""
    provider = get_current_provider()
    return _PROVIDER_MODEL.get(provider, _OPENAI_MODEL)


def is_available() -> bool:
    """AI 기능 사용 가능 여부 (키가 하나라도 설정돼 있으면 True, 전부 차단 중이어도
    마지막 수단으로 시도하므로 True)."""
    return get_current_provider() is not None


# 모듈 로드 시 이전 차단 키 정리
try:
    _clear_stale_block()
except Exception:
    pass

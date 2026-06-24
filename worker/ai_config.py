"""
Groq / OpenAI AI 클라이언트 설정.

우선순위: Groq (무료) → OpenAI (유료 폴백)
- Groq 429 시 Redis에 차단 상태 저장 → 모든 worker 프로세스가 공유
- Groq 차단 중에는 OpenAI로 자동 폴백 (두 API 키 모두 있을 때)

Groq 무료 티어 (Llama 3.3 70B): 14,400 RPD / 30 RPM / 6,000 TPM
- normalizer (~1,900/day), clusterer+ai_title (~2,400/day), generators (~30/day)
- 합계 ~4,330/day → RPD 한도 대비 30%
- TPM 위험: RSS 동시 수집 시 짧은 구간에 몰림 → 배치 지연으로 해소
"""
import logging
import os
import time

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "llama-3.3-70b-versatile"
_OPENAI_MODEL = "gpt-4o-mini"

USE_GROQ = bool(GROQ_API_KEY)
USE_OPENAI = bool(OPENAI_API_KEY)

if USE_GROQ and USE_OPENAI:
    logger.info("AI 클라이언트: Groq (Llama 3.3 70B) 우선, OpenAI (gpt-4o-mini) 폴백")
elif USE_GROQ:
    logger.info("AI 클라이언트: Groq (Llama 3.3 70B) 사용 (OpenAI 키 없음)")
elif USE_OPENAI:
    logger.info("AI 클라이언트: OpenAI (gpt-4o-mini) 사용 (Groq 키 없음)")
else:
    logger.warning("AI API 키 미설정 — AI 기능 비활성")

# ── Redis 서킷 브레이커 ────────────────────────────────────────────────────────
# 프로세스 메모리 변수 대신 Redis를 사용해 모든 celery worker 프로세스가 공유.
# Groq 429 → Redis에 "ai:groq_blocked" 키 TTL 저장 → 전 프로세스가 확인.
# Redis 장애 시 False 반환 (fail-open) — Redis 없으면 celery 자체가 안 돌아가므로 실질 위험 없음.

_REDIS_BLOCK_KEY = "ai:groq_blocked"
_redis_sync_client = None

# 배포/재시작 시 이전 차단 키 정리 (24시간 차단이 남아있을 수 있음)
def _clear_stale_block():
    """기존 차단 키가 남아있으면 삭제 (배포 직후 AI 복구용)."""
    try:
        r = _get_redis_sync()
        ttl = r.ttl(_REDIS_BLOCK_KEY)
        if ttl and ttl > 900:  # 15분 이상 남았으면 비정상 (이전 24시간 차단)
            r.delete(_REDIS_BLOCK_KEY)
            logger.info("이전 Groq 차단 키 삭제 (TTL=%ds → 배포 후 초기화)", ttl)
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
    """Groq 차단 상태인지 확인 (Redis 우선, 메모리 폴백)."""
    # 메모리 먼저 확인 (Redis 오류 시 사용)
    if time.monotonic() < _mem_blocked_until:
        return True
    try:
        return bool(_get_redis_sync().exists(_REDIS_BLOCK_KEY))
    except Exception:
        return False  # Redis 장애 시 차단 해제 (fail-open)


# 하위 호환: 기존 코드에서 is_rate_limited() 호출하는 곳들
def is_rate_limited() -> bool:
    return is_groq_rate_limited()


def get_client(timeout: float = 30.0):
    """Groq 우선, Groq rate limited 시 OpenAI 폴백."""
    from openai import OpenAI

    groq_blocked = is_groq_rate_limited()

    if USE_GROQ and not groq_blocked:
        return OpenAI(api_key=GROQ_API_KEY, base_url=_GROQ_BASE_URL, timeout=timeout)

    if USE_OPENAI:
        if groq_blocked:
            logger.debug("Groq 차단 중 → OpenAI gpt-4o-mini 사용")
        return OpenAI(api_key=OPENAI_API_KEY, timeout=timeout)

    # 마지막 수단: Groq (차단 상태라도 — OpenAI 없을 때)
    if USE_GROQ:
        return OpenAI(api_key=GROQ_API_KEY, base_url=_GROQ_BASE_URL, timeout=timeout)

    raise RuntimeError("AI API 키 미설정 — Groq, OpenAI 모두 없음")


def get_model() -> str:
    """현재 사용할 모델명 반환."""
    groq_blocked = is_groq_rate_limited()
    if USE_GROQ and not groq_blocked:
        return _GROQ_MODEL
    if USE_OPENAI:
        return _OPENAI_MODEL
    return _GROQ_MODEL  # 폴백


def is_available() -> bool:
    """AI 기능 사용 가능 여부.
    - Groq 정상: True
    - Groq 차단 + OpenAI 있음: True (OpenAI로 폴백)
    - 모두 없음: False
    """
    if USE_GROQ and not is_groq_rate_limited():
        return True
    if USE_OPENAI:
        return True
    return False


# 모듈 로드 시 이전 차단 키 정리
try:
    _clear_stale_block()
except Exception:
    pass

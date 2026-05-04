"""
Groq / OpenAI AI 클라이언트 설정.

Groq 무료 티어 (Llama 3.3 70B): 14,400 RPD / 30 RPM
- normalizer (~1,900/day), clusterer (~1,900/day), ai_title (~475/day), generators (~30/day)
- 합계 ~4,305/day → 한도 대비 30%

OpenAI 유지 (gpt-4o-mini): newsletter, impact, monitor (~60/day)
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

# Groq 우선, OpenAI 폴백
USE_GROQ = bool(GROQ_API_KEY)

if USE_GROQ:
    logger.info("AI 클라이언트: Groq (Llama 3.3 70B) 사용")
elif OPENAI_API_KEY:
    logger.info("AI 클라이언트: OpenAI (gpt-4o-mini) 사용")
else:
    logger.warning("AI API 키 미설정 — AI 기능 비활성")

# ── 서킷 브레이커 (일일 토큰 한도 소진 시 자동 차단) ──────────────────────────
_rate_limited_until: float = 0.0


def mark_rate_limited(retry_after_seconds: float) -> None:
    """429 TPD 발생 시 호출 — 지정 시간 동안 AI 호출을 전면 차단."""
    global _rate_limited_until
    _rate_limited_until = time.monotonic() + retry_after_seconds
    logger.warning(
        "Groq 일일 토큰 한도 소진 — %.0f초(%.1f분) 동안 AI 호출 중단",
        retry_after_seconds,
        retry_after_seconds / 60,
    )


def is_rate_limited() -> bool:
    """현재 서킷 브레이커가 열려 있으면 True."""
    return time.monotonic() < _rate_limited_until


def get_client(timeout: float = 30.0):
    """Groq 우선, OpenAI 폴백 클라이언트 반환."""
    from openai import OpenAI

    if USE_GROQ:
        return OpenAI(
            api_key=GROQ_API_KEY,
            base_url=_GROQ_BASE_URL,
            timeout=timeout,
        )
    return OpenAI(api_key=OPENAI_API_KEY, timeout=timeout)


def get_model() -> str:
    """현재 활성 모델명 반환."""
    return _GROQ_MODEL if USE_GROQ else _OPENAI_MODEL


def is_available() -> bool:
    """AI 기능 사용 가능 여부. 서킷 브레이커 차단 중이면 False."""
    if is_rate_limited():
        return False
    return bool(GROQ_API_KEY or OPENAI_API_KEY)

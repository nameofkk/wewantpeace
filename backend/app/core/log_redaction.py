"""로그에서 비밀값을 가리는 필터.

2026-07-30 사고 배경:
텔레그램 Bot API는 토큰을 URL 경로에 넣는 규격이다 (`api.telegram.org/bot<TOKEN>/...`).
httpx가 INFO로 요청 URL을 찍기 때문에 워커 로그에 봇 토큰이 평문으로 남았고,
실제로 외부인이 그 토큰으로 봇에 자기 웹훅을 걸어 모든 업데이트를 가로챘다.

호출부 25곳을 고쳐도 URL에서 토큰을 뺄 수는 없다 (API 규격). 그래서 로그로
나가는 마지막 지점에서 가린다.
"""
from __future__ import annotations

import logging
import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # 텔레그램 봇 토큰: 123456789:AA... 형태가 URL 경로에 그대로 들어간다.
    (re.compile(r"bot\d{6,}:[A-Za-z0-9_-]{20,}"), "bot<REDACTED>"),
    (re.compile(r"\b\d{8,}:[A-Za-z0-9_-]{30,}\b"), "<REDACTED_TG_TOKEN>"),
    # 쿼리스트링으로 새는 흔한 비밀값
    (
        re.compile(r"((?:api_?key|access_token|auth_token|token|secret|password)=)[^&\s\"'>]+", re.I),
        r"\1<REDACTED>",
    ),
    # Authorization 헤더가 문자열로 찍히는 경우
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{16,}", re.I), r"\1<REDACTED>"),
]


def redact(text: str) -> str:
    """문자열에서 알려진 비밀값 패턴을 가린다."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactSecretsFilter(logging.Filter):
    """LogRecord의 메시지·인자에서 비밀값을 가린다 (레코드는 항상 통과시킴)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = redact(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: (redact(v) if isinstance(v, str) else v)
                        for k, v in record.args.items()
                    }
                elif isinstance(record.args, tuple):
                    record.args = tuple(
                        redact(a) if isinstance(a, str) else a for a in record.args
                    )
        except Exception:
            # 로깅이 절대 예외로 죽지 않게 한다 — 가리기 실패해도 로그는 남긴다.
            pass
        return True


_FILTER = RedactSecretsFilter()

# 토큰을 URL째로 찍는 것으로 확인된 로거들. 로거에 붙은 필터는 그 로거로
# 생성된 레코드에 반드시 적용되므로(propagate 여부와 무관) 가장 확실하다.
_KNOWN_NOISY_LOGGERS = ("httpx", "httpcore", "urllib3", "telethon", "aiohttp.client")


def install() -> None:
    """루트 핸들러 + 알려진 라이브러리 로거에 리댁션 필터를 건다. 여러 번 호출해도 안전."""
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, RedactSecretsFilter) for f in handler.filters):
            handler.addFilter(_FILTER)

    for name in _KNOWN_NOISY_LOGGERS:
        lg = logging.getLogger(name)
        if not any(isinstance(f, RedactSecretsFilter) for f in lg.filters):
            lg.addFilter(_FILTER)

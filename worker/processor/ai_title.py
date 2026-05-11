"""
GPT-4o-mini 기반 클러스터 AI 제목 생성.

이벤트 제목 + 본문을 종합하여 한/영 최적화 제목을 생성한다.
실패 시 기존 Google Translate 폴백.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

# 번역투 감지 패턴 (한국어 제목 후처리용)
_TRANSLATION_STYLE_RE = re.compile(
    r"(?:합니다|됩니다|입니다|있습니다|했습니다|됩니다|겠습니다|봅니다"
    r"|하고 있습니다|될 것입니다|할 수 있습니다"
    r"|을 예고합니다|을 발표합니다|을 시사합니다"
    r"|에서의 |으로의 |, 그리고 "
    r"|말했습니다|말했다|전했습니다|밝혔습니다"   # 보고동사
    r"|있습니까|합니까|겠습니까|일까요|ㄹ까요"    # 의문형
    r")[.!?。…]?$"                               # 후행 마침표 허용
)

from worker.ai_config import get_client as _get_ai_client, get_model as _get_ai_model, is_available as _ai_available, mark_rate_limited as _mark_rate_limited

_SYSTEM_PROMPT = """\
You are a concise news headline writer for a Korean conflict/crisis monitoring app.
Given event titles and article bodies about the same issue, write ONE best headline in both English and Korean.

Rules:
- English: min 30 chars, max 160 chars, AP style, no quotes
- Korean: min 10 chars, max 80 chars
- Read the article body carefully to understand the full context before writing the headline
- Focus on WHAT happened, WHERE — be specific and accurate
- Include specific details: country/city name, actor, action, number if available
- No hashtags, no emojis, no commentary
- Never start with "Recap", "Summary", "Breaking" or similar prefixes
- If titles are all junk/hashtags, infer from body content, topic and country
- Korean headline must be pure Korean (한국어만, no English mixed in except proper nouns)

## Korean headline style (매우 중요):
Write like a Korean news wire editor. Use 간결체/명사형 종결.

NEVER use these translation-style endings (번역투 금지):
- ~합니다, ~됩니다, ~입니다, ~있습니다, ~했습니다
- ~을 예고합니다, ~을 발표합니다, ~을 시사합니다
- ~하고 있습니다, ~될 것입니다, ~할 수 있습니다

ALWAYS end with these headline-style endings:
- 명사형: ~개시, ~발생, ~격화, ~돌입, ~체결, ~발표, ~시사, ~우려, ~확산, ~충돌
- 동사 간결체: ~밝혀, ~나서, ~시작, ~합의, ~철수, ~선언
- 쉼표+동사: ", ~개시", ", ~돌입", ", ~나서"

GOOD Korean examples:
- "레바논군, 남부 국경 헤즈볼라 거점에 군사작전 개시"
- "이스라엘-하마스 휴전 협상 결렬…가자 공습 재개"
- "미·중 무역전쟁 격화, 상호 관세 25%로 인상"
- "핀란드 NATO 훈련, '카렐리아 전선' 개방 가능성 시사"
- "우크라이나 동부 전선 교착…러 공세 3주째 소강"
- "수단 내전 6개월째, 민간인 사망자 1만 명 넘어"

BAD Korean examples (절대 이렇게 쓰지 마):
- "핀란드에서의 NATO 훈련은 '카렐리아 전선'의 잠재적 개방을 예고합니다" (번역투, ~합니다 종결)
- "중동 상황 악화" (too vague)
- "이스라엘이 가자에 대한 공격을 계속하고 있습니다" (번역투)
- "러시아 전문가가 경고를 발표했습니다" (번역투)

CRITICAL: Respond with ONLY a valid JSON object. No explanation, no markdown.
Format: {"title_en": "...", "title_ko": "..."}"""


def _build_user_prompt(
    titles: list[str],
    topic: str,
    country_code: str | None,
    bodies: list[str] | None = None,
) -> str:
    lines = [f"Topic: {topic}"]
    if country_code:
        lines.append(f"Country: {country_code}")
    lines.append("Event titles:")
    for i, t in enumerate(titles[:5], 1):
        lines.append(f"  {i}. {t[:200]}")
    if bodies:
        lines.append("\nArticle bodies (for context):")
        for i, b in enumerate(bodies[:3], 1):
            # 본문은 300자까지만 (토큰 절약)
            lines.append(f"  [{i}] {b[:300]}")
    return "\n".join(lines)


def generate_ai_title(
    events: list[dict],
    topic: str,
    country_code: str | None,
) -> tuple[str, str] | None:
    """
    GPT-4o-mini로 클러스터 제목 생성.

    Args:
        events: [{"title": "...", "body": "..."}, ...] 소속 이벤트 (최대 5개)
        topic: 클러스터 토픽
        country_code: 국가 코드 (ISO-2)

    Returns:
        (title_en, title_ko) 또는 실패 시 None
    """
    if not _ai_available():
        logger.debug("AI API 키 미설정, AI 제목 생성 건너뜀")
        return None

    titles = [e.get("title", "") for e in events if e.get("title")]
    if not titles:
        return None

    # 본문 수집 (있는 것만, 최대 3개)
    bodies = [e["body"] for e in events if e.get("body")][:3]

    try:
        client = _get_ai_client()
        resp = client.chat.completions.create(
            model=_get_ai_model(),
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(titles, topic, country_code, bodies or None)},
            ],
            temperature=0.3,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)
        title_en = data.get("title_en", "").strip()
        title_ko = data.get("title_ko", "").strip()
        if not title_en or not title_ko:
            logger.warning("AI 제목 응답 불완전: %s", raw[:200])
            return None
        if len(title_en) < 5 or len(title_ko) < 2:
            logger.warning("AI 제목 너무 짧음 (en=%d, ko=%d): %s", len(title_en), len(title_ko), raw[:200])
            return None
        # 번역투 감지 → 1회 재시도
        if _TRANSLATION_STYLE_RE.search(title_ko):
            logger.info("번역투 감지, 재시도: %s", title_ko)
            try:
                retry_prompt = (
                    _build_user_prompt(titles, topic, country_code, bodies or None)
                    + "\n\n⚠️ 이전 한국어 제목이 번역투였습니다: \""
                    + title_ko
                    + "\"\n간결체/명사형으로 다시 작성하세요. 예: '레바논군, 헤즈볼라 거점에 군사작전 개시'"
                )
                resp2 = client.chat.completions.create(
                    model=_get_ai_model(),
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": retry_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=200,
                    response_format={"type": "json_object"},
                )
                raw2 = resp2.choices[0].message.content
                data2 = json.loads(raw2)
                retry_ko = data2.get("title_ko", "").strip()
                retry_en = data2.get("title_en", "").strip()
                if retry_ko and not _TRANSLATION_STYLE_RE.search(retry_ko):
                    title_ko = retry_ko
                    if retry_en and len(retry_en) >= 5:
                        title_en = retry_en
                    logger.info("번역투 재시도 성공: %s", title_ko)
                else:
                    logger.warning("번역투 재시도도 실패, 원본 사용: %s", title_ko)
            except Exception:
                logger.warning("번역투 재시도 예외, 원본 사용: %s", title_ko)
        # 길이 제한 적용
        if len(title_en) > 160:
            title_en = title_en[:158] + "…"
        if len(title_ko) > 80:
            title_ko = title_ko[:78] + "…"
        logger.info("AI 제목 생성: en=%s / ko=%s", title_en[:50], title_ko)
        return title_en, title_ko
    except Exception as _exc:
        # 일일 토큰 한도 429 → 서킷 브레이커 (트레이스백 스팸 없이 조용히 차단)
        try:
            from openai import RateLimitError as _RateLimitError
            if isinstance(_exc, _RateLimitError):
                _wait = 86400.0
                _m = re.search(r"try again in (\d+)m([\d.]+)s", str(_exc))
                if _m:
                    _wait = int(_m.group(1)) * 60 + float(_m.group(2)) + 30
                _mark_rate_limited(_wait)
                return None
        except Exception:
            pass
        logger.exception("AI 제목 생성 실패")
        return None

"""
GPT-4o-mini 기반 클러스터 AI 제목 생성.

이벤트 제목들을 종합하여 한/영 최적화 제목을 생성한다.
실패 시 기존 Google Translate 폴백.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

_SYSTEM_PROMPT = """\
You are a concise news headline writer for a global conflict/crisis monitoring app.
Given a list of event titles about the same issue, write ONE best headline in both English and Korean.

Rules:
- English: max 80 chars, AP style, no quotes
- Korean: max 40 chars, 뉴스 헤드라인 스타일, 간결체
- Focus on WHAT happened, WHERE
- No hashtags, no emojis, no commentary
- If titles are all junk/hashtags, infer from topic and country

Respond ONLY with JSON: {"title_en": "...", "title_ko": "..."}"""


def _build_user_prompt(
    titles: list[str],
    topic: str,
    country_code: str | None,
) -> str:
    lines = [f"Topic: {topic}"]
    if country_code:
        lines.append(f"Country: {country_code}")
    lines.append("Event titles:")
    for i, t in enumerate(titles[:5], 1):
        lines.append(f"  {i}. {t[:200]}")
    return "\n".join(lines)


def generate_ai_title(
    events: list[dict],
    topic: str,
    country_code: str | None,
) -> tuple[str, str] | None:
    """
    GPT-4o-mini로 클러스터 제목 생성.

    Args:
        events: [{"title": "..."}, ...] 소속 이벤트 (최대 5개)
        topic: 클러스터 토픽
        country_code: 국가 코드 (ISO-2)

    Returns:
        (title_en, title_ko) 또는 실패 시 None
    """
    if not _OPENAI_KEY:
        logger.debug("OPENAI_API_KEY 미설정, AI 제목 생성 건너뜀")
        return None

    titles = [e.get("title", "") for e in events if e.get("title")]
    if not titles:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=_OPENAI_KEY)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(titles, topic, country_code)},
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
        # 길이 제한 적용
        if len(title_en) > 80:
            title_en = title_en[:78] + "…"
        if len(title_ko) > 40:
            title_ko = title_ko[:38] + "…"
        logger.info("AI 제목 생성: en=%s / ko=%s", title_en[:50], title_ko)
        return title_en, title_ko
    except Exception:
        logger.exception("AI 제목 생성 실패")
        return None

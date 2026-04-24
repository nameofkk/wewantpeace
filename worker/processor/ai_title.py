"""
GPT-4o-mini 기반 클러스터 AI 제목 생성.

이벤트 제목 + 본문을 종합하여 한/영 최적화 제목을 생성한다.
실패 시 기존 Google Translate 폴백.
"""
import json
import logging

logger = logging.getLogger(__name__)

from worker.ai_config import get_client as _get_ai_client, get_model as _get_ai_model, is_available as _ai_available

_SYSTEM_PROMPT = """\
You are a concise news headline writer for a global conflict/crisis monitoring app.
Given event titles and article bodies about the same issue, write ONE best headline in both English and Korean.

Rules:
- English: min 30 chars, max 160 chars, AP style, no quotes
- Korean: min 10 chars, max 80 chars, 뉴스 헤드라인 스타일, 간결체
- Read the article body carefully to understand the full context before writing the headline
- Focus on WHAT happened, WHERE — be specific and accurate
- Include specific details: country/city name, actor, action, number if available
- No hashtags, no emojis, no commentary
- Never start with "Recap", "Summary", "Breaking" or similar prefixes
- If titles are all junk/hashtags, infer from body content, topic and country
- Korean headline must be pure Korean (한국어만, no English mixed in except proper nouns)

GOOD examples:
- EN: "Lebanon Military Launches Operation Against Hezbollah Positions in Southern Border"
- KO: "레바논군, 남부 국경 헤즈볼라 거점에 군사작전 개시"

BAD examples:
- EN: "Conflict Update" (too vague)
- KO: "중동 상황 악화" (too vague, no specifics)

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
        # 길이 제한 적용
        if len(title_en) > 160:
            title_en = title_en[:158] + "…"
        if len(title_ko) > 80:
            title_ko = title_ko[:78] + "…"
        logger.info("AI 제목 생성: en=%s / ko=%s", title_en[:50], title_ko)
        return title_en, title_ko
    except Exception:
        logger.exception("AI 제목 생성 실패")
        return None

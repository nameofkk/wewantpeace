"""
폴백 vs AI 제목 심층 비교 + 개선 포인트 식별.
"""
import asyncio, sys, re
sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from worker.processor.clusterer import (
    _fix_translation_style, _make_cluster_title_ko, _is_junk_title,
    _translate_cached,
)
from worker.processor.ai_title import _TRANSLATION_STYLE_RE as _ai_bad_re

PROD_DB = (
    "postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:"
    "WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
)

_EMOJI_RE = re.compile(
    r'[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE00-\uFE0F'
    r'\u200D\u20E3\U000E0020-\U000E007F'
    r'\U0001F1E0-\U0001F1FF⚡️🔴🟠🟡🟢⚠️🚨📰💥🔥❗️‼️]+'
)

def classify_diff(ai: str, fb: str) -> list[str]:
    """AI vs FB 제목의 차이 분류."""
    tags = []
    if ai == fb:
        return ["동일"]

    # AI 번역투
    if _ai_bad_re.search(ai) and not _ai_bad_re.search(fb):
        tags.append("FB가_번역투제거")

    # 이모지
    if _EMOJI_RE.search(ai) and not _EMOJI_RE.search(fb):
        tags.append("FB가_이모지제거")
    if _EMOJI_RE.search(fb) and not _EMOJI_RE.search(ai):
        tags.append("FB에_이모지남음")

    # 마크다운
    if '**' in ai and '**' not in fb:
        tags.append("FB가_마크다운제거")
    if '**' in fb and '**' not in ai:
        tags.append("FB에_마크다운남음")

    # 불완전 문장
    if re.search(r'[이가은는을를]\s*$', fb):
        tags.append("FB_불완전문장(조사dangling)")
    if re.search(r'[가-힣]고\s*$', fb):
        tags.append("FB_고dangling")
    if re.search(r'(?:았|었|됐|겠|받)\s*$', fb):
        tags.append("FB_동사어간dangling")
    if re.search(r'(?:다고|라고|고)\s*$', fb):
        tags.append("FB_접속사dangling")

    # AI 마침표 제거됨 (FB에서)
    if ai.endswith('.') and not fb.endswith('.'):
        tags.append("FB_마침표제거(good)")

    # 길이 차이
    len_diff = len(ai) - len(fb)
    if len_diff > 15:
        tags.append(f"FB가_짧음({len_diff}자)")
    elif len_diff < -10:
        tags.append(f"FB가_긺({-len_diff}자)")

    # 주어 쉼표 변환 확인
    if re.match(r'^[가-힣]{2,8},\s', fb) and not re.match(r'^[가-힣]{2,8},\s', ai):
        tags.append("FB_쉼표변환적용")

    if not tags:
        tags.append("기타차이")
    return tags


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(PROD_DB, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        rows = await db.execute(text("""
            SELECT title, title_ko, topic, country_code, kscore
            FROM issue_clusters
            WHERE is_active = true
              AND title IS NOT NULL AND title != ''
              AND title_ko IS NOT NULL AND title_ko != ''
            ORDER BY kscore DESC
            LIMIT 300
        """))
        clusters = rows.fetchall()
    await engine.dispose()
    print(f"로드: {len(clusters)}개\n")

    tag_counts: dict[str, int] = {}
    problem_cases: list[dict] = []
    good_cases: list[dict] = []

    for row in clusters:
        title, title_ko, topic, cc, kscore = row
        fb = _make_cluster_title_ko(title, topic, cc)
        tags = classify_diff(title_ko, fb)

        for t in tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1

        # 문제 케이스 수집
        bad_tags = [t for t in tags if any(x in t for x in [
            "남음", "dangling", "FB가_짧음", "기타차이"
        ])]
        if bad_tags:
            problem_cases.append({
                "kscore": kscore, "en": title, "ai": title_ko,
                "fb": fb, "tags": tags, "topic": topic, "cc": cc,
            })
        elif "FB가_번역투제거" in tags or "FB_쉼표변환적용" in tags or "FB_마침표제거(good)" in tags:
            good_cases.append({
                "kscore": kscore, "en": title, "ai": title_ko,
                "fb": fb, "tags": tags,
            })

    # ── 전체 차이 태그 집계 ────────────────────────────────────────────────────
    print("=" * 65)
    print("  차이 유형별 집계 (300개 기준)")
    print("=" * 65)
    for tag, cnt in sorted(tag_counts.items(), key=lambda x: -x[1]):
        pct = cnt / len(clusters) * 100
        print(f"  {tag:<35}: {cnt:>4}건 ({pct:.1f}%)")

    # ── 문제 케이스 전체 출력 ──────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  문제 케이스 전체 ({len(problem_cases)}건) — 개선 필요")
    print(f"{'='*65}")
    for item in sorted(problem_cases, key=lambda x: -x["kscore"])[:40]:
        print(f"\n  kscore={item['kscore']:.1f} | {item['topic']}/{item['cc']}")
        print(f"    EN  : {item['en'][:70]}")
        print(f"    AI  : {item['ai']}")
        print(f"    FB  : {item['fb']}")
        print(f"    Tags: {', '.join(item['tags'])}")

    # ── 폴백이 AI보다 나은 케이스 ─────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  폴백이 AI보다 나은 케이스 ({len(good_cases)}건) — 확인용")
    print(f"{'='*65}")
    for item in sorted(good_cases, key=lambda x: -x["kscore"])[:20]:
        print(f"\n  kscore={item['kscore']:.1f}")
        print(f"    AI: {item['ai']}")
        print(f"    FB: {item['fb']}")
        print(f"    Tags: {', '.join(item['tags'])}")

    # ── Google Translate 원본과 후처리 결과 비교 ──────────────────────────────
    print(f"\n{'='*65}")
    print(f"  번역→후처리 변환 샘플 (랜덤 20개)")
    print(f"{'='*65}")
    import random
    sample = random.sample(clusters, min(20, len(clusters)))
    for row in sample:
        title, title_ko, topic, cc, kscore = row
        if _is_junk_title(title):
            continue
        raw_trans = _translate_cached(title)
        fixed = _fix_translation_style(raw_trans or "") if raw_trans else "(번역실패)"
        if raw_trans and raw_trans != fixed:
            print(f"\n  EN  : {title[:65]}")
            print(f"  RAW : {raw_trans}")
            print(f"  FIXED: {fixed}")

asyncio.run(main())

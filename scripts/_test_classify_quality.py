"""
AI 분류 vs 폴백 분류 품질 비교 분석.
실제 DB에서 이벤트를 샘플링해 AI 분류 결과와 규칙 기반 폴백을 비교.
"""
import asyncio
import sys
import re
from collections import defaultdict

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from worker.processor.normalizer import (
    _classify_topic,
    _classify_sub_topic,
    _calculate_severity,
    _extract_geo,
    _has_terror_diplomatic_context,
    _has_non_military_context,
    _is_entertainment_noise,
)

PROD_DB = (
    "postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:"
    "WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
)

# ── 통계용 ────────────────────────────────────────────────────────────────────
topic_match = 0
topic_mismatch = 0
country_match = 0
country_mismatch = 0
country_null = 0
severity_diffs = []
mismatch_cases = []
good_cases = []


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(PROD_DB, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        rows = await db.execute(text("""
            SELECT
                ne.title,
                ne.body,
                ne.topic,
                ne.sub_topic,
                ne.severity,
                ne.country_code
            FROM normalized_events ne
            WHERE ne.topic IS NOT NULL
              AND ne.topic != 'unknown'
              AND ne.title IS NOT NULL
              AND ne.title != ''
              AND ne.severity > 20
            ORDER BY ne.created_at DESC
            LIMIT 500
        """))
        events = rows.fetchall()
    await engine.dispose()
    print(f"로드: {len(events)}개\n")

    for row in events:
        title, body, ai_topic, ai_sub, ai_sev, ai_cc = row
        text_for_analysis = f"{title or ''} {body or ''}".strip()

        # 폴백 분류
        fb_topic = _classify_topic(text_for_analysis)
        fb_sub = _classify_sub_topic(text_for_analysis, fb_topic)
        fb_sev = _calculate_severity(text_for_analysis, fb_topic, title=title)
        fb_cc, _, _ = _extract_geo(text_for_analysis, title=title)

        # ── 토픽 비교 ──────────────────────────────────────────────────────────
        global topic_match, topic_mismatch, country_match, country_mismatch, country_null

        topic_ok = (ai_topic == fb_topic)
        if topic_ok:
            topic_match += 1
        else:
            topic_mismatch += 1

        # ── 국가코드 비교 ──────────────────────────────────────────────────────
        if ai_cc:
            if fb_cc == ai_cc:
                country_match += 1
            else:
                country_mismatch += 1
        else:
            country_null += 1

        # ── 심각도 차이 ────────────────────────────────────────────────────────
        if ai_sev is not None:
            severity_diffs.append(abs(ai_sev - fb_sev))

        # ── 케이스 수집 ────────────────────────────────────────────────────────
        entry = {
            "title": title[:80],
            "ai_topic": ai_topic,
            "fb_topic": fb_topic,
            "ai_sub": ai_sub,
            "fb_sub": fb_sub,
            "ai_sev": ai_sev,
            "fb_sev": fb_sev,
            "ai_cc": ai_cc,
            "fb_cc": fb_cc,
        }
        if not topic_ok:
            mismatch_cases.append(entry)

    total = len(events)

    # ── 전체 통계 ─────────────────────────────────────────────────────────────
    print("=" * 65)
    print("  전체 통계 (AI 분류 vs 폴백 분류 비교)")
    print("=" * 65)
    print(f"  총 이벤트 수          : {total}")
    print(f"  토픽 일치             : {topic_match} ({topic_match/total*100:.1f}%)")
    print(f"  토픽 불일치           : {topic_mismatch} ({topic_mismatch/total*100:.1f}%)")
    if severity_diffs:
        avg_sev = sum(severity_diffs) / len(severity_diffs)
        over_20 = sum(1 for d in severity_diffs if d > 20)
        print(f"  심각도 평균차이       : {avg_sev:.1f}점")
        print(f"  심각도 차이 20점 이상 : {over_20}건 ({over_20/total*100:.1f}%)")
    has_cc = total - country_null
    if has_cc:
        print(f"  국가코드 일치         : {country_match}/{has_cc} ({country_match/has_cc*100:.1f}%)")
        print(f"  국가코드 불일치       : {country_mismatch}/{has_cc} ({country_mismatch/has_cc*100:.1f}%)")
    print(f"  AI 국가코드 없음      : {country_null}")

    # ── 토픽별 불일치 집계 ─────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  토픽 불일치 패턴 분석 (AI → 폴백)")
    print(f"{'='*65}")
    mismatch_patterns: dict[str, int] = defaultdict(int)
    for c in mismatch_cases:
        key = f"{c['ai_topic']:12s} → {c['fb_topic']}"
        mismatch_patterns[key] += 1
    for pattern, cnt in sorted(mismatch_patterns.items(), key=lambda x: -x[1]):
        pct = cnt / topic_mismatch * 100
        print(f"  {pattern}  : {cnt:>4}건 ({pct:.1f}%)")

    # ── 불일치 케이스 샘플 ─────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  불일치 케이스 TOP 30 (AI topic ≠ 폴백 topic)")
    print(f"{'='*65}")

    # AI topic 별로 그룹화해서 출력
    by_ai_topic: dict[str, list] = defaultdict(list)
    for c in mismatch_cases:
        by_ai_topic[c["ai_topic"]].append(c)

    shown = 0
    for ai_topic in ["diplomacy", "conflict", "terror", "sanctions", "protest", "disaster", "health", "cyber", "maritime", "coup"]:
        cases = by_ai_topic.get(ai_topic, [])
        if not cases:
            continue
        print(f"\n  ── AI:{ai_topic} → 폴백 오분류 ({len(cases)}건) ──")
        for c in cases[:5]:
            print(f"    FB:{c['fb_topic']:12s} | {c['title'][:65]}")
        shown += len(cases[:5])
        if shown >= 30:
            break


# ── 2. 분류 규칙 직접 테스트 ─────────────────────────────────────────────────
def test_known_cases():
    """AI 프롬프트와 동일한 경계 케이스 규칙 기반 검증."""
    print(f"\n{'='*65}")
    print("  AI 프롬프트 경계 케이스 검증 (폴백 분류 정합성)")
    print(f"{'='*65}\n")

    cases = [
        # (텍스트, AI기대topic, 설명)
        ("IDF airstrikes kill 60 militants in Rafah", "conflict", "군사 작전 → conflict"),
        ("US designates Houthi group as terrorist organization", "diplomacy", "조직 지정 → diplomacy"),
        ("Suicide bomber kills 50 at market in Baghdad", "terror", "테러 공격 → terror"),
        ("US imposes new sanctions on Iran over nuclear program", "sanctions", "제재 → sanctions"),
        ("Protesters take to streets over economic crisis", "protest", "시위 → protest"),
        ("Hamas and Israel ceasefire talks in Qatar", "diplomacy", "휴전 협상 → diplomacy"),
        ("7.8 magnitude earthquake strikes Turkey, 2000 dead", "disaster", "재해 → disaster"),
        ("North Korea fires ICBM toward Sea of Japan", "conflict", "北 미사일 → conflict"),
        ("Ransomware attack shuts down hospital systems", "cyber", "사이버 → cyber"),
        ("Houthi attacks disrupt Red Sea shipping", "maritime", "해상 → maritime"),
        ("Military junta arrests elected president", "coup", "쿠데타 → coup"),
        ("Measles outbreak kills 100 in Congo", "health", "보건 → health"),
        ("BTS concert draws record crowd in Seoul", "unknown", "엔터 → unknown"),
        ("Travel advisory: Level 3 Do Not Travel to Syria", "diplomacy", "여행 경보 → diplomacy"),
        ("Russia conducts military exercise near NATO border", "conflict", "군사 훈련 → conflict"),
        ("Analysis: Will the Gaza war escalate?", "conflict", "분석 기사 → conflict (낮은 severity)"),
    ]

    all_ok = True
    for text, expected_topic, desc in cases:
        fb_topic = _classify_topic(text)
        ok = "✓" if fb_topic == expected_topic else "✗ FAIL"
        if fb_topic != expected_topic:
            all_ok = False
        print(f"  {ok} [{desc}]")
        print(f"       텍스트: {text[:65]}")
        print(f"       기대: {expected_topic}, 실제: {fb_topic}")
        if fb_topic != expected_topic:
            # 추가 디버그
            has_td = _has_terror_diplomatic_context(text.lower())
            has_nm = _has_non_military_context(text.lower())
            print(f"       terror_diplomatic={has_td}, non_military={has_nm}")
        print()

    print(f"  결과: {'모두 통과 ✓' if all_ok else '일부 실패 ✗'}")


test_known_cases()
asyncio.run(main())

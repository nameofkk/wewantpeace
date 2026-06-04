"""
AI 생성 제목 vs 폴백 제목 품질 비교 분석.
실제 DB에서 대량 샘플을 뽑아 diff를 분석한다.
"""
import asyncio
import sys
import re

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from worker.processor.clusterer import (
    _fix_translation_style,
    _make_fallback_titles,
    _make_cluster_title_ko,
    _is_junk_title,
)

# ai_title.py의 번역투 감지 패턴도 가져오기
from worker.processor.ai_title import _TRANSLATION_STYLE_RE as _ai_trans_re

PROD_DB = (
    "postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:"
    "WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
)


async def load_clusters(limit=200):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(PROD_DB, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        rows = await db.execute(text(f"""
            SELECT title, title_ko, topic, country_code, kscore, event_count
            FROM issue_clusters
            WHERE is_active = true
              AND title IS NOT NULL
              AND title != ''
            ORDER BY kscore DESC
            LIMIT {limit}
        """))
        result = rows.fetchall()
    await engine.dispose()
    return result


def score_title(title_ko: str | None) -> dict:
    """제목 품질 점수 (0~100)."""
    if not title_ko:
        return {"score": 0, "issues": ["없음"]}
    issues = []
    score = 100

    # 번역투 어미 감지
    if _ai_trans_re.search(title_ko):
        issues.append("번역투어미")
        score -= 30

    # 너무 짧음
    if len(title_ko) < 8:
        issues.append("너무짧음")
        score -= 20

    # 너무 긺
    if len(title_ko) > 70:
        issues.append("너무긺")
        score -= 10

    # 영문 이름만 있는 경우 (한국어 없음)
    ko_chars = len(re.findall(r'[가-힣]', title_ko))
    if ko_chars < 4:
        issues.append("한국어부족")
        score -= 25

    # 이모지 포함
    emoji_re = re.compile(r'[\U0001F000-\U0001FFFF\u2600-\u27BF]')
    if emoji_re.search(title_ko):
        issues.append("이모지포함")
        score -= 15

    # 마크다운 강조 포함 (**텍스트**)
    if '**' in title_ko:
        issues.append("마크다운포함")
        score -= 10

    # 불완전 문장 (주어만 남은 경우: 마지막 글자가 이/가/은/는)
    if re.search(r'[이가은는을를]\s*$', title_ko):
        issues.append("불완전문장")
        score -= 20

    # 문장 끝에 조사/접속사 dangling
    if re.search(r'(?:했|됐|겠|받|쳤|쳤)$', title_ko):
        issues.append("동사어간dangling")
        score -= 10

    return {"score": max(0, score), "issues": issues}


async def main():
    print("프로덕션 DB에서 클러스터 200개 로드 중...")
    clusters = await load_clusters(200)
    print(f"로드됨: {len(clusters)}개\n")

    stats = {
        "total": len(clusters),
        "junk_en": 0,          # 영문 제목이 junk
        "ai_번역투": 0,         # AI 제목이 번역투
        "fallback_better": 0,  # 폴백이 AI보다 좋음
        "fallback_worse": 0,   # 폴백이 AI보다 나쁨
        "same": 0,             # 동일
        "no_ai": 0,            # AI 제목 없음
    }

    problems = []   # (kscore, en, ai_ko, fb_ko, issue)
    good_fb = []    # 폴백이 잘 나온 케이스
    bad_fb = []     # 폴백이 나쁜 케이스

    for row in clusters:
        title, title_ko, topic, cc, kscore, event_count = row
        is_junk = _is_junk_title(title)
        if is_junk:
            stats["junk_en"] += 1

        fallback_ko = _make_cluster_title_ko(title, topic, cc)
        fb_score = score_title(fallback_ko)
        ai_score = score_title(title_ko)

        if not title_ko:
            stats["no_ai"] += 1
        elif _ai_trans_re.search(title_ko):
            stats["ai_번역투"] += 1

        if title_ko == fallback_ko:
            stats["same"] += 1
        elif fb_score["score"] > ai_score["score"]:
            stats["fallback_better"] += 1
        elif fb_score["score"] < ai_score["score"]:
            stats["fallback_worse"] += 1
            if fb_score["score"] < 60 or ai_score["score"] - fb_score["score"] > 20:
                bad_fb.append({
                    "kscore": kscore,
                    "en": title,
                    "ai": title_ko,
                    "fb": fallback_ko,
                    "ai_score": ai_score,
                    "fb_score": fb_score,
                    "topic": topic,
                    "cc": cc,
                })
        else:
            stats["same"] += 1
            if fb_score["score"] >= 80 and not is_junk and title_ko != fallback_ko:
                good_fb.append({
                    "kscore": kscore,
                    "en": title,
                    "ai": title_ko,
                    "fb": fallback_ko,
                    "fb_score": fb_score,
                })

    # ── 통계 출력 ─────────────────────────────────────────────────────────────
    print("=" * 65)
    print("  전체 통계")
    print("=" * 65)
    print(f"  전체 클러스터     : {stats['total']}")
    print(f"  영문 junk 제목    : {stats['junk_en']} ({stats['junk_en']/stats['total']*100:.1f}%)")
    print(f"  AI 제목 없음      : {stats['no_ai']}")
    print(f"  AI 번역투 제목    : {stats['ai_번역투']}")
    print(f"  폴백이 AI보다 좋음: {stats['fallback_better']}")
    print(f"  폴백이 AI보다 나쁨: {stats['fallback_worse']}")
    print(f"  동일/유사         : {stats['same']}")

    # ── 폴백이 나쁜 케이스 ─────────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  폴백 품질 나쁜 케이스 TOP {min(30, len(bad_fb))} (개선 대상)")
    print(f"{'='*65}")
    bad_fb_sorted = sorted(bad_fb, key=lambda x: x["fb_score"]["score"])
    for item in bad_fb_sorted[:30]:
        print(f"\n  kscore={item['kscore']:.1f} | {item['topic']}/{item['cc']}")
        print(f"    EN: {item['en'][:70]}")
        print(f"    AI: {item['ai']}")
        print(f"    FB: {item['fb']}  [score={item['fb_score']['score']}, issues={item['fb_score']['issues']}]")

    # ── 폴백이 잘 나온 케이스 ──────────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  폴백 품질 우수 케이스 (AI와 비슷한 수준)")
    print(f"{'='*65}")
    for item in good_fb[:15]:
        print(f"\n  kscore={item['kscore']:.1f}")
        print(f"    EN: {item['en'][:70]}")
        print(f"    AI: {item['ai']}")
        print(f"    FB: {item['fb']}  [score={item['fb_score']['score']}]")

    # ── 자주 나타나는 패턴 분류 ───────────────────────────────────────────────
    print(f"\n{'='*65}")
    print(f"  폴백 이슈 유형별 집계")
    print(f"{'='*65}")
    issue_counts: dict[str, int] = {}
    for item in bad_fb:
        for issue in item["fb_score"]["issues"]:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    for issue, cnt in sorted(issue_counts.items(), key=lambda x: -x[1]):
        print(f"    {issue:<20}: {cnt}건")


asyncio.run(main())

"""
AI 소진 시 이슈 클러스터 제목 폴백 품질 테스트.
번역투 후처리, junk 판정, 실 DB 클러스터 제목 변환 검증.
"""
import asyncio
import os
import sys

sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from worker.processor.clusterer import (
    _fix_translation_style,
    _make_fallback_titles,
    _make_cluster_title_ko,
    _is_junk_title,
)


def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ── 1. 번역투 후처리 테스트 ─────────────────────────────────────────────────
section("1. 번역투 다양한 패턴 → 간결체 변환")

trans_cases = [
    "이스라엘이 가자에 대한 공습을 재개합니다",
    "러시아가 우크라이나 동부 공세를 강화하고 있습니다",
    "북한이 탄도 미사일을 발사했습니다",
    "유엔이 인도주의적 위기에 대한 우려를 발표합니다",
    "미국이 이란에 추가 경제 제재를 시사합니다",
    "핀란드 NATO 훈련은 카렐리아 전선의 개방을 예고합니다",
    "회담 결과가 전쟁 종식 가능성을 시사합니다",
    "유엔이 즉각적인 휴전을 촉구합니다",
    "사상자가 500명을 넘어섰다고 합니다",
    "러시아가 협상에 동의했다고 밝혔습니다",
    "레바논에서의 분쟁이 계속되고 있습니다",
    "시리아에서의 난민 위기가 악화됩니다",
    "이스라엘-하마스 휴전 협상 결렬…가자 공습 재개",  # 이미 깔끔
    "우크라이나 동부 전선 교착, 러 공세 소강",        # 이미 깔끔
    "수단 내전 6개월째, 민간인 사망자 1만 명 넘어",   # 이미 깔끔
    "미얀마군, 국경 지역 반군 거점에 군사작전 개시",   # 이미 깔끔
]

for t in trans_cases:
    out = _fix_translation_style(t)
    tag = " [변환]" if out != t else " [변경없음]"
    print(f"  IN : {t}")
    print(f"  OUT: {out}{tag}")
    print()


# ── 2. Junk 제목 판정 테스트 ─────────────────────────────────────────────────
section("2. 이모지/국기/해시태그 junk 판정")

junk_cases = [
    # (title, expected_junk, desc)
    ("🇮🇱⚡️ #Israel #Gaza #Breaking", True, "국기+이모지+해시태그"),
    ("🔴🟠 #Russia #Ukraine", True, "이모지+해시태그"),
    ("#북한 #미사일 🚀💥", True, "한글해시태그+이모지"),
    ("⚡️⚡️ #Syria", True, "이모지+해시태그만"),
    ("🚨🔥 BREAKING #Lebanon", True, "Breaking+이모지+해시태그"),
    ("🇺🇦🇷🇺 Conflict Update", True, "국기만+2단어"),
    ("Good morning from Beirut", True, "인사 패턴"),
    ("Morning Recap", True, "뉴스 메타"),
    ("Daily Briefing: Ukraine", True, "뉴스 메타+국가"),
    ("Breaking: Live Update:", True, "Live Update 패턴"),
    ("Tehran 20 February 2026 #1", True, "날짜+도시"),
    ("China Diplomacy", True, "국가+토픽2단어"),
    ("Lebanon Disaster", True, "국가+토픽2단어"),
    # 정상 제목 (junk 아님)
    ("Israel resumes airstrikes on Gaza after ceasefire", False, "정상 영문"),
    ("North Korea fires ballistic missile toward Sea of Japan", False, "정상 영문 긴"),
    ("Russia conducts massive drone attack on Kyiv", False, "정상 영문"),
    ("Sudan civil war enters 6th month, 10,000+ deaths", False, "숫자포함 정상"),
    ("미얀마군, 국경 지역 반군 거점에 군사작전 개시", False, "정상 한국어"),
    ("이스라엘-하마스 휴전 협상 결렬…가자 공습 재개", False, "정상 한국어"),
]

all_pass = True
for title, expected, desc in junk_cases:
    result = _is_junk_title(title)
    ok = "✓" if result == expected else "✗ FAIL"
    if result != expected:
        all_pass = False
    print(f"  {ok} [{desc}] junk={result}: {title[:55]}")

print(f"\n  결과: {'모두 통과 ✓' if all_pass else '일부 실패 ✗'}")


# ── 3. _make_cluster_title_ko 엔드-투-엔드 ─────────────────────────────────
section("3. _make_cluster_title_ko 엔드-투-엔드 (Google Translate 포함)")

print("  ※ Google Translate 실제 호출 — 네트워크 필요\n")

e2e_cases = [
    # (title, topic, country_code, desc)
    ("Israel resumes airstrikes on Gaza after ceasefire collapse", "conflict", "IL", "이스라엘 공습"),
    ("Russia conducts massive drone attack on Ukrainian infrastructure", "conflict", "RU", "러시아 드론"),
    ("North Korea fires ballistic missile toward Sea of Japan", "conflict", "KP", "북한 미사일"),
    ("UN Security Council demands immediate ceasefire in Sudan", "diplomacy", "SD", "유엔 휴전 요구"),
    ("US imposes new sanctions on Iran over nuclear program", "sanctions", "IR", "미국 이란 제재"),
    ("Myanmar military junta arrests hundreds of protesters", "coup", "MM", "미얀마 쿠데타"),
    ("Lebanon-Israel border clashes intensify after overnight shelling", "conflict", "LB", "레바논 교전"),
    ("Hamas and Israel reach temporary ceasefire agreement in Qatar talks", "diplomacy", "IL", "협상 합의"),
    # junk 제목들 → 폴백
    ("🇮🇱⚡️ #Israel #Gaza #Breaking", "conflict", "IL", "junk: 이스라엘"),
    ("#Russia #Ukraine 🔥", "conflict", "UA", "junk: 우크라"),
    ("Morning Recap", "diplomacy", "US", "junk: 메타"),
    ("Tehran 20 February 2026 #1", "conflict", "IR", "junk: 날짜"),
    ("🇸🇩 Sudan Crisis 🔴", "disaster", "SD", "junk: 수단"),
    ("China Diplomacy", "diplomacy", "CN", "junk: 2단어"),
]

for title, topic, cc, desc in e2e_cases:
    result = _make_cluster_title_ko(title, topic, cc)
    is_junk = _is_junk_title(title)
    tag = "[junk폴백]" if is_junk else "[번역+후처리]"
    print(f"  [{desc}] {tag}")
    print(f"    EN: {title[:60]}")
    print(f"    KO: {result}")
    print()


# ── 4. 실제 DB 클러스터 샘플 ─────────────────────────────────────────────────
section("4. 실제 프로덕션 DB 클러스터 샘플 (AI 폴백 적용 시)")

async def test_real_clusters():
    prod_db = (
        "postgresql+asyncpg://postgres.smxitufpgfuzepldglfo:"
        "WwpAdmin2026@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres"
    )
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import text

        engine = create_async_engine(prod_db, echo=False)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as db:
            rows = await db.execute(text("""
                SELECT title, title_ko, topic, country_code, kscore
                FROM issue_clusters
                WHERE is_active = true
                ORDER BY kscore DESC
                LIMIT 20
            """))
            clusters = rows.fetchall()

        print(f"  상위 20개 활성 클러스터 — 폴백 적용 시 KO 제목 비교:\n")
        for row in clusters:
            title, title_ko, topic, cc, kscore = row
            # AI 없이 폴백 제목이면 어떻게 나왔을지 시뮬레이션
            fallback_ko = _make_cluster_title_ko(title, topic, cc)
            current_tag = "[AI생성]" if title_ko else "[누락]"
            print(f"  kscore={kscore:.1f} | {topic}/{cc}")
            print(f"    현재 EN : {(title or '')[:60]}")
            print(f"    현재 KO {current_tag}: {title_ko or '(없음)'}")
            print(f"    폴백 KO : {fallback_ko}")
            print()

        await engine.dispose()
    except Exception as e:
        print(f"  DB 연결 실패: {e}")
        print("  (로컬 환경이거나 네트워크 없음 — 3번까지만 확인)")

asyncio.run(test_real_clusters())

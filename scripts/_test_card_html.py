#!/usr/bin/env python3
"""HTML 카드 생성기 로컬 테스트.

Usage:
    cd ~/Projects/wewantpeace
    python scripts/_test_card_html.py

Output:
    test_card_alert.png   — kscore_alert (BREAKING NEWS)
    test_card_daily.png   — daily_movers (DAILY BRIEF)
    test_card_weekly.png  — weekly_recap (WEEK IN REVIEW)
"""
from __future__ import annotations

import sys
import os

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from worker.social.card_html_generator import generate_html_card

# ── 샘플 데이터 ───────────────────────────────────────────────────────────────

ISSUES = [
    {
        "title_en": "Russia Launches Overnight Missile Strike on Kyiv",
        "title_ko": "러시아, 키이우에 야간 미사일 공습",
        "country_code": "UA",
        "severity": 85,
        "independent_sources": 3,
        "source_tiers": ["t1"],
        "is_verified": True,
        "event_count": 7,
    },
    {
        "title_en": "IDF Expands Ground Operations in Northern Gaza",
        "title_ko": "IDF, 가자 북부 지상 작전 확대",
        "country_code": "PS",
        "severity": 72,
        "independent_sources": 2,
        "source_tiers": ["t1"],
        "is_verified": False,
        "event_count": 4,
    },
    {
        "title_en": "Airstrikes Target Residential Areas Near Aleppo",
        "title_ko": "알레포 인근 주거지역 공습 발생",
        "country_code": "SY",
        "severity": 61,
        "independent_sources": 2,
        "source_tiers": ["t2"],
        "is_verified": False,
        "event_count": 3,
    },
    {
        "title_en": "Houthi Forces Fire Ballistic Missiles at Saudi Arabia",
        "title_ko": "후티 세력, 사우디아라비아에 탄도미사일 발사",
        "country_code": "YE",
        "severity": 55,
        "independent_sources": 1,
        "source_tiers": ["t2"],
        "is_verified": False,
        "event_count": 2,
    },
    {
        "title_en": "Clashes Intensify in Khartoum as RSF Advances",
        "title_ko": "RSF 진격으로 하르툼 교전 격화",
        "country_code": "SD",
        "severity": 48,
        "independent_sources": 1,
        "source_tiers": ["t3"],
        "is_verified": False,
        "event_count": 5,
    },
]

DATE = "2026.05.19"

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 생성 & 저장 ───────────────────────────────────────────────────────────────

def save(filename: str, data: bytes | None) -> None:
    if not data:
        print(f"  [FAIL] {filename} — None 반환됨")
        return
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    size_kb = len(data) // 1024
    print(f"  [OK]   {filename}  ({size_kb} KB, {len(data)} bytes)")

    # 크기 assert
    from PIL import Image
    import io
    img = Image.open(io.BytesIO(data))
    assert img.size == (720, 900), f"크기 오류: {img.size} (기대: 720x900)"
    print(f"         해상도 확인: {img.size[0]}×{img.size[1]} px ✓")


def main() -> None:
    print("\n=== HTML 카드 생성 테스트 ===\n")

    print("1. kscore_alert (BREAKING NEWS)")
    save("test_card_alert.png",
         generate_html_card("kscore_alert", ISSUES[:1], date=DATE))

    print("2. daily_movers (DAILY BRIEF)")
    save("test_card_daily.png",
         generate_html_card("daily_movers", ISSUES[:3], date=DATE))

    print("3. weekly_recap (WEEK IN REVIEW)")
    save("test_card_weekly.png",
         generate_html_card("weekly_recap", ISSUES[:5], date=DATE))

    print("\n완료. 생성된 파일을 열어 시각 검토 후 승인해주세요.")


if __name__ == "__main__":
    main()

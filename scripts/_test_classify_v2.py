"""분류 폴백 개선 검증 테스트."""
import sys
sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")
from worker.processor.normalizer import _classify_topic

cases = [
    # (text, expected_topic, description)
    ("IDF airstrikes kill 60 militants in Rafah", "conflict", "군사 작전"),
    ("US designates Houthi group as terrorist organization", "diplomacy", "조직 지정 → diplomacy"),
    ("Suicide bomber kills 50 at market in Baghdad", "terror", "테러 공격"),
    ("US imposes new sanctions on Iran over nuclear program", "sanctions", "제재 + nuclear program"),
    ("Protesters take to streets over economic crisis", "protest", "시위 > 경제위기"),
    ("Hamas and Israel ceasefire talks in Qatar", "diplomacy", "휴전 협상 → diplomacy"),
    ("7.8 magnitude earthquake strikes Turkey, 2000 dead", "disaster", "자연재해"),
    ("North Korea fires ICBM toward Sea of Japan", "conflict", "北 ICBM"),
    ("Ransomware attack shuts down hospital systems", "cyber", "사이버 공격"),
    ("Houthi attacks disrupt Red Sea shipping", "maritime", "홍해 해상 공격"),
    ("Military junta arrests elected president", "coup", "쿠데타"),
    ("Measles outbreak kills 100 in Congo", "health", "전염병"),
    ("BTS concert draws record crowd in Seoul", "unknown", "엔터테인먼트"),
    ("Travel advisory: Level 3 Do Not Travel to Syria", "diplomacy", "여행 경보"),
    ("Russia conducts military exercise near NATO border", "conflict", "군사 훈련"),
    ("Analysis: Will the Gaza war escalate?", "conflict", "분석 기사(war 키워드)"),
    # 추가 엣지케이스
    ("Ceasefire violation reported: Israel resumes shelling", "conflict", "휴전 위반 → conflict"),
    ("Greece faces economic crisis amid austerity protests", "protest", "경제위기 배경 시위"),
    ("Iran nuclear talks reach critical juncture", "diplomacy", "핵 협상 → diplomacy"),
    ("Turkey, Greece tensions rise in Aegean Sea", "maritime", "에게해 긴장"),
    ("Protests erupt in Tehran over fuel price hike", "protest", "연료 가격 시위"),
    ("Stock market crashes as trade war escalates", "sanctions", "무역전쟁 주가 폭락"),
]

all_ok = True
for text, expected, desc in cases:
    result = _classify_topic(text)
    ok = "✓" if result == expected else "✗ FAIL"
    if result != expected:
        all_ok = False
    print(f"  {ok} [{desc}]")
    if result != expected:
        print(f"       기대: {expected}, 실제: {result}")
        print(f"       텍스트: {text}")
    print()

print(f"결과: {'모두 통과 ✓' if all_ok else '일부 실패 ✗'}")

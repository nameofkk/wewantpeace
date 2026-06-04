"""개선된 번역투 후처리 검증 테스트."""
import sys
sys.path.insert(0, "/home/krshin7/Projects/wewantpeace")

from worker.processor.clusterer import (
    _fix_translation_style, _PAST_TENSE_SYLS,
    _make_cluster_title_ko, _is_junk_title,
)


def show(label, inp, out):
    changed = "[변환]" if out != inp.strip().rstrip(".…") else "[변경없음]"
    print(f"  {label}")
    print(f"    IN : {inp}")
    print(f"    OUT: {out} {changed}")
    print()


print("=== PAST_TENSE_SYLS 샘플 ===")
for c in ["았", "었", "됐", "렸", "났", "봤", "왔", "겠", "고", "경", "압", "력"]:
    print(f"  {c!r:5s} past={c in _PAST_TENSE_SYLS}")

print()
print("=== 1. 고 있습니다 일반화 ===")
cases1 = [
    ("동의하라는 압력을 받고 있습니다.", "→ 동의하라는 압력"),
    ("계획을 세우고 있습니다", "→ 계획"),
    ("말리인들을 지원하고 있습니다", "→ 말리인들"),
    ("위험에 노출되고 있습니다", "→ 위험에 노출"),
    ("보도를 하고 있습니다", "→ 보도"),
    ("핵탄두 수가 증가하고 있다고 경고", "→ 변경없음(이미 깔끔)"),
]
for inp, expected in cases1:
    show(expected, inp, _fix_translation_style(inp))

print("=== 2. 과거형 stem + 다 ===")
cases2 = [
    ("지연됐습니다.", "→ 지연됐다"),
    ("열렸습니다.", "→ 열렸다"),
    ("받았습니다.", "→ 받았다"),
    ("회수됐습니다.", "→ 회수됐다"),
    ("타격을 입었습니다.", "→ 타격을 입었다"),
    ("파괴된 후에도 위험하다고 조지아주 관리들이 밝혔습니다.", "→ 조지아주 관리들이 밝혔다"),
    ("핀란드와 에스토니아는 납품이 지연됐다고 밝혔습니다.", "→ 납품이 지연됐다고 밝혔다? or 지연됐다"),
]
for inp, expected in cases2:
    show(expected, inp, _fix_translation_style(inp))

print("=== 3. 인용 다고 변형 ===")
cases3 = [
    ("공격했다'고 밝혔습니다.", "→ 공격했다 (인용 패턴)"),
    ("화물선을 공격했다'고 밝혔습니다.", "→ 화물선을 공격했다"),
    ("보냈다고 국영 기관이 밝혔습니다.", "→ ...국영 기관이 밝혔다"),
]
for inp, expected in cases3:
    show(expected, inp, _fix_translation_style(inp))

print("=== 4. 기존 케이스들 (유지 확인) ===")
cases4 = [
    ("이스라엘이 가자에 대한 공습을 재개합니다", "→ 이스라엘, 가자에 대한 공습을 재개"),
    ("러시아가 우크라이나 동부 공세를 강화하고 있습니다", "→ 러시아, 우크라이나 동부 공세를 강화"),
    ("북한이 탄도 미사일을 발사했습니다", "→ 북한, 탄도 미사일을 발사"),
    ("미국이 이란에 추가 경제 제재를 시사합니다", "→ 미국, 이란에 추가 경제 제재를 시사"),
    ("핀란드 NATO 훈련은 카렐리아 전선의 개방을 예고합니다", "→ 예고 제거"),
    ("이스라엘, 가자 공습 재개", "→ 변경없음"),
    ("수단 내전 6개월째, 민간인 1만명 사망", "→ 변경없음"),
    ("이스라엘-하마스 휴전 협상 결렬…가자 공습 재개", "→ 변경없음"),
]
for inp, expected in cases4:
    show(expected, inp, _fix_translation_style(inp))

print("=== 5. 이모지 제거 E2E (Google Translate 실호출) ===")
emoji_cases = [
    ("🇷🇺🇲🇱The medics of the African Corps are providing assistance to Mali", "conflict", None),
    ("🇺🇦🇷🇺Russian media are publishing footage from Tuapse", "conflict", "UA"),
    ("🇱🇧🇮🇱Hezbollah FPV drone attacks Israeli tanker and soldiers", "conflict", "LB"),
    ("**BREAKING**: Israel launches massive airstrike on Tehran", "conflict", "IR"),
]
for title, topic, cc in emoji_cases:
    result = _make_cluster_title_ko(title, topic, cc)
    has_emoji = any(0x2600 <= ord(c) <= 0x1FFFF for c in (result or ""))
    has_md = "**" in (result or "")
    print(f"  EN: {title[:65]}")
    print(f"  KO: {result}")
    print(f"  이모지_남음={has_emoji}, 마크다운_남음={has_md}")
    print()

print("=== 6. junk 판정 전체 재확인 ===")
junk_cases = [
    ("🇮🇱⚡ #Israel #Gaza #Breaking", True),
    ("🚨🔥 BREAKING #Lebanon", True),
    ("Breaking: Live Update:", True),
    ("Morning Recap", True),
    ("🇷🇺🇲🇱The medics of the African Corps...", False),  # 내용 있음 → not junk
    ("Israel resumes airstrikes on Gaza", False),
    ("North Korea fires ballistic missile", False),
]
all_ok = True
for title, expected in junk_cases:
    result = _is_junk_title(title)
    ok = "✓" if result == expected else "✗ FAIL"
    if result != expected:
        all_ok = False
    print(f"  {ok} junk={result} (exp={expected}): {title[:55]}")
print(f"\n  결과: {'모두 통과 ✓' if all_ok else '일부 실패 ✗'}")

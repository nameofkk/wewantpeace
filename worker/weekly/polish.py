"""주간 브리핑 문장 다듬기 — 한국어는 humanize-korean 룰북으로 윤문, 영어는 상투구 검사.

2026-10-01 사장님 지적("AI 슬롭의 명수", "항상 깃허브 윤문스킬로 검사하고 내보내"). 같은 날
humanize-korean 진단: 사실 문단은 깨끗하고, AI 티는 '왜 중요해?·앞으로 볼 것' 두 칸에 몰려 있었다.
  - I-4/E-2: 다섯 기사 모두 "…지켜봐야 해요."로 끝남 (5/5)
  - E-3: 기사마다 같은 길이·같은 순서
  - A-15: 추상 주어 + 만능 동사 ("이번 사건은 … 긴장 관계를 보여줘요")
  - E-2: "[추세]-면서 [결과]-고 있어요" 틀 반복
  - A-18/A-19: 긴 좌향 수식, "통로에서의"
처방: (1) 생성 지시에 위 금지 규칙, (2) 생성 뒤 룰북(quick-rules.md)을 시스템 지시로 한 번 더 윤문,
(3) 결과는 결정적으로 검사 — 숫자·고유명사가 그대로인지, 변경률이 50% 미만인지(룰북 철칙 #4),
    어기면 그 칸은 윤문 전 문장으로 되돌린다.
"""
from __future__ import annotations

import difflib
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

RULES = (Path(__file__).parent / "humanize_ko" / "quick-rules.md").read_text(encoding="utf-8")
CHANGE_ABORT = 0.50  # humanize-korean 철칙 #4

# 영어판 상투구 — AI 가 쓴 티가 나는 표현 (2026-10-01 드라이런에서 실제로 나온 것 포함)
EN_SLOP = re.compile(
    r"\b(highlights?|underscores?|underscoring|amid(?:st)?|growing tensions|volatile|landscape|"
    r"remains? to be seen|will be (?:closely )?(?:watched|monitored)|in the wake of|"
    r"we track the latest|stay tuned|a stark reminder|sending shockwaves|escalating tensions|"
    r"it is worth noting|plays? a (?:key|crucial|pivotal) role|delve|meanwhile|remains? a (?:critical|key|major) risk)\b",
    re.I,
)
# 한국어판 상투구 — 룰북 S1 결산어·의의 과장 + 드라이런에서 반복된 끝맺음
KO_SLOP = re.compile(
    r"(지켜봐야 해요|주목해야|행보가 주목|귀추가 주목|관심이 쏠리|시사하는 바가|주목할 만|수포로 돌아갈|"
    r"결론적으로|요약하면|정리하자면|의 향방|보여줘요|보여 줘요|에 있어서?|에서의|으로의)"
)

POLISH_SYSTEM = (
    "너는 한국어 뉴스레터 편집자다. 아래 룰북(humanize-korean quick-rules)을 그대로 따라 입력 JSON 의 각 칸을 "
    "윤문한다. 이 글은 뉴스 해설이고 해요체(-어요/-했어요/-예요)가 의도된 문체다 — 해요체를 유지한다. "
    "제목(headline, short)은 손대지 않는다. 사실·수치·고유명사·인용·출처 표현('~라고 주장했어요', "
    "'~했다는 보고가 있었어요')은 한 글자도 바꾸지 않는다. 칸을 합치거나 지우지 않는다. "
    "특히 이 글에서 진단된 패턴: 여러 기사의 watch 칸이 모두 '…지켜봐야 해요'로 끝나는 반복(I-4/E-2), "
    "추상 주어+만능 동사('이번 사건은 …을 보여줘요', A-15), '-면서 …-고 있어요' 틀 반복(E-2), "
    "명사 앞 3어절 이상 관형구(A-18)와 '~에서의'(A-19). watch 칸은 라벨이 이미 '앞으로 볼 것'이므로 "
    "'지켜봐야 해요' 대신 무엇이 언제 어떻게 될지를 구체적으로 말하는 문장으로 쓴다. 여러 기사의 watch·why 칸이 "
    "같은 어미('~할 예정이에요', '~고 있어요', '~해야 해요')로 세 번 이상 끝나면 서법은 유지한 채 끝맺음을 서로 다르게 "
    "고친다(E-2). why 칸이 세 번 이상 '-면서'로 원인과 결과를 잇고 있으면 하나만 남기고 두 문장으로 끊거나 "
    "결과를 먼저 말한다. '~간의'는 '~사이의'로 풀거나 서술어로 바꾼다. "
    "새 상투구·새 대구·연결어미 뒤 쉼표를 만들지 않는다. 입력과 같은 키 구조의 JSON 만 돌려준다.\n\n"
    "=== 룰북 ===\n" + RULES
)


def change_rate(before: str, after: str) -> float:
    """humanize-korean metrics_v2.change_rate 와 같은 계산 (문자 단위 SequenceMatcher 의 보수)."""
    if not before and not after:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, before, after, autojunk=False).ratio()


_NUM = re.compile(r"\d[\d,.]*")
_LATIN = re.compile(r"[A-Za-z][A-Za-z.\-']+")


def facts_kept(before: str, after: str) -> bool:
    """숫자와 로마자 고유명사(RAF, IRGC 등)가 하나도 빠지거나 바뀌지 않았나."""
    return sorted(_NUM.findall(before)) == sorted(_NUM.findall(after)) and \
        sorted(_LATIN.findall(before)) == sorted(_LATIN.findall(after))


def _sentences(text: str) -> int:
    return len([x for x in re.split(r"(?<=[.?!])\s+", text.strip()) if x])


def reject_reason(before: str, after) -> str | None:
    """칸 하나 검사 — 사실·문체. 통과면 None, 아니면 이유. 변경률 게이트는 글 전체에 건다(apply_ko): 룰북의
    30/50% 기준은 문서 단위라 한 문장짜리 칸('지켜봐야 해요' → 구체 문장)은 제대로 고쳐도 칸 단위로는 50%를 넘는다."""
    from worker.weekly.edition import has_formal_ending
    if not isinstance(after, str) or not after.strip():
        return "empty"
    if not re.search(r"[가-힣]", after):
        return "no_hangul"
    if has_formal_ending(after) and not has_formal_ending(before):
        return "formal_register"  # 해요체 → 합쇼체로 올라가면 안 된다 ('ㅂ니다'는 받침이라 '니다'로 본다)
    nb, na = max(_sentences(before), 1), _sentences(after)
    # 한 문장을 둘로 끊는 건 룰북 처방(E-2)이라 허용하되 길이가 거의 그대로여야 한다. 문장이 늘고 길이도 늘면 덧붙인 것.
    if na > nb + 1 or (na > nb and len(after) > len(before) * 1.35 + 15) or len(after) > len(before) * 2 + 30:
        return "added_content"  # 룰북: 새 주장·사실 추가 금지
    if sorted(_NUM.findall(before)) != sorted(_NUM.findall(after)):
        return "numbers_changed"
    if sorted(_LATIN.findall(before)) != sorted(_LATIN.findall(after)):
        return "names_changed"
    return None


def accept(before: str, after: str) -> bool:
    return reject_reason(before, after) is None


def collect_ko(data: dict) -> dict:
    """윤문할 한국어 칸만 모은다 (제목 제외)."""
    out = {}
    intro = (data.get("intro") or {}).get("ko") or {}
    if intro.get("intro"):
        out["intro"] = intro["intro"]
    for i, s in enumerate(data.get("stories") or []):
        ko = s.get("ko") or {}
        for k in ("what", "why", "watch"):
            if ko.get(k):
                out[f"s{i}.{k}"] = ko[k]
    return out


def apply_ko(data: dict, polished: dict, only_given: bool = False) -> dict:
    """검사를 통과한 칸만 반영. {key: (before, after, rate, accepted)} 보고를 돌려준다."""
    report = {}
    before_all = collect_ko(data)
    chosen = {}
    for key, before in before_all.items():
        if only_given and key not in polished:
            chosen[key] = before
            continue
        after = polished.get(key)
        reason = reject_reason(before, after) if after is not None else "missing"
        ok = reason is None
        rate = change_rate(before, after) if isinstance(after, str) else None
        report[key] = {"rate": round(rate, 3) if rate is not None else None, "accepted": ok}
        if not ok:
            report[key]["reason"] = reason
            report[key]["after"] = (after or "")[:80] if isinstance(after, str) else None
        chosen[key] = after if ok else before
    whole = change_rate("\n".join(before_all.values()), "\n".join(chosen.values()))
    report["_whole"] = {"rate": round(whole, 3), "accepted": whole < CHANGE_ABORT}
    if whole >= CHANGE_ABORT:
        logger.warning("한국어 윤문 변경률 %.0f%% — 룰북 철칙 #4(50%%)에 걸려 전부 되돌림", whole * 100)
        return report
    from worker.weekly.edition import normalize_ko
    for key, before in before_all.items():
        after = normalize_ko(chosen[key])
        if after == before:
            continue
        if key == "intro":
            data["intro"]["ko"]["intro"] = after
        else:
            idx, field = key[1:].split(".")
            data["stories"][int(idx)]["ko"][field] = after
    return report


def _ko_targets(data: dict) -> tuple[dict, list[str]]:
    """1차 윤문 뒤에도 남은 한국어 AI 티 — 고칠 칸과 문제 설명."""
    fields, notes = {}, []
    stories = data.get("stories") or []
    my = [i for i, st in enumerate(stories) if "면서" in (st.get("ko", {}).get("why") or "")]
    if len(my) >= 3:
        notes.append(f"why 칸 {len(my)}개가 모두 '-면서'로 원인과 결과를 잇는다(E-2). 하나만 남기고 나머지는 "
                     "'-아/-어'·두 문장·결과 먼저 말하기로 골격을 서로 다르게 바꿔라.")
        for i in my[1:]:
            fields[f"s{i}.why"] = stories[i]["ko"]["why"]
    for i, st in enumerate(stories):
        for k in ("why", "watch"):
            v = st.get("ko", {}).get(k) or ""
            if KO_SLOP.search(v):
                fields[f"s{i}.{k}"] = v
    if any(KO_SLOP.search(v) for v in fields.values()):
        notes.append("'지켜봐야 해요·주목돼요·보여줘요·~에서의·~의 향방' 같은 표현을 빼고 구체적으로 써라.")
    return fields, notes


def polish_ko(data: dict) -> dict:
    """한국어판 윤문 (브리프 전용 Gemini 모델): 룰북 전체로 1콜, 그래도 남은 AI 티가 있으면 그 칸만 1콜 더.

    모델 응답이 매번 달라서(10-01 드라이런: 같은 입력에 '-면서' 5곳을 한 번은 고치고 한 번은 그대로 둠)
    남은 것을 이름 붙여 다시 시킨다. 두 번 다 실패하면 원문 그대로 두고 slop 기록에 남는다.
    """
    from worker.social import brief as B

    fields = collect_ko(data)
    if not fields:
        return {}
    raw = B._call_dedicated(POLISH_SYSTEM, json.dumps(fields, ensure_ascii=False), max_tokens=4000)
    if not isinstance(raw, dict):
        logger.warning("한국어 윤문 콜 실패 — 원문 그대로")
        report = {"_error": "no_response"}
    else:
        report = apply_ko(data, {k: B._clean(str(v)) for k, v in raw.items() if isinstance(v, (str, int, float))})
    targets, notes = _ko_targets(data)
    if targets:
        system = POLISH_SYSTEM + "\n\n=== 이번에 고칠 것 ===\n" + "\n".join(notes)
        raw2 = B._call_dedicated(system, json.dumps(targets, ensure_ascii=False), max_tokens=3000)
        if isinstance(raw2, dict):
            merged = {k: B._clean(str(v)) for k, v in raw2.items() if isinstance(v, (str, int, float)) and k in targets}
            report["_retry"] = apply_ko(data, merged, only_given=True)
        else:
            report["_retry"] = {"_error": "no_response"}
    return report


def slop_report(data: dict) -> dict:
    """내보내기 전 상투구 검사 결과 (남은 것 목록). 발송은 막지 않고 기록·로그만."""
    hits = {"en": [], "ko": []}
    intro = data.get("intro") or {}
    texts = {"en": [intro.get("en", {}).get("intro", "")], "ko": [intro.get("ko", {}).get("intro", "")]}
    for s in data.get("stories") or []:
        for lang in ("en", "ko"):
            texts[lang] += [s.get(lang, {}).get(k, "") for k in ("what", "why", "watch")]
    for lang, pat in (("en", EN_SLOP), ("ko", KO_SLOP)):
        for t in texts[lang]:
            hits[lang] += [m.group(0) for m in pat.finditer(t or "")]
    from worker.weekly.edition import has_formal_ending
    for t in texts["ko"]:
        if has_formal_ending(t):
            hits["ko"].append("합쇼체 끝맺음: " + t[-12:])
    # "-면서" 인과 틀이 why 칸마다 되풀이되는지 (E-2)
    n_myeonseo = sum("면서" in (s.get("ko", {}).get("why") or "") for s in data.get("stories") or [])
    if n_myeonseo >= 3:
        hits["ko"].append(f"why '-면서' 반복 x{n_myeonseo}")
    # 같은 끝맺음이 기사 칸마다 되풀이되는지 (E-2) — 문장 끝 4글자 기준
    for field in ("why", "watch"):
        ends = [re.sub(r"[.?!\s]+$", "", s.get("ko", {}).get(field, ""))[-5:] for s in data.get("stories") or []]
        for end, n in __import__("collections").Counter(e for e in ends if e).items():
            if n >= 3:
                hits["ko"].append(f"{field} 끝맺음 반복 x{n}: …{end}")
    return hits


# ── 영어판: 상투구가 걸린 칸만 고친다 ────────────────────────────────────────

EN_FIX_SYSTEM = (
    "You edit a wire-style weekly conflict newsletter. Rewrite each given sentence so it no longer uses the "
    "listed stock phrases, in plain concrete English a Reuters editor would accept. Keep every fact, number, "
    "name and attribution exactly. Do not add information. Keep roughly the same length. Return JSON with the "
    "same keys. Banned: highlights, underscores, amid, growing tensions, volatile, landscape, remains to be seen, "
    "will be watched/monitored, in the wake of, a stark reminder, meanwhile, remain(s) a critical/key risk, "
    "plays a key role, it is worth noting."
)

_CAPS = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-zA-Z]+")


def _en_facts(text: str) -> tuple:
    return (sorted(_NUM.findall(text)), sorted(set(_CAPS.findall(text)) - {"Meanwhile", "The", "A", "An", "It", "This"}))


def collect_en(data: dict) -> dict:
    out = {}
    intro = (data.get("intro") or {}).get("en") or {}
    if intro.get("intro") and EN_SLOP.search(intro["intro"]):
        out["intro"] = intro["intro"]
    for i, s in enumerate(data.get("stories") or []):
        for k in ("what", "why", "watch"):
            v = (s.get("en") or {}).get(k)
            if v and EN_SLOP.search(v):
                out[f"s{i}.{k}"] = v
    return out


def _set_en(data: dict, key: str, value: str) -> None:
    if key == "intro":
        data["intro"]["en"]["intro"] = value
    else:
        idx, field = key[1:].split(".")
        data["stories"][int(idx)]["en"][field] = value


def polish_en(data: dict) -> dict:
    """상투구가 걸린 영어 칸만 1콜로 고친다. 숫자·고유명사가 그대로이고 상투구가 사라진 것만 반영."""
    from worker.social import brief as B

    fields = collect_en(data)
    report = {}
    # 문장 첫머리 'Meanwhile,' 는 떼기만 하면 된다 (결정적)
    for key, v in list(fields.items()):
        fixed = re.sub(r"(^|(?<=[.!?]) )Meanwhile, ([a-z])", lambda m: m.group(1) + m.group(2).upper(), v)
        if fixed != v:
            _set_en(data, key, fixed)
            fields[key] = fixed
            report[key] = {"accepted": True, "how": "rule"}
            if not EN_SLOP.search(fixed):
                fields.pop(key)
    if not fields:
        return report
    raw = B._call_dedicated(EN_FIX_SYSTEM, json.dumps(fields, ensure_ascii=False), max_tokens=2000)
    if not isinstance(raw, dict):
        return dict(report, _error="no_response")
    for key, before in fields.items():
        after = B._clean(str(raw.get(key, "") or ""))
        ok = bool(after) and not EN_SLOP.search(after) and _en_facts(before)[0] == _en_facts(after)[0] \
            and set(_en_facts(before)[1]) <= set(_en_facts(after)[1]) and len(after) <= len(before) * 1.5 + 20
        report[key] = {"accepted": ok, "how": "ai"}
        if ok:
            _set_en(data, key, after)
    return report

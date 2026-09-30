"""주간 브리핑 통합 (2026-09-30) — 기사 거르기·순위·AI 응답 검사·한국어 문체·언어 판정·메일 렌더."""
import re
import uuid
from types import SimpleNamespace

from worker.weekly import edition as E
from worker.weekly import render as R
from worker.weekly import send as S


def _cluster(title, kscore=5.0, cc="PS", topic="conflict"):
    return SimpleNamespace(id=uuid.uuid4(), title=title, kscore=kscore, country_code=cc, topic=topic,
                           title_ko=None, lat=31.9, lon=35.2, first_event_at=None, last_event_at=None)


# ── 기사 고르기 ──────────────────────────────────────────────────────────────

def test_business_filter_catches_contracts_not_attacks():
    """출처 수로는 무기 계약이 1번이 됐다 (9/30 드라이런: 펜타곤 미사일 계약 23곳)."""
    assert E.BUSINESS_RE.search("Pentagon awards RTX's Raytheon $20.7 billion contract for AMRAAM missiles")
    assert E.BUSINESS_RE.search("Defence firm shares jump after procurement deal")
    assert not E.BUSINESS_RE.search("Houthi drone attack hits Saudi airbase")
    assert not E.BUSINESS_RE.search("Israeli settlers attack Palestinian homes in Halhul")


def test_rank_prefers_heavier_story_over_widely_copied_one():
    """출처 20곳 상한 × KScore — 널리 받아쓴 가벼운 기사보다 무거운 기사가 앞."""
    heavy = (_cluster("Settlers attack villages", kscore=9.4), {"n_sources": 14})
    light = (_cluster("Summit photo op", kscore=2.0, cc="US"), {"n_sources": 23})
    assert sorted([light, heavy], key=E.rank_key)[0] is heavy


def test_pick_distinct_one_story_per_country():
    a = (_cluster("A", cc="IR"), {"n_sources": 9})
    b = (_cluster("B", cc="IR"), {"n_sources": 8})
    c = (_cluster("C", cc="UA"), {"n_sources": 7})
    got = E.pick_distinct([a, b, c], 3, set())
    assert [x[0].title for x in got] == ["A", "C"]


# ── AI 응답 검사 ─────────────────────────────────────────────────────────────

GOOD = {
    "skip": False,
    "en": {"headline": "Settlers raid West Bank villages", "short": "Settlers raid villages",
           "what": "More than 100 settlers attacked Jalud, officials said.", "why": "Violence is spreading.",
           "watch": "Whether arrests follow."},
    "ko": {"headline": "요르단강 서안 정착민, 팔레스타인 마을 습격했습니다", "short": "서안 정착민 습격",
           "what": "정착민 100여 명이 잘루드 마을을 습격해 3명이 부상을 입었습니다.", "why": "폭력이 번지고 있습니다.",
           "watch": "체포가 이어질지 지켜봐야 합니다."},
    "number": {"value": "100+", "en": "settlers in the raid", "ko": "습격한 정착민", "source": "Dawn (Pakistan)"},
}


def test_clean_story_normalizes_korean_register_and_headline():
    out = E.clean_story_ai(GOOD, ["Al Jazeera English", "Dawn (Pakistan)"])
    assert out and out["ko"]["headline"] == "요르단강 서안 정착민, 팔레스타인 마을 습격"
    joined = " ".join(out["ko"][k] for k in ("what", "why", "watch"))
    assert "습니다" not in joined and "니다" not in joined
    assert out["ko"]["what"].endswith("입었어요.")
    assert out["number"]["value"] == "100+"


def test_number_dropped_when_source_not_in_reports():
    """어느 매체가 말한 숫자인지 확인 안 되면 큰 숫자를 싣지 않는다."""
    out = E.clean_story_ai(GOOD, ["Al Jazeera English"])
    assert out and "number" not in out


def test_clean_story_rejects_wrong_language():
    bad = dict(GOOD, ko=dict(GOOD["ko"], headline="Settlers raid villages"))
    assert E.clean_story_ai(bad, []) is None
    bad2 = dict(GOOD, en=dict(GOOD["en"], what="정착민이 공격했다"))
    assert E.clean_story_ai(bad2, []) is None
    assert E.clean_story_ai({"skip": True}, []) == {"skip": True}


def test_normalize_ko_batchim():
    assert E.normalize_ko("긴급한 조치입니다.") == "긴급한 조치예요."
    assert E.normalize_ko("새로운 사건입니다.") == "새로운 사건이에요."
    assert E.normalize_ko("공세를 강화합니다.") == "공세를 강화해요."


# ── 언어 판정 ────────────────────────────────────────────────────────────────

def test_decide_lang(monkeypatch):
    """설정 language='ko' 는 기본값이라 믿지 않는다 (74명 전부 Asia/Seoul·KR 기본값이었다)."""
    monkeypatch.delenv("WEEKLY_AMBIGUOUS_LANG", raising=False)
    assert S.decide_user_lang("김민수", None, "ko") == "ko"
    assert S.decide_user_lang("peacewatcher", "John Smith", "ko") == "en"
    assert S.decide_user_lang("krshin", None, "ko") == "en"
    assert S.decide_user_lang("krshin", None, "ko", explicit=True) == "ko"  # 메일 링크로 직접 고름
    monkeypatch.setenv("WEEKLY_AMBIGUOUS_LANG", "ko")
    assert S.decide_user_lang("krshin", None, "ko") == "ko"
    assert S.decide_user_lang("김민수", None, "en", explicit=True) == "en"


# ── 메일 렌더 ────────────────────────────────────────────────────────────────

def _edition():
    story = {
        "cluster_id": str(uuid.uuid4()), "cc": "PS", "lat": 31.9, "lon": 35.2, "n_sources": 14,
        "source_names": ["Al Jazeera English", "BBC World News", "France 24 English", "Haaretz"],
        "photo": {"url": "https://example.com/p.jpg", "credit": "Al Jazeera English"}, "photos": [],
        "number": {"value": "100+", "en": "settlers in the raid", "ko": "습격한 정착민", "source": "Dawn (Pakistan)"},
        "en": GOOD["en"], "ko": {"headline": "서안 정착민 습격", "short": "서안 습격", "what": "습격했어요.", "why": "번져요.", "watch": "지켜봐요."},
        "ai": True,
    }
    other = dict(story, cluster_id=str(uuid.uuid4()), cc="IR", photo=None, number=None)
    item = {"cluster_id": str(uuid.uuid4()), "cc": "UA", "n_sources": 5, "en": {"headline": "Drone strikes on Kyiv"},
            "ko": {"headline": "키이우 드론 공격"}}
    return {
        "week_key": "2026-W40", "start": "2026-09-23", "end": "2026-09-30",
        "stories": [story, other], "also": [item], "easing": [item],
        "countries": {"PS": {"n": 3, "top": item}}, "advisories": {"PS": 4},
        "numbers": {"stories": 42, "outlets": 58, "brent": {"now": 96.28, "then": 97.83, "pct": -1.6,
                                                            "now_date": "2026-09-30", "then_date": "2026-09-23"}},
        "intro": {"en": {"subject": "West Bank raids and more", "preheader": "Five stories", "intro": "A calm week.",
                         "lines": ["One", "Two", "Three"]},
                  "ko": {"subject": "서안 습격 외", "preheader": "다섯 건", "intro": "차분한 한 주였어요.", "lines": ["하나", "둘", "셋"]}},
        "images": {"hero_en": "https://cdn.example/h.png", "hero_ko": "https://cdn.example/hk.png", "map": "https://cdn.example/m.png"},
    }


def test_render_email_both_langs_no_template_leaks_or_false_claims():
    data = _edition()
    for lang in ("en", "ko"):
        for follow in (None, ["PS", "KR"]):
            mail = R.render_email(data, lang, follow=follow, unsubscribe_url="https://x/unsub?token=t",
                                  switch_url="https://x/lang?t=t", feedback_token="tok")
            html = mail["html"]
            assert "{%" not in html and "{{" not in html
            assert "4.9" not in html and "News #1" not in html and "1위" not in html
            assert "file:///" not in html
            assert "https://x/unsub?token=t" in html
            assert mail["subject"] == data["intro"][lang]["subject"]
            assert ("COUNTRIES YOU FOLLOW" in html or "내가 고른 나라" in html) == bool(follow)
    ko = R.render_email(data, "ko")["html"]
    assert "1.6% 내렸어요" in ko and "브렌트유" in ko  # 가격 표에서 계산한 주간 변화, 방향 그대로
    en = R.render_email(data, "en")["html"]
    assert "down 1.6%" in en


def test_web_version_has_no_personal_links():
    html = R.render_email(_edition(), "en")["html"]
    assert "Unsubscribe" not in html  # 웹판에는 개인 수신거부 링크가 없다
    assert "/weekly/2026-W40?lang=ko" in html


def test_map_svg_highlights_story_countries():
    svg = R.map_svg(_edition())
    assert svg.startswith("<svg") and svg.count("<circle") == 2
    assert "#E9C9C6" in svg  # 이번 주 기사 나라


def test_not_easing_filter():
    """AI 가 '위협을 주고받는 외교'를 협상·휴전으로 골랐다 (9/30 드라이런) — 제목으로 한 번 더 거른다."""
    assert E.NOT_EASING_RE.search("Diplomatic efforts intensify as US and Iran trade threats of war")
    assert not E.NOT_EASING_RE.search("Russia and Ukraine agree prisoner exchange")
    assert not E.NOT_EASING_RE.search("Ceasefire talks resume in Doha")


# ── 윤문 (humanize-korean 룰북) ──────────────────────────────────────────────

from worker.weekly import polish as P  # noqa: E402


def test_polish_accepts_style_change_keeps_facts():
    before = "이번 사건은 미국과 영국 간의 엇갈린 입장을 보여줘요. 남성 5명이 체포됐어요."
    after = "이번 사건으로 미국과 영국의 입장이 엇갈렸어요. 남성 5명이 체포됐어요."
    assert P.accept(before, after)


def test_polish_rejects_changed_numbers_or_names_or_register():
    before = "RAF 페어포드 인근에서 남성 5명이 체포됐어요."
    assert not P.accept(before, "RAF 페어포드 인근에서 남성 6명이 체포됐어요.")        # 숫자 바뀜
    assert not P.accept(before, "페어포드 인근에서 남성 5명이 체포됐어요.")            # RAF 빠짐
    assert not P.accept(before, "RAF 페어포드 인근에서 남성 5명이 체포되었습니다.")    # 합쇼체로 올라감
    assert not P.accept(before, "RAF 페어포드 인근에서 남성 5명이 체포됐어요. 추가로 여러 정황이 드러났고 경찰은 배후를 캐고 있어요.")  # 내용 덧붙임


def test_polish_apply_reverts_rejected_fields():
    data = {"intro": {"ko": {"intro": "차분한 한 주였어요."}},
            "stories": [{"ko": {"what": "5명이 다쳤어요.", "why": "긴장을 보여줘요.", "watch": "대응을 지켜봐야 해요."}}]}
    rep = P.apply_ko(data, {"intro": "차분한 한 주였어요.", "s0.what": "6명이 다쳤어요.",
                            "s0.watch": "정부가 이번 주 안에 대응을 내놓을지가 다음 관심사예요."})
    assert data["stories"][0]["ko"]["what"] == "5명이 다쳤어요."          # 숫자 바뀐 윤문은 되돌림
    assert data["stories"][0]["ko"]["watch"].startswith("정부가")
    assert rep["s0.what"]["accepted"] is False and rep["s0.watch"]["accepted"] is True


def test_polish_whole_text_change_gate():
    """글 전체 변경률 50% 이상이면 전부 되돌린다 (humanize-korean 철칙 #4)."""
    data = {"intro": {"ko": {"intro": "가"}}, "stories": [{"ko": {"what": "이란이 공격했어요.", "why": "위험해요.", "watch": "대응이 나와요."}}]}
    rep = P.apply_ko(data, {"s0.what": "이란군이 새벽 기습을 감행했어요.", "s0.why": "해협 통항이 멈출 수 있어요.",
                            "s0.watch": "미국 대응 수위가 다음 변수예요."})
    assert rep["_whole"]["accepted"] is False
    assert data["stories"][0]["ko"]["what"] == "이란이 공격했어요."


def test_slop_report_flags_known_tells():
    data = {"intro": {"en": {"intro": "We track the latest developments amid growing tensions."}, "ko": {"intro": ""}},
            "stories": [{"en": {"why": "It highlights risks."}, "ko": {"watch": "대응을 지켜봐야 해요."}}]}
    hits = P.slop_report(data)
    assert {"amid", "highlights"} <= {h.lower() for h in hits["en"]}
    assert "지켜봐야 해요" in hits["ko"]


def test_formal_endings_normalized_or_flagged():
    """'ㅂ니다'는 받침이라 글자로 안 잡힌다 — 10-01 드라이런에서 '나타납니다·주목됩니다'가 그대로 나갔다."""
    assert E.normalize_ko("움직임이 나타납니다.") == "움직임이 나타나요."
    assert E.normalize_ko("실행할지 주목됩니다.") == "실행할지 주목돼요."
    assert E.normalize_ko("확인해야 합니다.") == "확인해야 해요."
    assert E.has_formal_ending("사람들이 봅니다.")          # 못 고치는 건 남겨서 검사가 잡는다
    assert not P.accept("대응을 지켜봐야 해요.", "대응을 지켜봐야 합니다.")
    hits = P.slop_report({"intro": {}, "stories": [{"ko": {"watch": "사람들이 봅니다."}, "en": {}}]})
    assert any(h.startswith("합쇼체") for h in hits["ko"])


def test_polish_en_rule_and_ai_fix(monkeypatch):
    from worker.social import brief as B
    data = {"intro": {"en": {"intro": "Russia hit Ukraine's grid. Meanwhile, settler violence rose in the West Bank."}},
            "stories": [{"en": {"watch": "Houthi threats to target Saudi infrastructure remain a critical risk."}}]}
    monkeypatch.setattr(B, "_call_dedicated", lambda *a, **k: {
        "s0.watch": "The Houthis have threatened to strike Saudi infrastructure next."})
    rep = P.polish_en(data)
    assert data["intro"]["en"]["intro"].endswith("Settler violence rose in the West Bank.")
    assert data["stories"][0]["en"]["watch"].startswith("The Houthis")
    assert rep["s0.watch"]["accepted"] is True


def test_polish_ko_retries_leftover_tells(monkeypatch):
    from worker.social import brief as B
    whys = ["물가가 오르면서 불만이 커졌어요.", "교전이 이어지면서 피란민이 늘었어요.", "공습이 잦아지면서 학교가 문을 닫았어요."]
    data = {"intro": {"ko": {"intro": "한 주였어요."}},
            "stories": [{"ko": {"what": "일이 있었어요.", "why": w, "watch": "다음 회의가 10일에 열려요."}} for w in whys]}
    calls = []

    def fake(system, user, max_tokens=0):
        calls.append(system)
        if len(calls) == 1:
            return {}  # 1차 윤문은 아무것도 안 고침
        return {"s1.why": "교전이 이어져 피란민이 늘었어요.", "s2.why": "공습이 잦아졌어요. 학교가 문을 닫았어요."}
    monkeypatch.setattr(B, "_call_dedicated", fake)
    rep = P.polish_ko(data)
    assert len(calls) == 2 and "-면서" in calls[1]
    assert data["stories"][1]["ko"]["why"] == "교전이 이어져 피란민이 늘었어요."
    assert rep["_retry"]["s1.why"]["accepted"] is True
    assert data["stories"][2]["ko"]["why"] == "공습이 잦아졌어요. 학교가 문을 닫았어요."  # 두 문장으로 끊기는 허용

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
            assert ("Countries you follow" in html or "내가 고른 나라" in html) == bool(follow)
    ko = R.render_email(data, "ko")["html"]
    assert "▼1.6%" in ko and "브렌트유" in ko  # 가격 표에서 계산한 주간 변화, 부호 그대로


def test_web_version_has_no_personal_links():
    html = R.render_email(_edition(), "en")["html"]
    assert "Unsubscribe" not in html  # 웹판에는 개인 수신거부 링크가 없다
    assert "/weekly/2026-W40?lang=ko" in html


def test_map_svg_highlights_story_countries():
    svg = R.map_svg(_edition())
    assert svg.startswith("<svg") and svg.count("<circle") == 2
    assert "#F6C9CB" in svg  # 이번 주 기사 나라

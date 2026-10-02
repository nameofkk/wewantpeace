"""수집처 확대·묶기 품질 (2026-10-02) — GDELT GKG 거르기, 장소 충돌 거부권, 모음 채널 출처 세기."""
from worker.collector import gdelt_collector as G
from worker.processor.clusterer import places_conflict, _places


def _row(domain, title, themes, tone="-6.5,1,7", loc="1#Ukraine#UP#UP#49#32#UP"):
    f = [""] * 27
    f[1] = "20261002011500"
    f[3] = domain
    f[4] = f"https://{domain}/a/{abs(hash(title))}"
    f[7] = themes
    f[9] = loc
    f[15] = tone
    f[26] = f"<PAGE_TITLE>{title}</PAGE_TITLE>"
    return "\t".join(f)


def test_gkg_keeps_conflict_drops_noise_and_syndication():
    text = "\n".join([
        _row("kyivpost.com", "Russian drone strike hits Kyiv school shelter", "ARMED_CONFLICT;KILL;MILITARY"),
        _row("paper1.co.uk", "Sixth man arrested in RAF Fairford terror plot", "TERROR;MILITARY;ARREST", loc="1#United Kingdom#UK#UK#54#-2#UK"),
        _row("paper2.co.uk", "Sixth man arrested in RAF Fairford terror plot", "TERROR;MILITARY;ARREST", loc="1#United Kingdom#UK#UK#54#-2#UK"),
        _row("hindustantimes.com", "5 gripping OTT web series on military", "MILITARY;ARMED_CONFLICT", loc="1#India#IN#IN#21#78#IN"),
        _row("local.com", "Man sentenced after shooting at bar", "KILL;WB_2433_CONFLICT_AND_VIOLENCE", loc="1#United States#US#US#38#-97#US"),
        _row("bbc.co.uk", "Israeli strike kills five in Gaza", "ARMED_CONFLICT;KILL;MILITARY", loc="1#Gaza Strip#GZ#GZ#31.4#34.4#GZ"),
        _row("happy.com", "Peace festival draws crowds", "ARMED_CONFLICT", tone="3.2,4,1"),
    ])
    rows = G.parse_gkg(text, skip_domains={"bbc.co.uk"})
    titles = [r["title"] for r in rows]
    assert "Russian drone strike hits Kyiv school shelter" in titles
    assert titles.count("Sixth man arrested in RAF Fairford terror plot") == 1   # 지역지 동시 게재는 한 건만
    assert not any("OTT" in t for t in titles)                                  # 드라마 소개
    assert not any("sentenced" in t for t in titles)                            # 지역 범죄
    assert not any("Gaza" in t for t in titles)                                 # 이미 RSS 로 받는 매체
    assert not any("festival" in t for t in titles)                             # 감성 양수
    kyiv = next(r for r in rows if "Kyiv" in r["title"])
    assert kyiv["country"] == "Ukraine" and kyiv["topic"] == "conflict" and kyiv["domain"] == "kyivpost.com"


def test_gkg_title_unescape_and_suffix():
    assert G._title("<PAGE_TITLE>PSTA Gazette &#x2013; paving the way for a digital dictatorship | LankaWeb</PAGE_TITLE>") ==         "PSTA Gazette – paving the way for a digital dictatorship"
    assert G._title("<PAGE_TITLE>Police officers honoured | Wimmera Mallee News | Local News</PAGE_TITLE>") == "Police officers honoured"


def test_place_conflict_veto():
    """재현 실험에서 잘못 붙던 사례 — 장소가 다르면 다른 사건, 철자만 다르면 같은 곳."""
    assert places_conflict("Israel attacks area in Syria's southern Quneitra province", ["Five killed in Israel attack on Gaza City taxi"])
    assert places_conflict("Ukrainian strikes damaged the Feodosia marine oil terminal", ["Russian forces attacked Odesa"])
    assert places_conflict("Russian strike on Vyshhorod kills child", ["Guided bombs hit Sumy, killing two"])
    assert not places_conflict("Kyiv shrouded in smoke after strikes", ["Explosions in Kiev as air defence works"])
    assert not places_conflict("Death toll from flooding climbs", ["Floods in Thailand"])  # 장소 없는 쪽이 있으면 판단 안 함


def test_demonyms_and_institutions_are_not_places():
    assert _places("At least one Palestinian killed across Gaza") == set()
    assert _places("Pentagon and White House officials say") == set()
    assert _places("Strike near Khan Younis") != set()


def test_rule_fallback_requires_topic_word_in_title():
    """AI 한도가 바닥나 규칙 폴백으로 분류될 때, 제목에 그 토픽다운 단어가 없으면 버린다 (10-02 실측 오분류)."""
    from worker.processor.normalizer import _title_fits_topic as fits
    assert not fits("Dushanbe forum explores a new digital trade model for Central Asia", "maritime")
    assert not fits("Wind, rain and frost: what weather to expect in Tajikistan in October", "disaster")
    assert fits("Russian drone strike hits Kyiv school", "conflict")
    assert fits("Protesters storm parliament in Nairobi", "protest")
    assert fits("Death toll from Thailand floods climbs to 23", "disaster")


def test_google_translate_parses_gtx_and_handles_429(monkeypatch):
    """번역은 gtx 공개 API — 응답 조립, 429 면 차단 키, 실패하면 원문 유지."""
    import httpx
    from worker.processor import normalizer as N

    class R:
        def __init__(self, code, data=None):
            self.status_code, self._d = code, data
        def json(self):
            return self._d
    monkeypatch.setattr(N, "_translate_pace", lambda: None)
    monkeypatch.setattr(N, "_translate_cached", lambda *a: None)
    monkeypatch.setattr(N, "_translate_cache_store", lambda *a: None)
    monkeypatch.setattr(N, "_is_translate_blocked", lambda: False)
    monkeypatch.setattr(httpx, "get", lambda *a, **k: R(200, [[["Drone attack ", "x"], ["in Colombia", "y"]], None, "es"]))
    assert N._translate_to_english("Ataque con drones en Colombia", "es") == "Drone attack in Colombia"
    marked = []
    monkeypatch.setattr(N, "_mark_translate_blocked", lambda: marked.append(1))
    monkeypatch.setattr(httpx, "get", lambda *a, **k: R(429))
    assert N._translate_to_english("Ataque", "es") == "Ataque" and marked

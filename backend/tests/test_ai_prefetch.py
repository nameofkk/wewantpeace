"""수집 직후 AI 묶음 분류 → 캐시 → 단건 분류가 캐시를 꺼내 쓰는지."""
import worker.ai_config as ai_config
import worker.processor.normalizer as nz


class _FakeRedis:
    def __init__(self):
        self.d = {}

    def get(self, k):
        return self.d.get(k)

    def set(self, k, v, ex=None, nx=False):
        self.d[k] = v
        return True

    def exists(self, k):
        return k in self.d

    def ttl(self, k):
        return -2


def _setup(monkeypatch):
    r = _FakeRedis()
    monkeypatch.setattr(ai_config, "_get_redis_sync", lambda: r)
    monkeypatch.setattr(nz, "_ai_available", lambda: True)
    monkeypatch.setattr(nz, "_translate_to_english", lambda t, lang: t)
    return r


def test_prefetch_batches_and_single_call_hits_cache(monkeypatch):
    _setup(monkeypatch)
    calls = []

    def fake_batch(items):
        calls.append(len(items))
        return [("conflict", "airstrike", 70, "IL", f"제목{i}", "본문") for i, _ in enumerate(items)]

    monkeypatch.setattr(nz, "_classify_batch_with_ai", fake_batch)
    items = [(f"Israeli airstrike hits Gaza city number {i} killing several people", f"Airstrike hits Gaza {i}")
             for i in range(23)]
    assert nz.prefetch_ai_classification(items) == 23
    assert calls == [10, 10, 3]  # 23건 → 3콜

    # 같은 기사를 다시 넣으면 이미 캐시돼 있어 AI 를 부르지 않는다
    assert nz.prefetch_ai_classification(items[:5]) == 0
    assert calls == [10, 10, 3]

    # 단건 분류는 같은 (제목, 본문)이면 AI 를 부르지 않고 캐시를 돌려준다
    monkeypatch.setattr(nz, "_get_ai_client", lambda **kw: (_ for _ in ()).throw(AssertionError("AI 호출됨")))
    _, _, text, title, _ = nz._prepare_ai_input(items[0][0], items[0][1])
    assert nz._classify_with_ai(title, text) == ("conflict", "airstrike", 70, "IL", "제목0", "본문")


def test_prefetch_failure_caches_nothing(monkeypatch):
    r = _setup(monkeypatch)
    monkeypatch.setattr(nz, "_classify_batch_with_ai", lambda items: None)
    items = [(f"Missile strike reported near Kharkiv overnight {i}", f"Missile strike Kharkiv {i}") for i in range(15)]
    assert nz.prefetch_ai_classification(items) == 0
    assert not any(k.startswith("ai:cls:") for k in r.d)


def test_batch_prefers_gemini(monkeypatch):
    monkeypatch.setattr(ai_config, "USE_GEMINI", True)
    monkeypatch.setattr(ai_config, "is_gemini_rate_limited", lambda: False)
    monkeypatch.setattr(ai_config, "is_gemini_unavailable", lambda: False)
    assert ai_config.get_batch_provider() == "gemini"
    monkeypatch.setattr(ai_config, "is_gemini_rate_limited", lambda: True)
    monkeypatch.setattr(ai_config, "get_current_provider", lambda: "groq")
    assert ai_config.get_batch_provider() == "groq"


def test_gemini_daily_quota_blocks_until_reset(monkeypatch):
    seen = {}
    monkeypatch.setattr(ai_config, "mark_gemini_unavailable", lambda s: seen.setdefault("s", s))
    ai_config.mark_gemini_rate_limited(60.0, "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    assert 60 <= seen["s"] <= 25 * 3600


def test_single_call_never_uses_gemini(monkeypatch):
    monkeypatch.setitem(ai_config._PROVIDER_CONFIGURED, "groq", lambda: True)
    monkeypatch.setitem(ai_config._PROVIDER_CONFIGURED, "openai", lambda: False)
    monkeypatch.setitem(ai_config._PROVIDER_BLOCKED, "groq", lambda: True)
    assert ai_config.get_single_provider() is None
    monkeypatch.setitem(ai_config._PROVIDER_BLOCKED, "groq", lambda: False)
    assert ai_config.get_single_provider() == "groq"

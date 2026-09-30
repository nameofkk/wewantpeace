"""Threads 영어 브리프 (2026-09-30 개편) — 본문 길이·이모지·주제 태그·품질 게이트·생성기."""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from worker.social import brief as B
from worker.social.adapters import threads_adapter

BRIEF = {
    "headline": "Iranian cruise missile wounds eight US Marines at Iraq base",
    "what": "A cruise missile struck Al Asad air base in western Iraq overnight, wounding eight US Marines, "
            "according to the Pentagon. Two were evacuated for treatment.",
    "why": "It is the first attack on US troops in Iraq this month to cause injuries, raising the risk of direct US strikes on Iran.",
    "watch": "Whether Washington names Iran as responsible and orders a retaliatory strike within days.",
}


def test_caption_follows_reference_format():
    """본문 = 뉴스 한 문장 + 맥락 한 문장 + 출처 (헤드라인은 표지 카드에 있어 반복하지 않고, 링크는 답글로)."""
    text = B.compose_alert_text(BRIEF, 7, uuid.uuid4(), ["Reuters", "AP", "BBC", "NHK"])
    assert len(text) <= 500
    assert text.startswith(BRIEF["what"])
    assert BRIEF["headline"] not in text
    assert "http" not in text
    assert text.endswith("Sources: Reuters, AP, BBC and 1 more.")


def test_caption_drops_why_when_long():
    long = dict(BRIEF, what="x " * 95, why="y " * 200)
    text = B.compose_alert_text(long, 5, uuid.uuid4(), ["Reuters"])
    assert len(text) <= 500
    assert "y y" not in text


def test_strip_emoji_and_clean():
    assert B.strip_emoji("🚨 Missiles hit Kyiv 🔴") == "Missiles hit Kyiv"
    assert B._clean("BREAKING: **Strikes** in #Gaza") == "Strikes in Gaza"


def test_topic_tag_rules():
    assert B.topic_tag_for("UA") == "Ukraine"
    assert B.topic_tag_for("US") == "United States"
    assert B.topic_tag_for(None, "cyber") == "Cybersecurity"
    post = SimpleNamespace(hashtags=["#St. Kitts & Nevis"])
    assert threads_adapter._topic_tag(post) == "St Kitts and Nevis"


def test_adapter_keeps_body_without_adding_emoji_or_telegram():
    body = B.compose_alert_text(BRIEF, 14, uuid.uuid4())
    post = SimpleNamespace(body_text=body, content_type="kscore_alert", id=uuid.uuid4())
    out = threads_adapter._build_text(post)
    assert out == body
    assert "t.me" not in out and "💬" not in out


def _cluster(title="Russian missiles strike Kyiv energy grid overnight", cc="UA", topic="conflict"):
    return SimpleNamespace(id=uuid.uuid4(), title=title, country_code=cc, topic=topic, severity=80, title_ko=None)


def test_quality_gate():
    fresh = datetime.now(timezone.utc) - timedelta(hours=2)
    ok_ctx = {"n_sources": 4, "source_names": [], "reports": [], "newest_event_at": fresh}
    assert B.quality_reject_reason(_cluster(), ok_ctx, 3) is None
    assert B.quality_reject_reason(_cluster(), dict(ok_ctx, n_sources=2), 3) == "sources<3"
    assert B.quality_reject_reason(_cluster(title="Ukraine Conflict"), ok_ctx, 3) == "template_title"
    stale = dict(ok_ctx, newest_event_at=datetime.now(timezone.utc) - timedelta(hours=60))
    assert B.quality_reject_reason(_cluster(), stale, 3) == "stale"


def test_build_brief_rejects_non_english_and_strips_emoji():
    ctx = {"n_sources": 4, "reports": ["- [Reuters] x"]}
    with patch.object(B, "_call_ai_json", return_value=dict(BRIEF, headline="🚨 BREAKING: " + BRIEF["headline"])):
        out = B.build_brief(_cluster(), ctx)
    assert out["headline"] == BRIEF["headline"]
    with patch.object(B, "_call_ai_json", return_value=dict(BRIEF, what="키이우에 미사일 공격")):
        assert B.build_brief(_cluster(), ctx) is None
    with patch.object(B, "_call_ai_json", return_value=None):
        assert B.build_brief(_cluster(), ctx) is None
    # AI 가 게시할 사건이 아니라고 판단하면 버린다 (9/30 실측: "German online forum hosts weekend discussion")
    with patch.object(B, "_call_ai_json", return_value=dict(BRIEF, skip=True)):
        assert B.build_brief(_cluster(), ctx) is None


def test_dedicated_model_first_then_shared():
    with patch.object(B, "_call_dedicated", return_value=BRIEF) as d, \
         patch.object(B, "_call_shared", return_value=None) as s:
        assert B._call_ai_json("s", "u") == BRIEF
        s.assert_not_called()
    with patch.object(B, "_call_dedicated", return_value=None), \
         patch.object(B, "_call_shared", return_value=BRIEF) as s:
        assert B._call_ai_json("s", "u") == BRIEF
        s.assert_called_once()


def test_self_reply_has_watch_link_and_brief():
    cid = uuid.uuid4()
    reply = B.compose_sources_reply(["Reuters"], "IR", BRIEF["watch"], cid)
    assert reply.startswith("What to watch: " + BRIEF["watch"])
    assert f"/issues/{cid}?ref=threads" in reply
    assert "/brief?c=IR&ref=threads" in reply
    assert B.compose_sources_reply([]) is None


def test_highlight_must_be_in_headline():
    ctx = {"n_sources": 4, "reports": ["- [Reuters] x"]}
    with patch.object(B, "_call_ai_json", return_value=dict(BRIEF, highlight="eight US Marines")):
        assert B.build_brief(_cluster(), ctx)["highlight"] == "eight US Marines"
    with patch.object(B, "_call_ai_json", return_value=dict(BRIEF, highlight="not in there")):
        assert B.build_brief(_cluster(), ctx)["highlight"] == ""


def test_alert_slides_structure():
    """표지 / 무슨 일 / 왜 중요 / 지켜볼 점 / 출처·구독 5장, 사진은 장마다 돌려 쓴다."""
    from worker.social import brief_card as C
    with patch.object(C, "fetch_photo", side_effect=["data:image/jpeg;base64,AAA", "data:image/jpeg;base64,BBB", None]):
        slides = C.alert_slides(dict(BRIEF, highlight="eight US Marines", dek="Pentagon says two evacuated"),
                                country="Iran", cc="IR", n_sources=7, source_names=["Reuters", "AP"],
                                photos=[("u1", "Reuters"), ("u2", "AP"), ("u3", "")])
    assert len(slides) == 5
    assert "<em>eight US Marines</em>" in slides[0] and "7 sources" in slides[0]
    assert "What happened" in slides[1] and "Why it matters" in slides[2] and "What to watch" in slides[3]
    assert "Get a weekly brief on Iran" in slides[4] and "brief?c=IR" in slides[4]
    assert "BBB" in slides[1] and "AAA" in slides[2]  # 2장뿐이면 돌려 쓴다
    assert "Photo: AP" in slides[1]


def test_adapter_uses_carousel_for_multiple_slides():
    from unittest.mock import MagicMock
    calls = []

    def fake_post(url, params=None):
        calls.append(dict(params or {}))
        r = MagicMock(status_code=200)
        r.json.return_value = {"id": f"id{len(calls)}"}
        return r

    client = MagicMock()
    client.post.side_effect = fake_post
    post = SimpleNamespace(id=uuid.uuid4(), body_text="x", content_type="kscore_alert", hashtags=["Iran"],
                           image_url="https://cdn/1.png", image_urls=["https://cdn/1.png", "https://cdn/2.png"],
                           reply_text=None)
    with patch.object(threads_adapter, "is_configured", return_value=True), \
         patch.object(threads_adapter, "THREADS_USER_ID", "u"), \
         patch.object(threads_adapter.time, "sleep"), \
         patch("httpx.Client") as hc:
        hc.return_value.__enter__.return_value = client
        tid, err = threads_adapter.publish(post)
    assert err is None
    assert [c.get("is_carousel_item") for c in calls[:2]] == ["true", "true"]
    assert calls[2]["media_type"] == "CAROUSEL" and calls[2]["children"] == "id1,id2"


@pytest.mark.asyncio
async def test_generate_kscore_alert_pending_during_review(db, monkeypatch):
    from backend.app.models.issue_cluster import IssueCluster
    from worker.social import generators

    now = datetime.now(timezone.utc)
    cluster = IssueCluster(
        cluster_key="IR:conflict", geohash5="00000", topic="conflict", country_code="IR",
        title="Iranian cruise missile wounds US Marines at Al Asad base", event_count=12, severity=85,
        confidence=0.8, kscore=7.0, source_tiers=["A"], independent_sources=5,
        first_event_at=now - timedelta(hours=5), last_event_at=now, window_start=now, window_end=now,
        is_active=True,
    )
    db.add(cluster)
    await db.flush()
    ctx = {"n_sources": 5, "source_names": ["Reuters", "AP", "BBC", "Al Jazeera", "Military Times"],
           "reports": ["- [Reuters] ..."], "photos": [], "newest_event_at": now - timedelta(hours=1)}

    monkeypatch.setattr("worker.social.config.SOCIAL_REVIEW_UNTIL", (now + timedelta(hours=48)).isoformat())
    with patch.object(B, "_call_ai_json", return_value=BRIEF), \
         patch("worker.social.brief_card.fetch_photo", return_value=None), \
         patch("worker.social.brief_card.attach_carousel", new=AsyncMock(return_value=True)) as card:
        post = await generators.generate_kscore_alert(cluster, db, ctx=ctx)

    assert post is not None
    assert post.status == "pending_review"
    assert post.lang == "en"
    assert post.hashtags == ["Iran"]
    assert post.reply_text.startswith("What to watch:")
    assert card.await_args.args[1][0].count("WEWANTPEACE") == 1  # 표지 장 HTML 이 넘어갔다
    assert len(post.body_text) <= 500
    card.assert_awaited_once()

    # 같은 날 같은 클러스터는 다시 만들지 않는다
    with patch.object(B, "_call_ai_json", return_value=BRIEF), \
         patch("worker.social.brief_card.attach_carousel", new=AsyncMock(return_value=True)):
        assert await generators.generate_kscore_alert(cluster, db, ctx=ctx) is None


@pytest.mark.asyncio
async def test_generate_kscore_alert_skips_when_ai_fails(db):
    from backend.app.models.issue_cluster import IssueCluster
    from worker.social import generators

    now = datetime.now(timezone.utc)
    cluster = IssueCluster(
        cluster_key="UA:conflict", geohash5="00000", topic="conflict", country_code="UA",
        title="Russian missiles strike Kyiv energy grid overnight", event_count=8, severity=80,
        confidence=0.8, kscore=6.0, source_tiers=["A"], independent_sources=4,
        first_event_at=now, last_event_at=now, window_start=now, window_end=now, is_active=True,
    )
    db.add(cluster)
    await db.flush()
    ctx = {"n_sources": 4, "source_names": ["Reuters"], "reports": [], "newest_event_at": now}
    with patch.object(B, "_call_ai_json", return_value=None):
        assert await generators.generate_kscore_alert(cluster, db, ctx=ctx) is None

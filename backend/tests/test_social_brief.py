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


def test_alert_text_fits_threads_and_has_link():
    cid = uuid.uuid4()
    text = B.compose_alert_text(BRIEF, 14, cid)
    assert len(text) <= 500
    assert text.startswith(BRIEF["headline"])
    assert f"/issues/{cid}?ref=threads" in text
    assert "14 independent sources" in text


def test_alert_text_drops_optional_parts_when_long():
    long = dict(BRIEF, what="x " * 95, why="y " * 70, watch="z " * 60)
    text = B.compose_alert_text(long, 5, uuid.uuid4())
    assert len(text) <= 500
    assert "?ref=threads" in text


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


def test_sources_reply():
    reply = B.compose_sources_reply(["Reuters", "AP", "BBC", "Al Jazeera", "NHK", "DW", "France 24"])
    assert reply.startswith("Sources for this brief: Reuters, AP, BBC, Al Jazeera, NHK and 2 more.")
    assert B.compose_sources_reply([]) is None


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
           "reports": ["- [Reuters] ..."], "newest_event_at": now - timedelta(hours=1)}

    monkeypatch.setattr("worker.social.config.SOCIAL_REVIEW_UNTIL", (now + timedelta(hours=48)).isoformat())
    with patch.object(B, "_call_ai_json", return_value=BRIEF), \
         patch("worker.social.brief_card.attach_card", new=AsyncMock(return_value=True)) as card:
        post = await generators.generate_kscore_alert(cluster, db, ctx=ctx)

    assert post is not None
    assert post.status == "pending_review"
    assert post.lang == "en"
    assert post.hashtags == ["Iran"]
    assert post.reply_text.startswith("Sources for this brief: Reuters")
    assert len(post.body_text) <= 500
    card.assert_awaited_once()

    # 같은 날 같은 클러스터는 다시 만들지 않는다
    with patch.object(B, "_call_ai_json", return_value=BRIEF), \
         patch("worker.social.brief_card.attach_card", new=AsyncMock(return_value=True)):
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

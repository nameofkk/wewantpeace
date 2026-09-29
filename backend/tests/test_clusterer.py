"""
EventClusterer 단위 테스트.
"""
import pytest
from datetime import datetime, timezone, timedelta
from worker.processor.clusterer import (
    assign_cluster, can_merge_clusters, decayed_severity, merge_fragmented_clusters, WINDOW_MINUTES,
)
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.issue_cluster import IssueCluster


BASE_TIME = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_event(
    topic: str = "conflict",
    geohash5: str = "u8c3m",
    country_code: str = "UA",
    lat: float = 50.0,
    lon: float = 30.0,
    severity: int = 55,
    confidence: float = 0.70,
    event_time: datetime = BASE_TIME,
) -> NormalizedEvent:
    return NormalizedEvent(
        raw_event_id=None,
        title="Test Event",
        body="body text",
        topic=topic,
        entity_anchor=country_code,
        lat=lat,
        lon=lon,
        geohash5=geohash5,
        country_code=country_code,
        severity=severity,
        source_tier="B",
        confidence=confidence,
        dedup_key="test_dedup_key",
        is_duplicate=False,
        event_time=event_time,
    )


@pytest.mark.asyncio
async def test_new_cluster_created(db):
    """동일 키의 클러스터가 없으면 새로 생성."""
    event = _make_event()
    db.add(event)
    await db.flush()

    cluster, _ = await assign_cluster(event, db)
    assert cluster.id is not None
    assert cluster.event_count == 1
    # country_code 우선 클러스터 키: {country_code}:{topic}
    assert cluster.cluster_key == "UA:conflict"
    assert cluster.severity == 55
    assert cluster.confidence == pytest.approx(0.70)


@pytest.mark.asyncio
async def test_same_window_merges(db):
    """60분 윈도우 내 이벤트는 같은 클러스터에 묶임."""
    e1 = _make_event(event_time=BASE_TIME)
    db.add(e1)
    await db.flush()

    c1, _ = await assign_cluster(e1, db)

    e2 = _make_event(event_time=BASE_TIME + timedelta(minutes=30))
    db.add(e2)
    await db.flush()

    c2, _ = await assign_cluster(e2, db)

    assert c1.id == c2.id
    assert c2.event_count == 2


@pytest.mark.asyncio
async def test_outside_window_creates_new(db):
    """60분 윈도우를 벗어난 이벤트는 새 클러스터 생성."""
    e1 = _make_event(event_time=BASE_TIME)
    db.add(e1)
    await db.flush()
    c1, _ = await assign_cluster(e1, db)

    # 윈도우 초과: e1.event_time + 61분 → window_cutoff가 e1보다 늦음
    late_time = BASE_TIME + timedelta(minutes=WINDOW_MINUTES + 1)
    e2 = _make_event(event_time=late_time)
    db.add(e2)
    await db.flush()
    c2, _ = await assign_cluster(e2, db)

    assert c1.id != c2.id


@pytest.mark.asyncio
async def test_different_topic_creates_new(db):
    """같은 위치라도 topic이 다르면 별도 클러스터."""
    e1 = _make_event(topic="conflict")
    db.add(e1)
    await db.flush()
    c1, _ = await assign_cluster(e1, db)

    e2 = _make_event(topic="protest")
    db.add(e2)
    await db.flush()
    c2, _ = await assign_cluster(e2, db)

    assert c1.id != c2.id
    assert c2.cluster_key == "UA:protest"


@pytest.mark.asyncio
async def test_severity_max_maintained(db):
    """클러스터 severity는 최대값 유지."""
    e1 = _make_event(severity=40)
    db.add(e1)
    await db.flush()
    c1, _ = await assign_cluster(e1, db)

    e2 = _make_event(severity=80, event_time=BASE_TIME + timedelta(minutes=10))
    db.add(e2)
    await db.flush()
    c2, _ = await assign_cluster(e2, db)

    assert c2.severity == 80


@pytest.mark.asyncio
async def test_confidence_moving_average(db):
    """confidence는 이동 평균."""
    e1 = _make_event(confidence=0.60)
    db.add(e1)
    await db.flush()
    c, _ = await assign_cluster(e1, db)

    e2 = _make_event(confidence=0.80, event_time=BASE_TIME + timedelta(minutes=5))
    db.add(e2)
    await db.flush()
    c, _ = await assign_cluster(e2, db)

    # (0.60 * 1 + 0.80) / 2 = 0.70
    assert c.confidence == pytest.approx(0.70, abs=0.01)


@pytest.mark.asyncio
async def test_no_geohash_uses_default(db):
    """geohash5 없으면 country_code 기반 키 사용."""
    e = _make_event(geohash5=None)
    db.add(e)
    await db.flush()

    c, _ = await assign_cluster(e, db)
    # country_code가 "UA"이므로 country_code 우선
    assert c.cluster_key == "UA:conflict"


@pytest.mark.asyncio
async def test_cluster_event_link_created(db):
    """ClusterEvent 연결 레코드가 생성됨."""
    from backend.app.models.issue_cluster import ClusterEvent
    from sqlalchemy import select

    e = _make_event()
    db.add(e)
    await db.flush()

    c, _ = await assign_cluster(e, db)

    res = await db.execute(
        select(ClusterEvent).where(
            ClusterEvent.cluster_id == c.id,
            ClusterEvent.event_id == e.id,
        )
    )
    link = res.scalar_one_or_none()
    assert link is not None


def test_decayed_severity_half_life():
    """과거 최고 severity 는 48시간마다 절반."""
    assert decayed_severity(100, BASE_TIME, BASE_TIME) == 100
    assert decayed_severity(100, BASE_TIME, BASE_TIME + timedelta(hours=48)) == 50
    assert decayed_severity(100, BASE_TIME, BASE_TIME + timedelta(hours=96)) == 25
    # 순서가 뒤바뀐 이벤트(과거 시각)는 감쇠하지 않는다
    assert decayed_severity(80, BASE_TIME, BASE_TIME - timedelta(hours=5)) == 80


@pytest.mark.asyncio
async def test_old_peak_severity_decays(db):
    """하루 전 100점 이벤트 뒤에 40점 이벤트가 오면 100에 붙어 있지 않는다."""
    e1 = _make_event(severity=100)
    db.add(e1)
    await db.flush()
    c1, _ = await assign_cluster(e1, db)

    e2 = _make_event(severity=40, event_time=BASE_TIME + timedelta(hours=20))
    db.add(e2)
    await db.flush()
    c2, _ = await assign_cluster(e2, db)

    assert c1.id == c2.id
    assert 40 < c2.severity < 100  # 100 * 0.5^(20/48) ≈ 75


def _cluster(title, first, last, n, cc="IR"):
    return IssueCluster(
        cluster_key=f"{cc}:conflict", geohash5="00000", topic="conflict", country_code=cc,
        title=title, title_ko=None, event_count=n, severity=60, confidence=0.7, kscore=1.0,
        source_tiers=["B"] * n, independent_sources=1, first_event_at=first, last_event_at=last,
        window_start=first, window_end=last + timedelta(minutes=WINDOW_MINUTES), is_active=True,
    )


@pytest.mark.asyncio
async def test_fragment_merge_respects_lifetime(db):
    """합친 기간이 5일을 넘으면 작은 클러스터를 큰 클러스터에 붙이지 않는다."""
    now = datetime.now(timezone.utc)
    title = "Iranian cruise missile strike wounds US Marines at base"
    # 조회 조건(first 5일 근접)은 통과하지만 합치면 5일 12시간이 되는 조합
    big = _cluster(title, now - timedelta(days=5, hours=12), now - timedelta(days=5), 10)
    small = _cluster(title, now - timedelta(hours=26), now - timedelta(minutes=10), 2)
    db.add_all([big, small])
    await db.flush()

    merged = await merge_fragmented_clusters(db)
    assert merged == []
    assert small.is_active is True


@pytest.mark.asyncio
async def test_fragment_merge_within_lifetime(db):
    """기간 안이면 예전처럼 병합된다 (대조군)."""
    now = datetime.now(timezone.utc)
    title = "Iranian cruise missile strike wounds US Marines at base"
    big = _cluster(title, now - timedelta(days=1), now - timedelta(hours=10), 10)
    small = _cluster(title, now - timedelta(hours=2), now - timedelta(hours=1), 1)
    db.add_all([big, small])
    await db.flush()

    merged = await merge_fragmented_clusters(db)
    assert merged == [(str(small.id), str(big.id))]
    assert small.is_active is False


def test_can_merge_blocks_absorbing_mega_cluster():
    """오늘 생긴 작은 클러스터가 몇 달 치 거대 클러스터를 흡수하지 못한다 (9/28 이란 1,475건 사례)."""
    now = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    title = "Iranian cruise missile strike"
    fresh = _cluster(title, now - timedelta(hours=6), now, 40)
    mega = _cluster(title, datetime(2026, 3, 27, tzinfo=timezone.utc), now - timedelta(hours=3), 1400)
    assert not can_merge_clusters(fresh, mega, max_events=100)
    # 크기는 작아도 기간이 길면 안 된다
    old_small = _cluster(title, now - timedelta(days=7), now - timedelta(hours=3), 5)
    assert not can_merge_clusters(fresh, old_small, max_events=100)
    # 대조군: 같은 날 작은 조각은 합쳐진다
    sibling = _cluster(title, now - timedelta(hours=10), now - timedelta(hours=1), 5)
    assert can_merge_clusters(fresh, sibling, max_events=100)

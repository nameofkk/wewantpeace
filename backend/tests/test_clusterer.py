"""
EventClusterer 단위 테스트.
"""
import pytest
from datetime import datetime, timezone, timedelta
from worker.processor.clusterer import assign_cluster, WINDOW_MINUTES
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

    cluster = await assign_cluster(event, db)
    assert cluster.id is not None
    assert cluster.event_count == 1
    assert cluster.cluster_key == "u8c3m:conflict"
    assert cluster.severity == 55
    assert cluster.confidence == pytest.approx(0.70)


@pytest.mark.asyncio
async def test_same_window_merges(db):
    """60분 윈도우 내 이벤트는 같은 클러스터에 묶임."""
    e1 = _make_event(event_time=BASE_TIME)
    db.add(e1)
    await db.flush()

    c1 = await assign_cluster(e1, db)

    e2 = _make_event(event_time=BASE_TIME + timedelta(minutes=30))
    db.add(e2)
    await db.flush()

    c2 = await assign_cluster(e2, db)

    assert c1.id == c2.id
    assert c2.event_count == 2


@pytest.mark.asyncio
async def test_outside_window_creates_new(db):
    """60분 윈도우를 벗어난 이벤트는 새 클러스터 생성."""
    e1 = _make_event(event_time=BASE_TIME)
    db.add(e1)
    await db.flush()
    c1 = await assign_cluster(e1, db)

    # 윈도우 초과: e1.event_time + 61분 → window_cutoff가 e1보다 늦음
    late_time = BASE_TIME + timedelta(minutes=WINDOW_MINUTES + 1)
    e2 = _make_event(event_time=late_time)
    db.add(e2)
    await db.flush()
    c2 = await assign_cluster(e2, db)

    assert c1.id != c2.id


@pytest.mark.asyncio
async def test_different_topic_creates_new(db):
    """같은 위치라도 topic이 다르면 별도 클러스터."""
    e1 = _make_event(topic="conflict")
    db.add(e1)
    await db.flush()
    c1 = await assign_cluster(e1, db)

    e2 = _make_event(topic="protest")
    db.add(e2)
    await db.flush()
    c2 = await assign_cluster(e2, db)

    assert c1.id != c2.id
    assert c2.cluster_key == "u8c3m:protest"


@pytest.mark.asyncio
async def test_severity_max_maintained(db):
    """클러스터 severity는 최대값 유지."""
    e1 = _make_event(severity=40)
    db.add(e1)
    await db.flush()
    c1 = await assign_cluster(e1, db)

    e2 = _make_event(severity=80, event_time=BASE_TIME + timedelta(minutes=10))
    db.add(e2)
    await db.flush()
    c2 = await assign_cluster(e2, db)

    assert c2.severity == 80


@pytest.mark.asyncio
async def test_confidence_moving_average(db):
    """confidence는 이동 평균."""
    e1 = _make_event(confidence=0.60)
    db.add(e1)
    await db.flush()
    c = await assign_cluster(e1, db)

    e2 = _make_event(confidence=0.80, event_time=BASE_TIME + timedelta(minutes=5))
    db.add(e2)
    await db.flush()
    c = await assign_cluster(e2, db)

    # (0.60 * 1 + 0.80) / 2 = 0.70
    assert c.confidence == pytest.approx(0.70, abs=0.01)


@pytest.mark.asyncio
async def test_no_geohash_uses_default(db):
    """geohash5 없으면 '00000' 사용."""
    e = _make_event(geohash5=None)
    db.add(e)
    await db.flush()

    c = await assign_cluster(e, db)
    assert c.cluster_key == "00000:conflict"


@pytest.mark.asyncio
async def test_cluster_event_link_created(db):
    """ClusterEvent 연결 레코드가 생성됨."""
    from backend.app.models.issue_cluster import ClusterEvent
    from sqlalchemy import select

    e = _make_event()
    db.add(e)
    await db.flush()

    c = await assign_cluster(e, db)

    res = await db.execute(
        select(ClusterEvent).where(
            ClusterEvent.cluster_id == c.id,
            ClusterEvent.event_id == e.id,
        )
    )
    link = res.scalar_one_or_none()
    assert link is not None

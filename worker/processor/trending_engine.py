"""
TrendingEngine: KScore 기반 트렌딩 키워드 계산.

KScore = 0.40*(log2(1+k10)*spike_factor) + 0.20*quality + 0.20*severity_norm + 0.20*spread
포함 조건: k10 >= 6 OR (event_count >= 20 AND is_spike) AND KScore >= 1.2

결과를 trending_keywords 테이블에 UPSERT.
"""
import logging
import math
import uuid as uuid_lib
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.issue_cluster import IssueCluster
from backend.app.models.trending_keyword import TrendingKeyword

logger = logging.getLogger(__name__)

TRENDING_LIMIT = 20
KSCORE_MIN = 0.4   # 단일 이벤트도 포함 (초기 데이터 부족 시 너무 많이 걸러지는 것 방지)
VALID_MINUTES = 60 * 24  # 24시간 유효 (Celery beat가 없어도 캐시 유지)


def _calc_kscore(
    event_count: int,
    is_spike: bool,
    confidence: float,
    severity: int,
    independent_sources: int,
    source_tiers: list[str],
) -> float:
    """
    KScore 계산 (v2).

    KScore = 0.35*velocity + 0.15*quality + 0.35*severity_norm + 0.15*spread

    velocity 개선:
    - log2 → k10^0.65 (소규모 구간 1~10 이벤트 변별력 향상)
    - log2(1+1)=1.0 == 1^0.65=1.0 (1이벤트 기준점 동일)
    - k10=3: log2(4)=2.0 → 3^0.65=2.24 (+12%)
    - k10=7: log2(8)=3.0 → 7^0.65=3.73 (+24%)
    - velocity 상한 6.0 (스파이크 10+이벤트 과도 방지)

    가중치 조정:
    - velocity 0.45→0.35 (속도), severity 0.25→0.35 (심각도)
    - quality/spread 각 0.15 유지
    """
    k10 = max(1, event_count)

    spike_factor = 1.5 if is_spike else 1.0
    velocity = min(6.0, (k10 ** 0.7) * spike_factor)

    # quality: confidence + tier 보너스
    tier_bonus = sum(
        0.05 if t == "A" else 0.03 if t == "B" else 0.01
        for t in source_tiers
    )
    quality = min(1.0, confidence + tier_bonus)

    severity_norm = severity / 100.0

    # spread: 독립출처 수 기반 (최대 1.0)
    spread = min(1.0, independent_sources / 5.0)

    kscore = (
        0.35 * velocity
        + 0.15 * quality
        + 0.35 * severity_norm
        + 0.15 * spread
    )
    return round(kscore, 3)


async def calculate_global_trending(db: AsyncSession) -> list[dict]:
    """
    최근 60분 IssueCluster에서 KScore 상위 20개 계산.
    trending_keywords 테이블에 저장 후 결과 반환.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=48)  # 48시간 윈도우 (KScore 계산 범위)

    # 최근 48시간 활성 클러스터 조회
    result = await db.execute(
        select(IssueCluster)
        .where(IssueCluster.last_event_at >= cutoff)
        .order_by(IssueCluster.event_count.desc())
        .limit(200)
    )
    clusters = result.scalars().all()

    if not clusters:
        return []

    # KScore 계산
    scored = []
    for c in clusters:
        kscore = _calc_kscore(
            event_count=c.event_count,
            is_spike=c.is_spike,
            confidence=c.confidence,
            severity=c.severity,
            independent_sources=c.independent_sources,
            source_tiers=c.source_tiers or [],
        )
        # 포함 조건 완화: event_count >= 1 이상이면 포함
        if kscore < KSCORE_MIN:
            continue

        scored.append({
            "cluster_id": str(c.id),
            "keyword": c.title,
            "keyword_ko": c.title_ko,
            "kscore": kscore,
            "topic": c.topic,
            "country_codes": [c.country_code] if c.country_code else [],
            "is_spike": c.is_spike,
            "severity": c.severity,
            "event_count": c.event_count,
            "k10": c.event_count,
            "reason": _make_reason(c, kscore),
        })

    scored.sort(key=lambda x: x["kscore"], reverse=True)
    top = scored[:TRENDING_LIMIT]

    # trending_keywords 테이블 갱신: 먼저 새 레코드 삽입 후 기존 삭제 (빈 window 방지)
    # NOTE: on_conflict_do_update(UPSERT) 사용을 위해서는 TrendingKeyword 모델에
    # normalized_kw + scope UniqueConstraint가 필요합니다. 현재 미적용 상태이므로
    # INSERT 후 DELETE 순서로 처리하여 API 응답 빈 구간을 최소화합니다.
    valid_until = now + timedelta(minutes=VALID_MINUTES)

    for item in top:
        kw = TrendingKeyword(
            keyword=item["keyword"],
            keyword_ko=item.get("keyword_ko"),
            normalized_kw=item["keyword"].lower(),
            kscore=item["kscore"],
            topic=item["topic"],
            country_codes=item["country_codes"],
            cluster_ids=[uuid_lib.UUID(item["cluster_id"])],
            event_count=item.get("event_count", 0),
            severity=item.get("severity", 0),
            is_spike=item.get("is_spike", False),
            scope="global",
            calculated_at=now,
            valid_until=valid_until,
        )
        db.add(kw)

    # 만료된 레코드만 삭제 (valid_until < now)
    # ← 핵심 수정: 이전에는 calculated_at < now로 모든 과거 배치를 삭제해서
    #   히스토리가 최대 15분치만 남는 버그가 있었음.
    #   valid_until = now + VALID_MINUTES(24h) 이므로 24시간치 히스토리 누적됨.
    await db.flush()
    await db.execute(
        delete(TrendingKeyword).where(
            TrendingKeyword.valid_until < now,
        )
    )

    # issue_clusters.kscore 업데이트 — 상위 20개만 아닌 전체 scored 클러스터 갱신
    # (트렌딩 20위 밖 클러스터도 상세 페이지에서 KScore 0.0 고정 방지)
    from sqlalchemy import update as sql_update
    for item in scored:  # top → scored (전체)
        await db.execute(
            sql_update(IssueCluster)
            .where(IssueCluster.id == uuid_lib.UUID(item["cluster_id"]))
            .values(kscore=item["kscore"])
        )

    logger.info("트렌딩 계산 완료: 클러스터 %d개 → 트렌딩 %d개", len(clusters), len(top))
    return top


def _make_reason(cluster: IssueCluster, kscore: float) -> str:
    """'왜 뜸?' 설명 문자열 생성."""
    if cluster.is_spike:
        return f"1분간 이벤트 급증 (KScore {kscore:.1f})"
    if cluster.independent_sources >= 3:
        return f"{cluster.independent_sources}개 독립출처 동시 보도 (KScore {kscore:.1f})"
    return f"60분간 {cluster.event_count}개 이벤트 (KScore {kscore:.1f})"

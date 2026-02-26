"""
TrendingEngine: KScore 기반 트렌딩 키워드 계산.

KScore = 0.25*velocity + 0.15*quality + 0.40*severity_norm + 0.20*spread
포함 조건: KScore >= calibration.KSCORE_MIN

결과를 trending_keywords 테이블에 UPSERT.
모든 튜닝 가능한 상수는 calibration.py에서 관리.
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
from worker.processor.calibration import (
    VELOCITY_CAP,
    VELOCITY_EXPONENT,
    SPIKE_FACTOR,
    SPREAD_SATURATION,
    KSCORE_MIN,
    TRENDING_LIMIT,
    KSCORE_VALID_MINUTES,
)

logger = logging.getLogger(__name__)

# 모듈 수준 alias (하위 호환 및 가독성)
VALID_MINUTES = KSCORE_VALID_MINUTES


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

    KScore = 0.25*velocity + 0.15*quality + 0.40*severity_norm + 0.20*spread

    velocity:
    - k10^VELOCITY_EXPONENT × spike_factor, 상한 VELOCITY_CAP
    - 소규모(1~10) 구간 변별력 유지, 대규모에서 cap에 수렴
    - k10=5: 3.09, k10=10: 5.01, k10=15: 6.0(cap)

    가중치 조정 (v3):
    - velocity 0.35→0.25 (속도 과지배 방지)
    - severity 0.35→0.40 (심각도 우선)
    - spread 0.15→0.20 (소스 다양성 강조)

    상수 변경 시: calibration.py 수정 후 이 함수는 자동 반영됨.
    """
    k10 = max(1, event_count)

    sf = SPIKE_FACTOR if is_spike else 1.0
    velocity = min(VELOCITY_CAP, (k10 ** VELOCITY_EXPONENT) * sf)

    # quality: confidence + tier 보너스
    tier_bonus = sum(
        0.05 if t == "A" else 0.03 if t == "B" else 0.01
        for t in source_tiers
    )
    quality = min(1.0, confidence + tier_bonus)

    severity_norm = severity / 100.0

    # spread: 독립출처 수 기반 (최대 1.0, calibration.SPREAD_SATURATION 기준)
    spread = min(1.0, independent_sources / float(SPREAD_SATURATION))

    kscore = (
        0.25 * velocity
        + 0.15 * quality
        + 0.40 * severity_norm
        + 0.20 * spread
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

    # 히스토리 보관: 90일 이전 레코드만 삭제
    # valid_until은 현재 트렌딩 표시용 (24h), calculated_at 기준으로 90일 보관.
    # Pro+ 사용자가 90일 KScore 히스토리를 조회할 수 있어야 함.
    history_cutoff = now - timedelta(days=91)
    await db.flush()
    await db.execute(
        delete(TrendingKeyword).where(
            TrendingKeyword.calculated_at < history_cutoff,
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

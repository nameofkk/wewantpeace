"""헬스체크 로직 — 6가지 시스템 건강 체크.

6시간마다 실행되어 파이프라인 품질, 소스채널 건강, 클러스터 품질,
OpenAI API 상태, RSS 수집 지연, 워커 프로세스 상태를 점검합니다.
"""
import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.core.redis import get_redis

logger = logging.getLogger(__name__)


@dataclass
class HealthIssue:
    check_name: str           # "misclassification_rate"
    severity: str             # "critical" | "warning"
    message: str              # 사람이 읽을 수 있는 설명
    auto_fix_available: bool  # 자동 수정 가능 여부
    fix_action: str | None = None   # "reactivate_channels" | "reprocess_topics" | ...
    fix_params: dict = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class HealthCheckResult:
    """개별 체크 결과."""
    check_name: str
    status: str  # "ok" | "warning" | "critical"
    message: str
    issues: list[HealthIssue] = field(default_factory=list)


# ── Check 1: 미분류율 ───────────────────────────────────────────────────────


async def check_misclassification_rate(db: AsyncSession) -> HealthCheckResult:
    """최근 24시간 normalized_events에서 topic='unknown' 비율 계산."""
    try:
        total_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM normalized_events"
                " WHERE created_at >= NOW() - INTERVAL '24 hours'"
                " AND is_duplicate = false"
            )
        )
        total = total_q.scalar() or 0

        if total == 0:
            return HealthCheckResult(
                check_name="misclassification_rate",
                status="warning",
                message="최근 24h 이벤트 없음",
            )

        unknown_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM normalized_events"
                " WHERE created_at >= NOW() - INTERVAL '24 hours'"
                " AND is_duplicate = false"
                " AND topic = 'unknown'"
            )
        )
        unknown = unknown_q.scalar() or 0
        rate = (unknown / total) * 100

        if rate > 20:
            issue = HealthIssue(
                check_name="misclassification_rate",
                severity="critical" if rate > 40 else "warning",
                message=f"미분류율 {rate:.1f}% (임계값 20%)\n  └ 최근 24h: {unknown}/{total} 이벤트 unknown\n  └ 주요 원인: OpenAI API 분류 실패 추정",
                auto_fix_available=True,
                fix_action="reprocess_topics",
                fix_params={"scope": "unknown_24h"},
            )
            return HealthCheckResult(
                check_name="misclassification_rate",
                status=issue.severity,
                message=issue.message,
                issues=[issue],
            )

        return HealthCheckResult(
            check_name="misclassification_rate",
            status="ok",
            message=f"미분류율 {rate:.1f}% ({unknown}/{total})",
        )
    except Exception as e:
        logger.exception("미분류율 체크 오류")
        return HealthCheckResult(
            check_name="misclassification_rate",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 2: 소스채널 건강 ──────────────────────────────────────────────────


async def check_source_channels(db: AsyncSession) -> HealthCheckResult:
    """비활성 소스 수, 신규 비활성화 채널, 오비활성화 탐지."""
    try:
        # 전체 채널 수
        total_q = await db.execute(text("SELECT COUNT(*) FROM source_channels"))
        total = total_q.scalar() or 0

        # 비활성 채널 수
        inactive_q = await db.execute(
            text("SELECT COUNT(*) FROM source_channels WHERE is_active = false")
        )
        inactive = inactive_q.scalar() or 0

        # 최근 24시간 내 새로 비활성화된 채널 (updated_at 기준)
        newly_inactive_q = await db.execute(
            text(
                "SELECT id, display_name, feed_url, source_type FROM source_channels"
                " WHERE is_active = false"
                " AND updated_at >= NOW() - INTERVAL '24 hours'"
            )
        )
        newly_inactive = newly_inactive_q.fetchall()

        # 비활성 RSS 채널 중 실제 HTTP 200 반환하는 것 탐지 (오비활성화)
        inactive_rss_q = await db.execute(
            text(
                "SELECT id, display_name, feed_url FROM source_channels"
                " WHERE is_active = false AND source_type = 'rss'"
                " AND feed_url IS NOT NULL"
            )
        )
        inactive_rss = inactive_rss_q.fetchall()

        recoverable_channels: list[dict] = []
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for ch in inactive_rss:
                try:
                    resp = await client.head(ch.feed_url)
                    if resp.status_code == 200:
                        recoverable_channels.append({
                            "id": ch.id,
                            "name": ch.display_name,
                        })
                except Exception:
                    pass  # 네트워크 오류는 무시 — 여전히 비활성 유지

        issues: list[HealthIssue] = []

        if recoverable_channels:
            channel_names = ", ".join(c["name"] for c in recoverable_channels[:5])
            channel_ids = [c["id"] for c in recoverable_channels]
            issues.append(HealthIssue(
                check_name="source_channels",
                severity="warning",
                message=(
                    f"소스채널 {inactive}/{total} 비활성\n"
                    f"  └ 신규 비활성화: {len(newly_inactive)}개\n"
                    f"  └ 복구 가능: {channel_names}"
                ),
                auto_fix_available=True,
                fix_action="reactivate_channels",
                fix_params={"channel_ids": channel_ids},
            ))

        if issues:
            return HealthCheckResult(
                check_name="source_channels",
                status="warning",
                message=issues[0].message,
                issues=issues,
            )

        msg = f"소스채널 {total - inactive}/{total} 활성"
        if newly_inactive:
            msg += f" (신규 비활성화 {len(newly_inactive)}개)"

        return HealthCheckResult(
            check_name="source_channels",
            status="ok" if not newly_inactive else "warning",
            message=msg,
        )
    except Exception as e:
        logger.exception("소스채널 체크 오류")
        return HealthCheckResult(
            check_name="source_channels",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 3: 클러스터 품질 ──────────────────────────────────────────────────


async def check_cluster_quality(db: AsyncSession) -> HealthCheckResult:
    """메가 클러스터 탐지, 장기 지속 클러스터, 교차오염 비율 계산."""
    try:
        issues: list[HealthIssue] = []

        # 메가 클러스터 (event_count > 50, 활성 상태)
        mega_q = await db.execute(
            text(
                "SELECT id, title_ko, title, event_count, topic, country_code"
                " FROM issue_clusters"
                " WHERE event_count > 50 AND is_active = true AND severity > 0"
                " ORDER BY event_count DESC"
                " LIMIT 5"
            )
        )
        mega_clusters = mega_q.fetchall()

        # 72시간 이상 지속되는 클러스터
        stale_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM issue_clusters"
                " WHERE is_active = true AND severity > 0"
                " AND first_event_at < NOW() - INTERVAL '72 hours'"
            )
        )
        stale_count = stale_q.scalar() or 0

        # 교차오염: 하나의 클러스터 내에 서로 다른 country_code를 가진 이벤트 비율
        cross_contamination_q = await db.execute(
            text("""
                WITH cluster_diversity AS (
                    SELECT ce.cluster_id,
                           COUNT(DISTINCT ne.country_code) as country_cnt,
                           COUNT(DISTINCT ne.topic) as topic_cnt
                    FROM cluster_events ce
                    JOIN normalized_events ne ON ce.event_id = ne.id
                    JOIN issue_clusters ic ON ce.cluster_id = ic.id
                    WHERE ic.is_active = true AND ic.severity > 0
                    GROUP BY ce.cluster_id
                    HAVING COUNT(*) >= 3
                )
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE country_cnt > 2 OR topic_cnt > 2) as contaminated
                FROM cluster_diversity
            """)
        )
        row = cross_contamination_q.fetchone()
        total_clusters = row.total if row else 0
        contaminated = row.contaminated if row else 0
        contamination_rate = (contaminated / total_clusters * 100) if total_clusters > 0 else 0

        if mega_clusters:
            mega_names = ", ".join(
                (c.title_ko or c.title)[:30] + f"({c.event_count})"
                for c in mega_clusters[:3]
            )
            mega_ids = [str(c.id) for c in mega_clusters]
            issues.append(HealthIssue(
                check_name="cluster_quality",
                severity="warning",
                message=f"메가 클러스터 {len(mega_clusters)}개: {mega_names}",
                auto_fix_available=True,
                fix_action="split_mega_cluster",
                fix_params={"cluster_ids": mega_ids},
            ))

        parts = []
        parts.append(f"메가 클러스터: {len(mega_clusters)}개")
        if stale_count:
            parts.append(f"72h+ 장기: {stale_count}개")
        parts.append(f"교차오염: {contamination_rate:.1f}%")

        status = "ok"
        if issues:
            status = "warning"
        elif contamination_rate > 10:
            status = "warning"

        return HealthCheckResult(
            check_name="cluster_quality",
            status=status,
            message="\n  └ ".join(["클러스터 품질"] + parts),
            issues=issues,
        )
    except Exception as e:
        logger.exception("클러스터 품질 체크 오류")
        return HealthCheckResult(
            check_name="cluster_quality",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 4: OpenAI API 상태 ────────────────────────────────────────────────


async def check_openai_status(db: AsyncSession) -> HealthCheckResult:
    """최근 1시간 AI 분류 성공/실패 비율. Redis 카운터 또는 DB 로그 활용."""
    try:
        redis = get_redis()

        # Redis 카운터 확인 (worker에서 카운팅하는 경우)
        success = await redis.get("openai:classify:success_1h") or 0
        failure = await redis.get("openai:classify:failure_1h") or 0
        success = int(success)
        failure = int(failure)

        # Redis 카운터가 없으면 DB에서 추정
        if success == 0 and failure == 0:
            # 최근 1시간 raw_events processed=true vs 전체
            total_q = await db.execute(
                text(
                    "SELECT COUNT(*) FROM raw_events"
                    " WHERE collected_at >= NOW() - INTERVAL '1 hour'"
                )
            )
            total_raw = total_q.scalar() or 0

            processed_q = await db.execute(
                text(
                    "SELECT COUNT(*) FROM raw_events"
                    " WHERE collected_at >= NOW() - INTERVAL '1 hour'"
                    " AND processed = true"
                )
            )
            processed = processed_q.scalar() or 0

            if total_raw == 0:
                return HealthCheckResult(
                    check_name="openai_status",
                    status="ok",
                    message="최근 1h 처리할 이벤트 없음",
                )

            fail_rate = ((total_raw - processed) / total_raw) * 100
            if fail_rate > 30:
                issue = HealthIssue(
                    check_name="openai_status",
                    severity="critical" if fail_rate > 50 else "warning",
                    message=f"AI 분류 실패율 {fail_rate:.1f}% ({total_raw - processed}/{total_raw}, 최근 1h)",
                    auto_fix_available=True,
                    fix_action="reset_openai_rate_limit",
                    fix_params={},
                )
                return HealthCheckResult(
                    check_name="openai_status",
                    status=issue.severity,
                    message=issue.message,
                    issues=[issue],
                )

            return HealthCheckResult(
                check_name="openai_status",
                status="ok",
                message=f"AI 분류 정상 (처리 {processed}/{total_raw}, 최근 1h)",
            )

        # Redis 카운터 있는 경우
        total_ai = success + failure
        if total_ai == 0:
            return HealthCheckResult(
                check_name="openai_status",
                status="ok",
                message="최근 1h AI 호출 없음",
            )

        fail_rate = (failure / total_ai) * 100
        if fail_rate > 30:
            issue = HealthIssue(
                check_name="openai_status",
                severity="critical" if fail_rate > 50 else "warning",
                message=f"AI 분류 실패율 {fail_rate:.1f}% (실패 {failure}, 성공 {success})",
                auto_fix_available=True,
                fix_action="reset_openai_rate_limit",
                fix_params={},
            )
            return HealthCheckResult(
                check_name="openai_status",
                status=issue.severity,
                message=issue.message,
                issues=[issue],
            )

        return HealthCheckResult(
            check_name="openai_status",
            status="ok",
            message=f"AI 분류 정상 (성공 {success}, 실패 {failure})",
        )
    except Exception as e:
        logger.exception("OpenAI 상태 체크 오류")
        return HealthCheckResult(
            check_name="openai_status",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 5: RSS 수집 지연 ──────────────────────────────────────────────────


async def check_rss_freshness(db: AsyncSession) -> HealthCheckResult:
    """최근 수집된 이벤트의 최신 시각 확인. 30분 이상 새 이벤트 없으면 경고."""
    try:
        result = await db.execute(
            text("SELECT MAX(collected_at) FROM raw_events")
        )
        last = result.scalar()

        if not last:
            return HealthCheckResult(
                check_name="rss_freshness",
                status="critical",
                message="수집 기록이 전혀 없음",
            )

        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)

        age = datetime.now(timezone.utc) - last
        mins = int(age.total_seconds() / 60)

        if mins > 30:
            return HealthCheckResult(
                check_name="rss_freshness",
                status="critical" if mins > 60 else "warning",
                message=f"RSS 수집 지연: 최신 이벤트 {mins}분 전 (임계값 30분)",
            )

        return HealthCheckResult(
            check_name="rss_freshness",
            status="ok",
            message=f"RSS 수집 정상 (최신: {mins}분 전)",
        )
    except Exception as e:
        logger.exception("RSS 수집 지연 체크 오류")
        return HealthCheckResult(
            check_name="rss_freshness",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 6: 디스크/메모리 (간단) ───────────────────────────────────────────


async def check_worker_resources() -> HealthCheckResult:
    """워커 프로세스 기본 상태 — 메모리 사용량."""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem = proc.memory_info()
        mem_mb = mem.rss / (1024 * 1024)

        # 전체 시스템 메모리
        sys_mem = psutil.virtual_memory()
        sys_pct = sys_mem.percent

        # 디스크
        disk = psutil.disk_usage("/")
        disk_pct = disk.percent

        parts = [f"메모리: {mem_mb:.0f}MB (시스템 {sys_pct:.0f}%)"]
        parts.append(f"디스크: {disk_pct:.0f}%")

        status = "ok"
        if sys_pct > 90 or disk_pct > 90:
            status = "critical"
        elif sys_pct > 80 or disk_pct > 80:
            status = "warning"

        return HealthCheckResult(
            check_name="worker_resources",
            status=status,
            message=" | ".join(parts),
        )
    except ImportError:
        return HealthCheckResult(
            check_name="worker_resources",
            status="ok",
            message="psutil 미설치 — 리소스 체크 건너뜀",
        )
    except Exception as e:
        logger.exception("리소스 체크 오류")
        return HealthCheckResult(
            check_name="worker_resources",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── 전체 헬스체크 실행 ──────────────────────────────────────────────────────


async def run_all_checks() -> list[HealthCheckResult]:
    """6가지 헬스 체크를 모두 실행. 각 체크는 독립 try/except."""
    results: list[HealthCheckResult] = []

    async with AsyncSessionLocal() as db:
        # DB 의존 체크들
        db_checks = [
            check_misclassification_rate,
            check_source_channels,
            check_cluster_quality,
            check_openai_status,
            check_rss_freshness,
        ]
        for check_fn in db_checks:
            try:
                r = await check_fn(db)
            except Exception as e:
                try:
                    await db.rollback()
                except Exception:
                    pass
                r = HealthCheckResult(
                    check_name=check_fn.__name__.replace("check_", ""),
                    status="warning",
                    message=f"체크 오류: {e}",
                )
            results.append(r)

    # DB 독립 체크
    try:
        r = await check_worker_resources()
    except Exception as e:
        r = HealthCheckResult(
            check_name="worker_resources",
            status="warning",
            message=f"체크 오류: {e}",
        )
    results.append(r)

    return results

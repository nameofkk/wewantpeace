"""헬스체크 로직 — 18가지 시스템 건강 체크.

6시간마다 실행되어 파이프라인 품질, 소스채널 건강, 클러스터 품질,
OpenAI API 상태, RSS 수집 지연, 워커 프로세스 상태, Celery Beat,
API 소스, 중복률, FCM 전송, 구독 무결성, 긴장도 지수, Redis,
고아 이벤트, SNS 포스팅, SNS 토큰, 스파이크 전송, K점수 분포를 점검합니다.
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
                    # HEAD 대신 GET으로 Content-Type 확인 — HTML 반환 사이트 오탐 방지
                    resp = await client.get(ch.feed_url, headers={
                        "User-Agent": "Mozilla/5.0 (compatible; WeWantPeace/1.0)"
                    })
                    if resp.status_code == 200:
                        ct = resp.headers.get("content-type", "")
                        # XML/RSS/Atom 형식이어야 실제 복구 가능
                        if "xml" in ct or "rss" in ct or "atom" in ct:
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


# ── Check 7: Celery Beat 건강 ──────────────────────────────────────────────


async def check_celery_beat_health() -> HealthCheckResult:
    """Redis에서 beat heartbeat와 핵심 태스크 마지막 실행 시각 확인."""
    try:
        redis = get_redis()
        issues: list[HealthIssue] = []
        parts: list[str] = []

        # beat:heartbeat 키 확인 (TTL 10분)
        heartbeat = await redis.get("beat:heartbeat")
        if not heartbeat:
            issues.append(HealthIssue(
                check_name="celery_beat_health",
                severity="warning",
                message="beat:heartbeat 키 없음 — Celery Beat 중단 의심",
                auto_fix_available=False,
            ))
            parts.append("heartbeat: 없음")
        else:
            ttl = await redis.ttl("beat:heartbeat")
            parts.append(f"heartbeat: TTL {ttl}s")

        # 핵심 태스크 마지막 실행 시각 확인
        core_tasks = ["collect_rss", "calculate_tension", "collect_telegram"]
        now = datetime.now(timezone.utc)
        for task_name in core_tasks:
            key = f"celery:last_run:{task_name}"
            last_run_str = await redis.get(key)
            if not last_run_str:
                parts.append(f"{task_name}: 기록없음")
                continue
            try:
                last_run = datetime.fromisoformat(last_run_str.decode() if isinstance(last_run_str, bytes) else last_run_str)
                if last_run.tzinfo is None:
                    last_run = last_run.replace(tzinfo=timezone.utc)
                age_min = int((now - last_run).total_seconds() / 60)
                if age_min > 10:
                    issues.append(HealthIssue(
                        check_name="celery_beat_health",
                        severity="warning",
                        message=f"{task_name}: {age_min}분 미실행 (임계값 10분)",
                        auto_fix_available=False,
                    ))
                parts.append(f"{task_name}: {age_min}분 전")
            except Exception:
                parts.append(f"{task_name}: 파싱오류")

        status = "ok"
        if any(i.severity == "critical" for i in issues):
            status = "critical"
        elif issues:
            status = "warning"

        return HealthCheckResult(
            check_name="celery_beat_health",
            status=status,
            message="\n  └ ".join(["Celery Beat"] + parts),
            issues=issues,
        )
    except Exception as e:
        logger.exception("Celery Beat 체크 오류")
        return HealthCheckResult(
            check_name="celery_beat_health",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 8: API 소스 수집 지연 ────────────────────────────────────────────


# API 소스별 기대 주기 (분)
_API_SOURCE_INTERVALS: dict[str, int] = {
    "gdelt": 15,
    "usgs": 5,
    "telegram": 5,
    "reliefweb": 30,
    "acled": 1440,  # 일 1회
    "travel_advisory": 360,  # 6시간
}


async def check_api_sources(db: AsyncSession) -> HealthCheckResult:
    """API 소스별 최신 수집 시각 확인. 주기 대비 2배 이상 지연 시 warning."""
    try:
        issues: list[HealthIssue] = []
        parts: list[str] = []
        now = datetime.now(timezone.utc)

        result = await db.execute(
            text(
                "SELECT source_type, MAX(collected_at) as last_at"
                " FROM raw_events"
                " WHERE source_type != 'rss'"
                " GROUP BY source_type"
            )
        )
        rows = result.fetchall()
        source_map = {row.source_type: row.last_at for row in rows}

        for src, interval_min in _API_SOURCE_INTERVALS.items():
            last_at = source_map.get(src)
            if not last_at:
                parts.append(f"{src}: 수집기록없음")
                continue
            if last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=timezone.utc)
            age_min = int((now - last_at).total_seconds() / 60)
            threshold = interval_min * 2
            if age_min > threshold:
                issues.append(HealthIssue(
                    check_name="api_sources",
                    severity="warning",
                    message=f"{src}: {age_min}분 지연 (기대 주기 {interval_min}분, 임계값 {threshold}분)",
                    auto_fix_available=False,
                ))
            parts.append(f"{src}: {age_min}분 전")

        status = "ok" if not issues else "warning"
        return HealthCheckResult(
            check_name="api_sources",
            status=status,
            message="\n  └ ".join(["API 소스 수집"] + parts),
            issues=issues,
        )
    except Exception as e:
        logger.exception("API 소스 체크 오류")
        return HealthCheckResult(
            check_name="api_sources",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 9: 중복률 ───────────────────────────────────────────────────────


async def check_duplicate_rate(db: AsyncSession) -> HealthCheckResult:
    """24시간 중복률 계산. 70% 초과 또는 10% 미만이면 warning."""
    try:
        total_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM normalized_events"
                " WHERE created_at >= NOW() - INTERVAL '24 hours'"
            )
        )
        total = total_q.scalar() or 0

        if total == 0:
            return HealthCheckResult(
                check_name="duplicate_rate",
                status="ok",
                message="최근 24h 이벤트 없음",
            )

        dup_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM normalized_events"
                " WHERE created_at >= NOW() - INTERVAL '24 hours'"
                " AND is_duplicate = true"
            )
        )
        dup = dup_q.scalar() or 0
        rate = (dup / total) * 100

        issues: list[HealthIssue] = []
        if rate > 70:
            issues.append(HealthIssue(
                check_name="duplicate_rate",
                severity="warning",
                message=f"중복률 {rate:.1f}% (임계값 70%)\n  └ {dup}/{total} 이벤트 중복 — 소스 중복 과다",
                auto_fix_available=False,
            ))
        elif rate < 10 and total >= 50:
            issues.append(HealthIssue(
                check_name="duplicate_rate",
                severity="warning",
                message=f"중복률 {rate:.1f}% (임계값 10%)\n  └ {dup}/{total} — 수집 다양성 저하 의심",
                auto_fix_available=False,
            ))

        return HealthCheckResult(
            check_name="duplicate_rate",
            status="warning" if issues else "ok",
            message=f"중복률 {rate:.1f}% ({dup}/{total}, 최근 24h)",
            issues=issues,
        )
    except Exception as e:
        logger.exception("중복률 체크 오류")
        return HealthCheckResult(
            check_name="duplicate_rate",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 10: FCM Push 건강 ───────────────────────────────────────────────


async def check_fcm_push_health(db: AsyncSession) -> HealthCheckResult:
    """alert_delivery_log에서 최근 6시간 전송 결과 집계."""
    try:
        # 테이블 존재 확인
        result = await db.execute(
            text(
                "SELECT COUNT(*) FROM alert_delivery_log"
                " WHERE created_at >= NOW() - INTERVAL '6 hours'"
                " AND decision = 'sent'"
            )
        )
        sent = result.scalar() or 0

        failed_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM alert_delivery_log"
                " WHERE created_at >= NOW() - INTERVAL '6 hours'"
                " AND decision = 'failed'"
            )
        )
        failed = failed_q.scalar() or 0

        pending_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM alert_delivery_log"
                " WHERE decision = 'pending'"
            )
        )
        pending = pending_q.scalar() or 0

        issues: list[HealthIssue] = []
        total_delivery = sent + failed
        parts = [f"전송: {sent}", f"실패: {failed}", f"대기: {pending}"]

        if total_delivery > 0:
            success_rate = (sent / total_delivery) * 100
            if success_rate < 80:
                issues.append(HealthIssue(
                    check_name="fcm_push_health",
                    severity="warning",
                    message=f"FCM 성공률 {success_rate:.1f}% (임계값 80%)\n  └ sent={sent}, failed={failed}",
                    auto_fix_available=True,
                    fix_action="cleanup_stale_fcm_tokens",
                    fix_params={},
                ))

        if pending > 20:
            issues.append(HealthIssue(
                check_name="fcm_push_health",
                severity="warning",
                message=f"대기 건수 {pending}개 (임계값 20)",
                auto_fix_available=True,
                fix_action="cleanup_stale_fcm_tokens",
                fix_params={},
            ))

        status = "ok"
        if any(i.severity == "critical" for i in issues):
            status = "critical"
        elif issues:
            status = "warning"

        return HealthCheckResult(
            check_name="fcm_push_health",
            status=status,
            message="FCM Push: " + " | ".join(parts),
            issues=issues,
        )
    except Exception as e:
        # 테이블 미존재 등 — skip
        if "alert_delivery_log" in str(e).lower() or "relation" in str(e).lower():
            try:
                await db.rollback()
            except Exception:
                pass
            return HealthCheckResult(
                check_name="fcm_push_health",
                status="ok",
                message="alert_delivery_log 테이블 없음 — 건너뜀",
            )
        logger.exception("FCM Push 체크 오류")
        return HealthCheckResult(
            check_name="fcm_push_health",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 11: 구독 무결성 ─────────────────────────────────────────────────


async def check_subscription_integrity(db: AsyncSession) -> HealthCheckResult:
    """만료된 활성 구독, 플랜 불일치 등 무결성 검사."""
    try:
        # 활성인데 만료된 구독
        expired_active_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM subscriptions"
                " WHERE status = 'active'"
                " AND expires_at < NOW()"
            )
        )
        expired_active = expired_active_q.scalar() or 0

        # pro/pro_plus 플랜인데 활성 구독 없는 유저
        orphan_plan_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM users u"
                " WHERE u.plan IN ('pro', 'pro_plus')"
                " AND NOT EXISTS ("
                "   SELECT 1 FROM subscriptions s"
                "   WHERE s.user_id = u.id AND s.status = 'active'"
                " )"
                " AND u.referral_pro_expires_at IS NULL"
            )
        )
        orphan_plan = orphan_plan_q.scalar() or 0

        issues: list[HealthIssue] = []
        parts = [f"만료된 활성구독: {expired_active}", f"구독없는 유료플랜: {orphan_plan}"]

        if expired_active > 0:
            issues.append(HealthIssue(
                check_name="subscription_integrity",
                severity="warning",
                message=f"만료된 활성 구독 {expired_active}건",
                auto_fix_available=True,
                fix_action="expire_stale_subscriptions",
                fix_params={"count": expired_active},
            ))

        if orphan_plan > 0:
            issues.append(HealthIssue(
                check_name="subscription_integrity",
                severity="warning",
                message=f"활성 구독 없는 유료 플랜 유저 {orphan_plan}명",
                auto_fix_available=True,
                fix_action="expire_stale_subscriptions",
                fix_params={"orphan_plan_count": orphan_plan},
            ))

        return HealthCheckResult(
            check_name="subscription_integrity",
            status="warning" if issues else "ok",
            message="구독 무결성: " + " | ".join(parts),
            issues=issues,
        )
    except Exception as e:
        if "subscriptions" in str(e).lower() or "relation" in str(e).lower():
            try:
                await db.rollback()
            except Exception:
                pass
            return HealthCheckResult(
                check_name="subscription_integrity",
                status="ok",
                message="subscriptions 테이블 없음 — 건너뜀",
            )
        logger.exception("구독 무결성 체크 오류")
        return HealthCheckResult(
            check_name="subscription_integrity",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 12: 긴장도 지수 건강 ────────────────────────────────────────────


async def check_tension_index_health(db: AsyncSession) -> HealthCheckResult:
    """tension_index 최근 레코드 시각 및 0점 비율 확인."""
    try:
        # 최신 레코드 시각
        latest_q = await db.execute(
            text("SELECT MAX(time) FROM tension_index")
        )
        latest = latest_q.scalar()

        if not latest:
            return HealthCheckResult(
                check_name="tension_index_health",
                status="warning",
                message="tension_index 레코드 없음",
            )

        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)

        age = datetime.now(timezone.utc) - latest
        age_min = int(age.total_seconds() / 60)

        issues: list[HealthIssue] = []
        parts = [f"최신: {age_min}분 전"]

        if age_min > 15:
            issues.append(HealthIssue(
                check_name="tension_index_health",
                severity="warning",
                message=f"긴장도 지수 {age_min}분 지연 (5분 주기, 임계값 15분)",
                auto_fix_available=True,
                fix_action="recalculate_tension",
                fix_params={},
            ))

        # 최신 배치의 0점 국가 비율
        zero_q = await db.execute(
            text("""
                WITH latest_batch AS (
                    SELECT country_code, score
                    FROM tension_index
                    WHERE time = (SELECT MAX(time) FROM tension_index)
                )
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE score = 0) as zero_cnt
                FROM latest_batch
            """)
        )
        row = zero_q.fetchone()
        total_countries = row.total if row else 0
        zero_countries = row.zero_cnt if row else 0

        if total_countries > 0:
            zero_pct = (zero_countries / total_countries) * 100
            parts.append(f"0점 비율: {zero_pct:.0f}% ({zero_countries}/{total_countries})")
            if zero_pct > 90:
                issues.append(HealthIssue(
                    check_name="tension_index_health",
                    severity="warning",
                    message=f"0점 국가 비율 {zero_pct:.0f}% (임계값 90%)",
                    auto_fix_available=True,
                    fix_action="recalculate_tension",
                    fix_params={},
                ))

        status = "ok"
        if any(i.severity == "critical" for i in issues):
            status = "critical"
        elif issues:
            status = "warning"

        return HealthCheckResult(
            check_name="tension_index_health",
            status=status,
            message="\n  └ ".join(["긴장도 지수"] + parts),
            issues=issues,
        )
    except Exception as e:
        if "tension_index" in str(e).lower() or "relation" in str(e).lower():
            try:
                await db.rollback()
            except Exception:
                pass
            return HealthCheckResult(
                check_name="tension_index_health",
                status="ok",
                message="tension_index 테이블 없음 — 건너뜀",
            )
        logger.exception("긴장도 지수 체크 오류")
        return HealthCheckResult(
            check_name="tension_index_health",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 13: Redis 건강 ──────────────────────────────────────────────────


async def check_redis_health() -> HealthCheckResult:
    """Redis 메모리 사용량, 키 수 확인."""
    try:
        redis = get_redis()
        info = await redis.info("memory")
        used_mb = info.get("used_memory", 0) / (1024 * 1024)
        peak_mb = info.get("used_memory_peak", 0) / (1024 * 1024)

        dbsize = await redis.dbsize()

        issues: list[HealthIssue] = []
        parts = [f"메모리: {used_mb:.1f}MB (peak {peak_mb:.1f}MB)", f"키 수: {dbsize:,}"]

        if dbsize > 100_000:
            issues.append(HealthIssue(
                check_name="redis_health",
                severity="warning",
                message=f"Redis 키 {dbsize:,}개 (임계값 100,000)",
                auto_fix_available=True,
                fix_action="cleanup_redis_keys",
                fix_params={"dbsize": dbsize},
            ))

        status = "ok" if not issues else "warning"

        return HealthCheckResult(
            check_name="redis_health",
            status=status,
            message="Redis: " + " | ".join(parts),
            issues=issues,
        )
    except Exception as e:
        logger.exception("Redis 건강 체크 오류")
        return HealthCheckResult(
            check_name="redis_health",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 14: 고아 이벤트 ─────────────────────────────────────────────────


async def check_orphan_events(db: AsyncSession) -> HealthCheckResult:
    """cluster_events에 없는 normalized_events (severity >= 20, 최근 7일) 카운트."""
    try:
        orphan_q = await db.execute(
            text("""
                SELECT COUNT(*) FROM normalized_events ne
                WHERE ne.severity >= 20
                  AND ne.is_duplicate = false
                  AND ne.created_at >= NOW() - INTERVAL '7 days'
                  AND NOT EXISTS (
                      SELECT 1 FROM cluster_events ce WHERE ce.event_id = ne.id
                  )
            """)
        )
        orphan_count = orphan_q.scalar() or 0

        issues: list[HealthIssue] = []
        if orphan_count > 500:
            issues.append(HealthIssue(
                check_name="orphan_events",
                severity="critical",
                message=f"고아 이벤트 {orphan_count}개 (임계값 500)",
                auto_fix_available=True,
                fix_action="reprocess_orphans",
                fix_params={"count": orphan_count},
            ))
        elif orphan_count > 100:
            issues.append(HealthIssue(
                check_name="orphan_events",
                severity="warning",
                message=f"고아 이벤트 {orphan_count}개 (임계값 100)",
                auto_fix_available=True,
                fix_action="reprocess_orphans",
                fix_params={"count": orphan_count},
            ))

        status = "ok"
        if any(i.severity == "critical" for i in issues):
            status = "critical"
        elif issues:
            status = "warning"

        return HealthCheckResult(
            check_name="orphan_events",
            status=status,
            message=f"고아 이벤트: {orphan_count}개 (severity>=20, 최근 7일)",
            issues=issues,
        )
    except Exception as e:
        logger.exception("고아 이벤트 체크 오류")
        return HealthCheckResult(
            check_name="orphan_events",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 15: SNS 포스팅 건강 ─────────────────────────────────────────────


async def check_sns_posting_health(db: AsyncSession) -> HealthCheckResult:
    """social_posts에서 stale approved, 장기 pending_review 탐지."""
    try:
        # approved인데 30분 이상 미발행
        stale_approved_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM social_posts"
                " WHERE status = 'approved'"
                " AND approved_at < NOW() - INTERVAL '30 minutes'"
                " AND published_at IS NULL"
            )
        )
        stale_approved = stale_approved_q.scalar() or 0

        # pending_review 48시간 이상 대기
        stale_pending_q = await db.execute(
            text(
                "SELECT COUNT(*) FROM social_posts"
                " WHERE status = 'pending_review'"
                " AND created_at < NOW() - INTERVAL '48 hours'"
            )
        )
        stale_pending = stale_pending_q.scalar() or 0

        issues: list[HealthIssue] = []
        parts = [f"stale approved: {stale_approved}", f"48h+ pending: {stale_pending}"]

        if stale_approved > 5:
            issues.append(HealthIssue(
                check_name="sns_posting_health",
                severity="warning",
                message=f"approved 후 30분+ 미발행 {stale_approved}건 (임계값 5)",
                auto_fix_available=True,
                fix_action="retry_sns_publish",
                fix_params={"stale_approved": stale_approved},
            ))

        if stale_pending > 0:
            issues.append(HealthIssue(
                check_name="sns_posting_health",
                severity="warning",
                message=f"48시간+ 대기 중인 pending_review {stale_pending}건",
                auto_fix_available=False,
            ))

        return HealthCheckResult(
            check_name="sns_posting_health",
            status="warning" if issues else "ok",
            message="SNS 포스팅: " + " | ".join(parts),
            issues=issues,
        )
    except Exception as e:
        if "social_posts" in str(e).lower() or "relation" in str(e).lower():
            try:
                await db.rollback()
            except Exception:
                pass
            return HealthCheckResult(
                check_name="sns_posting_health",
                status="ok",
                message="social_posts 테이블 없음 — 건너뜀",
            )
        logger.exception("SNS 포스팅 체크 오류")
        return HealthCheckResult(
            check_name="sns_posting_health",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 16: SNS 토큰 유효성 ─────────────────────────────────────────────


async def check_sns_token_validity() -> HealthCheckResult:
    """각 SNS 어댑터의 is_configured() 체크."""
    try:
        adapters: dict[str, bool] = {}

        # 동적 import — 어댑터가 없어도 안전
        adapter_modules = {
            "X (Twitter)": "worker.social.adapters.x_adapter",
            "Telegram": "worker.social.adapters.telegram_channel_adapter",
            "Threads": "worker.social.adapters.threads_adapter",
            "Instagram": "worker.social.adapters.instagram_adapter",
            "LinkedIn": "worker.social.adapters.linkedin_adapter",
        }

        import importlib
        for name, module_path in adapter_modules.items():
            try:
                mod = importlib.import_module(module_path)
                adapters[name] = mod.is_configured()
            except Exception:
                adapters[name] = False

        unconfigured = [name for name, ok in adapters.items() if not ok]
        configured = [name for name, ok in adapters.items() if ok]

        parts = []
        if configured:
            parts.append(f"설정됨: {', '.join(configured)}")
        if unconfigured:
            parts.append(f"미설정: {', '.join(unconfigured)}")

        issues: list[HealthIssue] = []
        if unconfigured:
            issues.append(HealthIssue(
                check_name="sns_token_validity",
                severity="info" if len(unconfigured) < len(adapters) else "warning",
                message=f"미설정 어댑터: {', '.join(unconfigured)}",
                auto_fix_available=False,
            ))

        # info 레벨은 ok 상태 유지
        status = "ok"
        if issues and all(i.severity == "warning" for i in issues):
            status = "warning"

        return HealthCheckResult(
            check_name="sns_token_validity",
            status=status,
            message="SNS 토큰: " + " | ".join(parts),
            issues=issues,
        )
    except Exception as e:
        logger.exception("SNS 토큰 체크 오류")
        return HealthCheckResult(
            check_name="sns_token_validity",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 17: KScore 기반 알림 전송 (v7: 스파이크 → KScore) ──────────────


async def check_spike_delivery(db: AsyncSession) -> HealthCheckResult:
    """v7: KScore >= 5.0 + severity >= 50 클러스터 중 알림 미전송 탐지."""
    try:
        undelivered_q = await db.execute(
            text("""
                SELECT COUNT(*) FROM issue_clusters ic
                WHERE ic.kscore >= 5.0
                  AND ic.severity >= 50
                  AND ic.is_active = true
                  AND ic.last_event_at >= NOW() - INTERVAL '6 hours'
                  AND NOT EXISTS (
                      SELECT 1 FROM alert_delivery_log adl
                      WHERE adl.cluster_id = ic.id
                        AND adl.decision = 'sent'
                        AND adl.created_at >= NOW() - INTERVAL '6 hours'
                  )
            """)
        )
        undelivered = undelivered_q.scalar() or 0

        issues: list[HealthIssue] = []
        if undelivered > 0:
            issues.append(HealthIssue(
                check_name="alert_delivery",
                severity="warning",
                message=f"미전송 KScore 알림 {undelivered}건 (KScore>=5.0, severity>=50, 최근 6h)",
                auto_fix_available=True,
                fix_action="retry_alerts",
                fix_params={"undelivered": undelivered},
            ))

        return HealthCheckResult(
            check_name="alert_delivery",
            status="warning" if issues else "ok",
            message=f"KScore 알림 전송: 미전송 {undelivered}건",
            issues=issues,
        )
    except Exception as e:
        if "alert_delivery_log" in str(e).lower() or "relation" in str(e).lower():
            try:
                await db.rollback()
            except Exception:
                pass
            return HealthCheckResult(
                check_name="alert_delivery",
                status="ok",
                message="alert_delivery_log 테이블 없음 — 건너뜀",
            )
        logger.exception("KScore 알림 체크 오류")
        return HealthCheckResult(
            check_name="alert_delivery",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── Check 18: K점수 분포 ──────────────────────────────────────────────────


async def check_kscore_distribution(db: AsyncSession) -> HealthCheckResult:
    """issue_clusters 활성 클러스터의 kscore 분포 확인."""
    try:
        result = await db.execute(
            text("""
                SELECT
                    AVG(kscore) as avg_kscore,
                    MAX(kscore) as max_kscore,
                    MIN(kscore) as min_kscore,
                    COUNT(*) as cnt
                FROM issue_clusters
                WHERE is_active = true AND severity > 0
            """)
        )
        row = result.fetchone()
        cnt = row.cnt if row else 0

        if cnt == 0:
            return HealthCheckResult(
                check_name="kscore_distribution",
                status="ok",
                message="활성 클러스터 없음",
            )

        avg_k = row.avg_kscore or 0
        max_k = row.max_kscore or 0
        min_k = row.min_kscore or 0

        issues: list[HealthIssue] = []
        parts = [
            f"AVG: {avg_k:.2f}",
            f"MAX: {max_k:.2f}",
            f"MIN: {min_k:.2f}",
            f"클러스터: {cnt}개",
        ]

        if max_k == 0:
            issues.append(HealthIssue(
                check_name="kscore_distribution",
                severity="critical",
                message="모든 활성 클러스터 kscore=0 — 계산 중단 의심",
                auto_fix_available=False,
            ))
        elif avg_k > 7:
            issues.append(HealthIssue(
                check_name="kscore_distribution",
                severity="warning",
                message=f"평균 K점수 {avg_k:.2f} (임계값 7) — 과대평가 의심",
                auto_fix_available=False,
            ))
        elif avg_k < 0.5:
            issues.append(HealthIssue(
                check_name="kscore_distribution",
                severity="warning",
                message=f"평균 K점수 {avg_k:.2f} (임계값 0.5) — 과소평가 의심",
                auto_fix_available=False,
            ))

        status = "ok"
        if any(i.severity == "critical" for i in issues):
            status = "critical"
        elif issues:
            status = "warning"

        return HealthCheckResult(
            check_name="kscore_distribution",
            status=status,
            message="\n  └ ".join(["K점수 분포"] + parts),
            issues=issues,
        )
    except Exception as e:
        logger.exception("K점수 분포 체크 오류")
        return HealthCheckResult(
            check_name="kscore_distribution",
            status="warning",
            message=f"체크 오류: {e}",
        )


# ── 전체 헬스체크 실행 ──────────────────────────────────────────────────────


async def run_all_checks() -> list[HealthCheckResult]:
    """18가지 헬스 체크를 모두 실행. 각 체크는 독립 try/except."""
    results: list[HealthCheckResult] = []

    async with AsyncSessionLocal() as db:
        # DB 의존 체크들 (기존 5개 + 신규 8개)
        db_checks = [
            check_misclassification_rate,
            check_source_channels,
            check_cluster_quality,
            check_openai_status,
            check_rss_freshness,
            # ── 신규 DB 의존 체크 ──
            check_api_sources,
            check_duplicate_rate,
            check_fcm_push_health,
            check_subscription_integrity,
            check_tension_index_health,
            check_orphan_events,
            check_sns_posting_health,
            check_spike_delivery,
            check_kscore_distribution,
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

    # DB 독립 체크 (기존 1개 + 신규 3개)
    independent_checks = [
        ("worker_resources", check_worker_resources),
        ("celery_beat_health", check_celery_beat_health),
        ("redis_health", check_redis_health),
        ("sns_token_validity", check_sns_token_validity),
    ]
    for name, check_fn in independent_checks:
        try:
            r = await check_fn()
        except Exception as e:
            r = HealthCheckResult(
                check_name=name,
                status="warning",
                message=f"체크 오류: {e}",
            )
        results.append(r)

    return results

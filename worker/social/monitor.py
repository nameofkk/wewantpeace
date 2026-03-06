"""서비스 모니터링 + AI 에이전트.

8가지 헬스 체크, /status 명령어, AI 질문 응답을 처리합니다.
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import AsyncSessionLocal
from backend.app.core.redis import get_redis

logger = logging.getLogger(__name__)

SOCIAL_TG_BOT_TOKEN = os.getenv("SOCIAL_TG_BOT_TOKEN", "")
SOCIAL_TG_CHAT_ID = os.getenv("SOCIAL_TG_CHAT_ID", "")
_OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

# Anti-spam TTL (초)
_ALERT_COOLDOWN = 1800  # 30분


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


# ── 8가지 헬스 체크 ───────────────────────────────────────────────────────


async def _check_db_connection(db: AsyncSession) -> CheckResult:
    """1. DB 연결 + 레이턴시."""
    t0 = asyncio.get_event_loop().time()
    await db.execute(text("SELECT 1"))
    latency = asyncio.get_event_loop().time() - t0
    ok = latency < 5.0
    return CheckResult(
        name="db_connection",
        ok=ok,
        detail=f"레이턴시 {latency:.2f}s" if ok else f"DB 느림: {latency:.2f}s (>5s)",
    )


async def _check_rss_collection(db: AsyncSession) -> CheckResult:
    """2. RSS 수집 최신성."""
    result = await db.execute(
        text(
            "SELECT MAX(collected_at) FROM raw_events WHERE source_type = 'rss'"
        )
    )
    last = result.scalar()
    if not last:
        return CheckResult("rss_collection", False, "RSS 수집 기록 없음")
    age = datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc) if last.tzinfo is None else datetime.now(timezone.utc) - last
    ok = age < timedelta(minutes=15)
    mins = int(age.total_seconds() / 60)
    return CheckResult(
        "rss_collection",
        ok,
        f"최근 수집: {mins}분 전" if ok else f"RSS 수집 중단: {mins}분 경과 (>15분)",
    )


async def _check_telegram_collection(db: AsyncSession) -> CheckResult:
    """3. Telegram 수집 최신성."""
    result = await db.execute(
        text(
            "SELECT MAX(collected_at) FROM raw_events WHERE source_type = 'telegram'"
        )
    )
    last = result.scalar()
    if not last:
        return CheckResult("telegram_collection", False, "Telegram 수집 기록 없음")
    age = datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc) if last.tzinfo is None else datetime.now(timezone.utc) - last
    ok = age < timedelta(minutes=10)
    mins = int(age.total_seconds() / 60)
    return CheckResult(
        "telegram_collection",
        ok,
        f"최근 수집: {mins}분 전" if ok else f"Telegram 수집 중단: {mins}분 경과 (>10분)",
    )


async def _check_backlog(db: AsyncSession) -> CheckResult:
    """4. 미처리 백로그."""
    result = await db.execute(
        text("SELECT COUNT(*) FROM raw_events WHERE processed = false")
    )
    count = result.scalar() or 0
    ok = count <= 50
    return CheckResult(
        "backlog",
        ok,
        f"미처리: {count}건" if ok else f"백로그 과다: {count}건 (>50)",
    )


async def _check_cluster_freshness(db: AsyncSession) -> CheckResult:
    """5. 클러스터 정체."""
    result = await db.execute(
        text("SELECT MAX(updated_at) FROM issue_clusters WHERE severity > 0")
    )
    last = result.scalar()
    if not last:
        return CheckResult("cluster_freshness", True, "활성 클러스터 없음")
    age = datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc) if last.tzinfo is None else datetime.now(timezone.utc) - last
    ok = age < timedelta(minutes=30)
    mins = int(age.total_seconds() / 60)
    return CheckResult(
        "cluster_freshness",
        ok,
        f"최근 업데이트: {mins}분 전" if ok else f"클러스터 정체: {mins}분 경과 (>30분)",
    )


async def _check_sns_failures(db: AsyncSession) -> CheckResult:
    """6. SNS 발행 실패."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db.execute(
        text(
            "SELECT COUNT(*) FROM social_post_platform spp"
            " JOIN social_posts sp ON spp.post_id = sp.id"
            " WHERE spp.status = 'failed' AND spp.published_at IS NULL"
            " AND sp.created_at >= :cutoff"
        ),
        {"cutoff": cutoff},
    )
    count = result.scalar() or 0
    ok = count == 0
    return CheckResult(
        "sns_failures",
        ok,
        "발행 실패 없음" if ok else f"SNS 발행 실패: {count}건 (최근 1시간)",
    )


async def _check_push_failures(db: AsyncSession) -> CheckResult:
    """7. 푸시 알림 실패."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    result = await db.execute(
        text(
            "SELECT COUNT(*) FROM alert_delivery_log"
            " WHERE decision = 'failed' AND created_at >= :cutoff"
        ),
        {"cutoff": cutoff},
    )
    count = result.scalar() or 0
    ok = count <= 5
    return CheckResult(
        "push_failures",
        ok,
        f"푸시 실패: {count}건" if ok else f"푸시 실패 과다: {count}건 (>5, 최근 1시간)",
    )


async def _check_unpublished_spikes(db: AsyncSession) -> CheckResult:
    """8. 미발행 스파이크."""
    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM spike_events se
            JOIN issue_clusters ic ON se.cluster_id = ic.id
            WHERE ic.severity >= 70
              AND se.triggered_at >= NOW() - INTERVAL '6 hours'
              AND NOT EXISTS (
                  SELECT 1 FROM social_posts sp
                  WHERE sp.source_spike_id = se.id
              )
        """)
    )
    count = result.scalar() or 0
    ok = count == 0
    return CheckResult(
        "unpublished_spikes",
        ok,
        "모든 스파이크 처리됨" if ok else f"미발행 스파이크: {count}건 (severity≥70)",
    )


_ALL_CHECKS = [
    _check_db_connection,
    _check_rss_collection,
    _check_telegram_collection,
    _check_backlog,
    _check_cluster_freshness,
    _check_sns_failures,
    _check_push_failures,
    _check_unpublished_spikes,
]


# ── 공개 API ─────────────────────────────────────────────────────────────


async def check_service_health() -> list[CheckResult]:
    """8가지 헬스 체크 실행. 각 체크는 독립 try/except + rollback."""
    results: list[CheckResult] = []
    async with AsyncSessionLocal() as db:
        for check_fn in _ALL_CHECKS:
            try:
                r = await check_fn(db)
            except Exception as e:
                # SQL 에러 시 트랜잭션 롤백 — 다음 체크가 연쇄 실패하지 않도록
                try:
                    await db.rollback()
                except Exception:
                    pass
                r = CheckResult(
                    name=check_fn.__name__.replace("_check_", ""),
                    ok=False,
                    detail=f"체크 오류: {e}",
                )
            results.append(r)
    return results


async def send_monitoring_alert(results: list[CheckResult]) -> bool:
    """이상 있는 체크에 대해 Telegram 알림 (anti-spam 적용)."""
    if not SOCIAL_TG_BOT_TOKEN or not SOCIAL_TG_CHAT_ID:
        return False

    redis = get_redis()
    alerts: list[str] = []
    resolved: list[str] = []

    for r in results:
        cache_key = f"monitor:alert:{r.name}"
        was_bad = await redis.get(cache_key)

        if not r.ok:
            # 30분 내 동일 알림 방지
            if not was_bad:
                await redis.set(cache_key, "1", ex=_ALERT_COOLDOWN)
                alerts.append(f"🔴 {r.name}: {r.detail}")
        else:
            # 이전에 이상이었다가 해결된 경우
            if was_bad:
                await redis.delete(cache_key)
                resolved.append(f"✅ {r.name}: 해결됨")

    if not alerts and not resolved:
        return False

    lines = []
    if alerts:
        lines.append("⚠️ *서비스 이상 감지*\n")
        lines.extend(alerts)
    if resolved:
        if alerts:
            lines.append("")
        lines.extend(resolved)

    message = "\n".join(lines)

    try:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{SOCIAL_TG_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": SOCIAL_TG_CHAT_ID,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
            if resp.status_code == 200:
                logger.info("모니터링 알림 전송 완료: alerts=%d, resolved=%d", len(alerts), len(resolved))
                return True
            logger.error("모니터링 알림 전송 실패: %s", resp.text)
            return False
    except Exception:
        logger.exception("모니터링 알림 전송 오류")
        return False


async def handle_status_command() -> str:
    """8가지 헬스 체크 결과 + 서비스 요약을 포맷팅."""
    results = await check_service_health()

    lines = ["📊 *WeWantPeace 시스템 상태*\n"]
    all_ok = True
    for r in results:
        icon = "✅" if r.ok else "🔴"
        if not r.ok:
            all_ok = False
        lines.append(f"{icon} {r.name}: {r.detail}")

    # 추가 통계
    try:
        async with AsyncSessionLocal() as db:
            active_clusters = (await db.execute(
                text("SELECT COUNT(*) FROM issue_clusters WHERE severity > 0")
            )).scalar() or 0

            events_24h = (await db.execute(
                text(
                    "SELECT COUNT(*) FROM normalized_events"
                    " WHERE event_time >= NOW() - INTERVAL '24 hours'"
                    " AND is_duplicate = false"
                )
            )).scalar() or 0

            spikes_24h = (await db.execute(
                text(
                    "SELECT COUNT(*) FROM spike_events"
                    " WHERE triggered_at >= NOW() - INTERVAL '24 hours'"
                )
            )).scalar() or 0

            pending_posts = (await db.execute(
                text(
                    "SELECT COUNT(*) FROM social_posts"
                    " WHERE status = 'pending_review'"
                )
            )).scalar() or 0

        lines.append("")
        lines.append(f"📈 활성 클러스터: {active_clusters}개")
        lines.append(f"📰 24h 이벤트: {events_24h}건")
        lines.append(f"⚡ 24h 스파이크: {spikes_24h}건")
        lines.append(f"📝 대기 포스트: {pending_posts}건")
    except Exception as e:
        lines.append(f"\n⚠️ 통계 조회 오류: {e}")

    overall = "✅ 정상" if all_ok else "⚠️ 이상 감지"
    lines.insert(1, f"상태: {overall}\n")

    return "\n".join(lines)


async def handle_ai_question(question: str) -> str:
    """AI 에이전트: 실시간 DB 컨텍스트 + gpt-4o-mini로 질문 응답."""
    if not _OPENAI_KEY:
        return "⚠️ OPENAI_API_KEY가 설정되어 있지 않습니다."

    # DB에서 실시간 컨텍스트 수집
    context_parts: list[str] = []
    try:
        async with AsyncSessionLocal() as db:
            # 최근 스파이크 (6시간 이내)
            spikes = await db.execute(
                text("""
                    SELECT ic.title_ko, ic.title, ic.severity, ic.country_code,
                           se.triggered_at
                    FROM spike_events se
                    JOIN issue_clusters ic ON se.cluster_id = ic.id
                    WHERE se.triggered_at >= NOW() - INTERVAL '6 hours'
                    ORDER BY se.triggered_at DESC
                    LIMIT 5
                """)
            )
            spike_rows = spikes.fetchall()
            if spike_rows:
                context_parts.append("최근 스파이크:")
                for row in spike_rows:
                    title = row.title_ko or row.title
                    context_parts.append(
                        f"  - {title} (severity={row.severity}, "
                        f"country={row.country_code}, {row.triggered_at})"
                    )

            # TOP 10 활성 클러스터
            clusters = await db.execute(
                text("""
                    SELECT title_ko, title, severity, country_code, event_count, kscore
                    FROM issue_clusters
                    WHERE severity > 0
                    ORDER BY kscore DESC
                    LIMIT 10
                """)
            )
            cluster_rows = clusters.fetchall()
            if cluster_rows:
                context_parts.append("\nTOP 10 활성 이슈:")
                for row in cluster_rows:
                    title = row.title_ko or row.title
                    context_parts.append(
                        f"  - {title} (severity={row.severity}, "
                        f"country={row.country_code}, events={row.event_count})"
                    )

            # SNS 포스트 상태
            sns_stats = await db.execute(
                text("""
                    SELECT status, COUNT(*) as cnt
                    FROM social_posts
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY status
                """)
            )
            sns_rows = sns_stats.fetchall()
            if sns_rows:
                context_parts.append("\n24h SNS 포스트 상태:")
                for row in sns_rows:
                    context_parts.append(f"  - {row.status}: {row.cnt}건")

            # 수집 현황
            collection_stats = await db.execute(
                text("""
                    SELECT source_type, COUNT(*) as cnt
                    FROM raw_events
                    WHERE collected_at >= NOW() - INTERVAL '1 hour'
                    GROUP BY source_type
                """)
            )
            coll_rows = collection_stats.fetchall()
            if coll_rows:
                context_parts.append("\n최근 1시간 수집 현황:")
                for row in coll_rows:
                    context_parts.append(f"  - {row.source_type}: {row.cnt}건")

    except Exception as e:
        context_parts.append(f"\n[DB 컨텍스트 수집 오류: {e}]")

    context_text = "\n".join(context_parts) if context_parts else "현재 데이터 없음"

    system_prompt = (
        "당신은 WeWantPeace 서비스의 운영 AI 어시스턴트입니다.\n"
        "WeWantPeace는 전 세계 군사/안보/분쟁 이슈를 실시간으로 수집·분석하는 서비스입니다.\n"
        "아래 실시간 데이터를 참고하여 관리자의 질문에 한국어로 간결하게 답변하세요.\n"
        "데이터에 없는 내용은 추측하지 말고 '데이터에서 확인되지 않습니다'라고 답하세요.\n\n"
        f"=== 실시간 데이터 ===\n{context_text}"
    )

    try:
        reply = await asyncio.to_thread(_call_openai_agent, system_prompt, question)
        return reply if reply else "⚠️ AI 응답이 비어있습니다."
    except Exception:
        logger.exception("AI 에이전트 오류")
        return "⚠️ AI 처리 중 오류가 발생했습니다."


def _call_openai_agent(system_prompt: str, user_prompt: str) -> str:
    """sync OpenAI 호출 (asyncio.to_thread에서 사용)."""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=_OPENAI_KEY, timeout=30.0)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.5,
            max_tokens=1000,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("OpenAI 에이전트 호출 실패")
        return f"⚠️ AI 호출 오류: {type(e).__name__}: {e}"

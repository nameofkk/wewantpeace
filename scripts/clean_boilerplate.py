"""
scripts/clean_boilerplate.py
────────────────────────────
기존 DB에서 편집자 주·재출판 고지·CC라이선스·스팸 boilerplate 데이터 정리.

실행:
  cd ~/Projects/wewantpeace
  python -m scripts.clean_boilerplate [--dry-run] [--batch 500]

처리 순서:
  1. raw_events 스캔 → 스팸/boilerplate 식별
  2. 해당 raw_event에 연결된 normalized_events 조회
  3. cluster_events (CASCADE) 포함 normalized_events 삭제
  4. issue_clusters event_count 재계산 → 0이면 클러스터도 삭제
  5. raw_events 삭제
  6. 본문 중간 boilerplate만 있는 raw_events는 텍스트만 정제 후 업데이트
"""
from __future__ import annotations

import asyncio
import argparse
import logging
import re
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, delete, update, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.models.raw_event import RawEvent
from backend.app.models.normalized_event import NormalizedEvent
from backend.app.models.issue_cluster import IssueCluster, ClusterEvent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── 필터 정의 (rss_collector.py와 동일 조건) ─────────────────────────────────

_SPAM_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"blog (has been|is (now|currently)) (closed|archived|moved|discontinued)",
    r"this (site|blog|page|website) (has|is|will be|has been)",
    r"we (have|'ve) (moved|closed|shut down|discontinued)",
    r"(site|blog|page) (moved|closed|unavailable|no longer)",
    r"(sign up|subscribe) (for|to) (our|the|free|breaking|daily)",
    r"(free|breaking|daily) (news|email|newsletter|app|podcast|alert)",
    r"(get|receive|download) (our|the) (free|daily|breaking)",
    r"(follow|find) us (on|at) (twitter|facebook|instagram|social)",
    r"(click|tap) here to (subscribe|sign up|download|read more)",
    r"download (our|the) (free )?app",
    r"(page|content) (not found|unavailable|removed|deleted)",
    r"404 (error|not found)",
    r"(coming soon|under construction|temporarily unavailable)",
    r"(sponsored|advertisement|advertorial|paid content|promoted)",
    r"(privacy policy|cookie policy|terms of (use|service))$",
    r"(actor|actress|singer|musician|rapper|comedian|celebrity|footballer|athlete).{0,80}(dies|died|dead|passes away|passed away)",
    r"(dies|died|dead|passed away).{0,80}(actor|actress|singer|musician|rapper|comedian|celebrity)",
    r"died aged \d+",
    r"dead at \d+",
    r"passes? away at \d+",
    r"(oscar|grammy|emmy|bafta|golden globe|cannes).{0,60}(winner|nominee|nominated|award)",
    r"(box office|film review|movie review|album review|concert|tour dates)",
    r"(fashion week|runway|supermodel|catwalk)",
    r"(premier league|nba|nfl|nhl|mlb|fifa|champions league|world cup).{0,60}(score|match|game|win|lose|draw|goal)",
    r"(carnival|festival|parade|annual tradition|celebration).{0,120}(battle|fight|throw|toss|hurl|pelt)",
    r"(orange|tomato|flower|food|fruit).{0,80}(battle|fight|throwing|toss|festival|carnival)",
    r"ivrea",
    r"la tomatina",
    r"mardi gras",
    r"(rio|venice|nice|cologne|trinidad).{0,30}carnival",
    # 편집자 주 전체가 기사인 경우
    r"^editor'?s?\s+(note|correction)\s*[:\-–].{0,400}(creative commons|license|republished|copyright)",
    r"^this article (was|has been) (republished|reprinted).{0,300}(creative commons|permission|license)",
]]

_PROMO_SENTENCE_PATTERNS: list[re.Pattern] = [re.compile(p, re.IGNORECASE) for p in [
    r"editor'?s?\s+(note|correction|update)\s*[:\-–]",
    r"this article (was|has been|is) (republished|reprinted|reposted|syndicated|originally published)",
    r"(republished|reprinted|reposted|syndicated) (with (permission|consent)|from|by|under)",
    r"(originally|first) (published|appeared|posted) (in|on|at|by)",
    r"this (story|article|piece|report) (was|is|has been) (first|originally|previously)",
    r"(this|the) article (is|was) (from|provided by|courtesy of|by)",
    r"(read|view|see) the (original|full) (article|story|post|version)",
    r"creative commons (license|licence|attribution)",
    r"(licensed|published|shared) under (a )?(creative commons|cc by|cc-by)",
    r"(cc\s*by|cc\s*nc|cc\s*sa|cc\s*nd)[\s\-][\d.]+",
    r"^(ap|afp|reuters|bloomberg|bbc|guardian)\s*(reporting|report)\s*[:\-–]",
    r"(associated press|agence france-presse)\s*contributed",
    r"wire (service|story|report) (from|by|provided by)",
    r"copyright\s+©?\s+\d{4}",
    r"©\s+\d{4}\s+\w",
    r"all rights reserved",
    r"(do not|may not) (reproduce|republish|redistribute)",
    r"this (is a )?developing story",
    r"this (story|article|post) (will be|has been|was) updated",
    r"(we will|we'll) update this (story|article|post)",
    r"(whatsapp|telegram|discord).{0,60}(join|subscribe|channel|가입|채널)",
    r"(to stay|to keep).{0,30}(up.to.date|updated|informed).{0,100}",
    r"(this investigation|this report).{0,30}(part of|collaboration|partnership)",
    r"(sign up|subscribe|join).{0,50}(here|now|today)",
    r"^(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}\b.{0,60}$",
    r"(click|tap|read more|see more|learn more).{0,30}(here|below|above|→|»)",
    r"(share|follow|like).{0,20}(this|us|our).{0,30}(story|article|page|account)",
    r".{0,30}(채널|뉴스레터|이메일).{0,30}(구독|가입|신청).{0,60}",
    r"(편집자|기자)\s*(주|노트|코멘트)\s*[:\-：]",
    r"이 (기사|콘텐츠|글)는?.{0,30}(재게재|재배포|제공|출처)",
    r"크리에이티브 커먼즈.{0,30}라이선스",
    r"저작권.{0,20}\d{4}",
    r"무단 (전재|복제|배포|전용).{0,30}(금지|위반)",
]]

MIN_WORDS = 8
MIN_CHARS = 60


def _is_spam(text: str) -> bool:
    for pattern in _SPAM_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _strip_promo_sentences(text: str) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    clean = []
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if any(p.search(sent) for p in _PROMO_SENTENCE_PATTERNS):
            continue
        clean.append(sent)
    return " ".join(clean).strip()


def _is_quality(text: str) -> bool:
    return len(text.split()) >= MIN_WORDS and len(text) >= MIN_CHARS


# ── 메인 정리 로직 ────────────────────────────────────────────────────────────

async def clean(dry_run: bool, batch_size: int) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    to_delete_raw: list[str] = []      # 삭제할 raw_event ID
    to_update_raw: list[tuple[str, str]] = []  # (id, cleaned_text) 업데이트할 항목

    async with async_session() as session:
        # ── 1단계: raw_events 스캔 ──────────────────────────────────────────
        logger.info("raw_events 스캔 시작...")
        offset = 0
        total_scanned = 0

        while True:
            result = await session.execute(
                select(RawEvent.id, RawEvent.raw_text)
                .order_by(RawEvent.id)
                .offset(offset)
                .limit(batch_size)
            )
            rows = result.all()
            if not rows:
                break

            for row_id, raw_text in rows:
                text = raw_text or ""

                # 스팸 전체 차단
                if _is_spam(text):
                    to_delete_raw.append(str(row_id))
                    continue

                # 문장 단위 boilerplate 제거 후 품질 확인
                cleaned = _strip_promo_sentences(text)
                if cleaned != text:
                    if _is_quality(cleaned):
                        to_update_raw.append((str(row_id), cleaned))
                    else:
                        # 정제 후 너무 짧아지면 삭제
                        to_delete_raw.append(str(row_id))

            total_scanned += len(rows)
            offset += batch_size
            logger.info("  스캔: %d개 완료 (삭제 대상: %d, 정제 대상: %d)",
                        total_scanned, len(to_delete_raw), len(to_update_raw))

        logger.info("스캔 완료 — 삭제: %d개, 텍스트 정제: %d개", len(to_delete_raw), len(to_update_raw))

        if dry_run:
            logger.info("[DRY-RUN] 실제 DB 변경 없이 종료합니다.")
            await engine.dispose()
            return

        # ── 2단계: 삭제 대상 처리 ────────────────────────────────────────────
        if to_delete_raw:
            logger.info("normalized_events 조회 및 삭제 시작...")

            # 배치 처리
            for i in range(0, len(to_delete_raw), batch_size):
                chunk = to_delete_raw[i:i + batch_size]

                # 해당 raw_event에 연결된 normalized_event ID 조회
                norm_result = await session.execute(
                    select(NormalizedEvent.id)
                    .where(NormalizedEvent.raw_event_id.in_(
                        [__import__('uuid').UUID(x) for x in chunk]
                    ))
                )
                norm_ids = [str(r[0]) for r in norm_result.all()]

                if norm_ids:
                    # cluster_events에서 해당 이벤트가 속한 클러스터 ID와 개수 집계
                    cluster_counts_result = await session.execute(
                        select(
                            ClusterEvent.cluster_id,
                            func.count(ClusterEvent.event_id).label("cnt")
                        )
                        .where(ClusterEvent.event_id.in_(
                            [__import__('uuid').UUID(x) for x in norm_ids]
                        ))
                        .group_by(ClusterEvent.cluster_id)
                    )
                    cluster_counts = {str(r[0]): r[1] for r in cluster_counts_result.all()}

                    # cluster_events CASCADE 삭제 → normalized_events 삭제
                    await session.execute(
                        delete(NormalizedEvent).where(
                            NormalizedEvent.id.in_(
                                [__import__('uuid').UUID(x) for x in norm_ids]
                            )
                        )
                    )

                    # issue_clusters event_count 재계산
                    for cluster_id_str, removed_cnt in cluster_counts.items():
                        await session.execute(
                            update(IssueCluster)
                            .where(IssueCluster.id == __import__('uuid').UUID(cluster_id_str))
                            .values(event_count=IssueCluster.event_count - removed_cnt)
                        )

                # raw_events 삭제
                await session.execute(
                    delete(RawEvent).where(
                        RawEvent.id.in_(
                            [__import__('uuid').UUID(x) for x in chunk]
                        )
                    )
                )

                await session.commit()
                logger.info("  삭제 배치 %d/%d 완료", i + len(chunk), len(to_delete_raw))

            # ── 3단계: event_count ≤ 0인 클러스터 삭제 ────────────────────────
            logger.info("빈 클러스터 삭제 중...")
            deleted_clusters = await session.execute(
                delete(IssueCluster)
                .where(IssueCluster.event_count <= 0)
                .returning(IssueCluster.id)
            )
            cluster_del_count = len(deleted_clusters.all())
            await session.commit()
            logger.info("빈 클러스터 %d개 삭제 완료", cluster_del_count)

        # ── 4단계: 텍스트 정제 업데이트 ─────────────────────────────────────
        if to_update_raw:
            logger.info("텍스트 정제 업데이트 시작 (%d개)...", len(to_update_raw))
            import uuid as _uuid
            for i in range(0, len(to_update_raw), batch_size):
                chunk = to_update_raw[i:i + batch_size]
                for raw_id_str, cleaned_text in chunk:
                    await session.execute(
                        update(RawEvent)
                        .where(RawEvent.id == _uuid.UUID(raw_id_str))
                        .values(raw_text=cleaned_text)
                    )
                await session.commit()
                logger.info("  정제 배치 %d/%d 완료", i + len(chunk), len(to_update_raw))

    logger.info("✓ 정리 완료")
    await engine.dispose()


# ── 진입점 ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DB boilerplate 정리 스크립트")
    parser.add_argument("--dry-run", action="store_true",
                        help="실제 삭제 없이 대상만 카운트 출력")
    parser.add_argument("--batch", type=int, default=500,
                        help="배치 크기 (기본값: 500)")
    args = parser.parse_args()

    asyncio.run(clean(dry_run=args.dry_run, batch_size=args.batch))

"""Multi-signal convergence detector.

When 3+ distinct topic types are active in a single country within 24 hours,
it signals escalating instability. Different combinations carry different weight.

Political/military convergence (conflict, coup, protest, sanctions, terror, cyber)
indicates intentional crisis escalation. Natural disaster convergence (disaster, health)
signals compound humanitarian crisis. Mixed convergence has intermediate weight.

Integration: called from tension_calculator.calculate_country_tension() after
raw_score calculation, before percentile/floor. Adds convergence_bonus to raw_score.
"""
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.issue_cluster import IssueCluster

logger = logging.getLogger(__name__)

# Political/military convergence -- intentional crisis signal (high weight)
POLITICAL_MILITARY = {"conflict", "coup", "protest", "sanctions", "terror", "cyber"}

# Natural disaster convergence -- compound disaster (medium weight, not intentional)
NATURAL_DISASTER = {"disaster", "health"}


def calc_convergence_bonus(active_topics: set[str]) -> float:
    """Calculate convergence bonus for a country based on active topic types.

    Returns bonus points (0~25) to add to raw_score.
    """
    pol_mil = active_topics & POLITICAL_MILITARY
    nat_dis = active_topics & NATURAL_DISASTER

    if len(pol_mil) >= 3:
        # Political/military 3+ convergence: high crisis signal
        return min(25.0, len(pol_mil) * 7.0)
    elif len(pol_mil) >= 2 and len(nat_dis) >= 1:
        # Mixed convergence: disaster + political unrest
        return min(15.0, (len(pol_mil) + len(nat_dis)) * 4.0)
    elif len(active_topics) >= 3 and len(pol_mil) < 2:
        # Natural disaster-centric compound: lower bonus
        return min(10.0, len(active_topics) * 3.0)
    return 0.0


async def detect_convergence(session: AsyncSession) -> dict[str, float]:
    """Scan active clusters and return convergence bonuses per country.

    Queries issue_clusters for active clusters in the last 24 hours,
    groups by country_code, and calculates convergence bonus for each
    country with 3+ distinct active topic types.

    Returns: {country_code: bonus_points}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    stmt = (
        select(
            IssueCluster.country_code,
            func.array_agg(func.distinct(IssueCluster.topic)).label("topics"),
        )
        .where(
            and_(
                IssueCluster.is_active == True,  # noqa: E712
                IssueCluster.last_event_at >= cutoff,
                IssueCluster.country_code.isnot(None),
                IssueCluster.topic.isnot(None),
            )
        )
        .group_by(IssueCluster.country_code)
    )

    result = await session.execute(stmt)
    rows = result.all()

    bonuses: dict[str, float] = {}
    for row in rows:
        cc = row.country_code
        topics = set(row.topics) if row.topics else set()
        if len(topics) < 3:
            continue
        bonus = calc_convergence_bonus(topics)
        if bonus > 0:
            bonuses[cc] = bonus
            logger.info(
                "Convergence detected: %s topics=%s bonus=%.1f",
                cc, topics, bonus,
            )

    return bonuses

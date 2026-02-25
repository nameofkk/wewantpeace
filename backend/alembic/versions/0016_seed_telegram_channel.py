"""seed telegram channel

Revision ID: 0016
Revises: 0015
Create Date: 2026-02-25

Telegram Bot 채널 활성화 — channel_id=NULL (catch-all 모드)로
봇이 수신하는 모든 메시지를 수집.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 이미 telegram 채널이 활성화되어 있으면 스킵
    result = conn.execute(
        sa.text("SELECT COUNT(*) FROM source_channels WHERE source_type = 'telegram' AND is_active = true")
    )
    count = result.scalar()
    if count and count > 0:
        return

    conn.execute(
        sa.text("""
            INSERT INTO source_channels
              (display_name, source_type, tier, base_confidence, language,
               channel_id, username, topics, geo_focus, is_active)
            VALUES
              (:display_name, :source_type, :tier, :base_confidence, :language,
               :channel_id, :username, :topics, :geo_focus, true)
            ON CONFLICT DO NOTHING
        """).bindparams(
            sa.bindparam("topics", type_=sa.ARRAY(sa.Text())),
            sa.bindparam("geo_focus", type_=sa.ARRAY(sa.Text())),
        ),
        {
            "display_name": "WeWantPeace Bot (catch-all)",
            "source_type": "telegram",
            "tier": "C",
            "base_confidence": 0.55,
            "language": None,
            "channel_id": None,
            "username": "WeWantPeace_bot",
            "topics": [],
            "geo_focus": [],
        },
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM source_channels WHERE source_type = 'telegram' AND display_name = 'WeWantPeace Bot (catch-all)'"
    )

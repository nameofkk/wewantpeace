"""activate osint channels

Revision ID: 0017
Revises: 0016
Create Date: 2026-02-25

Telethon MTProto 전환에 따라:
- seed_sources.py의 OSINT 채널 5개를 DB에 INSERT (없으면) + is_active=True
- 0016의 "WeWantPeace Bot (catch-all)" 채널 비활성화 (Telethon에서 불필요)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OSINT_CHANNELS = [
    {
        "username": "IntelSlava",
        "display_name": "Intel Slava Z",
        "tier": "C",
        "base_confidence": 0.55,
        "language": "ru",
        "topics": ["conflict", "military"],
        "geo_focus": ["UA", "RU"],
    },
    {
        "username": "OSINTdefender",
        "display_name": "OSINT Defender",
        "tier": "B",
        "base_confidence": 0.70,
        "language": "en",
        "topics": ["conflict", "cyber", "terror"],
        "geo_focus": [],
    },
    {
        "username": "GeoConfirmed",
        "display_name": "GeoConfirmed",
        "tier": "B",
        "base_confidence": 0.72,
        "language": "en",
        "topics": ["conflict", "military"],
        "geo_focus": [],
    },
    {
        "username": "warmonitor1",
        "display_name": "War Monitor",
        "tier": "C",
        "base_confidence": 0.58,
        "language": "en",
        "topics": ["conflict", "military"],
        "geo_focus": [],
    },
    {
        "username": "hacktivist1",
        "display_name": "Cyber Monitor",
        "tier": "C",
        "base_confidence": 0.55,
        "language": "en",
        "topics": ["cyber"],
        "geo_focus": [],
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    # 0016의 catch-all 봇 채널 비활성화 (Telethon에서 불필요)
    conn.execute(
        sa.text(
            "UPDATE source_channels SET is_active = false "
            "WHERE source_type = 'telegram' AND display_name = 'WeWantPeace Bot (catch-all)'"
        )
    )

    # OSINT 채널 5개 INSERT (없으면) + 활성화
    for ch in OSINT_CHANNELS:
        # 이미 존재하는지 확인 (username 기준)
        result = conn.execute(
            sa.text(
                "SELECT id FROM source_channels "
                "WHERE source_type = 'telegram' AND username = :username"
            ),
            {"username": ch["username"]},
        )
        row = result.fetchone()

        if row:
            # 이미 존재하면 활성화만
            conn.execute(
                sa.text(
                    "UPDATE source_channels SET is_active = true WHERE id = :id"
                ),
                {"id": row[0]},
            )
        else:
            # 새로 INSERT
            conn.execute(
                sa.text("""
                    INSERT INTO source_channels
                      (display_name, source_type, tier, base_confidence, language,
                       channel_id, username, topics, geo_focus, is_active)
                    VALUES
                      (:display_name, :source_type, :tier, :base_confidence, :language,
                       NULL, :username, :topics, :geo_focus, true)
                """).bindparams(
                    sa.bindparam("topics", type_=sa.ARRAY(sa.Text())),
                    sa.bindparam("geo_focus", type_=sa.ARRAY(sa.Text())),
                ),
                {
                    "display_name": ch["display_name"],
                    "source_type": "telegram",
                    "tier": ch["tier"],
                    "base_confidence": ch["base_confidence"],
                    "language": ch["language"],
                    "username": ch["username"],
                    "topics": ch["topics"],
                    "geo_focus": ch["geo_focus"],
                },
            )


def downgrade() -> None:
    conn = op.get_bind()

    # OSINT 채널 5개 비활성화
    usernames = [ch["username"] for ch in OSINT_CHANNELS]
    for username in usernames:
        conn.execute(
            sa.text(
                "UPDATE source_channels SET is_active = false "
                "WHERE source_type = 'telegram' AND username = :username"
            ),
            {"username": username},
        )

    # catch-all 봇 채널 재활성화
    conn.execute(
        sa.text(
            "UPDATE source_channels SET is_active = true "
            "WHERE source_type = 'telegram' AND display_name = 'WeWantPeace Bot (catch-all)'"
        )
    )

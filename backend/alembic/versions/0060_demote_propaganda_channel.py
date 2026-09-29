"""친러 선전 텔레그램(Intel Slava Z)을 D등급(미검증)으로 내림

이라크 뉴스 채널과 같은 C등급("중립")으로 들어가 있어서, 이슈 상세 타임라인에
경고 없이 일반 출처처럼 노출됐다. D등급으로 내리면 화면에 "미검증" 배지가 붙고
confidence 도 D 기준(0.35)으로 계산된다. 이미 적재된 이벤트의 등급도 같이 맞춘다.

Revision ID: 0060
Revises: 0059
"""
from alembic import op

revision = "0060"
down_revision = "0059"

_CHANNEL = "intelslava"


def upgrade() -> None:
    op.execute(
        f"""
        UPDATE source_channels
        SET tier = 'D', base_confidence = 0.35, updated_at = now()
        WHERE username = '{_CHANNEL}'
        """
    )
    op.execute(
        f"""
        UPDATE normalized_events ne
        SET source_tier = 'D'
        FROM raw_events re, source_channels sc
        WHERE ne.raw_event_id = re.id
          AND re.source_channel_id = sc.id
          AND sc.username = '{_CHANNEL}'
          AND ne.source_tier <> 'D'
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        UPDATE source_channels
        SET tier = 'C', base_confidence = 0.55, updated_at = now()
        WHERE username = '{_CHANNEL}'
        """
    )

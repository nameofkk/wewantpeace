"""Spike 모델 → KScore Alert 모델 전환 (소프트 마이그레이션)

- user_missed_spike_summary → user_missed_alert_summary 리네임
- spike_event_id → alert_cluster_id 컬럼 리네임
- notifications.type에서 'spike' → 'fast' 업데이트
- 기존 테이블/컬럼은 삭제하지 않음 (히스토리 보존)

Revision ID: 0040
Revises: 0039
"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"


def upgrade():
    # 1. user_missed_spike_summary → user_missed_alert_summary
    op.rename_table("user_missed_spike_summary", "user_missed_alert_summary")

    # 2. spike_event_id → alert_cluster_id
    op.alter_column(
        "user_missed_alert_summary",
        "spike_event_id",
        new_column_name="alert_cluster_id",
    )

    # 3. notifications.type: 'spike' → 'fast'
    op.execute("UPDATE notifications SET type = 'fast' WHERE type = 'spike'")


def downgrade():
    # 3. notifications.type: 'fast' → 'spike' 복원
    op.execute("UPDATE notifications SET type = 'spike' WHERE type = 'fast'")

    # 2. alert_cluster_id → spike_event_id 복원
    op.alter_column(
        "user_missed_alert_summary",
        "alert_cluster_id",
        new_column_name="spike_event_id",
    )

    # 1. user_missed_alert_summary → user_missed_spike_summary 복원
    op.rename_table("user_missed_alert_summary", "user_missed_spike_summary")

"""Add image_url to normalized_events and issue_clusters

Revision ID: 0030
Revises: 0029
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)

    ne_cols = {c["name"] for c in inspector.get_columns("normalized_events")}
    if "image_url" not in ne_cols:
        op.add_column("normalized_events", sa.Column("image_url", sa.String(1024), nullable=True))

    ic_cols = {c["name"] for c in inspector.get_columns("issue_clusters")}
    if "image_url" not in ic_cols:
        op.add_column("issue_clusters", sa.Column("image_url", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("issue_clusters", "image_url")
    op.drop_column("normalized_events", "image_url")

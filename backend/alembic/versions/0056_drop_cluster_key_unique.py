"""drop cluster_key unique constraint — same country:topic can have multiple clusters

Revision ID: 0056
Revises: 0055
"""
from alembic import op

revision = "0056"
down_revision = "0055"


def upgrade() -> None:
    # Drop the UNIQUE constraint added in 0055
    op.drop_constraint("uq_issue_clusters_cluster_key", "issue_clusters", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("uq_issue_clusters_cluster_key", "issue_clusters", ["cluster_key"])

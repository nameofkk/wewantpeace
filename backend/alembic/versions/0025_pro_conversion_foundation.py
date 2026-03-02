"""pro conversion foundation tables and columns

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # ── A. spike_events table ──────────────────────────────────────────
    if "spike_events" not in existing_tables:
        op.create_table(
            "spike_events",
            sa.Column("id", sa.dialects.postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("cluster_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("issue_clusters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("severity", sa.SmallInteger(), nullable=False),
            sa.Column("kscore", sa.Float(), nullable=False),
            sa.Column("c1", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("c10", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("baseline", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("ratio", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("unique_sources", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index(
            "ix_spike_events_cluster",
            "spike_events",
            ["cluster_id", "triggered_at"],
        )

    # ── B. alert_delivery_log table ────────────────────────────────────
    if "alert_delivery_log" not in existing_tables:
        op.create_table(
            "alert_delivery_log",
            sa.Column("id", sa.dialects.postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("user_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cluster_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("issue_clusters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("spike_event_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("spike_events.id", ondelete="SET NULL"), nullable=True),
            sa.Column("alert_type", sa.String(16), nullable=False),
            sa.Column("decision", sa.String(16), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("suppression_reason", sa.String(64), nullable=True),
            sa.Column("failure_reason", sa.String(256), nullable=True),
            sa.Column("platform", sa.String(16), nullable=False, server_default=sa.text("'web'")),
            sa.Column("pipeline_mode", sa.String(16), nullable=False, server_default=sa.text("'shadow'")),
            sa.Column("collapse_key", sa.String(128), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.CheckConstraint("decision IN ('pending','sent','failed','suppressed')", name="ck_delivery_decision"),
            sa.CheckConstraint("pipeline_mode IN ('shadow','primary')", name="ck_pipeline_mode"),
        )
        op.create_index(
            "uq_delivery_user_spike",
            "alert_delivery_log",
            ["user_id", "spike_event_id", "alert_type"],
            unique=True,
        )
        op.create_index(
            "ix_delivery_created",
            "alert_delivery_log",
            ["created_at"],
        )
        op.create_index(
            "ix_delivery_decision",
            "alert_delivery_log",
            ["decision", "created_at"],
        )

        # TimescaleDB hypertable (optional)
        try:
            op.execute(sa.text(
                "SELECT create_hypertable('alert_delivery_log', 'created_at', "
                "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE)"
            ))
            op.execute(sa.text(
                "SELECT add_retention_policy('alert_delivery_log', "
                "INTERVAL '90 days', if_not_exists => TRUE)"
            ))
        except Exception:
            pass  # TimescaleDB not available

    # ── C. user_push_tokens improvements ───────────────────────────────
    if "user_push_tokens" in existing_tables:
        push_cols = [c["name"] for c in inspector.get_columns("user_push_tokens")]

        if "status" not in push_cols:
            op.add_column(
                "user_push_tokens",
                sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
            )
            op.execute(sa.text(
                "ALTER TABLE user_push_tokens ADD CONSTRAINT ck_token_status "
                "CHECK (status IN ('active','expired','revoked'))"
            ))

        if "last_seen_at" not in push_cols:
            op.add_column(
                "user_push_tokens",
                sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
            )

        op.create_index(
            "ix_push_tokens_active",
            "user_push_tokens",
            ["user_id"],
            postgresql_where=sa.text("status = 'active'"),
            if_not_exists=True,
        )

    # ── D. user_missed_spike_summary table ─────────────────────────────
    if "user_missed_spike_summary" not in existing_tables:
        op.create_table(
            "user_missed_spike_summary",
            sa.Column("id", sa.dialects.postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("user_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("cluster_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("issue_clusters.id", ondelete="CASCADE"), nullable=False),
            sa.Column("spike_event_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("spike_events.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reason", sa.String(32), nullable=False),
            sa.Column("is_shown", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index(
            "ix_missed_spike_user",
            "user_missed_spike_summary",
            ["user_id", "is_shown", "created_at"],
        )

    # ── E. subscriptions trial columns ─────────────────────────────────
    if "subscriptions" in existing_tables:
        sub_cols = [c["name"] for c in inspector.get_columns("subscriptions")]

        if "trial_start" not in sub_cols:
            op.add_column(
                "subscriptions",
                sa.Column("trial_start", sa.DateTime(timezone=True), nullable=True),
            )

        if "trial_end" not in sub_cols:
            op.add_column(
                "subscriptions",
                sa.Column("trial_end", sa.DateTime(timezone=True), nullable=True),
            )

        op.create_index(
            "ix_sub_trial",
            "subscriptions",
            ["status", "trial_end"],
            postgresql_where=sa.text("status = 'trial'"),
            if_not_exists=True,
        )

    # ── F. paywall_events table ────────────────────────────────────────
    if "paywall_events" not in existing_tables:
        op.create_table(
            "paywall_events",
            sa.Column("id", sa.dialects.postgresql.UUID(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("user_id", sa.dialects.postgresql.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("trigger", sa.String(64), nullable=False),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("source", sa.String(64), nullable=True),
            sa.Column("plan", sa.String(16), nullable=True),
            sa.Column("session_id", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index(
            "ix_paywall_user",
            "paywall_events",
            ["user_id", "created_at"],
        )

    # ── G. user_preferences intent column ──────────────────────────────
    if "user_preferences" in existing_tables:
        pref_cols = [c["name"] for c in inspector.get_columns("user_preferences")]

        if "intent" not in pref_cols:
            op.add_column(
                "user_preferences",
                sa.Column("intent", sa.String(16), server_default=sa.text("'general'")),
            )
            op.execute(sa.text(
                "ALTER TABLE user_preferences ADD CONSTRAINT ck_pref_intent "
                "CHECK (intent IN ('travel','invest','expat','general'))"
            ))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    existing_tables = inspector.get_table_names()

    # ── G. user_preferences intent column ──────────────────────────────
    if "user_preferences" in existing_tables:
        pref_cols = [c["name"] for c in inspector.get_columns("user_preferences")]
        if "intent" in pref_cols:
            op.execute(sa.text(
                "ALTER TABLE user_preferences DROP CONSTRAINT IF EXISTS ck_pref_intent"
            ))
            op.drop_column("user_preferences", "intent")

    # ── F. paywall_events table ────────────────────────────────────────
    if "paywall_events" in existing_tables:
        op.drop_index("ix_paywall_user", table_name="paywall_events")
        op.drop_table("paywall_events")

    # ── E. subscriptions trial columns ─────────────────────────────────
    if "subscriptions" in existing_tables:
        sub_cols = [c["name"] for c in inspector.get_columns("subscriptions")]
        op.drop_index("ix_sub_trial", table_name="subscriptions", if_exists=True)
        if "trial_end" in sub_cols:
            op.drop_column("subscriptions", "trial_end")
        if "trial_start" in sub_cols:
            op.drop_column("subscriptions", "trial_start")

    # ── D. user_missed_spike_summary table ─────────────────────────────
    if "user_missed_spike_summary" in existing_tables:
        op.drop_index("ix_missed_spike_user", table_name="user_missed_spike_summary")
        op.drop_table("user_missed_spike_summary")

    # ── C. user_push_tokens improvements ───────────────────────────────
    if "user_push_tokens" in existing_tables:
        push_cols = [c["name"] for c in inspector.get_columns("user_push_tokens")]
        op.drop_index("ix_push_tokens_active", table_name="user_push_tokens", if_exists=True)
        if "last_seen_at" in push_cols:
            op.drop_column("user_push_tokens", "last_seen_at")
        if "status" in push_cols:
            op.execute(sa.text(
                "ALTER TABLE user_push_tokens DROP CONSTRAINT IF EXISTS ck_token_status"
            ))
            op.drop_column("user_push_tokens", "status")

    # ── B. alert_delivery_log table ────────────────────────────────────
    if "alert_delivery_log" in existing_tables:
        # Remove retention policy if TimescaleDB is available
        try:
            op.execute(sa.text(
                "SELECT remove_retention_policy('alert_delivery_log', if_exists => TRUE)"
            ))
        except Exception:
            pass
        op.drop_index("ix_delivery_decision", table_name="alert_delivery_log")
        op.drop_index("ix_delivery_created", table_name="alert_delivery_log")
        op.drop_index("uq_delivery_user_spike", table_name="alert_delivery_log")
        op.drop_table("alert_delivery_log")

    # ── A. spike_events table ──────────────────────────────────────────
    if "spike_events" in existing_tables:
        op.drop_index("ix_spike_events_cluster", table_name="spike_events")
        op.drop_table("spike_events")

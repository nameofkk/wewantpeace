"""경제 데이터 테이블 생성 (Tier 2 데이터 파이프라인)

trade_bilateral: IMF IMTS 양자간 교역 데이터
economic_indicator: World Bank 경제 지표
exchange_rate: Frankfurter ECB 환율

Revision ID: 0045
Revises: 0044
"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"


def upgrade():
    # trade_bilateral
    op.create_table(
        "trade_bilateral",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("reporter_code", sa.String(4), nullable=False),
        sa.Column("partner_code", sa.String(4), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("period_type", sa.String(1), nullable=False, server_default="A"),
        sa.Column("export_value_usd", sa.Float, nullable=True),
        sa.Column("import_value_usd", sa.Float, nullable=True),
        sa.Column("total_trade_usd", sa.Float, nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="imf_imts"),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_trade_bilateral_reporter", "trade_bilateral", ["reporter_code"])
    op.create_index("ix_trade_bilateral_pair", "trade_bilateral", ["reporter_code", "partner_code"])
    op.create_index("ix_trade_bilateral_period", "trade_bilateral", ["period"])

    # economic_indicator
    op.create_table(
        "economic_indicator",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(4), nullable=False),
        sa.Column("indicator_code", sa.String(40), nullable=False),
        sa.Column("indicator_name", sa.Text, nullable=True),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="world_bank"),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_econ_indicator_country", "economic_indicator", ["country_code"])
    op.create_index("ix_econ_indicator_lookup", "economic_indicator", ["country_code", "indicator_code", "year"])

    # exchange_rate
    op.create_table(
        "exchange_rate",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("target_currency", sa.String(3), nullable=False),
        sa.Column("rate_date", sa.String(10), nullable=False),
        sa.Column("rate", sa.Float, nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_exchange_rate_date", "exchange_rate", ["rate_date"])
    op.create_index("ix_exchange_rate_lookup", "exchange_rate", ["base_currency", "target_currency", "rate_date"])


def downgrade():
    op.drop_table("exchange_rate")
    op.drop_table("economic_indicator")
    op.drop_table("trade_bilateral")

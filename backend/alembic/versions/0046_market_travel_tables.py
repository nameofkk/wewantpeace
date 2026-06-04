"""시장 데이터 + 여행 경보 테이블 (Phase 2)

commodity_price: yfinance 원자재 가격
market_index: yfinance 주가 지수
travel_advisory: 구조화된 여행 경보

Revision ID: 0046
Revises: 0045
"""
from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"


def upgrade():
    # commodity_price
    op.create_table(
        "commodity_price",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("price_usd", sa.Float, nullable=False),
        sa.Column("change_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("price_date", sa.String(10), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_commodity_price_symbol_date", "commodity_price", ["symbol", "price_date"])

    # market_index
    op.create_table(
        "market_index",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("change_pct", sa.Float, nullable=False, server_default="0"),
        sa.Column("index_date", sa.String(10), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_market_index_symbol_date", "market_index", ["symbol", "index_date"])

    # travel_advisory
    op.create_table(
        "travel_advisory",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_travel_advisory_country_source", "travel_advisory", ["country_code", "source"])


def downgrade():
    op.drop_table("travel_advisory")
    op.drop_table("market_index")
    op.drop_table("commodity_price")

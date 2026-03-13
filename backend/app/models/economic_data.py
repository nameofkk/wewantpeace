"""
외부 경제 데이터 모델 — Tier 2 데이터 파이프라인

trade_bilateral: IMF IMTS 양자간 교역 데이터
economic_indicator: World Bank 경제 지표 (GDP, 교역 의존도 등)
exchange_rate: Frankfurter ECB 환율 데이터
"""

from sqlalchemy import Float, String, Integer, TIMESTAMP, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from backend.app.core.database import Base


class TradeBilateral(Base):
    """IMF IMTS 양자간 교역 데이터 (월간/연간)"""
    __tablename__ = "trade_bilateral"
    __table_args__ = (
        Index("ix_trade_bilateral_reporter", "reporter_code"),
        Index("ix_trade_bilateral_pair", "reporter_code", "partner_code"),
        Index("ix_trade_bilateral_period", "period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reporter_code: Mapped[str] = mapped_column(String(4), nullable=False)
    partner_code: Mapped[str] = mapped_column(String(4), nullable=False)
    period: Mapped[str] = mapped_column(String(10), nullable=False)  # "2024" or "2024-06"
    period_type: Mapped[str] = mapped_column(String(1), nullable=False, default="A")  # A=annual, M=monthly
    export_value_usd: Mapped[float | None] = mapped_column(Float, nullable=True)  # USD millions
    import_value_usd: Mapped[float | None] = mapped_column(Float, nullable=True)  # USD millions
    total_trade_usd: Mapped[float | None] = mapped_column(Float, nullable=True)  # USD millions
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="imf_imts")
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default="now()",
    )


class EconomicIndicator(Base):
    """World Bank 경제 지표"""
    __tablename__ = "economic_indicator"
    __table_args__ = (
        Index("ix_econ_indicator_country", "country_code"),
        Index("ix_econ_indicator_lookup", "country_code", "indicator_code", "year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(4), nullable=False)
    indicator_code: Mapped[str] = mapped_column(String(40), nullable=False)
    indicator_name: Mapped[str] = mapped_column(Text, nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="world_bank")
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default="now()",
    )


class ExchangeRate(Base):
    """Frankfurter ECB 환율 데이터"""
    __tablename__ = "exchange_rate"
    __table_args__ = (
        Index("ix_exchange_rate_date", "rate_date"),
        Index("ix_exchange_rate_lookup", "base_currency", "target_currency", "rate_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    target_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rate_date: Mapped[str] = mapped_column(String(10), nullable=False)  # "2024-03-14"
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default="now()",
    )

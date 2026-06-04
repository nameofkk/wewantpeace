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


class CommodityPrice(Base):
    """원자재 가격 (yfinance 수집)"""
    __tablename__ = "commodity_price"
    __table_args__ = (
        Index("ix_commodity_price_symbol_date", "symbol", "price_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)  # "WTI", "BRENT", "GOLD"
    name: Mapped[str] = mapped_column(String(50), nullable=False)    # "WTI Crude Oil"
    price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    change_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # 전일 대비 %
    price_date: Mapped[str] = mapped_column(String(10), nullable=False)  # "2026-03-14"
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default="now()",
    )


class MarketIndex(Base):
    """주요 주가 지수 (yfinance 수집)"""
    __tablename__ = "market_index"
    __table_args__ = (
        Index("ix_market_index_symbol_date", "symbol", "index_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)   # "KOSPI", "SPX"
    name: Mapped[str] = mapped_column(String(50), nullable=False)     # "KOSPI", "S&P 500"
    value: Mapped[float] = mapped_column(Float, nullable=False)       # 지수 값
    change_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    index_date: Mapped[str] = mapped_column(String(10), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)  # "KRW", "USD"
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default="now()",
    )


class TravelAdvisory(Base):
    """구조화된 여행 경보 (US State Dept / Korea MOFA / UK FCDO)"""
    __tablename__ = "travel_advisory"
    __table_args__ = (
        Index("ix_travel_advisory_country_source", "country_code", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 2-letter
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4
    title: Mapped[str] = mapped_column(String(200), nullable=False)  # "Exercise Normal Precautions"
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "us_state_dept", "kr_mofa", "uk_fcdo"
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default="now()",
    )
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default="now()",
    )

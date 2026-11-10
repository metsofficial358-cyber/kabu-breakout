from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Stock(Base):
    __tablename__ = "stocks"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    market: Mapped[str] = mapped_column(String(16), index=True)  # prime/standard/growth/etf/reit/other
    market_raw: Mapped[str | None] = mapped_column(String(64))   # JPX の「市場・商品区分」そのまま（外国株の判定用）
    sector33: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class DailyPrice(Base):
    __tablename__ = "daily_prices"
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[float | None] = mapped_column(Float)
    high: Mapped[float | None] = mapped_column(Float)
    low: Mapped[float | None] = mapped_column(Float)
    close: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (Index("ix_daily_prices_date", "date"),)


class ScreenResult(Base):
    __tablename__ = "screen_results"
    run_date: Mapped[date] = mapped_column(Date, primary_key=True)
    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    close: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    ytd_high: Mapped[float | None] = mapped_column(Float)
    ytd_high_date: Mapped[date | None] = mapped_column(Date)
    dist_pct: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    vol_ratio: Mapped[float | None] = mapped_column(Float)
    ma25: Mapped[float | None] = mapped_column(Float)
    ma75: Mapped[float | None] = mapped_column(Float)
    turnover_avg25: Mapped[float | None] = mapped_column(Float)
    range20_pct: Mapped[float | None] = mapped_column(Float)  # 直近20営業日の値幅（%）
    updated_today: Mapped[bool | None] = mapped_column(Boolean)
    score: Mapped[float | None] = mapped_column(Float)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_date: Mapped[date | None] = mapped_column(Date, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(16))  # running/success/stale/failed/skipped
    total: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)


class FetchError(Base):
    __tablename__ = "fetch_errors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(8))
    message: Mapped[str] = mapped_column(Text)

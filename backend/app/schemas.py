from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class ScreenItem(BaseModel):
    code: str
    name: str | None
    market: str | None
    sector33: str | None
    close: float | None
    change_pct: float | None
    ytd_high: float | None
    ytd_high_date: date | None
    dist_pct: float | None
    volume: int | None
    vol_ratio: float | None
    ma25: float | None
    ma75: float | None
    turnover_avg25: float | None
    updated_today: bool | None
    score: float | None
    range20_pct: float | None = None
    is_foreign: bool = False
    spark: list[float] | None = None


class ScreenResponse(BaseModel):
    run_date: date | None
    updated_at: datetime | None
    count: int
    items: list[ScreenItem]


class Bar(BaseModel):
    date: date
    open: float | None
    high: float | None
    low: float | None
    close: float | None
    volume: int | None


class ChartResponse(BaseModel):
    code: str
    name: str | None
    market: str | None
    run_date: date | None
    ytd_high: float | None
    ytd_high_date: date | None
    bars: list[Bar]


class RefreshStatus(BaseModel):
    running: bool
    run_id: int | None
    run_date: str | None
    phase: str | None
    processed: int
    total: int
    errors: int
    status: str | None
    message: str | None
    started_at: str | None
    finished_at: str | None


class RefreshStarted(BaseModel):
    run_id: int
    status: str


class Health(BaseModel):
    ok: bool
    db: bool
    last_run_date: date | None
    last_run_status: str | None
    scheduler_next_run: datetime | None

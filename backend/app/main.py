"""FastAPI 本体。"""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .calendar_jp import business_days_back
from .config import get_settings
from .db import SessionLocal, init_db
from .jobs import AlreadyRunning, Progress, runner
from .models import DailyPrice, Run, ScreenResult, Stock
from .schemas import ChartResponse, Health, RefreshStarted, RefreshStatus, ScreenResponse
from .screener import RESULT_COLUMNS, ScreenParams, apply_filters

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)
_scheduler = None


# ---------------------------------------------------------------- 結果のキャッシュ
class ResultCache:
    """run_date ごとの「絞り込み前の指標表」（stocks と結合済み）。新しい実行が終わったら破棄する。"""

    def __init__(self) -> None:
        self._data: dict[date, pd.DataFrame] = {}
        self._lock = threading.Lock()

    def get(self, db: Session, run_date: date) -> pd.DataFrame:
        with self._lock:
            if run_date in self._data:
                return self._data[run_date]
        q = (select(ScreenResult, Stock.name, Stock.market, Stock.sector33)
             .join(Stock, Stock.code == ScreenResult.code, isouter=True)
             .where(ScreenResult.run_date == run_date))
        rows = [{**{c: getattr(sr, c) for c in RESULT_COLUMNS}, "name": n, "market": m, "sector33": s}
                for sr, n, m, s in db.execute(q)]
        df = pd.DataFrame(rows, columns=[*RESULT_COLUMNS, "name", "market", "sector33"])
        for c in ("dist_pct", "score", "vol_ratio", "close", "ma25", "ma75", "turnover_avg25", "change_pct"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
        with self._lock:
            self._data[run_date] = df
        return df

    def clear(self, *_: object) -> None:
        with self._lock:
            self._data.clear()


cache = ResultCache()


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    global _scheduler
    init_db()
    runner.recover_interrupted()
    runner.on_finished.append(cache.clear)
    if get_settings().scheduler_enabled:
        from .scheduler import create_scheduler

        _scheduler = create_scheduler(runner)
        _scheduler.start()
        log.info("scheduler started: next=%s", _scheduler.get_job("daily").next_run_time)
    yield
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None


app = FastAPI(title="kabu-breakout", lifespan=lifespan)


def get_db():  # noqa: ANN201
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def latest_run(db: Session, run_date: date | None = None) -> Run | None:
    q = select(Run).where(Run.status == "success")
    if run_date:
        q = q.where(Run.run_date == run_date)
    return db.execute(q.order_by(Run.run_date.desc(), Run.finished_at.desc()).limit(1)).scalar()


def _clean(v: object) -> object:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if v is pd.NaT:
        return None
    return v


# ---------------------------------------------------------------- API
@app.get("/api/screen", response_model=ScreenResponse)
def screen(
    market: Literal["all", "prime", "standard", "growth"] = "all",
    max_dist: float = Query(5.0, gt=0, le=100),
    min_vol_ratio: float = Query(1.5, ge=0),
    vol_filter: bool = True,
    above_ma25: bool = True,
    above_ma75: bool = True,
    min_turnover: float = Query(100_000_000, ge=0),
    include_etf: bool = False,
    include_updated: bool = False,
    sort: Literal["dist", "vol_ratio", "change", "score"] = "dist",
    order: Literal["asc", "desc"] = "asc",
    limit: int = Query(200, ge=1, le=5000),
    run_date: date | None = None,
    with_spark: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    run = latest_run(db, run_date)
    if run is None:
        if run_date:
            raise HTTPException(404, f"{run_date} の結果はありません")
        return {"run_date": None, "updated_at": None, "count": 0, "items": []}
    df = cache.get(db, run.run_date)
    sp = ScreenParams(market=market, max_dist=max_dist, vol_filter=vol_filter, min_vol_ratio=min_vol_ratio,
                      above_ma25=above_ma25, above_ma75=above_ma75, min_turnover=min_turnover,
                      include_etf=include_etf, include_updated=include_updated, sort=sort, order=order,
                      limit=None)
    hit = apply_filters(df, sp)
    count = len(hit)
    hit = hit.head(limit)
    items = [{k: _clean(v) for k, v in rec.items()} for rec in hit.to_dict("records")]
    if with_spark and items:
        sparks = sparklines(db, [i["code"] for i in items], run.run_date, 60)
        for i in items:
            i["spark"] = sparks.get(i["code"], [])
    return {"run_date": run.run_date, "updated_at": run.finished_at, "count": count, "items": items}


def sparklines(db: Session, codes: list[str], until: date, days: int) -> dict[str, list[float]]:
    since = business_days_back(until, days - 1)
    q = (select(DailyPrice.code, DailyPrice.close).where(DailyPrice.code.in_(codes), DailyPrice.date >= since,
                                                         DailyPrice.date <= until)
         .order_by(DailyPrice.code, DailyPrice.date))
    out: dict[str, list[float]] = {}
    for code, close in db.execute(q):
        if close is not None:
            out.setdefault(code, []).append(close)
    return out


@app.get("/api/stocks/{code}/chart", response_model=ChartResponse)
def chart(code: str, days: int = Query(120, ge=5, le=1000), run_date: date | None = None,
          db: Session = Depends(get_db)) -> dict:
    code = code.upper()
    stock = db.get(Stock, code)
    if stock is None:
        raise HTTPException(404, f"銘柄 {code} が見つかりません")
    run = latest_run(db, run_date)
    until = run.run_date if run else (run_date or date.max)
    bars = db.execute(select(DailyPrice).where(DailyPrice.code == code, DailyPrice.date <= until)
                      .order_by(DailyPrice.date.desc()).limit(days)).scalars().all()
    sr = db.get(ScreenResult, (run.run_date, code)) if run else None
    return {
        "code": code, "name": stock.name, "market": stock.market,
        "run_date": run.run_date if run else None,
        "ytd_high": sr.ytd_high if sr else None, "ytd_high_date": sr.ytd_high_date if sr else None,
        "bars": [{"date": b.date, "open": b.open, "high": b.high, "low": b.low, "close": b.close,
                  "volume": b.volume} for b in reversed(bars)],
    }


@app.post("/api/refresh", status_code=202, response_model=RefreshStarted)
def refresh() -> dict | JSONResponse:
    try:
        run_id = runner.start(background=True, trigger="manual")
    except AlreadyRunning as e:
        return JSONResponse(status_code=409, content={"detail": "更新中です", "run_id": e.run_id})
    return {"run_id": run_id, "status": "running"}


@app.get("/api/refresh/status", response_model=RefreshStatus)
def refresh_status(db: Session = Depends(get_db)) -> dict:
    st = runner.status()
    if st["run_id"] is None:  # 再起動後などメモリに状態がなければ最後の実行を返す
        last = db.execute(select(Run).order_by(Run.id.desc()).limit(1)).scalar()
        if last:
            st = Progress(running=last.status == "running", run_id=last.id,
                          run_date=last.run_date.isoformat() if last.run_date else None,
                          processed=last.processed, total=last.total, errors=last.errors, status=last.status,
                          started_at=last.started_at.isoformat(timespec="seconds"),
                          finished_at=last.finished_at.isoformat(timespec="seconds") if last.finished_at else None
                          ).__dict__
    return st


@app.get("/api/health", response_model=Health)
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        ok_db = True
    except Exception:  # noqa: BLE001
        ok_db = False
    last = db.execute(select(Run).order_by(Run.id.desc()).limit(1)).scalar() if ok_db else None
    nxt = _scheduler.get_job("daily").next_run_time if _scheduler else None
    return {"ok": ok_db, "db": ok_db, "last_run_date": last.run_date if last else None,
            "last_run_status": last.status if last else None,
            "scheduler_next_run": nxt.replace(tzinfo=None) if nxt else None}

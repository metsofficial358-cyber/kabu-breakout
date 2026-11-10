"""日次ジョブ本体（手動・定時・CLI 共通）。二重起動はロックで防ぎ、進捗をメモリと runs に書く。"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import date, datetime, time as dtime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from .calendar_jp import expected_trading_date
from .config import get_settings
from .db import SessionLocal
from .models import DailyPrice, FetchError, Run, ScreenResult, Stock
from .prices import initial_start, update_prices
from .providers.base import PriceProvider
from .screener import RESULT_COLUMNS, CalcParams, compute_all
from .universe import refresh_universe

log = logging.getLogger(__name__)
RUN_STALE_AFTER = timedelta(hours=3)  # これより古い running は中断されたものとみなす


class AlreadyRunning(Exception):
    def __init__(self, run_id: int | None) -> None:
        super().__init__(f"run {run_id} is already running")
        self.run_id = run_id


@dataclass
class Progress:
    running: bool = False
    run_id: int | None = None
    run_date: str | None = None
    phase: str | None = None        # universe / prices / screen
    processed: int = 0
    total: int = 0
    errors: int = 0
    status: str | None = None       # running / success / stale / failed / skipped
    message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


def now_jst() -> datetime:
    return datetime.now(ZoneInfo(get_settings().timezone)).replace(tzinfo=None)


def current_t(now: datetime | None = None) -> date:
    s = get_settings()
    return expected_trading_date(now or now_jst(), dtime(s.batch_hour, s.batch_minute))


def load_prices(db: Session, t: date) -> pd.DataFrame:
    since = min(initial_start(t), date(t.year - 1, 1, 1))
    q = select(DailyPrice.code, DailyPrice.date, DailyPrice.open, DailyPrice.high, DailyPrice.low,
               DailyPrice.close, DailyPrice.volume).where(DailyPrice.date >= since, DailyPrice.date <= t)
    df = pd.DataFrame(db.execute(q).all(), columns=["code", "date", "open", "high", "low", "close", "volume"])
    return df


def rescreen(db: Session, t: date) -> int:
    """保存済みの株価から指標を計算し直して保存する（株価は取得しない）。"""
    res = compute_all(load_prices(db, t), t, CalcParams.from_settings())
    return save_results(db, t, res)


def save_results(db: Session, t: date, res: pd.DataFrame) -> int:
    db.execute(delete(ScreenResult).where(ScreenResult.run_date == t))
    rows = []
    for rec in res[RESULT_COLUMNS].to_dict("records"):
        clean = {k: (None if (v is not None and not isinstance(v, (str, date)) and pd.isna(v)) else v)
                 for k, v in rec.items()}
        clean["volume"] = int(clean["volume"]) if clean["volume"] is not None else None
        clean["updated_today"] = bool(clean["updated_today"]) if clean["updated_today"] is not None else None
        rows.append(clean | {"run_date": t})
    for i in range(0, len(rows), 500):
        db.execute(ScreenResult.__table__.insert(), rows[i : i + 500])
    db.commit()
    return len(rows)


class JobRunner:
    def __init__(self, session_factory: sessionmaker = SessionLocal,
                 provider_factory: Callable[[], PriceProvider] | None = None) -> None:
        self.session_factory = session_factory
        self.provider_factory = provider_factory
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()
        self.progress = Progress()
        self.on_finished: list[Callable[[Progress], None]] = []

    # ---- 状態
    def status(self) -> dict:
        with self._state_lock:
            return asdict(self.progress)

    def _set(self, **kw) -> None:  # noqa: ANN003
        with self._state_lock:
            for k, v in kw.items():
                setattr(self.progress, k, v)

    def _provider(self) -> PriceProvider:
        if self.provider_factory:
            return self.provider_factory()
        from .providers.yfinance_provider import YFinanceProvider
        return YFinanceProvider()

    def recover_interrupted(self) -> None:
        """プロセスが落ちて running のまま一定時間以上残った実行を failed にする。"""
        with self.session_factory() as db:
            db.execute(update(Run).where(Run.status == "running", Run.started_at < now_jst() - RUN_STALE_AFTER)
                       .values(status="failed", finished_at=now_jst()))
            db.commit()

    # ---- 起動
    def start(self, t: date | None = None, background: bool = True, trigger: str = "manual") -> int:
        """ロックを取って runs に行を作り、ジョブを開始する。実行中なら AlreadyRunning。"""
        if not self._lock.acquire(blocking=False):
            raise AlreadyRunning(self.progress.run_id)
        try:
            t = t or current_t()
            started = now_jst()
            with self.session_factory() as db:
                # 別プロセス（CLI と API サーバーなど）での同時実行も防ぐ
                other = db.execute(select(Run.id).where(Run.status == "running",
                                                        Run.started_at >= started - RUN_STALE_AFTER)).scalar()
                if other is not None:
                    raise AlreadyRunning(other)
                run = Run(run_date=t, started_at=started, status="running", total=0, processed=0, errors=0)
                db.add(run)
                db.commit()
                run_id = run.id
            self.progress = Progress(running=True, run_id=run_id, run_date=t.isoformat(), phase="universe",
                                     status="running", started_at=started.isoformat(timespec="seconds"))
        except Exception:
            self._lock.release()
            raise
        log.info("run %d start (T=%s, trigger=%s)", run_id, t, trigger)
        if background:
            threading.Thread(target=self._execute, args=(run_id, t), daemon=True, name=f"run-{run_id}").start()
        else:
            self._execute(run_id, t)
        return run_id

    # ---- 本体
    def _execute(self, run_id: int, t: date) -> None:
        s = get_settings()
        status, message = "failed", None
        try:
            with self.session_factory() as db:
                # 1) 銘柄一覧（空、または最終更新から一定日数たっていれば取り込み直す）
                last_upd = db.execute(select(func.max(Stock.updated_at))).scalar()
                # 旧版の DB（market_raw 列がまだ空）も取り込み直す
                missing_raw = db.execute(select(func.count()).where(Stock.is_active.is_(True),
                                                                    Stock.market_raw.is_(None))).scalar()
                if (last_upd is None or missing_raw
                        or now_jst() - last_upd > timedelta(days=s.universe_refresh_days)):
                    try:
                        log.info("universe: %s", refresh_universe(db))
                    except Exception as e:  # noqa: BLE001  既存の一覧があれば続行
                        if last_upd is None:
                            raise
                        log.warning("universe refresh failed, using existing list: %s", e)
                codes = list(db.execute(select(Stock.code).where(Stock.is_active.is_(True))
                                        .order_by(Stock.code)).scalars())
                self._set(phase="prices", total=len(codes), processed=0)
                self._update_run(run_id, total=len(codes))

                # 2) 株価
                def on_progress(done: int, total: int) -> None:
                    self._set(processed=done)
                    self._update_run(run_id, processed=done)

                st = update_prices(db, self._provider(), codes, t, progress=on_progress)
                if st.errors:
                    db.execute(FetchError.__table__.insert(),
                               [{"run_id": run_id, "code": c, "message": m[:1000]} for c, m in st.errors.items()])
                    db.commit()
                self._set(errors=len(st.errors), processed=len(codes))
                self._update_run(run_id, processed=len(codes), errors=len(st.errors))

                # 3) データ未更新の判定（T の足を持つ銘柄の割合）
                have_t = db.execute(select(func.count(func.distinct(DailyPrice.code)))
                                    .where(DailyPrice.date == t, DailyPrice.code.in_(codes))).scalar() or 0
                ratio = have_t / len(codes) if codes else 0.0
                if ratio < s.stale_ratio_threshold:
                    status = "stale"
                    message = f"{t} の株価が揃っていません（{have_t}/{len(codes)} 銘柄）"
                    return

                # 4) スクリーニング（絞り込み前の全銘柄の指標を保存）
                self._set(phase="screen")
                res = compute_all(load_prices(db, t), t, CalcParams.from_settings())
                n = save_results(db, t, res)
                status = "success"
                message = f"{n} 銘柄の指標を保存（取得失敗 {len(st.errors)} 件）"
        except Exception as e:  # noqa: BLE001
            log.exception("run %d failed", run_id)
            status, message = "failed", f"{type(e).__name__}: {e}"
        finally:
            fin = now_jst()
            self._update_run(run_id, status=status, finished_at=fin)
            self._set(running=False, status=status, message=message, phase=None,
                      finished_at=fin.isoformat(timespec="seconds"))
            log.info("run %d %s: %s", run_id, status, message)
            self._lock.release()
            for cb in self.on_finished:
                try:
                    cb(self.progress)
                except Exception:  # noqa: BLE001
                    log.exception("on_finished callback failed")

    def _update_run(self, run_id: int, **values) -> None:  # noqa: ANN003
        with self.session_factory() as db:
            db.execute(update(Run).where(Run.id == run_id).values(**values))
            db.commit()


runner = JobRunner()

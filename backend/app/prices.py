"""株価の保存と差分取得（初回は全期間、2回目以降は直近N営業日を取り直して上書き）。"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .calendar_jp import business_days_back
from .config import get_settings
from .models import DailyPrice
from .providers.base import FetchResult, PriceProvider, ProgressCallback

log = logging.getLogger(__name__)


def initial_start(t: date) -> date:
    """初回取得の開始日：1〜3月の前年集計と MA75 を満たす最小の範囲（最長約1年3ヶ月）。"""
    s = get_settings()
    if s.ytd_prev_year_until_month and t.month <= s.ytd_prev_year_until_month:
        return date(t.year - 1, 1, 1)
    return min(date(t.year, 1, 1), t - timedelta(days=s.initial_min_calendar_days))


def upsert_prices(db: Session, code: str, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    rows = [
        {"code": code, "date": d, "open": _f(r.open), "high": _f(r.high), "low": _f(r.low),
         "close": _f(r.close), "volume": int(r.volume)}
        for d, r in zip(df.index, df.itertuples())
    ]
    for i in range(0, len(rows), 500):
        stmt = insert(DailyPrice).values(rows[i : i + 500])
        stmt = stmt.on_conflict_do_update(
            index_elements=["code", "date"],
            set_={k: stmt.excluded[k] for k in ("open", "high", "low", "close", "volume")},
        )
        db.execute(stmt)
    return len(rows)


def _f(v: object) -> float | None:
    return None if pd.isna(v) else float(v)


def load_closes(db: Session, code: str, start: date) -> dict[date, float]:
    q = select(DailyPrice.date, DailyPrice.close).where(DailyPrice.code == code, DailyPrice.date >= start)
    return {d: c for d, c in db.execute(q) if c is not None}


def detect_split(stored: dict[date, float], new: pd.DataFrame, threshold: float) -> bool:
    """取り直した期間で保存済み終値とずれていれば、過去分が分割で調整し直されたとみなす。"""
    for d, c in new["close"].items():
        old = stored.get(d)
        if old and not pd.isna(c) and abs(c - old) / old >= threshold:
            return True
    return False


@dataclass
class UpdateStats:
    full: int = 0
    incremental: int = 0
    split_refetched: list[str] = field(default_factory=list)
    rows: int = 0
    errors: dict[str, str] = field(default_factory=dict)


def update_prices(
    db: Session,
    provider: PriceProvider,
    codes: list[str],
    t: date,
    progress: ProgressCallback | None = None,
) -> UpdateStats:
    s = get_settings()
    stats = UpdateStats()
    last = dict(
        db.execute(
            select(DailyPrice.code, func.max(DailyPrice.date))
            .where(DailyPrice.code.in_(codes)).group_by(DailyPrice.code)
        ).all()
    )
    inc_start = business_days_back(t, s.refetch_business_days)

    # 取得開始日ごとにまとめる（初回は全期間、既存は直近N営業日。長く止まっていた銘柄は最終日から）
    groups: dict[date, list[str]] = defaultdict(list)
    for c in codes:
        if c not in last:
            groups[initial_start(t)].append(c)
        else:
            groups[min(inc_start, last[c])].append(c)

    total = len(codes)
    base = 0
    for start, group in sorted(groups.items()):
        is_full = group[0] not in last
        cb = (lambda d, _t, b=base: progress(b + d, total)) if progress else None
        res: FetchResult = provider.fetch_daily(group, start, t, cb)
        stats.errors.update(res.errors)
        for code, df in res.data.items():
            if code in last and detect_split(load_closes(db, code, start), df, s.split_detect_threshold):
                stats.split_refetched.append(code)
                continue
            stats.rows += upsert_prices(db, code, df)
        db.commit()
        if is_full:
            stats.full += len(res.data)
        else:
            stats.incremental += len(res.data)
        base += len(group)

    # 分割が疑われる銘柄は全期間を取り直して置き換える
    if stats.split_refetched:
        log.info("split detected: %s", stats.split_refetched)
        res = provider.fetch_daily(stats.split_refetched, initial_start(t), t)
        stats.errors.update(res.errors)
        for code, df in res.data.items():
            db.query(DailyPrice).filter(DailyPrice.code == code).delete()
            stats.rows += upsert_prices(db, code, df)
        db.commit()
    return stats

from datetime import date

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import init_db, make_engine
from app.models import DailyPrice
from app.prices import detect_split, initial_start, update_prices
from app.providers.base import FetchResult, PriceProvider


def test_initial_start():
    assert initial_start(date(2026, 3, 31)) == date(2025, 1, 1)
    assert initial_start(date(2026, 11, 10)) == date(2026, 1, 1)
    assert initial_start(date(2026, 4, 10)) == date(2025, 11, 11)  # MA75 用に150暦日


class FakeProvider(PriceProvider):
    def __init__(self, scale=1.0):
        self.scale = scale
        self.calls = []

    def fetch_daily(self, codes, start, end, progress=None):
        self.calls.append((tuple(codes), start))
        idx = [d.date() for d in pd.bdate_range(start, end)]
        res = FetchResult()
        for c in codes:
            if c == "9999":
                res.errors[c] = "no data returned"
                continue
            res.data[c] = pd.DataFrame(
                {"open": 100.0 * self.scale, "high": 110.0 * self.scale, "low": 90.0 * self.scale,
                 "close": 100.0 * self.scale, "volume": 1000}, index=idx)
        return res


def _db():
    eng = make_engine("sqlite:///:memory:")
    init_db(eng)
    return sessionmaker(bind=eng)()


def test_update_full_then_incremental_and_split():
    db = _db()
    t = date(2026, 11, 10)
    p = FakeProvider()
    st = update_prices(db, p, ["7203", "9999"], t)
    assert st.full == 1 and "9999" in st.errors
    assert p.calls[0][1] == date(2026, 1, 1)

    p2 = FakeProvider()
    st2 = update_prices(db, p2, ["7203"], t)
    assert st2.incremental == 1 and not st2.split_refetched
    assert p2.calls[0][1] == date(2026, 10, 26)  # 10営業日前（11/3 祝日を除く）

    p3 = FakeProvider(scale=0.5)  # 1:2 分割で過去の値が半分に
    st3 = update_prices(db, p3, ["7203"], t)
    assert st3.split_refetched == ["7203"]
    first = db.execute(select(DailyPrice.close).where(DailyPrice.date == date(2026, 1, 5))).scalar()
    assert first == 50.0  # 全期間が置き換わる


def test_detect_split_tolerates_small_changes():
    stored = {date(2026, 11, 9): 100.0}
    new = pd.DataFrame({"close": [100.5]}, index=[date(2026, 11, 9)])
    assert not detect_split(stored, new, 0.01)


def test_normalize_frame_rounds_float32_noise():
    from app.providers.yfinance_provider import normalize_frame
    raw = pd.DataFrame({"Open": [181.3000030517578], "High": [181.3000030517578], "Low": [160.1999969482422],
                        "Close": [165.1999969482422], "Adj Close": [150.0], "Volume": [1.0]},
                       index=pd.DatetimeIndex(["2026-11-09"]))
    df = normalize_frame(raw)
    assert df.loc[date(2026, 11, 9), "high"] == 181.3 and df.loc[date(2026, 11, 9), "close"] == 165.2
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]  # Adj Close は使わない

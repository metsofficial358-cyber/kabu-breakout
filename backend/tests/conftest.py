"""合成日足データの生成ヘルパー。"""
from __future__ import annotations

import os
import tempfile
from datetime import date

# app を import する前にテスト用 DB とスケジューラ無効を設定
_TMP = tempfile.mkdtemp(prefix="kabu-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["SCHEDULER_ENABLED"] = "false"

import pandas as pd
import pytest

from app.calendar_jp import business_days_back, is_business_day

T = date(2026, 11, 9)  # 判定日（月曜）


def bdays(end: date, n: int) -> list[date]:
    """end を含めて n 営業日分（昇順）。"""
    start = business_days_back(end, n - 1)
    return [d.date() for d in pd.date_range(start, end) if is_business_day(d.date())]


def make_df(closes: list[float], end: date = T, volumes: list[int] | int = 2_000_000,
            highs: list[float] | None = None, spread: float = 0.5) -> pd.DataFrame:
    """終値の列から日足を作る。high は既定で close + spread。"""
    n = len(closes)
    idx = bdays(end, n)
    if isinstance(volumes, int):
        volumes = [volumes] * n
    highs = highs or [c + spread for c in closes]
    return pd.DataFrame(
        {"open": closes, "high": highs, "low": [c - spread for c in closes],
         "close": closes, "volume": volumes},
        index=idx,
    )


def uptrend_near_high(n: int = 120, dist: float = 3.0, vol_mult: float = 2.0) -> pd.DataFrame:
    """上昇トレンド（60→90）の途中で高値 100 を付け、押した後 dist% 下で引ける銘柄。
    MA25 < 終値（dist<=5.5 の範囲）、MA25 > MA75。T の出来高は直前平均の vol_mult 倍。"""
    k = n - 10                                       # 高値を付けた日の位置（T の10営業日前）
    closes = [60 + 30 * i / (k - 1) for i in range(k)]
    closes[k - 1] = 98.0                             # 高値の日（日中高値 100）
    closes += [90.0] * 9                             # 押し
    target = 100 * (1 - dist / 100)
    closes.append(target)
    highs = [c + 0.5 for c in closes]
    highs[k - 1] = 100.0
    highs[-1] = target + 0.3
    vols = [2_000_000] * (n - 1) + [int(2_000_000 * vol_mult)]
    return make_df(closes, volumes=vols, highs=highs)


@pytest.fixture
def near_high_df():
    return uptrend_near_high()

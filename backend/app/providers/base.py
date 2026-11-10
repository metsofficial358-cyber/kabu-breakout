"""株価データ取得の抽象化（将来 J-Quants などに差し替えるため）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

# 返す DataFrame の列（index は datetime.date、昇順）
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]

ProgressCallback = Callable[[int, int], None]  # (処理済み件数, 全件数)


@dataclass
class FetchResult:
    data: dict[str, pd.DataFrame] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)


class PriceProvider(ABC):
    """日足 OHLCV（分割調整済み・配当調整なし）を返す。"""

    @abstractmethod
    def fetch_daily(
        self,
        codes: list[str],
        start: date,
        end: date,
        progress: ProgressCallback | None = None,
    ) -> FetchResult:
        """start〜end（両端含む）の日足を銘柄ごとに返す。失敗した銘柄は errors に入れて続行する。"""

"""yfinance による PriceProvider 実装。ティッカーは {code}.T。"""
from __future__ import annotations

import logging
import random
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from ..config import get_settings
from .base import OHLCV_COLUMNS, FetchResult, PriceProvider, ProgressCallback

log = logging.getLogger(__name__)
_CACHE_DIR = Path(get_settings().database_url.removeprefix("sqlite:///")).parent / "yf-cache"
try:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(_CACHE_DIR))
except OSError:  # 読み取り専用などではキャッシュなしで動かす
    pass


def to_ticker(code: str) -> str:
    return f"{code}.T"


def normalize_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """yfinance の1銘柄分の DataFrame を OHLCV_COLUMNS・date インデックスに整える。"""
    if raw is None or raw.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = raw.rename(columns=str.lower)
    # auto_adjust=False の Open/High/Low/Close/Volume は分割調整済み・配当調整なし。adj close は使わない
    missing = [c for c in OHLCV_COLUMNS if c not in df.columns]
    if missing:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    df = df[OHLCV_COLUMNS].copy()
    idx = pd.to_datetime(df.index)
    if idx.tz is not None:
        idx = idx.tz_convert("Asia/Tokyo").tz_localize(None)
    df.index = idx.date
    df = df[~df.index.duplicated(keep="last")]
    df = df.dropna(subset=["open", "high", "low", "close"], how="all")
    df["volume"] = df["volume"].fillna(0).astype("int64")
    # yfinance は float32 由来の誤差を含む（例 181.3000030517578）。東証の呼値は最小 0.1 円なので丸める
    df[["open", "high", "low", "close"]] = df[["open", "high", "low", "close"]].round(2)
    return df.sort_index()


class YFinanceProvider(PriceProvider):
    def __init__(self, chunk_size: int | None = None) -> None:
        s = get_settings()
        self.chunk_size = chunk_size or s.fetch_chunk_size
        self.sleep_range = (s.fetch_sleep_min, s.fetch_sleep_max)
        self.retries = s.fetch_retries
        self.backoff = s.fetch_backoff_base

    def _download(self, codes: list[str], start: date, end: date) -> dict[str, pd.DataFrame]:
        tickers = [to_ticker(c) for c in codes]
        raw = yf.download(
            tickers,
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),  # yfinance の end は排他的
            interval="1d",
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )
        out: dict[str, pd.DataFrame] = {}
        if raw is None or raw.empty:
            return out
        for code, tk in zip(codes, tickers):
            if isinstance(raw.columns, pd.MultiIndex):
                if tk not in raw.columns.get_level_values(0):
                    continue
                sub = raw[tk]
            else:
                sub = raw
            df = normalize_frame(sub)
            if not df.empty:
                out[code] = df
        return out

    def fetch_daily(
        self,
        codes: list[str],
        start: date,
        end: date,
        progress: ProgressCallback | None = None,
    ) -> FetchResult:
        result = FetchResult()
        total = len(codes)
        done = 0
        chunks = [codes[i : i + self.chunk_size] for i in range(0, total, self.chunk_size)]
        for ci, chunk in enumerate(chunks):
            pending = list(chunk)
            last_err: dict[str, str] = {}
            for attempt in range(self.retries + 1):  # 初回 + 再試行 retries 回
                if attempt:
                    wait = self.backoff ** attempt
                    log.info("retry %d for %d codes after %.0fs", attempt, len(pending), wait)
                    time.sleep(wait)
                try:
                    got = self._download(pending, start, end)
                except Exception as e:  # noqa: BLE001  チャンク全体の失敗
                    last_err = {c: f"{type(e).__name__}: {e}" for c in pending}
                    continue
                result.data.update(got)
                pending = [c for c in pending if c not in got]
                last_err = {c: "no data returned" for c in pending}
                if not pending:
                    break
            result.errors.update(last_err)
            done += len(chunk)
            if progress:
                progress(done, total)
            if ci < len(chunks) - 1:
                time.sleep(random.uniform(*self.sleep_range))
        return result

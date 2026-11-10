"""2章（指標の定義）と3章（スクリーニング条件）のロジック。DB に依存しない純粋関数。

入力の日足 DataFrame は index=datetime.date（昇順）、列 open/high/low/close/volume。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import pandas as pd

from . import config
from .calendar_jp import ytd_start

STOCK_MARKETS = ("prime", "standard", "growth")
NON_STOCK_MARKETS = ("etf", "reit", "other")

RESULT_COLUMNS = [
    "code", "close", "change_pct", "ytd_high", "ytd_high_date", "dist_pct", "volume",
    "vol_ratio", "ma25", "ma75", "turnover_avg25", "updated_today", "score", "range20_pct",
]


@dataclass(frozen=True)
class CalcParams:
    ytd_prev_year_until_month: int = 3
    vol_avg_days: int = 25
    ma_short: int = 25
    ma_long: int = 75
    turnover_avg_days: int = 25
    min_history_days: int = 75
    pinned_days: int = 20

    @classmethod
    def from_settings(cls) -> CalcParams:
        s = config.get_settings()
        return cls(s.ytd_prev_year_until_month, s.vol_avg_days, s.ma_short, s.ma_long,
                   s.turnover_avg_days, s.min_history_days, s.pinned_days)


def breakout_score(dist_pct: float, vol_ratio: float | None, ma25: float | None, ma75: float | None) -> float:
    """並び替え用の参考スコア。重みは config の定数。"""
    vol = min(vol_ratio, config.SCORE_VOL_CAP) if vol_ratio is not None else 0.0
    bonus = config.SCORE_MA_BONUS if (ma25 is not None and ma75 is not None and ma25 > ma75) else 0.0
    return (config.SCORE_DIST_BASE - dist_pct) * config.SCORE_DIST_WEIGHT + vol * config.SCORE_VOL_WEIGHT + bonus


def _num(v: object) -> float | None:
    if v is None:
        return None
    f = float(v)
    return None if math.isnan(f) or math.isinf(f) else f


def _empty(code: str) -> dict:
    return {c: None for c in RESULT_COLUMNS} | {"code": code}


def compute_indicators(code: str, df: pd.DataFrame, t: date, p: CalcParams | None = None) -> dict:
    """1銘柄の T 時点の指標。データ不足のときは close/change_pct/volume 以外を None にする。"""
    p = p or CalcParams()
    out = _empty(code)
    if df is None or df.empty:
        return out
    df = df[df.index <= t]
    # 欠損行（値が NaN）は捨て、存在する営業日だけで計算する
    df = df.dropna(subset=["high", "close"])
    if df.empty or df.index[-1] != t:
        return out  # T の足がない（売買停止・取得漏れ）

    row = df.iloc[-1]
    close_t, high_t = float(row["close"]), float(row["high"])
    vol_t = int(row["volume"]) if not pd.isna(row["volume"]) else 0
    out["close"], out["volume"] = close_t, vol_t
    if len(df) >= 2:
        prev = float(df["close"].iloc[-2])
        out["change_pct"] = _num((close_t - prev) / prev * 100) if prev else None

    if len(df) < p.min_history_days or vol_t <= 0:
        return out  # データ不足として除外対象

    # 年初来高値：集計開始日〜T-1 の日中高値の最大値
    past = df.iloc[:-1]
    window = past[past.index >= ytd_start(t, p.ytd_prev_year_until_month)]
    if window.empty:
        return out
    ytd_high = float(window["high"].max())
    out["ytd_high"] = ytd_high
    out["ytd_high_date"] = window["high"].idxmax()  # 同値が複数なら最初に付けた日
    dist = (ytd_high - close_t) / ytd_high * 100
    out["dist_pct"] = dist
    out["updated_today"] = bool(high_t > ytd_high)

    # 出来高倍率：T を含まない直前 N 営業日の平均
    vol_prev = past["volume"].fillna(0).iloc[-p.vol_avg_days:]
    avg = float(vol_prev.mean()) if len(vol_prev) else 0.0
    out["vol_ratio"] = vol_t / avg if avg > 0 else None

    closes = df["close"]
    out["ma25"] = _num(closes.iloc[-p.ma_short:].mean())
    out["ma75"] = _num(closes.iloc[-p.ma_long:].mean())
    tail = df.iloc[-p.turnover_avg_days:]
    out["turnover_avg25"] = _num((tail["close"] * tail["volume"].fillna(0)).mean())
    # 直近 N 営業日の値幅（TOB の買付価格への張り付きなど、値動きが止まった銘柄の判定用）
    win = df.iloc[-p.pinned_days:]
    low = win["low"].min() if "low" in win and win["low"].notna().any() else win["close"].min()
    out["range20_pct"] = _num((win["high"].max() - low) / close_t * 100) if close_t else None
    out["score"] = breakout_score(dist, out["vol_ratio"], out["ma25"], out["ma75"])
    return out


def compute_all(prices: pd.DataFrame, t: date, p: CalcParams | None = None) -> pd.DataFrame:
    """縦持ち（code,date,open,high,low,close,volume）の全銘柄から、絞り込み前の指標表を作る。"""
    p = p or CalcParams()
    rows = []
    if not prices.empty:
        for code, g in prices.groupby("code", sort=True):
            rows.append(compute_indicators(str(code), g.set_index("date").sort_index(), t, p))
    return pd.DataFrame(rows, columns=RESULT_COLUMNS)


# ---------------------------------------------------------------- 3章：絞り込み

SORT_KEYS = {"dist": "dist_pct", "vol_ratio": "vol_ratio", "change": "change_pct", "score": "score"}


@dataclass(frozen=True)
class ScreenParams:
    market: str = "all"            # all / prime / standard / growth
    max_dist: float = 5.0
    vol_filter: bool = True
    min_vol_ratio: float = 1.5
    above_ma25: bool = True
    above_ma75: bool = True
    min_turnover: float = 100_000_000
    include_etf: bool = False        # ETF・ETN
    include_reit: bool = False       # REIT・インフラファンド等
    include_other: bool = False      # PRO Market・出資証券など（東証の3市場以外）
    include_foreign: bool = False    # 外国株（JDR を含む）
    exclude_pinned: bool = True      # 値動きが止まった銘柄（TOB 等）を除外
    pinned_range_pct: float = 1.0
    include_updated: bool = False
    sort: str = "dist"
    order: str = "asc"
    limit: int | None = 200


def allowed_markets(market: str, include_etf: bool = False, include_reit: bool = False,
                    include_other: bool = False) -> tuple[str, ...]:
    if market == "all":
        extra = tuple(m for m, on in (("etf", include_etf), ("reit", include_reit), ("other", include_other)) if on)
        return STOCK_MARKETS + extra
    return (market,)


def apply_filters(df: pd.DataFrame, sp: ScreenParams) -> pd.DataFrame:
    """指標表（market 列つき）を条件で絞り込み、並び替える。"""
    if df.empty:
        return df
    m = df["dist_pct"].notna() & df["score"].notna()  # データ不足は常に除外
    if "market" in df.columns:
        m &= df["market"].isin(allowed_markets(sp.market, sp.include_etf, sp.include_reit, sp.include_other))
    if not sp.include_foreign and "is_foreign" in df.columns:
        m &= ~df["is_foreign"].fillna(False).astype(bool)
    if sp.exclude_pinned and "range20_pct" in df.columns:
        m &= ~(df["range20_pct"] < sp.pinned_range_pct)  # 値幅が不明（NULL）の銘柄は除外しない
    near = (df["dist_pct"] > 0) & (df["dist_pct"] <= sp.max_dist) & ~df["updated_today"].fillna(False).astype(bool)
    if sp.include_updated:
        near |= df["updated_today"].fillna(False).astype(bool)
    m &= near
    if sp.vol_filter:
        m &= df["vol_ratio"].fillna(0) >= sp.min_vol_ratio
    if sp.above_ma25:
        m &= df["close"] > df["ma25"]
    if sp.above_ma75:
        m &= df["close"] > df["ma75"]
    if sp.min_turnover:
        m &= df["turnover_avg25"].fillna(0) >= sp.min_turnover
    out = df[m]
    key = SORT_KEYS.get(sp.sort, "dist_pct")
    out = out.sort_values([key, "code"], ascending=[sp.order != "desc", True], na_position="last")
    return out.head(sp.limit) if sp.limit else out

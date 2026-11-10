from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.screener import (
    CalcParams,
    ScreenParams,
    apply_filters,
    breakout_score,
    compute_all,
    compute_indicators,
)
from tests.conftest import T, bdays, make_df, uptrend_near_high


def screen(dfs: dict[str, pd.DataFrame], t: date = T, sp: ScreenParams | None = None,
           market: str = "prime", p: CalcParams | None = None) -> pd.DataFrame:
    long = pd.concat([df.rename_axis("date").reset_index().assign(code=c) for c, df in dfs.items()])
    res = compute_all(long, t, p)
    res["market"] = market
    return apply_filters(res, sp or ScreenParams())


# ① 高値の 3% 下 → 抽出される
def test_01_three_percent_below_high_is_picked(near_high_df):
    r = compute_indicators("1111", near_high_df, T)
    assert r["ytd_high"] == pytest.approx(100.0)
    assert r["dist_pct"] == pytest.approx(3.0)
    assert r["ytd_high_date"] == near_high_df.index[-11]  # T の10営業日前
    assert r["updated_today"] is False
    assert r["close"] > r["ma25"] > r["ma75"]
    assert list(screen({"1111": near_high_df})["code"]) == ["1111"]


def test_01b_dist_bounds():
    out = screen({"A": uptrend_near_high(dist=5.0), "B": uptrend_near_high(dist=5.5)})
    assert list(out["code"]) == ["A"]  # dist <= 5.0 は含み、5.5 は外れる
    out = screen({"B": uptrend_near_high(dist=5.5)}, sp=ScreenParams(max_dist=6.0))
    assert list(out["code"]) == ["B"]


# ② 本日更新済み → 除外される（表示切り替えで含められる）
def test_02_updated_today_is_excluded(near_high_df):
    df = near_high_df.copy()
    df.iloc[-1, df.columns.get_loc("high")] = 100.5   # 場中に 100 を上抜け、終値は 97
    r = compute_indicators("2222", df, T)
    assert r["updated_today"] is True
    assert screen({"2222": df}).empty
    assert list(screen({"2222": df}, sp=ScreenParams(include_updated=True))["code"]) == ["2222"]


def test_02b_equal_to_high_is_not_updated(near_high_df):
    df = near_high_df.copy()
    df.iloc[-1, df.columns.get_loc("high")] = 100.0   # 並んだだけ（> ではない）
    assert compute_indicators("X", df, T)["updated_today"] is False


# ③ 出来高 1.4 倍 → 除外される
def test_03_volume_1_4x_is_excluded():
    df = uptrend_near_high(vol_mult=1.4)
    assert compute_indicators("3333", df, T)["vol_ratio"] == pytest.approx(1.4)
    assert screen({"3333": df}).empty
    assert len(screen({"3333": df}, sp=ScreenParams(vol_filter=False))) == 1
    assert len(screen({"3333": df}, sp=ScreenParams(min_vol_ratio=1.4))) == 1


# ④ MA75 の下 → 除外される
def test_04_below_ma75_is_excluded():
    closes = [103.0] * 51 + [98.0] * 24 + [99.0]           # 76本。MA25≈98.04 < 99 < MA75≈101.3
    highs = [103.5] * 51 + [98.5] * 24 + [99.3]
    vols = [2_000_000] * 75 + [4_000_000]
    df = make_df(closes, volumes=vols, highs=highs)
    r = compute_indicators("4444", df, T)
    assert r["ma25"] < r["close"] < r["ma75"]
    assert 0 < r["dist_pct"] <= 5
    assert screen({"4444": df}).empty
    assert len(screen({"4444": df}, sp=ScreenParams(above_ma75=False))) == 1


# ⑤ 1〜3月は前年の高値を使う
def test_05_jan_to_mar_uses_previous_year():
    t = date(2026, 2, 16)
    days = bdays(t, 300)                                    # 2025年1月〜
    closes = np.where([d.year == 2025 for d in days], 100.0, 105.0)
    df = make_df(list(closes), end=t)
    i_peak = days.index(date(2025, 7, 1))
    df.iloc[i_peak, df.columns.get_loc("high")] = 120.0    # 前年7月の高値
    df.iloc[-1, df.columns.get_loc("close")] = 115.0
    r = compute_indicators("5555", df, t)
    assert r["ytd_high"] == 120.0 and r["ytd_high_date"] == date(2025, 7, 1)
    assert r["dist_pct"] == pytest.approx((120 - 115) / 120 * 100)
    # 設定で切り替えると当年分のみ（2026年の高値 105.5）
    r0 = compute_indicators("5555", df, t, CalcParams(ytd_prev_year_until_month=0))
    assert r0["ytd_high"] == 105.5
    # 4月になれば当年分のみ
    t_apr = date(2026, 4, 1)
    df_apr = pd.concat([df, make_df([105.0] * 31, end=t_apr).loc[lambda x: x.index > t]])
    assert compute_indicators("5555", df_apr, t_apr)["ytd_high"] == 105.5


# ⑥ 平均出来高に T を含めない
def test_06_volume_average_excludes_t():
    vols = [9_999_999] * 50 + [1_000_000] * 25 + [3_000_000]  # 26本前より古い出来高は無関係
    df = make_df([100.0] * 76, volumes=vols)
    r = compute_indicators("6666", df, T)
    assert r["vol_ratio"] == pytest.approx(3.0)   # T を含めると 3e6/1.077e6 ≈ 2.79 になる


# ⑦ 欠損日があっても落ちない
def test_07_missing_days_do_not_crash(near_high_df):
    rng = np.random.default_rng(0)
    df = near_high_df.copy()
    drop = rng.choice(len(df) - 1, size=10, replace=False)   # T 以外の10日を欠損
    df = df.drop(df.index[drop])
    df.iloc[5, df.columns.get_loc("close")] = np.nan          # 値の欠損（NaN）
    df.iloc[7, df.columns.get_loc("volume")] = np.nan
    r = compute_indicators("7777", df, T)
    assert r["dist_pct"] == pytest.approx(3.0)
    for k in ("vol_ratio", "ma25", "ma75", "turnover_avg25", "score"):
        assert r[k] is not None and np.isfinite(r[k])


def test_07b_insufficient_data_is_excluded_not_crashing(near_high_df):
    short = near_high_df.iloc[-74:]                           # 74本 < 75営業日
    zero = near_high_df.copy()
    zero.iloc[-1, zero.columns.get_loc("volume")] = 0         # T の出来高 0
    no_t = near_high_df.iloc[:-1]                             # T の足がない
    out = compute_all(
        pd.concat([d.rename_axis("date").reset_index().assign(code=c)
                   for c, d in {"S": short, "Z": zero, "N": no_t}.items()]), T)
    assert out["dist_pct"].isna().all() and out["score"].isna().all()
    assert out.set_index("code").loc["S", "close"] == pytest.approx(97.0)  # 行は残す（close は保持）
    out["market"] = "prime"
    assert apply_filters(out, ScreenParams(vol_filter=False, above_ma25=False, above_ma75=False,
                                           min_turnover=0)).empty
    assert compute_indicators("E", pd.DataFrame(), T)["close"] is None


# ---- 補助：スコア・流動性・市場・並び替え
def test_score():
    assert breakout_score(3.0, 2.0, 98, 90) == pytest.approx(20 + 16 + 10)
    assert breakout_score(1.0, 9.0, 90, 98) == pytest.approx(40 + 40)   # 出来高は 5 で頭打ち
    assert breakout_score(2.0, None, None, None) == pytest.approx(30)


def test_turnover_filter():
    df = uptrend_near_high()
    thin = df.assign(volume=df["volume"] // 100)              # 売買代金 ≈ 200万円
    assert screen({"T": thin}).empty
    assert len(screen({"T": thin}, sp=ScreenParams(min_turnover=0))) == 1


def test_market_filter_and_sort():
    dfs = {"A": uptrend_near_high(dist=4.0), "B": uptrend_near_high(dist=1.0),
           "C": uptrend_near_high(dist=2.0)}
    long = pd.concat([d.rename_axis("date").reset_index().assign(code=c) for c, d in dfs.items()])
    res = compute_all(long, T)
    res["market"] = ["prime", "growth", "etf"]
    assert list(apply_filters(res, ScreenParams())["code"]) == ["B", "A"]          # ETF は除外・距離昇順
    assert list(apply_filters(res, ScreenParams(include_etf=True))["code"]) == ["B", "C", "A"]
    assert list(apply_filters(res, ScreenParams(market="growth"))["code"]) == ["B"]
    assert list(apply_filters(res, ScreenParams(sort="score", order="desc"))["code"]) == ["B", "A"]
    assert len(apply_filters(res, ScreenParams(include_etf=True, limit=1))) == 1

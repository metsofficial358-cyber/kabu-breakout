"""東証の営業日判定（土日・祝日・12/31〜1/3 を休場とする）。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import jpholiday


def is_business_day(d: date) -> bool:
    if d.weekday() >= 5:
        return False
    if (d.month, d.day) in {(12, 31), (1, 1), (1, 2), (1, 3)}:
        return False
    return not jpholiday.is_holiday(d)


def latest_business_day(d: date) -> date:
    """d 以前（d を含む）で最も近い営業日。"""
    while not is_business_day(d):
        d -= timedelta(days=1)
    return d


def prev_business_day(d: date) -> date:
    return latest_business_day(d - timedelta(days=1))


def business_days_back(d: date, n: int) -> date:
    """d（営業日とみなす）から n 営業日さかのぼった日。"""
    d = latest_business_day(d)
    for _ in range(n):
        d = prev_business_day(d)
    return d


def ytd_start(t: date, prev_year_until_month: int = 3) -> date:
    """年初来高値の集計開始日。1〜prev_year_until_month 月は前年1/1から。"""
    if prev_year_until_month and t.month <= prev_year_until_month:
        return date(t.year - 1, 1, 1)
    return date(t.year, 1, 1)


def expected_trading_date(now: datetime, cutoff: time) -> date:
    """判定日 T：営業日で cutoff（既定 18:00 JST）を過ぎていれば当日、そうでなければ前営業日。
    取引時間中の途中の足を確定値として扱わないため。now は JST の naive/aware datetime。"""
    d = now.date()
    if is_business_day(d) and now.time() >= cutoff:
        return d
    return prev_business_day(d)

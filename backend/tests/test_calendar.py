from datetime import date

from app.calendar_jp import (
    business_days_back,
    expected_trading_date,
    is_business_day,
    latest_business_day,
    ytd_start,
)


def test_holidays():
    assert not is_business_day(date(2026, 11, 3))   # 文化の日
    assert not is_business_day(date(2026, 11, 7))   # 土曜
    assert not is_business_day(date(2026, 12, 31))
    assert is_business_day(date(2027, 1, 4))  # 1/4(月)は大発会
    assert is_business_day(date(2026, 11, 10))


def test_latest_and_back():
    assert latest_business_day(date(2026, 11, 8)) == date(2026, 11, 6)
    assert business_days_back(date(2026, 11, 10), 1) == date(2026, 11, 9)
    assert business_days_back(date(2026, 11, 5), 2) == date(2026, 11, 2)  # 11/3 祝日を飛ばす


def test_ytd_start():
    assert ytd_start(date(2026, 3, 31)) == date(2025, 1, 1)
    assert ytd_start(date(2026, 4, 1)) == date(2026, 1, 1)
    assert ytd_start(date(2026, 2, 1), prev_year_until_month=0) == date(2026, 1, 1)


def test_expected_trading_date():
    from datetime import datetime, time
    cut = time(18, 0)
    assert expected_trading_date(datetime(2026, 11, 10, 12, 49), cut) == date(2026, 11, 9)  # 場中は前営業日
    assert expected_trading_date(datetime(2026, 11, 10, 18, 5), cut) == date(2026, 11, 10)
    assert expected_trading_date(datetime(2026, 11, 4, 9, 0), cut) == date(2026, 11, 2)    # 11/3 祝日を飛ばす
    assert expected_trading_date(datetime(2026, 11, 8, 20, 0), cut) == date(2026, 11, 6)   # 日曜

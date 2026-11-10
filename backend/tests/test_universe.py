import pandas as pd
import pytest

from app.universe import map_market, normalize_code, parse_list


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("プライム（内国株式）", "prime"),
        ("プライム（外国株式）", "prime"),
        ("スタンダード（内国株式）", "standard"),
        ("グロース（内国株式）", "growth"),
        ("ETF・ETN", "etf"),
        ("REIT・ベンチャーファンド・カントリーファンド・インフラファンド", "reit"),
        ("PRO Market", "other"),
        ("出資証券", "other"),
    ],
)
def test_map_market(raw, expected):
    assert map_market(raw) == expected


def test_codes_are_strings():
    assert normalize_code("1301") == "1301"
    assert normalize_code("1301.0") == "1301"
    assert normalize_code("130a") == "130A"


def test_parse_list():
    df = pd.DataFrame({
        "日付": ["20261031"] * 3,
        "コード": ["7203", "130A", "1306"],
        "銘柄名": ["トヨタ自動車", "Veritas In Silico", "ＮＥＸＴ　ＦＵＮＤＳ　ＴＯＰＩＸ連動型上場投信"],
        "市場・商品区分": ["プライム（内国株式）", "グロース（内国株式）", "ETF・ETN"],
        "33業種区分": ["輸送用機器", "医薬品", "-"],
    })
    out = parse_list(df).set_index("code")
    assert out.loc["130A", "market"] == "growth"
    assert out.loc["1306", "market"] == "etf"
    assert out.loc["1306", "sector33"] is None
    assert out.loc["1306", "name"] == "NEXT FUNDS TOPIX連動型上場投信"  # 全角英数・空白は半角に

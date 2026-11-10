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


def test_is_foreign():
    from app.universe import is_foreign
    assert is_foreign("プライム（外国株式）") and is_foreign("グロース（外国株式）")
    assert not is_foreign("プライム（内国株式）") and not is_foreign(None)


def test_migration_adds_columns_to_old_db(tmp_path):
    """旧版の DB（market_raw / range20_pct 列なし）でも起動時に列が追加される。"""
    import sqlite3
    from app.db import init_db, make_engine
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE stocks (code VARCHAR(8) PRIMARY KEY, name VARCHAR(128), market VARCHAR(16), "
                "sector33 VARCHAR(64), is_active BOOLEAN, updated_at DATETIME)")
    con.execute("CREATE TABLE screen_results (run_date DATE, code VARCHAR(8), close FLOAT, "
                "PRIMARY KEY (run_date, code))")
    con.commit(); con.close()
    init_db(make_engine(f"sqlite:///{path}"))
    con = sqlite3.connect(path)
    assert "market_raw" in {r[1] for r in con.execute("PRAGMA table_info(stocks)")}
    assert "range20_pct" in {r[1] for r in con.execute("PRAGMA table_info(screen_results)")}

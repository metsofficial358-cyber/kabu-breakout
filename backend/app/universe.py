"""JPX「東証上場銘柄一覧」の取り込み。"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from datetime import datetime
from urllib.parse import urljoin

import pandas as pd
import requests
from sqlalchemy import update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Stock

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (kabu-breakout screener)"}


def is_foreign(raw: str | None) -> bool:
    """「プライム（外国株式）」など、外国会社の株式（JDR を含む）。"""
    return "外国株式" in str(raw or "")


def map_market(raw: str) -> str:
    s = str(raw or "")
    if "PRO Market" in s:
        return "other"
    if "プライム" in s:
        return "prime"
    if "スタンダード" in s:
        return "standard"
    if "グロース" in s:
        return "growth"
    if "ETF" in s or "ETN" in s:
        return "etf"
    if "REIT" in s or "インフラファンド" in s:
        return "reit"
    return "other"


def normalize_code(v: object) -> str:
    s = str(v).strip().upper()
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def find_list_url(session: requests.Session | None = None) -> str:
    page = get_settings().jpx_list_page
    html = (session or requests).get(page, headers=UA, timeout=30).text
    m = re.search(r'href="([^"]*data_j\.xlsx?)"', html)
    if not m:
        raise RuntimeError("data_j.xls(x) へのリンクが見つかりません")
    return urljoin(page, m.group(1))


def download_list() -> pd.DataFrame:
    url = find_list_url()
    log.info("download %s", url)
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    engine = "xlrd" if url.endswith(".xls") else "openpyxl"
    return pd.read_excel(io.BytesIO(r.content), dtype=str, engine=engine)


def parse_list(df: pd.DataFrame) -> pd.DataFrame:
    """JPXの表 → code/name/market/sector33。"""
    out = pd.DataFrame(
        {
            "code": df["コード"].map(normalize_code),
            "name": df["銘柄名"].astype(str).map(lambda x: unicodedata.normalize("NFKC", x).strip()),
            "market_raw": df["市場・商品区分"].astype(str).str.strip(),
            "sector33": df["33業種区分"].astype(str).str.strip().replace({"-": None, "nan": None}),
        }
    )
    out["market"] = out["market_raw"].map(map_market)
    return out[out["code"].str.fullmatch(r"[0-9A-Z]{4,5}")].drop_duplicates("code")


def upsert_stocks(db: Session, parsed: pd.DataFrame) -> dict[str, int]:
    now = datetime.now()
    rows = [
        {"code": r.code, "name": r.name, "market": r.market, "market_raw": r.market_raw,
         "sector33": r.sector33, "is_active": True, "updated_at": now}
        for r in parsed.itertuples()
    ]
    stmt = insert(Stock).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["code"],
        set_={k: stmt.excluded[k] for k in ("name", "market", "market_raw", "sector33", "is_active", "updated_at")},
    )
    db.execute(stmt)
    # 一覧から消えた銘柄は非アクティブに
    deactivated = db.execute(
        update(Stock).where(Stock.code.not_in(parsed["code"].tolist()), Stock.is_active.is_(True))
        .values(is_active=False, updated_at=now)
    ).rowcount
    db.commit()
    return {"upserted": len(rows), "deactivated": deactivated or 0}


def refresh_universe(db: Session) -> dict[str, int]:
    parsed = parse_list(download_list())
    stats = upsert_stocks(db, parsed)
    stats.update(parsed["market"].value_counts().to_dict())
    return stats

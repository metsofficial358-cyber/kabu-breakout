"""CLI。

  python -m app.batch run [--date YYYY-MM-DD] [--no-retry]   # 日次ジョブ（cron 用）
  python -m app.batch init-db
  python -m app.batch universe
  python -m app.batch fetch --sample 20 | --codes 7203 6758  # 株価だけ取得
  python -m app.batch screen [--date YYYY-MM-DD]             # 指標を計算して表示（保存しない）
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date

import pandas as pd
from sqlalchemy import func, select

from .calendar_jp import is_business_day
from .config import get_settings
from .db import SessionLocal, init_db
from .jobs import current_t, load_prices, runner
from .models import DailyPrice, Stock
from .prices import update_prices
from .screener import CalcParams, ScreenParams, apply_filters, compute_all
from .universe import refresh_universe

log = logging.getLogger("app.batch")

SAMPLE_FIXED = ["7203", "6758", "9984", "8306", "6861", "9432", "8035", "7974", "4063", "6098"]


def pick_sample(db, n: int) -> list[str]:  # noqa: ANN001
    """プライム主力10＋スタンダード・グロース各4＋英字コード1＋ETF1（不足分はプライムで補う）。"""
    active = {c for (c,) in db.execute(select(Stock.code).where(Stock.is_active.is_(True)))}
    codes = [c for c in SAMPLE_FIXED if c in active]
    for market, k in (("standard", 4), ("growth", 4), ("etf", 1)):
        codes += list(db.execute(select(Stock.code).where(Stock.market == market, Stock.is_active.is_(True))
                                 .order_by(Stock.code).limit(k)).scalars())
    alpha = db.execute(select(Stock.code).where(Stock.code.regexp_match("[A-Z]"),
                                                Stock.market.in_(["prime", "standard", "growth"]))
                       .order_by(Stock.code).limit(1)).scalar()
    if alpha:
        codes.append(alpha)
    seen = list(dict.fromkeys(codes))
    if len(seen) < n:  # 重複で足りない分はプライムで補う
        seen += list(db.execute(select(Stock.code).where(Stock.market == "prime", Stock.is_active.is_(True),
                                                         Stock.code.not_in(seen)).order_by(Stock.code)
                                .limit(n - len(seen))).scalars())
    return seen[:n]


def cmd_run(args: argparse.Namespace) -> int:
    t = date.fromisoformat(args.date) if args.date else current_t()
    if not args.date and not is_business_day(t):
        print(f"{t} は休場日のためスキップ")
        return 0
    last = None
    for attempt in range(1 if args.no_retry else 2):
        if attempt:
            wait = get_settings().stale_retry_minutes
            print(f"データ未更新のため {wait} 分後に再試行します")
            time.sleep(wait * 60)
        runner.start(t=t, background=False, trigger="cli")
        last = runner.status()
        print(f"run {last['run_id']} T={t}: {last['status']} {last['message']}")
        if last["status"] != "stale":
            break
    return 0 if last and last["status"] == "success" else 1


def cmd_fetch(args: argparse.Namespace) -> None:
    from .providers.yfinance_provider import YFinanceProvider

    t = current_t()
    with SessionLocal() as db:
        codes = args.codes or pick_sample(db, args.sample)
        print(f"T={t}  対象 {len(codes)} 銘柄: {' '.join(codes)}")
        t0 = time.time()
        st = update_prices(db, YFinanceProvider(), codes, t,
                           progress=lambda d, n: print(f"  progress {d}/{n}"))
        print(f"完了 {time.time() - t0:.1f}s  初回={st.full} 差分={st.incremental} "
              f"保存行={st.rows} 分割再取得={st.split_refetched} 失敗={len(st.errors)}")
        for c, m in st.errors.items():
            print(f"  ERR {c}: {m}")
        q = (select(DailyPrice.code, func.count(), func.min(DailyPrice.date), func.max(DailyPrice.date))
             .where(DailyPrice.code.in_(codes)).group_by(DailyPrice.code))
        for code, cnt, mn, mx in db.execute(q):
            print(f"  {code:6s} {cnt:4d}本  {mn} 〜 {mx}")


def cmd_screen(args: argparse.Namespace) -> None:
    t = date.fromisoformat(args.date) if args.date else current_t()
    with SessionLocal() as db:
        res = compute_all(load_prices(db, t), t, CalcParams.from_settings())
        markets = dict(db.execute(select(Stock.code, Stock.market)).all())
    res["market"] = res["code"].map(markets)
    pd.set_option("display.width", 200)
    cols = ["code", "market", "close", "change_pct", "ytd_high", "ytd_high_date", "dist_pct",
            "vol_ratio", "ma25", "ma75", "turnover_avg25", "updated_today", "score"]
    print(f"T={t}  全{len(res)}銘柄の指標")
    print(res[cols].round(2).to_string(index=False))
    hit = apply_filters(res, ScreenParams())
    print(f"\n既定条件で該当 {len(hit)} 銘柄: {list(hit['code'])}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="python -m app.batch")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--date")
    r.add_argument("--no-retry", action="store_true")
    sub.add_parser("init-db")
    sub.add_parser("universe")
    f = sub.add_parser("fetch")
    f.add_argument("--sample", type=int, default=20)
    f.add_argument("--codes", nargs="*")
    sc = sub.add_parser("screen")
    sc.add_argument("--date")
    args = p.parse_args()

    init_db()
    if args.cmd == "run":
        runner.recover_interrupted()
        sys.exit(cmd_run(args))
    elif args.cmd == "init-db":
        print("DB initialized:", get_settings().database_url)
    elif args.cmd == "universe":
        with SessionLocal() as db:
            print(refresh_universe(db))
    elif args.cmd == "fetch":
        cmd_fetch(args)
    elif args.cmd == "screen":
        cmd_screen(args)


if __name__ == "__main__":
    main()

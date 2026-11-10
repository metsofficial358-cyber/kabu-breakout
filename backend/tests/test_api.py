import threading
import time
from datetime import date, datetime

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app import jobs, scheduler
from app.db import SessionLocal, init_db
from app.jobs import AlreadyRunning, runner
from app.main import app, cache
from app.models import DailyPrice, FetchError, Run, ScreenResult, Stock
from app.providers.base import FetchResult, PriceProvider
from tests.conftest import T, make_df, uptrend_near_high


RAW = {"prime": "プライム（内国株式）", "standard": "スタンダード（内国株式）", "growth": "グロース（内国株式）",
       "etf": "ETF・ETN", "reit": "REIT・ベンチャーファンド・カントリーファンド・インフラファンド",
       "other": "PRO Market", "foreign": "プライム（外国株式）"}


def series():
    return {
        "1001": ("prime", uptrend_near_high(n=300, dist=3.0)),          # 抽出
        "1002": ("growth", uptrend_near_high(n=300, dist=1.0)),         # 抽出
        "1003": ("standard", uptrend_near_high(n=300, dist=4.0, vol_mult=1.2)),  # 出来高不足
        "1004": ("etf", uptrend_near_high(n=300, dist=2.0)),            # ETF
        "130A": ("growth", make_df([100.0] * 300)),                     # 横ばい（距離 0.5%）
        "1005": ("reit", uptrend_near_high(n=300, dist=2.5)),           # REIT
        "1006": ("other", uptrend_near_high(n=300, dist=3.5)),          # PRO Market
        "1007": ("foreign", uptrend_near_high(n=300, dist=1.5)),        # 外国株（市場区分はプライム）
    }


class FakeProvider(PriceProvider):
    def __init__(self, data, gate: threading.Event | None = None, last_day: date | None = None,
                 fail: tuple[str, ...] = ()):
        self.data, self.gate, self.last_day, self.fail = data, gate, last_day, fail

    def fetch_daily(self, codes, start, end, progress=None):
        if self.gate:
            self.gate.wait(5)
        res = FetchResult()
        end = min(end, self.last_day or end)
        for i, c in enumerate(codes):
            if c in self.fail or c not in self.data:
                res.errors[c] = "no data returned"
            else:
                df = self.data[c][1]
                res.data[c] = df[(df.index >= start) & (df.index <= end)]
            if progress:
                progress(i + 1, len(codes))
        return res


@pytest.fixture
def client():
    init_db()
    with SessionLocal() as db:
        for m in (ScreenResult, DailyPrice, FetchError, Run, Stock):
            db.execute(delete(m))
        for code, (market, _) in series().items():
            db.add(Stock(code=code, name=f"銘柄{code}", market="prime" if market == "foreign" else market,
                         sector33="テスト",
                         market_raw=RAW[market], is_active=True, updated_at=jobs.now_jst()))
        db.commit()
    cache.clear()
    runner.provider_factory = lambda: FakeProvider(series(), fail=("9999",))
    with TestClient(app) as c:
        yield c
    runner.provider_factory = None


def wait_done(c, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = c.get("/api/refresh/status").json()
        if not st["running"]:
            return st
        time.sleep(0.05)
    raise TimeoutError


def run_once(c):
    r = runner.start(t=T, background=False)
    cache.clear()
    return r


def test_screen_empty_before_first_run(client):
    r = client.get("/api/screen").json()
    assert r == {"run_date": None, "updated_at": None, "count": 0, "items": []}


def test_run_and_screen(client):
    run_once(client)
    st = client.get("/api/refresh/status").json()
    assert st["status"] == "success" and st["processed"] == st["total"] == 8
    r = client.get("/api/screen").json()
    assert r["run_date"] == T.isoformat()
    assert [i["code"] for i in r["items"]] == ["1002", "1001"]           # 距離の昇順
    item = r["items"][1]
    assert item["name"] == "銘柄1001" and item["market"] == "prime"
    assert item["dist_pct"] == pytest.approx(3.0)                        # 丸めずに返す
    assert item["ytd_high_date"] and item["spark"] is None


def test_screen_params(client):
    run_once(client)
    g = lambda **q: [i["code"] for i in client.get("/api/screen", params=q).json()["items"]]  # noqa: E731
    assert g(market="growth") == ["1002"]
    assert g(include_etf="true") == ["1002", "1004", "1001"]
    assert g(include_reit="true") == ["1002", "1005", "1001"]
    assert g(include_other="true") == ["1002", "1001", "1006"]
    assert g(include_foreign="true") == ["1002", "1007", "1001"]
    assert g(include_etf="true", include_reit="true", include_other="true", include_foreign="true") == [
        "1002", "1007", "1004", "1005", "1001", "1006"]
    item = client.get("/api/screen", params={"include_foreign": "true"}).json()["items"][1]
    assert item["is_foreign"] is True and item["range20_pct"] > 5
    assert g(vol_filter="false") == ["1002", "1001", "1003"]
    assert g(max_dist=2) == ["1002"]
    assert g(sort="score", order="desc") == ["1002", "1001"]
    r = client.get("/api/screen", params={"limit": 1}).json()
    assert r["count"] == 2 and len(r["items"]) == 1                     # count は件数上限の前
    assert client.get("/api/screen", params={"sort": "bad"}).status_code == 422
    assert client.get("/api/screen", params={"run_date": "2020-01-01"}).status_code == 404
    sp = client.get("/api/screen", params={"with_spark": "true"}).json()["items"][0]["spark"]
    assert len(sp) == 60


def test_chart(client):
    run_once(client)
    r = client.get("/api/stocks/1001/chart", params={"days": 120}).json()
    assert len(r["bars"]) == 120 and r["bars"][-1]["date"] == T.isoformat()
    assert r["ytd_high"] == pytest.approx(100.0)
    assert r["bars"][0]["date"] < r["bars"][-1]["date"]
    assert client.get("/api/stocks/130a/chart").json()["code"] == "130A"
    assert client.get("/api/stocks/0000/chart").status_code == 404


def test_refresh_lock_and_progress(client):
    gate = threading.Event()
    runner.provider_factory = lambda: FakeProvider(series(), gate=gate)
    r1 = client.post("/api/refresh")
    assert r1.status_code == 202
    r2 = client.post("/api/refresh")
    assert r2.status_code == 409 and r2.json()["run_id"] == r1.json()["run_id"]   # 二重起動しない
    st = client.get("/api/refresh/status").json()
    assert st["running"] and st["phase"] == "prices" and st["total"] == 8
    gate.set()
    st = wait_done(client)
    assert st["status"] == "success"
    assert client.post("/api/refresh").status_code == 202                       # 終われば再び起動できる
    wait_done(client)


def test_lock_across_processes(client):
    with SessionLocal() as db:                    # 別プロセスの実行中を模擬
        db.add(Run(run_date=T, started_at=jobs.now_jst(), status="running"))
        db.commit()
    with pytest.raises(AlreadyRunning):
        runner.start(t=T, background=False)


def test_fetch_errors_recorded(client):
    with SessionLocal() as db:
        db.add(Stock(code="9999", name="x", market="prime", market_raw="プライム（内国株式）",
                     is_active=True, updated_at=jobs.now_jst()))
        db.commit()
    run_id = run_once(client)
    with SessionLocal() as db:
        errs = db.query(FetchError).filter_by(run_id=run_id).all()
        run = db.get(Run, run_id)
    assert [e.code for e in errs] == ["9999"] and run.errors == 1 and run.status == "success"


def test_stale_data_is_not_saved(client):
    runner.provider_factory = lambda: FakeProvider(series(), last_day=date(2026, 11, 6))  # T の足がない
    runner.start(t=T, background=False)
    assert runner.status()["status"] == "stale"
    with SessionLocal() as db:
        assert db.query(ScreenResult).count() == 0
    assert client.get("/api/screen").json()["count"] == 0


def test_daily_job_skip_and_retry(client, monkeypatch):
    monkeypatch.setattr(scheduler, "now_jst", lambda: datetime(2026, 11, 3, 18, 0))   # 文化の日
    assert scheduler.daily_job(runner, None) == "skipped"

    class Sched:
        jobs = []
        def add_job(self, *a, **kw):  # noqa: E301
            self.jobs.append(kw)

    s = Sched()
    monkeypatch.setattr(scheduler, "now_jst", lambda: datetime(2026, 11, 9, 18, 0))
    runner.provider_factory = lambda: FakeProvider(series(), last_day=date(2026, 11, 6))
    assert scheduler.daily_job(runner, s) == "stale"
    assert len(s.jobs) == 1 and s.jobs[0]["run_date"] == datetime(2026, 11, 9, 18, 30)
    assert s.jobs[0]["args"][2] is True                       # 再試行は1回だけ
    assert scheduler.daily_job(runner, s, retry=True) == "stale" and len(s.jobs) == 1
    runner.provider_factory = lambda: FakeProvider(series())
    assert scheduler.daily_job(runner, s, retry=True) == "success"


def test_health(client):
    r = client.get("/api/health").json()
    assert r["ok"] and r["db"]


def test_screen_is_fast_with_full_universe(client):
    """約4,400銘柄の結果でも条件変更（API 側の絞り込み）が十分速いこと。"""
    rows, stocks = [], []
    for i in range(4400):
        code = f"{2000 + i}"
        stocks.append({"code": code, "name": code, "market": "prime", "sector33": None,
                       "market_raw": "プライム（内国株式）",
                       "is_active": True, "updated_at": jobs.now_jst()})
        rows.append({"run_date": T, "code": code, "close": 100.0, "change_pct": 1.0, "ytd_high": 102.0 + i % 10,
                     "ytd_high_date": date(2026, 9, 1), "dist_pct": (i % 100) / 10, "volume": 10**6,
                     "vol_ratio": 1 + (i % 30) / 10, "ma25": 95.0, "ma75": 90.0, "turnover_avg25": 2e8,
                     "updated_today": i % 50 == 0, "score": 10.0})
    with SessionLocal() as db:
        db.execute(Stock.__table__.insert(), stocks)
        db.execute(ScreenResult.__table__.insert(), rows)
        db.add(Run(run_date=T, started_at=jobs.now_jst(), finished_at=jobs.now_jst(), status="success"))
        db.commit()
    client.get("/api/screen")  # 1回目でキャッシュ
    t0 = time.perf_counter()
    for md in (1, 3, 5, 8, 10):
        r = client.get("/api/screen", params={"max_dist": md, "with_spark": "true"})
        assert r.status_code == 200
    per = (time.perf_counter() - t0) / 5
    assert per < 1.0, per

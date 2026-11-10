"""APScheduler：毎営業日 18:00 JST に日次ジョブ。データ未更新なら30分後に1回だけ再試行。"""
from __future__ import annotations

import logging
from datetime import timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .calendar_jp import is_business_day
from .config import get_settings
from .jobs import AlreadyRunning, JobRunner, now_jst

log = logging.getLogger(__name__)
DAILY_JOB_ID = "daily"


def daily_job(runner: JobRunner, sched: BackgroundScheduler | None, retry: bool = False) -> str:
    """定時ジョブ。戻り値は結果（テスト用）：skipped / busy / success / stale / failed。"""
    today = now_jst().date()
    if not is_business_day(today):
        log.info("%s は休場日のためスキップ", today)
        return "skipped"
    try:
        runner.start(t=today, background=False, trigger="retry" if retry else "scheduled")
    except AlreadyRunning:
        log.info("手動更新が実行中のため定時ジョブをスキップ")
        return "busy"
    status = runner.progress.status or "failed"
    if status == "stale" and not retry and sched is not None:
        when = now_jst() + timedelta(minutes=get_settings().stale_retry_minutes)
        log.info("データ未更新。%s に再試行します", when)
        sched.add_job(daily_job, "date", run_date=when, args=[runner, sched, True],
                      id="daily-retry", replace_existing=True)
    return status


def create_scheduler(runner: JobRunner) -> BackgroundScheduler:
    s = get_settings()
    sched = BackgroundScheduler(timezone=s.timezone)
    sched.add_job(
        daily_job,
        CronTrigger(day_of_week="mon-fri", hour=s.batch_hour, minute=s.batch_minute, timezone=s.timezone),
        args=[runner, sched], id=DAILY_JOB_ID, replace_existing=True,
        misfire_grace_time=3600, coalesce=True, max_instances=1,
    )
    return sched

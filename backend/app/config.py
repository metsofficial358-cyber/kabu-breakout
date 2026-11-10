"""既定値・定数。すべて環境変数（.env）で上書きできる。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # リポジトリ直下の .env → backend/.env の順に読む（後の方が優先）。環境変数はさらに優先
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR.parent / ".env", BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # --- DB ---
    database_url: str = f"sqlite:///{BASE_DIR.parent / 'data' / 'kabu.db'}"

    # --- データ取得 ---
    jpx_list_page: str = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"
    universe_refresh_days: int = 7          # JPX一覧の再取り込み間隔（日）
    fetch_chunk_size: int = 100             # yf.download 1回あたりの銘柄数
    fetch_sleep_min: float = 1.0            # チャンク間の待ち（秒）
    fetch_sleep_max: float = 2.0
    fetch_retries: int = 3                  # 失敗時の再試行回数（指数バックオフ）
    fetch_backoff_base: float = 2.0
    refetch_business_days: int = 10         # 2回目以降に取り直す直近営業日数
    split_detect_threshold: float = 0.01    # 保存済み終値とのずれがこれ以上なら全期間を再取得
    initial_min_calendar_days: int = 150    # 初回取得で最低限さかのぼる暦日（MA75用）

    # --- 計算定義 ---
    ytd_prev_year_until_month: int = 3      # この月までは前年1月から集計（0で無効）
    vol_avg_days: int = 25
    ma_short: int = 25
    ma_long: int = 75
    turnover_avg_days: int = 25
    min_history_days: int = 75
    # 値動きが止まった銘柄（TOB の買付価格への張り付きなど）の判定：
    # 直近 pinned_days 営業日の (最高値 - 最安値) / 終値 が pinned_range_pct % 未満
    pinned_days: int = 20
    pinned_range_pct: float = 1.0

    # --- スケジューラ ---
    scheduler_enabled: bool = True
    timezone: str = "Asia/Tokyo"
    batch_hour: int = 18
    batch_minute: int = 0
    stale_retry_minutes: int = 30
    stale_ratio_threshold: float = 0.5      # 当日分を持つ銘柄がこの割合未満なら「データ未更新」


# --- breakout_score の重み（3章） ---
SCORE_DIST_BASE = 5.0
SCORE_DIST_WEIGHT = 10.0
SCORE_VOL_CAP = 5.0
SCORE_VOL_WEIGHT = 8.0
SCORE_MA_BONUS = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

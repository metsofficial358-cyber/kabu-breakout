export type Market = "prime" | "standard" | "growth" | "etf" | "reit" | "other";
export type MarketTab = "all" | "prime" | "standard" | "growth";
export type SortKey = "dist" | "vol_ratio" | "change" | "score";
export type Order = "asc" | "desc";
export type View = "card" | "table";

export interface ScreenItem {
  code: string;
  name: string | null;
  market: Market | null;
  sector33: string | null;
  close: number | null;
  change_pct: number | null;
  ytd_high: number | null;
  ytd_high_date: string | null;
  dist_pct: number | null;
  volume: number | null;
  vol_ratio: number | null;
  ma25: number | null;
  ma75: number | null;
  turnover_avg25: number | null;
  updated_today: boolean | null;
  score: number | null;
  range20_pct?: number | null;
  is_foreign?: boolean;
  spark?: number[] | null;
}

export interface ScreenResponse {
  run_date: string | null;
  updated_at: string | null;
  count: number;
  items: ScreenItem[];
}

export interface Bar {
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
}

export interface ChartResponse {
  code: string;
  name: string | null;
  market: Market | null;
  run_date: string | null;
  ytd_high: number | null;
  ytd_high_date: string | null;
  bars: Bar[];
}

export interface RefreshStatus {
  running: boolean;
  run_id: number | null;
  run_date: string | null;
  phase: "universe" | "prices" | "screen" | null;
  processed: number;
  total: number;
  errors: number;
  status: "running" | "success" | "stale" | "failed" | "skipped" | null;
  message: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Filters {
  market: MarketTab;
  max_dist: number;
  vol_filter: boolean;
  min_vol_ratio: number;
  above_ma25: boolean;
  above_ma75: boolean;
  min_turnover: number;
  exclude_pinned: boolean;
  include_updated: boolean;
  sort: SortKey;
  order: Order;
  view: View;
}

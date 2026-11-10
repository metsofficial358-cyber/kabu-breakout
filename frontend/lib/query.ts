// フィルタ状態 ⇄ URL クエリ。既定値と同じ項目は URL に書かない（短く共有しやすくするため）。
import type { Filters, MarketTab, Order, SortKey, View } from "./types";

export const DEFAULT_FILTERS: Filters = {
  market: "all",
  max_dist: 5,
  vol_filter: true,
  min_vol_ratio: 1.5,
  above_ma25: true,
  above_ma75: true,
  min_turnover: 100_000_000,
  include_etf: false,
  include_reit: false,
  include_other: false,
  include_foreign: false,
  exclude_pinned: true,
  include_updated: false,
  sort: "dist",
  order: "asc",
  view: "card",
};

export const TURNOVER_OPTIONS = [
  { value: 0, label: "指定なし" },
  { value: 50_000_000, label: "5,000万円以上" },
  { value: 100_000_000, label: "1億円以上" },
  { value: 500_000_000, label: "5億円以上" },
];

const MARKETS: MarketTab[] = ["all", "prime", "standard", "growth"];
const SORTS: SortKey[] = ["dist", "vol_ratio", "change", "score"];

function num(v: string | null, def: number, min: number, max: number): number {
  if (v === null) return def;
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : def;
}

function bool(v: string | null, def: boolean): boolean {
  if (v === null) return def;
  return v === "true" || v === "1";
}

export function parseFilters(sp: URLSearchParams): Filters {
  const d = DEFAULT_FILTERS;
  const market = sp.get("market") as MarketTab;
  const sort = sp.get("sort") as SortKey;
  const turnover = num(sp.get("min_turnover"), d.min_turnover, 0, 1e13);
  return {
    market: MARKETS.includes(market) ? market : d.market,
    max_dist: Math.round(num(sp.get("max_dist"), d.max_dist, 1, 10) * 2) / 2,
    vol_filter: bool(sp.get("vol_filter"), d.vol_filter),
    min_vol_ratio: Math.round(num(sp.get("min_vol_ratio"), d.min_vol_ratio, 1, 5) * 10) / 10,
    above_ma25: bool(sp.get("above_ma25"), d.above_ma25),
    above_ma75: bool(sp.get("above_ma75"), d.above_ma75),
    min_turnover: TURNOVER_OPTIONS.some((o) => o.value === turnover) ? turnover : d.min_turnover,
    include_etf: bool(sp.get("include_etf"), d.include_etf),
    include_reit: bool(sp.get("include_reit"), d.include_reit),
    include_other: bool(sp.get("include_other"), d.include_other),
    include_foreign: bool(sp.get("include_foreign"), d.include_foreign),
    exclude_pinned: bool(sp.get("exclude_pinned"), d.exclude_pinned),
    include_updated: bool(sp.get("include_updated"), d.include_updated),
    sort: SORTS.includes(sort) ? sort : d.sort,
    order: (sp.get("order") as Order) === "desc" ? "desc" : "asc",
    view: (sp.get("view") as View) === "table" ? "table" : "card",
  };
}

export function filtersToQuery(f: Filters): string {
  const sp = new URLSearchParams();
  (Object.keys(f) as (keyof Filters)[]).forEach((k) => {
    if (f[k] !== DEFAULT_FILTERS[k]) sp.set(k, String(f[k]));
  });
  return sp.toString();
}

/** API 用（view を除き、すべての条件を明示する） */
export function filtersToApiQuery(f: Filters, extra: Record<string, string> = {}): string {
  const sp = new URLSearchParams();
  (Object.keys(f) as (keyof Filters)[]).forEach((k) => {
    if (k !== "view") sp.set(k, String(f[k]));
  });
  Object.entries(extra).forEach(([k, v]) => sp.set(k, v));
  return sp.toString();
}

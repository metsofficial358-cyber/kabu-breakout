"use client";
import { fmtPct, fmtPrice, fmtRatio, fmtYen } from "@/lib/format";
import type { ScreenItem } from "@/lib/types";
import CandleChart from "./CandleChart";
import MarketBadge from "./MarketBadge";
import { CodeLink, YahooLink } from "./StockLinks";

export default function StockCard({ item, runDate }: { item: ScreenItem; runDate: string | null }) {
  const ch = item.change_pct;
  const chCls = ch == null || ch === 0 ? "text-slate-500" : ch > 0 ? "text-up" : "text-down";
  const trendUp = item.ma25 != null && item.ma75 != null && item.ma25 > item.ma75;

  return (
    <article className="flex flex-col rounded-lg border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-800 dark:bg-slate-900/60">
      <div className="flex items-center gap-2">
        <CodeLink code={item.code} />
        <YahooLink code={item.code} />
        <h3 className="min-w-0 flex-1 truncate text-sm font-medium" title={item.name ?? ""}>
          {item.name}
        </h3>
        <MarketBadge market={item.market} />
      </div>

      <div className="mt-1 flex items-baseline gap-2">
        <span className="tabular text-2xl font-bold">{fmtPrice(item.close)}</span>
        <span className="text-xs text-slate-500">円</span>
        <span className={`tabular text-sm font-semibold ${chCls}`}>{fmtPct(ch, 2, true)}</span>
      </div>

      <div className="mt-2 rounded-md border border-hl-border bg-hl-bg px-2.5 py-1.5 text-hl-text">
        {item.updated_today ? (
          <div className="text-sm font-bold">本日 年初来高値を更新</div>
        ) : (
          <div className="text-sm">
            高値まで あと <span className="tabular text-lg font-extrabold">{fmtPct(item.dist_pct, 1)}</span>
          </div>
        )}
        <div className="tabular text-[11px] opacity-90">
          （年初来高値 ¥{fmtPrice(item.ytd_high)}／{item.ytd_high_date ?? "—"}）
        </div>
      </div>

      <dl className="tabular mt-2 grid grid-cols-3 gap-1 text-[11px]">
        <Stat label="出来高倍率" value={fmtRatio(item.vol_ratio)} strong={(item.vol_ratio ?? 0) >= 1.5} />
        <Stat label="平均売買代金" value={fmtYen(item.turnover_avg25)} />
        <Stat label="スコア" value={item.score == null ? "—" : item.score.toFixed(1)} />
        <Stat label="MA25" value={fmtPrice(item.ma25)} />
        <Stat label="MA75" value={fmtPrice(item.ma75)} />
        <Stat label="トレンド" value={trendUp ? "MA25>MA75" : "MA25≦MA75"} strong={trendUp} />
      </dl>

      <div className="mt-2">
        <CandleChart code={item.code} runDate={runDate} />
      </div>
    </article>
  );
}

function Stat({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="min-w-0 rounded bg-slate-50 px-1.5 py-1 dark:bg-slate-800/50">
      <dt className="truncate text-slate-500 dark:text-slate-400">{label}</dt>
      <dd className={`truncate ${strong ? "font-semibold text-slate-900 dark:text-white" : ""}`}>{value}</dd>
    </div>
  );
}

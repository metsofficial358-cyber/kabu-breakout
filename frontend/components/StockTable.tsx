"use client";
import { useMemo, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { fmtPct, fmtPrice, fmtVolume, MARKET_LABEL } from "@/lib/format";
import type { ScreenItem } from "@/lib/types";
import { CodeLink, YahooLink } from "./StockLinks";
import Sparkline from "./Sparkline";

type ColKey =
  | "code" | "name" | "market" | "close" | "change_pct" | "ytd_high" | "dist_pct" | "volume" | "vol_ratio" | "score";

const COLS: { key: ColKey; label: string; num?: boolean }[] = [
  { key: "code", label: "コード" },
  { key: "name", label: "銘柄名" },
  { key: "market", label: "市場" },
  { key: "close", label: "現在値", num: true },
  { key: "change_pct", label: "前日比", num: true },
  { key: "ytd_high", label: "年初来高値", num: true },
  { key: "dist_pct", label: "高値まで(%)", num: true },
  { key: "volume", label: "本日出来高", num: true },
  { key: "vol_ratio", label: "25日平均比(%)", num: true },
  { key: "score", label: "スコア", num: true },
];

export default function StockTable({ items }: { items: ScreenItem[] }) {
  // 見出しクリックで並び替え（取得済みの行の中で）。未指定なら API の並び順のまま
  const [sort, setSort] = useState<{ key: ColKey; dir: 1 | -1 } | null>(null);

  const rows = useMemo(() => {
    if (!sort) return items;
    const { key, dir } = sort;
    return [...items].sort((a, b) => {
      const va = a[key];
      const vb = b[key];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === "number" && typeof vb === "number") return (va - vb) * dir;
      return String(va).localeCompare(String(vb), "ja") * dir;
    });
  }, [items, sort]);

  const onHead = (key: ColKey) =>
    setSort((s) => (s?.key === key ? (s.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 }));

  return (
    <div className="max-h-[calc(100vh-220px)] overflow-auto rounded-lg border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/60">
      <table className="tabular w-full min-w-[1080px] border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-slate-100 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          <tr>
            {COLS.map((c) => (
              <th
                key={c.key}
                scope="col"
                aria-sort={sort?.key === c.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
                className={`whitespace-nowrap px-3 py-2 font-medium ${c.num ? "text-right" : "text-left"}`}
              >
                <button onClick={() => onHead(c.key)} className="inline-flex items-center gap-0.5 hover:text-slate-900 dark:hover:text-white">
                  {c.label}
                  {sort?.key === c.key &&
                    (sort.dir === 1 ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />)}
                </button>
              </th>
            ))}
            <th scope="col" className="px-3 py-2 text-left font-medium">60日</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((it) => {
            const ch = it.change_pct;
            return (
              <tr key={it.code} className="border-t border-slate-100 hover:bg-amber-50/50 dark:border-slate-800 dark:hover:bg-slate-800/40">
                <td className="whitespace-nowrap px-3 py-1.5">
                  <span className="inline-flex items-center gap-1.5">
                    <CodeLink code={it.code} />
                    <YahooLink code={it.code} />
                  </span>
                </td>
                <td className="max-w-[16rem] truncate px-3 py-1.5" title={it.name ?? ""}>{it.name}</td>
                <td className="whitespace-nowrap px-3 py-1.5 text-xs text-slate-500">{MARKET_LABEL[it.market ?? ""] ?? it.market}</td>
                <td className="px-3 py-1.5 text-right font-semibold">{fmtPrice(it.close)}</td>
                <td className={`px-3 py-1.5 text-right ${ch == null || ch === 0 ? "" : ch > 0 ? "text-up" : "text-down"}`}>
                  {fmtPct(ch, 2, true)}
                </td>
                <td className="px-3 py-1.5 text-right">
                  {fmtPrice(it.ytd_high)}
                  <div className="text-[10px] text-slate-400">{it.ytd_high_date}</div>
                </td>
                <td className="px-3 py-1.5 text-right">
                  {it.updated_today ? (
                    <span className="rounded bg-hl-bg px-1 text-xs font-semibold text-hl-text">更新</span>
                  ) : (
                    <span className="font-bold text-amber-700 dark:text-amber-400">{fmtPct(it.dist_pct, 2)}</span>
                  )}
                </td>
                <td className="px-3 py-1.5 text-right">{fmtVolume(it.volume)}</td>
                <td className="px-3 py-1.5 text-right">{it.vol_ratio == null ? "—" : `${(it.vol_ratio * 100).toFixed(0)}%`}</td>
                <td className="px-3 py-1.5 text-right">{it.score == null ? "—" : it.score.toFixed(1)}</td>
                <td className="px-3 py-1">
                  <Sparkline values={it.spark ?? []} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

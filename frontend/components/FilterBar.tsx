"use client";
import { useEffect, useState } from "react";
import { ArrowDownWideNarrow, ArrowUpNarrowWide, RotateCcw } from "lucide-react";
import { DEFAULT_FILTERS, TURNOVER_OPTIONS } from "@/lib/query";
import type { Filters, SortKey } from "@/lib/types";

const SORTS: { value: SortKey; label: string }[] = [
  { value: "dist", label: "高値までの距離" },
  { value: "vol_ratio", label: "出来高倍率" },
  { value: "change", label: "前日比" },
  { value: "score", label: "スコア" },
];

interface Props {
  filters: Filters;
  onChange: (patch: Partial<Filters>) => void;
}

export default function FilterBar({ filters: f, onChange }: Props) {
  // スライダーはドラッグ中も表示を追従させ、確定は少し待ってから（URL と API 呼び出しを間引く）
  const [dist, setDist] = useState(f.max_dist);
  const [vol, setVol] = useState(f.min_vol_ratio);
  useEffect(() => setDist(f.max_dist), [f.max_dist]);
  useEffect(() => setVol(f.min_vol_ratio), [f.min_vol_ratio]);
  useEffect(() => {
    if (dist === f.max_dist) return;
    const t = setTimeout(() => onChange({ max_dist: dist }), 150);
    return () => clearTimeout(t);
  }, [dist]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (vol === f.min_vol_ratio) return;
    const t = setTimeout(() => onChange({ min_vol_ratio: vol }), 300);
    return () => clearTimeout(t);
  }, [vol]); // eslint-disable-line react-hooks/exhaustive-deps

  const isDefault = (Object.keys(DEFAULT_FILTERS) as (keyof Filters)[]).every(
    (k) => k === "market" || k === "view" || f[k] === DEFAULT_FILTERS[k],
  );

  return (
    <section
      aria-label="絞り込み条件"
      className="rounded-lg border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-900/60"
    >
      <div className="grid gap-x-6 gap-y-3 md:grid-cols-2 xl:grid-cols-[minmax(220px,1fr)_minmax(280px,1fr)_auto_auto]">
        <label className="block">
          <div className="mb-1 flex items-baseline justify-between">
            <span className="text-slate-600 dark:text-slate-400">高値までの距離</span>
            <span className="tabular font-semibold">{dist.toFixed(1)}% 以内</span>
          </div>
          <input
            type="range"
            min={1}
            max={10}
            step={0.5}
            value={dist}
            onChange={(e) => setDist(Number(e.target.value))}
            className="w-full"
            aria-label="高値までの距離（%）"
          />
        </label>

        <div>
          <div className="mb-1 flex items-center justify-between gap-2">
            <Toggle checked={f.vol_filter} onChange={(v) => onChange({ vol_filter: v })} label="出来高急増（25日平均比）" />
            <span className={`tabular whitespace-nowrap font-semibold ${f.vol_filter ? "" : "text-slate-400 dark:text-slate-600"}`}>
              {vol.toFixed(1)} 倍以上
            </span>
          </div>
          <input
            type="range"
            min={1}
            max={5}
            step={0.1}
            value={vol}
            disabled={!f.vol_filter}
            onChange={(e) => setVol(Number(e.target.value))}
            className="w-full disabled:opacity-40"
            aria-label="出来高倍率"
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Toggle checked={f.above_ma25} onChange={(v) => onChange({ above_ma25: v })} label="MA25 より上" />
          <Toggle checked={f.above_ma75} onChange={(v) => onChange({ above_ma75: v })} label="MA75 より上" />
          <label className="flex items-center gap-2">
            <span className="text-slate-600 dark:text-slate-400">売買代金</span>
            <select
              value={f.min_turnover}
              onChange={(e) => onChange({ min_turnover: Number(e.target.value) })}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
            >
              {TURNOVER_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Toggle checked={f.include_etf} onChange={(v) => onChange({ include_etf: v })} label="ETF・REIT等を含める" />
          <Toggle
            checked={f.include_updated}
            onChange={(v) => onChange({ include_updated: v })}
            label="本日更新済みを含める"
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3 dark:border-slate-800">
        <span className="text-slate-600 dark:text-slate-400">並び替え</span>
        <select
          value={f.sort}
          onChange={(e) => onChange({ sort: e.target.value as SortKey })}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900"
        >
          {SORTS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <button
          onClick={() => onChange({ order: f.order === "asc" ? "desc" : "asc" })}
          className="inline-flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 dark:border-slate-700"
          aria-label={f.order === "asc" ? "昇順（クリックで降順）" : "降順（クリックで昇順）"}
        >
          {f.order === "asc" ? <ArrowUpNarrowWide className="h-4 w-4" /> : <ArrowDownWideNarrow className="h-4 w-4" />}
          {f.order === "asc" ? "昇順" : "降順"}
        </button>
        {!isDefault && (
          <button
            onClick={() => {
              const { market, view, ...rest } = DEFAULT_FILTERS; // eslint-disable-line @typescript-eslint/no-unused-vars
              onChange(rest);
            }}
            className="ml-auto inline-flex items-center gap-1 text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            条件を既定に戻す
          </button>
        )}
      </div>
    </section>
  );
}

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <span className="inline-flex cursor-pointer select-none items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 shrink-0 rounded-full transition-colors ${
          checked ? "bg-amber-500" : "bg-slate-300 dark:bg-slate-700"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${
            checked ? "left-[18px]" : "left-0.5"
          }`}
        />
      </button>
      <span className="whitespace-nowrap" onClick={() => onChange(!checked)}>{label}</span>
    </span>
  );
}

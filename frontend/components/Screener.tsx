"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { LayoutGrid, Table2 } from "lucide-react";
import { clearChartCache, fetchScreen } from "@/lib/api";
import { filtersToQuery, parseFilters } from "@/lib/query";
import type { Filters, ScreenResponse } from "@/lib/types";
import FilterBar from "./FilterBar";
import Footer from "./Footer";
import Header from "./Header";
import StockCard from "./StockCard";
import StockTable from "./StockTable";
import { CardSkeletons, EmptyState, ErrorState, TableSkeleton } from "./States";

export default function Screener() {
  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();
  const filters = useMemo(() => parseFilters(new URLSearchParams(sp.toString())), [sp]);

  const [data, setData] = useState<ScreenResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  // 条件は URL に反映（共有・ブックマーク用）。履歴は増やさない。
  // URL の反映は非同期なので、続けて操作しても前の変更を失わないよう最新の条件を ref に持つ
  const latest = useRef(filters);
  useEffect(() => {
    latest.current = filters;
  }, [filters]);
  const update = useCallback(
    (patch: Partial<Filters>) => {
      const next = { ...latest.current, ...patch };
      latest.current = next;
      const q = filtersToQuery(next);
      router.replace(q ? `${pathname}?${q}` : pathname, { scroll: false });
    },
    [pathname, router],
  );

  useEffect(() => {
    abortRef.current?.abort();
    const ac = new AbortController();
    abortRef.current = ac;
    setLoading(true);
    setError(null);
    fetchScreen(filters, ac.signal)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        if (ac.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
        setLoading(false);
      });
    return () => ac.abort();
  }, [filters, reloadKey]);

  const onRefreshed = useCallback(() => {
    clearChartCache();
    setReloadKey((k) => k + 1);
  }, []);

  // 再取得中は前の一覧を薄く表示したまま（ちらつきを抑える）。初回だけスケルトン
  const firstLoad = loading && !data;

  return (
    <div className="flex min-h-screen flex-col">
      <Header
        runDate={data?.run_date ?? null}
        updatedAt={data?.updated_at ?? null}
        market={filters.market}
        onMarket={(m) => update({ market: m })}
        onRefreshed={onRefreshed}
      />
      <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-3 px-4 py-4">
        <FilterBar filters={filters} onChange={update} />

        <div className="flex items-center justify-between">
          <p className="text-sm" aria-live="polite">
            該当 <span className="tabular text-xl font-bold">{data ? data.count.toLocaleString() : "—"}</span> 銘柄
            {data && data.count > data.items.length && (
              <span className="ml-2 text-xs text-slate-500">（上位 {data.items.length} 件を表示）</span>
            )}
          </p>
          <div className="inline-flex rounded-md border border-slate-300 p-0.5 dark:border-slate-700" role="group" aria-label="表示形式">
            <ViewButton active={filters.view === "card"} onClick={() => update({ view: "card" })} label="カード">
              <LayoutGrid className="h-4 w-4" />
            </ViewButton>
            <ViewButton active={filters.view === "table"} onClick={() => update({ view: "table" })} label="テーブル">
              <Table2 className="h-4 w-4" />
            </ViewButton>
          </div>
        </div>

        {error ? (
          <ErrorState message={error} onRetry={() => setReloadKey((k) => k + 1)} />
        ) : firstLoad ? (
          filters.view === "card" ? <CardSkeletons /> : <TableSkeleton />
        ) : data && data.items.length === 0 ? (
          <EmptyState noData={!data.run_date} />
        ) : data ? (
          <div className={`transition-opacity ${loading ? "opacity-60" : ""}`}>
            {filters.view === "card" ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {data.items.map((it) => (
                  <StockCard key={it.code} item={it} runDate={data.run_date} />
                ))}
              </div>
            ) : (
              <StockTable items={data.items} />
            )}
          </div>
        ) : null}
      </main>
      <Footer />
    </div>
  );
}

function ViewButton({ active, onClick, label, children }: { active: boolean; onClick: () => void; label: string; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`inline-flex items-center gap-1 rounded px-2 py-1 text-xs ${
        active ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "text-slate-600 dark:text-slate-400"
      }`}
    >
      {children}
      {label}
    </button>
  );
}

"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useTheme } from "next-themes";
import { ArrowDownUp, Loader2, Moon, RefreshCw, Sun, TrendingUp } from "lucide-react";
import { fetchRefreshStatus, startRefresh } from "@/lib/api";
import { fmtMD, fmtMDHM } from "@/lib/format";
import { usePrefs } from "@/lib/prefs";
import type { MarketTab, RefreshStatus } from "@/lib/types";

const TABS: { value: MarketTab; label: string }[] = [
  { value: "all", label: "全市場" },
  { value: "prime", label: "プライム" },
  { value: "standard", label: "スタンダード" },
  { value: "growth", label: "グロース" },
];

const PHASE: Record<string, string> = { universe: "銘柄一覧", prices: "株価取得", screen: "指標計算" };

interface Props {
  runDate: string | null;
  updatedAt: string | null;
  market: MarketTab;
  onMarket: (m: MarketTab) => void;
  onRefreshed: () => void;
}

export default function Header({ runDate, updatedAt, market, onMarket, onRefreshed }: Props) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur dark:border-slate-800 dark:bg-[#0d1117]/90">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <TrendingUp className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
          <h1 className="truncate text-base font-bold sm:text-lg">
            <span aria-hidden>🚓 </span>タカネパトロール君
          </h1>
          <span className="hidden text-xs text-slate-500 sm:inline dark:text-slate-400">年初来高値 更新間近</span>
        </div>
        <UpdatedBadge runDate={runDate} updatedAt={updatedAt} />
        <div className="ml-auto flex items-center gap-2">
          <RefreshControl onRefreshed={onRefreshed} />
          <ColorToggle />
          <ThemeToggle />
        </div>
      </div>
      <nav className="mx-auto max-w-[1600px] overflow-x-auto px-4" aria-label="市場">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button
              key={t.value}
              onClick={() => onMarket(t.value)}
              aria-current={market === t.value ? "page" : undefined}
              className={`whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
                market === t.value
                  ? "border-amber-500 text-slate-900 dark:text-white"
                  : "border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </nav>
    </header>
  );
}

function UpdatedBadge({ runDate, updatedAt }: { runDate: string | null; updatedAt: string | null }) {
  if (!runDate) {
    return (
      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-500 dark:bg-slate-800 dark:text-slate-400">
        データ未取得
      </span>
    );
  }
  return (
    <span className="tabular rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
      {fmtMDHM(updatedAt)} 時点（{fmtMD(runDate)} 終値）
    </span>
  );
}

function RefreshControl({ onRefreshed }: { onRefreshed: () => void }) {
  const [st, setSt] = useState<RefreshStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wasRunning = useRef(false);

  const poll = useCallback(async () => {
    try {
      const s = await fetchRefreshStatus();
      setSt(s);
      if (s.running) {
        wasRunning.current = true;
        timer.current = setTimeout(poll, 1000);
      } else if (wasRunning.current) {
        wasRunning.current = false;
        if (s.status === "success") onRefreshed();
        else setErr(s.message ?? "更新に失敗しました");
      }
    } catch {
      timer.current = setTimeout(poll, 3000);
    }
  }, [onRefreshed]);

  useEffect(() => {
    poll(); // 開いた時点で実行中なら進捗を表示する
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [poll]);

  const onClick = async () => {
    setErr(null);
    try {
      await startRefresh(); // 実行中（409）でもそのまま進捗の表示に入る
      wasRunning.current = true;
      if (timer.current) clearTimeout(timer.current);
      poll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "更新を開始できません");
    }
  };

  const running = !!st?.running;
  const pct = st && st.total > 0 ? Math.round((st.processed / st.total) * 100) : 0;

  return (
    <div className="flex items-center gap-2">
      {running && (
        <div className="hidden w-44 sm:block" role="status" aria-live="polite">
          <div className="tabular mb-1 flex justify-between text-[11px] text-slate-500 dark:text-slate-400">
            <span>{PHASE[st!.phase ?? ""] ?? "準備中"}</span>
            <span>
              {st!.processed.toLocaleString()}/{st!.total.toLocaleString()}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
            <div className="h-full rounded-full bg-amber-500 transition-all" style={{ width: `${pct}%` }} />
          </div>
        </div>
      )}
      {err && !running && (
        <span className="hidden max-w-56 truncate text-xs text-red-600 md:inline dark:text-red-400" title={err}>
          {err}
        </span>
      )}
      <button
        onClick={onClick}
        disabled={running}
        className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800"
      >
        {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        <span>{running ? `${pct}%` : "更新"}</span>
      </button>
    </div>
  );
}

function ColorToggle() {
  const { colorMode, toggleColorMode } = usePrefs();
  return (
    <button
      onClick={toggleColorMode}
      title={colorMode === "jp" ? "上昇=赤／下落=青（クリックで反転）" : "上昇=青／下落=赤（クリックで戻す）"}
      aria-label="上昇・下落の色を反転"
      className="inline-flex h-8 items-center gap-1 rounded-md border border-slate-300 px-2 text-xs dark:border-slate-700"
    >
      <ArrowDownUp className="h-3.5 w-3.5" />
      <span className="font-bold text-up">▲</span>
      <span className="font-bold text-down">▼</span>
    </button>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const dark = mounted && resolvedTheme === "dark";
  return (
    <button
      onClick={() => setTheme(dark ? "light" : "dark")}
      aria-label={dark ? "ライトモードにする" : "ダークモードにする"}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-slate-300 dark:border-slate-700"
    >
      {mounted ? dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" /> : <span className="h-4 w-4" />}
    </button>
  );
}

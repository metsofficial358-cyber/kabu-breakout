import { MARKET_LABEL } from "@/lib/format";

const STYLE: Record<string, string> = {
  prime: "bg-indigo-50 text-indigo-700 ring-indigo-200 dark:bg-indigo-950/60 dark:text-indigo-300 dark:ring-indigo-800",
  standard: "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:ring-emerald-800",
  growth: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200 dark:bg-fuchsia-950/60 dark:text-fuchsia-300 dark:ring-fuchsia-800",
};
const OTHER = "bg-slate-100 text-slate-600 ring-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700";

export default function MarketBadge({ market }: { market: string | null }) {
  if (!market) return null;
  return (
    <span className={`inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset ${STYLE[market] ?? OTHER}`}>
      {MARKET_LABEL[market] ?? market}
    </span>
  );
}

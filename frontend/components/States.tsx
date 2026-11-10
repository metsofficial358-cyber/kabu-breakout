import { AlertTriangle, SearchX } from "lucide-react";

export function CardSkeletons({ n = 8 }: { n?: number }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4" aria-busy="true" aria-label="読み込み中">
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} className="animate-pulse rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900/60">
          <div className="h-4 w-2/3 rounded bg-slate-200 dark:bg-slate-800" />
          <div className="mt-3 h-7 w-1/3 rounded bg-slate-200 dark:bg-slate-800" />
          <div className="mt-3 h-12 rounded bg-slate-100 dark:bg-slate-800/60" />
          <div className="mt-3 h-[220px] rounded bg-slate-100 dark:bg-slate-800/60" />
        </div>
      ))}
    </div>
  );
}

export function TableSkeleton() {
  return (
    <div className="animate-pulse space-y-2 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900/60" aria-busy="true" aria-label="読み込み中">
      {Array.from({ length: 12 }).map((_, i) => (
        <div key={i} className="h-6 rounded bg-slate-100 dark:bg-slate-800/60" />
      ))}
    </div>
  );
}

export function EmptyState({ noData }: { noData: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 px-6 py-16 text-center dark:border-slate-700">
      <SearchX className="h-8 w-8 text-slate-400" aria-hidden />
      {noData ? (
        <>
          <p className="mt-3 font-medium">まだ結果がありません</p>
          <p className="mt-1 text-sm text-slate-500">右上の「更新」で株価を取得してください（初回は数分〜十数分かかります）。</p>
        </>
      ) : (
        <>
          <p className="mt-3 font-medium">条件に該当する銘柄はありません</p>
          <p className="mt-1 text-sm text-slate-500">高値までの距離を広げる、出来高やトレンドの条件を外す などを試してください。</p>
        </>
      )}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center rounded-lg border border-red-200 bg-red-50 px-6 py-12 text-center dark:border-red-900 dark:bg-red-950/30">
      <AlertTriangle className="h-8 w-8 text-red-500" aria-hidden />
      <p className="mt-3 font-medium text-red-800 dark:text-red-300">一覧を読み込めませんでした</p>
      <p className="mt-1 text-sm text-red-700/80 dark:text-red-300/80">{message}</p>
      <button onClick={onRetry} className="mt-4 rounded-md bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700">
        再読み込み
      </button>
    </div>
  );
}

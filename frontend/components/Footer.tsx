export default function Footer() {
  return (
    <footer className="mt-10 border-t border-slate-200 py-6 text-center text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
      <p>本ツールは情報提供のみを目的とし、投資助言ではありません。データの正確性は保証しません。</p>
      <p className="mt-1">株価データ：Yahoo Finance（yfinance 経由・遅延や欠損の可能性あり）／銘柄一覧：日本取引所グループ</p>
    </footer>
  );
}

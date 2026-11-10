// 表示用の丸め（API は丸めずに返す）

const intFmt = new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 0 });
const dec1Fmt = new Intl.NumberFormat("ja-JP", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "—";
  // 1,000円未満は小数第1位まで（例：165.2）、それ以上は整数
  return Math.abs(v) < 1000 && !Number.isInteger(v)
    ? new Intl.NumberFormat("ja-JP", { maximumFractionDigits: 1 }).format(v)
    : intFmt.format(v);
}

export function fmtPct(v: number | null | undefined, digits = 1, sign = false): string {
  if (v == null) return "—";
  const s = v.toFixed(digits);
  return `${sign && v > 0 ? "+" : ""}${s}%`;
}

export function fmtRatio(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toFixed(2)}倍`;
}

export function fmtVolume(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e8) return `${dec1Fmt.format(v / 1e8)}億株`;
  if (v >= 1e4) return `${dec1Fmt.format(v / 1e4)}万株`;
  return `${intFmt.format(v)}株`;
}

export function fmtYen(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 1e12) return `${dec1Fmt.format(v / 1e12)}兆円`;
  if (v >= 1e8) return `${dec1Fmt.format(v / 1e8)}億円`;
  if (v >= 1e4) return `${intFmt.format(v / 1e4)}万円`;
  return `${intFmt.format(v)}円`;
}

/** "2026-11-10" → "11/10" */
export function fmtMD(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [, m, d] = iso.slice(0, 10).split("-");
  return `${Number(m)}/${Number(d)}`;
}

/** "2026-11-10T18:05:12" → "11/10 18:05" */
export function fmtMDHM(iso: string | null | undefined): string {
  if (!iso) return "—";
  return `${fmtMD(iso)} ${iso.slice(11, 16)}`;
}

export const MARKET_LABEL: Record<string, string> = {
  prime: "プライム",
  standard: "スタンダード",
  growth: "グロース",
  etf: "ETF",
  reit: "REIT",
  other: "その他",
};

export const kabutanUrl = (code: string) => `https://kabutan.jp/stock/?code=${encodeURIComponent(code)}`;
export const yahooUrl = (code: string) => `https://finance.yahoo.co.jp/quote/${encodeURIComponent(code)}.T`;

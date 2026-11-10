"use client";
import { usePrefs } from "@/lib/prefs";

export default function Sparkline({ values, width = 120, height = 28 }: { values: number[]; width?: number; height?: number }) {
  const { colors } = usePrefs();
  if (values.length < 2) return <span className="text-slate-400">—</span>;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values
    .map((v, i) => `${((i / (values.length - 1)) * width).toFixed(1)},${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`)
    .join(" ");
  const up = values.at(-1)! >= values[0];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden className="block">
      <polyline points={pts} fill="none" stroke={up ? colors.up : colors.down} strokeWidth={1.4} strokeLinejoin="round" />
    </svg>
  );
}

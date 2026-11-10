"use client";
// 120営業日のローソク足＋出来高＋年初来高値の水平線。画面に入ったときに読み込む。
import { useEffect, useRef, useState } from "react";
import {
  CandlestickSeries,
  ColorType,
  CrosshairMode,
  HistogramSeries,
  LineStyle,
  createChart,
  type AutoscaleInfo,
  type IChartApi,
  type MouseEventParams,
  type Time,
} from "lightweight-charts";
import { fetchChart } from "@/lib/api";
import { fmtPrice, fmtVolume } from "@/lib/format";
import { usePrefs } from "@/lib/prefs";
import type { Bar, ChartResponse } from "@/lib/types";

interface Props {
  code: string;
  runDate: string | null;
  height?: number;
  days?: number;
}

export default function CandleChart({ code, runDate, height = 220, days = 120 }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const boxRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [data, setData] = useState<ChartResponse | null>(null);
  const [error, setError] = useState(false);
  const [hover, setHover] = useState<Bar | null>(null);
  const { colors } = usePrefs();

  // 遅延読み込み：画面に入る少し手前で取得を始める
  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (ents) => {
        if (ents.some((e) => e.isIntersecting)) {
          setVisible(true);
          io.disconnect();
        }
      },
      { rootMargin: "300px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    let alive = true;
    setError(false);
    fetchChart(code, runDate, days)
      .then((d) => alive && setData(d))
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, [visible, code, runDate, days]);

  useEffect(() => {
    const box = boxRef.current;
    if (!box || !data || data.bars.length === 0) return;
    const chart: IChartApi = createChart(box, {
      height,
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: colors.text,
        fontSize: 10,
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.08, bottom: 0.28 } },
      timeScale: { borderVisible: false, fixLeftEdge: true, fixRightEdge: true },
      crosshair: { mode: CrosshairMode.Magnet },
      handleScroll: false,
      handleScale: false,
      localization: { locale: "ja-JP", dateFormat: "yyyy/MM/dd" },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: colors.up,
      downColor: colors.down,
      borderUpColor: colors.up,
      borderDownColor: colors.down,
      wickUpColor: colors.up,
      wickDownColor: colors.down,
      priceLineVisible: false,
      lastValueVisible: false,
      // 年初来高値の線が常に見えるよう、縦軸の範囲に含める
      autoscaleInfoProvider: (orig: () => AutoscaleInfo | null) => {
        const r = orig();
        if (!r || !r.priceRange || data.ytd_high == null) return r;
        return { ...r, priceRange: { minValue: r.priceRange.minValue, maxValue: Math.max(r.priceRange.maxValue, data.ytd_high) } };
      },
    });
    const vols = chart.addSeries(HistogramSeries, {
      priceScaleId: "vol",
      priceFormat: { type: "volume" },
      priceLineVisible: false,
      lastValueVisible: false,
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.78, bottom: 0 }, visible: false });

    const valid = data.bars.filter((b) => b.open != null && b.high != null && b.low != null && b.close != null);
    // 価格の桁：1,000円未満の銘柄は小数1桁、それ以上は整数
    const small = valid.some((b) => b.close! < 1000);
    candles.applyOptions({ priceFormat: { type: "price", precision: small ? 1 : 0, minMove: small ? 0.1 : 1 } });
    candles.setData(
      valid.map((b) => ({ time: b.date as Time, open: b.open!, high: b.high!, low: b.low!, close: b.close! })),
    );
    vols.setData(
      valid.map((b) => ({
        time: b.date as Time,
        value: b.volume ?? 0,
        color: (b.close! >= b.open! ? colors.up : colors.down) + "66",
      })),
    );
    if (data.ytd_high != null) {
      candles.createPriceLine({
        price: data.ytd_high,
        color: colors.hl,
        lineWidth: 1,
        lineStyle: LineStyle.Dashed,
        axisLabelVisible: true,
        title: "年初来高値",
      });
    }
    chart.timeScale().fitContent();

    const byDate = new Map(valid.map((b) => [b.date, b]));
    const onMove = (p: MouseEventParams) => {
      setHover(p.time ? (byDate.get(p.time as string) ?? null) : null);
    };
    chart.subscribeCrosshairMove(onMove);
    return () => {
      chart.unsubscribeCrosshairMove(onMove);
      chart.remove();
    };
  }, [data, height, colors]);

  const last = data?.bars.at(-1) ?? null;
  const shown = hover ?? last;

  return (
    <div ref={wrapRef} className="relative" style={{ height: height + 20 }}>
      {shown && <Ohlc bar={shown} />}
      {!data && !error && <div className="mt-5 h-full animate-pulse rounded bg-slate-100 dark:bg-slate-800/60" />}
      {error && (
        <div className="flex h-full items-center justify-center text-xs text-slate-400">チャートを読み込めません</div>
      )}
      {data && data.bars.length === 0 && (
        <div className="flex h-full items-center justify-center text-xs text-slate-400">データがありません</div>
      )}
      <div ref={boxRef} className="absolute inset-x-0 bottom-0" style={{ height }} />
    </div>
  );
}

function Ohlc({ bar }: { bar: Bar }) {
  const up = (bar.close ?? 0) >= (bar.open ?? 0);
  return (
    <div className="tabular flex h-5 items-center gap-2 overflow-hidden whitespace-nowrap text-[10.5px] text-slate-500 dark:text-slate-400">
      <span className="font-medium text-slate-700 dark:text-slate-300">{bar.date.replaceAll("-", "/")}</span>
      <span>始 {fmtPrice(bar.open)}</span>
      <span>高 {fmtPrice(bar.high)}</span>
      <span>安 {fmtPrice(bar.low)}</span>
      <span className={up ? "text-up" : "text-down"}>終 {fmtPrice(bar.close)}</span>
      <span>出来高 {fmtVolume(bar.volume)}</span>
    </div>
  );
}

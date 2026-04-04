"use client";

import React, { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  IChartApi,
  ISeriesApi,
  CandlestickData,
  Time,
  CandlestickSeries,
} from "lightweight-charts";
import { getBrowserWebSocketUrl } from "../app/utils/runtimeUrls";

interface PositionLines {
  entry_price: number;
  stop_loss_price: number;
  take_profit_price: number;
  side: "long" | "short";
}

interface LightweightChartProps {
  symbol: string;
  position?: PositionLines | null;
  className?: string;
}

export default function LightweightChart({ symbol, position, className }: LightweightChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const hasDataRef = useRef(false);
  const emptyStateRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "#06060f" },
        textColor: "#64748b",
      },
      grid: {
        vertLines: { color: "#111124" },
        horzLines: { color: "#111124" },
      },
      width: el.clientWidth,
      height: el.clientHeight || 400,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#1a1a2e",
      },
      rightPriceScale: {
        borderColor: "#1a1a2e",
      },
      crosshair: {
        vertLine: { color: "#6366f1", labelBackgroundColor: "#6366f1" },
        horzLine: { color: "#6366f1", labelBackgroundColor: "#6366f1" },
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (el && chartRef.current) {
        chartRef.current.applyOptions({
          width: el.clientWidth,
          height: el.clientHeight || 400,
        });
      }
    });
    ro.observe(el);

    // Fetch initial candle data — no demo fallback
    const load = async () => {
      try {
        const clean = symbol.replace("/", "").toUpperCase();
        const res = await fetch(`/api/v1/market/klines/${clean}?limit=500`);
        if (res.ok) {
          const data: CandlestickData[] = await res.json();
          if (data && data.length > 0) {
            series.setData(data);
            chart.timeScale().fitContent();
            hasDataRef.current = true;
            if (emptyStateRef.current) emptyStateRef.current.style.display = "none";
          } else {
            showEmpty();
          }
        } else {
          showEmpty();
        }
      } catch {
        showEmpty();
      }
    };

    const showEmpty = () => {
      hasDataRef.current = false;
      if (emptyStateRef.current) emptyStateRef.current.style.display = "flex";
    };

    load();

    // WebSocket live updates
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(getBrowserWebSocketUrl(`/ws/market/${symbol.replace("/", "")}`));
      ws.onmessage = (event) => {
        try {
          const p = JSON.parse(event.data);
          if (p.type === "ticker" && seriesRef.current) {
            const d = p.data;
            const nowSec = Math.floor(Date.now() / 1000);
            const minuteBucket = Math.floor(nowSec / 60) * 60;
            seriesRef.current.update({
              time: minuteBucket as Time,
              open: d.open_price || d.last_price,
              high: d.high_price || d.last_price,
              low: d.low_price || d.last_price,
              close: d.last_price,
            });
            if (!hasDataRef.current) {
              hasDataRef.current = true;
              if (emptyStateRef.current) emptyStateRef.current.style.display = "none";
            }
          }
        } catch {}
      };
    } catch {}

    return () => {
      ro.disconnect();
      try { chart.remove(); } catch {}
      try { ws?.close(); } catch {}
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [symbol]);

  // Add/update price lines when position changes
  useEffect(() => {
    const s = seriesRef.current;
    if (!s) return;
    if (!position) return;
    try {
      s.createPriceLine({ price: position.entry_price, color: "#60a5fa", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "Entry" });
      s.createPriceLine({ price: position.stop_loss_price, color: "#ef4444", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "SL" });
      s.createPriceLine({ price: position.take_profit_price, color: "#10b981", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "TP" });
    } catch {}
  }, [position]);

  return (
    <div className={`relative w-full h-full ${className ?? ""}`} style={{ minHeight: 200 }}>
      <div ref={containerRef} className="w-full h-full" />

      {/* Empty state overlay */}
      <div
        ref={emptyStateRef}
        className="absolute inset-0 flex flex-col items-center justify-center text-zinc-600 font-mono text-sm pointer-events-none"
        style={{ display: "flex", background: "#06060f" }}
      >
        <svg className="w-10 h-10 mb-3 text-zinc-800" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M3 3v18h18M7 16l4-4 4 4 4-8" />
        </svg>
        <span className="text-zinc-700">Warte auf Kerzen-Daten...</span>
        <span className="text-zinc-800 text-xs mt-1">IngestionAgent muss laufen</span>
      </div>

      {/* Position price lines legend */}
      {position && (
        <div className="absolute top-2 right-2 flex flex-col gap-1 font-mono text-xs pointer-events-none">
          <div className="flex items-center gap-1.5 bg-zinc-950/80 px-2 py-0.5 rounded">
            <span className="w-3 h-px bg-blue-400 inline-block" />
            <span className="text-blue-400">Entry ${position.entry_price.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
          </div>
          <div className="flex items-center gap-1.5 bg-zinc-950/80 px-2 py-0.5 rounded">
            <span className="w-3 h-px bg-red-500 inline-block" />
            <span className="text-red-400">SL ${position.stop_loss_price.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
          </div>
          <div className="flex items-center gap-1.5 bg-zinc-950/80 px-2 py-0.5 rounded">
            <span className="w-3 h-px bg-emerald-500 inline-block" />
            <span className="text-emerald-400">TP ${position.take_profit_price.toLocaleString("en-US", { maximumFractionDigits: 0 })}</span>
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CrosshairMode, LineSeries } from 'lightweight-charts';
import { getBrowserWebSocketUrl } from "../app/utils/runtimeUrls";

/**
 * Lightweight BTC price line chart for the Dashboard overview.
 * Shows a simple line chart with gradient fill — NOT the full candlestick trading chart.
 */
export default function PriceLineChart({ symbol }: { symbol: string }) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: 'transparent' },
        textColor: '#475569',
        fontSize: 10,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#1a1a2e', style: 2 },
      },
      crosshair: {
        mode: CrosshairMode.Magnet,
        vertLine: { labelBackgroundColor: '#6366f1' },
        horzLine: { labelBackgroundColor: '#6366f1' },
      },
      timeScale: {
        borderVisible: false,
        timeVisible: true,
      },
      rightPriceScale: {
        borderVisible: false,
      },
      handleScroll: false,
      handleScale: false,
      width: chartContainerRef.current.clientWidth,
      height: 200,
    });

    const series = chart.addSeries(LineSeries, {
      color: '#6366f1',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, []);

  // WebSocket price feed — use ticker data to build a simple price line
  useEffect(() => {
    if (!seriesRef.current || !chartRef.current) return;

    const ws = new WebSocket(getBrowserWebSocketUrl(`/ws/market/${symbol}`));

    ws.onmessage = (event) => {
      try {
        if (!seriesRef.current || !chartRef.current) return;
        
        const payload = JSON.parse(event.data);
        if (payload.type === 'ticker' && payload.data) {
          const now = Math.floor(Date.now() / 1000);
          seriesRef.current.update({
            time: now as any,
            value: payload.data.last_price,
          });
        }
        // Also accept candle data and extract close price
        if (payload.type === 'candle' && payload.data) {
          const d = payload.data;
          seriesRef.current.update({
            time: (new Date(d.time).getTime() / 1000) as any,
            value: d.close,
          });
        }
      } catch {}
    };

    return () => {
      // Robuste Cleanup-Logik
      try {
        if (ws) {
          ws.close();
        }
      } catch (error) {
        console.warn("WebSocket close failed:", error);
      }
      
      try {
        if (chartRef.current) {
          chartRef.current.remove();
        }
      } catch (error) {
        console.warn("Chart removal failed (may be already disposed):", error);
      }
      
      // Setze Referenzen zurück
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [symbol]);

  return (
    <div className="w-full relative rounded-xl overflow-hidden">
      <div ref={chartContainerRef} className="w-full h-[200px]" />
    </div>
  );
}

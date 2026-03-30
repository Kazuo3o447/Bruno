"use client";

import React, { useEffect, useRef } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickData, Time, CandlestickSeries } from "lightweight-charts";

// Demo data generation function
function generateDemoData(): CandlestickData[] {
  const data: CandlestickData[] = [];
  let time = new Date();
  time.setDate(time.getDate() - 30);
  
  let price = 65000;
  
  for (let i = 0; i < 30 * 24; i++) {
    const open = price;
    const high = price * (1 + Math.random() * 0.02);
    const low = price * (1 - Math.random() * 0.02);
    const close = low + Math.random() * (high - low);
    
    data.push({
      time: Math.floor(time.getTime() / 1000) as Time,
      open,
      high,
      low,
      close,
    });
    
    price = close;
    time.setHours(time.getHours() + 1);
  }
  
  return data;
}

interface LightweightChartProps {
  symbol: string;
}

export default function LightweightChart({ symbol }: LightweightChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#06060f" },
        textColor: "#64748b",
      },
      grid: {
        vertLines: { color: "#1a1a2e" },
        horzLines: { color: "#1a1a2e" },
      },
      width: chartContainerRef.current.clientWidth,
      height: 300,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#1a1a2e",
      },
      rightPriceScale: {
        borderColor: "#1a1a2e",
      },
      crosshair: {
        mode: 0, // Normal
        vertLine: {
            color: "#6366f1",
            labelBackgroundColor: "#6366f1",
        },
        horzLine: {
            color: "#6366f1",
            labelBackgroundColor: "#6366f1",
        }
      }
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

    // Responsive
    const handleResize = () => {
      chart.applyOptions({ width: chartContainerRef.current!.clientWidth });
    };
    window.addEventListener("resize", handleResize);

    // Initial Data
    const loadInitialData = async () => {
      try {
        const cleanSymbol = symbol.replace("/", "").toUpperCase();
        const res = await fetch(`http://localhost:8001/api/v1/market/klines/${cleanSymbol}`);
        if (res.ok) {
          const data = await res.json();
          series.setData(data);
          chart.timeScale().fitContent();
        } else {
          // Load demo data if backend is not available
          const demoData = generateDemoData();
          series.setData(demoData);
          chart.timeScale().fitContent();
        }
      } catch (err) {
        console.error("Chart data fetch failed, using demo data:", err);
        // Load demo data if backend is not available
        const demoData = generateDemoData();
        series.setData(demoData);
        chart.timeScale().fitContent();
      }
    };
    loadInitialData();

    // WS Updates
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(`ws://localhost:8001/ws/market/${symbol.replace("/", "")}`);
      ws.onmessage = (event) => {
        try {
          const p = JSON.parse(event.data);
          if (p.type === "ticker") {
            const d = p.data;
            const nowSeconds = Math.floor(Date.now() / 1000);
            const currentMinute = Math.floor(nowSeconds / 60) * 60;
            
            series.update({
              time: currentMinute as Time,
              open: d.open_price || d.last_price,
              high: d.high_price || d.last_price,
              low: d.low_price || d.last_price,
              close: d.last_price
            });
          }
        } catch {}
      };
    } catch (err) {
      console.log("WebSocket not available, using demo data only");
    }

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      if (ws) {
        ws.close();
      }
    };
  }, [symbol]);

  return (
    <div className="w-full h-full relative">
      <div ref={chartContainerRef} className="w-full h-[300px]" />
    </div>
  );
}

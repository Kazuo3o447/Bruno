"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries, CandlestickData } from "lightweight-charts";

interface TradingChartProps {
  symbol?: string;
  data?: CandlestickData[];
}

export default function TradingChart({ symbol = "BTCUSDT", data: initialData }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Chart erstellen
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#1a1a2e" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#2d2d44" },
        horzLines: { color: "#2d2d44" },
      },
      crosshair: {
        mode: 1,
      },
      rightPriceScale: {
        borderColor: "#2d2d44",
      },
      timeScale: {
        borderColor: "#2d2d44",
        timeVisible: true,
      },
    });

    chartRef.current = chart;

    // Candlestick Serie hinzufügen - Lightweight Charts v4 API
    const candlestickSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    seriesRef.current = candlestickSeries;

    // Beispiel-Daten oder übergebene Daten verwenden
    if (initialData && initialData.length > 0) {
      candlestickSeries.setData(initialData);
      const lastCandle = initialData[initialData.length - 1];
      setCurrentPrice(lastCandle.close);
    } else {
      // Demo-Daten generieren
      const demoData = generateDemoData();
      candlestickSeries.setData(demoData);
      const lastCandle = demoData[demoData.length - 1];
      setCurrentPrice(lastCandle.close);
    }

    // Chart auf Fenstergröße anpassen
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };

    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [initialData]);

  // Neue Daten hinzufügen (für WebSocket Updates)
  useEffect(() => {
    if (initialData && initialData.length > 0 && seriesRef.current) {
      const lastCandle = initialData[initialData.length - 1];
      seriesRef.current.update(lastCandle);
      setCurrentPrice(lastCandle.close);
    }
  }, [initialData]);

  return (
    <div className="bg-[#1a1a2e] rounded-lg p-4 h-full">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{symbol}</h3>
          <p className="text-sm text-gray-400">Live Chart</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-white">
            {currentPrice ? `$${currentPrice.toLocaleString()}` : "Loading..."}
          </p>
          <p className="text-sm text-green-400">+2.34%</p>
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full h-[400px]" />
    </div>
  );
}

// Demo-Daten generieren
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
      time: time.getTime() / 1000,
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

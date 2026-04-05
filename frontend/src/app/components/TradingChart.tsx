"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, CandlestickSeries, CandlestickData, UTCTimestamp } from "lightweight-charts";

interface TradingChartProps {
  symbol?: string;
  data?: CandlestickData[];
  height?: number;
  compact?: boolean;
}

// Demo-Daten Generator
function generateDemoData(): CandlestickData[] {
  const now = Date.now() / 1000;
  const basePrice = 65000;
  const data: CandlestickData[] = [];
  
  for (let i = 20; i >= 0; i--) {
    const time = (now - i * 3600) as UTCTimestamp;
    const volatility = 0.02;
    const trend = 0.001;
    
    const open = i === 20 ? basePrice : data[data.length - 1].close;
    const change = (Math.random() - 0.5 + trend) * volatility * open;
    const close = open + change;
    const high = Math.max(open, close) + Math.random() * volatility * open * 0.5;
    const low = Math.min(open, close) - Math.random() * volatility * open * 0.5;
    
    data.push({ time, open, high, low, close });
  }
  
  return data;
}

export default function TradingChart({ symbol = "BTCUSDT", data: initialData, height = 400, compact = false }: TradingChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number>(0);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    let chart: IChartApi | null = null;
    let candlestickSeries: ISeriesApi<"Candlestick"> | null = null;
    let isDisposed = false;

    try {
      // Chart erstellen
      chart = createChart(chartContainerRef.current, {
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
      candlestickSeries = chart.addSeries(CandlestickSeries, {
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderUpColor: "#22c55e",
        borderDownColor: "#ef4444",
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
      });

      seriesRef.current = candlestickSeries;

      // Beispiel-Daten oder übergebene Daten verwenden
      const dataToUse = initialData && initialData.length > 0 ? initialData : generateDemoData();
      
      if (candlestickSeries && !isDisposed) {
        candlestickSeries.setData(dataToUse);
        const lastCandle = dataToUse[dataToUse.length - 1];
        const firstCandle = dataToUse[0];
        setCurrentPrice(lastCandle.close);
        const change = ((lastCandle.close - firstCandle.open) / firstCandle.open) * 100;
        setPriceChange(change);
      }

      // Chart auf Fenstergröße anpassen
      const handleResize = () => {
        if (!isDisposed && chartContainerRef.current && chart && chartContainerRef.current.isConnected) {
          try {
            chart.applyOptions({
              width: chartContainerRef.current.clientWidth,
              height: chartContainerRef.current.clientHeight,
            });
          } catch (error) {
            console.warn("Chart resize failed - chart may be disposed:", error);
          }
        }
      };

      window.addEventListener("resize", handleResize);
      handleResize();

      // Cleanup function
      return () => {
        isDisposed = true;
        window.removeEventListener("resize", handleResize);
        
        // Sichere Entfernung des Charts
        setTimeout(() => {
          if (chart) {
            try {
              chart.remove();
            } catch (error) {
              console.warn("Chart removal failed:", error);
            } finally {
              chartRef.current = null;
              seriesRef.current = null;
            }
          }
        }, 100); // Kleine Verzögerung, um Race Conditions zu vermeiden
      };
    } catch (error) {
      console.error("Chart initialization failed:", error);
      return () => {
        isDisposed = true;
        chartRef.current = null;
        seriesRef.current = null;
      };
    }
  }, [initialData]);

  // Neue Daten hinzufügen (für WebSocket Updates)
  useEffect(() => {
    if (initialData && initialData.length > 0 && seriesRef.current && chartRef.current) {
      try {
        const lastCandle = initialData[initialData.length - 1];
        const firstCandle = initialData[0];
        seriesRef.current.update(lastCandle);
        setCurrentPrice(lastCandle.close);
        const change = ((lastCandle.close - firstCandle.open) / firstCandle.open) * 100;
        setPriceChange(change);
      } catch (error) {
        console.warn("Chart update failed - chart may be disposed:", error);
      }
    }
  }, [initialData]);

  return (
    <div className="bg-[#1a1a2e] rounded-lg p-4 h-full">
      <div className={`flex justify-between items-center ${compact ? "mb-2" : "mb-4"}`}>
        <div>
          <h3 className={`${compact ? "text-base" : "text-lg"} font-semibold text-white`}>{symbol}</h3>
          <p className={`${compact ? "text-xs" : "text-sm"} text-gray-400`}>Live Chart</p>
        </div>
        <div className="text-right">
          <p className={`${compact ? "text-lg" : "text-2xl"} font-bold text-white`}>
            {currentPrice ? `$${currentPrice.toLocaleString()}` : "Loading..."}
          </p>
          <p className={`${compact ? "text-xs" : "text-sm"} ${priceChange >= 0 ? "text-green-400" : "text-red-400"}`}>
            {priceChange >= 0 ? "+" : ""}{priceChange.toFixed(2)}%
          </p>
        </div>
      </div>
      <div ref={chartContainerRef} className="w-full" style={{ height }} />
    </div>
  );
}

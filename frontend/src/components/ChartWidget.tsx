"use client";

import React, { useEffect, useRef } from 'react';
import { createChart, ColorType, CrosshairMode, CandlestickSeries } from 'lightweight-charts';

export default function ChartWidget({ symbol }: { symbol: string }) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const markersRef = useRef<any[]>([]);

  // Chart init
  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#06060f' },
        textColor: '#64748b',
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#1a1a2e' },
        horzLines: { color: '#1a1a2e' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { labelBackgroundColor: '#6366f1' },
        horzLine: { labelBackgroundColor: '#6366f1' },
      },
      timeScale: {
        borderColor: '#1a1a2e',
        timeVisible: true,
      },
      rightPriceScale: {
        borderColor: '#1a1a2e',
      },
      width: chartContainerRef.current.clientWidth,
      height: 420,
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#22c55e',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#22c55e',
      wickDownColor: '#ef4444',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // WebSocket data feed
  useEffect(() => {
    if (!seriesRef.current) return;

    // Load historical candle data
    const loadHistoricalData = async () => {
      try {
        const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=1m&limit=100`);
        if (!res.ok) return;
        const klines = await res.json();
        
        const candles = klines.map((k: any[]) => ({
          time: parseInt(k[0]) / 1000,
          open: parseFloat(k[1]),
          high: parseFloat(k[2]),
          low: parseFloat(k[3]),
          close: parseFloat(k[4]),
        }));
        
        if (seriesRef.current) {
          seriesRef.current.setData(candles);
        }
      } catch (e) {
        console.error("Fehler beim Laden der historischen Daten:", e);
      }
    };

    loadHistoricalData();

    // Trade-Historie abrufen für Marker
    const fetchTradeMarkers = async () => {
      try {
        const res = await fetch(`http://localhost:8000/api/v1/trades/history?symbol=${symbol}`);
        if (!res.ok) return;
        const trades = await res.json();
        
        const markers = trades.map((t: any) => ({
          time: new Date(t.timestamp).getTime() / 1000,
          position: t.action === 'buy' ? 'belowBar' : 'aboveBar',
          color: t.action === 'buy' ? '#22c55e' : '#ef4444',
          shape: t.action === 'buy' ? 'arrowUp' : 'arrowDown',
          text: t.action.toUpperCase(),
        }));
        
        markersRef.current = markers;
        if (seriesRef.current) {
          seriesRef.current.setMarkers(markers);
        }
      } catch (e) {
        console.error("Fehler beim Laden der Trade-Marker:", e);
      }
    };

    fetchTradeMarkers();

    const ws = new WebSocket(`ws://localhost:8000/ws/market/${symbol}`);

    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'candle' && payload.data) {
          const d = payload.data;
          seriesRef.current.update({
            time: (new Date(d.time).getTime() / 1000) as any,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
          });
        }
      } catch {}
    };

    return () => ws.close();
  }, [symbol]);

  return (
    <div className="w-full relative rounded-2xl overflow-hidden border border-[#1a1a2e] bg-[#06060f]">
      {/* Overlay Badge */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2.5">
        <span className="text-white font-bold text-sm bg-[#0c0c18]/90 px-3 py-1.5 rounded-lg backdrop-blur-sm border border-[#1a1a2e]">
          {symbol}
        </span>
        <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-1 rounded-md uppercase tracking-wider">
          Live
        </span>
      </div>
      <div ref={chartContainerRef} className="w-full h-[420px]" />
    </div>
  );
}

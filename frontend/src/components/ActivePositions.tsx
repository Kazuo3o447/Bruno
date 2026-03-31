"use client";

import React, { useState, useEffect } from "react";
import { TrendingUp, TrendingDown, Target, Shield, ArrowRight } from "lucide-react";

interface Position {
  id: string;
  symbol: string;
  side: "long" | "short";
  entry_price: number;
  quantity: number;
  stop_loss_price: number | null;
  take_profit_price: number | null;
  current_price?: number;
  current_pnl_pct?: number;
  current_pnl_eur?: number;
  created_at: string;
}

export default function ActivePositions() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchPositions = async () => {
    try {
      const res = await fetch("/api/v1/positions/open");
      if (res.ok) {
        const data = await res.json();
        setPositions(data.positions || []);
      }
    } catch (err) {
      console.error("Positions fetch failed:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    const iv = setInterval(fetchPositions, 5000);
    return () => clearInterval(iv);
  }, []);

  if (loading && positions.length === 0) {
    return (
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-8 flex flex-col items-center justify-center gap-3 text-slate-600 italic text-sm">
        <div className="w-5 h-5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        Synchronisiere Positionen...
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-8 text-center">
        <p className="text-slate-500 text-sm italic mb-2">Keine aktiven Positionen.</p>
        <p className="text-[10px] text-slate-700 uppercase tracking-widest font-bold">Bruno Scannt den Markt...</p>
      </div>
    );
  }

  return (
    <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl overflow-hidden shadow-lg border-l-4 border-l-indigo-500">
      <div className="px-6 py-4 border-b border-[#1a1a2e] flex items-center justify-between">
        <h3 className="text-[11px] text-slate-500 font-bold uppercase tracking-wider flex items-center gap-2">
          <Target className="w-3.5 h-3.5 text-indigo-400" /> Active Institutional Positions
        </h3>
        <span className="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded-full font-bold uppercase">
          {positions.length} Live
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-[#0e0e1e]/50 text-[10px] text-slate-500 uppercase font-bold tracking-wider">
              <th className="px-6 py-3">Symbol</th>
              <th className="px-6 py-3">Side</th>
              <th className="px-6 py-3 text-right">Entry</th>
              <th className="px-6 py-3 text-right">Quantity</th>
              <th className="px-6 py-3 text-right">SL / TP</th>
              <th className="px-6 py-3 text-right">Current PnL</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1a1a2e]/50">
            {positions.map((pos) => {
              const pnl = pos.current_pnl_pct || 0;
              const isWin = pnl >= 0;
              return (
                <tr key={pos.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex flex-col">
                      <span className="text-sm font-bold text-white font-mono">{pos.symbol}</span>
                      <span className="text-[10px] text-slate-600 font-mono">ID: {pos.id.slice(0, 8)}...</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${pos.side === 'long' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'}`}>
                      {pos.side}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-xs font-mono text-slate-300">${pos.entry_price.toLocaleString()}</span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <span className="text-xs font-mono text-slate-300">{pos.quantity}</span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex flex-col items-end gap-1">
                      <div className="flex items-center gap-1.5 text-[10px] text-red-400 font-medium font-mono">
                        <Shield className="w-2.5 h-2.5" /> ${pos.stop_loss_price?.toLocaleString() || '—'}
                      </div>
                      <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-medium font-mono">
                        <Target className="w-2.5 h-2.5" /> ${pos.take_profit_price?.toLocaleString() || '—'}
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className={`flex flex-col items-end ${isWin ? 'text-emerald-400' : 'text-red-400'}`}>
                      <div className="flex items-center gap-1 text-sm font-bold font-mono">
                        {isWin ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
                        {isWin ? '+' : ''}{(pnl * 100).toFixed(2)}%
                      </div>
                      <div className="text-[10px] opacity-70 font-mono">
                        {isWin ? '+' : ''}${pos.current_pnl_eur?.toFixed(2) || '0.00'} EUR
                      </div>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

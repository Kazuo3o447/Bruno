"use client";

import { useState } from "react";
import { 
  Play, 
  Calendar, 
  TrendingUp, 
  AlertTriangle, 
  CheckCircle, 
  BarChart3, 
  Clock, 
  ArrowRight,
  RefreshCw
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from "recharts";

interface BacktestResult {
  total_trades: number;
  win_rate_pct: number;
  profit_factor: number;
  total_pnl_eur: number;
  max_drawdown_pct: number;
  avg_pnl_pct: number;
  trades: Array<{
    entry_time: string;
    exit_time: string;
    side: string;
    pnl_pct: number;
    exit_reason: string;
  }>;
}

export default function BacktestPage() {
  const [start, setStart] = useState("2026-03-01");
  const [end, setEnd] = useState("2026-04-01");
  const [capital, setCapital] = useState(10000);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/v1/backtest/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          start,
          end,
          initial_capital: capital
        })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || "Backtest failed");
      }

      const data = await response.json();
      setResult(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const chartData = result?.trades.map((t, i) => {
    const prevPnl = result.trades.slice(0, i).reduce((sum, curr) => sum + curr.pnl_pct, 0);
    return {
      name: i + 1,
      pnl: prevPnl + t.pnl_pct,
      time: new Date(t.exit_time).toLocaleDateString()
    };
  }) || [];

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6 space-y-6">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
            Walk-Forward Pipeline Backtest
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Validiert die echte CompositeScorer-Pipeline gegen historische Daten
          </p>
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 items-end">
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Calendar className="w-3 h-3" /> Start Datum
            </label>
            <input 
              type="date" 
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="w-full bg-[#080810] border border-slate-800 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <Calendar className="w-3 h-3" /> End Datum
            </label>
            <input 
              type="date" 
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="w-full bg-[#080810] border border-slate-800 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div className="space-y-2">
            <label className="text-xs font-medium text-slate-500 uppercase tracking-wider flex items-center gap-2">
              <TrendingUp className="w-3 h-3" /> Startkapital (EUR)
            </label>
            <input 
              type="number" 
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              className="w-full bg-[#080810] border border-slate-800 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <button 
            onClick={runBacktest}
            disabled={loading}
            className={`flex items-center justify-center gap-2 px-6 py-2.5 rounded-lg font-bold text-sm transition-all ${
              loading ? "bg-slate-800 text-slate-500" : "bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20"
            }`}
          >
            {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {loading ? "Simuliere..." : "Backtest starten"}
          </button>
        </div>
        {error && (
          <div className="mt-4 p-3 bg-red-900/20 border border-red-800 rounded-lg flex items-center gap-3 text-red-400 text-sm">
            <AlertTriangle className="w-4 h-4" /> {error}
          </div>
        )}
      </div>

      {result && (
        <>
          {/* Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="bg-[#0c0c18] border border-[#1a1a2e] p-4 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Total P&L</div>
              <div className={`text-xl font-bold ${result.total_pnl_eur >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                €{result.total_pnl_eur.toLocaleString()}
              </div>
            </div>
            <div className="bg-[#0c0c18] border border-[#1a1a2e] p-4 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Win Rate</div>
              <div className="text-xl font-bold text-indigo-400">{result.win_rate_pct}%</div>
            </div>
            <div className="bg-[#0c0c18] border border-[#1a1a2e] p-4 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Profit Factor</div>
              <div className="text-xl font-bold text-emerald-400">{result.profit_factor}</div>
            </div>
            <div className="bg-[#0c0c18] border border-[#1a1a2e] p-4 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Trades</div>
              <div className="text-xl font-bold text-slate-300">{result.total_trades}</div>
            </div>
            <div className="bg-[#0c0c18] border border-[#1a1a2e] p-4 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Max DD</div>
              <div className="text-xl font-bold text-red-400">{result.max_drawdown_pct}%</div>
            </div>
            <div className="bg-[#0c0c18] border border-[#1a1a2e] p-4 rounded-xl">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Avg Trade</div>
              <div className={`text-xl font-bold ${result.avg_pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {result.avg_pnl_pct}%
              </div>
            </div>
          </div>

          {/* Cumulative Chart */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-6">
            <h3 className="text-sm font-medium text-slate-300 mb-6 flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-indigo-400" />
              Kumulative P&L Kurve (%)
            </h3>
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                  <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 10 }} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
                  <Tooltip 
                    contentStyle={{ background: "#0c0c18", border: "1px solid #1a1a2e", borderRadius: "8px" }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Area type="monotone" dataKey="pnl" stroke="#6366f1" fillOpacity={1} fill="url(#colorPnl)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Trade List */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl overflow-hidden">
            <div className="px-6 py-4 bg-[#080810] border-b border-[#1a1a2e]">
              <h3 className="text-sm font-medium text-slate-300">Detaillierte Trade Historie</h3>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-[#080810] text-[10px] uppercase text-slate-500 tracking-wider">
                  <tr>
                    <th className="px-6 py-3 font-bold">Zeitpunkt</th>
                    <th className="px-6 py-3 font-bold">Richtung</th>
                    <th className="px-6 py-3 font-bold">P&L (%)</th>
                    <th className="px-6 py-3 font-bold">Exit Grund</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1a1a2e]">
                  {result.trades.map((trade, idx) => (
                    <tr key={idx} className="hover:bg-indigo-500/5 transition-colors">
                      <td className="px-6 py-4 text-xs font-mono text-slate-400">
                        {new Date(trade.exit_time).toLocaleString()}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          trade.side === "long" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                        }`}>
                          {trade.side.toUpperCase()}
                        </span>
                      </td>
                      <td className={`px-6 py-4 text-xs font-bold font-mono ${
                        trade.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"
                      }`}>
                        {trade.pnl_pct > 0 ? "+" : ""}{trade.pnl_pct.toFixed(2)}%
                      </td>
                      <td className="px-6 py-4 text-xs text-slate-500 capitalize">
                        {trade.exit_reason.replace("_", " ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Institutional Note */}
      <div className="p-4 bg-indigo-950/20 border border-indigo-800 rounded-xl flex gap-4">
        <CheckCircle className="w-5 h-5 text-indigo-400 shrink-0" />
        <div className="space-y-1">
          <h4 className="text-xs font-bold text-indigo-300 uppercase tracking-wider">Pipeline-Validierungs Hinweis</h4>
          <p className="text-xs text-slate-400 leading-relaxed">
            Dieser Backtest führt jeden einzelnen Evaluierungs-Schritt der echten Live-Pipeline durch. 
            Es wird ein isolierter Mock-Redis verwendet, um Seiteneffekte zu vermeiden. 
            Gebühren von 4bps (Taker) und 1bps (Maker) sowie Intrabar-Pessimismus sind in der Simulation berücksichtigt.
          </p>
        </div>
      </div>
    </div>
  );
}

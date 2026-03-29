"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import {
  TrendingUp, TrendingDown, Activity, ShieldAlert, Cpu,
  Database, Zap, BarChart3
} from "lucide-react";
import { 
  ResponsiveContainer, 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip 
} from "recharts";

const ChartWidget = dynamic(() => import("../../components/ChartWidget"), { ssr: false });

type Period = "24h" | "1w" | "6m" | "1y" | "ytd";

// Performance Data Types
type PerformanceData = {
  total_pnl_eur: number;
  total_trades: number;
  win_rate_pct: number;
  winning_trades: number;
  losing_trades: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  cumulative_chart_data: Array<{date: string; cumulative_return_pct: number}>;
};

// Mock performance data
const MOCK_PERFORMANCE: Record<Period, PerformanceData> = {
  "24h": {
    total_pnl_eur: 125.50,
    total_trades: 3,
    win_rate_pct: 66.67,
    winning_trades: 2,
    losing_trades: 1,
    best_trade_pct: 2.1,
    worst_trade_pct: -0.5,
    cumulative_chart_data: [
      { date: "2026-03-28", cumulative_return_pct: 0 },
      { date: "2026-03-29", cumulative_return_pct: 0.85 }
    ]
  },
  "1w": {
    total_pnl_eur: 485.20,
    total_trades: 12,
    win_rate_pct: 66.67,
    winning_trades: 8,
    losing_trades: 4,
    best_trade_pct: 3.2,
    worst_trade_pct: -1.1,
    cumulative_chart_data: [
      { date: "2026-03-22", cumulative_return_pct: 0 },
      { date: "2026-03-23", cumulative_return_pct: 0.45 },
      { date: "2026-03-24", cumulative_return_pct: 1.12 },
      { date: "2026-03-25", cumulative_return_pct: 0.85 },
      { date: "2026-03-26", cumulative_return_pct: 1.55 },
      { date: "2026-03-27", cumulative_return_pct: 2.10 },
      { date: "2026-03-28", cumulative_return_pct: 1.95 },
      { date: "2026-03-29", cumulative_return_pct: 2.42 }
    ]
  },
  "6m": {
    total_pnl_eur: 3250.80,
    total_trades: 145,
    win_rate_pct: 61.38,
    winning_trades: 89,
    losing_trades: 56,
    best_trade_pct: 5.8,
    worst_trade_pct: -2.5,
    cumulative_chart_data: Array.from({ length: 26 }, (_, i) => ({
      date: `2026-01-${String((i * 7) % 30 + 1).padStart(2, '0')}`,
      cumulative_return_pct: Math.sin(i * 0.3) * 2 + i * 0.15
    }))
  },
  "1y": {
    total_pnl_eur: 6850.40,
    total_trades: 312,
    win_rate_pct: 60.58,
    winning_trades: 189,
    losing_trades: 123,
    best_trade_pct: 8.2,
    worst_trade_pct: -3.1,
    cumulative_chart_data: Array.from({ length: 52 }, (_, i) => ({
      date: `Week ${i + 1}`,
      cumulative_return_pct: Math.sin(i * 0.15) * 3 + i * 0.25
    }))
  },
  "ytd": {
    total_pnl_eur: 2150.60,
    total_trades: 89,
    win_rate_pct: 60.67,
    winning_trades: 54,
    losing_trades: 35,
    best_trade_pct: 4.5,
    worst_trade_pct: -1.8,
    cumulative_chart_data: Array.from({ length: 12 }, (_, i) => ({
      date: `2026-${String(i + 1).padStart(2, '0')}-01`,
      cumulative_return_pct: Math.sin(i * 0.5) * 1.5 + i * 0.4
    }))
  }
};

// Client-side time component to fix hydration error
function TimeDisplay({ timestamp }: { timestamp: string }) {
  const [time, setTime] = useState("");
  const [mounted, setMounted] = useState(false);
  
  useEffect(() => {
    setMounted(true);
    setTime(new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
  }, [timestamp]);
  
  if (!mounted) {
    return <span>--:--:--</span>;
  }
  
  return <span suppressHydrationWarning>{time}</span>;
}

// Horizontal Performance Widget
function PerformanceWidgetHorizontal({ 
  performance, 
  selectedPeriod, 
  setSelectedPeriod, 
  isPaperTrading 
}: { 
  performance: PerformanceData;
  selectedPeriod: Period;
  setSelectedPeriod: (p: Period) => void;
  isPaperTrading: boolean;
}) {
  const periods: { key: Period; label: string }[] = [
    { key: "24h", label: "24h" },
    { key: "1w", label: "1W" },
    { key: "6m", label: "6M" },
    { key: "1y", label: "1Y" },
    { key: "ytd", label: "YTD" },
  ];

  return (
    <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
      {/* Header Row */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          <TrendingUp className="w-5 h-5 text-emerald-400" />
          <h3 className="text-sm text-white font-bold">Simulated Performance</h3>
          <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded ${
            isPaperTrading ? "bg-amber-500/20 text-amber-400" : "bg-emerald-500/20 text-emerald-400"
          }`}>
            {isPaperTrading ? "Paper" : "Real"}
          </span>
        </div>
        
        {/* Period Selector */}
        <div className="flex gap-1">
          {periods.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setSelectedPeriod(key)}
              className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all ${
                selectedPeriod === key
                  ? "bg-emerald-500 text-white"
                  : "bg-[#1a1a2e] text-slate-400 hover:text-white"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
        {/* Main PnL - Takes 2 columns on large screens */}
        <div className="col-span-2 flex flex-col justify-center">
          <div className={`text-4xl font-black ${
            performance.total_pnl_eur >= 0 ? "text-emerald-400" : "text-rose-400"
          }`}>
            {performance.total_pnl_eur >= 0 ? "+" : ""}
            {performance.total_pnl_eur.toFixed(2)} €
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {performance.total_trades} Trades • {performance.win_rate_pct}% Win
          </div>
        </div>

        {/* Stats */}
        <div className="bg-[#06060f] rounded-lg p-3 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Wins</div>
          <div className="text-lg font-bold text-emerald-400">{performance.winning_trades}</div>
        </div>
        <div className="bg-[#06060f] rounded-lg p-3 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Losses</div>
          <div className="text-lg font-bold text-rose-400">{performance.losing_trades}</div>
        </div>
        <div className="bg-[#06060f] rounded-lg p-3 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Best</div>
          <div className="text-lg font-bold text-emerald-400">+{performance.best_trade_pct}%</div>
        </div>
        <div className="bg-[#06060f] rounded-lg p-3 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Worst</div>
          <div className="text-lg font-bold text-rose-400">{performance.worst_trade_pct}%</div>
        </div>
      </div>

      {/* Chart - Full Width */}
      <div className="h-[140px] w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={performance.cumulative_chart_data}>
            <defs>
              <linearGradient id={`colorReturn-${selectedPeriod}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" vertical={false} />
            <XAxis 
              dataKey="date" 
              stroke="#475569" 
              fontSize={10}
              tickFormatter={(value) => {
                if (selectedPeriod === "1y") return value;
                const date = new Date(value);
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
            />
            <YAxis stroke="#475569" fontSize={10} unit="%" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: "#0c0c18", 
                borderColor: "#1a1a2e", 
                borderRadius: "6px",
                fontSize: "11px"
              }}
              formatter={(value: number) => [`${value.toFixed(2)}%`, "Return"]}
            />
            <Area 
              type="monotone" 
              dataKey="cumulative_return_pct" 
              stroke="#10b981" 
              strokeWidth={2}
              fillOpacity={1} 
              fill={`url(#colorReturn-${selectedPeriod})`} 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function MetricCard({ title, value, subValue, trend, icon }: {
  title: string; value: string; subValue: string; trend: string; icon: React.ReactNode;
}) {
  return (
    <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5 relative overflow-hidden group hover:border-[#2d2b5e] transition-colors">
      <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/[0.02] to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
      <div className="flex justify-between items-start mb-3 relative z-10">
        <h3 className="text-xs text-slate-500 font-medium">{title}</h3>
        <div className="p-2 bg-[#06060f] rounded-lg border border-[#1a1a2e]">{icon}</div>
      </div>
      <div className="relative z-10">
        <div className="text-xl font-bold text-white mb-1 font-mono">{value}</div>
        <div className={`text-xs flex items-center gap-1 font-medium ${
          trend === "up" ? "text-emerald-400" : trend === "down" ? "text-red-400" : "text-slate-500"
        }`}>
          {trend === "up" && <TrendingUp className="w-3 h-3" />}
          {trend === "down" && <TrendingDown className="w-3 h-3" />}
          {subValue}
        </div>
      </div>
    </div>
  );
}

function StreamItem({ agent, action, text, time, color }: {
  agent: string; action: string; text: string; time: React.ReactNode; color: string;
}) {
  return (
    <div className={`pl-3 pr-2 py-2.5 border-l-2 ${color} bg-[#06060f] rounded-r-xl text-sm`}>
      <div className="flex justify-between items-center mb-1">
        <span className="font-bold text-[11px] uppercase tracking-wider">
          {agent} <span className="text-slate-600 font-normal">| {action}</span>
        </span>
        <span className="text-[10px] text-slate-600">{time}</span>
      </div>
      <p className="text-slate-400 text-xs leading-relaxed">{text}</p>
    </div>
  );
}

function PerformanceWidget({ 
  performance, 
  selectedPeriod, 
  setSelectedPeriod, 
  isPaperTrading 
}: { 
  performance: PerformanceData;
  selectedPeriod: Period;
  setSelectedPeriod: (p: Period) => void;
  isPaperTrading: boolean;
}) {
  const periods: { key: Period; label: string }[] = [
    { key: "24h", label: "24h" },
    { key: "1w", label: "1W" },
    { key: "6m", label: "6M" },
    { key: "1y", label: "1Y" },
    { key: "ytd", label: "YTD" },
  ];

  return (
    <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm text-white font-bold flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-emerald-400" />
          Performance
        </h3>
        <span className={`text-[10px] font-bold uppercase px-2 py-1 rounded ${
          isPaperTrading ? "bg-amber-500/20 text-amber-400" : "bg-emerald-500/20 text-emerald-400"
        }`}>
          {isPaperTrading ? "Paper Trading" : "Real Trading"}
        </span>
      </div>

      {/* Period Selector */}
      <div className="flex gap-1 mb-4">
        {periods.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSelectedPeriod(key)}
            className={`flex-1 px-2 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-all ${
              selectedPeriod === key
                ? "bg-emerald-500 text-white"
                : "bg-[#1a1a2e] text-slate-400 hover:text-white"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Main PnL */}
      <div className="text-center py-3 mb-4">
        <div className={`text-4xl font-black ${
          performance.total_pnl_eur >= 0 ? "text-emerald-400" : "text-rose-400"
        }`}>
          {performance.total_pnl_eur >= 0 ? "+" : ""}
          {performance.total_pnl_eur.toFixed(2)} €
        </div>
        <div className="text-xs text-slate-500 mt-1">
          {performance.total_trades} Trades • {performance.win_rate_pct}% Win Rate
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="bg-[#06060f] rounded-lg p-2 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Wins</div>
          <div className="text-sm font-bold text-emerald-400">{performance.winning_trades}</div>
        </div>
        <div className="bg-[#06060f] rounded-lg p-2 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Losses</div>
          <div className="text-sm font-bold text-rose-400">{performance.losing_trades}</div>
        </div>
        <div className="bg-[#06060f] rounded-lg p-2 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Best</div>
          <div className="text-sm font-bold text-emerald-400">+{performance.best_trade_pct}%</div>
        </div>
        <div className="bg-[#06060f] rounded-lg p-2 border border-[#1a1a2e]">
          <div className="text-[10px] text-slate-500 uppercase">Worst</div>
          <div className="text-sm font-bold text-rose-400">{performance.worst_trade_pct}%</div>
        </div>
      </div>

      {/* Mini Chart */}
      <div className="h-[120px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={performance.cumulative_chart_data}>
            <defs>
              <linearGradient id={`colorReturn-${selectedPeriod}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" vertical={false} />
            <XAxis 
              dataKey="date" 
              stroke="#475569" 
              fontSize={8}
              tickFormatter={(value) => {
                if (selectedPeriod === "1y") return value;
                const date = new Date(value);
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
            />
            <YAxis stroke="#475569" fontSize={8} unit="%" />
            <Tooltip 
              contentStyle={{ 
                backgroundColor: "#0c0c18", 
                borderColor: "#1a1a2e", 
                borderRadius: "6px",
                fontSize: "11px"
              }}
              formatter={(value: number) => [`${value.toFixed(2)}%`, "Return"]}
            />
            <Area 
              type="monotone" 
              dataKey="cumulative_return_pct" 
              stroke="#10b981" 
              strokeWidth={2}
              fillOpacity={1} 
              fill={`url(#colorReturn-${selectedPeriod})`} 
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// Main Page Component
export default function TradingPage() {
  const [metrics, setMetrics] = useState({
    price: 0,
    change24h: 0,
  });
  const [logs, setLogs] = useState<any[]>([]);
  const [systemHealth, setSystemHealth] = useState<string>("loading");
  const [performance, setPerformance] = useState(MOCK_PERFORMANCE);
  const [selectedPeriod, setSelectedPeriod] = useState<Period>("1w");
  const [isPaperTrading, setIsPaperTrading] = useState(true);

  // Fetch performance data
  useEffect(() => {
    const fetchPerformance = async () => {
      try {
        const response = await fetch('/api/v1/performance/simulated');
        if (response.ok) {
          const data = await response.json();
          if (data.performance_by_period) {
            setPerformance(data.performance_by_period);
            setIsPaperTrading(data.summary?.trading_mode === "paper");
          }
        }
      } catch (error) {
        console.error('Failed to fetch performance:', error);
      }
    };
    
    fetchPerformance();
    const interval = setInterval(fetchPerformance, 60000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const marketWs = new WebSocket("ws://localhost:8000/ws/market/BTCUSDT");
    marketWs.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.type === "orderbook") {
          const orderbook = payload.data;
          setMetrics({
            price: 0,
            change24h: orderbook.imbalance_ratio || 0,
          });
        } else if (payload.type === "ticker") {
          setMetrics({
            price: payload.data.last_price,
            change24h: payload.data.price_change_percent,
          });
        }
      } catch {}
    };

    // Live Logs für Decision Stream
    const logsWs = new WebSocket("ws://localhost:8000/api/v1/logs/ws");
    logsWs.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.type === "history") {
          setLogs(payload.logs.slice(0, 10));
        } else if (payload.type === "new_log") {
          setLogs(prev => [payload.log, ...prev].slice(0, 10));
        }
      } catch {}
    };

    // System Status & Price Polling
    const checkHealth = async () => {
      try {
        const res = await fetch("http://localhost:8000/health");
        const data = await res.json();
        setSystemHealth(data.status);
        
        // Get live price from Binance API
        try {
          const priceRes = await fetch("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT");
          const priceData = await priceRes.json();
          setMetrics(prev => ({
            ...prev,
            price: parseFloat(priceData.lastPrice),
            change24h: parseFloat(priceData.priceChangePercent)
          }));
        } catch (e) {
          console.error("Price API Error:", e);
        }
      } catch (e) {
        setSystemHealth("error");
      }
    };
    const healthInterval = setInterval(checkHealth, 5000);
    checkHealth();

    return () => {
      marketWs.close();
      logsWs.close();
      clearInterval(healthInterval);
    };
  }, []);

  const isUp = metrics.change24h >= 0;

  return (
    <div className="p-6 lg:p-8 animate-page-in">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
        <div>
          <p className="text-[11px] text-slate-600 font-bold uppercase tracking-[0.2em] mb-1">
            Live Terminal
          </p>
          <h1 className="text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
            <Zap className="text-yellow-400 w-7 h-7" />
            Trading
          </h1>
        </div>

        {/* Portfolio Bar */}
        <div className="flex items-center gap-3">
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl px-4 py-2.5 text-center">
            <p className="text-[9px] text-slate-600 font-bold uppercase tracking-wider">Portfolio</p>
            <p className="text-sm text-white font-bold font-mono">$1,000.00</p>
          </div>
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl px-4 py-2.5 text-center">
            <p className="text-[9px] text-slate-600 font-bold uppercase tracking-wider">Live PnL</p>
            <p className="text-sm text-slate-400 font-bold font-mono">+$0.00</p>
          </div>
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl px-4 py-2.5 text-center">
            <p className="text-[9px] text-slate-600 font-bold uppercase tracking-wider">BTC Price</p>
            <p className={`text-sm font-bold font-mono ${isUp ? "text-emerald-400" : "text-red-400"}`}>
              ${metrics.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </p>
          </div>
        </div>
      </header>

      {/* KPI Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <MetricCard
          title="BTC / USDT"
          value={`$${metrics.price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
          subValue={`${isUp ? "+" : ""}${metrics.change24h.toFixed(2)}%`}
          trend={isUp ? "up" : "down"}
          icon={<TrendingUp className="w-5 h-5 text-blue-400" />}
        />
        <MetricCard
          title="Fear & Greed"
          value="50"
          subValue="Neutraler Markt"
          trend="neutral"
          icon={<Activity className="w-5 h-5 text-purple-400" />}
        />
        <MetricCard
          title="System Status"
          value={systemHealth === "healthy" ? "Online" : systemHealth === "degraded" ? "Warnung" : "Offline"}
          subValue={systemHealth === "healthy" ? "Alle Systeme OK" : systemHealth === "degraded" ? "Eingeschränkter Modus" : "Verbindung verloren"}
          trend={systemHealth === "healthy" ? "up" : systemHealth === "degraded" ? "neutral" : "down"}
          icon={<Zap className={`w-5 h-5 ${systemHealth === "healthy" ? "text-emerald-400" : systemHealth === "degraded" ? "text-yellow-400" : "text-red-400"}`} />}
        />
        <MetricCard
          title="Bots Aktiv"
          value="5 / 5"
          subValue="Vollständig synchron"
          trend="up"
          icon={<Cpu className="w-5 h-5 text-indigo-400" />}
        />
      </div>

      {/* Horizontal Performance Widget - Fills the gap */}
      <div className="mb-6">
        <PerformanceWidgetHorizontal 
          performance={performance[selectedPeriod]} 
          selectedPeriod={selectedPeriod}
          setSelectedPeriod={setSelectedPeriod}
          isPaperTrading={isPaperTrading}
        />
      </div>

      {/* Main Workspace */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Chart + Positions */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          <ChartWidget symbol="BTCUSDT" />

          {/* Positions Table */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl overflow-hidden">
            <div className="px-5 py-4 border-b border-[#1a1a2e] flex items-center justify-between">
              <h3 className="text-sm text-white font-bold flex items-center gap-2">
                <Database className="w-4 h-4 text-emerald-400" />
                Offene Positionen
              </h3>
              <span className="text-[10px] text-slate-600 font-mono">0 active</span>
            </div>
            <div className="p-8 text-center">
              <p className="text-sm text-slate-600">Keine aktiven Trades. Die Agenten überwachen den Markt.</p>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="flex flex-col gap-6">
          {/* Orderbook Depth */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
            <h3 className="text-sm text-white font-bold flex items-center gap-2 mb-4">
              <BarChart3 className="w-4 h-4 text-blue-400" />
              Orderbook Tiefe (20 Lvl)
            </h3>
            <div className="space-y-3">
              <div className="w-full bg-[#06060f] rounded-full h-3 flex overflow-hidden border border-[#1a1a2e]">
                <div className="bg-emerald-500/40 h-full transition-all" style={{ width: "60%" }} />
                <div className="bg-red-500/40 h-full transition-all" style={{ width: "40%" }} />
              </div>
              <div className="flex justify-between text-xs font-mono">
                <span className="text-emerald-400">60% Bids</span>
                <span className="text-red-400">40% Asks</span>
              </div>
              <p className="text-[11px] text-slate-600 leading-relaxed p-3 bg-[#06060f] rounded-xl border border-[#1a1a2e]">
                Quant Agent: Starker Kaufdruck unter dem aktuellen Preis erkannt. Orderbook-Imbalance deutet auf Support hin.
              </p>
            </div>
          </div>

          {/* AI Decision Stream */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl flex-1 flex flex-col overflow-hidden min-h-[320px]">
            <div className="px-5 py-4 border-b border-[#1a1a2e]">
              <h3 className="text-sm text-white font-bold flex items-center gap-2">
                <Cpu className="w-4 h-4 text-indigo-400" />
                AI Decision Stream
              </h3>
            </div>
            <div className="flex-1 p-4 overflow-y-auto space-y-2.5 custom-scrollbar">
              {logs.length === 0 ? (
                <div className="h-full flex items-center justify-center text-slate-700 text-xs italic">
                  Warte auf Agenten-Aktivität...
                </div>
              ) : (
                logs.map((log, i) => (
                  <StreamItem
                    key={i}
                    agent={log.source.replace('agent.', '').toUpperCase()}
                    action={log.level}
                    text={log.message}
                    time={<TimeDisplay timestamp={log.timestamp} />}
                    color={
                      log.level === 'ERROR' ? 'border-red-500/30 text-red-400' :
                      log.level === 'WARNING' ? 'border-yellow-500/30 text-yellow-400' :
                      'border-indigo-500/30 text-indigo-400'
                    }
                  />
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

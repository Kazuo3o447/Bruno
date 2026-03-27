"use client";

import React, { useState, useEffect } from "react";
import { 
  Activity, 
  ShieldAlert, 
  Zap, 
  Target, 
  BarChart3, 
  Cpu, 
  History, 
  TrendingDown,
  ChevronRight,
  ShieldCheck,
  AlertTriangle
} from "lucide-react";
import { 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell, 
  ScatterChart, 
  Scatter, 
  XAxis, 
  YAxis, 
  ZAxis, 
  Tooltip, 
  Legend, 
  CartesianGrid,
  AreaChart,
  Area
} from "recharts";

// Mock Data for demonstration if API is missing
const MOCK_TELEMETRY = {
  status: "ARMED",
  veto_reason: "None (System Healthy)",
  execution_latency_ms: 1.25,
  dry_run: true
};

const MOCK_VETO_DATA = [
  { name: "SMA200 Break", value: 40, color: "#6366f1" },
  { name: "0.5% Liq Wall", value: 35, color: "#8b5cf6" },
  { name: "News Silence", value: 25, color: "#a855f7" }
];

const MOCK_SLIPPAGE = Array.from({ length: 50 }, (_, i) => ({
  time: i,
  slippage: (Math.random() * 0.08) - (Math.random() * 0.02),
  symbol: "BTC/USDT"
}));

const MOCK_PARAMS = {
  current: { "GRSS_Threshold": 40, "Liq_Distance": 0.005, "OFI_Threshold": 500 },
  optimized: { "GRSS_Threshold": 45, "Liq_Distance": 0.006, "OFI_Threshold": 550 },
  theoretical_pnl: 12.45
};

export default function MonitoringPage() {
  const [telemetry, setTelemetry] = useState(MOCK_TELEMETRY);
  const [params, setParams] = useState(MOCK_PARAMS);
  const [loading, setLoading] = useState(false);

  // In a real app, use fetch() to backend endpoints
  // useEffect(() => { fetchTelemetry(); fetchParams(); }, []);

  const getLatencyColor = (ms: number) => {
    if (ms < 5) return "text-emerald-400";
    if (ms < 15) return "text-amber-400";
    return "text-rose-400";
  };

  return (
    <div className="p-8 space-y-8 bg-[#06060f] min-h-screen text-slate-200">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white flex items-center gap-3">
            <Activity className="text-indigo-500 w-8 h-8" />
            MLOps & Telemetry Cockpit
          </h1>
          <p className="text-slate-500 mt-1 font-medium italic">
            "Millisekunden entscheiden über Profit oder Totalverlust."
          </p>
        </div>
        <div className="flex gap-4">
          {telemetry.dry_run && (
            <div className="px-4 py-2 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-center gap-2 animate-pulse">
              <Zap className="w-4 h-4 text-amber-500" />
              <span className="text-xs font-bold text-amber-500 tracking-widest uppercase">Dry Run Active</span>
            </div>
          )}
          <div className="px-4 py-2 bg-indigo-500/10 border border-indigo-500/20 rounded-lg flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${telemetry.status === "ARMED" ? "bg-emerald-500" : "bg-rose-500"} animate-ping`} />
            <span className={`text-xs font-bold tracking-widest uppercase ${telemetry.status === "ARMED" ? "text-emerald-400" : "text-rose-400"}`}>
              {telemetry.status}
            </span>
          </div>
        </div>
      </div>

      {/* KPI Row (Sektor 1) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <KPICard 
          title="Execution Latency" 
          value={`${telemetry.execution_latency_ms}ms`} 
          subValue="Last Execution" 
          icon={Zap}
          className={getLatencyColor(telemetry.execution_latency_ms)}
        />
        <KPICard 
          title="Consensus Speed" 
          value="450ms" 
          subValue="Ollama Reasoning" 
          icon={BrainCircuitIcon}
        />
        <KPICard 
          title="Veto Reason" 
          value={telemetry.veto_reason || "None"} 
          subValue="Active Risk State" 
          icon={ShieldAlert}
          className={telemetry.status === "HALTED" ? "text-rose-400" : "text-emerald-400"}
        />
        <KPICard 
          title="Health Score" 
          value="99.8%" 
          subValue="Infrastructure Up" 
          icon={Cpu}
        />
      </div>

      {/* Charts Row (Sektor 3) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Veto Distribution (Pie Chart) */}
        <div className="bg-[#0c0c1e] rounded-2xl border border-[#1a1a2e] p-6 space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-indigo-400" />
              Veto Distribution (Last 24h)
            </h3>
            <span className="text-xs text-slate-500 uppercase tracking-widest font-bold">Risk Matrix Audit</span>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={MOCK_VETO_DATA}
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="none"
                >
                  {MOCK_VETO_DATA.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip 
                  contentStyle={{ backgroundColor: "#0c0c1e", borderColor: "#1a1a2e", borderRadius: "12px" }}
                  itemStyle={{ color: "#fff" }}
                />
                <Legend layout="vertical" align="right" verticalAlign="middle" />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Slippage Analysis (Scatter Plot) */}
        <div className="bg-[#0c0c1e] rounded-2xl border border-[#1a1a2e] p-6 space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-indigo-400" />
              Slippage Analysis (HFT Shadow Trading)
            </h3>
            <span className="text-xs text-slate-500 uppercase tracking-widest font-bold">Actual vs Expected</span>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" vertical={false} />
                <XAxis type="number" dataKey="time" hide />
                <YAxis 
                  type="number" 
                  dataKey="slippage" 
                  name="Slippage" 
                  unit="%" 
                  stroke="#475569" 
                  fontSize={10}
                  domain={[-0.05, 0.1]}
                />
                <Tooltip 
                  cursor={{ strokeDasharray: '3 3' }}
                  contentStyle={{ backgroundColor: "#0c0c1e", borderColor: "#1a1a2e", borderRadius: "12px" }}
                />
                <Scatter name="Trades" data={MOCK_SLIPPAGE} fill="#6366f1">
                  {MOCK_SLIPPAGE.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.slippage > 0.05 ? "#fb7185" : "#10b981"} 
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* MLOps Hub (Sektor 4) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-[#0c0c1e] rounded-2xl border border-[#1a1a2e] overflow-hidden">
          <div className="p-6 border-b border-[#1a1a2e] flex justify-between items-center bg-white/[0.01]">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <History className="w-5 h-5 text-indigo-400" />
              MLOps Parameter Comparison
            </h3>
            <div className="flex items-center gap-2 px-3 py-1 bg-rose-500/10 border border-rose-500/20 rounded-full">
              <AlertTriangle className="w-3 h-3 text-rose-500" />
              <span className="text-[10px] font-black uppercase text-rose-500">Read Only</span>
            </div>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500 border-b border-[#1a1a2e]">
              <tr>
                <th className="px-6 py-4 font-bold uppercase tracking-wider">Parameter</th>
                <th className="px-6 py-4 font-bold uppercase tracking-wider">Productive (Active)</th>
                <th className="px-6 py-4 font-bold uppercase tracking-wider">Optimized (Target)</th>
                <th className="px-6 py-4 font-bold uppercase tracking-wider">Delta</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1a1a2e]">
              {Object.keys(params.current).map((key) => (
                <tr key={key} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-4 font-medium text-slate-300">{key}</td>
                  <td className="px-6 py-4 font-mono text-indigo-400">{(params.current as any)[key]}</td>
                  <td className="px-6 py-4 font-mono text-violet-400">{(params.optimized as any)[key]}</td>
                  <td className="px-6 py-4">
                    <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                      (params.optimized as any)[key] > (params.current as any)[key] ? "bg-emerald-500/10 text-emerald-400" : "bg-rose-500/10 text-rose-400"
                    }`}>
                      {((params.optimized as any)[key] - (params.current as any)[key]).toFixed(4)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="bg-gradient-to-br from-indigo-900/40 to-violet-900/40 rounded-2xl border border-indigo-500/20 p-8 flex flex-col justify-center items-center text-center space-y-4">
          <div className="p-4 bg-white/10 rounded-full">
            <TrendingDown className="w-12 h-12 text-emerald-400 transform rotate-180" />
          </div>
          <div>
            <h4 className="text-indigo-200 font-bold uppercase tracking-widest text-xs">Simulated Performance</h4>
            <div className="text-5xl font-black text-white mt-2">
              +{params.theoretical_pnl}%
            </div>
            <p className="text-emerald-400 font-bold mt-1 uppercase text-[10px] tracking-tighter">
              Theoretical Profit Factor Improvement
            </p>
          </div>
          <div className="pt-4 text-xs text-indigo-300/60 font-medium">
            Based on historical slippage & 2.5x Leverage
          </div>
        </div>
      </div>
    </div>
  );
}

function KPICard({ title, value, subValue, icon: Icon, className = "" }: any) {
  return (
    <div className="bg-[#0c0c1e] rounded-2xl border border-[#1a1a2e] p-6 hover:border-indigo-500/30 transition-all duration-300 relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-4 opacity-5 group-hover:opacity-10 transition-opacity">
        <Icon className="w-16 h-16" />
      </div>
      <div className="flex flex-col space-y-2">
        <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">{title}</span>
        <div className={`text-3xl font-black tracking-tighter ${className}`}>
          {value}
        </div>
        <div className="flex items-center gap-1 text-[10px] font-bold text-slate-600 uppercase">
          {subValue}
          <ChevronRight className="w-3 h-3" />
        </div>
      </div>
    </div>
  );
}

function BrainCircuitIcon(props: any) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .52 8.125A9 9 0 1 0 12 5Z" />
      <path d="M9 13a4.5 4.5 0 0 0 3-4" />
      <path d="M6.003 5.125A3 3 0 1 1 12 5" />
      <path d="M15 13a4.5 4.5 0 0 1-3-4" />
      <path d="M17.997 5.125A3 3 0 1 0 12 5" />
    </svg>
  );
}

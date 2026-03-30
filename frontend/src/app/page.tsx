"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Activity, ShieldAlert, Cpu, Zap,
  BarChart3, Radio, AlertTriangle, CheckCircle2, Clock, Wifi,
  ArrowRight, MessageSquare, Eye
} from "lucide-react";

const LightweightChart = dynamic(() => import("../components/LightweightChart"), { ssr: false });
const SystemMatrix = dynamic(() => import("../components/SystemMatrix"), { ssr: false });
const ActivePositions = dynamic(() => import("../components/ActivePositions"), { ssr: false });


/* ─── Types ─── */
interface HealthData {
  api: boolean;
  db: boolean;
  redis: boolean;
  ollama: boolean;
}

interface AgentBrief {
  id: string;
  name: string;
  status: string;
  type: string;
  processed_count: number;
  error_count: number;
  description: string;
  last_activity: string;
  uptime_seconds?: number;
}

interface LogEntry {
  timestamp: string;
  level: string;
  source: string;
  message: string;
}

export default function HomePage() {
  const [price, setPrice] = useState(0);
  const [change24h, setChange24h] = useState(0);
  const [health, setHealth] = useState<HealthData>({ api: false, db: false, redis: false, ollama: false });
  const [agents, setAgents] = useState<AgentBrief[]>([]);
  const [newsHealth, setNewsHealth] = useState<{ active: number, total: number } | null>(null);
  const [contextData, setContextData] = useState<any>(null);
  const [microData, setMicroData] = useState<any>(null);
  const [time, setTime] = useState<Date | null>(null);
  const [recentLogs, setRecentLogs] = useState<LogEntry[]>([]);
  const [sourceHealth, setSourceHealth] = useState<any>({});
  const wsLogRef = useRef<WebSocket | null>(null);

  // Realtime price via WS
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8001/ws/market/BTCUSDT");
    ws.onmessage = (e) => {
      try {
        const p = JSON.parse(e.data);
        if (p.type === "ticker") {
          setPrice(p.data.last_price);
          setChange24h(p.data.price_change_percent);
        } else if (p.type === "context_update") {
          setContextData(p.data);
        } else if (p.type === "micro_update") {
          setMicroData(p.data);
        }
      } catch {}
    };
    return () => ws.close();
  }, []);

  // Health check
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch("http://localhost:8001/health");
        if (res.ok) {
          const d = await res.json();
          setHealth({
            api: true,
            db: d.database === "connected" || d.db === "ok",
            redis: d.redis === "connected" || d.redis === "ok",
            ollama: d.ollama === "connected" || d.ollama === "ok",
          });
        }
      } catch {
        setHealth({ api: false, db: false, redis: false, ollama: false });
      }
    };
    check();
    const iv = setInterval(check, 15000);
    return () => clearInterval(iv);
  }, []);

  // Agent status
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("http://localhost:8001/api/v1/agents/status");
        if (res.ok) {
          const d = await res.json();
          setAgents(d.agents || []);
        }
      } catch {}
    };
    load();
    const iv = setInterval(load, 5000);
    return () => clearInterval(iv);
  }, []);

  // News Health
  useEffect(() => {
    const loadHealth = async () => {
      try {
        const res = await fetch("http://localhost:8001/api/v1/systemtest/news_health");
        if (res.ok) {
          const d = await res.json();
          const feeds = Object.values(d.feeds || {});
          const active = feeds.filter((f: any) => f.status === "success").length;
          setNewsHealth({ active, total: feeds.length });
        }
      } catch {}
    };
    loadHealth();
    const iv = setInterval(loadHealth, 30000);
    return () => clearInterval(iv);
  }, []);

  // Data Source Health & Latency
  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetch("http://localhost:8001/api/v1/systemtest/health/sources");
        if (res.ok) {
          setSourceHealth(await res.json());
        }
      } catch {}
    };
    load();
    const iv = setInterval(load, 10000);
    return () => clearInterval(iv);
  }, []);

  // Live log stream for activity feed
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket("ws://localhost:8001/api/v1/logs/ws");
      wsLogRef.current = ws;
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "new_log") {
            setRecentLogs((prev: LogEntry[]) => [data.log, ...prev].slice(0, 30));
          } else if (data.type === "history") {
            setRecentLogs(data.logs.slice(0, 30));
          }
        } catch {}
      };
      ws.onclose = () => setTimeout(connect, 3000);
    };
    connect();
    return () => wsLogRef.current?.close();
  }, []);

  // Clock
  useEffect(() => {
    setTime(new Date()); // Set initial time on client
    const iv = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  const isUp = change24h >= 0;
  const runningAgents = agents.filter(a => a.status === "running").length;
  const totalOps = agents.reduce((sum, a) => sum + a.processed_count, 0);
  const totalErrors = agents.reduce((sum, a) => sum + a.error_count, 0);

  return (
    <div className="p-6 lg:p-8 animate-page-in min-h-screen relative">

      {/* Header */}
      <header className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-8 relative z-10">
        <div>
          <p className="text-[11px] text-slate-600 font-bold uppercase tracking-[0.2em] mb-1">
            Command Center
          </p>
          <h1 className="text-3xl font-extrabold tracking-tight relative">
            {/* Neon BRUNO Effect */}
            <span className="relative text-cyan-400">
              BRUNO
            </span>
          </h1>
          <p className="text-xs text-cyan-200/60 font-mono mt-1">
            Autonomous Bitcoin Trading Intelligence
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <Wifi className="w-3.5 h-3.5 text-emerald-500" />
          <span className="font-mono">{time ? time.toLocaleTimeString("de-DE", { hour12: false }) : "--:--:--"}</span>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-2">
            {contextData?.GRSS_Score === 0 && (
              <span className="text-red-500 font-bold animate-pulse px-2 py-0.5 bg-red-500/10 border border-red-500/20 rounded-md uppercase text-[10px]">
                [CRITICAL] Data Silence - Trading Halted
              </span>
            )}
            <span>{runningAgents}/{agents.length} Agenten aktiv</span>
          </div>
          <span className="text-slate-700">|</span>
          <span>Paper Trading</span>
        </div>
      </header>

      {/* Price Hero with inline chart */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6 lg:p-8 mb-6 relative overflow-hidden glow-indigo">
        <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-500/[0.03] rounded-full -translate-y-1/2 translate-x-1/2 blur-3xl pointer-events-none" />
        <div className="flex flex-col xl:flex-row xl:items-start justify-between gap-6 relative z-10">
          <div className="shrink-0">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-sm font-bold text-slate-400">BTC / USDT</span>
              <span className="text-[9px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-bold uppercase tracking-wider">
                Binance Futures
              </span>
            </div>
            <div className="flex items-end gap-4 mb-2">
              <span className="text-5xl font-extrabold text-white font-mono tracking-tight">
                ${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`flex items-center gap-1 text-lg font-bold mb-1 ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                {isUp ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                {isUp ? "+" : ""}{change24h.toFixed(2)}%
              </span>
            </div>
            {/* Live Telemetry (Phase 6) */}
            <div className="flex items-center gap-3 mb-4">
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#111122] border border-[#1a1a2e]">
                <span className="text-[10px] text-slate-500 font-bold uppercase">Source</span>
                <span className="text-[10px] text-indigo-400 font-mono font-bold">{microData?.Source || "BINANCE"}</span>
              </div>
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#111122] border border-[#1a1a2e]">
                <span className="text-[10px] text-slate-500 font-bold uppercase">Latency</span>
                <span className={`text-[10px] font-mono font-bold ${microData?.latency_ms < 200 ? 'text-emerald-400' : 'text-amber-400'}`}>
                   {microData?.latency_ms ? `${Math.round(microData.latency_ms)}ms` : "--"}
                </span>
              </div>
              <div className={`flex items-center gap-1.5 px-2 py-0.5 rounded bg-[#111122] border border-[#1a1a2e] ${contextData?.Stress_Score > 80 ? 'animate-pulse' : ''}`}>
                <span className="text-[10px] text-slate-500 font-bold uppercase">Stress</span>
                <span className={`text-[10px] font-mono font-bold ${contextData?.Stress_Score > 70 ? 'text-red-400' : contextData?.Stress_Score > 40 ? 'text-amber-400' : 'text-emerald-400'}`}>
                   {contextData?.Stress_Score ?? "--"}
                </span>
              </div>
            </div>
            </div>
            
            <div className="flex-1 min-w-0">
               <LightweightChart symbol="BTCUSDT" />
            </div>
          </div>
        </div>

        <div className="mb-8">
          <ActivePositions />
        </div>

        <div className="mb-8">
          <SystemMatrix />
        </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

        {/* Agent Pipeline — now with more info */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6">
          <div className="flex items-center justify-between mb-5">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Cpu className="w-4 h-4 text-indigo-400" />
              Agent Pipeline
            </h2>
            <Link href="/agenten" className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1 transition-colors">
              Details <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
          {agents.length === 0 ? (
            <p className="text-xs text-slate-600 italic">Lade Agenten-Status…</p>
          ) : (
            <div className="space-y-2">
              {agents.map((a: AgentBrief) => (
                <div key={a.id} className="flex items-center justify-between py-1.5 group">
                  <div className="flex items-center gap-2.5">
                    <div className="relative">
                      <span className={`flex w-2 h-2 rounded-full ${a.status === "running" ? "bg-emerald-500" : "bg-slate-700"}`} />
                      {a.status === "running" && (
                        <span className="absolute inset-0 flex w-2 h-2 rounded-full bg-emerald-400 animate-ping opacity-30" />
                      )}
                    </div>
                    <span className="text-sm text-slate-300 font-medium">{a.name}</span>
                  </div>
                  <span className="text-[10px] text-slate-600 font-mono group-hover:text-slate-400 transition-colors">
                    {a.processed_count} ops
                  </span>
                </div>
              ))}
            </div>
          )}
          {/* Pipeline Summary */}
          <div className="mt-4 pt-4 border-t border-[#1a1a2e] grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="text-[9px] text-slate-600 font-bold uppercase">Aktiv</p>
              <p className="text-sm font-bold text-emerald-400 font-mono">{runningAgents}</p>
            </div>
            <div>
              <p className="text-[9px] text-slate-600 font-bold uppercase">Total Ops</p>
              <p className="text-sm font-bold text-white font-mono">{totalOps}</p>
            </div>
            <div>
              <p className="text-[9px] text-slate-600 font-bold uppercase">Errors</p>
              <p className={`text-sm font-bold font-mono ${totalErrors > 0 ? "text-red-400" : "text-emerald-400"}`}>{totalErrors}</p>
            </div>
          </div>
        </div>

        {/* Market Indicators / Sentiment & Macro Card */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-5 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            Sentiment & Macro Bias
          </h2>
          <div className="space-y-4">
            {/* GRSS Score Section */}
            <div className="mb-4">
              <div className="flex justify-between items-end mb-1.5">
                <span className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">GRSS Score</span>
                <span className={`text-lg font-mono font-bold ${
                  !contextData ? "text-slate-600" :
                  contextData.GRSS_Score < 40 ? "text-red-400" :
                  contextData.GRSS_Score < 70 ? "text-amber-400" : "text-emerald-400"
                }`}>
                  {contextData?.GRSS_Score ?? "—"}
                </span>
              </div>
              <div className="h-1.5 w-full bg-[#1a1a2e] rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all duration-1000 ${
                    !contextData ? "bg-slate-800" :
                    contextData.GRSS_Score < 40 ? "bg-red-500" :
                    contextData.GRSS_Score < 70 ? "bg-amber-500" : "bg-emerald-500"
                  }`}
                  style={{ width: `${contextData?.GRSS_Score ?? 0}%` }}
                />
              </div>
            </div>

            {/* Market Stress Meter Section (Phase 6) */}
            <div className="mb-6">
              <div className="flex justify-between items-end mb-1.5">
                <span className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">Market Stress Meter</span>
                <span className={`text-xs font-mono font-bold ${
                  !contextData ? "text-slate-600" :
                  contextData.Stress_Score > 70 ? "text-red-400" :
                  contextData.Stress_Score > 40 ? "text-amber-400" : "text-emerald-400"
                }`}>
                  {contextData?.Stress_Score ? (
                    contextData.Stress_Score > 80 ? "EXTREME" :
                    contextData.Stress_Score > 60 ? "HIGH" :
                    contextData.Stress_Score > 30 ? "MEDIUM" : "LOW"
                  ) : "—"}
                </span>
              </div>
              <div className="h-2 w-full bg-[#1a1a2e] rounded-full overflow-hidden flex gap-1 p-0.5">
                  {[...Array(10)].map((_, i) => {
                    const isActive = contextData?.Stress_Score >= (i + 1) * 10;
                    const color = i < 4 ? "bg-emerald-500" : i < 7 ? "bg-amber-500" : "bg-red-500";
                    return (
                      <div key={i} className={`h-full flex-1 rounded-sm transition-all duration-500 ${isActive ? color : "bg-slate-800/30"}`} />
                    );
                  })}
              </div>
            </div>
            
            <div className="space-y-3 pt-2">
              <BiasBar label="F-BERT (Macro)" value={contextData?.Bias_Breakdown?.Macro} />
              <BiasBar label="C-BERT (Crypto)" value={contextData?.Bias_Breakdown?.Crypto} />
              
              <div className="pt-2 grid grid-cols-2 gap-3">
                <div className="bg-[#06060f] p-2.5 rounded-xl border border-[#1a1a2e]">
                  <p className="text-[9px] text-slate-600 font-bold uppercase mb-1">DXY 24h</p>
                  <p className={`text-xs font-mono font-bold ${contextData?.DXY_Change_24h > 0 ? "text-red-400" : "text-emerald-400"}`}>
                    {contextData?.DXY_Change_24h > 0 ? "+" : ""}{contextData?.DXY_Change_24h ?? "0.0"}%
                  </p>
                  {contextData?.Bias_Breakdown?.DXY_Decoupling && (
                    <span className="text-[8px] text-indigo-400 font-bold animate-pulse mt-1 block">DECOUPLING!</span>
                  )}
                </div>
                <div className="bg-[#06060f] p-2.5 rounded-xl border border-[#1a1a2e]">
                  <p className="text-[9px] text-slate-600 font-bold uppercase mb-1">ETF Flow (3d)</p>
                  <p className={`text-xs font-mono font-bold ${contextData?.ETF_Flows_3d_M > 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {contextData?.ETF_Flows_3d_M > 0 ? "+" : ""}{contextData?.ETF_Flows_3d_M ?? "0"}M
                  </p>
                </div>
              </div>
            </div>

            {contextData?.Veto_Active && (
              <div className="mt-4 p-2.5 bg-red-500/5 border border-red-500/10 rounded-xl">
                 <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2 text-red-400 text-[10px] font-bold">
                        <ShieldAlert className="w-3 h-3" /> HARD VETO ACTIVE
                    </div>
                    {contextData?.Macro_Status === "BEARISH" && (
                        <span className="text-[8px] bg-red-500/20 text-red-500 px-1.5 py-0.5 rounded font-bold">NASDAQ {"<"} SMA200</span>
                    )}
                 </div>
                 <p className="text-xs text-slate-500 font-mono leading-snug">{contextData.Reason}</p>
              </div>
            )}
          </div>
        </div>

        {/* Micro-Structure Card */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-5 flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            OB Micro-Structure
          </h2>
          <div className="space-y-4">
             <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#06060f] p-3 rounded-xl border border-[#1a1a2e]">
                   <p className="text-[9px] text-slate-600 font-bold uppercase mb-1">OFI (Imbalance)</p>
                   <p className={`text-lg font-mono font-bold ${microData?.OFI > 0 ? "text-emerald-400" : microData?.OFI < 0 ? "text-red-400" : "text-slate-400"}`}>
                      {microData?.OFI > 0 ? "+" : ""}{microData?.OFI ?? "—"}
                   </p>
                </div>
                <div className="bg-[#06060f] p-3 rounded-xl border border-[#1a1a2e]">
                   <p className="text-[9px] text-slate-600 font-bold uppercase mb-1">VAMP vs Price</p>
                   <p className="text-sm font-mono text-slate-300">
                      {microData?.VAMP ? `$${microData.VAMP.toLocaleString()}` : "—"}
                   </p>
                </div>
             </div>

             <div className="pt-2">
                <div className="flex justify-between items-center mb-1.5">
                   <div className="flex items-center gap-2">
                      <span className="text-[11px] text-slate-500 font-bold uppercase">CVD Trend</span>
                      {contextData?.Veto_Active && contextData.Reason.includes("CVD") && (
                        <AlertTriangle className="w-3.5 h-3.5 text-red-500 animate-pulse" />
                      )}
                   </div>
                   <span className={`text-xs font-mono font-bold ${microData?.CVD >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {microData?.CVD > 0 ? "+" : ""}{microData?.CVD?.toFixed(2) ?? "—"}
                   </span>
                </div>
                <div className="h-1.5 w-full bg-[#1a1a2e] rounded-full overflow-hidden">
                   <div 
                      className={`h-full transition-all duration-500 ${microData?.CVD >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
                      style={{ width: `${Math.min(100, Math.abs((microData?.CVD ?? 0) / 100) * 100)}%` }}
                   />
                </div>
             </div>

             <IndicatorRow 
                label="Funding APR" 
                value={microData?.Funding_APR ? `${microData.Funding_APR}%` : "—"} 
                badge={microData?.Funding_APR > 15 ? "Overheated" : "Stable"}
                badgeColor={microData?.Funding_APR > 15 ? "text-red-400 bg-red-400/10 border-red-400/20" : "text-slate-500 bg-slate-800 border-slate-700"}
             />
          </div>
        </div>

        {/* KPI Summary */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-5 flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" />
            Trading KPIs
          </h2>
          <div className="space-y-4">
            <KPIRow icon={<Activity className="w-4 h-4 text-emerald-400" />} label="Signale heute" value="0" />
            <KPIRow icon={<ShieldAlert className="w-4 h-4 text-red-400" />} label="Risk Vetos" value="0" />
            <KPIRow icon={<Zap className="w-4 h-4 text-yellow-400" />} label="Trades ausgeführt" value="0" />
            <KPIRow icon={<Clock className="w-4 h-4 text-indigo-400" />} label="Worker Uptime" value={agents[0]?.uptime_seconds ? formatUptime(agents[0].uptime_seconds) : "—"} />
          </div>
        </div>
      </div>

      {/* Live Activity Feed — full transparency */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1a1a2e]">
          <h2 className="text-sm font-bold text-white flex items-center gap-2">
            <Eye className="w-4 h-4 text-indigo-400" />
            Live-Aktivitäten
            <span className="text-[9px] text-slate-600 font-mono ml-2">Echtzeit-Feed</span>
          </h2>
          <Link href="/logs" className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold uppercase tracking-wider flex items-center gap-1 transition-colors">
            Vollständige Logs <ArrowRight className="w-3 h-3" />
          </Link>
        </div>
        <div className="max-h-[280px] overflow-y-auto custom-scrollbar">
          {recentLogs.length === 0 ? (
            <div className="p-8 text-center text-slate-600 text-sm">
              Verbinde zum Log-Stream…
            </div>
          ) : (
            <div className="divide-y divide-[#1a1a2e]/50">
              {recentLogs.map((log: LogEntry, i: number) => {
                const levelColor = log.level === "ERROR" || log.level === "CRITICAL"
                  ? "text-red-400"
                  : log.level === "WARNING"
                    ? "text-amber-400"
                    : "text-blue-400/60";

                const agentName = log.source?.replace("agent.", "").replace("system.", "");

                return (
                  <div key={i} className="flex items-start gap-3 px-6 py-2.5 hover:bg-white/[0.01] transition-colors text-[12px]">
                    <span className="shrink-0 text-slate-700 font-mono w-16 pt-0.5">
                      {new Date(log.timestamp).toLocaleTimeString("de-DE", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                    </span>
                    <span className={`shrink-0 w-4 pt-0.5 ${levelColor}`}>
                      {log.level === "ERROR" || log.level === "CRITICAL" ? "✕" : log.level === "WARNING" ? "⚠" : "●"}
                    </span>
                    <span className="shrink-0 text-indigo-400/40 font-bold text-[10px] uppercase tracking-wider w-24 truncate pt-0.5">
                      {agentName}
                    </span>
                    <span className="flex-1 text-slate-400">{log.message}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Sub-Components ─── */

function MiniStat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-[#06060f] border border-[#1a1a2e] rounded-xl px-4 py-2.5 min-w-[110px]">
      <p className="text-[9px] text-slate-600 font-bold uppercase tracking-wider mb-0.5">{label}</p>
      <p className={`text-sm font-bold font-mono ${color}`}>{value}</p>
    </div>
  );
}

function SourceHealthRow({ label, data }: { label: string; data: any }) {
  const status = data?.status || "offline";
  const latency = data?.latency_ms || 0;
  
  const latencyColor = latency < 200 ? "text-emerald-500" : latency < 1000 ? "text-amber-500" : "text-red-500";
  
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-slate-400">{label}</span>
      <div className="flex items-center gap-2">
        {status === "online" && latency > 0 && (
           <span className={`text-[10px] font-mono ${latencyColor}`}>
              {Math.round(latency)}ms
           </span>
        )}
        <span className={`w-2 h-2 rounded-full ${status === "online" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]" : "bg-red-500"}`} />
      </div>
    </div>
  );
}

function HealthRow({ label, ok, warn }: { label: string; ok: boolean; warn?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-slate-400">{label}</span>
      {ok ? (
        <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
          <CheckCircle2 className="w-3.5 h-3.5" /> Online
        </span>
      ) : warn ? (
        <span className="flex items-center gap-1.5 text-xs text-amber-400 font-medium">
          <AlertTriangle className="w-3.5 h-3.5" /> Fallback
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-xs text-slate-600 font-medium">
          <Clock className="w-3.5 h-3.5" /> Prüfe…
        </span>
      )}
    </div>
  );
}

function IndicatorRow({ label, value, badge, badgeColor }: { label: string; value: string; badge: string; badgeColor: string }) {
  return (
    <div className="flex items-center justify-between group">
      <div>
        <p className="text-[10px] text-slate-600 font-bold uppercase tracking-wider mb-0.5">{label}</p>
        <p className="text-sm font-bold text-white font-mono">{value}</p>
      </div>
      <span className={`text-[9px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wider ${badgeColor}`}>
        {badge}
      </span>
    </div>
  );
}

function BiasBar({ label, value }: { label: string; value: number | undefined }) {
  const normValue = value !== undefined ? (value + 1) / 2 : 0.5; // -1..1 to 0..1
  const colorClass = value === undefined ? "bg-slate-800" :
                    value > 0.3 ? "bg-emerald-500" :
                    value < -0.3 ? "bg-red-500" : "bg-indigo-500/60";

  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <span className="text-[10px] text-slate-500 font-medium">{label}</span>
        <span className={`text-[10px] font-mono ${value && value > 0 ? "text-emerald-400" : value && value < 0 ? "text-red-400" : "text-slate-500"}`}>
          {value !== undefined ? (value > 0 ? "+" : "") + value.toFixed(2) : "—"}
        </span>
      </div>
      <div className="h-1 w-full bg-[#1a1a2e] rounded-full overflow-hidden">
        <div 
          className={`h-full transition-all duration-700 ${colorClass}`}
          style={{ width: `${normValue * 100}%` }}
        />
      </div>
    </div>
  );
}

function KPIRow({ icon, label, value }: { icon: any; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-sm text-slate-300">{label}</span>
      </div>
      <span className="text-sm font-bold text-white font-mono">{value}</span>
    </div>
  );
}

function formatUptime(sec: number): string {
  if (sec < 60) return `${sec}s`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m`;
  return `${Math.floor(sec / 3600)}h ${Math.floor((sec % 3600) / 60)}m`;
}



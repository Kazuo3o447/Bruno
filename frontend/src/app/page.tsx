"use client";

import { useState, useEffect, useRef } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  TrendingUp, TrendingDown, Activity, ShieldAlert, Cpu, Zap,
  BarChart3, Radio, AlertTriangle, CheckCircle2, Clock, Wifi,
  ArrowRight, MessageSquare, Eye
} from "lucide-react";

const PriceLineChart = dynamic(() => import("../components/PriceLineChart"), { ssr: false });

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
  const [time, setTime] = useState(new Date());
  const [recentLogs, setRecentLogs] = useState<LogEntry[]>([]);
  const wsLogRef = useRef<WebSocket | null>(null);

  // Realtime price via WS
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/market/BTCUSDT");
    ws.onmessage = (e) => {
      try {
        const p = JSON.parse(e.data);
        if (p.type === "ticker") {
          setPrice(p.data.last_price);
          setChange24h(p.data.price_change_percent);
        }
      } catch {}
    };
    return () => ws.close();
  }, []);

  // Health check
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch("http://localhost:8000/health");
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
        const res = await fetch("http://localhost:8000/api/v1/agents/status");
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

  // Live log stream for activity feed
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket("ws://localhost:8000/api/v1/logs/ws");
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
    const iv = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(iv);
  }, []);

  const isUp = change24h >= 0;
  const runningAgents = agents.filter(a => a.status === "running").length;
  const totalOps = agents.reduce((sum, a) => sum + a.processed_count, 0);
  const totalErrors = agents.reduce((sum, a) => sum + a.error_count, 0);

  return (
    <div className="p-6 lg:p-8 animate-page-in min-h-screen">
      {/* Header */}
      <header className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-8">
        <div>
          <p className="text-[11px] text-slate-600 font-bold uppercase tracking-[0.2em] mb-1">
            Command Center
          </p>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">
            Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <Wifi className="w-3.5 h-3.5 text-emerald-500" />
          <span className="font-mono">{time.toLocaleTimeString("de-DE", { hour12: false })}</span>
          <span className="text-slate-700">|</span>
          <span>{runningAgents}/{agents.length} Agenten aktiv</span>
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
            <div className="flex items-end gap-4 mb-4">
              <span className="text-5xl font-extrabold text-white font-mono tracking-tight">
                ${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span className={`flex items-center gap-1 text-lg font-bold mb-1 ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                {isUp ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
                {isUp ? "+" : ""}{change24h.toFixed(2)}%
              </span>
            </div>
            {/* Mini stats */}
            <div className="flex flex-wrap gap-3">
              <MiniStat label="Portfolio" value="$1,000.00" color="text-white" />
              <MiniStat label="Open PnL" value="+$0.00" color="text-slate-400" />
              <MiniStat label="Trades (24h)" value="0" color="text-slate-400" />
              <MiniStat label="Win Rate" value="—" color="text-slate-500" />
            </div>
          </div>

          {/* BTC Price Line Chart */}
          <div className="flex-1 min-w-0">
            <PriceLineChart symbol="BTCUSDT" />
          </div>
        </div>
      </div>

      {/* Main Grid: Health + Agents + Market + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-6">

        {/* System Health */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-5 flex items-center gap-2">
            <Radio className="w-4 h-4 text-indigo-400" />
            System Health
          </h2>
          <div className="space-y-3">
            <HealthRow label="Backend API" ok={health.api} />
            <HealthRow label="PostgreSQL" ok={health.db} />
            <HealthRow label="Redis" ok={health.redis} />
            <HealthRow label="Ollama LLM" ok={health.ollama} warn />
          </div>
        </div>

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

        {/* Market Indicators */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-6">
          <h2 className="text-sm font-bold text-white mb-5 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-indigo-400" />
            Markt-Indikatoren
          </h2>
          <div className="space-y-4">
            <IndicatorRow label="Fear & Greed Index" value="50" badge="Neutral" badgeColor="text-slate-400 bg-slate-800 border-slate-700" />
            <IndicatorRow label="Funding Rate" value="0.012%" badge="Longs zahlen" badgeColor="text-amber-400 bg-amber-500/10 border-amber-500/20" />
            <IndicatorRow label="Open Interest" value="—" badge="Lade..." badgeColor="text-slate-500 bg-slate-800 border-slate-700" />
            <IndicatorRow label="Liquidations (1h)" value="—" badge="Lade..." badgeColor="text-slate-500 bg-slate-800 border-slate-700" />
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
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm text-slate-300 font-medium">{label}</p>
        <p className="text-lg font-bold text-white font-mono">{value}</p>
      </div>
      <span className={`text-[10px] px-2.5 py-1 rounded-lg font-bold border ${badgeColor}`}>{badge}</span>
    </div>
  );
}

function KPIRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2.5">
        {icon}
        <span className="text-sm text-slate-400">{label}</span>
      </div>
      <span className="text-sm font-bold text-white font-mono">{value}</span>
    </div>
  );
}

function formatUptime(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m ${seconds % 60}s`;
}

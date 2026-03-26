"use client";

import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import {
  TrendingUp, TrendingDown, Activity, ShieldAlert, Cpu,
  Database, Zap, BarChart3
} from "lucide-react";

const ChartWidget = dynamic(() => import("../../components/ChartWidget"), { ssr: false });

export default function TradingPage() {
  const [metrics, setMetrics] = useState({
    price: 0,
    change24h: 0,
  });
  const [logs, setLogs] = useState<any[]>([]);
  const [systemHealth, setSystemHealth] = useState<string>("loading");

  useEffect(() => {
    const marketWs = new WebSocket("ws://localhost:8000/ws/market/BTCUSDT");
    marketWs.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (payload.type === "ticker") {
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

    // System Status Polling
    const checkHealth = async () => {
      try {
        const res = await fetch("http://localhost:8000/health");
        const data = await res.json();
        setSystemHealth(data.status);
      } catch {
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
                    time={new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
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

/* ─── Sub-Components ─── */

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
  agent: string; action: string; text: string; time: string; color: string;
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

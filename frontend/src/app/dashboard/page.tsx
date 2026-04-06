"use client";

import { useEffect, useState, useCallback } from "react";
import { Activity, TrendingUp, AlertTriangle, Shield, Zap, Clock, XCircle } from "lucide-react";

interface Telemetry {
  status: "ARMED" | "HALTED";
  veto_active: boolean;
  veto_reason: string;
  dry_run: boolean;
  live_trading_approved?: boolean;
  grss: {
    score: number | null;
    velocity_30min: number | null;
    veto_active: boolean;
  };
  market: {
    btc_price: number | null;
    btc_change_24h_pct: number | null;
    btc_change_1h_pct: number | null;
    ofi: number | null;
    funding_rate: number | null;
    put_call_ratio: number | null;
    fear_greed: number | null;
    vix?: number | null;
    dvol?: number | null;
    retail_score?: number | null;
    sentiment?: number | null;
    oi_delta_pct?: number | null;
    long_short_ratio?: number | null;
  };
  data_sources: Record<string, { status: string; latency_ms: number; last_update: string }>;
  agents: Record<string, { status: string; age_seconds: number | null; healthy: boolean }>;
}

interface Position {
  status: string;
  symbol: string;
  side: string;
  entry_price: number;
  quantity: number;
  stop_loss_price: number;
  take_profit_price: number;
}

interface DecisionFeedResponse {
  events: Array<{
    ts?: string;
    outcome?: string;
    reason?: string;
    regime?: string;
  }>;
  count: number;
  stats: {
    ofi_below_threshold: number;
    cascade_hold: number;
    signals_generated: number;
  };
}

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}

function fmtPrice(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

// Compact Decision Timeline Component
function DecisionTimeline({ events }: { events: DecisionFeedResponse["events"] }) {
  const recent = events.slice(0, 12).reverse();
  
  return (
    <div className="flex gap-1 items-end h-16">
      {recent.map((event, idx) => {
        const isSignal = String(event.outcome ?? "").toUpperCase().includes("SIGNAL_");
        const isBlocked = String(event.outcome ?? "").toUpperCase().includes("HOLD") || 
                         String(event.outcome ?? "").toUpperCase().includes("BLOCK") ||
                         String(event.outcome ?? "").toUpperCase().includes("VETO");
        
        return (
          <div
            key={idx}
            className={`flex-1 rounded-t min-w-[20px] transition-all hover:opacity-80 ${
              isSignal ? "bg-emerald-500" : isBlocked ? "bg-red-500" : "bg-slate-600"
            }`}
            style={{ height: `${30 + (event.outcome?.length || 10) * 2}%` }}
            title={`${event.outcome} - ${event.reason}`}
          />
        );
      })}
    </div>
  );
}

// Market Sentiment Bars
function SentimentBars({ market }: { market: Telemetry["market"] }) {
  const metrics = [
    { label: "OFI", value: market.ofi, max: 1, color: market.ofi && market.ofi > 0.5 ? "emerald" : market.ofi && market.ofi < 0.3 ? "red" : "amber" },
    { label: "Funding", value: market.funding_rate, max: 0.01, color: market.funding_rate && market.funding_rate > 0.005 ? "red" : market.funding_rate && market.funding_rate < 0 ? "emerald" : "amber" },
    { label: "PCR", value: market.put_call_ratio, max: 1, color: market.put_call_ratio && market.put_call_ratio > 0.8 ? "emerald" : market.put_call_ratio && market.put_call_ratio < 0.5 ? "red" : "amber" },
    { label: "F&G", value: market.fear_greed, max: 100, color: market.fear_greed && market.fear_greed > 70 ? "amber" : market.fear_greed && market.fear_greed < 30 ? "emerald" : "red" },
  ];
  
  return (
    <div className="space-y-2">
      {metrics.map((metric) => {
        const normalized = metric.value !== null ? Math.min(Math.max(metric.value / metric.max, 0), 1) : 0;
        const colorClass = metric.color === "emerald" ? "bg-emerald-500" : metric.color === "amber" ? "bg-amber-500" : "bg-red-500";
        
        return (
          <div key={metric.label} className="flex items-center gap-2">
            <span className="w-8 text-[10px] text-slate-500">{metric.label}</span>
            <div className="flex-1 h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
              <div className={`h-full ${colorClass} transition-all`} style={{ width: `${normalized * 100}%` }} />
            </div>
            <span className="w-12 text-[10px] text-right text-slate-400">
              {metric.value !== null ? fmt(metric.value, metric.label === "F&G" ? 0 : 2) : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// Agent Status Grid
function AgentGrid({ agents, vetoActive, vetoReason }: { 
  agents: Record<string, { status: string; age_seconds: number | null; healthy: boolean }>;
  vetoActive?: boolean;
  vetoReason?: string;
}) {
  const agentList = [
    { id: "ingestion", name: "Ingestion", icon: Activity },
    { id: "quant", name: "Quant", icon: TrendingUp },
    { id: "context", name: "Context", icon: Shield },
    { id: "risk", name: "Risk", icon: AlertTriangle },
    { id: "execution", name: "Execution", icon: Zap },
  ];
  
  return (
    <div className="grid grid-cols-5 gap-2">
      {agentList.map((agent) => {
        const a = agents[agent.id];
        const Icon = agent.icon;
        const isHealthy = a?.healthy;
        const isRiskWithVeto = agent.id === 'risk' && vetoActive;
        
        return (
          <div
            key={agent.id}
            className={`p-2 rounded-lg border flex flex-col items-center gap-1 transition-all ${
              isRiskWithVeto 
                ? "border-rose-800 bg-rose-950/30" 
                : isHealthy 
                  ? "border-emerald-800 bg-emerald-950/20" 
                  : "border-red-800 bg-red-950/20"
            }`}
          >
            <Icon className={`w-4 h-4 ${isRiskWithVeto ? "text-rose-400" : isHealthy ? "text-emerald-400" : "text-red-400"}`} />
            <span className="text-[10px] text-slate-400">{agent.name}</span>
            <span className={`text-[9px] ${isRiskWithVeto ? "text-rose-400 font-bold" : isHealthy ? "text-emerald-400" : "text-red-400"}`}>
              {isRiskWithVeto ? "VETO" : a?.age_seconds !== null ? `${Math.round(a.age_seconds)}s` : "—"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// Data Source Status
function DataSourceStatus({ sources }: { sources: Record<string, { status: string; latency_ms: number; last_update: string }> }) {
  const sourceList = Object.entries(sources).slice(0, 12);
  const healthyCount = sourceList.filter(([_, data]) => 
    ["online", "ok", "healthy", "connected", "success", "running"].includes((data.status || "offline").toLowerCase())
  ).length;
  
  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-[10px] text-slate-500">Datenquellen</span>
        <span className={`text-[10px] font-bold ${healthyCount === sourceList.length ? "text-emerald-400" : "text-amber-400"}`}>
          {healthyCount}/{sourceList.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-1">
        {sourceList.map(([name, data]) => {
          const isHealthy = ["online", "ok", "healthy", "connected", "success", "running"].includes((data.status || "offline").toLowerCase());
          
          return (
            <div
              key={name}
              className={`px-2 py-1 rounded text-[9px] border ${
                isHealthy 
                  ? "border-emerald-800 bg-emerald-950/30 text-emerald-400" 
                  : "border-red-800 bg-red-950/30 text-red-400"
              }`}
            >
              {name.replace(/_/g, " ")}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [decisionFeed, setDecisionFeed] = useState<DecisionFeedResponse | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [telRes, posRes, decisionsRes] = await Promise.allSettled([
        fetch("/api/v1/telemetry/live").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        fetch("/api/v1/positions/open").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        fetch("/api/v1/decisions/feed?limit=50").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      ]);

      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (posRes.status === "fulfilled") {
        setPosition(posRes.value.position ?? posRes.value.positions?.[0] ?? null);
        setCurrentPrice(telRes.status === "fulfilled" ? telRes.value.market?.btc_price ?? null : null);
      }
      if (decisionsRes.status === "fulfilled") setDecisionFeed(decisionsRes.value);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 10000);
    return () => clearInterval(iv);
  }, [refresh]);

  if (error) return <div className="min-h-screen bg-[#0a0a0f] text-white p-8 text-red-400">Error: {error}</div>;
  if (!telemetry) return <div className="min-h-screen bg-[#0a0a0f] text-white p-8">Loading...</div>;

  const market = telemetry.market;
  const grss = telemetry.grss.score;
  const isArmed = telemetry.status === "ARMED";

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-2xl font-bold tracking-tight">Bruno Dashboard</h1>
          {telemetry.dry_run && (
            <span className="px-2 py-1 rounded border border-amber-700 bg-amber-950/30 text-amber-400 text-xs font-bold">
              PAPER TRADING
            </span>
          )}
        </div>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isArmed ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
            <span className={`font-bold ${isArmed ? "text-emerald-400" : "text-red-400"}`}>
              {isArmed ? "ARMED" : "HALTED"}
            </span>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold">{fmtPrice(market.btc_price)}</div>
            <div className={`text-sm ${(market.btc_change_24h_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {fmt(market.btc_change_24h_pct, 2)}% 24h
            </div>
          </div>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">GRSS Score</span>
            <Shield className="w-4 h-4 text-slate-600" />
          </div>
          <div className={`text-2xl font-bold ${grss && grss >= 48 ? "text-emerald-400" : grss && grss >= 35 ? "text-amber-400" : "text-red-400"}`}>
            {fmt(grss, 1)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Global Risk Sentiment</div>
        </div>

        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">OFI</span>
            <Zap className="w-4 h-4 text-slate-600" />
          </div>
          <div className={`text-2xl font-bold ${market.ofi && market.ofi > 0.5 ? "text-emerald-400" : market.ofi && market.ofi < 0.3 ? "text-red-400" : "text-amber-400"}`}>
            {fmt(market.ofi, 3)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Order Flow Imbalance</div>
        </div>

        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">VIX</span>
            <AlertTriangle className="w-4 h-4 text-slate-600" />
          </div>
          <div className={`text-2xl font-bold ${market.vix && market.vix > 30 ? "text-red-400" : market.vix && market.vix > 20 ? "text-amber-400" : "text-emerald-400"}`}>
            {fmt(market.vix, 1)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">Volatility Index</div>
        </div>

        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-slate-500 uppercase tracking-wider">Funding</span>
            <Clock className="w-4 h-4 text-slate-600" />
          </div>
          <div className={`text-2xl font-bold ${market.funding_rate && market.funding_rate > 0.01 ? "text-red-400" : market.funding_rate && market.funding_rate < 0 ? "text-emerald-400" : "text-amber-400"}`}>
            {market.funding_rate !== null ? `${(market.funding_rate * 100).toFixed(4)}%` : "—"}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">8h Funding Rate</div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Chart & Position */}
        <div className="lg:col-span-2 space-y-4">
          {/* Chart Placeholder - Will be enhanced with cascade markers */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-300">BTC/USDT Chart</h3>
              <span className="text-[10px] text-slate-500">1h candles with cascade markers</span>
            </div>
            <div className="h-64 bg-[#0a0a0f] rounded-lg border border-[#1a1a2e] flex items-center justify-center text-slate-600">
              <div className="text-center">
                <Activity className="w-12 h-12 mx-auto mb-2 opacity-50" />
                <p className="text-sm">Chart Component</p>
                <p className="text-xs">Will show candles with cascade decision markers</p>
              </div>
            </div>
          </div>

          {/* Open Position */}
          {position?.status === "open" ? (
            <div className={`bg-[#0c0c18] border rounded-xl p-4 ${position.side === "long" ? "border-emerald-800" : "border-red-800"}`}>
              <div className="flex items-center gap-3 mb-3">
                <span className={`w-2 h-2 rounded-full animate-pulse ${position.side === "long" ? "bg-emerald-400" : "bg-red-400"}`} />
                <span className="text-sm font-bold text-white">{position.side.toUpperCase()} {position.symbol}</span>
                <span className="text-[10px] text-slate-500">Qty: {position.quantity}</span>
              </div>
              <div className="grid grid-cols-4 gap-4">
                <div>
                  <div className="text-[10px] text-slate-500">Entry</div>
                  <div className="text-sm font-semibold text-white">{fmtPrice(position.entry_price)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Stop Loss</div>
                  <div className="text-sm font-semibold text-red-400">{fmtPrice(position.stop_loss_price)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Take Profit</div>
                  <div className="text-sm font-semibold text-emerald-400">{fmtPrice(position.take_profit_price)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">P&L</div>
                  <div className={`text-sm font-semibold ${currentPrice && ((currentPrice - position.entry_price) / position.entry_price) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {currentPrice ? `${fmt(((currentPrice - position.entry_price) / position.entry_price) * 100, 2)}%` : "—"}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4 text-center text-sm text-slate-500">
              Keine offene Position
            </div>
          )}
        </div>

        {/* Right Column - System Health & Decisions */}
        <div className="space-y-4">
          {/* Decision Timeline */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-300">Entscheidungszyklen</h3>
              <span className="text-[10px] text-slate-500">Letzte 12 Zyklen</span>
            </div>
            <DecisionTimeline events={decisionFeed?.events ?? []} />
            <div className="flex justify-between mt-2 text-[9px] text-slate-500">
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-sm" /> Signal</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500 rounded-sm" /> Block</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 bg-slate-600 rounded-sm" /> Hold</span>
            </div>
          </div>

          {/* Agent Health */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Agenten-Gesundheit</h3>
            <AgentGrid 
              agents={telemetry.agents} 
              vetoActive={telemetry.veto_active}
              vetoReason={telemetry.veto_reason}
            />
            {telemetry.veto_active && (
              <div className="mt-3 p-2 rounded bg-rose-950/20 border border-rose-800/50">
                <p className="text-[10px] text-rose-400 font-medium">Risk Veto: {telemetry.veto_reason}</p>
              </div>
            )}
          </div>

          {/* Data Sources */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <DataSourceStatus sources={telemetry.data_sources} />
          </div>

          {/* Market Sentiment */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">Markt-Sentiment</h3>
            <SentimentBars market={market} />
          </div>
        </div>
      </div>

      {/* Bottom Row - Veto Info */}
      {!isArmed && telemetry.veto_reason && (
        <div className="bg-red-950/20 border border-red-800 rounded-xl p-4">
          <div className="flex items-center gap-2 text-red-400">
            <XCircle className="w-5 h-5" />
            <span className="font-bold">VETO AKTIV</span>
          </div>
          <div className="mt-1 text-sm text-red-300">{telemetry.veto_reason}</div>
        </div>
      )}
    </div>
  );
}

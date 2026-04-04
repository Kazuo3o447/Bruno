"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Cell,
  PieChart,
  Pie,
  Area,
  AreaChart,
} from "recharts";
import {
  TrendingUp,
  Activity,
  Zap,
  Shield,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronRight,
  BarChart3,
  Settings,
  Monitor,
  Cpu,
  Radio,
  Database,
  Wifi
} from "lucide-react";

// Types
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
  pnl_pct?: number;
}

interface TradePipelineStatus {
  summary: {
    blocking_gates: string[];
    trade_possible: boolean;
    grss_score: number | null;
    vix: number | null;
    data_freshness_active: boolean | null;
    context_timestamp: string | null;
  };
  gates: Record<string, { blocked?: boolean; note?: string }>;
  portfolio: {
    capital_eur: number | null;
    total_trades: number | null;
    daily_pnl_eur: number | null;
  };
  quant_micro: {
    price: number | null;
    ofi: number | null;
    ofi_buy_pressure: number | null;
    source: string | null;
    timestamp: string | null;
  };
}

interface DecisionEvent {
  ts?: string;
  outcome?: string;
  reason?: string;
  regime?: string;
  ofi?: number;
}

interface DecisionFeedResponse {
  events: DecisionEvent[];
  count: number;
  stats: {
    ofi_below_threshold: number;
    cascade_hold: number;
    signals_generated: number;
  };
}

interface PerformanceMetrics {
  daily_return?: number;
  weekly_return?: number;
  win_rate?: number;
  total_pnl?: number;
  profit_factor?: number;
  max_drawdown?: number;
  status: string;
}

// Utility functions
function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}

function fmtPrice(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function timeAgo(isoStr: string | null | undefined): string {
  if (!isoStr) return "—";
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  return `${Math.floor(diff / 3600)}h`;
}

// Components
function StatusCard({ title, value, status, icon: Icon, detail }: { 
  title: string; 
  value: string; 
  status: "success" | "warning" | "error" | "neutral";
  icon: React.ElementType;
  detail?: string;
}) {
  const colors = {
    success: "border-emerald-800 bg-emerald-950/20 text-emerald-400",
    warning: "border-amber-800 bg-amber-950/20 text-amber-400",
    error: "border-red-800 bg-red-950/20 text-red-400",
    neutral: "border-slate-800 bg-slate-950/20 text-slate-400",
  };

  return (
    <div className={`p-4 rounded-xl border ${colors[status]}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-wider text-slate-500">{title}</span>
        <Icon className="w-4 h-4 opacity-60" />
      </div>
      <div className="text-lg font-bold">{value}</div>
      {detail && <div className="text-[10px] mt-1 opacity-70">{detail}</div>}
    </div>
  );
}

export default function Dashboard() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [pipeline, setPipeline] = useState<TradePipelineStatus | null>(null);
  const [decisions, setDecisions] = useState<DecisionFeedResponse | null>(null);
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const refresh = useCallback(async () => {
    try {
      const [telRes, posRes, pipeRes, decRes, perfRes] = await Promise.allSettled([
        fetch("/api/v1/telemetry/live").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/positions/open").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/monitoring/debug/trade-pipeline").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/decisions/feed?limit=20").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/performance/metrics").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
      ]);

      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (posRes.status === "fulfilled") setPosition(posRes.value.position || posRes.value.positions?.[0] || null);
      if (pipeRes.status === "fulfilled") setPipeline(pipeRes.value);
      if (decRes.status === "fulfilled") setDecisions(decRes.value);
      if (perfRes.status === "fulfilled") setPerformance(perfRes.value);

      setLastUpdate(new Date());
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  // Derived data
  const decisionTimeline = useMemo(() => {
    if (!decisions?.events) return [];
    return [...decisions.events].reverse().slice(0, 20).map((e, i) => ({
      time: e.ts ? new Date(e.ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "—",
      signal: e.outcome?.includes("SIGNAL") ? 1 : 0,
      blocked: e.outcome?.includes("HOLD") || e.outcome?.includes("BLOCK") || e.outcome?.includes("VETO") ? 1 : 0,
      ofi: e.ofi || 0,
    }));
  }, [decisions]);

  const marketData = useMemo(() => [
    { label: "BTC Preis", value: fmtPrice(telemetry?.market?.btc_price), change: telemetry?.market?.btc_change_24h_pct },
    { label: "24h Change", value: fmt(telemetry?.market?.btc_change_24h_pct, 2) + "%", change: telemetry?.market?.btc_change_24h_pct },
    { label: "1h Change", value: fmt(telemetry?.market?.btc_change_1h_pct, 2) + "%", change: telemetry?.market?.btc_change_1h_pct },
    { label: "OFI", value: fmt(telemetry?.market?.ofi, 2), change: telemetry?.market?.ofi },
    { label: "Funding", value: telemetry?.market?.funding_rate ? (telemetry.market.funding_rate * 100).toFixed(4) + "%" : "—", change: telemetry?.market?.funding_rate },
    { label: "VIX", value: fmt(telemetry?.market?.vix, 1), change: telemetry?.market?.vix ? -(telemetry.market.vix - 20) : 0 },
  ], [telemetry]);

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] text-white p-8">
        <div className="bg-red-950/30 border border-red-800 rounded-xl p-6">
          <AlertTriangle className="w-8 h-8 text-red-400 mb-2" />
          <h2 className="text-lg font-bold text-red-400">Verbindungsfehler</h2>
          <p className="text-slate-400">{error}</p>
          <button onClick={refresh} className="mt-4 px-4 py-2 bg-red-600 rounded-lg text-sm">Erneut versuchen</button>
        </div>
      </div>
    );
  }

  if (!telemetry) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] text-white p-8 flex items-center justify-center">
        <div className="text-center">
          <Activity className="w-8 h-8 text-indigo-400 animate-pulse mx-auto mb-4" />
          <p className="text-slate-400">Lade Dashboard...</p>
        </div>
      </div>
    );
  }

  const armed = telemetry.status === "ARMED";
  const grss = telemetry.grss?.score;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Dashboard</h1>
            <p className="text-sm text-slate-500">Letzte Aktualisierung: {lastUpdate.toLocaleTimeString("de-DE")}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${armed ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
              {armed ? "ARMED" : "HALTED"}
            </span>
            {telemetry.dry_run && (
              <span className="px-3 py-1 rounded-full text-sm font-medium bg-amber-500/20 text-amber-400">
                PAPER TRADING
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Quick Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
        <StatusCard
          title="System Status"
          value={armed ? "ONLINE" : "PAUSED"}
          status={armed ? "success" : "warning"}
          icon={armed ? CheckCircle : XCircle}
          detail={telemetry.veto_reason || "Keine Veto-Gründe"}
        />
        <StatusCard
          title="GRSS Score"
          value={grss ? grss.toFixed(1) : "—"}
          status={grss && grss >= 40 ? "success" : grss && grss >= 25 ? "warning" : "error"}
          icon={Shield}
          detail={grss && grss >= 48 ? "Risk-On" : "Risk-Off"}
        />
        <StatusCard
          title="BTC Preis"
          value={fmtPrice(telemetry.market.btc_price)}
          status={telemetry.market.btc_change_24h_pct && telemetry.market.btc_change_24h_pct >= 0 ? "success" : "error"}
          icon={TrendingUp}
          detail={`24h: ${fmt(telemetry.market.btc_change_24h_pct, 2)}%`}
        />
        <StatusCard
          title="VIX"
          value={fmt(telemetry.market.vix, 1)}
          status={telemetry.market.vix && telemetry.market.vix > 30 ? "error" : telemetry.market.vix && telemetry.market.vix > 20 ? "warning" : "success"}
          icon={Activity}
          detail={telemetry.market.vix && telemetry.market.vix > 30 ? "High Volatility" : "Normal"}
        />
        <StatusCard
          title="OFI"
          value={fmt(telemetry.market.ofi, 2)}
          status={telemetry.market.ofi && telemetry.market.ofi > 0.3 ? "success" : telemetry.market.ofi && telemetry.market.ofi < -0.3 ? "error" : "neutral"}
          icon={Zap}
          detail="Order Flow Imbalance"
        />
        <StatusCard
          title="Win Rate"
          value={performance?.win_rate ? fmt(performance.win_rate, 1) + "%" : "—"}
          status={performance?.win_rate && performance.win_rate > 50 ? "success" : "neutral"}
          icon={BarChart3}
          detail={`${pipeline?.portfolio?.total_trades || 0} Trades`}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Chart & Position */}
        <div className="lg:col-span-2 space-y-6">
          {/* Chart */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-slate-300">BTC/USDT - Entscheidungszyklen</h3>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500"/> Signal</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500"/> Blocked</span>
              </div>
            </div>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={decisionTimeline}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                  <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} />
                  <YAxis tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} domain={[0, 1]} />
                  <Tooltip 
                    contentStyle={{ background: "#0c0c18", border: "1px solid #1a1a2e", borderRadius: "8px" }}
                    labelStyle={{ color: "#94a3b8" }}
                  />
                  <Area type="step" dataKey="signal" stackId="1" stroke="#10b981" fill="#10b981" fillOpacity={0.3} />
                  <Area type="step" dataKey="blocked" stackId="2" stroke="#ef4444" fill="#ef4444" fillOpacity={0.3} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Position Card */}
          {position?.status === "open" ? (
            <div className={`p-4 rounded-xl border ${position.side === "long" ? "border-emerald-800 bg-emerald-950/10" : "border-red-800 bg-red-950/10"}`}>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs font-bold ${position.side === "long" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
                    {position.side.toUpperCase()}
                  </span>
                  <span className="font-medium">{position.symbol}</span>
                </div>
                <Link href="/trading" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                  Details <ChevronRight className="w-3 h-3" />
                </Link>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Entry</div>
                  <div className="text-sm font-medium">{fmtPrice(position.entry_price)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">Current</div>
                  <div className="text-sm font-medium">{fmtPrice(telemetry.market.btc_price)}</div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">P&L</div>
                  <div className={`text-sm font-medium ${position.pnl_pct && position.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {position.pnl_pct ? fmt(position.pnl_pct, 2) + "%" : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500 uppercase">SL / TP</div>
                  <div className="text-sm font-medium text-slate-300">
                    {fmtPrice(position.stop_loss_price)} / {fmtPrice(position.take_profit_price)}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/20 text-center">
              <p className="text-slate-500 text-sm">Keine offene Position</p>
              <Link href="/trading" className="text-xs text-indigo-400 hover:text-indigo-300 mt-2 inline-block">
                Zur Trading-Ansicht →
              </Link>
            </div>
          )}

          {/* Pipeline Gates */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-slate-300">Entscheidungs-Kaskade</h3>
              <Link href="/trading" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                Vollständige Ansicht <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
              {[
                { name: "Data", check: !pipeline?.gates?.gate_1_data_freshness?.blocked, detail: "Freshness" },
                { name: "Context", check: !pipeline?.gates?.gate_2_context?.blocked, detail: "GRSS" },
                { name: "Sentiment", check: !pipeline?.gates?.gate_3_sentiment?.blocked, detail: "News" },
                { name: "Quant", check: !pipeline?.gates?.gate_4_quant_micro?.blocked, detail: "OFI" },
                { name: "Risk", check: !pipeline?.gates?.gate_5_risk_veto?.blocked, detail: "Vetos" },
                { name: "Portfolio", check: !pipeline?.gates?.gate_6_portfolio?.blocked, detail: "Limits" },
              ].map((gate, i) => (
                <div key={gate.name} className={`p-3 rounded-lg border text-center ${gate.check ? "border-emerald-800 bg-emerald-950/10" : "border-red-800 bg-red-950/10"}`}>
                  <div className={`w-2 h-2 rounded-full mx-auto mb-1 ${gate.check ? "bg-emerald-400" : "bg-red-400"}`} />
                  <div className={`text-xs font-medium ${gate.check ? "text-emerald-400" : "text-red-400"}`}>{gate.name}</div>
                  <div className="text-[9px] text-slate-500">{gate.detail}</div>
                </div>
              ))}
            </div>
            {pipeline?.summary?.blocking_gates && pipeline.summary.blocking_gates.length > 0 && (
              <div className="mt-3 p-2 bg-red-950/20 border border-red-800 rounded-lg text-xs text-red-400">
                Blocked by: {pipeline.summary.blocking_gates.join(" → ")}
              </div>
            )}
          </div>
        </div>

        {/* Right Column - Market & Agents */}
        <div className="space-y-6">
          {/* Market Overview */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-4">Marktdaten</h3>
            <div className="space-y-3">
              {marketData.map((item) => (
                <div key={item.label} className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">{item.label}</span>
                  <span className={`text-sm font-medium ${
                    item.change !== undefined && item.change !== null
                      ? item.change > 0 ? "text-emerald-400" : item.change < 0 ? "text-red-400" : "text-slate-300"
                      : "text-slate-300"
                  }`}>{item.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Agent Status */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-slate-300">Agenten</h3>
              <Link href="/monitor" className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
                <Monitor className="w-3 h-3" />
              </Link>
            </div>
            <div className="space-y-2">
              {["ingestion", "technical", "quant", "context", "risk", "execution"].map((agentId) => {
                const agent = telemetry.agents?.[agentId];
                if (!agent) return null;
                return (
                  <div key={agentId} className="flex items-center justify-between p-2 rounded-lg bg-[#080810]">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${agent.healthy ? "bg-emerald-400" : "bg-red-400"}`} />
                      <span className="text-xs capitalize text-slate-300">{agentId}</span>
                    </div>
                    <span className="text-[10px] text-slate-500">{agent.age_seconds ? Math.round(agent.age_seconds) + "s" : "—"}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Performance Summary */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-4">Performance</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-xs text-slate-500">Daily Return</span>
                <span className={`text-sm ${performance?.daily_return && performance.daily_return >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {performance?.daily_return ? fmt(performance.daily_return, 2) + "%" : "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-slate-500">Weekly Return</span>
                <span className={`text-sm ${performance?.weekly_return && performance.weekly_return >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {performance?.weekly_return ? fmt(performance.weekly_return, 2) + "%" : "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-slate-500">Profit Factor</span>
                <span className={`text-sm ${performance?.profit_factor && performance.profit_factor >= 1.5 ? "text-emerald-400" : "text-amber-400"}`}>
                  {performance?.profit_factor ? fmt(performance.profit_factor, 2) : "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-xs text-slate-500">Max Drawdown</span>
                <span className="text-sm text-red-400">
                  {performance?.max_drawdown ? fmt(performance.max_drawdown, 2) + "%" : "—"}
                </span>
              </div>
            </div>
          </div>

          {/* Quick Links */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-4">Schnellzugriff</h3>
            <div className="space-y-2">
              <Link href="/trading" className="flex items-center justify-between p-2 rounded-lg bg-[#080810] hover:bg-[#0f0f18] transition-colors">
                <span className="text-xs text-slate-300">Trading Details</span>
                <ChevronRight className="w-3 h-3 text-slate-500" />
              </Link>
              <Link href="/monitor" className="flex items-center justify-between p-2 rounded-lg bg-[#080810] hover:bg-[#0f0f18] transition-colors">
                <span className="text-xs text-slate-300">System Monitor</span>
                <ChevronRight className="w-3 h-3 text-slate-500" />
              </Link>
              <Link href="/settings" className="flex items-center justify-between p-2 rounded-lg bg-[#080810] hover:bg-[#0f0f18] transition-colors">
                <span className="text-xs text-slate-300">Einstellungen</span>
                <Settings className="w-3 h-3 text-slate-500" />
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

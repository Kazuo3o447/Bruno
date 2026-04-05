"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  ChevronRight,
  BarChart3,
  Settings,
  Monitor,
  Brain,
  Database,
  Lock,
  PauseCircle,
  Wallet,
  Bitcoin,
  Target,
} from "lucide-react";
import { CandlestickData, UTCTimestamp } from "lightweight-charts";

// Candlestick chart — dynamic import (SSR disable, lightweight-charts needs window)
const TradingChart = dynamic(() => import("@/app/components/TradingChart"), { ssr: false });

// ─── Types ────────────────────────────────────────────────────────────────────

interface Telemetry {
  status: "ARMED" | "HALTED";
  veto_active: boolean;
  veto_reason: string;
  dry_run: boolean;
  grss: {
    score: number | null;
    score_raw?: number | null;
    velocity_30min: number | null;
    deriv_sub?: number | null;
    inst_sub?: number | null;
    sent_sub?: number | null;
    macro_sub?: number | null;
    veto_active: boolean;
  };
  market: {
    btc_price: number | null;
    btc_change_24h_pct: number | null;
    btc_change_1h_pct: number | null;
    ofi: number | null;
    cvd?: number | null;
    max_pain?: number | null;
    max_pain_distance?: number | null;
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
  id: string;
  symbol: string;
  side: "long" | "short";
  entry_price: number;
  quantity: number;
  stop_loss_price: number | null;
  take_profit_1_price: number | null;
  take_profit_2_price: number | null;
  current_price?: number;
  current_pnl_pct?: number;
  current_pnl_eur?: number;
  created_at: string;
}

interface TradePipelineStatus {
  summary: {
    blocking_gates: string[];
    trade_possible: boolean;
    grss_score: number | null;
    vix: number | null;
    data_freshness_active: boolean | null;
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
  };
}

interface DecisionEvent {
  ts?: string;
  outcome?: string;
  reason?: string;
  regime?: string;
  ofi?: number;
  grss_score?: number;
  composite_score?: number;
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
  sharpe_ratio?: number;
  avg_trade_pnl?: number;
  status: string;
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}

function fmtPrice(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtEur(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return "€" + n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function timeAgo(isoStr: string | null | undefined): string {
  if (!isoStr) return "—";
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

// ─── Mini Gate Cascade ────────────────────────────────────────────────────────

const GATES = [
  { key: "gate_1_data_freshness", name: "Data", icon: Database },
  { key: "gate_2_grss_precheck", name: "GRSS", icon: Shield },
  { key: "gate_3_risk_veto", name: "Risk", icon: Lock },
  { key: "gate_4_composite_scorer", name: "Score", icon: Brain },
  { key: "gate_5_position_guard", name: "Position", icon: PauseCircle },
  { key: "gate_6_daily_limit", name: "Limit", icon: BarChart3 },
];

function MiniGateCascade({ pipeline }: { pipeline: TradePipelineStatus | null }) {
  const firstBlockedIdx = GATES.findIndex((g) => pipeline?.gates?.[g.key]?.blocked === true);
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Gate-Kaskade</span>
        <Link href="/trading" className="text-[10px] text-indigo-400 flex items-center gap-0.5">
          Details <ChevronRight className="w-3 h-3" />
        </Link>
      </div>
      <div className="flex items-center gap-1.5 mb-3">
        {GATES.map((gate, i) => {
          const isBlocked = pipeline?.gates?.[gate.key]?.blocked === true;
          const isGreyed = firstBlockedIdx !== -1 && i > firstBlockedIdx;
          return (
            <div key={gate.key} className="flex items-center gap-1">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center border text-[9px] font-bold ${
                  isBlocked
                    ? "border-red-600 bg-red-950/40 text-red-400"
                    : isGreyed
                    ? "border-slate-700 bg-slate-900/30 text-slate-600"
                    : "border-emerald-700 bg-emerald-950/30 text-emerald-400"
                }`}
                title={gate.name}
              >
                {i + 1}
              </div>
              {i < GATES.length - 1 && (
                <ChevronRight className={`w-3 h-3 flex-shrink-0 ${isGreyed || isBlocked ? "text-slate-700" : "text-emerald-800"}`} />
              )}
            </div>
          );
        })}
        <div className={`ml-1 text-xs font-bold px-2 py-0.5 rounded border ${
          pipeline?.summary?.trade_possible
            ? "border-emerald-700 text-emerald-400"
            : "border-red-700 text-red-400"
        }`}>
          {pipeline?.summary?.trade_possible ? "OK" : "BLOCK"}
        </div>
      </div>
      {pipeline?.summary?.blocking_gates && pipeline.summary.blocking_gates.length > 0 && (
        <div className="text-[10px] text-red-400 font-mono">
          ↳ {pipeline.summary.blocking_gates.join(" → ")}
        </div>
      )}
    </div>
  );
}

// ─── Decision Log ─────────────────────────────────────────────────────────────

function outcomeColor(outcome: string | undefined): string {
  if (!outcome) return "text-slate-500";
  const o = outcome.toUpperCase();
  if (o.includes("SIGNAL")) return "text-emerald-400";
  if (o.includes("VETO")) return "text-red-400";
  if (o.includes("HOLD") || o.includes("BLOCK")) return "text-amber-400";
  return "text-slate-400";
}

function outcomeBadge(outcome: string | undefined): string {
  if (!outcome) return "UNKNOWN";
  const o = outcome.toUpperCase();
  if (o.includes("SIGNAL_BUY")) return "BUY";
  if (o.includes("SIGNAL_SELL")) return "SELL";
  if (o.includes("VETO")) return "VETO";
  if (o.includes("HOLD")) return "HOLD";
  if (o.includes("BLOCK")) return "BLOCK";
  return outcome.slice(0, 8);
}

function DecisionLog({ decisions }: { decisions: DecisionFeedResponse | null }) {
  const events = useMemo(() => {
    if (!decisions?.events) return [];
    return [...decisions.events].reverse().slice(0, 12);
  }, [decisions]);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Letzte Entscheidungszyklen</span>
        <div className="flex gap-3 text-[10px] text-slate-600">
          <span className="text-emerald-500">{decisions?.stats?.signals_generated ?? 0} Signals</span>
          <span className="text-red-500">{decisions?.stats?.cascade_hold ?? 0} Hold</span>
        </div>
      </div>
      <div className="space-y-1">
        {events.length === 0 && (
          <div className="text-xs text-slate-600 italic">Keine Daten</div>
        )}
        {events.map((e, i) => (
          <div key={i} className="flex items-center gap-2 py-1 border-b border-[#1a1a2e] last:border-0">
            <span className="text-[10px] text-slate-600 font-mono w-[38px] flex-shrink-0">
              {e.ts ? new Date(e.ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "—"}
            </span>
            <span className={`text-[10px] font-bold font-mono w-[38px] flex-shrink-0 ${outcomeColor(e.outcome)}`}>
              {outcomeBadge(e.outcome)}
            </span>
            <span className="text-[10px] text-slate-500 font-mono flex-shrink-0 w-[34px]">
              {e.grss_score !== undefined ? `G:${e.grss_score.toFixed(0)}` : e.composite_score !== undefined ? `C:${e.composite_score.toFixed(0)}` : ""}
            </span>
            <span className="text-[10px] text-slate-600 truncate">
              {e.reason?.slice(0, 32) || e.regime || ""}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Dashboard ────────────────────────────────────────────────────────────

export default function Dashboard() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [pipeline, setPipeline] = useState<TradePipelineStatus | null>(null);
  const [decisions, setDecisions] = useState<DecisionFeedResponse | null>(null);
  const [performance, setPerformance] = useState<PerformanceMetrics | null>(null);
  const [klines, setKlines] = useState<CandlestickData[]>([]);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const START_CAPITAL = 1000;

  const refresh = useCallback(async () => {
    try {
      const [telRes, posRes, pipeRes, decRes, perfRes] = await Promise.allSettled([
        fetch("/api/v1/telemetry/live").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/positions/open").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/monitoring/debug/trade-pipeline").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/decisions/feed?limit=50").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/performance/metrics").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
      ]);

      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (posRes.status === "fulfilled") setPositions(posRes.value.positions ?? []);
      if (pipeRes.status === "fulfilled") setPipeline(pipeRes.value);
      if (decRes.status === "fulfilled") setDecisions(decRes.value);
      if (perfRes.status === "fulfilled") setPerformance(perfRes.value);

      setLastUpdate(new Date());
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  // Klines — less frequent (every 60s)
  const refreshKlines = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/market/klines/BTCUSDT?limit=120");
      if (res.ok) {
        const raw: { time: number; open: number; high: number; low: number; close: number }[] = await res.json();
        setKlines(raw.map(c => ({
          time: c.time as UTCTimestamp,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })));
      }
    } catch {}
  }, []);

  useEffect(() => {
    refresh();
    refreshKlines();
    const fast = setInterval(refresh, 5000);
    const slow = setInterval(refreshKlines, 60000);
    return () => { clearInterval(fast); clearInterval(slow); };
  }, [refresh, refreshKlines]);

  const deployedEur = useMemo(() => {
    return positions.reduce((sum, p) => sum + p.quantity * (p.current_price ?? p.entry_price), 0);
  }, [positions]);

  const cashEur = pipeline?.portfolio?.capital_eur ?? START_CAPITAL;
  const dailyPnl = pipeline?.portfolio?.daily_pnl_eur ?? 0;
  const totalTrades = pipeline?.portfolio?.total_trades ?? 0;

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
      <div className="min-h-screen bg-[#0a0a0f] text-white flex items-center justify-center">
        <Activity className="w-8 h-8 text-indigo-400 animate-pulse" />
      </div>
    );
  }

  const armed = telemetry.status === "ARMED";
  const grss = telemetry.grss?.score;
  const market = telemetry.market;
  const pos = positions[0] ?? null;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6 space-y-4">

      {/* ── Header ──────────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between rounded-xl border border-[#1a1a2e] bg-[#0c0c18] px-5 py-3">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.28em] text-slate-500 font-bold">Bruno · Dashboard</div>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-xl font-bold font-mono text-white">{fmtPrice(market.btc_price)}</span>
              <span className={`text-sm font-mono ${market.btc_change_24h_pct && market.btc_change_24h_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {market.btc_change_24h_pct && market.btc_change_24h_pct >= 0 ? "▲" : "▼"} {fmt(market.btc_change_24h_pct, 2)}% 24h
              </span>
              <span className={`text-sm font-mono hidden md:inline ${market.btc_change_1h_pct && market.btc_change_1h_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {market.btc_change_1h_pct && market.btc_change_1h_pct >= 0 ? "▲" : "▼"} {fmt(market.btc_change_1h_pct, 2)}% 1h
              </span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <span className={`text-xs font-bold px-3 py-1 rounded-full border ${
            armed ? "border-emerald-700 bg-emerald-950/30 text-emerald-400" : "border-red-700 bg-red-950/30 text-red-400"
          }`}>{telemetry.status}</span>
          {telemetry.dry_run && (
            <span className="text-xs font-bold px-3 py-1 rounded-full border border-amber-700 bg-amber-950/30 text-amber-400">PAPER</span>
          )}
          <span className="text-[10px] text-slate-600">{lastUpdate.toLocaleTimeString("de-DE")}</span>
        </div>
      </div>

      {/* ── Row 1: KPI Cards ────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {/* GRSS */}
        <div className={`bg-[#0c0c18] border rounded-xl p-3 ${
          grss && grss >= 48 ? "border-emerald-800" : grss && grss >= 25 ? "border-amber-800" : "border-red-800"
        }`}>
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Shield className="w-3 h-3" /> GRSS Score
          </div>
          <div className={`text-xl font-bold font-mono ${
            grss && grss >= 48 ? "text-emerald-400" : grss && grss >= 25 ? "text-amber-400" : "text-red-400"
          }`}>{grss?.toFixed(1) ?? "—"}</div>
          <div className="text-[10px] text-slate-600 mt-0.5">{grss && grss >= 48 ? "Risk-On" : grss && grss >= 25 ? "Neutral" : "Risk-Off"}</div>
        </div>

        {/* VIX */}
        <div className={`bg-[#0c0c18] border rounded-xl p-3 ${
          market.vix && market.vix > 30 ? "border-red-800" : market.vix && market.vix > 20 ? "border-amber-800" : "border-slate-800"
        }`}>
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Activity className="w-3 h-3" /> VIX
          </div>
          <div className={`text-xl font-bold font-mono ${
            market.vix && market.vix > 30 ? "text-red-400" : market.vix && market.vix > 20 ? "text-amber-400" : "text-slate-300"
          }`}>{fmt(market.vix, 1)}</div>
          <div className="text-[10px] text-slate-600 mt-0.5">{market.vix && market.vix > 30 ? "High Vol" : "Normal"}</div>
        </div>

        {/* OFI */}
        <div className="bg-[#0c0c18] border border-slate-800 rounded-xl p-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Zap className="w-3 h-3" /> OFI
          </div>
          <div className={`text-xl font-bold font-mono ${
            market.ofi && market.ofi > 0.3 ? "text-emerald-400" : market.ofi && market.ofi < -0.3 ? "text-red-400" : "text-slate-300"
          }`}>{fmt(market.ofi, 3)}</div>
          <div className="text-[10px] text-slate-600 mt-0.5">Order Flow</div>
        </div>

        {/* Cash / Deployed */}
        <div className="bg-[#0c0c18] border border-slate-800 rounded-xl p-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Wallet className="w-3 h-3" /> Kapital
          </div>
          <div className="text-xl font-bold font-mono text-emerald-400">{fmtEur(cashEur)}</div>
          <div className="text-[10px] text-slate-600 mt-0.5">
            {deployedEur > 0 ? `+ ${fmtEur(deployedEur)} deployed` : "€1.000 Start"}
          </div>
        </div>

        {/* Daily P&L */}
        <div className={`bg-[#0c0c18] border rounded-xl p-3 ${dailyPnl >= 0 ? "border-emerald-900" : "border-red-900"}`}>
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
            {dailyPnl >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />} Daily P&L
          </div>
          <div className={`text-xl font-bold font-mono ${dailyPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {dailyPnl >= 0 ? "+" : ""}{fmtEur(dailyPnl)}
          </div>
          <div className="text-[10px] text-slate-600 mt-0.5">{totalTrades} Trades</div>
        </div>

        {/* Win Rate */}
        <div className="bg-[#0c0c18] border border-slate-800 rounded-xl p-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
            <BarChart3 className="w-3 h-3" /> Win Rate
          </div>
          <div className={`text-xl font-bold font-mono ${performance?.win_rate && performance.win_rate > 50 ? "text-emerald-400" : "text-slate-300"}`}>
            {performance?.win_rate ? fmt(performance.win_rate, 1) + "%" : "—"}
          </div>
          <div className="text-[10px] text-slate-600 mt-0.5">PF: {performance?.profit_factor ? fmt(performance.profit_factor, 2) : "—"}</div>
        </div>
      </div>

      {/* ── Row 2: Chart + Performance + Position ───────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Candlestick Chart — 2/3 */}
        <div className="xl:col-span-2 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 pt-4 pb-2">
            <div>
              <span className="text-xs font-bold uppercase tracking-widest text-slate-400">BTC/USDT · 1h Kerzen</span>
              {klines.length === 0 && (
                <span className="ml-2 text-[10px] text-amber-500">Demo-Daten (keine DB-Verbindung)</span>
              )}
            </div>
            <span className="text-[10px] text-slate-600">{klines.length > 0 ? `${klines.length} Kerzen` : ""}</span>
          </div>
          <div className="h-[300px]">
            <TradingChart
              symbol="BTC/USDT"
              data={klines.length > 0 ? klines : undefined}
              height={280}
              compact={true}
            />
          </div>
        </div>

        {/* Performance + Position — 1/3 */}
        <div className="space-y-3">
          {/* Performance Metrics */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Performance</span>
              <Link href="/monitor" className="text-[10px] text-indigo-400 flex items-center gap-0.5">
                Details <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="space-y-2.5">
              {[
                { label: "Daily Return", value: performance?.daily_return ? (performance.daily_return >= 0 ? "+" : "") + fmt(performance.daily_return, 2) + "%" : "—", color: performance?.daily_return !== undefined && performance.daily_return !== null ? (performance.daily_return >= 0 ? "text-emerald-400" : "text-red-400") : "text-slate-400" },
                { label: "Weekly Return", value: performance?.weekly_return ? (performance.weekly_return >= 0 ? "+" : "") + fmt(performance.weekly_return, 2) + "%" : "—", color: performance?.weekly_return !== undefined && performance.weekly_return !== null ? (performance.weekly_return >= 0 ? "text-emerald-400" : "text-red-400") : "text-slate-400" },
                { label: "Total P&L", value: performance?.total_pnl ? fmtEur(performance.total_pnl) : "—", color: performance?.total_pnl !== undefined && performance.total_pnl !== null ? (performance.total_pnl >= 0 ? "text-emerald-400" : "text-red-400") : "text-slate-400" },
                { label: "Profit Factor", value: performance?.profit_factor ? fmt(performance.profit_factor, 2) : "—", color: performance?.profit_factor && performance.profit_factor >= 1.5 ? "text-emerald-400" : "text-amber-400" },
                { label: "Sharpe Ratio", value: performance?.sharpe_ratio ? fmt(performance.sharpe_ratio, 2) : "—", color: performance?.sharpe_ratio && performance.sharpe_ratio >= 1 ? "text-emerald-400" : "text-slate-400" },
                { label: "Max Drawdown", value: performance?.max_drawdown ? fmt(performance.max_drawdown, 2) + "%" : "—", color: "text-red-400" },
                { label: "Avg Trade P&L", value: performance?.avg_trade_pnl ? fmtEur(performance.avg_trade_pnl) : "—", color: "text-slate-300" },
              ].map((row) => (
                <div key={row.label} className="flex justify-between items-center">
                  <span className="text-xs text-slate-500">{row.label}</span>
                  <span className={`text-xs font-mono font-semibold ${row.color}`}>{row.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Active Position summary */}
          <div className={`bg-[#0c0c18] border rounded-xl p-4 ${pos ? (pos.side === "long" ? "border-emerald-900" : "border-red-900") : "border-[#1a1a2e]"}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-1.5">
                <Target className="w-3.5 h-3.5 text-indigo-400" /> Position
              </span>
              <Link href="/trading" className="text-[10px] text-indigo-400 flex items-center gap-0.5">
                Details <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            {pos ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded border ${
                    pos.side === "long"
                      ? "border-emerald-700 bg-emerald-950/30 text-emerald-400"
                      : "border-red-700 bg-red-950/30 text-red-400"
                  }`}>{pos.side.toUpperCase()}</span>
                  <span className="text-sm font-bold font-mono text-white">{pos.symbol}</span>
                  <span className={`ml-auto text-lg font-bold font-mono ${(pos.current_pnl_pct ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {(pos.current_pnl_pct ?? 0) >= 0 ? "+" : ""}{((pos.current_pnl_pct ?? 0) * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-slate-500">Entry</span>
                    <div className="font-mono text-slate-300">{fmtPrice(pos.entry_price)}</div>
                  </div>
                  <div>
                    <span className="text-slate-500">Current</span>
                    <div className="font-mono text-slate-300">{fmtPrice(pos.current_price ?? market.btc_price)}</div>
                  </div>
                  <div>
                    <span className="text-slate-500">BTC</span>
                    <div className="font-mono text-slate-300">{pos.quantity} BTC</div>
                  </div>
                  <div>
                    <span className="text-slate-500">P&L EUR</span>
                    <div className={`font-mono ${(pos.current_pnl_eur ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {(pos.current_pnl_eur ?? 0) >= 0 ? "+" : ""}{fmtEur(pos.current_pnl_eur)}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-2">
                <p className="text-slate-600 text-xs">Keine offene Position</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Row 3: Market Data + Gate Cascade + Agents ──────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* Market Data */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Marktdaten</div>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
            {[
              { label: "BTC Preis", value: fmtPrice(market.btc_price), color: "text-white" },
              { label: "Fear & Greed", value: fmt(market.fear_greed, 0), color: market.fear_greed && market.fear_greed > 75 ? "text-red-400" : market.fear_greed && market.fear_greed < 25 ? "text-emerald-400" : "text-slate-300" },
              { label: "Funding Rate", value: market.funding_rate ? (market.funding_rate * 100).toFixed(4) + "%" : "—", color: market.funding_rate && market.funding_rate > 0.01 ? "text-red-400" : "text-slate-300" },
              { label: "Put/Call", value: fmt(market.put_call_ratio, 2), color: market.put_call_ratio && market.put_call_ratio > 0.9 ? "text-red-400" : "text-slate-300" },
              { label: "DVOL", value: fmt(market.dvol, 1), color: "text-slate-300" },
              { label: "OI Delta", value: fmt(market.oi_delta_pct, 1) + "%", color: market.oi_delta_pct && market.oi_delta_pct > 5 ? "text-red-400" : "text-slate-300" },
              { label: "L/S Ratio", value: fmt(market.long_short_ratio, 2), color: "text-slate-300" },
              { label: "Retail Score", value: fmt(market.retail_score, 0), color: "text-slate-300" },
              { label: "CVD", value: fmt(market.cvd, 0), color: market.cvd && market.cvd > 0 ? "text-emerald-400" : "text-red-400" },
              { label: "Sentiment", value: fmt(market.sentiment, 2), color: market.sentiment && market.sentiment > 0.2 ? "text-emerald-400" : market.sentiment && market.sentiment < -0.2 ? "text-red-400" : "text-slate-300" },
              { label: "Max Pain", value: fmtPrice(market.max_pain), color: "text-slate-300" },
              { label: "Max Pain Dist.", value: market.max_pain_distance ? fmt(market.max_pain_distance, 1) + "%" : "—", color: "text-slate-300" },
            ].map((item) => (
              <div key={item.label} className="flex justify-between items-center text-xs border-b border-[#1a1a2e] pb-1">
                <span className="text-slate-500">{item.label}</span>
                <span className={`font-mono font-semibold ${item.color}`}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Gate Cascade + GRSS Breakdown */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4 space-y-5">
          <MiniGateCascade pipeline={pipeline} />

          <div className="border-t border-[#1a1a2e] pt-4">
            <div className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">GRSS Breakdown</div>
            <div className="space-y-2.5">
              {[
                { label: "Derivate", value: telemetry.grss.deriv_sub },
                { label: "Institutional", value: telemetry.grss.inst_sub },
                { label: "Sentiment", value: telemetry.grss.sent_sub },
                { label: "Macro", value: telemetry.grss.macro_sub },
              ].map((sub) => (
                <div key={sub.label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-500">{sub.label}</span>
                    <span className={sub.value && sub.value > 0 ? "text-emerald-400" : sub.value && sub.value < 0 ? "text-red-400" : "text-slate-500"}>
                      {sub.value !== null && sub.value !== undefined ? (sub.value > 0 ? "+" : "") + sub.value.toFixed(1) : "—"}
                    </span>
                  </div>
                  <div className="h-1 w-full bg-slate-900 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${sub.value && sub.value > 0 ? "bg-emerald-600" : "bg-red-600"}`}
                      style={{ width: `${Math.min(100, Math.abs((sub.value || 0) / 25) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Velocity */}
          <div className="border-t border-[#1a1a2e] pt-3">
            <div className="flex justify-between text-xs">
              <span className="text-slate-500">GRSS Velocity 30min</span>
              <span className={`font-mono ${telemetry.grss.velocity_30min && telemetry.grss.velocity_30min > 0 ? "text-emerald-400" : "text-red-400"}`}>
                {telemetry.grss.velocity_30min ? (telemetry.grss.velocity_30min > 0 ? "▲" : "▼") + " " + fmt(telemetry.grss.velocity_30min, 2) : "—"}
              </span>
            </div>
          </div>
        </div>

        {/* Agents + Decision Log */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4 space-y-5">
          {/* Agents */}
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold uppercase tracking-widest text-slate-400">Agenten</span>
              <Link href="/monitor" className="text-[10px] text-indigo-400 flex items-center gap-0.5">
                Monitor <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {["ingestion", "technical", "quant", "context", "risk", "execution"].map((agentId) => {
                const agent = telemetry.agents?.[agentId];
                if (!agent) return null;
                return (
                  <div key={agentId} className="flex items-center gap-2 px-2 py-1.5 rounded bg-[#080810]">
                    <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${agent.healthy ? "bg-emerald-400" : "bg-red-400 animate-pulse"}`} />
                    <span className="text-[11px] capitalize text-slate-300 flex-1">{agentId}</span>
                    <span className="text-[10px] text-slate-600 font-mono">{agent.age_seconds ? Math.round(agent.age_seconds) + "s" : "—"}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Decision Log */}
          <div className="border-t border-[#1a1a2e] pt-4">
            <DecisionLog decisions={decisions} />
          </div>
        </div>
      </div>

      {/* ── Quick Links ─────────────────────────────────────────────────────── */}
      <div className="flex gap-3 flex-wrap">
        {[
          { href: "/trading", label: "Trading Cockpit", icon: BarChart3 },
          { href: "/monitor", label: "System Monitor", icon: Monitor },
          { href: "/settings", label: "Einstellungen", icon: Settings },
        ].map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#0c0c18] border border-[#1a1a2e] hover:border-indigo-800 hover:bg-indigo-950/20 transition-colors text-xs text-slate-400 hover:text-slate-200"
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
            <ChevronRight className="w-3 h-3 opacity-50" />
          </Link>
        ))}
      </div>
    </div>
  );
}

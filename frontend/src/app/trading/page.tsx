"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  Shield,
  Clock,
  AlertTriangle,
  CheckCircle,
  XCircle,
  BarChart3,
  Brain,
  Database,
  Lock,
  Unlock,
  PauseCircle,
  ArrowRight,
  Target,
  Wallet,
  Bitcoin,
  ChevronRight,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface Telemetry {
  status: "ARMED" | "HALTED";
  veto_active: boolean;
  veto_reason: string;
  dry_run: boolean;
  live_trading_approved: boolean;
  portfolio?: {
    capital_eur: number;
    total_trades: number;
    daily_pnl_eur: number;
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
  grss: {
    score: number | null;
    score_raw?: number | null;
    velocity_30min: number | null;
  };
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
  portfolio: {
    capital_eur: number;
    total_trades: number;
    daily_pnl_eur: number;
  };
  gates: Record<string, {
    blocked?: boolean;
    note?: string;
    [key: string]: any;
  }>;
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

interface Position {
  id: string;
  symbol: string;
  side: "long" | "short";
  entry_price: number;
  quantity: number;
  stop_loss_price: number | null;
  take_profit_1_price: number | null;
  take_profit_2_price: number | null;
  tp1_hit: boolean;
  breakeven_active?: boolean;
  atr_trailing_enabled: boolean;
  current_price?: number;
  current_pnl_pct?: number;
  current_pnl_eur?: number;
  created_at: string;
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}

function fmtEur(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return "€" + n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
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

function positionDuration(createdAt: string): string {
  const diff = Math.floor((Date.now() - new Date(createdAt).getTime()) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ${diff % 60}s`;
  const h = Math.floor(diff / 3600);
  const m = Math.floor((diff % 3600) / 60);
  return `${h}h ${m}m`;
}

// ─── Gate Cascade ─────────────────────────────────────────────────────────────

const GATES = [
  { key: "gate_1_data_freshness", name: "Data", fullName: "Data Freshness", icon: Database },
  { key: "gate_2_grss_precheck", name: "GRSS", fullName: "GRSS Pre-Check", icon: Shield },
  { key: "gate_3_risk_veto", name: "Risk", fullName: "Risk Veto", icon: Lock },
  { key: "gate_4_composite_scorer", name: "Score", fullName: "Composite Scorer", icon: Brain },
  { key: "gate_5_position_guard", name: "Position", fullName: "Position Guard", icon: PauseCircle },
  { key: "gate_6_daily_limit", name: "Limit", fullName: "Daily Limit", icon: BarChart3 },
];

function GateCascade({ pipeline }: { pipeline: TradePipelineStatus | null }) {
  const firstBlockedIdx = GATES.findIndex(
    (g) => pipeline?.gates?.[g.key]?.blocked === true
  );

  return (
    <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Entscheidungs-Kaskade</h3>
        <span className={`text-xs font-bold px-3 py-1 rounded-full border ${
          pipeline?.summary?.trade_possible
            ? "border-emerald-700 bg-emerald-950/30 text-emerald-400"
            : "border-red-700 bg-red-950/30 text-red-400"
        }`}>
          {pipeline?.summary?.trade_possible ? "TRADE MÖGLICH" : "BLOCKIERT"}
        </span>
      </div>

      {/* Horizontal chain */}
      <div className="flex items-start gap-1 overflow-x-auto pb-2">
        {GATES.map((gate, i) => {
          const gateData = pipeline?.gates?.[gate.key];
          const isBlocked = gateData?.blocked === true;
          const isGreyed = firstBlockedIdx !== -1 && i > firstBlockedIdx;
          const Icon = gate.icon;

          return (
            <div key={gate.key} className="flex items-start gap-1 flex-shrink-0">
              <div className={`flex flex-col items-center gap-1.5 w-[88px]`}>
                <div className={`w-9 h-9 rounded-full flex items-center justify-center border-2 transition-all ${
                  isBlocked
                    ? "border-red-500 bg-red-950/30"
                    : isGreyed
                    ? "border-slate-700 bg-slate-900/30"
                    : "border-emerald-500 bg-emerald-950/30"
                }`}>
                  {isBlocked ? (
                    <XCircle className="w-4 h-4 text-red-400 animate-pulse" />
                  ) : isGreyed ? (
                    <Icon className="w-4 h-4 text-slate-600" />
                  ) : (
                    <CheckCircle className="w-4 h-4 text-emerald-400" />
                  )}
                </div>
                <span className={`text-[10px] font-semibold text-center leading-tight ${
                  isBlocked ? "text-red-400" : isGreyed ? "text-slate-600" : "text-emerald-400"
                }`}>{gate.fullName}</span>
                {gateData?.note && isBlocked && (
                  <span className="text-[9px] text-red-300/80 text-center leading-tight max-w-[88px]">{gateData.note}</span>
                )}
              </div>
              {i < GATES.length - 1 && (
                <div className={`mt-4 flex-shrink-0 ${isGreyed || isBlocked ? "text-slate-700" : "text-emerald-800"}`}>
                  <ChevronRight className="w-4 h-4" />
                </div>
              )}
            </div>
          );
        })}

        {/* Final result */}
        <div className="flex items-start gap-1 flex-shrink-0">
          <div className={`mt-4 flex-shrink-0 ${pipeline?.summary?.trade_possible ? "text-emerald-800" : "text-slate-700"}`}>
            <ChevronRight className="w-4 h-4" />
          </div>
          <div className={`w-9 h-9 mt-0 rounded-full flex items-center justify-center border-2 ${
            pipeline?.summary?.trade_possible
              ? "border-emerald-400 bg-emerald-900/40"
              : "border-slate-700 bg-slate-900/20"
          }`}>
            {pipeline?.summary?.trade_possible
              ? <Unlock className="w-4 h-4 text-emerald-400" />
              : <Lock className="w-4 h-4 text-slate-600" />
            }
          </div>
        </div>
      </div>

      {/* Blocking details */}
      {pipeline?.summary?.blocking_gates && pipeline.summary.blocking_gates.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[#1a1a2e] text-xs text-red-400">
          Blockiert durch: <span className="font-mono">{pipeline.summary.blocking_gates.join(" → ")}</span>
        </div>
      )}

      {/* Key metrics row */}
      <div className="mt-3 pt-3 border-t border-[#1a1a2e] flex flex-wrap gap-4 text-xs text-slate-500">
        <span>GRSS: <span className="text-slate-300 font-mono">{fmt(pipeline?.summary?.grss_score, 1)}</span></span>
        <span>VIX: <span className="text-slate-300 font-mono">{fmt(pipeline?.summary?.vix, 1)}</span></span>
        <span>OFI: <span className="text-slate-300 font-mono">{fmt(pipeline?.quant_micro?.ofi, 3)}</span></span>
        <span>Buy Pressure: <span className="text-slate-300 font-mono">{fmt(pipeline?.quant_micro?.ofi_buy_pressure, 3)}</span></span>
        <span>Data Fresh: <span className={`font-mono ${pipeline?.summary?.data_freshness_active ? "text-emerald-400" : "text-red-400"}`}>{String(pipeline?.summary?.data_freshness_active ?? false)}</span></span>
        <span>Ctx: <span className="text-slate-300 font-mono">{pipeline?.summary?.context_timestamp ? new Date(pipeline.summary.context_timestamp).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "—"}</span></span>
      </div>
    </div>
  );
}

// ─── Position Card ─────────────────────────────────────────────────────────────

function PositionCard({ pos }: { pos: Position }) {
  const currentPrice = pos.current_price ?? pos.entry_price;
  const valueEur = pos.quantity * currentPrice;
  const entryValueEur = pos.quantity * pos.entry_price;
  const pnlPct = pos.current_pnl_pct ?? 0;
  const pnlEur = pos.current_pnl_eur ?? 0;
  const isWin = pnlPct >= 0;

  // TP progress: entry → TP1 → TP2
  const tp1 = pos.take_profit_1_price;
  const tp2 = pos.take_profit_2_price;
  const sl = pos.stop_loss_price;

  // Progress bar for price between SL and TP2
  let progressPct = 50;
  if (sl && tp2) {
    const range = tp2 - sl;
    if (range > 0) {
      progressPct = Math.max(0, Math.min(100, ((currentPrice - sl) / range) * 100));
    }
  }

  const tp1Pct = sl && tp1 && tp2 ? Math.max(0, Math.min(100, ((tp1 - sl) / (tp2 - sl)) * 100)) : 66;

  return (
    <div className={`bg-[#0c0c18] rounded-xl border-l-4 border border-[#1a1a2e] p-5 ${
      pos.side === "long" ? "border-l-emerald-500" : "border-l-red-500"
    }`}>
      {/* Header row */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div>
            <span className="text-lg font-bold text-white font-mono">{pos.symbol}</span>
            <span className={`ml-2 text-xs font-bold px-2 py-0.5 rounded uppercase ${
              pos.side === "long"
                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                : "bg-red-500/15 text-red-400 border border-red-500/30"
            }`}>{pos.side}</span>
          </div>
        </div>
        <div className="text-right">
          <div className={`text-2xl font-bold font-mono ${isWin ? "text-emerald-400" : "text-red-400"}`}>
            {isWin ? "+" : ""}{(pnlPct * 100).toFixed(2)}%
          </div>
          <div className={`text-sm font-mono ${isWin ? "text-emerald-500" : "text-red-500"}`}>
            {isWin ? "+" : ""}{fmtEur(pnlEur)}
          </div>
        </div>
      </div>

      {/* Key metrics grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-slate-900/40 rounded-lg p-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Bitcoin className="w-3 h-3" /> BTC Menge
          </div>
          <div className="text-sm font-bold font-mono text-white">{pos.quantity} BTC</div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{fmtEur(valueEur)}</div>
        </div>
        <div className="bg-slate-900/40 rounded-lg p-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Entry Price</div>
          <div className="text-sm font-bold font-mono text-slate-200">{fmtPrice(pos.entry_price)}</div>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">{fmtEur(entryValueEur)}</div>
        </div>
        <div className="bg-slate-900/40 rounded-lg p-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Current Price</div>
          <div className="text-sm font-bold font-mono text-white">{fmtPrice(currentPrice)}</div>
          <div className={`text-[10px] font-mono mt-0.5 ${currentPrice > pos.entry_price ? "text-emerald-500" : "text-red-500"}`}>
            {currentPrice > pos.entry_price ? "▲" : "▼"} {Math.abs(((currentPrice - pos.entry_price) / pos.entry_price) * 100).toFixed(2)}%
          </div>
        </div>
        <div className="bg-slate-900/40 rounded-lg p-3">
          <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">Laufzeit</div>
          <div className="text-sm font-bold font-mono text-slate-200">{positionDuration(pos.created_at)}</div>
          <div className="text-[10px] text-slate-500 mt-0.5">{new Date(pos.created_at).toLocaleTimeString("de-DE")}</div>
        </div>
      </div>

      {/* SL → Current → TP1 → TP2 progress bar */}
      <div className="mb-3">
        <div className="flex justify-between text-[10px] text-slate-500 mb-1 font-mono">
          <span className="text-red-400">SL {sl ? fmtPrice(sl) : "—"}</span>
          <span className="text-slate-400">Current {fmtPrice(currentPrice)}</span>
          <span className={tp1 && pos.tp1_hit ? "text-emerald-400 line-through opacity-50" : "text-amber-400"}>TP1 {tp1 ? fmtPrice(tp1) : "—"}</span>
          <span className="text-emerald-400">TP2 {tp2 ? fmtPrice(tp2) : "—"}</span>
        </div>
        <div className="relative h-2 rounded-full bg-slate-800 overflow-hidden">
          {/* TP1 marker */}
          <div className="absolute top-0 bottom-0 w-0.5 bg-amber-500/60 z-10" style={{ left: `${tp1Pct}%` }} />
          {/* Progress fill */}
          <div
            className={`h-full rounded-full transition-all ${isWin ? "bg-emerald-500" : "bg-red-500"}`}
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Status badges */}
      <div className="flex flex-wrap gap-2">
        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${
          pos.tp1_hit
            ? "border-emerald-700 bg-emerald-950/30 text-emerald-400"
            : "border-slate-700 bg-slate-900/30 text-slate-500"
        }`}>TP1 {pos.tp1_hit ? "✓ Hit" : "Pending"}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${
          pos.breakeven_active
            ? "border-blue-700 bg-blue-950/30 text-blue-400"
            : "border-slate-700 bg-slate-900/30 text-slate-500"
        }`}>Breakeven {pos.breakeven_active ? "✓ Aktiv" : "Inaktiv"}</span>
        <span className={`text-[10px] px-2 py-0.5 rounded border font-mono ${
          pos.atr_trailing_enabled
            ? "border-orange-700 bg-orange-950/30 text-orange-400"
            : "border-slate-700 bg-slate-900/30 text-slate-500"
        }`}>ATR Trailing {pos.atr_trailing_enabled ? "✓ Aktiv" : "Inaktiv"}</span>
        <span className="text-[10px] px-2 py-0.5 rounded border border-slate-700 bg-slate-900/30 text-slate-500 font-mono">
          ID: {pos.id.slice(0, 8)}
        </span>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────

export default function TradingPage() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [pipeline, setPipeline] = useState<TradePipelineStatus | null>(null);
  const [decisions, setDecisions] = useState<DecisionFeedResponse | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [refreshing, setRefreshing] = useState(false);

  const START_CAPITAL = 1000;

  const deployedEur = useMemo(() => {
    return positions.reduce((sum, p) => {
      const price = p.current_price ?? p.entry_price;
      return sum + p.quantity * price;
    }, 0);
  }, [positions]);

  const cashEur = pipeline?.portfolio?.capital_eur ?? telemetry?.portfolio?.capital_eur ?? START_CAPITAL;
  const dailyPnl = pipeline?.portfolio?.daily_pnl_eur ?? telemetry?.portfolio?.daily_pnl_eur ?? 0;
  const totalTrades = pipeline?.portfolio?.total_trades ?? telemetry?.portfolio?.total_trades ?? 0;
  const capitalUtilPct = Math.min(100, (deployedEur / START_CAPITAL) * 100);

  const decisionTimeline = useMemo(() => {
    if (!decisions?.events) return [];
    return [...decisions.events].reverse().slice(0, 30).map((e) => ({
      time: e.ts ? new Date(e.ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "—",
      signal: e.outcome?.includes("SIGNAL_BUY") ? 1 : e.outcome?.includes("SIGNAL_SELL") ? -1 : 0,
      grss: e.grss_score ?? e.composite_score ?? 0,
    }));
  }, [decisions]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const [telRes, pipeRes, decRes, posRes] = await Promise.allSettled([
        fetch("/api/v1/telemetry/live").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/monitoring/debug/trade-pipeline").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/decisions/feed?limit=50").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/positions/open").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
      ]);

      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (pipeRes.status === "fulfilled") setPipeline(pipeRes.value);
      if (decRes.status === "fulfilled") setDecisions(decRes.value);
      if (posRes.status === "fulfilled") setPositions(posRes.value.positions ?? []);

      setLastUpdate(new Date());
      setError("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  if (error) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] text-white p-8">
        <div className="bg-red-950/30 border border-red-800 rounded-xl p-6">
          <AlertTriangle className="w-8 h-8 text-red-400 mb-2" />
          <h2 className="text-lg font-bold text-red-400">Verbindungsfehler</h2>
          <p className="text-slate-400">{error}</p>
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
  const market = telemetry.market;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6 space-y-4">

      {/* ── Zone 1: Header Bar ──────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 rounded-xl border border-[#1a1a2e] bg-[#0c0c18] px-5 py-3">
        <div className="flex items-center gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.28em] text-slate-500 font-bold">Bruno · Trading Cockpit</div>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-2xl font-bold font-mono text-white">{fmtPrice(market.btc_price)}</span>
              <span className={`text-sm font-mono ${market.btc_change_24h_pct && market.btc_change_24h_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {market.btc_change_24h_pct && market.btc_change_24h_pct >= 0 ? "▲" : "▼"} {fmt(market.btc_change_24h_pct, 2)}% 24h
              </span>
              <span className={`text-sm font-mono ${market.btc_change_1h_pct && market.btc_change_1h_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {market.btc_change_1h_pct && market.btc_change_1h_pct >= 0 ? "▲" : "▼"} {fmt(market.btc_change_1h_pct, 2)}% 1h
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <span className={`text-xs font-bold px-3 py-1.5 rounded-full border ${
            armed
              ? "border-emerald-700 bg-emerald-950/30 text-emerald-400"
              : "border-red-700 bg-red-950/30 text-red-400"
          }`}>{telemetry.status}</span>

          {telemetry.dry_run && (
            <span className="text-xs font-bold px-3 py-1.5 rounded-full border border-amber-700 bg-amber-950/30 text-amber-400">
              DRY RUN
            </span>
          )}

          {telemetry.veto_active && (
            <span className="text-xs font-bold px-3 py-1.5 rounded-full border border-red-700 bg-red-950/30 text-red-400 max-w-[200px] truncate" title={telemetry.veto_reason}>
              VETO: {telemetry.veto_reason?.slice(0, 20)}
            </span>
          )}

          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <div className={`w-1.5 h-1.5 rounded-full ${refreshing ? "bg-indigo-400 animate-pulse" : "bg-slate-600"}`} />
            {lastUpdate.toLocaleTimeString("de-DE")}
          </div>
        </div>
      </div>

      {/* ── Zone 2: Portfolio Overview ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Startkapital */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Wallet className="w-4 h-4 text-slate-500" />
            <span className="text-[10px] uppercase tracking-wider text-slate-500">Startkapital</span>
          </div>
          <div className="text-xl font-bold text-white font-mono">€{START_CAPITAL.toLocaleString("de-DE")}</div>
          <div className="text-[10px] text-slate-500 mt-1">Paper Trading · 1x Leverage</div>
        </div>

        {/* Cash verfügbar */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-emerald-500" />
            <span className="text-[10px] uppercase tracking-wider text-slate-500">Cash verfügbar</span>
          </div>
          <div className="text-xl font-bold text-emerald-400 font-mono">{fmtEur(cashEur)}</div>
          <div className="text-[10px] text-slate-500 mt-1">{((cashEur / START_CAPITAL) * 100).toFixed(1)}% des Kapitals</div>
        </div>

        {/* Deployed */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <Bitcoin className="w-4 h-4 text-amber-500" />
            <span className="text-[10px] uppercase tracking-wider text-slate-500">Eingesetzt</span>
          </div>
          <div className="text-xl font-bold text-amber-400 font-mono">{fmtEur(deployedEur)}</div>
          <div className="mt-2 h-1.5 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-amber-500 rounded-full transition-all" style={{ width: `${capitalUtilPct}%` }} />
          </div>
          <div className="text-[10px] text-slate-500 mt-1">{capitalUtilPct.toFixed(1)}% Kapitalnutzung · {positions.length} Pos.</div>
        </div>

        {/* Daily P&L */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center gap-2 mb-2">
            {dailyPnl >= 0 ? <TrendingUp className="w-4 h-4 text-emerald-500" /> : <TrendingDown className="w-4 h-4 text-red-500" />}
            <span className="text-[10px] uppercase tracking-wider text-slate-500">Daily P&L</span>
          </div>
          <div className={`text-xl font-bold font-mono ${dailyPnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {dailyPnl >= 0 ? "+" : ""}{fmtEur(dailyPnl)}
          </div>
          <div className="text-[10px] text-slate-500 mt-1">{totalTrades} Trades heute · Risk 2%/Trade</div>
        </div>
      </div>

      {/* ── Zone 3: Open Positions ──────────────────────────────────────────── */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-400 flex items-center gap-2">
            <Target className="w-4 h-4 text-indigo-400" />
            Offene Positionen
          </h2>
          {positions.length > 0 && (
            <span className="text-xs bg-indigo-500/15 text-indigo-400 border border-indigo-500/30 px-2 py-0.5 rounded-full font-bold">
              {positions.length} aktiv
            </span>
          )}
        </div>

        {positions.length === 0 ? (
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-8 text-center">
            <p className="text-slate-500 text-sm">Keine offenen Positionen</p>
            <p className="text-[10px] text-slate-700 uppercase tracking-widest mt-1">Bruno scannt den Markt...</p>
          </div>
        ) : (
          <div className="space-y-3">
            {positions.map((pos) => (
              <PositionCard key={pos.id} pos={pos} />
            ))}
          </div>
        )}
      </div>

      {/* ── Zone 4: Gate Cascade ────────────────────────────────────────────── */}
      <GateCascade pipeline={pipeline} />

      {/* ── Zone 5: Market Signals ──────────────────────────────────────────── */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Marktsignale</h3>

        {/* Primary signals */}
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-4">
          {[
            {
              label: "GRSS Score",
              value: telemetry.grss?.score ? telemetry.grss.score.toFixed(1) : "—",
              sub: `Raw: ${fmt(telemetry.grss?.score_raw, 1)}`,
              color: telemetry.grss?.score && telemetry.grss.score >= 48 ? "text-emerald-400" : telemetry.grss?.score && telemetry.grss.score >= 25 ? "text-amber-400" : "text-red-400",
            },
            {
              label: "VIX",
              value: fmt(market.vix, 1),
              sub: market.vix && market.vix > 30 ? "High Volatility" : "Normal",
              color: market.vix && market.vix > 30 ? "text-red-400" : market.vix && market.vix > 20 ? "text-amber-400" : "text-emerald-400",
            },
            {
              label: "OFI",
              value: fmt(market.ofi, 3),
              sub: "Order Flow Imbalance",
              color: market.ofi && market.ofi > 0.3 ? "text-emerald-400" : market.ofi && market.ofi < -0.3 ? "text-red-400" : "text-slate-300",
            },
            {
              label: "Funding Rate",
              value: market.funding_rate ? (market.funding_rate * 100).toFixed(4) + "%" : "—",
              sub: "8h Funding",
              color: market.funding_rate && market.funding_rate > 0.01 ? "text-red-400" : market.funding_rate && market.funding_rate !== null && market.funding_rate < 0 ? "text-emerald-400" : "text-slate-300",
            },
            {
              label: "Fear & Greed",
              value: fmt(market.fear_greed, 0),
              sub: market.fear_greed && market.fear_greed > 75 ? "Extreme Gier" : market.fear_greed && market.fear_greed < 25 ? "Extreme Angst" : "Neutral",
              color: market.fear_greed && market.fear_greed > 75 ? "text-red-400" : market.fear_greed && market.fear_greed < 25 ? "text-emerald-400" : "text-slate-300",
            },
            {
              label: "Put/Call Ratio",
              value: fmt(market.put_call_ratio, 2),
              sub: "Options Sentiment",
              color: market.put_call_ratio && market.put_call_ratio < 0.5 ? "text-emerald-400" : market.put_call_ratio && market.put_call_ratio > 0.9 ? "text-red-400" : "text-slate-300",
            },
          ].map((m) => (
            <div key={m.label} className="bg-slate-900/40 rounded-lg p-3">
              <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-1">{m.label}</div>
              <div className={`text-base font-bold font-mono ${m.color}`}>{m.value}</div>
              <div className="text-[10px] text-slate-600 mt-0.5">{m.sub}</div>
            </div>
          ))}
        </div>

        {/* Secondary signals */}
        <div className="grid grid-cols-4 md:grid-cols-8 gap-2">
          {[
            { label: "DVOL", value: fmt(market.dvol, 1) },
            { label: "OI Delta", value: fmt(market.oi_delta_pct, 1) + "%" },
            { label: "L/S Ratio", value: fmt(market.long_short_ratio, 2) },
            { label: "Retail Score", value: fmt(market.retail_score, 0) },
            { label: "Sentiment", value: fmt(market.sentiment, 2) },
            { label: "GRSS Velocity", value: fmt(telemetry.grss?.velocity_30min, 2) },
            { label: "1h Change", value: (market.btc_change_1h_pct !== null && market.btc_change_1h_pct !== undefined ? (market.btc_change_1h_pct >= 0 ? "+" : "") + fmt(market.btc_change_1h_pct, 2) + "%" : "—") },
            { label: "24h Change", value: (market.btc_change_24h_pct !== null && market.btc_change_24h_pct !== undefined ? (market.btc_change_24h_pct >= 0 ? "+" : "") + fmt(market.btc_change_24h_pct, 2) + "%" : "—") },
          ].map((m) => (
            <div key={m.label} className="text-center">
              <div className="text-[9px] text-slate-600 uppercase tracking-wider mb-0.5">{m.label}</div>
              <div className="text-xs font-mono text-slate-300">{m.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Zone 6: Decision Timeline ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        <div className="xl:col-span-3 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400">Decision Timeline</h3>
            <span className="text-[10px] text-slate-600">letzte 30 Zyklen</span>
          </div>
          <div className="h-[180px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={decisionTimeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis yAxisId="left" tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} domain={[-1, 1]} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: "#475569", fontSize: 9 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: "#0c0c18", border: "1px solid #1a1a2e", borderRadius: "8px", fontSize: "11px" }}
                  labelStyle={{ color: "#94a3b8" }}
                />
                <ReferenceLine yAxisId="left" y={0} stroke="#334155" />
                <Line yAxisId="left" type="step" dataKey="signal" stroke="#10b981" strokeWidth={2} dot={{ fill: "#10b981", r: 2 }} name="Signal" />
                <Line yAxisId="right" type="monotone" dataKey="grss" stroke="#6366f1" strokeWidth={1} dot={false} strokeDasharray="3 3" name="GRSS" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex gap-4 text-[10px] text-slate-600">
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-emerald-500 inline-block" /> Signal</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-indigo-500 inline-block border-dashed" /> GRSS</span>
          </div>
        </div>

        {/* Stats box */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4 flex flex-col justify-between">
          <h3 className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-4">Entscheidungs-Mix</h3>
          <div className="space-y-3 flex-1">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-emerald-400">Signals</span>
                <span className="font-mono text-emerald-400">{decisions?.stats?.signals_generated ?? 0}</span>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full" style={{
                  width: `${decisions?.count ? ((decisions?.stats?.signals_generated ?? 0) / decisions.count) * 100 : 0}%`
                }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-red-400">Cascade Hold</span>
                <span className="font-mono text-red-400">{decisions?.stats?.cascade_hold ?? 0}</span>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-red-500 rounded-full" style={{
                  width: `${decisions?.count ? ((decisions?.stats?.cascade_hold ?? 0) / decisions.count) * 100 : 0}%`
                }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-amber-400">OFI Below Threshold</span>
                <span className="font-mono text-amber-400">{decisions?.stats?.ofi_below_threshold ?? 0}</span>
              </div>
              <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div className="h-full bg-amber-500 rounded-full" style={{
                  width: `${decisions?.count ? ((decisions?.stats?.ofi_below_threshold ?? 0) / decisions.count) * 100 : 0}%`
                }} />
              </div>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-[#1a1a2e]">
            <div className="text-[10px] text-slate-600 mb-1">Total Zyklen analysiert</div>
            <div className="text-xl font-bold font-mono text-slate-300">{decisions?.count ?? 0}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

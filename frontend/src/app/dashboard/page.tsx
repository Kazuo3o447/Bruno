"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import TradingChart from "../components/TradingChart";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  PieChart,
  Pie,
} from "recharts";

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

interface PhaseAStatus {
  phase_a_complete: boolean;
  checks: Record<string, boolean>;
  current_grss: number | null;
  grss_breakdown: {
    vix: number | null;
    ndx: string | null;
    yields: number | null;
    pcr: number | null;
    dvol: number | null;
    funding: number | null;
    sentiment: number | null;
    retail_score?: number | null;
  };
  data_sources: Record<string, string | number | null>;
}

interface TradePipelineGate {
  blocked?: boolean;
  note?: string;
  [key: string]: unknown;
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
  gates: Record<string, TradePipelineGate>;
  health_sources: Record<string, { status: string; latency_ms: number; last_update: string }>;
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

interface DecisionTimelinePoint {
  ts: string;
  label: string;
  blocked: number;
  signal: number;
  reason: string;
}

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

function chartColor(value: number, active = false): string {
  if (active) return "#f97316";
  if (value >= 1) return "#ef4444";
  if (value === 0) return "#10b981";
  return "#64748b";
}

function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-xs font-bold text-slate-400 uppercase tracking-wider">{title}</h2>
      {subtitle && <p className="text-[10px] text-slate-600 mt-0.5">{subtitle}</p>}
    </div>
  );
}

function HeaderBar({ telemetry }: { telemetry: Telemetry | null }) {
  const armed = telemetry?.status === "ARMED";
  const grss = telemetry?.grss?.score;
  const price = telemetry?.market?.btc_price;
  const chg24 = telemetry?.market?.btc_change_24h_pct;

  return (
    <div className="flex items-center gap-4 px-4 py-2 border-b border-zinc-800 bg-zinc-950 font-mono text-sm">
      {telemetry?.dry_run && (
        <span className="px-2 py-0.5 rounded border border-yellow-700 text-yellow-400 text-xs font-bold">DRY RUN</span>
      )}
      <span className={`flex items-center gap-1.5 font-bold ${armed ? "text-emerald-400" : "text-red-400"}`}>
        <span className={`w-2 h-2 rounded-full ${armed ? "bg-emerald-400 animate-pulse" : "bg-red-400"}`} />
        {armed ? "ARMED" : "HALTED"}
      </span>
      {grss !== null && grss !== undefined && (
        <span className={`${grss >= 48 ? "text-emerald-400" : grss >= 35 ? "text-amber-400" : "text-red-400"}`}>
          GRSS {grss.toFixed(1)}
        </span>
      )}
      {price && (
        <span className="text-white">
          BTC {fmtPrice(price)}
          <span className={`ml-2 text-xs ${(chg24 ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {fmt(chg24, 2)}% 24h
          </span>
        </span>
      )}
      {!armed && telemetry?.veto_reason && (
        <span className="text-red-400 text-xs truncate max-w-xs">{telemetry.veto_reason}</span>
      )}
    </div>
  );
}

function MarketOverview({ market, grss }: { market: Telemetry["market"] | undefined; grss?: { vix: number | null; sentiment: number | null; retail_score?: number | null } }) {
  if (!market) return <div className="border border-zinc-800 rounded p-3 font-mono text-xs text-zinc-600">Lade Marktdaten...</div>;

  const rows = [
    ["BTC 24h", fmt(market.btc_change_24h_pct, 2) + "%", (market.btc_change_24h_pct ?? 0) >= 0 ? "emerald" : "red"],
    ["BTC 1h", fmt(market.btc_change_1h_pct, 2) + "%", (market.btc_change_1h_pct ?? 0) >= 0 ? "emerald" : "red"],
    ["Funding", market.funding_rate !== null ? (market.funding_rate * 100).toFixed(4) + "%" : "—",
      (market.funding_rate ?? 0) > 0.05 ? "red" : (market.funding_rate ?? 0) < 0 ? "emerald" : "zinc"],
    ["PCR", market.put_call_ratio?.toFixed(2) ?? "—",
      (market.put_call_ratio ?? 1) < 0.5 ? "emerald" : (market.put_call_ratio ?? 1) > 0.8 ? "red" : "zinc"],
    ["F&G", market.fear_greed?.toString() ?? "—",
      (market.fear_greed ?? 50) > 70 ? "amber" : (market.fear_greed ?? 50) < 30 ? "red" : "zinc"],
    ["VIX", grss?.vix?.toFixed(1) ?? market.vix?.toFixed(1) ?? "—",
      (grss?.vix ?? market.vix ?? 20) > 30 ? "red" : (grss?.vix ?? market.vix ?? 20) > 20 ? "amber" : "emerald"],
    ["OI Δ", market.oi_delta_pct !== null ? fmt(market.oi_delta_pct, 1) + "%" : "—",
      (market.oi_delta_pct ?? 0) > 5 ? "red" : (market.oi_delta_pct ?? 0) < -5 ? "emerald" : "zinc"],
    ["L/S Ratio", market.long_short_ratio?.toFixed(2) ?? "—",
      (market.long_short_ratio ?? 1) > 2 ? "red" : (market.long_short_ratio ?? 1) < 0.5 ? "emerald" : "zinc"],
  ];

  const colorMap: Record<string, string> = { emerald: "text-emerald-400", red: "text-red-400", amber: "text-amber-400", zinc: "text-zinc-300" };

  return (
    <div className="border border-zinc-800 rounded p-3 font-mono text-xs bg-[#0a0a0f]">
      <div className="text-zinc-500 uppercase tracking-widest text-xs mb-2">Gesamtmarkt</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {rows.map(([label, value, color]) => (
          <div key={label} className="flex justify-between">
            <span className="text-zinc-500">{label}</span>
            <span className={colorMap[color ?? "zinc"]}>{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function OpenPositionPanel({ position, currentPrice }: { position: Position | null; currentPrice: number | null }) {
  if (!position || position.status !== "open") return (
    <div className="border border-zinc-800 rounded px-4 py-2 font-mono text-xs text-zinc-600 flex items-center gap-2">
      <span className="w-2 h-2 rounded-full bg-zinc-700" /> Keine offene Position
    </div>
  );

  const pnlPct = currentPrice ? ((currentPrice - position.entry_price) / position.entry_price) * 100 : null;
  const pnlPos = (pnlPct ?? 0) >= 0;

  return (
    <div className={`border rounded px-4 py-3 font-mono text-xs flex items-center gap-6 flex-wrap
      ${position.side === "long" ? "border-emerald-800 bg-emerald-950/30" : "border-red-800 bg-red-950/30"}`}>
      <span className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full animate-pulse ${position.side === "long" ? "bg-emerald-400" : "bg-red-400"}`} />
        <span className="text-white font-bold">{position.side.toUpperCase()} {position.symbol}</span>
      </span>
      <span className="text-zinc-400">Entry <span className="text-white">{fmtPrice(position.entry_price)}</span></span>
      {pnlPct !== null && (
        <span className={`font-bold text-sm ${pnlPos ? "text-emerald-400" : "text-red-400"}`}>P&L {fmt(pnlPct, 2)}%</span>
      )}
      <span className="text-zinc-400">SL <span className="text-red-400">{fmtPrice(position.stop_loss_price)}</span></span>
      <span className="text-zinc-400">TP <span className="text-emerald-400">{fmtPrice(position.take_profit_price)}</span></span>
    </div>
  );
}

function AgentStatusRow({ agents }: { agents: Record<string, { status: string; age_seconds: number | null; healthy: boolean }> }) {
  const agentOrder = ["ingestion", "quant", "context", "risk", "execution"];
  return (
    <div className="border border-zinc-800 rounded px-3 py-2 font-mono text-xs flex items-center gap-6 bg-[#0a0a0f]">
      <span className="text-zinc-500 uppercase tracking-widest text-xs flex-shrink-0">Agenten</span>
      {agentOrder.map(id => {
        const a = agents[id];
        if (!a) return <span key={id} className="text-zinc-700">{id} ●</span>;
        const color = a.healthy ? "emerald-400" : "red-400";
        return (
          <span key={id} className="flex items-center gap-1">
            <span className={`w-1.5 h-1.5 rounded-full bg-${color}`} />
            <span className="text-zinc-400">{id}</span>
            <span className="text-zinc-600">{a.age_seconds !== null ? `${Math.round(a.age_seconds)}s` : "?"}</span>
          </span>
        );
      })}
    </div>
  );
}

function DataFreshnessBar({ sources }: { sources: Record<string, { status: string; latency_ms: number; last_update: string }> }) {
  const items = Object.entries(sources).map(([name, data]) => ({
    name,
    ok: ["online", "ok", "healthy", "connected", "success", "running"].includes((data.status || "offline").toLowerCase()),
    age: timeAgo(data.last_update),
  }));

  if (items.length === 0) {
    return (
      <div className="border border-zinc-800 rounded px-3 py-2 font-mono text-xs flex items-center gap-4 flex-wrap bg-[#0a0a0f]">
        <span className="text-zinc-500 uppercase tracking-widest flex-shrink-0">Daten</span>
        <span className="text-zinc-500">keine Quellen gemeldet</span>
      </div>
    );
  }

  return (
    <div className="border border-zinc-800 rounded px-3 py-2 font-mono text-xs flex items-center gap-4 flex-wrap bg-[#0a0a0f]">
      <span className="text-zinc-500 uppercase tracking-widest flex-shrink-0">Daten</span>
      {items.map(({ name, ok, age }) => (
        <span key={name} className="flex items-center gap-1">
          <span className={ok ? "text-emerald-400" : "text-red-400"}>{ok ? "✓" : "✗"}</span>
          <span className="text-zinc-400">{name}</span>
          <span className="text-zinc-600">{age}</span>
        </span>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);
  const [phaseA, setPhaseA] = useState<PhaseAStatus | null>(null);
  const [tradePipeline, setTradePipeline] = useState<TradePipelineStatus | null>(null);
  const [decisionFeed, setDecisionFeed] = useState<DecisionFeedResponse | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [telRes, posRes, phaseARes, pipelineRes, decisionsRes] = await Promise.allSettled([
        fetch("/api/v1/telemetry/live").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        fetch("/api/v1/positions/open").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        fetch("/api/v1/monitoring/phase-a/status").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        fetch("/api/v1/monitoring/debug/trade-pipeline").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        fetch("/api/v1/decisions/feed?limit=50").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      ]);

      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (posRes.status === "fulfilled") {
        setPosition(posRes.value.position ?? posRes.value.positions?.[0] ?? null);
        setCurrentPrice(telRes.status === "fulfilled" ? telRes.value.market?.btc_price ?? null : null);
      }
      if (phaseARes.status === "fulfilled") setPhaseA(phaseARes.value);
      if (pipelineRes.status === "fulfilled") setTradePipeline(pipelineRes.value);
      if (decisionsRes.status === "fulfilled") setDecisionFeed(decisionsRes.value);
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  const tradeReasonData = useMemo(() => {
    const counts: Record<string, number> = {
      "Signal gesetzt": 0,
      "Composite Hold": 0,
      "OFI Gate": 0,
      "Risk/Veto": 0,
      "Position Guard": 0,
      "Daily Limit": 0,
      "Sonstiges": 0,
    };

    for (const event of decisionFeed?.events ?? []) {
      const text = `${event.outcome ?? ""} ${event.reason ?? ""}`.toUpperCase();
      if (text.includes("SIGNAL_")) counts["Signal gesetzt"] += 1;
      else if (text.includes("OFI")) counts["OFI Gate"] += 1;
      else if (text.includes("RISK") || text.includes("VETO")) counts["Risk/Veto"] += 1;
      else if (text.includes("POSITION")) counts["Position Guard"] += 1;
      else if (text.includes("DAILY")) counts["Daily Limit"] += 1;
      else if (text.includes("HOLD") || text.includes("THRESHOLD") || text.includes("CASCADE")) counts["Composite Hold"] += 1;
      else counts["Sonstiges"] += 1;
    }

    return Object.entries(counts)
      .map(([name, value]) => ({ name, value }))
      .filter((item) => item.value > 0);
  }, [decisionFeed]);

  const topNoTradeReasons = useMemo(() => {
    return tradeReasonData
      .filter((item) => item.name !== "Signal gesetzt")
      .sort((a, b) => b.value - a.value)
      .slice(0, 3);
  }, [tradeReasonData]);

  const blockerTimelineData = useMemo<DecisionTimelinePoint[]>(() => {
    const events = [...(decisionFeed?.events ?? [])].reverse().slice(0, 20);

    return events.map((event, index) => {
      const outcome = String(event.outcome ?? "").toUpperCase();
      const reason = String(event.reason ?? "");
      const blocked = outcome.includes("HOLD") || outcome.includes("BLOCK") || outcome.includes("VETO") || outcome.includes("LIMIT") || reason.toUpperCase().includes("VETO") ? 1 : 0;
      const signal = outcome.includes("SIGNAL_") ? 1 : 0;

      return {
        ts: event.ts ?? `event-${index}`,
        label: event.ts ? new Date(event.ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : `#${index + 1}`,
        blocked,
        signal,
        reason: reason || event.outcome || "—",
      };
    });
  }, [decisionFeed]);

  const gateHealthData = useMemo(() => {
    const gates = tradePipeline?.gates ?? {};
    return Object.entries(gates).map(([key, gate]) => ({
      name: key.replace(/^gate_\d+_/, "").replaceAll("_", " "),
      blocked: gate.blocked ? 1 : 0,
      note: String(gate.note ?? ""),
    }));
  }, [tradePipeline]);

  const platformSummary = useMemo(() => {
    const freshCount = Object.values(phaseA?.checks ?? {}).filter(Boolean).length;
    const blocking = tradePipeline?.summary.blocking_gates?.length ?? 0;
    return [
      { label: "Platform", value: telemetry?.status ?? "—", tone: telemetry?.status === "ARMED" ? "emerald" : "red" },
      { label: "Dry Run", value: telemetry?.dry_run ? "ON" : "OFF", tone: telemetry?.dry_run ? "amber" : "emerald" },
      { label: "Live Approved", value: telemetry?.live_trading_approved ? "YES" : "NO", tone: telemetry?.live_trading_approved ? "emerald" : "red" },
      { label: "Fresh Checks", value: `${freshCount}/${Object.keys(phaseA?.checks ?? {}).length || 0}`, tone: freshCount >= 5 ? "emerald" : "amber" },
      { label: "Blocking Gates", value: String(blocking), tone: blocking > 0 ? "red" : "emerald" },
      { label: "Current Veto", value: telemetry?.veto_active ? "ACTIVE" : "CLEAR", tone: telemetry?.veto_active ? "red" : "emerald" },
    ];
  }, [phaseA, telemetry, tradePipeline]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 10000);
    return () => clearInterval(iv);
  }, [refresh]);

  // ... (rest of the code remains the same)
  if (error) return <div className="min-h-screen bg-[#0a0a0f] text-white p-8 text-red-400">Error: {error}</div>;
  if (!telemetry) return <div className="min-h-screen bg-[#0a0a0f] text-white p-8">Loading...</div>;

  const market = telemetry.market;
  const grss = phaseA?.grss_breakdown;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6 space-y-4">
      <HeaderBar telemetry={telemetry} />

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        {platformSummary.map((item) => (
          <div key={item.label} className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-3">
            <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-1">{item.label}</div>
            <div className={`text-sm font-bold ${item.tone === "emerald" ? "text-emerald-400" : item.tone === "amber" ? "text-amber-400" : "text-red-400"}`}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Main Chart - Left Side */}
        <div className="lg:col-span-2 flex flex-col gap-4">
          <div className="h-[380px] bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-3">
            <TradingChart symbol="BTCUSDT" />
          </div>
          
          {/* Position Panel - Below Chart */}
          {position?.status === "open" ? (
            <div className={`flex items-center justify-between p-4 rounded-xl border ${position.side === "long" ? "border-emerald-800 bg-emerald-950/20" : "border-red-800 bg-red-950/20"}`}>
              <div className="flex items-center gap-4">
                <span className={`px-2 py-1 rounded text-xs font-bold ${position.side === "long" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
                  {position.side.toUpperCase()}
                </span>
                <span className="font-mono text-sm">{position.symbol}</span>
                <span className="text-xs text-slate-500">Entry: {fmtPrice(position.entry_price)}</span>
              </div>
              <div className="flex items-center gap-4 text-sm">
                {currentPrice && (
                  <span className={`font-bold ${((currentPrice - position.entry_price) / position.entry_price * 100) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    P&L {fmt((currentPrice - position.entry_price) / position.entry_price * 100, 2)}%
                  </span>
                )}
                <span className="text-xs text-slate-500">SL: {fmtPrice(position.stop_loss_price)}</span>
                <span className="text-xs text-slate-500">TP: {fmtPrice(position.take_profit_price)}</span>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-xl border border-zinc-800 bg-[#0c0c18] text-center">
              <span className="text-sm text-slate-500">No open position</span>
            </div>
          )}
        </div>

        {/* Sidebar - Right Side */}
        <div className="flex flex-col gap-4">
          {/* Market Data */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">Market Data</div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">24h</span>
                <span className={market.btc_change_24h_pct && market.btc_change_24h_pct >= 0 ? "text-emerald-400" : "text-red-400"}>
                  {fmt(market.btc_change_24h_pct, 2)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">1h</span>
                <span className={market.btc_change_1h_pct && market.btc_change_1h_pct >= 0 ? "text-emerald-400" : "text-red-400"}>
                  {fmt(market.btc_change_1h_pct, 2)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">OFI</span>
                <span className={market.ofi && market.ofi > 0.3 ? "text-emerald-400" : market.ofi && market.ofi < -0.3 ? "text-red-400" : "text-slate-400"}>
                  {fmt(market.ofi, 2)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Funding</span>
                <span className={market.funding_rate && market.funding_rate > 0.01 ? "text-red-400" : market.funding_rate && market.funding_rate < 0 ? "text-emerald-400" : "text-slate-400"}>
                  {market.funding_rate ? (market.funding_rate * 100).toFixed(4) : "—"}%
                </span>
              </div>
            </div>
          </div>

          {/* Sentiment */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">Sentiment & Bias</div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">News</span>
                <span className={grss?.sentiment && grss.sentiment > 0.2 ? "text-emerald-400" : grss?.sentiment && grss.sentiment < -0.2 ? "text-red-400" : "text-slate-400"}>
                  {grss?.sentiment?.toFixed(2) ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Retail</span>
                <span className={grss?.retail_score && grss.retail_score > 60 ? "text-red-400" : "text-emerald-400"}>
                  {grss?.retail_score?.toFixed(0) ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">F&G</span>
                <span className={market.fear_greed && market.fear_greed > 75 ? "text-red-400" : market.fear_greed && market.fear_greed < 25 ? "text-emerald-400" : "text-slate-400"}>
                  {market.fear_greed ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">P/C</span>
                <span className={market.put_call_ratio && market.put_call_ratio > 0.9 ? "text-emerald-400" : market.put_call_ratio && market.put_call_ratio < 0.5 ? "text-red-400" : "text-slate-400"}>
                  {market.put_call_ratio?.toFixed(2) ?? "—"}
                </span>
              </div>
            </div>
          </div>

          {/* GRSS */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">GRSS Components</div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-slate-500">VIX</span>
                <span className={grss?.vix && grss.vix > 30 ? "text-red-400" : grss?.vix && grss.vix > 20 ? "text-amber-400" : "text-emerald-400"}>
                  {grss?.vix?.toFixed(1) ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Macro</span>
                <span className={grss?.ndx === "risk_off" ? "text-red-400" : grss?.ndx === "risk_on" ? "text-emerald-400" : "text-amber-400"}>
                  {grss?.ndx ?? "—"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Yields</span>
                <span className="text-slate-300">{grss?.yields?.toFixed(2) ?? "—"}%</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">DVOL</span>
                <span className="text-slate-300">{grss?.dvol?.toFixed(1) ?? "—"}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Section 3: Decision Analysis */}
      <div className="border-t border-zinc-800 pt-6">
        <SectionHeader title="Decision Analysis" subtitle="Why trades are blocked" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Top Blockers */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-4">Top Blockers</div>
            {topNoTradeReasons.length > 0 ? (
              <div className="space-y-3">
                {topNoTradeReasons.map((reason, idx) => (
                  <div key={reason.name} className="flex items-center gap-3">
                    <span className={`text-xs font-bold w-5 ${idx === 0 ? "text-red-400" : idx === 1 ? "text-amber-400" : "text-slate-500"}`}>#{idx + 1}</span>
                    <div className="flex-1">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-slate-300">{reason.name}</span>
                        <span className="text-slate-500 font-mono">{reason.value}</span>
                      </div>
                      <div className="h-1.5 bg-[#1a1a2e] rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${idx === 0 ? "bg-red-500" : idx === 1 ? "bg-amber-500" : "bg-slate-500"}`}
                          style={{ width: `${Math.round((reason.value / (topNoTradeReasons[0]?.value || 1)) * 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">No blocker data</div>
            )}
          </div>

          {/* Blocker Distribution Chart */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-4">Distribution</div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={tradeReasonData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f1f33" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 9 }} axisLine={false} tickLine={false} interval={0} />
                  <Tooltip contentStyle={{ background: "#090913", border: "1px solid #1f1f33", color: "#e2e8f0" }} />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {tradeReasonData.map((entry) => (
                      <Cell key={entry.name} fill={chartColor(entry.value, entry.name === "Risk/Veto" || entry.name === "Daily Limit")} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Timeline */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-4">Recent (20)</div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={blockerTimelineData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f1f33" />
                  <XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 8 }} axisLine={false} tickLine={false} interval={2} />
                  <YAxis tick={false} axisLine={false} domain={[0, 1]} />
                  <Tooltip 
                    contentStyle={{ background: "#090913", border: "1px solid #1f1f33", color: "#e2e8f0" }}
                    labelFormatter={(_, p: any) => p?.[0]?.payload?.reason || ""}
                  />
                  <Line type="step" dataKey="blocked" stroke="#ef4444" strokeWidth={2} dot={false} />
                  <Line type="step" dataKey="signal" stroke="#10b981" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-4 mt-2 text-xs">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500"/> Signal</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500"/> Blocked</span>
            </div>
          </div>
        </div>
      </div>

      {/* Section 4: Pipeline Status */}
      <div className="border-t border-zinc-800 pt-6">
        <SectionHeader title="Pipeline Status" subtitle="6-Gate decision cascade" />
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { name: "Data", status: !tradePipeline?.gates?.gate_1_data_freshness?.blocked, info: "Fresh" },
            { name: "Context", status: !tradePipeline?.gates?.gate_2_context?.blocked, info: "GRSS" },
            { name: "Sentiment", status: !tradePipeline?.gates?.gate_3_sentiment?.blocked, info: "News" },
            { name: "Quant", status: !tradePipeline?.gates?.gate_4_quant_micro?.blocked, info: "OFI" },
            { name: "Risk", status: !tradePipeline?.gates?.gate_5_risk_veto?.blocked, info: "Vetos" },
            { name: "Portfolio", status: !tradePipeline?.gates?.gate_6_portfolio?.blocked, info: "Limits" },
          ].map((gate, idx) => (
            <div key={gate.name} className={`p-3 rounded-xl border ${gate.status ? "border-emerald-800 bg-emerald-950/10" : "border-red-800 bg-red-950/10"}`}>
              <div className="flex items-center gap-2 mb-1">
                <span className={`w-2 h-2 rounded-full ${gate.status ? "bg-emerald-400" : "bg-red-400"}`} />
                <span className="text-[10px] font-bold text-slate-400">Gate {idx + 1}</span>
              </div>
              <div className={`text-sm font-bold ${gate.status ? "text-emerald-400" : "text-red-400"}`}>{gate.name}</div>
              <div className="text-[10px] text-slate-500">{gate.info}</div>
            </div>
          ))}
        </div>

        {tradePipeline?.summary.blocking_gates && tradePipeline.summary.blocking_gates.length > 0 && (
          <div className="mt-3 p-3 bg-red-950/20 border border-red-800 rounded-xl">
            <span className="text-xs text-red-400 font-bold">Active: </span>
            <span className="text-sm text-red-300 font-mono">{tradePipeline.summary.blocking_gates.join(" → ")}</span>
          </div>
        )}
      </div>

      {/* Section 5: System Health */}
      <div className="border-t border-zinc-800 pt-6">
        <SectionHeader title="System Health" subtitle="Agents & data sources" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Agents */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">Agents</div>
            <div className="flex flex-wrap gap-2">
              {["ingestion", "technical", "quant", "context", "risk", "execution"].map((id) => {
                const a = telemetry.agents[id];
                if (!a) return null;
                return (
                  <div key={id} className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${a.healthy ? "border-emerald-800 bg-emerald-950/10" : "border-red-800 bg-red-950/10"}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${a.healthy ? "bg-emerald-400" : "bg-red-400"}`} />
                    <span className="text-xs font-medium capitalize text-slate-300">{id}</span>
                    <span className="text-[10px] text-slate-500">{timeAgo(a.age_seconds ? new Date(Date.now() - a.age_seconds * 1000).toISOString() : null)}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Data Sources */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="text-[10px] text-slate-500 uppercase tracking-wider mb-3">Data Sources</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(telemetry.data_sources).map(([name, data]) => {
                const ok = ["online", "ok", "healthy", "connected", "success", "running"].includes((data.status || "offline").toLowerCase());
                return (
                  <div key={name} className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs border ${ok ? "border-emerald-800 text-emerald-400" : "border-red-800 text-red-400"}`}>
                    <span>{ok ? "✓" : "✗"}</span>
                    <span className="text-slate-300">{name}</span>
                    <span className="text-slate-500">{timeAgo(data.last_update)}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

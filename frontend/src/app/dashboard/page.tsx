"use client";

import { useEffect, useState, useCallback } from "react";
import Sidebar from "../components/Sidebar";
import TradingChart from "../components/TradingChart";

interface Telemetry {
  status: "ARMED" | "HALTED";
  veto_active: boolean;
  veto_reason: string;
  dry_run: boolean;
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

function MarketOverview({ market }: { market: Telemetry["market"] | undefined }) {
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
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [telRes, posRes] = await Promise.allSettled([
        fetch("/api/v1/telemetry/live").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
        fetch("/api/v1/positions/open").then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      ]);

      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (posRes.status === "fulfilled") {
        setPosition(posRes.value.position ?? null);
        setCurrentPrice(posRes.value.current_price ?? null);
      }
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

  return (
    <div className="flex min-h-screen bg-[#0a0a0f] text-white">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <HeaderBar telemetry={telemetry} />
        <div className="flex-1 p-4 space-y-3 overflow-y-auto">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div className="lg:col-span-2 h-[320px] overflow-hidden">
              <div className="w-full h-full">
                <TradingChart symbol="BTCUSDT" />
              </div>
            </div>
            <div className="space-y-3">
              <OpenPositionPanel position={position} currentPrice={currentPrice} />
            </div>
          </div>

          <div className="border-t border-zinc-800 pt-3 mt-6">
            <h2 className="text-zinc-500 uppercase tracking-widest text-xs font-mono mb-3">System Monitoring</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
              <MarketOverview market={telemetry?.market} />
            </div>
            <AgentStatusRow agents={telemetry?.agents ?? {}} />
            <DataFreshnessBar sources={telemetry?.data_sources ?? {}} />
          </div>
        </div>
      </div>
    </div>
  );
}

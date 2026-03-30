"use client";
import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import { ExportButton } from "../components/ExportButton";
import { KillSwitch } from "../components/KillSwitch";

// ── Typen ─────────────────────────────────────────────────────────────────

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
    cvd: number | null;
    funding_rate: number | null;
    put_call_ratio: number | null;
    dvol: number | null;
    fear_greed: number | null;
    vix: number | null;
    ndx_status: string | null;
    yields_10y: number | null;
    m2_yoy_pct: number | null;
    stablecoin_delta_bn: number | null;
    llm_news_sentiment: number | null;
    news_silence_seconds: number | null;
  };
  data_sources: Record<string, { status: string; latency_ms: number; last_update: string }>;
  agents: Record<string, { status: string; age_seconds: number | null; healthy: boolean }>;
  last_decision: DecisionEvent | null;
}

interface GRSSFull {
  score: number | null;
  score_raw: number | null;
  velocity_30min: number | null;
  veto_active: boolean;
  reason: string | null;
  macro: { ndx_status: string; vix: number; yields_10y: number; dxy_change_pct: number; m2_yoy_pct: number };
  derivatives: { funding_rate: number; put_call_ratio: number; dvol: number; oi_delta_pct: number; perp_basis_pct: number; funding_divergence: number };
  sentiment: { fear_greed: number; llm_news_sentiment: number; stablecoin_delta_bn: number };
  data_quality: { fresh_source_count: number; data_freshness_ok: boolean; news_silence_seconds: number; last_update: string };
  btc: { change_24h_pct: number; change_1h_pct: number };
}

interface DecisionEvent {
  ts: string;
  ofi: number;
  ofi_threshold: number;
  ofi_met: boolean;
  grss: number | null;
  outcome: string;
  reason: string;
  regime: string | null;
  layer1_confidence: number | null;
  layer2_decision: string | null;
  layer3_blocked: boolean | null;
  price: number;
}

interface Position {
  status: string; side: string; symbol: string;
  entry_price: number; quantity: number;
  stop_loss_price: number; take_profit_price: number;
  grss_at_entry: number; created_at: string;
}

// ── Hilfsfunktionen ───────────────────────────────────────────────────────

function fmt(n: number | null | undefined, decimals = 2, prefix = ""): string {
  if (n === null || n === undefined) return "—";
  const sign = n > 0 ? "+" : "";
  return `${prefix}${sign}${n.toFixed(decimals)}`;
}

function fmtPrice(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `$${n.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function timeAgo(isoStr: string | null | undefined): string {
  if (!isoStr) return "—";
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  return `${Math.floor(diff / 3600)}h`;
}

function outcomeLabel(event: DecisionEvent): { text: string; color: string; icon: string } {
  const o = event.outcome || "";
  if (o === "OFI_BELOW_THRESHOLD")
    return { text: `OFI ${event.ofi.toFixed(0)} unter Schwelle ${event.ofi_threshold}`, color: "text-zinc-500", icon: "⛔" };
  if (o.startsWith("CASCADE_LAYER1"))
    return { text: `L1: ${event.regime}, conf ${event.layer1_confidence?.toFixed(2)} < 0.60`, color: "text-amber-600", icon: "⛔" };
  if (o.startsWith("CASCADE_LAYER2"))
    return { text: `L2: ${event.layer2_decision}, conf zu niedrig`, color: "text-amber-500", icon: "⛔" };
  if (o.startsWith("CASCADE_LAYER3"))
    return { text: `L3: Advocatus Diaboli blockiert`, color: "text-orange-500", icon: "⛔" };
  if (o.startsWith("SIGNAL_"))
    return { text: `Signal: ${o.replace("SIGNAL_", "")} — L2 conf ${event.layer1_confidence?.toFixed(2)}`, color: "text-emerald-400", icon: "✅" };
  return { text: event.reason || o, color: "text-zinc-400", icon: "○" };
}

// ── Komponenten ───────────────────────────────────────────────────────────

function HeaderBar({ telemetry }: { telemetry: Telemetry | null }) {
  const armed = telemetry?.status === "ARMED";
  const grss = telemetry?.grss.score;
  const price = telemetry?.market.btc_price;
  const chg24 = telemetry?.market.btc_change_24h_pct;
  const chg1h = telemetry?.market.btc_change_1h_pct;

  return (
    <div className="flex items-center gap-4 px-4 py-2 border-b border-zinc-800 bg-zinc-950 font-mono text-sm sticky top-0 z-40">
      {telemetry?.dry_run && (
        <span className="px-2 py-0.5 rounded border border-yellow-700 text-yellow-400 text-xs font-bold">
          DRY RUN
        </span>
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
          <span className={`ml-1 text-xs ${(chg1h ?? 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            {fmt(chg1h, 2)}% 1h
          </span>
        </span>
      )}
      {!armed && telemetry?.veto_reason && (
        <span className="text-red-400 text-xs truncate max-w-xs">
          {telemetry.veto_reason}
        </span>
      )}
      <div className="ml-auto flex items-center gap-2">
        <ExportButton />
        <KillSwitch compact />
      </div>
    </div>
  );
}

function OpenPositionPanel({ position, currentPrice }: {
  position: Position | null; currentPrice: number | null
}) {
  if (!position || position.status !== "open") return (
    <div className="border border-zinc-800 rounded px-4 py-2 font-mono text-xs text-zinc-600 flex items-center gap-2">
      <span className="w-2 h-2 rounded-full bg-zinc-700" /> Keine offene Position
    </div>
  );

  const pnlPct = currentPrice
    ? ((currentPrice - position.entry_price) / position.entry_price) * 100
    : null;
  const pnlPos = (pnlPct ?? 0) >= 0;
  const sl_dist = ((position.entry_price - position.stop_loss_price) / position.entry_price * 100).toFixed(2);
  const tp_dist = ((position.take_profit_price - position.entry_price) / position.entry_price * 100).toFixed(2);

  return (
    <div className={`border rounded px-4 py-3 font-mono text-xs flex items-center gap-6 flex-wrap
      ${position.side === "long" ? "border-emerald-800 bg-emerald-950/30" : "border-red-800 bg-red-950/30"}`}>
      <span className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full animate-pulse ${position.side === "long" ? "bg-emerald-400" : "bg-red-400"}`} />
        <span className="text-white font-bold">{position.side.toUpperCase()} {position.symbol}</span>
      </span>
      <span className="text-zinc-400">Entry <span className="text-white">{fmtPrice(position.entry_price)}</span></span>
      <span className="text-zinc-400">Qty <span className="text-white">{position.quantity} BTC</span></span>
      {pnlPct !== null && (
        <span className={`font-bold text-sm ${pnlPos ? "text-emerald-400" : "text-red-400"}`}>
          P&L {fmt(pnlPct, 2)}%
        </span>
      )}
      <span className="text-zinc-400">SL <span className="text-red-400">{fmtPrice(position.stop_loss_price)}</span>
        <span className="text-zinc-600 ml-1">(-{sl_dist}%)</span></span>
      <span className="text-zinc-400">TP <span className="text-emerald-400">{fmtPrice(position.take_profit_price)}</span>
        <span className="text-zinc-600 ml-1">(+{tp_dist}%)</span></span>
      <span className="text-zinc-600">GRSS@Entry {position.grss_at_entry?.toFixed(1)}</span>
    </div>
  );
}

function MarketOverview({ market }: { market: Telemetry["market"] | undefined }) {
  if (!market) return (
    <div className="border border-zinc-800 rounded p-3 font-mono text-xs text-zinc-600">Lade Marktdaten...</div>
  );

  const rows: [string, string, string?][] = [
    ["BTC 24h", fmt(market.btc_change_24h_pct, 2) + "%", (market.btc_change_24h_pct ?? 0) >= 0 ? "emerald" : "red"],
    ["BTC 1h", fmt(market.btc_change_1h_pct, 2) + "%", (market.btc_change_1h_pct ?? 0) >= 0 ? "emerald" : "red"],
    ["Funding", market.funding_rate !== null && market.funding_rate !== undefined
      ? (market.funding_rate * 100).toFixed(4) + "%" : "—",
      (market.funding_rate ?? 0) > 0.05 ? "red" : (market.funding_rate ?? 0) < 0 ? "emerald" : "zinc"],
    ["PCR", market.put_call_ratio?.toFixed(2) ?? "—",
      (market.put_call_ratio ?? 1) < 0.5 ? "emerald" : (market.put_call_ratio ?? 1) > 0.8 ? "red" : "zinc"],
    ["DVOL", market.dvol?.toFixed(0) ?? "—",
      (market.dvol ?? 50) > 80 ? "red" : (market.dvol ?? 50) < 40 ? "emerald" : "zinc"],
    ["F&G", market.fear_greed?.toString() ?? "—",
      (market.fear_greed ?? 50) > 70 ? "amber" : (market.fear_greed ?? 50) < 30 ? "red" : "zinc"],
    ["VIX", market.vix?.toFixed(1) ?? "—",
      (market.vix ?? 20) > 25 ? "red" : (market.vix ?? 20) < 15 ? "emerald" : "zinc"],
    ["NDX", market.ndx_status ?? "—",
      market.ndx_status === "BULLISH" ? "emerald" : market.ndx_status === "BEARISH" ? "red" : "zinc"],
    ["10Y", market.yields_10y !== null && market.yields_10y !== undefined
      ? market.yields_10y.toFixed(2) + "%" : "—",
      (market.yields_10y ?? 4) > 4.5 ? "red" : (market.yields_10y ?? 4) < 4.0 ? "emerald" : "zinc"],
    ["M2 YoY", market.m2_yoy_pct !== null && market.m2_yoy_pct !== undefined
      ? fmt(market.m2_yoy_pct, 1) + "%" : "—",
      (market.m2_yoy_pct ?? 0) > 5 ? "emerald" : (market.m2_yoy_pct ?? 0) < 0 ? "red" : "zinc"],
    ["USDT Δ7d", market.stablecoin_delta_bn !== null && market.stablecoin_delta_bn !== undefined
      ? fmt(market.stablecoin_delta_bn, 1) + "B" : "—",
      (market.stablecoin_delta_bn ?? 0) > 2 ? "emerald" : (market.stablecoin_delta_bn ?? 0) < -2 ? "red" : "zinc"],
    ["LLM Sent.", market.llm_news_sentiment !== null && market.llm_news_sentiment !== undefined
      ? fmt(market.llm_news_sentiment, 2) : "—",
      (market.llm_news_sentiment ?? 0) > 0.3 ? "emerald" : (market.llm_news_sentiment ?? 0) < -0.3 ? "red" : "zinc"],
  ];

  const colorMap: Record<string, string> = {
    emerald: "text-emerald-400", red: "text-red-400",
    amber: "text-amber-400", zinc: "text-zinc-300"
  };

  return (
    <div className="border border-zinc-800 rounded p-3 font-mono text-xs bg-[#0a0a0f]">
      <div className="text-zinc-500 uppercase tracking-widest text-xs mb-2">Gesamtmarkt</div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {rows.map(([label, value, color]) => (
          <div key={label} className="flex justify-between">
            <span className="text-zinc-500">{label}</span>
            <span className={colorMap[color ?? "zinc"] ?? "text-zinc-300"}>{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function GRSSBreakdown({ grss }: { grss: GRSSFull | null }) {
  if (!grss) return (
    <div className="border border-zinc-800 rounded p-3 font-mono text-xs text-zinc-600">Lade GRSS...</div>
  );

  const score = grss.score ?? 0;
  const scoreColor = score >= 60 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";
  const label = score >= 48 ? "AKTIV" : score >= 35 ? "GRENZWERTIG" : "VETO";

  function Bar({ pts, max, color }: { pts: number; max: number; color: string }) {
    const w = Math.min(100, Math.abs(pts) / max * 100);
    return (
      <div className="flex items-center gap-2">
        <div className="w-24 h-1 bg-zinc-800 rounded overflow-hidden flex-shrink-0">
          <div className="h-full rounded" style={{ width: `${w}%`, backgroundColor: color }} />
        </div>
        <span style={{ color: pts >= 0 ? "#22c55e" : "#ef4444" }} className="text-xs">
          {pts > 0 ? "+" : ""}{pts.toFixed(1)}
        </span>
      </div>
    );
  }

  const macroPts = (
    (grss.macro.ndx_status === "BULLISH" ? 15 : grss.macro.ndx_status === "BEARISH" ? -20 : 0) +
    (grss.macro.vix < 15 ? 7 : grss.macro.vix > 25 ? -15 : grss.macro.vix > 20 ? -7 : 0) +
    (grss.macro.yields_10y < 4.0 ? 8 : grss.macro.yields_10y > 4.5 ? -10 : 0) +
    ((grss.macro.m2_yoy_pct ?? 0) > 5 ? 8 : (grss.macro.m2_yoy_pct ?? 0) > 2 ? 3 : (grss.macro.m2_yoy_pct ?? 0) < 0 ? -10 : 0)
  );

  const derivPts = (
    (grss.derivatives.funding_rate > 0.05 ? -15 : grss.derivatives.funding_rate < -0.01 ? 5 : 10) +
    (grss.derivatives.put_call_ratio < 0.5 ? 12 : grss.derivatives.put_call_ratio > 0.8 ? -10 : 0) +
    (grss.derivatives.funding_divergence < 0.01 ? 8 : grss.derivatives.funding_divergence > 0.03 ? -10 : 0)
  );

  const sentPts = (
    ((grss.sentiment.fear_greed - 50) / 50) * 15 +
    ((grss.sentiment.stablecoin_delta_bn ?? 0) > 2 ? 8 : (grss.sentiment.stablecoin_delta_bn ?? 0) < -2 ? -10 : 0) +
    (grss.sentiment.llm_news_sentiment ?? 0) * 10
  );

  const velPct = grss.velocity_30min ?? 0;

  return (
    <div className="border border-zinc-800 rounded p-3 font-mono text-xs bg-[#0a0a0f]">
      <div className="flex items-center justify-between mb-3">
        <span className="text-zinc-500 uppercase tracking-widest text-xs">GRSS</span>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold" style={{ color: scoreColor }}>{score.toFixed(1)}</span>
          <span className="text-zinc-600">/ 100</span>
          <span className="text-xs px-1.5 py-0.5 rounded border"
            style={{ borderColor: scoreColor, color: scoreColor }}>{label}</span>
        </div>
      </div>

      {velPct !== 0 && (
        <div className={`text-xs mb-2 ${velPct > 0 ? "text-emerald-400" : "text-red-400"}`}>
          {velPct > 0 ? "▲" : "▼"} Velocity {fmt(velPct, 1)} Punkte letzte 30min
        </div>
      )}

      <div className="space-y-2">
        <div>
          <div className="flex justify-between text-zinc-500 mb-1 text-xs">
            <span>Makro</span>
            <span className="text-zinc-400">
              NDX:{grss.macro.ndx_status?.slice(0,4)} VIX:{grss.macro.vix.toFixed(1)} 10Y:{grss.macro.yields_10y.toFixed(2)}%
              {grss.macro.m2_yoy_pct !== null ? ` M2:${fmt(grss.macro.m2_yoy_pct, 1)}%` : ""}
            </span>
          </div>
          <Bar pts={macroPts} max={40} color="#3b82f6" />
        </div>
        <div>
          <div className="flex justify-between text-zinc-500 mb-1 text-xs">
            <span>Derivate</span>
            <span className="text-zinc-400">
              Fund:{(grss.derivatives.funding_rate * 100).toFixed(3)}%
              PCR:{grss.derivatives.put_call_ratio.toFixed(2)}
              DVOL:{grss.derivatives.dvol.toFixed(0)}
            </span>
          </div>
          <Bar pts={derivPts} max={45} color="#8b5cf6" />
        </div>
        <div>
          <div className="flex justify-between text-zinc-500 mb-1 text-xs">
            <span>Sentiment</span>
            <span className="text-zinc-400">
              F&G:{grss.sentiment.fear_greed}
              {grss.sentiment.stablecoin_delta_bn !== null
                ? ` USDT:${fmt(grss.sentiment.stablecoin_delta_bn, 1)}B` : ""}
            </span>
          </div>
          <Bar pts={sentPts} max={35} color="#f59e0b" />
        </div>
      </div>

      {grss.veto_active && (
        <div className="mt-2 text-red-400 text-xs border-t border-zinc-800 pt-2">
          ⚠ {grss.reason}
        </div>
      )}
      <div className="text-zinc-700 text-xs mt-1">
        Update: {timeAgo(grss.data_quality.last_update)} | Quellen: {grss.data_quality.fresh_source_count} aktiv
      </div>
    </div>
  );
}

function DecisionFeed({ events }: { events: DecisionEvent[] }) {
  return (
    <div className="border border-zinc-800 rounded font-mono text-xs bg-[#0a0a0f]">
      <div className="px-3 py-2 border-b border-zinc-800 flex items-center justify-between">
        <span className="text-zinc-500 uppercase tracking-widest">Live Decision Feed</span>
        <span className="text-zinc-600 text-xs">letzte Zyklen — alle 5 Minuten</span>
      </div>
      <div className="divide-y divide-zinc-900">
        {events.length === 0 && (
          <div className="px-3 py-4 text-zinc-600">Noch keine Events — Bot läuft seit weniger als 5 Minuten</div>
        )}
        {events.slice(0, 12).map((e, i) => {
          const { text, color, icon } = outcomeLabel(e);
          const isSignal = e.outcome?.startsWith("SIGNAL_");
          return (
            <div key={i}
              className={`px-3 py-2 flex items-start gap-3 ${isSignal ? "bg-emerald-950/20" : ""}`}>
              <span className="text-zinc-600 flex-shrink-0 w-12">
                {new Date(e.ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
              </span>
              <span className={`flex-shrink-0 ${color}`}>{icon}</span>
              <span className="text-zinc-400 flex-shrink-0 w-20">
                OFI <span className={Math.abs(e.ofi) >= e.ofi_threshold ? "text-white" : "text-zinc-500"}>
                  {e.ofi >= 0 ? "+" : ""}{e.ofi.toFixed(0)}
                </span>
              </span>
              {e.grss !== null && e.grss !== undefined && (
                <span className="text-zinc-500 flex-shrink-0">
                  GRSS <span className={e.grss >= 48 ? "text-emerald-400" : "text-amber-400"}>{e.grss.toFixed(1)}</span>
                </span>
              )}
              <span className={`${color} truncate`}>{text}</span>
              <span className="text-zinc-600 ml-auto flex-shrink-0">{fmtPrice(e.price)}</span>
            </div>
          );
        })}
      </div>
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
        if (!a) return (
          <span key={id} className="text-zinc-700">{id} ●</span>
        );
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
    ok: data.status === "online" || data.status === "ok",
    age: timeAgo(data.last_update),
    latency: data.latency_ms,
  }));

  if (items.length === 0) return null;

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

// ── Haupt-Export ──────────────────────────────────────────────────────────

export default function Dashboard() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [grss, setGRSS] = useState<GRSSFull | null>(null);
  const [decisions, setDecisions] = useState<DecisionEvent[]>([]);
  const [position, setPosition] = useState<Position | null>(null);
  const [currentPrice, setCurrentPrice] = useState<number | null>(null);

  const API = "/api/v1";

  async function refresh() {
    try {
      const [tel, gr, dec, pos] = await Promise.allSettled([
        fetch(`${API}/telemetry/live`).then(r => r.json()),
        fetch(`${API}/market/grss-full`).then(r => r.json()),
        fetch(`${API}/decisions/feed?limit=20`).then(r => r.json()),
        fetch(`${API}/positions/open`).then(r => r.json()),
      ]);

      if (tel.status === "fulfilled") setTelemetry(tel.value);
      if (gr.status === "fulfilled") setGRSS(gr.value);
      if (dec.status === "fulfilled") setDecisions(dec.value.events ?? []);
      if (pos.status === "fulfilled") {
        setPosition(pos.value.position ?? null);
        setCurrentPrice(pos.value.current_price ?? null);
      }
    } catch (e) {
      console.error("Dashboard fetch error", e);
    }
  }

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 15000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="flex min-h-screen bg-[#0a0a0f] text-white">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <HeaderBar telemetry={telemetry} />
        <div className="flex-1 p-4 space-y-3 overflow-y-auto">
          <OpenPositionPanel position={position} currentPrice={currentPrice} />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <MarketOverview market={telemetry?.market} />
            <GRSSBreakdown grss={grss} />
          </div>

          <DecisionFeed events={decisions} />

          <AgentStatusRow agents={telemetry?.agents ?? {}} />
          <DataFreshnessBar sources={telemetry?.data_sources ?? {}} />
        </div>
      </div>
    </div>
  );
}

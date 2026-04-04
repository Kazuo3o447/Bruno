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
  BarChart,
  Bar,
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
  ChevronRight,
  BarChart3,
  Brain,
  Server,
  Database,
  Wifi,
  Lock,
  Unlock,
  PauseCircle
} from "lucide-react";

// Types
interface Telemetry {
  status: "ARMED" | "HALTED";
  veto_active: boolean;
  veto_reason: string;
  dry_run: boolean;
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

// Gate Detail Component
function GateDetail({ name, data, index }: { name: string; data: any; index: number }) {
  const isBlocked = data?.blocked === true;
  const details = Object.entries(data || {}).filter(([k]) => k !== "blocked" && k !== "note");

  return (
    <div className={`p-4 rounded-xl border ${isBlocked ? "border-red-800 bg-red-950/10" : "border-emerald-800 bg-emerald-950/10"}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`w-3 h-3 rounded-full ${isBlocked ? "bg-red-400 animate-pulse" : "bg-emerald-400"}`} />
          <span className="font-medium text-sm">Gate {index}: {name}</span>
        </div>
        <span className={`text-xs px-2 py-1 rounded ${isBlocked ? "bg-red-500/20 text-red-400" : "bg-emerald-500/20 text-emerald-400"}`}>
          {isBlocked ? "BLOCKED" : "PASS"}
        </span>
      </div>
      {data?.note && (
        <p className="text-xs text-slate-400 mb-2">{data.note}</p>
      )}
      <div className="space-y-1">
        {details.slice(0, 4).map(([key, value]) => (
          <div key={key} className="flex justify-between text-xs">
            <span className="text-slate-500">{key.replace(/_/g, " ")}</span>
            <span className="text-slate-300 font-mono">{String(value).slice(0, 20)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Market Metric Card
function MetricCard({ label, value, subValue, status, icon: Icon }: {
  label: string;
  value: string;
  subValue?: string;
  status: "good" | "warning" | "danger" | "neutral";
  icon: React.ElementType;
}) {
  const colors = {
    good: "border-emerald-800 bg-emerald-950/10",
    warning: "border-amber-800 bg-amber-950/10",
    danger: "border-red-800 bg-red-950/10",
    neutral: "border-slate-800 bg-slate-950/10",
  };

  const textColors = {
    good: "text-emerald-400",
    warning: "text-amber-400",
    danger: "text-red-400",
    neutral: "text-slate-400",
  };

  return (
    <div className={`p-4 rounded-xl border ${colors[status]}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${textColors[status]}`} />
        <span className="text-xs text-slate-500 uppercase">{label}</span>
      </div>
      <div className={`text-lg font-bold ${textColors[status]}`}>{value}</div>
      {subValue && <div className="text-xs text-slate-500 mt-1">{subValue}</div>}
    </div>
  );
}

export default function TradingPage() {
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [pipeline, setPipeline] = useState<TradePipelineStatus | null>(null);
  const [decisions, setDecisions] = useState<DecisionFeedResponse | null>(null);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const refresh = useCallback(async () => {
    try {
      const [telRes, pipeRes, decRes] = await Promise.allSettled([
        fetch("/api/v1/telemetry/live").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/monitoring/debug/trade-pipeline").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
        fetch("/api/v1/decisions/feed?limit=50").then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`)),
      ]);

      if (telRes.status === "fulfilled") setTelemetry(telRes.value);
      if (pipeRes.status === "fulfilled") setPipeline(pipeRes.value);
      if (decRes.status === "fulfilled") setDecisions(decRes.value);

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

  // Decision timeline with more detail
  const decisionTimeline = useMemo(() => {
    if (!decisions?.events) return [];
    return [...decisions.events].reverse().slice(0, 30).map((e, i) => ({
      time: e.ts ? new Date(e.ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "—",
      signal: e.outcome?.includes("SIGNAL_BUY") ? 1 : e.outcome?.includes("SIGNAL_SELL") ? -1 : 0,
      blocked: e.outcome?.includes("HOLD") || e.outcome?.includes("BLOCK") || e.outcome?.includes("VETO") ? 1 : 0,
      ofi: e.ofi || 0,
      grss: e.grss_score || e.composite_score || 0,
    }));
  }, [decisions]);

  // Gate definitions with explanations
  const gates = [
    { key: "gate_1_data_freshness", name: "Data Freshness", icon: Database, desc: "Prüft ob alle Datenquellen aktuell sind" },
    { key: "gate_2_grss_precheck", name: "GRSS Pre-Check", icon: Shield, desc: "Global Risk Stress Score über 20 Punkte" },
    { key: "gate_3_risk_veto", name: "Risk Veto", icon: Lock, desc: "Keine aktiven Risk-Vetos (VIX, Liquidation, etc.)" },
    { key: "gate_4_llm_cascade", name: "LLM Cascade", icon: Brain, desc: "Zeitbasierte Kaskaden-Entscheidung" },
    { key: "gate_5_position_guard", name: "Position Guard", icon: PauseCircle, desc: "Keine offene Position" },
    { key: "gate_6_daily_limit", name: "Daily Limit", icon: BarChart3, desc: "Tägliches Limit nicht erreicht" },
  ];

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
      <div className="min-h-screen bg-[#0a0a0f] text-white p-8 flex items-center justify-center">
        <Activity className="w-8 h-8 text-indigo-400 animate-pulse" />
      </div>
    );
  }

  const armed = telemetry.status === "ARMED";
  const market = telemetry.market;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Trading</h1>
        <p className="text-sm text-slate-500">Marktanalyse & Entscheidungs-Kaskade</p>
      </div>

      {/* Market Overview Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
        <MetricCard
          label="BTC Preis"
          value={fmtPrice(market.btc_price)}
          subValue={`24h: ${fmt(market.btc_change_24h_pct, 2)}%`}
          status={market.btc_change_24h_pct && market.btc_change_24h_pct >= 0 ? "good" : "danger"}
          icon={TrendingUp}
        />
        <MetricCard
          label="GRSS Score"
          value={telemetry.grss?.score ? telemetry.grss.score.toFixed(1) : "—"}
          subValue={`Raw: ${fmt(telemetry.grss?.score_raw, 1)}`}
          status={telemetry.grss?.score && telemetry.grss.score >= 48 ? "good" : telemetry.grss?.score && telemetry.grss.score >= 25 ? "warning" : "danger"}
          icon={Shield}
        />
        <MetricCard
          label="VIX"
          value={fmt(market.vix, 1)}
          subValue={market.vix && market.vix > 30 ? "High Vol" : "Normal"}
          status={market.vix && market.vix > 30 ? "danger" : market.vix && market.vix > 20 ? "warning" : "good"}
          icon={Activity}
        />
        <MetricCard
          label="OFI"
          value={fmt(market.ofi, 3)}
          subValue="Order Flow"
          status={market.ofi && market.ofi > 0.3 ? "good" : market.ofi && market.ofi < -0.3 ? "danger" : "neutral"}
          icon={Zap}
        />
        <MetricCard
          label="Funding Rate"
          value={market.funding_rate ? (market.funding_rate * 100).toFixed(4) + "%" : "—"}
          subValue="8h Funding"
          status={market.funding_rate && market.funding_rate > 0.01 ? "danger" : market.funding_rate && market.funding_rate < 0 ? "good" : "neutral"}
          icon={Clock}
        />
        <MetricCard
          label="Put/Call Ratio"
          value={fmt(market.put_call_ratio, 2)}
          subValue="Options Sentiment"
          status={market.put_call_ratio && market.put_call_ratio < 0.5 ? "good" : market.put_call_ratio && market.put_call_ratio > 0.9 ? "danger" : "neutral"}
          icon={BarChart3}
        />
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Decision Timeline */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-300">Entscheidungs-Timeline (letzte 30)</h3>
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-emerald-500"/> Buy</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500"/> Block</span>
            </div>
          </div>
          <div className="h-[350px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={decisionTimeline}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1a1a2e" />
                <XAxis dataKey="time" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} />
                <YAxis yAxisId="left" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} domain={[-1, 1]} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={false} domain={[0, 100]} />
                <Tooltip 
                  contentStyle={{ background: "#0c0c18", border: "1px solid #1a1a2e", borderRadius: "8px" }}
                  labelStyle={{ color: "#94a3b8" }}
                />
                <ReferenceLine yAxisId="left" y={0} stroke="#334155" />
                <Line yAxisId="left" type="step" dataKey="signal" stroke="#10b981" strokeWidth={2} dot={{ fill: "#10b981" }} />
                <Line yAxisId="right" type="monotone" dataKey="grss" stroke="#6366f1" strokeWidth={1} dot={false} strokeDasharray="3 3" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            <span className="text-emerald-400">Grün</span> = Buy Signal, <span className="text-indigo-400">Lila</span> = GRSS Score
          </p>
        </div>

        {/* Right: Gate Status */}
        <div className="space-y-4">
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-4">6-Gate Entscheidungs-Kaskade</h3>
            
            {/* Pipeline Flow */}
            <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-2">
              {gates.map((gate, i) => {
                const gateData = pipeline?.gates?.[gate.key];
                const isBlocked = gateData?.blocked;
                const isLast = i === gates.length - 1;
                
                return (
                  <div key={gate.key} className="flex items-center gap-2 flex-shrink-0">
                    <div 
                      className={`w-10 h-10 rounded-full flex items-center justify-center text-xs font-bold ${
                        isBlocked ? "bg-red-500/20 text-red-400 border border-red-500" : "bg-emerald-500/20 text-emerald-400 border border-emerald-500"
                      }`}
                      title={`${gate.name}: ${gate.desc}`}
                    >
                      {i + 1}
                    </div>
                    {!isLast && (
                      <ChevronRight className={`w-4 h-4 ${isBlocked ? "text-red-500" : "text-emerald-500"}`} />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Trade Possible Status */}
            <div className={`p-3 rounded-lg border mb-4 ${
              pipeline?.summary?.trade_possible ? "border-emerald-800 bg-emerald-950/20" : "border-red-800 bg-red-950/20"
            }`}>
              <div className="flex items-center gap-2">
                {pipeline?.summary?.trade_possible ? (
                  <Unlock className="w-5 h-5 text-emerald-400" />
                ) : (
                  <Lock className="w-5 h-5 text-red-400" />
                )}
                <span className={pipeline?.summary?.trade_possible ? "text-emerald-400" : "text-red-400"}>
                  {pipeline?.summary?.trade_possible ? "Trading möglich" : "Trading blockiert"}
                </span>
              </div>
              {pipeline?.summary?.blocking_gates && pipeline.summary.blocking_gates.length > 0 && (
                <p className="text-xs text-red-400 mt-2">
                  Blockiert durch: {pipeline.summary.blocking_gates.join(" → ")}
                </p>
              )}
            </div>

            {/* Gate Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {gates.map((gate, i) => (
                <GateDetail 
                  key={gate.key} 
                  name={gate.name} 
                  data={pipeline?.gates?.[gate.key]} 
                  index={i + 1} 
                />
              ))}
            </div>
          </div>

          {/* Quant Micro Data */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Quant Micro Daten</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs text-slate-500">OFI (Order Flow Imbalance)</div>
                <div className={`text-lg font-bold ${
                  pipeline?.quant_micro?.ofi && pipeline.quant_micro.ofi > 0.3 ? "text-emerald-400" : 
                  pipeline?.quant_micro?.ofi && pipeline.quant_micro.ofi < -0.3 ? "text-red-400" : "text-slate-300"
                }`}>
                  {fmt(pipeline?.quant_micro?.ofi, 3)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">OFI Buy Pressure</div>
                <div className="text-lg font-bold text-slate-300">
                  {fmt(pipeline?.quant_micro?.ofi_buy_pressure, 3)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Preis</div>
                <div className="text-lg font-bold text-slate-300">
                  {fmtPrice(pipeline?.quant_micro?.price)}
                </div>
              </div>
              <div>
                <div className="text-xs text-slate-500">Quelle</div>
                <div className="text-sm font-medium text-slate-400">
                  {pipeline?.quant_micro?.source || "—"}
                </div>
              </div>
            </div>
            <div className="mt-3 text-xs text-slate-500">
              Letztes Update: {timeAgo(pipeline?.quant_micro?.timestamp)}
            </div>
          </div>
        </div>
      </div>

      {/* Additional Metrics */}
      <div className="mt-6 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <h3 className="text-sm font-medium text-slate-300 mb-4">Zusätzliche Marktmetriken</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4">
          {[
            { label: "Fear & Greed", value: fmt(market.fear_greed, 0), status: market.fear_greed && market.fear_greed > 75 ? "danger" : market.fear_greed && market.fear_greed < 25 ? "good" : "neutral" },
            { label: "DVOL", value: fmt(market.dvol, 1), status: "neutral" },
            { label: "OI Delta", value: fmt(market.oi_delta_pct, 1) + "%", status: market.oi_delta_pct && market.oi_delta_pct > 5 ? "danger" : market.oi_delta_pct && market.oi_delta_pct < -5 ? "good" : "neutral" },
            { label: "L/S Ratio", value: fmt(market.long_short_ratio, 2), status: market.long_short_ratio && market.long_short_ratio > 2 ? "danger" : "neutral" },
            { label: "Retail Score", value: fmt(market.retail_score, 0), status: market.retail_score && market.retail_score > 60 ? "danger" : "good" },
            { label: "1h Change", value: fmt(market.btc_change_1h_pct, 2) + "%", status: market.btc_change_1h_pct && market.btc_change_1h_pct >= 0 ? "good" : "danger" },
            { label: "24h Change", value: fmt(market.btc_change_24h_pct, 2) + "%", status: market.btc_change_24h_pct && market.btc_change_24h_pct >= 0 ? "good" : "danger" },
            { label: "Sentiment", value: fmt(market.sentiment, 2), status: market.sentiment && market.sentiment > 0.2 ? "good" : market.sentiment && market.sentiment < -0.2 ? "danger" : "neutral" },
          ].map((metric) => (
            <div key={metric.label} className="text-center">
              <div className="text-xs text-slate-500 mb-1">{metric.label}</div>
              <div className={`text-sm font-bold ${
                metric.status === "good" ? "text-emerald-400" : 
                metric.status === "danger" ? "text-red-400" : 
                metric.status === "warning" ? "text-amber-400" : "text-slate-300"
              }`}>{metric.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

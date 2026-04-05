"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  LineChart,
  Line,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from "recharts";

interface DecisionEvent {
  ts: string;
  outcome: string;
  reason: string;
  regime?: string;
  composite_score?: number;
  ta_score?: number;
  liq_score?: number;
  flow_score?: number;
  macro_score?: number;
  ofi?: number;
  grss_score?: number;
  vix?: number;
  diagnostics?: {
    effective_threshold?: number;
    threshold_base?: number;
    threshold_multiplier?: number;
    atr_14?: number;
    price?: number;
    gap_to_threshold?: number;
  };
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

interface PipelineStatus {
  summary: {
    blocking_gates: string[];
    trade_possible: boolean;
    grss_score: number | null;
    vix: number | null;
    data_freshness_active: boolean | null;
    context_timestamp: string | null;
  };
  gates: Record<string, { blocked: boolean; note?: string }>;
  health_sources: Record<string, { status: string; latency_ms: number; last_update: string }>;
}

interface AgentStatus {
  status: string;
  age_seconds: number | null;
  healthy: boolean;
  processed?: number;
  errors?: number;
}

interface GRSSBreakdown {
  vix: number | null;
  ndx: string | null;
  yields: number | null;
  pcr: number | null;
  dvol: number | null;
  funding: number | null;
  sentiment: number | null;
  etf_flows: number | null;
  stablecoin_delta: number | null;
}

function timeAgo(isoStr: string | null | undefined): string {
  if (!isoStr) return "—";
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  return `${Math.floor(diff / 3600)}h`;
}

function fmt(n: number | null | undefined, digits = 2): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}

export default function LogicPage() {
  const [decisions, setDecisions] = useState<DecisionFeedResponse | null>(null);
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [agents, setAgents] = useState<Record<string, AgentStatus> | null>(null);
  const [grssBreakdown, setGrssBreakdown] = useState<GRSSBreakdown | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [decRes, pipeRes, agentRes, grssRes] = await Promise.allSettled([
        fetch("/api/v1/decisions/feed?limit=100").then(r => r.json()),
        fetch("/api/v1/monitoring/debug/trade-pipeline").then(r => r.json()),
        fetch("/api/v1/agents/status").then(r => r.json()),
        fetch("/api/v1/monitoring/phase-a/status").then(r => r.json()),
      ]);

      if (decRes.status === "fulfilled") setDecisions(decRes.value);
      if (pipeRes.status === "fulfilled") setPipeline(pipeRes.value);
      if (agentRes.status === "fulfilled") {
        const agentList = agentRes.value?.agents ?? [];
        const agentRecord: Record<string, AgentStatus> = {};
        for (const agent of agentList) {
          agentRecord[agent.id] = {
            status: agent.status,
            age_seconds: agent.uptime_seconds,
            healthy: agent.health === "healthy",
            processed: agent.processed_count,
            errors: agent.error_count,
          };
        }
        setAgents(agentRecord);
      }
      if (grssRes.status === "fulfilled") setGrssBreakdown(grssRes.value?.grss_breakdown ?? null);
    } catch (e) {
      console.error("Failed to fetch logic data:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 10000);
    return () => clearInterval(iv);
  }, [refresh]);

  // Pipeline stages data
  const pipelineStages = useMemo(() => {
    const gates = pipeline?.gates ?? {};
    return [
      { name: "Data Freshness", status: !gates.gate_1_data_freshness?.blocked, info: "Marktdaten aktuell" },
      { name: "Context", status: !gates.gate_2_context?.blocked, info: "GRSS & Makro verfügbar" },
      { name: "Sentiment", status: !gates.gate_3_sentiment?.blocked, info: "News & Stimmung OK" },
      { name: "Quant Micro", status: !gates.gate_4_quant_micro?.blocked, info: "OFI & Liquidität" },
      { name: "Risk Veto", status: !gates.gate_5_risk_veto?.blocked, info: "6 Hard Vetos geprüft" },
      { name: "Portfolio", status: !gates.gate_6_portfolio?.blocked, info: "Kapital & Limits" },
    ];
  }, [pipeline]);

  // Decision outcomes over time
  const decisionTimeline = useMemo(() => {
    const events = [...(decisions?.events ?? [])].reverse().slice(0, 30);
    return events.map((e, i) => ({
      idx: i,
      time: e.ts ? new Date(e.ts).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : `#${i}`,
      composite: Math.abs(e.composite_score ?? 0),
      threshold: e.diagnostics?.effective_threshold ?? 55,
      signal: e.outcome?.includes("SIGNAL") ? 1 : 0,
      blocked: !e.outcome?.includes("SIGNAL") ? 1 : 0,
      outcome: e.outcome,
      reason: e.reason,
    }));
  }, [decisions]);

  // Composite score components radar
  const compositeRadar = useMemo(() => {
    const latest = decisions?.events?.[0];
    if (!latest) return [];
    return [
      { subject: "TA", A: latest.ta_score ?? 0, fullMark: 100 },
      { subject: "Liquidität", A: latest.liq_score ?? 0, fullMark: 100 },
      { subject: "Flow", A: latest.flow_score ?? 0, fullMark: 100 },
      { subject: "Makro", A: latest.macro_score ?? 0, fullMark: 100 },
      { subject: "GRSS", A: latest.grss_score ?? 0, fullMark: 100 },
      { subject: "OFI", A: (latest.ofi ?? 0) * 100, fullMark: 100 },
    ];
  }, [decisions]);

  // GRSS components
  const grssComponents = useMemo(() => {
    if (!grssBreakdown) return [];
    return [
      { name: "VIX", value: grssBreakdown.vix ?? 0, weight: 0.25, impact: (grssBreakdown.vix ?? 20) * 0.25 },
      { name: "NDX/Makro", value: grssBreakdown.ndx === "risk_off" ? 80 : grssBreakdown.ndx === "risk_on" ? 40 : 60, weight: 0.25, impact: 0 },
      { name: "Yields", value: (grssBreakdown.yields ?? 4) * 10, weight: 0.15, impact: 0 },
      { name: "PCR", value: (grssBreakdown.pcr ?? 1) * 50, weight: 0.15, impact: 0 },
      { name: "Funding", value: Math.abs(grssBreakdown.funding ?? 0) * 2000, weight: 0.10, impact: 0 },
      { name: "Sentiment", value: ((grssBreakdown.sentiment ?? 0) + 1) * 50, weight: 0.10, impact: 0 },
    ];
  }, [grssBreakdown]);

  // Top blockers
  const topBlockers = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of decisions?.events ?? []) {
      if (!e.outcome?.includes("SIGNAL")) {
        const key = e.reason || e.outcome || "Unknown";
        counts[key] = (counts[key] || 0) + 1;
      }
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([name, count]) => ({ name, count }));
  }, [decisions]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] text-white p-8 flex items-center justify-center">
        <div className="text-slate-500 font-mono">Loading Logic Pipeline...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6 space-y-6">
      {/* Header */}
      <div className="border-b border-zinc-800 pb-4">
        <h1 className="text-2xl font-bold bg-gradient-to-r from-indigo-400 to-purple-400 bg-clip-text text-transparent">
          Bruno v2 Logic & Cascade
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Complete decision pipeline, GRSS composition, and trading logic visualization
        </p>
      </div>

      {/* Pipeline Status */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">6-Gate Pipeline</div>
            <div className="text-xs text-slate-600 mt-1">Sequential decision cascade</div>
          </div>
          <div className={`text-xs font-bold px-3 py-1 rounded-full ${pipeline?.summary.trade_possible ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
            {pipeline?.summary.trade_possible ? "TRADE POSSIBLE" : "BLOCKED"}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {pipelineStages.map((stage, idx) => (
            <div key={stage.name} className={`border rounded-lg p-3 ${stage.status ? "border-emerald-800 bg-emerald-950/20" : "border-red-800 bg-red-950/20"}`}>
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${stage.status ? "bg-emerald-400" : "bg-red-400"}`} />
                <span className="text-xs font-bold text-slate-300">Gate {idx + 1}</span>
              </div>
              <div className={`text-sm font-bold ${stage.status ? "text-emerald-400" : "text-red-400"}`}>{stage.name}</div>
              <div className="text-[10px] text-slate-500 mt-1">{stage.info}</div>
            </div>
          ))}
        </div>

        {pipeline?.summary.blocking_gates && pipeline.summary.blocking_gates.length > 0 && (
          <div className="mt-4 p-3 bg-red-950/30 border border-red-800 rounded-lg">
            <div className="text-xs text-red-400 font-bold mb-2">⚠ Active Blockers:</div>
            <div className="text-sm text-red-300 font-mono">{pipeline.summary.blocking_gates.join(" → ")}</div>
          </div>
        )}
      </div>

      {/* GRSS Score Composition */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">GRSS Score Composition</div>
              <div className="text-xs text-slate-600 mt-1">Global Risk & Sentiment Score (0-100)</div>
            </div>
            <div className="text-2xl font-bold font-mono text-indigo-400">
              {fmt(pipeline?.summary.grss_score, 1)}
            </div>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={grssComponents} layout="vertical" margin={{ left: 80 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f1f33" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <YAxis type="category" dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} width={70} />
                <Tooltip contentStyle={{ background: "#090913", border: "1px solid #1f1f33", color: "#e2e8f0" }} />
                <Bar dataKey="value" fill="#6366f1" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-4 text-xs text-slate-500 space-y-1">
            <div className="flex justify-between">
              <span>VIX Weight:</span>
              <span className="text-slate-300">25% (inverse: lower = better)</span>
            </div>
            <div className="flex justify-between">
              <span>NDX/Macro Weight:</span>
              <span className="text-slate-300">25% (risk-on/risk-off/neutral)</span>
            </div>
            <div className="flex justify-between">
              <span>Yields Weight:</span>
              <span className="text-slate-300">15%</span>
            </div>
            <div className="flex justify-between">
              <span>Put/Call Ratio:</span>
              <span className="text-slate-300">15%</span>
            </div>
            <div className="flex justify-between">
              <span>Funding Rate:</span>
              <span className="text-slate-300">10%</span>
            </div>
            <div className="flex justify-between">
              <span>Sentiment:</span>
              <span className="text-slate-300">10%</span>
            </div>
          </div>
        </div>

        {/* Composite Score Radar */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">Composite Score Components</div>
              <div className="text-xs text-slate-600 mt-1">Latest decision cycle breakdown</div>
            </div>
          </div>

          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={compositeRadar}>
                <PolarGrid stroke="#1f1f33" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} />
                <Radar name="Score" dataKey="A" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3} />
                <Tooltip contentStyle={{ background: "#090913", border: "1px solid #1f1f33", color: "#e2e8f0" }} />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
            <div className="p-2 bg-[#0a0a0f] rounded border border-[#1a1a2e]">
              <div className="text-slate-500">TA Score</div>
              <div className="text-indigo-400 font-mono">{fmt(compositeRadar[0]?.A, 1)}</div>
            </div>
            <div className="p-2 bg-[#0a0a0f] rounded border border-[#1a1a2e]">
              <div className="text-slate-500">Liquidity</div>
              <div className="text-indigo-400 font-mono">{fmt(compositeRadar[1]?.A, 1)}</div>
            </div>
            <div className="p-2 bg-[#0a0a0f] rounded border border-[#1a1a2e]">
              <div className="text-slate-500">Flow (OFI)</div>
              <div className="text-indigo-400 font-mono">{fmt(compositeRadar[2]?.A, 1)}</div>
            </div>
            <div className="p-2 bg-[#0a0a0f] rounded border border-[#1a1a2e]">
              <div className="text-slate-500">Macro</div>
              <div className="text-indigo-400 font-mono">{fmt(compositeRadar[3]?.A, 1)}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Decision Timeline */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider">Decision Timeline</div>
            <div className="text-xs text-slate-600 mt-1">Last 30 decision cycles — Signal vs Block</div>
          </div>
          <div className="text-xs font-mono text-slate-500">
            Signals: {decisions?.stats.signals_generated ?? 0} | Holds: {decisions?.stats.cascade_hold ?? 0}
          </div>
        </div>

        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={decisionTimeline}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f1f33" />
              <XAxis dataKey="time" tick={{ fill: "#94a3b8", fontSize: 10 }} angle={-45} textAnchor="end" height={50} />
              <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} domain={[0, 100]} />
              <Tooltip
                contentStyle={{ background: "#090913", border: "1px solid #1f1f33", color: "#e2e8f0" }}
                formatter={(value: any, name: any, props: any) => {
                  if (name === "composite") return [fmt(value, 1), "Abs Score"];
                  if (name === "threshold") return [fmt(value, 1), "Threshold"];
                  if (name === "signal") return [value === 1 ? "Yes" : "No", "Signal"];
                  return [value, name];
                }}
                labelFormatter={(_, payload: any) => {
                  const p = payload?.[0]?.payload;
                  return p ? `${p.time} — ${p.outcome}` : "";
                }}
              />
              <Line type="monotone" dataKey="composite" stroke="#6366f1" strokeWidth={2} dot={false} />
              <Line type="stepAfter" dataKey="threshold" stroke="#f59e0b" strokeWidth={1} strokeDasharray="5 5" dot={false} />
              <Line type="step" dataKey="signal" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Top Blockers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-4">Top Blockers (Last 100 Cycles)</div>
          {topBlockers.length > 0 ? (
            <div className="space-y-2">
              {topBlockers.map((blocker, idx) => (
                <div key={blocker.name} className="flex items-center justify-between p-2 bg-[#0a0a0f] rounded border border-[#1a1a2e]">
                  <div className="flex items-center gap-3">
                    <span className={`text-xs font-bold w-5 ${idx === 0 ? "text-red-400" : idx === 1 ? "text-amber-400" : "text-slate-500"}`}>#{idx + 1}</span>
                    <span className="text-sm text-slate-300">{blocker.name}</span>
                  </div>
                  <span className="text-sm font-mono text-slate-400">{blocker.count}x</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-sm text-slate-500">No blockers recorded</div>
          )}
        </div>

        {/* Agent Status */}
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-4">Agent Pipeline Status</div>
          <div className="grid grid-cols-2 gap-2">
            {agents && Object.entries(agents).map(([name, status]) => (
              <div key={name} className={`p-2 rounded border ${status.healthy ? "border-emerald-800 bg-emerald-950/20" : "border-red-800 bg-red-950/20"}`}>
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${status.healthy ? "bg-emerald-400" : "bg-red-400"}`} />
                  <span className="text-xs font-bold text-slate-300 capitalize">{name}</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-1">{status.status}</div>
                <div className="text-[10px] text-slate-600">{timeAgo(status.age_seconds ? new Date(Date.now() - status.age_seconds * 1000).toISOString() : null)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Decision Rules Reference */}
      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
        <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mb-4">Bruno v2 Decision Rules</div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-xs">
          <div className="space-y-2">
            <div className="font-bold text-indigo-400">Composite Scoring</div>
            <div className="text-slate-400">Score = 0.40×TA + 0.25×Liq + 0.20×Flow + 0.15×Macro</div>
            <div className="text-slate-500">Threshold Learning: 45 | Production: 60</div>
          </div>
          <div className="space-y-2">
            <div className="font-bold text-red-400">6 Hard Vetos</div>
            <div className="text-slate-400 space-y-1">
              <div>1. Data Gap (keine frischen Daten)</div>
              <div>2. Stale Context (&gt;5min alt)</div>
              <div>3. VIX &gt; 45 (Extrem-Fear)</div>
              <div>4. System Pause (manuel)</div>
              <div>5. Death Zone (GRSS &lt; 20)</div>
              <div>6. Daily Drawdown Limit</div>
            </div>
          </div>
          <div className="space-y-2">
            <div className="font-bold text-emerald-400">Risk Management</div>
            <div className="text-slate-400 space-y-1">
              <div>Daily Max Loss: 3%</div>
              <div>Max Consecutive Losses: 3</div>
              <div>Breakeven Trigger: 0.5%</div>
              <div>Trade Cooldown: 300s</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

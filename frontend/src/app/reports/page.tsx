"use client";

import { useEffect, useState, useCallback, Fragment } from "react";
import {
  BarChart3,
  Download,
  RefreshCw,
  Brain,
  TrendingUp,
  Calendar,
  ChevronDown,
  ChevronUp,
  Database,
  Trash2,
} from "lucide-react";

// Types
interface TradeReport {
  id: string;
  trade_id: string;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number;
  pnl_pct: number;
  pnl_eur: number;
  entry_time: string;
  exit_time: string;
  duration_minutes: number;
  grss_at_entry: number;
  ofi_at_entry: number;
  veto_state: string;
  decision_context: Record<string, any>;
  debrief?: {
    decision_quality: string;
    key_signal: string;
    improvement: string;
    pattern: any;
    regime_assessment: string;
    raw_llm_response: any;
  };
}

interface DebriefSummary {
  regime_performance: Record<string, { total: number; win_rate: number }>;
  top_errors: Array<{ error: string; count: number }>;
  accuracy_ranking: {
    technical: number;
    flow: number;
    liquidity: number;
    macro: number;
  };
  recent_history: any[];
}

interface LearningRun {
  id: string;
  timestamp: string;
  run_type: "decision_cycle" | "trade_closed" | "market_analysis";
  context: Record<string, any>;
  decision: string;
  outcome?: string;
  grss_score: number;
  composite_score?: number;
  data_snapshot: Record<string, any>;
}

interface PerformancePeriod {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  total_pnl_eur: number;
  avg_return_per_trade_pct: number;
  best_trade_pct: number;
  worst_trade_pct: number;
  period: string;
  daily_breakdown: any[];
  cumulative_chart_data: any[];
}

export default function ReportsPage() {
  const [trades, setTrades] = useState<TradeReport[]>([]);
  const [learningRuns, setLearningRuns] = useState<LearningRun[]>([]);
  const [performance, setPerformance] = useState<Record<string, PerformancePeriod>>({});
  const [debriefSummary, setDebriefSummary] = useState<DebriefSummary | null>(null);
  const [activeTab, setActiveTab] = useState<"trades" | "learning" | "performance" | "debriefs">("trades");
  const [loading, setLoading] = useState(false);
  const [expandedTrade, setExpandedTrade] = useState<string | null>(null);
  const [dateFilter, setDateFilter] = useState("24h");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch closed trades
      const tradesRes = await fetch("/api/v1/trades/history?limit=100");
      if (tradesRes.ok) {
        const data = await tradesRes.json();
        setTrades(data || []);
      }

      // Fetch debrief summary
      const debriefRes = await fetch("/api/v1/debriefs/summary");
      if (debriefRes.ok) {
        const data = await debriefRes.json();
        setDebriefSummary(data);
      }

      // Fetch performance metrics
      const perfRes = await fetch("/api/v1/performance/simulated");
      if (perfRes.ok) {
        const data = await perfRes.json();
        setPerformance(data.performance_by_period || {});
      }

      // Fetch learning runs from Redis (custom endpoint needed)
      const learningRes = await fetch("/api/v1/decisions/feed?limit=100");
      if (learningRes.ok) {
        const data = await learningRes.json();
        setLearningRuns(data.events?.map((e: any, i: number) => ({
          id: `run-${i}`,
          timestamp: e.ts,
          run_type: e.outcome?.includes("SIGNAL") ? "trade_signal" : "decision_cycle",
          context: e,
          decision: e.outcome,
          grss_score: e.grss_score || 0,
        })) || []);
      }
    } catch (e) {
      console.error("Failed to fetch reports:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const exportData = (type: string) => {
    let data: any;
    let filename: string;

    switch (type) {
      case "trades":
        data = trades;
        filename = `trades-${new Date().toISOString().slice(0, 10)}.json`;
        break;
      case "learning":
        data = learningRuns;
        filename = `learning-runs-${new Date().toISOString().slice(0, 10)}.json`;
        break;
      case "performance":
        data = performance;
        filename = `performance-${new Date().toISOString().slice(0, 10)}.json`;
        break;
      default:
        return;
    }

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const getPnlColor = (pnl: number) => pnl >= 0 ? "text-emerald-400" : "text-red-400";

  const totalPnl = trades.reduce((sum, t) => sum + t.pnl_eur, 0);
  const avgReturn = trades.reduce((sum, t) => sum + t.pnl_pct, 0) / (trades.length || 1);
  const winRate = trades.length > 0 ? (trades.filter(t => t.pnl_pct > 0).length / trades.length) * 100 : 0;

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6 space-y-4">
      <div className="rounded-3xl border border-[#1a1a2e] bg-gradient-to-br from-indigo-950/25 via-[#0c0c18] to-[#080810] p-5 lg:p-6">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.28em] text-slate-500 font-bold">Reports · Lernen & Audit</div>
            <h1 className="text-2xl lg:text-3xl font-bold mt-2">Jeder Run, jeder Trade, jede Auswertung nachvollziehbar</h1>
            <p className="text-sm text-slate-400 mt-2 max-w-3xl">
              Reports speichert die Lernbasis der Plattform: geschlossene Trades dauerhaft, Entscheidungsruns nur kurzzeitig und alles exportierbar für Analyse.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={fetchData} className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm">
              <RefreshCw className="w-4 h-4" />
              Aktualisieren
            </button>
            <button onClick={() => exportData(activeTab)} className="flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm">
              <Download className="w-4 h-4" />
              Export
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
          <div className="text-xs text-slate-500">Closed Trades</div>
          <div className="text-2xl font-bold text-white">{trades.length}</div>
        </div>
        <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
          <div className="text-xs text-slate-500">Win Rate</div>
          <div className="text-2xl font-bold text-emerald-400">{winRate.toFixed(1)}%</div>
        </div>
        <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
          <div className="text-xs text-slate-500">Total P&L</div>
          <div className={`text-2xl font-bold ${getPnlColor(totalPnl)}`}>€{totalPnl.toFixed(2)}</div>
        </div>
        <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
          <div className="text-xs text-slate-500">Avg Return</div>
          <div className={`text-2xl font-bold ${getPnlColor(avgReturn)}`}>{avgReturn.toFixed(2)}%</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {[
          { id: "trades", label: "Geschlossene Trades", icon: TrendingUp },
          { id: "debriefs", label: "DeepSeek Debriefs", icon: Brain },
          { id: "learning", label: "Lern-Logs", icon: Brain },
          { id: "performance", label: "Performance", icon: BarChart3 },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors ${
              activeTab === tab.id
                ? "bg-indigo-600 text-white"
                : "bg-slate-800 text-slate-400 hover:bg-slate-700"
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "trades" && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Total Trades</div>
              <div className="text-2xl font-bold">{trades.length}</div>
            </div>
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Win Rate</div>
              <div className="text-2xl font-bold text-emerald-400">
                {winRate.toFixed(1)}%
              </div>
            </div>
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Total P&L</div>
              <div className={`text-2xl font-bold ${getPnlColor(totalPnl)}`}>
                €{totalPnl.toFixed(2)}
              </div>
            </div>
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Avg Return</div>
              <div className={`text-2xl font-bold ${getPnlColor(avgReturn)}`}>
                {avgReturn.toFixed(2)}%
              </div>
            </div>
          </div>

          {/* Trades List */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-[#080810] text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Zeit</th>
                    <th className="px-4 py-3">Symbol</th>
                    <th className="px-4 py-3">Side</th>
                    <th className="px-4 py-3">Entry/Exit</th>
                    <th className="px-4 py-3">P&L</th>
                    <th className="px-4 py-3">GRSS</th>
                    <th className="px-4 py-3">Dauer</th>
                    <th className="px-4 py-3">LLM</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody className="text-sm divide-y divide-slate-800/50">
                  {trades.map((trade) => (
                    <Fragment key={trade.id}>
                      <tr
                        key={trade.id}
                        className="hover:bg-slate-800/30 cursor-pointer"
                        onClick={() => setExpandedTrade(expandedTrade === trade.id ? null : trade.id)}
                      >
                        <td className="px-4 py-3 text-xs text-slate-400">
                          {new Date(trade.exit_time).toLocaleDateString("de-DE")}
                        </td>
                        <td className="px-4 py-3 font-medium">{trade.symbol}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-1 rounded text-xs ${
                            trade.side === "long" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                          }`}>
                            {trade.side.toUpperCase()}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-400">
                          ${trade.entry_price.toFixed(0)} → ${trade.exit_price.toFixed(0)}
                        </td>
                        <td className="px-4 py-3">
                          <span className={getPnlColor(trade.pnl_pct)}>
                            {trade.pnl_pct > 0 ? "+" : ""}{trade.pnl_pct.toFixed(2)}%
                          </span>
                          <div className="text-xs text-slate-500">€{trade.pnl_eur.toFixed(2)}</div>
                        </td>
                        <td className="px-4 py-3 text-slate-400">{trade.grss_at_entry?.toFixed(1) || "—"}</td>
                        <td className="px-4 py-3 text-xs text-slate-400">{trade.duration_minutes}min</td>
                        <td className="px-4 py-3">
                          {trade.debrief ? (
                            <div className="flex items-center gap-1">
                              <Brain className="w-4 h-4 text-indigo-400" />
                              <span className="text-xs">DeepSeek</span>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {expandedTrade === trade.id ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                        </td>
                      </tr>
                      {expandedTrade === trade.id && (
                        <tr>
                          <td colSpan={9} className="px-4 py-4 bg-[#080810]">
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-xs">
                              <div>
                                <span className="text-slate-500">Entry Time:</span>
                                <div className="text-slate-300">{new Date(trade.entry_time).toLocaleString("de-DE")}</div>
                              </div>
                              <div>
                                <span className="text-slate-500">Exit Time:</span>
                                <div className="text-slate-300">{new Date(trade.exit_time).toLocaleString("de-DE")}</div>
                              </div>
                              <div>
                                <span className="text-slate-500">Veto State:</span>
                                <div className="text-slate-300">{trade.veto_state || "—"}</div>
                              </div>
                              <div>
                                <span className="text-slate-500">OFI at Entry:</span>
                                <div className="text-slate-300">{trade.ofi_at_entry?.toFixed(3) || "—"}</div>
                              </div>
                            </div>
                            {trade.debrief && (
                              <div className="mt-4 p-3 bg-indigo-950/20 border border-indigo-800 rounded-lg">
                                <div className="flex items-center gap-2 mb-2">
                                  <Brain className="w-4 h-4 text-indigo-400" />
                                  <span className="text-sm font-medium text-indigo-400">DeepSeek V3 Debrief</span>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                                  <div>
                                    <span className="text-slate-500">Decision Quality:</span>
                                    <div className="text-slate-300">{trade.debrief.decision_quality}</div>
                                  </div>
                                  <div>
                                    <span className="text-slate-500">Key Signal:</span>
                                    <div className="text-slate-300">{trade.debrief.key_signal}</div>
                                  </div>
                                  <div>
                                    <span className="text-slate-500">Improvement:</span>
                                    <div className="text-slate-300">{trade.debrief.improvement}</div>
                                  </div>
                                  <div>
                                    <span className="text-slate-500">Regime Assessment:</span>
                                    <div className="text-slate-300">{trade.debrief.regime_assessment}</div>
                                  </div>
                                </div>
                              </div>
                            )}
                            {trade.decision_context && Object.keys(trade.decision_context).length > 0 && (
                              <div className="mt-4">
                                <span className="text-slate-500">Decision Context:</span>
                                <pre className="mt-1 p-2 bg-black/30 rounded text-xs text-slate-400 overflow-x-auto">
                                  {JSON.stringify(trade.decision_context, null, 2)}
                                </pre>
                              </div>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>

            {trades.length === 0 && !loading && (
              <div className="text-center py-12 text-slate-500">
                <TrendingUp className="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p>Keine abgeschlossenen Trades</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Learning Tab */}
      {activeTab === "learning" && (
        <div className="space-y-4">
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-medium text-slate-300">Entscheidungs-Lern-Logs (24h)</h3>
                <p className="text-xs text-slate-500 mt-1">Jeder Run dokumentiert Input, Entscheidung und Kontext für die spätere Auswertung.</p>
              </div>
              <div className="flex items-center gap-2">
                <select value={dateFilter} onChange={(e) => setDateFilter(e.target.value)} className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1 text-xs">
                  <option value="1h">Letzte Stunde</option>
                  <option value="24h">Letzte 24h</option>
                  <option value="7d">Letzte 7 Tage</option>
                </select>
              </div>
            </div>

            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {learningRuns.map((run, i) => (
                <div key={run.id} className="p-3 bg-[#080810] rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${
                        run.decision?.includes("SIGNAL") ? "bg-emerald-400" : "bg-amber-400"
                      }`} />
                      <span className="text-xs text-slate-500">{new Date(run.timestamp).toLocaleTimeString("de-DE")}</span>
                      <span className="text-sm">{run.decision}</span>
                    </div>
                    <span className="text-xs text-slate-400">GRSS: {run.grss_score?.toFixed(1) || "—"}</span>
                  </div>
                  {run.context && Object.keys(run.context).length > 0 && (
                    <pre className="mt-2 p-2 bg-black/30 rounded text-xs text-slate-500 overflow-x-auto">
                      {JSON.stringify(run.context, null, 2)}
                    </pre>
                  )}
                </div>
              ))}

              {learningRuns.length === 0 && (
                <div className="text-center py-8 text-slate-500">
                  <Brain className="w-10 h-10 mx-auto mb-2 opacity-50" />
                  <p>Keine Lern-Logs verfügbar</p>
                </div>
              )}
            </div>

            <div className="mt-4 p-3 bg-indigo-950/20 border border-indigo-800 rounded-lg">
              <div className="flex items-center gap-2 text-xs text-indigo-400">
                <Database className="w-4 h-4" />
                <span>Lern-Logs werden automatisch nach 24 Stunden gelöscht. Geschlossene Trades bleiben dauerhaft gespeichert.</span>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs text-slate-500">
              <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-3">Decision runs werden als kurzer Audit-Stream gespeichert.</div>
              <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-3">Geschlossene Trades bleiben als dauerhafte Historie erhalten.</div>
              <div className="rounded-xl border border-[#1a1a2e] bg-[#080810] p-3">Exports sind pro Tab direkt als JSON möglich.</div>
            </div>
          </div>
        </div>
      )}

      {/* DeepSeek Debriefs Tab */}
      {activeTab === "debriefs" && (
        <div className="space-y-4">
          {debriefSummary ? (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
                  <h3 className="text-sm font-medium text-slate-300 mb-3">Regime Performance</h3>
                  <div className="space-y-2">
                    {Object.entries(debriefSummary.regime_performance).map(([regime, perf]) => (
                      <div key={regime} className="flex justify-between text-xs">
                        <span className="text-slate-500 capitalize">{regime}</span>
                        <span className="text-slate-300">{perf.total} trades ({perf.win_rate}% WR)</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
                  <h3 className="text-sm font-medium text-slate-300 mb-3">Signal Accuracy Ranking</h3>
                  <div className="space-y-2">
                    {Object.entries(debriefSummary.accuracy_ranking)
                      .sort((a, b) => b[1] - a[1])
                      .map(([signal, accuracy]) => (
                        <div key={signal} className="flex justify-between text-xs">
                          <span className="text-slate-500 capitalize">{signal}</span>
                          <span className="text-slate-300">{accuracy}%</span>
                        </div>
                      ))}
                  </div>
                </div>
                <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
                  <h3 className="text-sm font-medium text-slate-300 mb-3">Top Error Patterns</h3>
                  <div className="space-y-2">
                    {debriefSummary.top_errors.slice(0, 5).map((error, i) => (
                      <div key={i} className="flex justify-between text-xs">
                        <span className="text-slate-500 truncate">{error.error}</span>
                        <span className="text-slate-300">{error.count}x</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Recent Debriefs */}
              <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
                <h3 className="text-sm font-medium text-slate-300 mb-4">Recent DeepSeek Debriefs</h3>
                <div className="space-y-3 max-h-[500px] overflow-y-auto">
                  {debriefSummary.recent_history.map((debrief, idx) => (
                    <div key={idx} className="p-3 bg-[#080810] rounded-lg">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-slate-500">
                          {new Date(debrief.timestamp).toLocaleString("de-DE")}
                        </span>
                        <span className={`px-2 py-1 rounded text-xs ${
                          debrief.outcome === "profitable" ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                        }`}>
                          {debrief.outcome}
                        </span>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-slate-500">Decision Quality:</span>
                          <div className="text-slate-300">{debrief.decision_quality}</div>
                        </div>
                        <div>
                          <span className="text-slate-500">Key Signal:</span>
                          <div className="text-slate-300">{debrief.key_signal}</div>
                        </div>
                        <div className="col-span-full">
                          <span className="text-slate-500">Improvement:</span>
                          <div className="text-slate-300">{debrief.improvement}</div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-slate-500">
              <Brain className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Keine DeepSeek Debriefs verfügbar</p>
              <p className="text-xs mt-2">Debriefs erscheinen hier nach geschlossenen Trades</p>
            </div>
          )}
        </div>
      )}

      {/* Performance Tab */}
      {activeTab === "performance" && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {["24h", "1w", "6m", "1y", "ytd"].map((period) => {
              const data = performance[period];
              if (!data) return null;

              return (
                <div key={period} className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs text-slate-500 uppercase">{period}</span>
                    <Calendar className="w-4 h-4 text-slate-500" />
                  </div>
                  <div className={`text-2xl font-bold ${getPnlColor(data.total_pnl_eur)}`}>
                    €{data.total_pnl_eur.toFixed(2)}
                  </div>
                  <div className="text-xs text-slate-500 mt-1">{data.total_trades} Trades</div>
                  <div className="text-xs text-emerald-400">{data.win_rate_pct.toFixed(1)}% Win Rate</div>
                  <div className="mt-3 pt-3 border-t border-slate-800 text-xs space-y-1">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Best:</span>
                      <span className="text-emerald-400">+{data.best_trade_pct.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Worst:</span>
                      <span className="text-red-400">{data.worst_trade_pct.toFixed(2)}%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Avg:</span>
                      <span className={getPnlColor(data.avg_return_per_trade_pct)}>{data.avg_return_per_trade_pct.toFixed(2)}%</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Cumulative Chart Placeholder */}
          <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
            <h3 className="text-sm font-medium text-slate-300 mb-4">Kumulative Performance</h3>
            <div className="h-[220px] flex items-center justify-center text-slate-500">
              <BarChart3 className="w-12 h-12 mb-2 opacity-50" />
              <span>Performance-Chart wird hier angezeigt</span>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 text-xs text-slate-500">
        <div className="rounded-xl border border-slate-800 bg-[#0c0c18] p-3">Audit-Logs und Trades dienen als Lernbasis für spätere Auswertungen.</div>
        <div className="rounded-xl border border-slate-800 bg-[#0c0c18] p-3">Exports sind für manuelle Analyse und Berichte gedacht.</div>
        <div className="rounded-xl border border-slate-800 bg-[#0c0c18] p-3">Performance bleibt getrennt von Entscheidungsruns und Trade-Historie.</div>
      </div>
    </div>
  );
}

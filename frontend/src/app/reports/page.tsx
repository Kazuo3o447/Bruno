"use client";

import { useEffect, useState, useCallback } from "react";
import {
  BarChart3,
  Download,
  RefreshCw,
  Brain,
  TrendingUp,
  TrendingDown,
  Clock,
  Calendar,
  Filter,
  ChevronDown,
  ChevronUp,
  FileText,
  Database,
  Trash2,
  CheckCircle,
  AlertCircle
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
  llm_analysis?: {
    rating: number;
    analysis: string;
    recommendation: string;
  };
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
  const [activeTab, setActiveTab] = useState<"trades" | "learning" | "performance">("trades");
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
        setTrades(data.trades || []);
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
  const getPnlBg = (pnl: number) => pnl >= 0 ? "bg-emerald-500/10" : "bg-red-500/10";

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Reports</h1>
            <p className="text-sm text-slate-500">Trade-Auswertungen, Lern-Logs & Performance</p>
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

      {/* Tabs */}
      <div className="flex gap-2 mb-6">
        {[
          { id: "trades", label: "Geschlossene Trades", icon: TrendingUp },
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

      {/* Trades Tab */}
      {activeTab === "trades" && (
        <div className="space-y-4">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Total Trades</div>
              <div className="text-2xl font-bold">{trades.length}</div>
            </div>
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Win Rate</div>
              <div className="text-2xl font-bold text-emerald-400">
                {trades.length > 0
                  ? ((trades.filter(t => t.pnl_pct > 0).length / trades.length) * 100).toFixed(1)
                  : "0"}%
              </div>
            </div>
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Total P&L</div>
              <div className={`text-2xl font-bold ${getPnlColor(trades.reduce((sum, t) => sum + t.pnl_eur, 0))}`}>
                €{trades.reduce((sum, t) => sum + t.pnl_eur, 0).toFixed(2)}
              </div>
            </div>
            <div className="p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
              <div className="text-xs text-slate-500">Avg Return</div>
              <div className={`text-2xl font-bold ${getPnlColor(trades.reduce((sum, t) => sum + t.pnl_pct, 0) / (trades.length || 1))}`}>
                {(trades.reduce((sum, t) => sum + t.pnl_pct, 0) / (trades.length || 1)).toFixed(2)}%
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
                    <>
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
                          {trade.llm_analysis ? (
                            <div className="flex items-center gap-1">
                              <Brain className="w-4 h-4 text-indigo-400" />
                              <span className="text-xs">{trade.llm_analysis.rating}/10</span>
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
                            {trade.llm_analysis && (
                              <div className="mt-4 p-3 bg-indigo-950/20 border border-indigo-800 rounded-lg">
                                <div className="flex items-center gap-2 mb-2">
                                  <Brain className="w-4 h-4 text-indigo-400" />
                                  <span className="text-sm font-medium text-indigo-400">LLM Analysis</span>
                                  <span className="text-xs text-slate-500">Rating: {trade.llm_analysis.rating}/10</span>
                                </div>
                                <p className="text-xs text-slate-300 mb-2">{trade.llm_analysis.analysis}</p>
                                <p className="text-xs text-indigo-400">Recommendation: {trade.llm_analysis.recommendation}</p>
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
                    </>
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
              <h3 className="text-sm font-medium text-slate-300">Entscheidungs-Lern-Logs (24h)</h3>
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
          </div>
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
            <div className="h-[300px] flex items-center justify-center text-slate-500">
              <BarChart3 className="w-12 h-12 mb-2 opacity-50" />
              <span>Performance-Chart wird hier angezeigt</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

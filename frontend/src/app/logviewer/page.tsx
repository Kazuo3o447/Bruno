"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Terminal,
  Filter,
  Download,
  Trash2,
  RefreshCw,
  AlertCircle,
  Info,
  AlertTriangle,
  XCircle,
  CheckCircle,
  Search,
  ChevronDown,
  ChevronUp,
  Wifi,
  WifiOff,
  Clock,
  Copy,
  Check
} from "lucide-react";

// Types
interface LogEntry {
  id: string;
  timestamp: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  category: string;
  source: string;
  message: string;
  metadata?: Record<string, any>;
}

interface LogStats {
  total: number;
  by_level: Record<string, number>;
  categories: string[];
  sources: string[];
}

export default function LogViewerPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [stats, setStats] = useState<LogStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [wsConnected, setWsConnected] = useState(false);
  const [expandedLog, setExpandedLog] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  const [filters, setFilters] = useState({
    level: "",
    category: "",
    source: "",
    search: "",
    limit: 1000,
  });

  const [showFilters, setShowFilters] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filters.level) params.append("level", filters.level);
      if (filters.category) params.append("category", filters.category);
      if (filters.source) params.append("source", filters.source);
      if (filters.search) params.append("search", filters.search);
      params.append("limit", filters.limit.toString());

      const res = await fetch(`/api/v1/logs?${params}`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/v1/logs/stats");
      if (res.ok) {
        const data = await res.json();
        setStats(data.stats);
      }
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    }
  }, []);

  const clearLogs = async () => {
    if (!confirm("Alle Logs löschen?")) return;
    try {
      const res = await fetch("/api/v1/logs/clear", { method: "POST" });
      if (res.ok) {
        fetchLogs();
        fetchStats();
      }
    } catch (e: any) {
      setError(e.message);
    }
  };

  const exportLogs = () => {
    const data = JSON.stringify(logs, null, 2);
    const blob = new Blob([data], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bruno-logs-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket(`ws://${window.location.host}/api/v1/logs/ws`);
      
      ws.onopen = () => {
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "new_log") {
          setLogs(prev => [data.log, ...prev].slice(0, filters.limit));
        } else if (data.type === "history") {
          setLogs(data.logs || []);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        setTimeout(connectWebSocket, 5000);
      };

      ws.onerror = () => {
        setWsConnected(false);
      };

      wsRef.current = ws;
    };

    connectWebSocket();
    return () => {
      wsRef.current?.close();
    };
  }, [filters.limit]);

  useEffect(() => {
    fetchLogs();
    fetchStats();
  }, [fetchLogs, fetchStats]);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const getLevelColor = (level: string) => {
    switch (level) {
      case "DEBUG": return "text-slate-400 bg-slate-900";
      case "INFO": return "text-blue-400 bg-blue-900/30";
      case "WARNING": return "text-amber-400 bg-amber-900/30";
      case "ERROR": return "text-red-400 bg-red-900/30";
      case "CRITICAL": return "text-red-500 bg-red-900/50 animate-pulse";
      default: return "text-slate-400 bg-slate-900";
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level) {
      case "DEBUG": return <Info className="w-4 h-4" />;
      case "INFO": return <Info className="w-4 h-4" />;
      case "WARNING": return <AlertTriangle className="w-4 h-4" />;
      case "ERROR": return <XCircle className="w-4 h-4" />;
      case "CRITICAL": return <AlertCircle className="w-4 h-4" />;
      default: return <Info className="w-4 h-4" />;
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-6">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Logs</h1>
            <p className="text-sm text-slate-500">Vollständiges System-Logging</p>
          </div>
          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-xs ${wsConnected ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
              {wsConnected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {wsConnected ? "Live" : "Offline"}
            </div>
            <button onClick={() => setShowFilters(!showFilters)} className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm">
              <Filter className="w-4 h-4" />
              Filter
            </button>
            <button onClick={exportLogs} className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm">
              <Download className="w-4 h-4" />
              Export
            </button>
            <button onClick={clearLogs} className="flex items-center gap-2 px-3 py-2 bg-red-900/30 hover:bg-red-900/50 border border-red-800 rounded-lg text-sm text-red-400">
              <Trash2 className="w-4 h-4" />
              Löschen
            </button>
            <button onClick={fetchLogs} className="flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm">
              <RefreshCw className="w-4 h-4" />
              Aktualisieren
            </button>
          </div>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-4">
          <div className="p-3 bg-slate-900/50 rounded-lg text-center">
            <div className="text-xs text-slate-500">Total</div>
            <div className="text-lg font-bold text-slate-300">{stats.total}</div>
          </div>
          {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map(level => (
            <div key={level} className="p-3 bg-slate-900/50 rounded-lg text-center">
              <div className="text-xs text-slate-500">{level}</div>
              <div className={`text-lg font-bold ${getLevelColor(level).split(" ")[0]}`}>
                {stats.by_level[level] || 0}
              </div>
            </div>
          ))}
        </div>
      )}

      {showFilters && (
        <div className="mb-4 p-4 bg-[#0c0c18] border border-[#1a1a2e] rounded-xl">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div>
              <label className="text-xs text-slate-500 block mb-1">Level</label>
              <select value={filters.level} onChange={(e) => setFilters(f => ({ ...f, level: e.target.value }))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm">
                <option value="">Alle</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Kategorie</label>
              <select value={filters.category} onChange={(e) => setFilters(f => ({ ...f, category: e.target.value }))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm">
                <option value="">Alle</option>
                {stats?.categories?.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Quelle</label>
              <select value={filters.source} onChange={(e) => setFilters(f => ({ ...f, source: e.target.value }))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm">
                <option value="">Alle</option>
                {stats?.sources?.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Suche</label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <input type="text" value={filters.search} onChange={(e) => setFilters(f => ({ ...f, search: e.target.value }))} placeholder="Nachricht suchen..." className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-2 text-sm" />
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-500 block mb-1">Limit</label>
              <select value={filters.limit} onChange={(e) => setFilters(f => ({ ...f, limit: parseInt(e.target.value) }))} className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm">
                <option value="100">100</option>
                <option value="500">500</option>
                <option value="1000">1000</option>
                <option value="5000">5000</option>
              </select>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-slate-500">{logs.length} Einträge</span>
        <label className="flex items-center gap-2 text-xs text-slate-400 cursor-pointer">
          <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} className="rounded bg-slate-800 border-slate-600" />
          Auto-Scroll
        </label>
      </div>

      <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-[#080810] text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 w-24">Zeit</th>
                <th className="px-4 py-3 w-20">Level</th>
                <th className="px-4 py-3 w-32">Kategorie</th>
                <th className="px-4 py-3 w-32">Quelle</th>
                <th className="px-4 py-3">Nachricht</th>
                <th className="px-4 py-3 w-16"></th>
              </tr>
            </thead>
            <tbody className="text-sm divide-y divide-slate-800/50">
              {logs.map((log) => (
                <>
                  <tr key={log.id} className="hover:bg-slate-800/30 cursor-pointer" onClick={() => setExpandedLog(expandedLog === log.id ? null : log.id)}>
                    <td className="px-4 py-2 text-xs text-slate-400 font-mono whitespace-nowrap">
                      {new Date(log.timestamp).toLocaleTimeString("de-DE")}
                    </td>
                    <td className="px-4 py-2">
                      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded text-xs ${getLevelColor(log.level)}`}>
                        {getLevelIcon(log.level)}
                        {log.level}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-xs text-slate-400">{log.category}</td>
                    <td className="px-4 py-2 text-xs text-slate-400">{log.source}</td>
                    <td className="px-4 py-2 text-slate-300 max-w-md truncate">{log.message}</td>
                    <td className="px-4 py-2">
                      {log.metadata && Object.keys(log.metadata).length > 0 && (
                        expandedLog === log.id ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />
                      )}
                    </td>
                  </tr>
                  {expandedLog === log.id && log.metadata && (
                    <tr>
                      <td colSpan={6} className="px-4 py-3 bg-[#080810]">
                        <div className="flex justify-between items-start mb-2">
                          <span className="text-xs text-slate-500 uppercase">Metadaten</span>
                          <button onClick={(e) => { e.stopPropagation(); copyToClipboard(JSON.stringify(log, null, 2), log.id); }} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
                            {copiedId === log.id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                            {copiedId === log.id ? "Kopiert!" : "Kopieren"}
                          </button>
                        </div>
                        <pre className="text-xs text-slate-400 font-mono bg-black/30 p-3 rounded-lg overflow-x-auto">
                          {JSON.stringify(log.metadata, null, 2)}
                        </pre>
                        <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                          <div className="text-slate-500">ID: <span className="text-slate-400 font-mono">{log.id}</span></div>
                          <div className="text-slate-500">Zeit: <span className="text-slate-400">{new Date(log.timestamp).toLocaleString("de-DE")}</span></div>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>

        {logs.length === 0 && !loading && (
          <div className="text-center py-12 text-slate-500">
            <Terminal className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p>Keine Logs gefunden</p>
          </div>
        )}

        {loading && (
          <div className="text-center py-4 text-slate-500">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto" />
          </div>
        )}

        <div ref={logsEndRef} />
      </div>
    </div>
  );
}

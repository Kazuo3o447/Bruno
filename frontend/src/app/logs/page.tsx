"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import {
  Terminal as TerminalIcon,
  Search,
  Trash2,
  Filter,
  Cpu,
  ShieldCheck,
  BarChart3,
  Zap,
  Clock,
  Info,
  AlertTriangle,
  XCircle,
  Bug,
  ChevronRight
} from "lucide-react";

interface LogEntry {
  timestamp: string;
  level: string;
  category: string;
  source: string;
  message: string;
  data?: any;
}

const LEVEL_COLORS: Record<string, string> = {
  INFO: "text-blue-400",
  WARNING: "text-amber-400",
  ERROR: "text-red-400",
  CRITICAL: "text-red-600 font-bold",
  DEBUG: "text-slate-500",
};

const LEVEL_BG: Record<string, string> = {
  INFO: "bg-blue-500/10 border-blue-500/20 text-blue-400",
  WARNING: "bg-amber-500/10 border-amber-500/20 text-amber-400",
  ERROR: "bg-red-500/10 border-red-500/20 text-red-400",
  CRITICAL: "bg-red-500/15 border-red-500/30 text-red-500",
  DEBUG: "bg-slate-800 border-slate-700 text-slate-400",
};

const LEVEL_ICONS: Record<string, any> = {
  INFO: Info,
  WARNING: AlertTriangle,
  ERROR: XCircle,
  CRITICAL: XCircle,
  DEBUG: Bug,
};

const SOURCE_ICONS: Record<string, any> = {
  "agent.quant": Cpu,
  "agent.risk": ShieldCheck,
  "agent.execution": Zap,
  "agent.sentiment": BarChart3,
  "ingestion": Clock,
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filterLevel, setFilterLevel] = useState<string>("ALL");
  const [filterSource, setFilterSource] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [autoScroll, setAutoScroll] = useState(true);
  const [expandedLog, setExpandedLog] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Connection Management
  useEffect(() => {
    let mounted = true;
    const connect = () => {
      try {
        const ws = new WebSocket("ws://localhost:8000/api/v1/logs/ws");
        wsRef.current = ws;

        ws.onmessage = (event: MessageEvent) => {
          if (!mounted) return;
          try {
            const data = JSON.parse(event.data);
            if (data.type === "history") {
              setLogs(data.logs);
            } else if (data.type === "new_log") {
              setLogs((prev: LogEntry[]) => [data.log, ...prev].slice(0, 500));
            }
          } catch (e) {
            console.error("Log Parse Error", e);
          }
        };

        ws.onerror = (error) => {
          console.error("WebSocket Error:", error);
          // Fallback to REST API on WebSocket error
          fetchLogsViaREST();
        };

        ws.onclose = () => {
          console.log("WebSocket closed, reconnecting in 3s...");
          if (mounted) {
            setTimeout(connect, 3000);
          }
        };
      } catch (error) {
        console.error("WebSocket connection error:", error);
        // Fallback to REST API
        fetchLogsViaREST();
        if (mounted) {
          setTimeout(connect, 5000);
        }
      }
    };

    const fetchLogsViaREST = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/v1/logs?limit=100");
        const data = await response.json();
        if (data.logs && mounted) {
          setLogs(data.logs);
        }
      } catch (e) {
        console.error("REST API fallback failed:", e);
      }
    };

    connect();
    return () => {
      mounted = false;
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Auto-scroll handler
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [logs, autoScroll]);

  // Counts per level (always computed from ALL logs, not filtered)
  const counts = useMemo(() => {
    const c = { INFO: 0, WARNING: 0, ERROR: 0, CRITICAL: 0, DEBUG: 0 };
    for (const log of logs) {
      if (log.level in c) c[log.level as keyof typeof c]++;
    }
    return c;
  }, [logs]);

  // Filtering Logic
  const filteredLogs = useMemo(() => {
    return logs.filter((log: LogEntry) => {
      const matchesLevel = filterLevel === "ALL" || log.level === filterLevel;
      const matchesSource = filterSource === "ALL" || log.source.includes(filterSource.toLowerCase());
      const matchesSearch = !searchQuery ||
        log.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
        log.source.toLowerCase().includes(searchQuery.toLowerCase());

      return matchesLevel && matchesSource && matchesSearch;
    });
  }, [logs, filterLevel, filterSource, searchQuery]);

  const clearLogs = async () => {
    try {
      await fetch("http://localhost:8000/api/v1/logs/clear", { method: "POST" });
      setLogs([]);
    } catch (e) {
      console.error("Clear logs failed", e);
    }
  };

  const handleBadgeClick = (level: string) => {
    setFilterLevel(filterLevel === level ? "ALL" : level);
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden animate-page-in">
      {/* Header */}
      <header className="border-b border-[#1a1a2e] bg-[#08081a]/90 backdrop-blur-md shrink-0 z-10">
        <div className="flex items-center justify-between px-6 lg:px-8 py-5">
          <div className="flex items-center gap-4">
            <div className="p-2.5 bg-indigo-500/10 rounded-xl border border-indigo-500/20">
              <TerminalIcon className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight">Aktivitäten</h1>
              <p className="text-xs text-slate-500 font-medium">Echtzeit-Überwachung aller Systemereignisse</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-indigo-400 transition-colors" />
              <input
                type="text"
                placeholder="Logs durchsuchen..."
                value={searchQuery}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-indigo-500/50 w-64 transition-all"
              />
            </div>
            <button
              onClick={clearLogs}
              className="p-2.5 bg-red-500/5 hover:bg-red-500/10 text-red-400 rounded-xl border border-red-500/20 transition-all group"
              title="Alle Logs löschen"
            >
              <Trash2 className="w-5 h-5 group-hover:scale-110 transition-transform" />
            </button>
          </div>
        </div>

        {/* Level Counter Badges + Filters */}
        <div className="px-6 lg:px-8 pb-4 flex items-center gap-6">
          {/* Clickable Level Badges */}
          <div className="flex items-center gap-2">
            <LevelBadge
              level="INFO"
              count={counts.INFO}
              icon={Info}
              active={filterLevel === "INFO"}
              onClick={() => handleBadgeClick("INFO")}
              color="bg-blue-500/10 border-blue-500/25 text-blue-400 hover:bg-blue-500/20"
              activeColor="bg-blue-500/25 border-blue-400 text-blue-300 ring-1 ring-blue-500/30"
            />
            <LevelBadge
              level="WARNING"
              count={counts.WARNING}
              icon={AlertTriangle}
              active={filterLevel === "WARNING"}
              onClick={() => handleBadgeClick("WARNING")}
              color="bg-amber-500/10 border-amber-500/25 text-amber-400 hover:bg-amber-500/20"
              activeColor="bg-amber-500/25 border-amber-400 text-amber-300 ring-1 ring-amber-500/30"
            />
            <LevelBadge
              level="ERROR"
              count={counts.ERROR + counts.CRITICAL}
              icon={XCircle}
              active={filterLevel === "ERROR" || filterLevel === "CRITICAL"}
              onClick={() => handleBadgeClick("ERROR")}
              color="bg-red-500/10 border-red-500/25 text-red-400 hover:bg-red-500/20"
              activeColor="bg-red-500/25 border-red-400 text-red-300 ring-1 ring-red-500/30"
            />
          </div>

          <div className="h-5 w-px bg-[#1a1a2e]" />

          {/* Source Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-slate-600" />
            <select
              value={filterSource}
              onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setFilterSource(e.target.value)}
              className="bg-transparent text-slate-400 text-sm font-medium focus:outline-none cursor-pointer hover:text-white transition-colors"
            >
              <option value="ALL">Alle Quellen</option>
              <option value="QUANT">Quant Agent</option>
              <option value="RISK">Risk Agent</option>
              <option value="SENTIMENT">Sentiment Agent</option>
              <option value="EXECUTION">Execution Agent</option>
              <option value="INGESTION">Data Ingestion</option>
            </select>
          </div>

          {/* Right: meta info */}
          <div className="ml-auto flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setAutoScroll(e.target.checked)}
                className="hidden"
              />
              <div className={`w-8 h-4 rounded-full transition-colors relative ${autoScroll ? 'bg-indigo-600' : 'bg-slate-700'}`}>
                <div className={`absolute top-1 w-2 h-2 rounded-full bg-white transition-all ${autoScroll ? 'right-1' : 'left-1'}`} />
              </div>
              <span className={`text-[11px] font-bold uppercase tracking-tight transition-colors ${autoScroll ? 'text-indigo-400' : 'text-slate-500'}`}>
                Auto-Scroll
              </span>
            </label>
            <div className="h-4 w-px bg-[#1a1a2e]" />
            {filterLevel !== "ALL" && (
              <button
                onClick={() => setFilterLevel("ALL")}
                className="text-[10px] text-indigo-400 hover:text-indigo-300 font-bold uppercase tracking-wider transition-colors"
              >
                Filter zurücksetzen
              </button>
            )}
            <div className="text-[11px] font-bold text-slate-500 uppercase tracking-tight font-mono">
              {filteredLogs.length} / {logs.length} Einträge
            </div>
          </div>
        </div>
      </header>

      {/* Terminal Area */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 lg:px-6 font-mono text-[13px] leading-relaxed custom-scrollbar bg-[#04040c]"
      >
        {filteredLogs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center opacity-20 select-none">
            <TerminalIcon className="w-16 h-16 mb-4" />
            <p className="text-lg font-bold uppercase tracking-widest">
              {logs.length === 0 ? "Verbinde zum Log-Stream…" : "Keine Logs für diesen Filter"}
            </p>
          </div>
        ) : (
          <div className="space-y-0.5">
            {filteredLogs.map((log: LogEntry, idx: number) => {
              const LevelIcon = LEVEL_ICONS[log.level] || Info;
              const isExpanded = expandedLog === idx;

              return (
                <div
                  key={idx}
                  onClick={() => setExpandedLog(isExpanded ? null : idx)}
                  className={`group flex gap-3 p-2.5 rounded-lg border cursor-pointer transition-all ${
                    isExpanded
                      ? "bg-indigo-500/5 border-indigo-500/15"
                      : "border-transparent hover:bg-white/[0.015] hover:border-[#1a1a2e]"
                  }`}
                >
                  {/* Level Icon */}
                  <div className="shrink-0 mt-0.5">
                    <LevelIcon className={`w-3.5 h-3.5 ${LEVEL_COLORS[log.level] || "text-slate-500"}`} />
                  </div>

                  {/* Timestamp */}
                  <div className="shrink-0 w-20 text-slate-600 font-medium select-none text-[12px]">
                    {new Date(log.timestamp).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </div>

                  {/* Level */}
                  <div className={`shrink-0 w-16 font-bold text-[10px] uppercase tracking-tight ${LEVEL_COLORS[log.level] || 'text-slate-400'}`}>
                    {log.level}
                  </div>

                  {/* Source */}
                  <div className="shrink-0 w-28 truncate text-indigo-400/50 font-semibold text-[10px] uppercase tracking-wider flex items-center gap-1.5">
                    {getSourceIcon(log.source)}
                    {log.source.replace('agent.', '')}
                  </div>

                  {/* Message */}
                  <div className="flex-1 text-slate-300 group-hover:text-slate-200 transition-colors break-all text-[12px]">
                    {log.message}
                  </div>

                  {/* Expand indicator */}
                  {log.data && (
                    <ChevronRight className={`w-3.5 h-3.5 text-slate-700 shrink-0 transition-transform ${isExpanded ? "rotate-90" : ""}`} />
                  )}

                  {/* Expanded data */}
                  {isExpanded && log.data && (
                    <div className="col-span-full mt-2 p-3 bg-black/60 rounded-lg border border-[#1a1a2e] text-[11px] text-slate-500 whitespace-pre overflow-x-auto font-mono">
                      {JSON.stringify(log.data, null, 2)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Sub-Components ─── */

function LevelBadge({
  level, count, icon: Icon, active, onClick, color, activeColor
}: {
  level: string; count: number; icon: any; active: boolean; onClick: () => void; color: string; activeColor: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-[11px] font-bold uppercase tracking-wider transition-all ${
        active ? activeColor : color
      }`}
    >
      <Icon className="w-3.5 h-3.5" />
      <span>{level}</span>
      <span className={`ml-0.5 px-1.5 py-0.5 rounded text-[10px] font-mono ${
        active ? "bg-white/10" : "bg-black/20"
      }`}>
        {count}
      </span>
    </button>
  );
}

function getSourceIcon(source: string) {
  const Icon = SOURCE_ICONS[source] || SOURCE_ICONS[Object.keys(SOURCE_ICONS).find(k => source.includes(k)) || ""] || TerminalIcon;
  return <Icon className="w-3 h-3" />;
}

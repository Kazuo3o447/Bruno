"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface LogEntry {
  timestamp: string;
  level: string;
  category: string;
  source: string;
  message: string;
  details?: Record<string, unknown>;
  stack_trace?: string;
}

interface LogViewerProps {
  isOpen: boolean;
  onClose: () => void;
}

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] as const;
const LOG_CATEGORIES = [
  "SYSTEM",
  "AGENT",
  "TRADING",
  "API",
  "DATABASE",
  "REDIS",
  "WEBSOCKET",
  "BINANCE",
  "LLM",
  "BACKUP",
] as const;

export default function LogViewer({ isOpen, onClose }: LogViewerProps) {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filteredLogs, setFilteredLogs] = useState<LogEntry[]>([]);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  
  // Filter States
  const [levelFilter, setLevelFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("");
  const [sourceFilter, setSourceFilter] = useState<string>("");
  const [searchFilter, setSearchFilter] = useState<string>("");
  const [sources, setSources] = useState<string[]>([]);
  
  const logsEndRef = useRef<HTMLDivElement>(null);
  const logsContainerRef = useRef<HTMLDivElement>(null);

  // WebSocket Connection
  useEffect(() => {
    if (!isOpen) return;

    const websocket = new WebSocket("ws://localhost:8000/api/v1/logs/ws");
    
    websocket.onopen = () => {
      console.log("Log WebSocket connected");
    };
    
    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.type === "history") {
        setLogs(data.logs);
        updateSources(data.logs);
      } else if (data.type === "new_log") {
        setLogs((prev) => [data.log, ...prev].slice(0, 10000));
        if (!sources.includes(data.log.source)) {
          setSources((prev) => [...prev, data.log.source]);
        }
      }
    };
    
    websocket.onerror = (error) => {
      console.error("Log WebSocket error:", error);
    };
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, [isOpen]);

  // Update sources list
  const updateSources = (logData: LogEntry[]) => {
    const uniqueSources = logData.reduce<string[]>((acc, log) => {
      if (!acc.includes(log.source)) {
        acc.push(log.source);
      }
      return acc;
    }, []);
    setSources(uniqueSources);
  };

  // Apply filters
  useEffect(() => {
    let filtered = [...logs];
    
    if (levelFilter) {
      filtered = filtered.filter((log) => log.level === levelFilter);
    }
    
    if (categoryFilter) {
      filtered = filtered.filter((log) => log.category === categoryFilter);
    }
    
    if (sourceFilter) {
      filtered = filtered.filter((log) => log.source === sourceFilter);
    }
    
    if (searchFilter) {
      const search = searchFilter.toLowerCase();
      filtered = filtered.filter(
        (log) =>
          log.message.toLowerCase().includes(search) ||
          log.source.toLowerCase().includes(search) ||
          log.category.toLowerCase().includes(search)
      );
    }
    
    setFilteredLogs(filtered);
  }, [logs, levelFilter, categoryFilter, sourceFilter, searchFilter]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && logsEndRef.current && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = 0;
    }
  }, [filteredLogs, autoScroll]);

  // Clear logs
  const handleClear = async () => {
    try {
      const response = await fetch("http://localhost:8000/api/v1/logs/clear", {
        method: "POST",
      });
      const data = await response.json();
      
      if (data.status === "success") {
        setLogs([]);
        setFilteredLogs([]);
      }
    } catch (error) {
      console.error("Failed to clear logs:", error);
    }
  };

  // Get level color
  const getLevelColor = (level: string) => {
    switch (level) {
      case "DEBUG":
        return "text-gray-400";
      case "INFO":
        return "text-blue-400";
      case "WARNING":
        return "text-yellow-400";
      case "ERROR":
        return "text-red-400";
      case "CRITICAL":
        return "text-red-600 font-bold";
      default:
        return "text-gray-400";
    }
  };

  // Get level background
  const getLevelBg = (level: string) => {
    switch (level) {
      case "DEBUG":
        return "bg-gray-900/50";
      case "INFO":
        return "bg-blue-900/20";
      case "WARNING":
        return "bg-yellow-900/20";
      case "ERROR":
        return "bg-red-900/20";
      case "CRITICAL":
        return "bg-red-900/40";
      default:
        return "bg-gray-900/50";
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/70 backdrop-blur-sm"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="relative w-full max-w-7xl h-[85vh] bg-[#1a1a2e] rounded-xl border border-gray-700 shadow-2xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700 bg-[#1a1a2e] rounded-t-xl">
          <div className="flex items-center gap-4">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <svg className="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              System Logs
              <span className="text-sm font-normal text-gray-400">
                ({filteredLogs.length} / {logs.length} entries)
              </span>
            </h2>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Auto-scroll toggle */}
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2 ${
                autoScroll
                  ? "bg-green-600/20 text-green-400 border border-green-600/50"
                  : "bg-gray-700 text-gray-400 border border-gray-600"
              }`}
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
              </svg>
              Auto-Scroll
            </button>
            
            {/* Clear button */}
            <button
              onClick={handleClear}
              className="px-3 py-1.5 rounded-lg text-sm font-medium bg-red-600/20 text-red-400 border border-red-600/50 hover:bg-red-600/30 transition-colors flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Clear
            </button>
            
            {/* Close button */}
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-gray-700 transition-colors"
            >
              <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="px-6 py-3 border-b border-gray-700 bg-[#16162a] flex flex-wrap items-center gap-3">
          {/* Level Filter */}
          <select
            value={levelFilter}
            onChange={(e) => setLevelFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-[#1a1a2e] border border-gray-600 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
          >
            <option value="">All Levels</option>
            {LOG_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>

          {/* Category Filter */}
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-[#1a1a2e] border border-gray-600 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
          >
            <option value="">All Categories</option>
            {LOG_CATEGORIES.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>

          {/* Source Filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-[#1a1a2e] border border-gray-600 text-sm text-gray-300 focus:border-blue-500 focus:outline-none max-w-[150px]"
          >
            <option value="">All Sources</option>
            {sources.map((source) => (
              <option key={source} value={source}>
                {source}
              </option>
            ))}
          </select>

          {/* Search */}
          <div className="relative flex-1 min-w-[200px]">
            <input
              type="text"
              placeholder="Search logs..."
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              className="w-full px-3 py-1.5 pl-9 rounded-lg bg-[#1a1a2e] border border-gray-600 text-sm text-gray-300 focus:border-blue-500 focus:outline-none"
            />
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>

          {/* Reset filters */}
          {(levelFilter || categoryFilter || sourceFilter || searchFilter) && (
            <button
              onClick={() => {
                setLevelFilter("");
                setCategoryFilter("");
                setSourceFilter("");
                setSearchFilter("");
              }}
              className="px-3 py-1.5 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
            >
              Reset
            </button>
          )}
        </div>

        {/* Log List */}
        <div
          ref={logsContainerRef}
          className="flex-1 overflow-y-auto p-4 space-y-1 font-mono text-sm"
        >
          {filteredLogs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              No logs to display
            </div>
          ) : (
            filteredLogs.map((log, index) => (
              <div
                key={index}
                onClick={() => setSelectedLog(log)}
                className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer hover:bg-gray-800/50 transition-colors ${getLevelBg(log.level)}`}
              >
                {/* Timestamp */}
                <span className="text-gray-500 text-xs whitespace-nowrap pt-0.5">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                
                {/* Level Badge */}
                <span className={`text-xs font-bold whitespace-nowrap pt-0.5 ${getLevelColor(log.level)}`}>
                  {log.level}
                </span>
                
                {/* Category */}
                <span className="text-xs text-purple-400 whitespace-nowrap pt-0.5">
                  [{log.category}]
                </span>
                
                {/* Source */}
                <span className="text-xs text-cyan-400 whitespace-nowrap pt-0.5">
                  {log.source}
                </span>
                
                {/* Message */}
                <span className="text-gray-300 flex-1 break-all pt-0.5">
                  {log.message}
                </span>

                {/* Expand indicator for logs with details */}
                {(log.details || log.stack_trace) && (
                  <svg className="w-4 h-4 text-gray-500 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-gray-700 bg-[#16162a] rounded-b-xl flex items-center justify-between text-sm text-gray-400">
          <div className="flex items-center gap-4">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500"></span>
              WebSocket {ws?.readyState === WebSocket.OPEN ? "Connected" : "Disconnected"}
            </span>
          </div>
          <div className="flex items-center gap-4">
            {LOG_LEVELS.map((level) => {
              const count = logs.filter((l) => l.level === level).length;
              return count > 0 ? (
                <span key={level} className={`${getLevelColor(level)}`}>
                  {level}: {count}
                </span>
              ) : null;
            })}
          </div>
        </div>
      </div>

      {/* Log Detail Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-60 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/80" onClick={() => setSelectedLog(null)} />
          <div className="relative w-full max-w-4xl max-h-[80vh] bg-[#1a1a2e] rounded-xl border border-gray-700 shadow-2xl flex flex-col">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
              <h3 className="text-lg font-bold text-white">Log Details</h3>
              <button onClick={() => setSelectedLog(null)} className="p-2 hover:bg-gray-700 rounded-lg">
                <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-6 overflow-y-auto space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs text-gray-500 uppercase">Timestamp</label>
                  <p className="text-sm text-gray-300">{new Date(selectedLog.timestamp).toLocaleString()}</p>
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase">Level</label>
                  <p className={`text-sm font-bold ${getLevelColor(selectedLog.level)}`}>{selectedLog.level}</p>
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase">Category</label>
                  <p className="text-sm text-purple-400">{selectedLog.category}</p>
                </div>
                <div>
                  <label className="text-xs text-gray-500 uppercase">Source</label>
                  <p className="text-sm text-cyan-400">{selectedLog.source}</p>
                </div>
              </div>
              <div>
                <label className="text-xs text-gray-500 uppercase">Message</label>
                <p className="text-sm text-gray-300 mt-1 p-3 bg-gray-900 rounded-lg">{selectedLog.message}</p>
              </div>
              {selectedLog.details && (
                <div>
                  <label className="text-xs text-gray-500 uppercase">Details</label>
                  <pre className="text-xs text-gray-300 mt-1 p-3 bg-gray-900 rounded-lg overflow-x-auto">
                    {JSON.stringify(selectedLog.details, null, 2)}
                  </pre>
                </div>
              )}
              {selectedLog.stack_trace && (
                <div>
                  <label className="text-xs text-gray-500 uppercase">Stack Trace</label>
                  <pre className="text-xs text-red-400 mt-1 p-3 bg-red-900/20 rounded-lg overflow-x-auto whitespace-pre-wrap">
                    {selectedLog.stack_trace}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

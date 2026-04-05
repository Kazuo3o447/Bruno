"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Server,
  Wifi,
  AlertTriangle,
  Cpu,
  Terminal,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Layers,
  Shield,
  Bot,
  Brain,
  Radio,
  Circle,
  Gauge,
  Zap,
  Database,
  Play,
  Pause,
  ArrowUpRight,
  ArrowDownRight
} from "lucide-react";

// Types - matching the actual API responses
interface AgentStatus {
  id: string;
  name: string;
  type: string;
  status: string;
  sub_state: string;
  last_activity: string;
  uptime_seconds: number;
  processed_count: number;
  error_count: number;
  consecutive_errors: number;
  last_error: string | null;
  health: string;
  description: string;
}

interface AgentsResponse {
  agents: AgentStatus[];
  overall_status: string;
  last_check: string;
  total_agents: number;
  running_agents: number;
  error_agents: number;
}

interface HealthSource {
  status: string;
  latency_ms: number;
  last_update: string;
}

interface SchedulerStatus {
  running: boolean;
  paused: boolean;
  interval_minutes: number;
  last_run: string | null;
  next_run: string | null;
  total_executions: number;
}

interface TestResult {
  name: string;
  category: string;
  status: "success" | "error" | "warning";
  response_time_ms: number;
  message: string;
  details?: Record<string, any>;
  timestamp: string;
}

interface SystemTestResponse {
  overall_status: string;
  total_tests: number;
  passed: number;
  failed: number;
  tests: TestResult[];
  execution_time_ms: number;
  timestamp: string;
}

// Agent icon mapping
const getAgentIcon = (type: string, className = "w-5 h-5") => {
  switch (type) {
    case "data": return <Database className={className} />;
    case "analysis": return <Brain className={className} />;
    case "context": return <Layers className={className} />;
    case "risk": return <Shield className={className} />;
    case "execution": return <Bot className={className} />;
    default: return <Cpu className={className} />;
  }
};

// Circular progress component
const CircularProgress = ({ value, max, color, size = 60, strokeWidth = 6 }: { 
  value: number; 
  max: number; 
  color: string; 
  size?: number;
  strokeWidth?: number;
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke="currentColor"
          strokeWidth={strokeWidth}
          fill="transparent"
          className="text-slate-800"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          stroke={color}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-500"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-sm font-bold" style={{ color }}>{Math.round(percentage)}%</span>
      </div>
    </div>
  );
};

// Mini bar chart component
const MiniBarChart = ({ data, color = "#22c55e" }: { data: number[]; color?: string }) => {
  const max = Math.max(...data, 1);
  return (
    <div className="flex items-end gap-1 h-8">
      {data.map((val, i) => (
        <div
          key={i}
          className="w-2 rounded-t"
          style={{
            height: `${(val / max) * 100}%`,
            backgroundColor: color,
            opacity: 0.4 + (i / data.length) * 0.6
          }}
        />
      ))}
    </div>
  );
};

export default function MonitorPage() {
  const [testResults, setTestResults] = useState<SystemTestResponse | null>(null);
  const [agentsData, setAgentsData] = useState<AgentsResponse | null>(null);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [healthSources, setHealthSources] = useState<Record<string, HealthSource>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const agentStatuses = agentsData?.agents || [];
  
  // Calculate stats
  const freshSourceCount = Object.values(healthSources).filter(s => 
    ["online", "healthy", "connected", "success", "running", "ok"].includes(s.status.toLowerCase())
  ).length;
  const warningSourceCount = Object.values(healthSources).filter(s => 
    ["degraded", "warning", "fallback", "partial"].includes(s.status.toLowerCase())
  ).length;
  const offlineSourceCount = Object.values(healthSources).filter(s => 
    ["offline", "error", "stopped"].includes(s.status.toLowerCase())
  ).length;

  const healthyAgentCount = agentStatuses.filter(a => a.health === "healthy").length;
  const runningAgentCount = agentStatuses.filter(a => a.status === "running").length;

  const fetchData = useCallback(async () => {
    try {
      const [testRes, agentRes, schedRes, healthRes] = await Promise.allSettled([
        fetch("/api/v1/systemtest/last").then(r => r.ok ? r.json() : null),
        fetch("/api/v1/agents/status").then(r => r.ok ? r.json() : null), // FIXED: was agents_status
        fetch("/api/v1/systemtest/scheduler/status").then(r => r.ok ? r.json() : null),
        fetch("/api/v1/systemtest/health/sources").then(r => r.ok ? r.json() : null),
      ]);

      if (testRes.status === "fulfilled" && testRes.value) setTestResults(testRes.value);
      if (agentRes.status === "fulfilled" && agentRes.value) {
        setAgentsData(agentRes.value);
      }
      if (schedRes.status === "fulfilled" && schedRes.value) setSchedulerStatus(schedRes.value);
      if (healthRes.status === "fulfilled" && healthRes.value) setHealthSources(healthRes.value);

      setLastUpdate(new Date());
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
  }, []);

  const runSystemTest = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/systemtest/run");
      if (res.ok) {
        const data = await res.json();
        setTestResults(data);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const controlScheduler = async (action: "start" | "stop" | "pause") => {
    try {
      const res = await fetch(`/api/v1/systemtest/scheduler/${action}`, { method: "POST" });
      if (res.ok) fetchData();
    } catch (e: any) {
      setError(e.message);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const getStatusIcon = (status: string) => {
    const s = status.toLowerCase();
    switch (s) {
      case "success":
      case "online":
      case "healthy":
      case "connected":
      case "running":
      case "ok":
        return <CheckCircle className="w-5 h-5 text-emerald-400" />;
      case "error":
      case "offline":
      case "stopped":
        return <XCircle className="w-5 h-5 text-red-400" />;
      case "warning":
      case "degraded":
      case "fallback":
      case "partial":
        return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      default:
        return <Activity className="w-5 h-5 text-slate-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    const s = status.toLowerCase();
    switch (s) {
      case "success":
      case "online":
      case "healthy":
      case "connected":
      case "running":
      case "ok":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-800";
      case "error":
      case "offline":
      case "stopped":
        return "text-red-400 bg-red-500/10 border-red-800";
      case "warning":
      case "degraded":
      case "fallback":
      case "partial":
        return "text-amber-400 bg-amber-500/10 border-amber-800";
      default:
        return "text-slate-400 bg-slate-500/10 border-slate-800";
    }
  };

  const getStatusBgColor = (status: string) => {
    const s = status.toLowerCase();
    if (["success", "online", "healthy", "connected", "running", "ok"].includes(s)) return "#22c55e";
    if (["error", "offline", "stopped"].includes(s)) return "#ef4444";
    if (["warning", "degraded", "fallback", "partial"].includes(s)) return "#f59e0b";
    return "#64748b";
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6">
      {/* Header Section */}
      <div className="rounded-3xl border border-[#1a1a2e] bg-gradient-to-br from-indigo-950/25 via-[#0c0c18] to-[#080810] p-5 lg:p-6 mb-6">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2 rounded-xl bg-indigo-500/20 border border-indigo-500/30">
                <Radio className="w-5 h-5 text-indigo-400" />
              </div>
              <div className="text-xs uppercase tracking-[0.28em] text-slate-500 font-bold">System Monitor</div>
            </div>
            <h1 className="text-2xl lg:text-3xl font-bold">Echtzeit-Überwachung</h1>
            <p className="text-sm text-slate-400 mt-2 max-w-2xl">
              Agenten-Status, Datenquellen-Gesundheit und System-Performance auf einen Blick.
            </p>
          </div>
          
          {/* Quick Stats Row */}
          <div className="flex flex-wrap gap-3">
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-4 min-w-[140px]">
              <div className="flex items-center gap-2 mb-1">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-[10px] uppercase tracking-[0.2em] text-emerald-400">Online</span>
              </div>
              <div className="text-2xl font-bold">{runningAgentCount}<span className="text-lg text-slate-500">/{agentStatuses.length}</span></div>
              <div className="text-xs text-slate-500">Agenten aktiv</div>
            </div>
            
            <div className="rounded-2xl border border-blue-500/20 bg-blue-950/20 p-4 min-w-[140px]">
              <div className="flex items-center gap-2 mb-1">
                <Database className="w-4 h-4 text-blue-400" />
                <span className="text-[10px] uppercase tracking-[0.2em] text-blue-400">Quellen</span>
              </div>
              <div className="text-2xl font-bold">{freshSourceCount}<span className="text-lg text-slate-500">/{Object.keys(healthSources).length}</span></div>
              <div className="text-xs text-slate-500">Datenquellen</div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/5 p-4 min-w-[140px]">
              <div className="flex items-center gap-2 mb-1">
                <Clock className="w-4 h-4 text-slate-400" />
                <span className="text-[10px] uppercase tracking-[0.2em] text-slate-400">Update</span>
              </div>
              <div className="text-xl font-bold">{lastUpdate.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</div>
              <div className="text-xs text-slate-500">Letzte Aktualisierung</div>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-950/30 border border-red-800 rounded-xl p-4 mb-6">
          <AlertTriangle className="w-5 h-5 text-red-400 inline mr-2" />
          <span className="text-red-400">{error}</span>
        </div>
      )}

      {/* Main Grid - 2 Columns */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        
        {/* Left Column - Agents */}
        <div className="space-y-6">
          {/* Agent Status Overview */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-indigo-500/20">
                  <Bot className="w-5 h-5 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">Agenten-Status</h2>
                  <p className="text-xs text-slate-500">{runningAgentCount} von {agentStatuses.length} Agenten aktiv</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={fetchData} className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition-colors">
                  <RefreshCw className="w-4 h-4 text-slate-400" />
                </button>
              </div>
            </div>

            {/* Agent Cards Grid */}
            <div className="grid grid-cols-2 gap-3">
              {agentStatuses.map((agent) => {
                const isRunning = agent.status === "running";
                const isHealthy = agent.health === "healthy";
                
                return (
                  <div 
                    key={agent.id} 
                    className={`p-4 rounded-xl border transition-all ${
                      isRunning 
                        ? "border-emerald-500/30 bg-emerald-950/10" 
                        : "border-slate-800 bg-slate-900/30"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <div className={`p-2 rounded-lg ${isRunning ? "bg-emerald-500/20" : "bg-slate-800"}`}>
                          {getAgentIcon(agent.type)}
                        </div>
                        <div>
                          <div className="font-medium text-sm">{agent.name}</div>
                          <div className="text-[10px] text-slate-500 uppercase">{agent.type}</div>
                        </div>
                      </div>
                      <div className={`w-2 h-2 rounded-full ${isHealthy ? "bg-emerald-400" : "bg-red-400"} ${isRunning && "animate-pulse"}`} />
                    </div>
                    
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500">Status</span>
                        <span className={isRunning ? "text-emerald-400" : "text-amber-400"}>{agent.status}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500">Sub-State</span>
                        <span className="text-slate-300">{agent.sub_state}</span>
                      </div>
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500">Processed</span>
                        <span className="text-slate-300">{agent.processed_count.toLocaleString()}</span>
                      </div>
                      {agent.error_count > 0 && (
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-500">Errors</span>
                          <span className="text-red-400">{agent.error_count}</span>
                        </div>
                      )}
                    </div>

                    {/* Uptime bar */}
                    <div className="mt-3">
                      <div className="flex items-center justify-between text-[10px] text-slate-500 mb-1">
                        <span>Uptime</span>
                        <span>{formatUptime(agent.uptime_seconds)}</span>
                      </div>
                      <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${isRunning ? "bg-emerald-500" : "bg-slate-600"}`}
                          style={{ width: `${Math.min(100, (agent.uptime_seconds / 3600) * 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {!agentStatuses.length && (
              <div className="text-center py-12 text-slate-500">
                <Bot className="w-12 h-12 mx-auto mb-3 opacity-30" />
                <p>Keine Agenten-Daten verfügbar</p>
              </div>
            )}
          </div>

          {/* Agent Activity Timeline */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
            <div className="flex items-center gap-3 mb-4">
              <BarChart3 className="w-5 h-5 text-indigo-400" />
              <h2 className="text-lg font-semibold">Aktivität</h2>
            </div>
            <div className="flex items-end gap-2 h-24">
              {agentStatuses.map((agent) => (
                <div key={agent.id} className="flex-1 flex flex-col items-center gap-2">
                  <div 
                    className="w-full bg-indigo-500/30 rounded-t transition-all hover:bg-indigo-500/50"
                    style={{ height: `${Math.max(20, Math.min(100, (agent.processed_count / Math.max(...agentStatuses.map(a => a.processed_count), 1)) * 100))}%` }}
                  />
                  <div className="text-[10px] text-slate-500 truncate w-full text-center">{agent.id}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column - Data Sources & System */}
        <div className="space-y-6">
          {/* Data Sources Health */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
            <div className="flex items-center justify-between mb-5">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-500/20">
                  <Database className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <h2 className="text-lg font-semibold">Datenquellen</h2>
                  <p className="text-xs text-slate-500">{freshSourceCount} gesund, {warningSourceCount} warnung, {offlineSourceCount} offline</p>
                </div>
              </div>
              
              {/* Donut Chart */}
              <div className="flex items-center gap-4">
                <CircularProgress 
                  value={freshSourceCount} 
                  max={Object.keys(healthSources).length || 1} 
                  color="#22c55e" 
                  size={70}
                />
              </div>
            </div>

            {/* Data Source List */}
            <div className="space-y-2 max-h-[280px] overflow-y-auto pr-2">
              {Object.entries(healthSources).map(([name, source]) => {
                const isFresh = ["online", "healthy", "connected", "success", "running", "ok"].includes(source.status.toLowerCase());
                const isWarning = ["degraded", "warning", "fallback", "partial"].includes(source.status.toLowerCase());
                
                return (
                  <div 
                    key={name} 
                    className={`flex items-center justify-between p-3 rounded-lg border ${
                      isFresh 
                        ? "border-emerald-500/20 bg-emerald-950/5" 
                        : isWarning 
                          ? "border-amber-500/20 bg-amber-950/5"
                          : "border-red-500/20 bg-red-950/5"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full`} style={{ backgroundColor: getStatusBgColor(source.status) }} />
                      <div>
                        <div className="text-sm font-medium">{name.replace(/_/g, " ")}</div>
                        <div className="text-[10px] text-slate-500">{source.status}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className={`text-xs ${source.latency_ms < 500 ? "text-emerald-400" : source.latency_ms < 1000 ? "text-amber-400" : "text-red-400"}`}>
                        {source.latency_ms.toFixed(0)}ms
                      </div>
                      <div className="text-[10px] text-slate-500">{timeAgo(source.last_update)}</div>
                    </div>
                  </div>
                );
              })}
              
              {!Object.keys(healthSources).length && (
                <div className="text-center py-8 text-slate-500">
                  <Database className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p>Keine Datenquellen-Informationen</p>
                </div>
              )}
            </div>
          </div>

          {/* System Status & Scheduler */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-purple-500/20">
                  <Gauge className="w-5 h-5 text-purple-400" />
                </div>
                <h2 className="text-lg font-semibold">Scheduler</h2>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 text-sm">Status</span>
                  <div className={`flex items-center gap-2 px-2 py-1 rounded-full text-xs ${schedulerStatus?.running ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
                    <Circle className={`w-2 h-2 ${schedulerStatus?.running && "fill-current"}`} />
                    {schedulerStatus?.running ? "AKTIV" : "INAKTIV"}
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 text-sm">Intervall</span>
                  <span className="text-slate-300">{schedulerStatus?.interval_minutes || 5} Min</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 text-sm">Executions</span>
                  <span className="text-slate-300">{schedulerStatus?.total_executions || 0}</span>
                </div>

                <div className="pt-3 border-t border-slate-800">
                  <div className="text-xs text-slate-500 mb-2">Nächster Lauf</div>
                  <div className="text-sm text-indigo-400">
                    {schedulerStatus?.next_run ? new Date(schedulerStatus.next_run).toLocaleTimeString("de-DE") : "—"}
                  </div>
                </div>

                {/* Control Buttons */}
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => controlScheduler("start")}
                    disabled={schedulerStatus?.running}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-700 rounded-lg text-xs transition-colors"
                  >
                    <Play className="w-3 h-3" />
                    Start
                  </button>
                  <button
                    onClick={() => controlScheduler("pause")}
                    disabled={!schedulerStatus?.running}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-700 rounded-lg text-xs transition-colors"
                  >
                    <Pause className="w-3 h-3" />
                    Pause
                  </button>
                </div>
              </div>
            </div>

            <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
              <div className="flex items-center gap-3 mb-4">
                <div className="p-2 rounded-lg bg-orange-500/20">
                  <Zap className="w-5 h-5 text-orange-400" />
                </div>
                <h2 className="text-lg font-semibold">System</h2>
              </div>
              
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 text-sm">Tests</span>
                  <span className="text-slate-300">{testResults?.passed || 0}/{testResults?.total_tests || 0}</span>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 text-sm">Status</span>
                  <span className={`text-xs ${testResults?.overall_status === "success" ? "text-emerald-400" : testResults?.overall_status === "warning" ? "text-amber-400" : "text-red-400"}`}>
                    {testResults?.overall_status?.toUpperCase() || "UNBEKANNT"}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-500 text-sm">Exec Time</span>
                  <span className="text-slate-300">{(testResults?.execution_time_ms || 0).toFixed(0)}ms</span>
                </div>

                <div className="pt-3 border-t border-slate-800">
                  <button
                    onClick={runSystemTest}
                    disabled={loading}
                    className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-700 rounded-lg text-xs transition-colors"
                  >
                    <RefreshCw className={`w-3 h-3 ${loading && "animate-spin"}`} />
                    {loading ? "Läuft..." : "Test Starten"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Latency Chart */}
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-2xl p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                <Activity className="w-5 h-5 text-emerald-400" />
                <h2 className="text-lg font-semibold">API Latenz</h2>
              </div>
              <div className="text-xs text-slate-500">
                Ø {Object.values(healthSources).length > 0 
                  ? (Object.values(healthSources).reduce((a, s) => a + s.latency_ms, 0) / Object.values(healthSources).length).toFixed(0) 
                  : 0}ms
              </div>
            </div>
            <MiniBarChart 
              data={Object.values(healthSources).map(s => s.latency_ms)} 
              color="#22c55e"
            />
            <div className="flex justify-between text-[10px] text-slate-500 mt-2">
              {Object.keys(healthSources).slice(0, 7).map(name => (
                <span key={name} className="truncate max-w-[60px]">{name.replace(/_/g, "")}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function timeAgo(isoStr: string): string {
  if (!isoStr) return "—";
  const diff = Math.floor((Date.now() - new Date(isoStr).getTime()) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

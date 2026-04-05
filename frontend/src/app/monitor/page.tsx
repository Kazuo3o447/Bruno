"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  Server,
  Database,
  Wifi,
  AlertTriangle,
  Cpu,
  HardDrive,
  Zap,
  Play,
  Pause,
  Settings,
  Terminal
} from "lucide-react";

// Types
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

interface AgentStatus {
  agent_id: string;
  status: string;
  last_heartbeat: string;
  age_seconds: number;
  healthy: boolean;
}

interface SchedulerStatus {
  running: boolean;
  paused: boolean;
  interval_minutes: number;
  last_run: string | null;
  next_run: string | null;
  total_executions: number;
}

interface HealthSource {
  status: string;
  latency_ms: number;
  last_update: string;
}

export default function MonitorPage() {
  const [testResults, setTestResults] = useState<SystemTestResponse | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>([]);
  const [schedulerStatus, setSchedulerStatus] = useState<SchedulerStatus | null>(null);
  const [healthSources, setHealthSources] = useState<Record<string, HealthSource>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  const freshSourceCount = Object.values(healthSources).filter(s => ["online", "healthy", "connected", "success", "running", "ok"].includes(s.status.toLowerCase())).length;
  const warningSourceCount = Object.values(healthSources).filter(s => ["degraded", "warning", "fallback", "partial"].includes(s.status.toLowerCase())).length;
  const healthyAgentCount = agentStatuses.filter(a => a.healthy).length;

  const fetchData = useCallback(async () => {
    try {
      const [testRes, agentRes, schedRes, healthRes] = await Promise.allSettled([
        fetch("/api/v1/systemtest/last").then(r => r.ok ? r.json() : null),
        fetch("/api/v1/agents_status").then(r => r.ok ? r.json() : null),
        fetch("/api/v1/systemtest/scheduler/status").then(r => r.ok ? r.json() : null),
        fetch("/api/v1/systemtest/health/sources").then(r => r.ok ? r.json() : null),
      ]);

      if (testRes.status === "fulfilled" && testRes.value) setTestResults(testRes.value);
      if (agentRes.status === "fulfilled" && agentRes.value) {
        setAgentStatuses(agentRes.value.agents || []);
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
      if (res.ok) {
        fetchData();
      }
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
    switch (status) {
      case "success":
      case "online":
      case "healthy":
      case "connected":
        return <CheckCircle className="w-5 h-5 text-emerald-400" />;
      case "error":
      case "offline":
        return <XCircle className="w-5 h-5 text-red-400" />;
      case "warning":
      case "degraded":
        return <AlertTriangle className="w-5 h-5 text-amber-400" />;
      default:
        return <Activity className="w-5 h-5 text-slate-400" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "success":
      case "online":
      case "healthy":
      case "connected":
        return "text-emerald-400 bg-emerald-500/10 border-emerald-800";
      case "error":
      case "offline":
        return "text-red-400 bg-red-500/10 border-red-800";
      case "warning":
      case "degraded":
        return "text-amber-400 bg-amber-500/10 border-amber-800";
      default:
        return "text-slate-400 bg-slate-500/10 border-slate-800";
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white p-4 lg:p-6 space-y-4">
      <div className="rounded-3xl border border-[#1a1a2e] bg-gradient-to-br from-indigo-950/25 via-[#0c0c18] to-[#080810] p-5 lg:p-6">
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-[0.28em] text-slate-500 font-bold">Monitor · Kontrolle</div>
            <h1 className="text-2xl lg:text-3xl font-bold mt-2">System-, API- und Agentengesundheit in Echtzeit</h1>
            <p className="text-sm text-slate-400 mt-2 max-w-3xl">
              Hier siehst du, was gerade wirklich läuft, was zuletzt geprüft wurde und wann der nächste Test ansteht.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-3 min-w-[280px]">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Letzter Test</div>
              <div className="mt-1 text-sm font-semibold text-white">{lastUpdate.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Nächster Test</div>
              <div className="mt-1 text-sm font-semibold text-indigo-400">{schedulerStatus?.next_run ? new Date(schedulerStatus.next_run).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }) : "—"}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Quellen</div>
              <div className="mt-1 text-sm font-semibold text-emerald-400">{freshSourceCount}/{Object.keys(healthSources).length || 0}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-3">
              <div className="text-[10px] uppercase tracking-[0.22em] text-slate-500">Agenten</div>
              <div className="mt-1 text-sm font-semibold text-slate-200">{healthyAgentCount}/{agentStatuses.length || 0}</div>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-950/30 border border-red-800 rounded-xl p-4">
          <AlertTriangle className="w-5 h-5 text-red-400 inline mr-2" />
          <span className="text-red-400">{error}</span>
        </div>
      )}

      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
        <div className={`p-4 rounded-xl border ${getStatusColor(testResults?.overall_status || "unknown")}`}>
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-5 h-5" />
            <span className="text-xs uppercase">System Status</span>
          </div>
          <div className="text-xl font-bold">
            {testResults?.overall_status === "success" ? "HEALTHY" : 
             testResults?.overall_status === "warning" ? "WARNUNG" : 
             testResults?.overall_status === "error" ? "FEHLER" : "UNBEKANNT"}
          </div>
          <div className="text-xs mt-1 opacity-70">
            {testResults?.passed || 0}/{testResults?.total_tests || 0} Tests bestanden
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/20">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-5 h-5 text-slate-400" />
            <span className="text-xs uppercase text-slate-400">Scheduler</span>
          </div>
          <div className={`text-xl font-bold ${schedulerStatus?.running ? "text-emerald-400" : "text-red-400"}`}>
            {schedulerStatus?.running ? "AKTIV" : "INAKTIV"}
          </div>
          <div className="text-xs mt-1 text-slate-500">
            {schedulerStatus?.paused ? "(Pausiert)" : `Intervall: ${schedulerStatus?.interval_minutes || 5}min`}
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/20">
          <div className="flex items-center gap-2 mb-2">
            <Server className="w-5 h-5 text-slate-400" />
            <span className="text-xs uppercase text-slate-400">Agenten</span>
          </div>
          <div className="text-xl font-bold text-slate-300">
            {agentStatuses.filter(a => a.healthy).length}/{agentStatuses.length}
          </div>
          <div className="text-xs mt-1 text-slate-500">
            {agentStatuses.filter(a => !a.healthy).length} nicht gesund
          </div>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-950/20">
          <div className="flex items-center gap-2 mb-2">
            <Wifi className="w-5 h-5 text-slate-400" />
            <span className="text-xs uppercase text-slate-400">Datenquellen</span>
          </div>
          <div className="text-xl font-bold text-slate-300">
            {Object.values(healthSources).filter(s => 
              ["online", "healthy", "connected", "success"].includes(s.status.toLowerCase())
            ).length}/{Object.keys(healthSources).length}
          </div>
          <div className="text-xs mt-1 text-slate-500">Aktive Verbindungen</div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 items-start">
        <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-medium text-slate-300">System-Tests</h3>
            {testResults?.timestamp && (
              <span className="text-xs text-slate-500">
                {new Date(testResults.timestamp).toLocaleString("de-DE")}
              </span>
            )}
          </div>

          <div className="space-y-2">
            {testResults?.tests.map((test, i) => (
              <div key={i} className={`p-3 rounded-lg border ${getStatusColor(test.status)}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {getStatusIcon(test.status)}
                    <div>
                      <div className="text-sm font-medium">{test.name}</div>
                      <div className="text-xs opacity-70">{test.category}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs">{test.response_time_ms.toFixed(0)}ms</div>
                    <div className="text-[10px] opacity-50">{timeAgo(test.timestamp)}</div>
                  </div>
                </div>
                <div className="mt-2 text-xs opacity-80">{test.message}</div>
                {test.details && Object.keys(test.details).length > 0 && (
                  <div className="mt-2 p-2 bg-black/20 rounded text-xs font-mono">
                    {Object.entries(test.details).slice(0, 3).map(([k, v]) => (
                      <div key={k}>{k}: {String(v).slice(0, 50)}</div>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {!testResults?.tests?.length && (
              <div className="text-center py-8 text-slate-500">
                <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p>Keine Test-Ergebnisse vorhanden</p>
                <button
                  onClick={runSystemTest}
                  className="mt-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-sm"
                >
                  System-Test starten
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-4">Agenten-Status</h3>
            <div className="space-y-2">
              {agentStatuses.map((agent) => (
                <div key={agent.agent_id} className="flex items-center justify-between p-3 rounded-lg bg-[#080810]">
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${agent.healthy ? "bg-emerald-400" : "bg-red-400 animate-pulse"}`} />
                    <div>
                      <div className="text-sm font-medium capitalize">{agent.agent_id}</div>
                      <div className="text-xs text-slate-500">{agent.status}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-xs ${agent.age_seconds > 60 ? "text-red-400" : agent.age_seconds > 30 ? "text-amber-400" : "text-emerald-400"}`}>
                      {agent.age_seconds.toFixed(0)}s alt
                    </div>
                    <div className="text-[10px] text-slate-500">{timeAgo(agent.last_heartbeat)}</div>
                  </div>
                </div>
              ))}

              {!agentStatuses.length && (
                <div className="text-center py-4 text-slate-500 text-sm">
                  Keine Agenten-Daten verfügbar
                </div>
              )}
            </div>
          </div>

          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-4">Datenquellen</h3>
            <div className="space-y-2 max-h-[300px] overflow-y-auto">
              {Object.entries(healthSources).map(([name, source]) => (
                <div key={name} className="flex items-center justify-between p-2 rounded-lg bg-[#080810]">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(source.status)}
                    <span className="text-sm">{name}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-slate-400">{source.latency_ms.toFixed(0)}ms</div>
                    <div className="text-[10px] text-slate-500">{timeAgo(source.last_update)}</div>
                  </div>
                </div>
              ))}

              {!Object.keys(healthSources).length && (
                <div className="text-center py-4 text-slate-500 text-sm">
                  Keine Datenquellen-Informationen
                </div>
              )}
            </div>
            <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
              <span>Fresh: {freshSourceCount}</span>
              <span>Warning: {warningSourceCount}</span>
              <span>Healthy Agents: {healthyAgentCount}</span>
            </div>
          </div>

          <div className="bg-[#0c0c18] border border-[#1a1a2e] rounded-xl p-4">
            <h3 className="text-sm font-medium text-slate-300 mb-4">Scheduler Steuerung</h3>
            <div className="flex gap-2">
              <button
                onClick={() => controlScheduler("start")}
                disabled={schedulerStatus?.running}
                className="flex items-center gap-2 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-sm disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                Start
              </button>
              <button
                onClick={() => controlScheduler("pause")}
                disabled={!schedulerStatus?.running || schedulerStatus?.paused}
                className="flex items-center gap-2 px-3 py-2 bg-amber-600 hover:bg-amber-500 rounded-lg text-sm disabled:opacity-50"
              >
                <Pause className="w-4 h-4" />
                Pause
              </button>
              <button
                onClick={() => controlScheduler("stop")}
                disabled={!schedulerStatus?.running}
                className="flex items-center gap-2 px-3 py-2 bg-red-600 hover:bg-red-500 rounded-lg text-sm disabled:opacity-50"
              >
                <XCircle className="w-4 h-4" />
                Stop
              </button>
            </div>

            {schedulerStatus && (
              <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
                <div className="p-2 bg-[#080810] rounded">
                  <span className="text-slate-500">Total Executions:</span>
                  <span className="ml-2 text-slate-300">{schedulerStatus.total_executions}</span>
                </div>
                <div className="p-2 bg-[#080810] rounded">
                  <span className="text-slate-500">Interval:</span>
                  <span className="ml-2 text-slate-300">{schedulerStatus.interval_minutes}min</span>
                </div>
                {schedulerStatus.last_run && (
                  <div className="p-2 bg-[#080810] rounded col-span-2">
                    <span className="text-slate-500">Last Run:</span>
                    <span className="ml-2 text-slate-300">{new Date(schedulerStatus.last_run).toLocaleString("de-DE")}</span>
                  </div>
                )}
                {schedulerStatus.next_run && (
                  <div className="p-2 bg-[#080810] rounded col-span-2">
                    <span className="text-slate-500">Next Run:</span>
                    <span className="ml-2 text-slate-300">{new Date(schedulerStatus.next_run).toLocaleString("de-DE")}</span>
                  </div>
                )}
              </div>
            )}
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

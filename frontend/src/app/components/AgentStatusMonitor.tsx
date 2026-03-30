"use client";

import { useEffect, useState } from "react";

interface Agent {
  agent_id: string;
  status: "idle" | "running" | "error" | "stopped";
  sub_state?: string;
  last_heartbeat: string;
  processed_count: number;
  cpu_usage?: number;
  memory_usage?: number;
  uptime_seconds: number;
  last_error?: string;
  health: "healthy" | "degraded" | "error" | "offline";
}

interface AgentStatusMonitorProps {
  agents?: Agent[];
  isLoading?: boolean;
}

export default function AgentStatusMonitor({ agents: initialAgents, isLoading = false }: AgentStatusMonitorProps) {
  const [agents, setAgents] = useState<Agent[]>(initialAgents || [
    {
      agent_id: "ingestion",
      status: "idle",
      health: "healthy",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "quant",
      status: "idle",
      health: "healthy",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "sentiment",
      status: "idle",
      health: "healthy",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "risk",
      status: "idle",
      health: "healthy",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "execution",
      status: "idle",
      health: "healthy",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
  ]);

  const [wsConnected, setWsConnected] = useState(false);
  const [cascadePulse, setCascadePulse] = useState<any>(null);

  useEffect(() => {
    if (initialAgents) {
      setAgents(initialAgents);
    }
  }, [initialAgents]);

  // WebSocket für Live-Updates
  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws/agents");

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === "agents_status" && message.data?.agents) {
          setAgents(message.data.agents);
        }
        if (message.type === "llm_pulse") {
          setCascadePulse(message.data);
        }
      } catch (error) {
        console.error("Agent WebSocket error:", error);
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    return () => {
      ws.close();
    };
  }, []);

  const getStatusColor = (status: string, health: string) => {
    if (health === "error") return "bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]";
    if (health === "degraded") return "bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]";
    
    switch (status) {
      case "running":
        return "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]";
      case "idle":
        return "bg-sky-400 shadow-[0_0_10px_rgba(56,189,248,0.5)]";
      case "error":
        return "bg-rose-500 shadow-[0_0_10px_rgba(244,63,94,0.5)]";
      case "stopped":
        return "bg-slate-500";
      default:
        return "bg-slate-500";
    }
  };

  const getStatusText = (status: string) => {
    switch (status) {
      case "running":
        return "Aktiv";
      case "idle":
        return "Bereit";
      case "error":
        return "Fehler";
      case "stopped":
        return "Gestoppt";
      default:
        return status;
    }
  };

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  return (
    <div className="bg-[#1a1a2e] rounded-lg p-4">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Agenten-Status</h3>
          <p className="text-sm text-gray-400">Echtzeit-Monitoring aller Trading-Agenten</p>
        </div>
        <div className="flex items-center gap-2">
          <div
            className={`w-2 h-2 rounded-full ${
              wsConnected ? "bg-green-500 animate-pulse" : "bg-red-500"
            }`}
          />
          <span className="text-xs text-gray-400">
            {wsConnected ? "Live" : "Offline"}
          </span>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
        </div>
      ) : (
        <div className="space-y-3">
          {agents.map((agent) => (
            <div
              key={agent.agent_id}
              className="flex items-center justify-between bg-[#2d2d44] rounded-lg p-3"
            >
              <div className="flex items-center gap-3">
                <div
                  className={`w-3 h-3 rounded-full ${getStatusColor(agent.status, agent.health || 'healthy')}`}
                />
                <div>
                  <p className="text-sm font-bold text-white tracking-wider uppercase">
                    {agent.agent_id}
                  </p>
                  <div className="flex flex-col">
                    <p className={`text-[10px] font-mono uppercase ${agent.status === 'running' ? 'text-emerald-400' : 'text-gray-400'}`}>
                      {agent.sub_state || getStatusText(agent.status)}
                    </p>
                    <p className="text-[10px] text-gray-500">
                      Uptime: {formatUptime(agent.uptime_seconds)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-4 text-right">
                <div>
                  <p className="text-xs text-gray-400">Verarbeitet</p>
                  <p className="text-sm font-semibold text-white">
                    {agent.processed_count.toLocaleString()}
                  </p>
                </div>
                {agent.cpu_usage !== undefined && (
                  <div>
                    <p className="text-xs text-gray-400">CPU</p>
                    <p className="text-sm font-semibold text-white">
                      {agent.cpu_usage.toFixed(1)}%
                    </p>
                  </div>
                )}
                {agent.memory_usage !== undefined && (
                  <div>
                    <p className="text-xs text-gray-400">RAM</p>
                    <p className="text-sm font-semibold text-white">
                      {agent.memory_usage.toFixed(0)}MB
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* System Overview */}
      <div className="mt-4 pt-4 border-t border-[#2d2d44]">
        <div className="flex justify-between text-sm">
          <span className="text-gray-400">Aktive Agenten</span>
          <span className="text-white font-semibold">
            {agents.filter((a) => a.status === "running").length} / {agents.length}
          </span>
        </div>
        <div className="flex justify-between text-sm mt-2">
          <span className="text-gray-400">Gesamtverarbeitet</span>
          <span className="text-white font-semibold">
            {agents.reduce((sum, a) => sum + a.processed_count, 0).toLocaleString()}
          </span>
        </div>
      </div>

      {/* Cascade Pulse - Real-time "Brain" Vision */}
      <div className="mt-4 pt-4 border-t border-[#2d2d44]">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2 h-2 rounded-full bg-purple-500 animate-pulse shadow-[0_0_8px_rgba(168,85,247,0.6)]" />
          <h4 className="text-xs font-bold text-gray-300 uppercase tracking-widest">Bruno Brain Pulse</h4>
        </div>
        <div className="bg-[#0f0f1e] rounded p-3 font-mono text-[10px] min-h-[60px] flex flex-col justify-center">
          {cascadePulse ? (
            <div className="flex flex-col gap-1">
              <div className="flex justify-between items-center text-emerald-400">
                <span>STEP: {String(cascadePulse.step).toUpperCase()}</span>
                <span className="text-[8px] text-gray-500">{new Date(cascadePulse.timestamp).toLocaleTimeString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded ${
                  cascadePulse.status === 'aborted' ? 'bg-rose-900/40 text-rose-400' : 
                  cascadePulse.status === 'passed' ? 'bg-emerald-900/40 text-emerald-400' : 
                  'bg-blue-900/40 text-blue-400'
                }`}>
                  {cascadePulse.status.toUpperCase()}
                </span>
                <span className="text-gray-400 truncate">
                  {cascadePulse.data?.reason || cascadePulse.data?.decision || cascadePulse.data?.regime || 'Processing...'}
                </span>
              </div>
            </div>
          ) : (
            <div className="text-gray-600 italic text-center">Warte auf Cascade Signal...</div>
          )}
        </div>
      </div>
    </div>
  );
}

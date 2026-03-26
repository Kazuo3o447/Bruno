"use client";

import { useEffect, useState } from "react";

interface Agent {
  agent_id: string;
  status: "idle" | "running" | "error" | "stopped";
  last_heartbeat: string;
  processed_count: number;
  cpu_usage?: number;
  memory_usage?: number;
  uptime_seconds: number;
  error_message?: string;
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
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "quant",
      status: "idle",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "sentiment",
      status: "idle",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "risk",
      status: "idle",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
    {
      agent_id: "execution",
      status: "idle",
      last_heartbeat: new Date().toISOString(),
      processed_count: 0,
      uptime_seconds: 0,
    },
  ]);

  const [wsConnected, setWsConnected] = useState(false);

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

  const getStatusColor = (status: string) => {
    switch (status) {
      case "running":
        return "bg-green-500";
      case "idle":
        return "bg-yellow-500";
      case "error":
        return "bg-red-500";
      case "stopped":
        return "bg-gray-500";
      default:
        return "bg-gray-500";
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
                  className={`w-3 h-3 rounded-full ${getStatusColor(agent.status)}`}
                />
                <div>
                  <p className="text-sm font-medium text-white capitalize">
                    {agent.agent_id} Agent
                  </p>
                  <p className="text-xs text-gray-400">
                    {getStatusText(agent.status)} • {formatUptime(agent.uptime_seconds)}
                  </p>
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
    </div>
  );
}
